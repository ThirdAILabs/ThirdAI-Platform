"""
Defines NDB model classes for the application.
"""

import ast
import os
import shutil
import tempfile
import traceback
import uuid
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import fitz
import platform_common.ndb.ndbv2_parser as ndbv2_parser
import thirdai.neural_db_v2.chunk_stores.constraints as ndbv2_constraints
from deployment_job.chat import llm_providers
from deployment_job.models.model import Model
from deployment_job.pydantic_models import inputs
from deployment_job.utils import acquire_file_lock, release_file_lock
from fastapi import HTTPException, status
from platform_common.file_handler import FileInfo, expand_cloud_buckets_and_directories
from platform_common.logging import JobLogger, LogCode
from platform_common.ndb.utils import delete_docs_and_remove_files
from platform_common.pydantic_models.deployment import DeploymentConfig
from thirdai import neural_db_v2 as ndbv2
from thirdai.neural_db_v2.core.types import Chunk


class NDBModel(Model):
    def __init__(
        self,
        config: DeploymentConfig,
        logger: JobLogger,
        write_mode: bool = False,
    ):
        super().__init__(config=config, logger=logger)

        self.db_lock = Lock()
        self.db = self.load(write_mode=write_mode)

        self.chat_instances = {}
        self.chat_instance_lock = Lock()
        self.set_chat(provider=self.config.model_options.llm_provider)

    def get_ndb_path(self, model_id: str) -> Path:
        """
        Returns the NDB model path for the given model ID.
        """
        return self.get_model_dir(model_id) / "model.ndb"

    def ndb_save_path(self):
        return os.path.join(self.model_dir, "model.ndb")

    def ndb_host_save_path(self):
        return os.path.join(self.host_model_dir, "model.ndb")

    def doc_save_path(self):
        return os.path.join(self.ndb_save_path(), "documents")

    def full_source_path(self, document: str) -> str:
        return os.path.join(self.doc_save_path(), document)

    def chunk_to_pydantic_ref(self, chunk: Chunk, score: float) -> inputs.Reference:
        return inputs.Reference(
            id=chunk.chunk_id,
            text=chunk.text,
            source=self.full_source_path(chunk.document),
            metadata=chunk.metadata or {},
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

        if self.config.autoscaling_enabled:
            results = self.db.search(
                query=query, top_k=top_k, constraints=constraints, rerank=rerank
            )
        else:
            with self.db_lock:
                results = self.db.search(
                    query=query, top_k=top_k, constraints=constraints, rerank=rerank
                )

        results = [self.chunk_to_pydantic_ref(chunk, score) for chunk, score in results]

        return inputs.SearchResultsNDB(query_text=query, references=results)

    def insert(self, documents: List[FileInfo], **kwargs: Any) -> List[Dict[str, str]]:
        # TODO(V2 Support): add flag for upsert

        documents = expand_cloud_buckets_and_directories(documents)
        ndb_docs = [
            ndbv2_parser.parse_doc(
                doc, doc_save_dir=self.doc_save_path(), tmp_dir=self.data_dir
            )
            for doc in documents
        ]

        for i, doc in enumerate(ndb_docs):
            if not doc:
                msg = f"Unable to parse {documents[i].path}. Unsupported file type."
                self.logger.error(msg, code=LogCode.FILE_VALIDATION)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

        with self.db_lock:
            self.db.insert(ndb_docs)

            upsert_doc_ids = [
                doc.source_id
                for doc in documents
                if doc.source_id and doc.options.get("upsert", False)
            ]

            delete_docs_and_remove_files(
                db=self.db,
                doc_ids=upsert_doc_ids,
                full_documents_path=self.doc_save_path(),
                keep_latest_version=True,
            )

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
        with self.db_lock:
            self.db.upvote(queries=queries, chunk_ids=chunk_ids, **kwargs)

    def associate(
        self, text_pairs: List[inputs.AssociateInputSingle], **kwargs: Any
    ) -> None:
        sources = [t.source for t in text_pairs]
        targets = [t.target for t in text_pairs]
        with self.db_lock:
            self.db.associate(sources=sources, targets=targets, **kwargs)

    def delete(self, source_ids: List[str], **kwargs: Any) -> None:
        with self.db_lock:
            delete_docs_and_remove_files(
                db=self.db,
                doc_ids=source_ids,
                full_documents_path=self.doc_save_path(),
                keep_latest_version=False,
            )

    def sources(self) -> List[Dict[str, str]]:
        with self.db_lock:
            docs = self.db.documents()
        return sorted(
            [
                {
                    "source": self.full_source_path(doc["document"]),
                    "source_id": doc["doc_id"],
                    "version": doc["doc_version"],
                }
                for doc in docs
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
        with self.db_lock:
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
        with self.db_lock:
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
        try:
            if self.host_model_dir.parent.exists():
                # This logic for cleaning up of old models assumes there can only be one deployment of a model at a time
                self.logger.info(
                    f"Cleaning up stale model copies at {self.host_model_dir.parent}"
                )

                if write_mode:
                    shutil.rmtree(self.host_model_dir.parent, ignore_errors=True)
                else:
                    deployment_ids = [
                        deployment.name
                        for deployment in self.host_model_dir.parent.iterdir()
                        if deployment.is_dir()
                    ]
                    for deployment_id in deployment_ids:
                        if deployment_id != self.config.deployment_id:
                            shutil.rmtree(
                                self.host_model_dir.parent / deployment_id,
                                ignore_errors=True,
                            )

            if write_mode:
                loaded_ndb = ndbv2.NeuralDB.load(
                    self.ndb_save_path(), read_only=not write_mode
                )

                self.logger.info(
                    f"Loaded NDBv2 model from {self.ndb_save_path()} read_only={not write_mode}",
                    code=LogCode.MODEL_LOAD,
                )

                return loaded_ndb
            else:
                lockfile = os.path.join(self.host_model_dir, "ndb.lock")
                lock = acquire_file_lock(lockfile)
                try:
                    if not os.path.exists(self.ndb_host_save_path()):
                        shutil.copytree(self.ndb_save_path(), self.ndb_host_save_path())
                    else:
                        pass
                finally:
                    release_file_lock(lock)

                loaded_ndb = ndbv2.NeuralDB.load(
                    self.ndb_host_save_path(), read_only=not write_mode
                )

                self.logger.info(
                    f"Loaded NDBv2 model from {self.ndb_host_save_path()} read_only={not write_mode}",
                    code=LogCode.MODEL_LOAD,
                )

                return loaded_ndb
        except Exception as e:
            self.logger.error(
                f"Failed to load NDBv2 model from {self.ndb_save_path() if write_mode else self.ndb_host_save_path()} read_only={not write_mode}",
                code=LogCode.MODEL_LOAD,
            )
            raise e

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
                    self.logger.debug(
                        f"Creating backup: {backup_id}", code=LogCode.MODEL_SAVE
                    )
                    shutil.copytree(model_path, backup_path)

                if model_path.exists():
                    shutil.rmtree(model_path)

                self.logger.debug(
                    f"Moving temp model to {model_path}", code=LogCode.MODEL_SAVE
                )
                shutil.move(temp_model_path, model_path)

                if model_path.exists() and backup_path is not None:
                    shutil.rmtree(backup_path.parent)

                self.logger.info(
                    f"Saved NDBv2 model to {model_path}", code=LogCode.MODEL_SAVE
                )

        except Exception as err:
            self.logger.error(
                f"Failed while saving with error: {err}", code=LogCode.MODEL_SAVE
            )
            traceback.print_exc()

            if backup_path is not None and backup_path.exists():
                if model_path.exists():
                    shutil.rmtree(model_path)
                shutil.copytree(backup_path, model_path)
                shutil.rmtree(backup_path.parent)

            raise err

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
                self.logger.info(
                    f"Chat instance for provider '{provider}' is already set.",
                    code=LogCode.CHAT,
                )
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
                self.logger.info(
                    f"Chat instance set for provider '{provider}'", code=LogCode.CHAT
                )
            except Exception:
                self.logger.error(
                    f"Error setting chat instance for provider '{provider}': {traceback.format_exc()}",
                    code=LogCode.CHAT,
                )
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

    def cleanup(self):
        if self.config.autoscaling_enabled:
            del self.db
            self.logger.info(f"Cleaning up model at {self.host_model_dir}")
            shutil.rmtree(self.host_model_dir, ignore_errors=True)
