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
from threading import Lock
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz
import platform_common.ndb.ndbv1_parser as ndbv1_parser
import platform_common.ndb.ndbv2_parser as ndbv2_parser
import thirdai.neural_db_v2.chunk_stores.constraints as ndbv2_constraints
from deployment_job.chat import llm_providers
from deployment_job.models.model import Model
from deployment_job.pydantic_models import inputs
from deployment_job.utils import highlighted_pdf_bytes, new_pdf_chunks, old_pdf_chunks
from platform_common.file_handler import FileInfo, expand_s3_buckets_and_directories
from platform_common.pydantic_models.deployment import DeploymentConfig
from thirdai import neural_db as ndb
from thirdai import neural_db_v2 as ndbv2
from thirdai.neural_db_v2.core.types import Chunk


class NDBModel(Model):
    """
    Base class for NeuralDB (NDB) models.
    """

    def __init__(self, config: DeploymentConfig):
        super().__init__(config=config)
        self.chat_instances = {}
        self.chat_instance_lock = Lock()

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

    @abstractmethod
    def load(self, write_mode: bool):
        raise NotImplementedError

    def set_chat(self, **kwargs):
        """
        Set up a chat instance for the given provider, if it hasn't been set already.
        """
        provider = kwargs.get("provider", "openai")

        # This is to handle an issue in which when multiple calls are made in parallel 
        # that create the chat object, the second one fails with a `table already exists`
        # error. This is likely becuase the first call as created the sqlite table but
        # not finished updating the chat_instance map. The GIL likely does not prevent 
        # this because of IO operations related to sqlite.
        with self.chat_instance_lock:
            if provider in self.chat_instances and self.chat_instances[provider]:
                # Chat instance for this provider already exists, do not recreate
                print(f"Chat instance for provider '{provider}' is already set.")
                return
            try:
                sqlite_db_path = os.path.join(
                    self.model_dir, provider, "chat_history.db"
                )

                os.makedirs(os.path.dirname(sqlite_db_path), exist_ok=True)

                chat_history_sql_uri = f"sqlite:///{sqlite_db_path}"

                if provider not in llm_providers:
                    raise ValueError(f"Unsupported chat provider: {provider}")

                llm_chat_interface = llm_providers.get(provider)

                key = kwargs.get("key") or self.config.model_options.genai_key

                # Remove 'key' from kwargs if present
                kwargs.pop("key", None)

                self.chat_instances[provider] = llm_chat_interface(
                    db=self.db,
                    chat_history_sql_uri=chat_history_sql_uri,
                    key=key,
                    base_url=self.config.model_bazaar_endpoint,
                    **kwargs,
                )
            except Exception:
                traceback.print_exc()
                self.chat_instances[provider] = None

    def get_chat(self, provider: str):
        """
        Retrieve the chat instance for the specified provider.
        """
        if provider in self.chat_instances:
            return self.chat_instances[provider]
        else:
            raise ValueError(f"No chat instance available for provider: {provider}")

    def get_ndb_path(self, model_id: str) -> Path:
        """
        Returns the NDB model path for the given model ID.
        """
        return self.get_model_dir(model_id) / "model.ndb"


