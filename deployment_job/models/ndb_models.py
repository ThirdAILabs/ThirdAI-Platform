"""
Defines NDB model classes for the application.
"""

import ast
import logging
import os
import shutil
import tempfile
import traceback
import uuid
from abc import abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz
import models.ndbv1_parser as ndbv1_parser
import models.ndbv2_parser as ndbv2_parser
import thirdai.neural_db_v2.chunk_stores.constraints as ndbv2_constraints
from chat import llm_providers
from file_handler import FileInfo, expand_s3_buckets_and_directories
from models.model import Model
from pydantic_models import inputs
from thirdai import neural_db as ndb
from thirdai import neural_db_v2 as ndbv2
from thirdai.neural_db_v2.core.types import Chunk
from utils import highlighted_pdf_bytes, new_pdf_chunks, old_pdf_chunks


class NDBModel(Model):
    """
    Base class for NeuralDB (NDB) models.
    """

    @abstractmethod
    def predict(self, query: str, top_k: int, **kwargs: Any) -> inputs.SearchResultsNDB:
        """
        Makes a prediction using the NDB model.
        """
        raise NotImplementedError

    @abstractmethod
    def insert(self, documents: List[FileInfo], **kwargs: Any) -> List[Dict[str, str]]:
        """
        Inserts documents into the NDB model.
        """
        raise NotImplementedError

    @abstractmethod
    def upvote(self, text_pairs: List[inputs.UpvoteInputSingle], **kwargs: Any) -> None:
        """
        Upvotes entries in the NDB model.
        """
        raise NotImplementedError

    @abstractmethod
    def associate(
        self, text_pairs: List[inputs.AssociateInputSingle], **kwargs: Any
    ) -> None:
        """
        Associates entries in the NDB model.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, source_ids: List[str], **kwargs: Any) -> None:
        """
        Deletes entries from the NDB model.
        """
        raise NotImplementedError

    @abstractmethod
    def sources(self) -> List[Dict[str, str]]:
        """
        Retrieves sources from the NDB model.
        """
        raise NotImplementedError

    @abstractmethod
    def highlight_pdf(self, chunk_id: int) -> Tuple[str, Optional[bytes]]:
        """
        Returns the document name, and bytes of the pdf document of the given chunk
        with the chunk highlighted.
        """
        raise NotImplementedError

    @abstractmethod
    def chunks(self, chunk_id: int) -> Optional[Dict[str, Any]]:
        """
        Returns information about the source file that contains the given chunk as
        as well as the other chunks in that file.
        """
        raise NotImplementedError

    @abstractmethod
    def save(self, **kwargs: Any) -> None:
        """
        Saves the NDB model.
        """
        raise NotImplementedError

    def set_chat(self, **kwargs):
        try:
            sqlite_db_path = os.path.join(self.model_dir, "chat_history.db")

            chat_history_sql_uri = f"sqlite:///{sqlite_db_path}"

            llm_chat_interface = llm_providers.get(kwargs.get("provider", "openai"))

            self.chat = llm_chat_interface(
                db=self.db,
                chat_history_sql_uri=chat_history_sql_uri,
                key=self.general_variables.genai_key,
                **kwargs,
            )
        except Exception as err:
            traceback.print_exc()
            self.chat = None


class NDBV1Model(NDBModel):
    """
    Base class for NeuralDBV1 (NDB) models.
    """

    def __init__(self, write_mode: bool = False) -> None:
        """
        Initializes NDB model with paths and NeuralDB.
        """
        super().__init__()
        self.model_path: Path = self.model_dir / "model.ndb"
        self.db: ndb.NeuralDB = self.load(write_mode=write_mode)
        self.set_chat()

    def get_ndb_path(self, model_id: str) -> Path:
        """
        Returns the NDB model path for the given model ID.
        """
        return self.get_model_dir(model_id) / "model.ndb"

    def upvote(
        self, text_id_pairs: List[inputs.UpvoteInputSingle], **kwargs: Any
    ) -> None:
        """
        Upvotes entries in the NDB model.
        """

        self.db.text_to_result_batch(
            text_id_pairs=[
                (text_id_pair.query_text, text_id_pair.reference_id)
                for text_id_pair in text_id_pairs
            ]
        )

    def predict(self, query: str, top_k: int, **kwargs: Any) -> inputs.SearchResultsNDB:
        """
        Makes a prediction using the NDB model.
        """
        constraints: Dict[str, Dict[str, Any]] = kwargs.get("constraints")

        ndb_constraints = {
            key: getattr(ndb, constraints[key]["constraint_type"])(
                **{k: v for k, v in constraints[key].items() if k != "constraint_type"}
            )
            for key in constraints.keys()
        }
        references = self.db.search(
            query=query,
            top_k=top_k,
            constraints=ndb_constraints,
            rerank=kwargs.get("rerank", False),
            top_k_rerank=kwargs.get("top_k_rerank", 100),
            rerank_threshold=kwargs.get("rerank_threshold", 1.5),
            top_k_threshold=kwargs.get("top_k_threshold", 10),
        )
        pydantic_references = [
            inputs.convert_reference_to_pydantic(ref, kwargs.get("context_radius", 1))
            for ref in references
        ]

        return inputs.SearchResultsNDB(
            query_text=query,
            references=pydantic_references,
        )

    def associate(
        self, text_pairs: List[inputs.AssociateInputSingle], **kwargs: Any
    ) -> None:
        """
        Associates entries in the NDB model.
        """
        self.db.associate_batch(
            text_pairs=[
                (text_pair.source, text_pair.target) for text_pair in text_pairs
            ]
        )

    def sources(self) -> List[Dict[str, str]]:
        """
        Retrieves sources from the NDB model.
        """
        return sorted(
            [
                {
                    "source": doc.source,
                    "source_id": doc.hash,
                }
                for doc, _ in self.db._savable_state.documents.registry.values()
            ],
            key=lambda source: source["source"],
        )

    def delete(self, source_ids: List[str], **kwargs: Any) -> None:
        """
        Deletes entries from the NDB model.
        """
        self.db.delete(source_ids=source_ids)

    def insert(self, documents: List[FileInfo], **kwargs: Any) -> List[Dict[str, str]]:
        """
        Inserts documents into the NDB model.
        """
        ndb_docs = [
            ndbv1_parser.parse_doc(doc, self.data_dir)
            for doc in expand_s3_buckets_and_directories(documents)
        ]

        self.db.insert(ndb_docs)

        return [
            {
                "source": doc.reference(0).source,
                "source_id": doc.hash,
            }
            for doc in ndb_docs
        ]

    def highlight_pdf(self, reference_id: int) -> Tuple[str, Optional[bytes]]:
        reference = self.db._savable_state.documents.reference(reference_id)
        return reference.source, highlighted_pdf_bytes(reference)

    def chunks(self, reference_id: int) -> Optional[Dict[str, Any]]:
        reference = self.db.reference(reference_id)
        chunks = new_pdf_chunks(self.db, reference)
        if chunks:
            return chunks
        return old_pdf_chunks(self.db, reference)

    def load(self, write_mode: bool = False) -> ndb.NeuralDB:
        """
        Loads the NDB model from a model path.
        """
        return ndb.NeuralDB.from_checkpoint(self.model_path, read_only=not write_mode)

    def save(self, **kwargs: Any) -> None:
        """
        Saves the NDB model to a model path.
        """
        model_path = self.get_ndb_path(kwargs.get("model_id"))
        temp_dir = None

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_model_path = Path(temp_dir) / "model.ndb"
                self.db.save(save_to=temp_model_path)
                if model_path.exists():
                    backup_id = str(uuid.uuid4())
                    backup_path = self.get_ndb_path(backup_id)
                    print(f"Creating backup: {backup_id}")
                    shutil.copytree(model_path, backup_path)

                if model_path.exists():
                    shutil.rmtree(model_path)
                shutil.move(temp_model_path, model_path)

                if model_path.exists() and "backup_path" in locals():
                    shutil.rmtree(backup_path.parent)

        except Exception as err:
            self.logger.error(f"Failed while saving with error: {err}")
            traceback.print_exc()

            if "backup_path" in locals() and backup_path.exists():
                if model_path.exists():
                    shutil.rmtree(model_path)
                shutil.copytree(backup_path, model_path)
                shutil.rmtree(backup_path.parent)

            raise


class NDBV2Model(NDBModel):
    def __init__(self, write_mode: bool = False):
        super().__init__()

        self.db = self.load(write_mode=write_mode)
        self.set_chat()

    def ndb_save_path(self):
        return os.path.join(self.model_dir, "model.ndb")

    def doc_save_path(self):
        return os.path.join(self.ndb_save_path(), "documents")

    def full_source_path(self, document: str) -> str:
        return os.path.join(self.doc_save_path(), document)

    def chunk_to_pydantic_ref(self, chunk: Chunk, score: float) -> inputs.Reference:
        return inputs.Reference(
            id=chunk.chunk_id,
            text=chunk.keywords + " " + chunk.text,
            source=self.full_source_path(chunk.document),
            metadata=chunk.metadata,
            context="",
            source_id=chunk.doc_id,
            score=score,
        )

    def predict(
        self,
        query: str,
        top_k: int,
        constraints: Dict[str, Dict[str, Any]],
        **kwargs: Any,
    ) -> inputs.SearchResultsNDB:
        constraints = {
            key: getattr(ndbv2_constraints, constraint["constraint_type"])(
                **{k: v for k, v in constraint.items() if k != "constraint_type"}
            )
            for key, constraint in constraints.items()
        }

        results = self.db.search(
            query=query, top_k=top_k, constraints=constraints, **kwargs
        )

        results = [self.chunk_to_pydantic_ref(chunk, score) for chunk, score in results]

        return inputs.SearchResultsNDB(query_text=query, references=results)

    def insert(self, documents: List[FileInfo], **kwargs: Any) -> List[Dict[str, str]]:
        # TODO(V2 Support): add flag for upsert

        ndb_docs = [
            ndbv2_parser.parse_doc(
                doc, doc_save_dir=self.doc_save_path(), tmp_dir=self.data_dir
            )
            for doc in expand_s3_buckets_and_directories(documents)
        ]

        self.db.insert(ndb_docs)

        return [
            {
                "source": self.full_source_path(doc.chunks()[0].document.iloc[0]),
                "source_id": doc.doc_id(),
            }
            for doc in ndb_docs
        ]

    def upvote(
        self, text_id_pairs: List[inputs.UpvoteInputSingle], **kwargs: Any
    ) -> None:
        queries = [t.query_text for t in text_id_pairs]
        chunk_ids = [t.reference_id for t in text_id_pairs]
        self.db.upvote(queries=queries, chunk_ids=chunk_ids, **kwargs)

    def associate(
        self, text_pairs: List[inputs.AssociateInputSingle], **kwargs: Any
    ) -> None:
        sources = [t.source for t in text_pairs]
        targets = [t.target for t in text_pairs]
        self.db.associate(sources=sources, targets=targets, **kwargs)

    def delete(self, source_ids: List[str], **kwargs: Any) -> None:
        for id in source_ids:
            self.db.delete_doc(doc_id=id)

    def sources(self) -> List[Dict[str, str]]:
        return sorted(
            [
                {
                    "source": self.full_source_path(doc["document"]),
                    "source_id": doc["doc_id"],
                    "version": doc["doc_version"],
                }
                for doc in self.db.documents()
            ],
            key=lambda x: x["source"],
        )

    def highlight_pdf(self, chunk_id: int) -> Tuple[str, Optional[bytes]]:
        chunk = self.db.chunk_store.get_chunks([chunk_id])
        if not chunk:
            raise ValueError(f"{chunk_id} is not a valid chunk_id")
        chunk = chunk[0]

        source = self.full_source_path(chunk.document)
        if "chunk_boxes" not in chunk.metadata:
            return source, None

        highlights = ast.literal_eval(chunk.metadata["chunk_boxes"])
        doc = fitz.open(source)
        for page, bounding_box in highlights:
            doc[page].add_highlight_annot(fitz.Rect(bounding_box))

        return source, doc.tobytes()

    def chunks(self, chunk_id: int) -> Optional[Dict[str, Any]]:
        chunk = self.db.chunk_store.get_chunks([chunk_id])
        if not chunk:
            raise ValueError(f"{chunk_id} is not a valid chunk_id")
        chunk = chunk[0]
        if "chunk_boxes" not in chunk.metadata:
            return None

        chunk_ids = self.db.chunk_store.get_doc_chunks(
            doc_id=chunk.doc_id, before_version=chunk.doc_version + 1
        )
        chunks = self.db.chunk_store.get_chunks(chunk_ids)

        chunks = list(filter(lambda c: c.doc_version == chunk.doc_version, chunks))

        return {
            "filename": self.full_source_path(chunk.document),
            "id": [c.chunk_id for c in chunks],
            "text": [c.text for c in chunks],
            "boxes": [ast.literal_eval(c.metadata["chunk_boxes"]) for c in chunks],
        }

    def load(self, write_mode: bool = False, **kwargs) -> ndbv2.NeuralDB:
        self.logger.info(
            f"Loading NDBv2 model from {self.ndb_save_path()} read_only={not write_mode}"
        )
        return ndbv2.NeuralDB.load(self.ndb_save_path(), read_only=not write_mode)

    def save(self, model_id: str, **kwargs) -> None:
        def ndb_path(model_id: str):
            return self.get_model_dir(model_id) / "model.ndb"

        model_path = ndb_path(model_id=model_id)
        backup_path = None

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_model_path = Path(temp_dir) / "model.ndb"
                self.db.save(temp_model_path)
                if model_path.exists():
                    backup_id = str(uuid.uuid4())
                    backup_path = ndb_path(backup_id)
                    print(f"Creating backup: {backup_id}")
                    shutil.copytree(model_path, backup_path)

                if model_path.exists():
                    shutil.rmtree(model_path)
                shutil.move(temp_model_path, model_path)

                if model_path.exists() and backup_path is not None:
                    shutil.rmtree(backup_path.parent)

        except Exception as err:
            logging.error(f"Failed while saving with error: {err}")
            traceback.print_exc()

            if backup_path is not None and backup_path.exists():
                if model_path.exists():
                    shutil.rmtree(model_path)
                shutil.copytree(backup_path, model_path)
                shutil.rmtree(backup_path.parent)

            raise
