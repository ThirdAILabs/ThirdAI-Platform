import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

import nltk
from thirdai import neural_db_v2 as ndb
from thirdai.neural_db_v2.chunk_stores import constraints


class Cache(ABC):
    @abstractmethod
    def suggestions(self, model_id: str, query: str) -> List[str]:
        raise NotImplemented

    @abstractmethod
    def query(self, model_id: str, query: str) -> Optional[str]:
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

    def suggestions(self, model_id: str, query: str) -> List[str]:
        results = self.db.search(
            query=query,
            top_k=5,
            constraints={"model_id": constraints.EqualTo(model_id)},
        )
        return [res[0].text for res in results]

    def query(self, model_id: str, query: str) -> Optional[str]:
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

        if reranked[0][1] > 0.95:
            return reranked[0][0].metadata["llm_res"]

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
