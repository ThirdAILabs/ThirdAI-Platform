import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import nltk
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


def similarity(query: str, cached_query: str) -> float:
    edits = nltk.edit_distance(query, cached_query, transpositions=True)
    return 1 - edits / len(query)


class NDBSemanticCache(Cache):
    def __init__(self):
        self.db = ndb.NeuralDB(save_path=f"{uuid.uuid4()}.cache")

    def suggestions(self, model_id: str, query: str) -> List[Dict[str, Any]]:
        if self.db.retriever.retriever.size() == 0:
            return []

        results = self.db.search(
            query=query,
            top_k=5,
            constraints={"model_id": constraints.EqualTo(model_id)},
        )
        return [{"query": res[0].text, "query_id": res[0].chunk_id} for res in results]

    def query(self, model_id: str, query: str) -> Optional[str]:
        if self.db.retriever.retriever.size() == 0:
            return None

        results = self.db.search(
            query=query,
            top_k=5,
            constraints={"model_id": constraints.EqualTo(model_id)},
        )

        reranked = sorted(
            [(res[0], similarity(query, res[0].text)) for res in results],
            key=lambda x: x[1],
            reverse=True,
        )

        if len(reranked) > 0 and reranked[0][1] > 0.95:
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
