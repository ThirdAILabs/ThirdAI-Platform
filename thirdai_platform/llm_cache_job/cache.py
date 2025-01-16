import os
from abc import ABC, abstractmethod
from logging import Logger
from typing import Any, Dict, List, Optional, Set

from llm_cache_job.utils import CacheInsertLog, UpdateLogger
from thirdai import neural_db_v2 as ndb


class Cache(ABC):
    @abstractmethod
    def suggestions(self, query: str) -> List[Dict[str, Any]]:
        raise NotImplemented

    @abstractmethod
    def query(self, query: str) -> Optional[Dict[str, Any]]:
        raise NotImplemented

    @abstractmethod
    def insert(self, query: str, llm_res: str) -> None:
        raise NotImplemented


def token_similarity(query_tokens: Set[str], cached_query: str) -> float:
    overlap = len(query_tokens.intersection(cached_query.split()))
    return overlap / len(query_tokens)


class NDBSemanticCache(Cache):
    def __init__(self, cache_ndb_path: str, log_dir: str, logger: Logger):
        self.logger = logger
        self.logger.info(f"cache ndb at {cache_ndb_path}")
        if os.path.exists(cache_ndb_path):
            try:
                self.db = ndb.NeuralDB.load(cache_ndb_path)
                self.logger.info("Loaded existing cache model from disk.")
            except Exception as e:
                self.logger.error("Failed to load cache model", exc_info=True)
                raise e
        else:
            try:
                self.db = ndb.NeuralDB(save_path=cache_ndb_path)
                self.logger.info("Initialized new cache model.")
            except Exception as e:
                self.logger.error("Failed to initialize new cache model", exc_info=True)
                raise e
        self.threshold = float(os.getenv("LLM_CACHE_THRESHOLD", "0.95"))
        self.logger.info(f"Cache threshold set to {self.threshold}")

        self.insertion_logger = UpdateLogger(
            os.path.join(log_dir, "llm_cache", "insertions", "new")
        )

    def suggestions(self, query: str) -> List[Dict[str, Any]]:
        self.logger.info(f"Fetching suggestions for query='{query}'")
        if self.db.retriever.retriever.size() == 0:
            self.logger.info("No suggestions found; cache is empty.")
            return []

        results = self.db.search(query=query, top_k=5)

        unique_suggestions = set()
        suggestions = []
        for res, _ in results:
            if res.text in unique_suggestions:
                continue
            suggestions.append({"query": res.text, "query_id": res.chunk_id})
            unique_suggestions.add(res.text)

        return suggestions

    def query(self, query: str) -> Optional[str]:
        self.logger.info(f"Executing cache query for query='{query}'")
        if self.db.retriever.retriever.size() == 0:
            self.logger.info("Cache is empty;")
            return None

        results = self.db.search(query=query, top_k=5)

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

    def queue_insert(self, query: str, llm_res: str, reference_ids: List[int]) -> None:
        self.logger.info(f"Inserting query into cache for query '{query}'")
        self.insertion_logger.log(
            CacheInsertLog(
                query=query,
                llm_res=llm_res,
                reference_ids=reference_ids,
            )
        )

    def insert(self, insertions: List[CacheInsertLog], batch_size: int = 2000):
        i = 0
        while i < len(insertions):
            self.db.insert(
                [
                    ndb.InMemoryText(
                        document_name="",
                        text=insert_log.query,
                        doc_metadata={
                            "llm_res": insert_log.llm_res,
                            "reference_ids": insert_log.reference_ids,
                        },
                    )
                    for insert_log in insertions[i : i + batch_size]
                ]
            )
            i += batch_size