class NDBV1Model(NDBModel):
    """
    Base class for NeuralDBV1 (NDB) models.
    """

    def __init__(self, config: DeploymentConfig, write_mode: bool = False) -> None:
        """
        Initializes NDB model with paths and NeuralDB.
        """
        super().__init__(config=config)
        self.model_path: Path = self.model_dir / "model.ndb"
        self.db: ndb.NeuralDB = self.load(write_mode=write_mode)
        self.set_chat(provider=self.config.model_options.llm_provider)

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

    def predict(
        self,
        query: str,
        top_k: int,
        constraints: Dict[str, Dict[str, Any]],
        rerank: bool,
        context_radius: int,
        **kwargs: Any,
    ) -> inputs.SearchResultsNDB:
        """
        Makes a prediction using the NDB model.
        """

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
            rerank=rerank,
            top_k_rerank=2 * top_k,
            top_k_threshold=top_k,
        )
        pydantic_references = [
            inputs.convert_reference_to_pydantic(ref, context_radius=context_radius)
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

    def save(self, model_id: str, **kwargs) -> None:
        """
        Saves the NDB model to a model path.
        """
        model_path = self.get_ndb_path(model_id)
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
    def __init__(self, config: DeploymentConfig, write_mode: bool = False):
        super().__init__(config=config)

        self.db = self.load(write_mode=write_mode)
        self.set_chat(provider=self.config.model_options.llm_provider)

    def ndb_save_path(self):
        return os.path.join(self.model_dir, "model.ndb")

    def doc_save_path(self):
        return os.path.join(self.ndb_save_path(), "documents")

    def full_source_path(self, document: str) -> str:
        return os.path.join(self.doc_save_path(), document)

    def chunk_to_pydantic_ref(self, chunk: Chunk, score: float) -> inputs.Reference:
        return inputs.Reference(
            id=chunk.chunk_id,
            text=chunk.text,
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
        rerank: bool,
        **kwargs: Any,
    ) -> inputs.SearchResultsNDB:
        constraints = {
            key: getattr(ndbv2_constraints, constraint["constraint_type"])(
                **{k: v for k, v in constraint.items() if k != "constraint_type"}
            )
            for key, constraint in constraints.items()
        }

        results = self.db.search(
            query=query, top_k=top_k, constraints=constraints, rerank=rerank
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

    def highlight_v1(self, chunk: Chunk) -> Tuple[str, Optional[bytes]]:
        source = self.full_source_path(chunk.document)
        highlights = ast.literal_eval(chunk.metadata["highlight"])

        doc = fitz.open(source)
        for key, val in highlights.items():
            page = doc[key]
            blocks = page.get_text("blocks")
            for i, b in enumerate(blocks):
                if i in val:
                    rect = fitz.Rect(b[:4])
                    page.add_highlight_annot(rect)

        return source, doc.tobytes()

    def highlight_v2(self, chunk: Chunk) -> Tuple[str, Optional[bytes]]:
        source = self.full_source_path(chunk.document)
        highlights = ast.literal_eval(chunk.metadata["chunk_boxes"])

        doc = fitz.open(source)
        for page, bounding_box in highlights:
            doc[page].add_highlight_annot(fitz.Rect(bounding_box))

        return source, doc.tobytes()

    def highlight_pdf(self, chunk_id: int) -> Tuple[str, Optional[bytes]]:
        chunk = self.db.chunk_store.get_chunks([chunk_id])
        if not chunk:
            raise ValueError(f"{chunk_id} is not a valid chunk_id")
        chunk = chunk[0]

        if "highlight" in chunk.metadata:
            return self.highlight_v1(chunk)
        elif "chunk_boxes" in chunk.metadata:
            return self.highlight_v2(chunk)
        else:
            return self.full_source_path(chunk.document), None

    def chunks(self, chunk_id: int) -> Optional[Dict[str, Any]]:
        chunk = self.db.chunk_store.get_chunks([chunk_id])
        if not chunk:
            raise ValueError(f"{chunk_id} is not a valid chunk_id")
        chunk = chunk[0]

        chunk_ids = self.db.chunk_store.get_doc_chunks(
            doc_id=chunk.doc_id, before_version=chunk.doc_version + 1
        )
        chunks = self.db.chunk_store.get_chunks(chunk_ids)

        chunks = list(filter(lambda c: c.doc_version == chunk.doc_version, chunks))

        if "chunk_boxes" in chunk.metadata:
            bboxes = [ast.literal_eval(c.metadata["chunk_boxes"]) for c in chunks]
        elif "highlight" in chunk.metadata:
            doc = fitz.open(self.full_source_path(chunk.document))
            page_blocks = [page.get_text("blocks") for page in doc]
            bboxes = [
                [
                    (page_idx, page_blocks[page_idx][i][:4])
                    for page_idx, block_ids in ast.literal_eval(
                        c.metadata["highlight"]
                    ).items()
                    for i in block_ids
                ]
                for c in chunks
            ]
        else:
            return None

        return {
            "filename": self.full_source_path(chunk.document),
            "id": [c.chunk_id for c in chunks],
            "text": [c.text for c in chunks],
            "boxes": bboxes,
        }

    def load(self, write_mode: bool = False, **kwargs) -> ndbv2.NeuralDB:
        self.logger.info(
            f"Loading NDBv2 model from {self.ndb_save_path()} read_only={not write_mode}"
        )
        return ndbv2.NeuralDB.load(self.ndb_save_path(), read_only=not write_mode)

    def save(self, model_id: str, **kwargs) -> None:
        model_path = self.get_ndb_path(model_id)
        backup_path = None

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_model_path = Path(temp_dir) / "model.ndb"
                self.db.save(temp_model_path)
                if model_path.exists():
                    backup_id = str(uuid.uuid4())
                    backup_path = self.get_ndb_path(backup_id)
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
