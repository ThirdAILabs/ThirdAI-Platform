"""
Defines NDB model classes for the application.
"""

import ast
import copy
import json
import logging
import os
import pickle
import shutil
import tempfile
import traceback
import uuid
from abc import abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz
import thirdai.neural_db_v2.chunk_stores.constraints as ndbv2_constraints
from file_handler import create_ndb_docs, create_ndbv2_docs
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
    def insert(self, **kwargs: Any) -> List[Dict[str, str]]:
        """
        Inserts documents into the NDB model.
        """
        raise NotImplementedError

    @abstractmethod
    def upvote(
        self, text_pairs: List[inputs.UpvoteInputSingle], token: str, **kwargs: Any
    ) -> None:
        """
        Upvotes entries in the NDB model.
        """
        raise NotImplementedError

    @abstractmethod
    def associate(
        self, text_pairs: List[inputs.AssociateInputSingle], token: str, **kwargs: Any
    ) -> None:
        """
        Associates entries in the NDB model.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, source_ids: List[str], token: str, **kwargs: Any) -> None:
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

        self.reporter.log(
            action="predict",
            model_id=self.general_variables.model_id,
            access_token=kwargs.get("token"),
            train_samples=[{"query": query}],
        )

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

    def delete(self, source_ids: List[str], token: str, **kwargs: Any) -> None:
        """
        Deletes entries from the NDB model.
        """
        self.db.delete(source_ids=source_ids)

        self.reporter.log(
            action="delete",
            model_id=self.general_variables.model_id,
            access_token=token,
            train_samples=[{"source_ids": " ".join(source_ids)}],
            used=True,
        )

    def insert(self, **kwargs: Any) -> List[Dict[str, str]]:
        """
        Inserts documents into the NDB model.
        """
        documents = kwargs.get("documents")

        ndb_docs = create_ndb_docs(documents, self.data_dir)

        source_ids = self.db.insert(sources=ndb_docs)

        self.reporter.log(
            action="insert",
            model_id=self.general_variables.model_id,
            access_token=kwargs.get("token"),
            train_samples=[({"sources_ids": " ".join(source_ids)})],
            used=True,
        )

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


class SingleNDB(NDBV1Model):
    """
    Single instance of the NDB model.
    """

    def __init__(self, write_mode: bool = False) -> None:
        """
        Initializes a single NDB model.
        """
        super().__init__(write_mode)

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


class ShardedNDB(NDBV1Model):
    """
    Sharded instance of the NDB model.
    """

    def __init__(self, write_mode: bool = False) -> None:
        """
        Initializes a sharded NDB model.
        """
        super().__init__(write_mode)

    def load(self, write_mode: bool = False) -> ndb.NeuralDB:
        """
        Loads the sharded NDB model from model path.
        """
        db = ndb.NeuralDB.from_checkpoint(self.model_path, read_only=not write_mode)

        for i in range(db._savable_state.model.num_shards):
            models = []

            for j in range(db._savable_state.model.num_models_per_shard):
                model_shard_num = i * db._savable_state.model.num_models_per_shard + j

                mach_model_pkl = (
                    self.model_dir / str(model_shard_num) / "shard_mach_model.pkl"
                )

                with open(mach_model_pkl, "rb") as pkl:
                    mach_model = pickle.load(pkl)

                models.append(mach_model)

            db._savable_state.model.ensembles[i].models = models

        return db

    def save(self, **kwargs: Any) -> None:
        """
        Saves the sharded NDB model to model path.
        """
        model_dir = self.get_model_dir(kwargs.get("model_id"))
        num_shards = self.db._savable_state.model.num_shards
        backup_dir = None

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                temp_dir = Path(tmpdir) / "latest"
                temp_dir.mkdir(parents=True, exist_ok=True)
                db_copy = copy.deepcopy(self.db)

                for i in range(num_shards):
                    ensemble = db_copy._savable_state.model.ensembles[i]
                    for j, model in enumerate(ensemble.models):
                        model_shard_num = (
                            i * db_copy._savable_state.model.num_models_per_shard + j
                        )
                        shard_dir = temp_dir / str(model_shard_num)
                        shard_dir.mkdir(parents=True, exist_ok=True)
                        mach_model_pkl = shard_dir / "shard_mach_model.pkl"
                        with mach_model_pkl.open("wb") as pkl:
                            pickle.dump(model, pkl)

                for ensemble in db_copy._savable_state.model.ensembles:
                    ensemble.set_model([])

                db_copy.save(save_to=temp_dir / "model.ndb")

                if model_dir.exists():
                    backup_id = str(uuid.uuid4())
                    backup_dir = self.get_model_dir(backup_id)
                    print(f"Creating backup: {backup_id}")
                    shutil.copytree(model_dir, backup_dir)

                    backup_deployments_dir = model_dir / "deployments"
                    latest_deployment_dir = temp_dir / "deployments"
                    if backup_deployments_dir.exists():
                        shutil.copytree(backup_deployments_dir, latest_deployment_dir)

                if model_dir.exists():
                    shutil.rmtree(model_dir)
                shutil.move(temp_dir, model_dir)

                if backup_dir and backup_dir.exists():
                    shutil.rmtree(backup_dir)

        except Exception as err:
            self.logger.error(f"Failed while saving with error: {err}")
            traceback.print_exc()

            if backup_dir and backup_dir.exists():
                if model_dir.exists():
                    shutil.rmtree(model_dir)
                shutil.copytree(backup_dir, model_dir)
                shutil.rmtree(backup_dir)

            raise


class NDBV2Model(NDBModel):
    def __init__(self, write_mode: bool = False):
        super().__init__()

        self.db = self.load(write_mode=write_mode)

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
        token: str,
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

        self.reporter.log(
            action="predict",
            model_id=self.general_variables.model_id,
            access_token=token,
            train_samples=[{"query": query}],
        )

        return inputs.SearchResultsNDB(query_text=query, references=results)

    def insert(
        self, documents: List[Dict[str, Any]], token: str, **kwargs: Any
    ) -> List[Dict[str, str]]:
        # TODO(V2 Support): add flag for upsert
        ndb_docs = create_ndbv2_docs(
            documents=documents,
            doc_save_dir=self.doc_save_path(),
            data_dir=self.data_dir,
        )

        source_ids = self.db.insert(ndb_docs)

        self.reporter.log(
            action="insert",
            model_id=self.general_variables.model_id,
            access_token=token,
            train_samples=[{"sources_ids": " ".join([x.doc_id for x in source_ids])}],
        )

        return [
            {
                "source": doc.reference(0).source,
                "source_id": doc.hash,
            }
            for doc in ndb_docs
        ]

    def upvote(
        self, text_id_pairs: List[inputs.UpvoteInputSingle], token: str, **kwargs: Any
    ) -> None:
        queries = [t.query_text for t in text_id_pairs]
        chunk_ids = [t.reference_id for t in text_id_pairs]
        self.db.upvote(queries=queries, chunk_ids=chunk_ids, **kwargs)

        chunks = self.db.chunk_store.get_chunks(chunk_ids=chunk_ids)

        train_samples = [
            {
                "query_text": query,
                "reference_id": str(id),
                "reference_text": chunk.keywords + " " + chunk.text,
            }
            for query, id, chunk in zip(queries, chunk_ids, chunks)
        ]

        self.reporter.log(
            action="upvote",
            model_id=self.general_variables.model_id,
            train_samples=train_samples,
            access_token=token,
        )

    def associate(
        self, text_pairs: List[inputs.AssociateInputSingle], token: str, **kwargs: Any
    ) -> None:
        sources = [t.source for t in text_pairs]
        targets = [t.target for t in text_pairs]
        self.db.associate(sources=sources, targets=targets, **kwargs)

        self.reporter.log(
            action="associate",
            model_id=self.general_variables.model_id,
            train_samples=[pair.model_dump() for pair in text_pairs],
            access_token=token,
        )

    def delete(self, source_ids: List[str], token: str, **kwargs: Any) -> None:
        for id in source_ids:
            self.db.delete_doc(doc_id=id)

        self.reporter.log(
            action="delete",
            model_id=self.general_variables.model_id,
            access_token=token,
            train_samples=[{"source_ids": " ".join(source_ids)}],
        )

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
