import os
from abc import ABC, abstractmethod
from logging import Logger
from typing import Any, Dict, List, Optional, Set

from thirdai import neural_db_v2 as ndb
from thirdai.neural_db_v2.chunk_stores import constraints


class Cache(ABC):
    @abstractmethod
    def suggestions(self, model_id: str, query: str) -> List[Dict[str, Any]]:
        raise NotImplemented

    @abstractmethod
    def query(self, model_id: str, query: str) -> Optional[Dict[str, Any]]:
        raise NotImplemented

    @abstractmethod
    def insert(self, model_id: str, query: str, llm_res: str) -> None:
        raise NotImplemented

    @abstractmethod
    def invalidate(self, model_id: str) -> None:
        raise NotImplemented


def token_similarity(query_tokens: Set[str], cached_query: str) -> float:
    overlap = len(query_tokens.intersection(cached_query.split()))
    return overlap / len(query_tokens)


class NDBSemanticCache(Cache):
    def __init__(self, logger: Logger):
        self.logger = logger
        self.cache_ndb_path = os.path.join(
            os.getenv("MODEL_BAZAAR_DIR"), "llm_cache.ndb"
        )
        self.logger.info(f"cache ndb at {self.cache_ndb_path}")
        if os.path.exists(self.cache_ndb_path):
            try:
                self.db = ndb.NeuralDB.load(self.cache_ndb_path)
                self.logger.info("Loaded existing cache model from disk.")
            except Exception as e:
                self.logger.error("Failed to load cache model", exc_info=True)
                raise e
        else:
            try:
                self.db = ndb.NeuralDB(save_path=self.cache_ndb_path)
                self.logger.info("Initialized new cache model.")
            except Exception as e:
                self.logger.error("Failed to initialize new cache model", exc_info=True)
                raise e
        self.threshold = float(os.getenv("LLM_CACHE_THRESHOLD", "0.95"))
        self.logger.info(f"Cache threshold set to {self.threshold}")

    def suggestions(self, model_id: str, query: str) -> List[Dict[str, Any]]:
        self.logger.info(
            f"Fetching suggestions for model_id={model_id}, query='{query}'"
        )
        if self.db.retriever.retriever.size() == 0:
            self.logger.info("No suggestions found; cache is empty.")
            return []

        results = self.db.search(
            query=query,
            top_k=5,
            constraints={"model_id": constraints.EqualTo(model_id)},
        )

        unique_suggestions = set()
        suggestions = []
        for res, _ in results:
            if res.text in unique_suggestions:
                continue
            suggestions.append({"query": res.text, "query_id": res.chunk_id})
            unique_suggestions.add(res.text)

        return suggestions

    def query(self, model_id: str, query: str) -> Optional[str]:
        self.logger.info(
            f"Executing cache query for model_id={model_id}, query='{query}'"
        )
        if self.db.retriever.retriever.size() == 0:
            self.logger.info("Cache is empty;")
            return None

        results = self.db.search(
            query=query,
            top_k=5,
            constraints={"model_id": constraints.EqualTo(model_id)},
        )

        query_tokens = set(query.split())
        reranked = sorted(
            [(res[0], token_similarity(query_tokens, res[0].text)) for res in results],
            key=lambda x: x[1],
            reverse=True,
        )

        if len(reranked) > 0 and reranked[0][1] > self.threshold:
            self.logger.info(
                f"Cache hit with similarity {reranked[0][1]} for query '{query}'"
            )
            return {
                "query": reranked[0][0].text,
                "query_id": reranked[0][0].chunk_id,
                "llm_res": reranked[0][0].metadata["llm_res"],
            }

        self.logger.info("Cache miss or similarity below threshold.")
        return None

    def insert(self, model_id: str, query: str, llm_res: str) -> None:
        self.logger.info(f"Inserting query into cache for model_id={model_id}")
        self.db.insert(
            [
                ndb.InMemoryText(
                    document_name="",
                    text=[query],
                    doc_metadata={"model_id": model_id, "llm_res": llm_res},
                )
            ]
        )

    def invalidate(self, model_id: str) -> None:
        self.logger.info(f"Invalidating cache entries for model_id={model_id}")
        ids = self.db.chunk_store.filter_chunk_ids(
            constraints={"model_id": constraints.EqualTo(model_id)}
        )

        self.db.delete(list(ids))
