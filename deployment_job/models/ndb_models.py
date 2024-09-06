"""
Defines NDB model classes for the application.
"""

import copy
import pickle
import shutil
import tempfile
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List

from file_handler import create_ndb_docs
from models.model import Model
from pydantic_models import inputs
from thirdai import neural_db as ndb


class NDBModel(Model):
    """
    Base class for NeuralDB (NDB) models.
    """

    def __init__(self, write_mode: bool = False) -> None:
        """
        Initializes NDB model with paths and NeuralDB.
        """
        super().__init__()
        self.model_path: Path = self.model_dir / "model.ndb"
        self.db: ndb.NeuralDB = self.load(write_mode)

    def get_ndb_path(self, model_id: str) -> Path:
        """
        Returns the NDB model path for the given model ID.
        """
        return self.get_model_dir(model_id) / "model.ndb"

    def upvote(self, **kwargs: Any) -> None:
        """
        Upvotes entries in the NDB model.
        """
        text_id_pairs = kwargs.get("text_id_pairs")

        self.db.text_to_result_batch(
            text_id_pairs=[
                (text_id_pair.query_text, text_id_pair.reference_id)
                for text_id_pair in text_id_pairs
            ]
        )

    def predict(self, **kwargs: Any) -> inputs.SearchResultsNDB:
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
            query=kwargs["query"],
            top_k=kwargs["top_k"],
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
            train_samples=[{"query": kwargs["query"]}],
        )

        return inputs.SearchResultsNDB(
            query_text=kwargs["query"],
            references=pydantic_references,
        )

    def associate(self, **kwargs: Any) -> None:
        """
        Associates entries in the NDB model.
        """
        text_pairs = kwargs.get("text_pairs")

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

    def delete(self, **kwargs: Any) -> None:
        """
        Deletes entries from the NDB model.
        """
        source_ids: List[str] = kwargs.get("source_ids")

        self.db.delete(source_ids=source_ids)

        self.reporter.log(
            action="delete",
            model_id=self.general_variables.model_id,
            access_token=kwargs.get("token"),
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


class SingleNDB(NDBModel):
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
        return ndb.NeuralDB.from_checkpoint(
            self.model_path, read_only=False if write_mode else True
        )

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


class ShardedNDB(NDBModel):
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
        db = ndb.NeuralDB.from_checkpoint(
            self.model_path, read_only=False if write_mode else True
        )

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
