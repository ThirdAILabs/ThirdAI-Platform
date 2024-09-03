import os
from abc import ABC, abstractmethod
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
    def __init__(self):
        self.cache_ndb_path = os.path.join(
            os.getenv("MODEL_BAZAAR_DIR"), "llm_cache.ndb"
        )
        print("AT", self.cache_ndb_path)
        if os.path.exists(self.cache_ndb_path):
            self.db = ndb.NeuralDB.load(self.cache_ndb_path)
            print("Loaded existing cache model")
        else:
            self.db = ndb.NeuralDB(save_path=self.cache_ndb_path)
            print("Initilaised new model")
        self.threshold = float(os.getenv("LLM_CACHE_THRESHOLD", "0.95"))

    def suggestions(self, model_id: str, query: str) -> List[Dict[str, Any]]:
        if self.db.retriever.retriever.size() == 0:
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
        if self.db.retriever.retriever.size() == 0:
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
            return {
                "query": reranked[0][0].text,
                "query_id": reranked[0][0].chunk_id,
                "llm_res": reranked[0][0].metadata["llm_res"],
            }

        return None

    def insert(self, model_id: str, query: str, llm_res: str) -> None:
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
        ids = self.db.chunk_store.filter_chunk_ids(
            constraints={"model_id": constraints.EqualTo(model_id)}
        )

        self.db.delete(list(ids))
