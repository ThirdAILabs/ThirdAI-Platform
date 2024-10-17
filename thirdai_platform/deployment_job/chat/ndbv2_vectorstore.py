import importlib
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, List, Optional, Union

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore


class NeuralDBV2VectorStore(VectorStore):
    """Vectorstore that uses ThirdAI's NeuralDB.

    To use, you should have the ``thirdai[neural_db_v2]`` python package installed.

    Example:
        .. code-block:: python

            from langchain_community.vectorstores import NeuralDBVectorStore
            from thirdai import neural_db_v2 as ndb

            db = ndb.NeuralDB()
            vectorstore = NeuralDBV2VectorStore(db=db)
    """

    def __init__(self, db: Any) -> None:
        self.db = db

    db: Any = None  #: :meta private:
    """NeuralDB instance"""

    class Config:
        extra = "forbid"
        underscore_attrs_are_private = True

    @staticmethod
    def _verify_thirdai_library(thirdai_key: Optional[str] = None):  # type: ignore[no-untyped-def]
        try:
            from thirdai import licensing

            importlib.util.find_spec("thirdai.neural_db_v2")

            licensing.activate(thirdai_key or os.getenv("THIRDAI_KEY"))
        except ImportError:
            raise ImportError(
                "Could not import thirdai python package and neuraldb dependencies. "
                "Please install it with `pip install thirdai[neural_db_v2]`."
            )

    @classmethod
    def from_scratch(  # type: ignore[no-untyped-def, no-untyped-def]
        cls,
        thirdai_key: Optional[str] = None,
        **model_kwargs,
    ):
        """
        Create a NeuralDBV2VectorStore from scratch.

        To use, set the ``THIRDAI_KEY`` environment variable with your ThirdAI
        API key, or pass ``thirdai_key`` as a named parameter.

        Example:
            .. code-block:: python

                from langchain_community.vectorstores import NeuralDBV2VectorStore

                vectorstore = NeuralDBV2VectorStore.from_scratch(
                    thirdai_key="your-thirdai-key",
                )

                vectorstore.insert([
                    "/path/to/doc.pdf",
                    "/path/to/doc.docx",
                    "/path/to/doc.csv",
                ])

                documents = vectorstore.similarity_search("AI-driven music therapy")
        """
        NeuralDBV2VectorStore._verify_thirdai_library(thirdai_key)
        from thirdai import neural_db_v2 as ndb

        return cls(db=ndb.NeuralDB(**model_kwargs))  # type: ignore[call-arg]

    @classmethod
    def from_checkpoint(  # type: ignore[no-untyped-def]
        cls,
        checkpoint: Union[str, Path],
        thirdai_key: Optional[str] = None,
    ):
        """
        Create a NeuralDBV2VectorStore with a base model from a saved checkpoint

        To use, set the ``THIRDAI_KEY`` environment variable with your ThirdAI
        API key, or pass ``thirdai_key`` as a named parameter.

        Example:
            .. code-block:: python

                from langchain_community.vectorstores import NeuralDBVectorStore

                vectorstore = NeuralDBVectorStore.from_checkpoint(
                    checkpoint="/path/to/checkpoint.ndb",
                    thirdai_key="your-thirdai-key",
                )

                vectorstore.insert([
                    "/path/to/doc.pdf",
                    "/path/to/doc.docx",
                    "/path/to/doc.csv",
                ])

                documents = vectorstore.similarity_search("AI-driven music therapy")
        """
        NeuralDBV2VectorStore._verify_thirdai_library(thirdai_key)
        from thirdai import neural_db_v2 as ndb

        return cls(db=ndb.NeuralDB.load(checkpoint))  # type: ignore[call-arg]

    @classmethod
    def from_texts(
        cls,
        texts: List[str],
        embedding: Embeddings,
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> "NeuralDBV2VectorStore":
        """Return VectorStore initialized from texts and embeddings."""
        model_kwargs = {}
        if "thirdai_key" in kwargs:
            model_kwargs["thirdai_key"] = kwargs["thirdai_key"]
            del kwargs["thirdai_key"]
        vectorstore = cls.from_scratch(**model_kwargs)
        vectorstore.add_texts(texts, metadatas, **kwargs)
        return vectorstore

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Run more texts through the embeddings and add to the vectorstore.

        Args:
            texts: Iterable of strings to add to the vectorstore.
            metadatas: Optional list of metadatas associated with the texts.
            kwargs: vectorstore specific parameters

        Returns:
            List of ids from adding the texts into the vectorstore.
        """
        import pandas as pd
        from thirdai import neural_db_v2 as ndb

        df = pd.DataFrame({"texts": texts})
        if metadatas:
            df = pd.concat([df, pd.DataFrame.from_records(metadatas)], axis=1)
        temp = tempfile.NamedTemporaryFile("w", delete=False, delete_on_close=False)  # type: ignore[call-overload]
        df.to_csv(temp)
        source_id = self.insert([ndb.CSV(temp.name)], **kwargs)[0]
        offset = self.db._savable_state.documents.get_source_by_id(source_id)[1]
        return [str(offset + i) for i in range(len(texts))]  # type: ignore[arg-type]

    def insert(  # type: ignore[no-untyped-def, no-untyped-def]
        self,
        sources: List[Any],
        **kwargs,
    ):
        """Inserts files / document sources into the vectorstore.

        Args:
            train: When True this means that the underlying model in the
            NeuralDB will undergo unsupervised pretraining on the inserted files.
            Defaults to True.
            fast_mode: Much faster insertion with a slight drop in performance.
            Defaults to True.
        """
        sources = self._preprocess_sources(sources)
        self.db.insert(
            sources,
            **kwargs,
        )

    def _preprocess_sources(self, sources):  # type: ignore[no-untyped-def]
        """Checks if the provided sources are string paths. If they are, convert
        to NeuralDB document objects.

        Args:
            sources: list of either string paths to PDF, DOCX or CSV files, or
            NeuralDB document objects.
        """
        from thirdai import neural_db_v2 as ndb

        if not sources:
            return sources
        preprocessed_sources = []
        for doc in sources:
            if not isinstance(doc, str):
                preprocessed_sources.append(doc)
            else:
                if doc.lower().endswith(".pdf"):
                    preprocessed_sources.append(ndb.PDF(doc))
                elif doc.lower().endswith(".docx"):
                    preprocessed_sources.append(ndb.DOCX(doc))
                elif doc.lower().endswith(".csv"):
                    preprocessed_sources.append(ndb.CSV(doc))
                else:
                    raise RuntimeError(
                        f"Could not automatically load {doc}. Only files "
                        "with .pdf, .docx, or .csv extensions can be loaded "
                        "automatically. For other formats, please use the "
                        "appropriate document object from the ThirdAI library."
                    )
        preprocessed_sources = [
            ndb.documents.PrebatchedDoc(list(doc.chunks()))
            for doc in preprocessed_sources
        ]
        return preprocessed_sources

    def similarity_search(
        self, query: str, k: int = 10, **kwargs: Any
    ) -> List[Document]:
        """Retrieve {k} contexts with for a given query

        Args:
            query: Query to submit to the model
            k: The max number of context results to retrieve. Defaults to 10.
        """
        try:
            references = self.db.search(query=query, top_k=k, **kwargs)
            return [
                Document(
                    page_content=chunk.keywords + " " + chunk.text,
                    metadata={
                        "document": chunk.document,
                        "metadata": chunk.metadata,
                        "score": score,
                    },
                )
                for chunk, score in references
            ]
        except Exception as e:
            raise ValueError(f"Error while retrieving documents: {e}") from e

    def save(self, path: str):  # type: ignore[no-untyped-def]
        """Saves a NeuralDB instance to disk. Can be loaded into memory by
        calling NeuralDB.from_checkpoint(path)

        Args:
            path: path on disk to save the NeuralDB instance to.
        """
        self.db.save(path)
