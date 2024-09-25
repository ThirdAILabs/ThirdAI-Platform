import time
from pathlib import Path
from typing import List

import thirdai
from config import FileInfo, NDBv1Options, TrainConfig
from exceptional_handler import apply_exception_handler
from models.model import Model
from reporter import Reporter
from thirdai import neural_db as ndb
from utils import (
    check_csv_only,
    check_local_nfs_only,
    convert_supervised_to_ndb_file,
    expand_s3_buckets_and_directories,
    get_directory_size,
)


@apply_exception_handler
class NDBModel(Model):
    report_failure_method = "report_status"

    def __init__(self, config: TrainConfig, reporter: Reporter):
        """
        Initialize the NDBModel with general and NeuralDB-specific options.
        """
        super().__init__(config=config, reporter=reporter)
        self.ndb_options: NDBv1Options = self.config.model_options.ndb_options
        self.model_save_path: Path = self.model_dir / "model.ndb"
        self.logger.info("NDBModel initialized with NeuralDB options.")

        self.unsupervised_checkpoint_config = self.create_checkpoint_config(
            self.get_checkpoint_dir(self.unsupervised_checkpoint_dir)
        )
        self.logger.info(f"Unsupervised checkpoint config created")

        self.supervised_checkpoint_config = self.create_checkpoint_config(
            self.get_checkpoint_dir(self.supervised_checkpoint_dir)
        )
        self.logger.info(f"Supervised checkpoint config created")

    def unsupervised_files(self) -> List[FileInfo]:
        return expand_s3_buckets_and_directories(self.config.data.unsupervised_files)

    def supervised_files(self) -> List[FileInfo]:
        all_files = expand_s3_buckets_and_directories(self.config.data.supervised_files)
        check_csv_only(all_files)
        check_local_nfs_only(all_files)
        return all_files

    def test_files(self) -> List[FileInfo]:
        all_files = expand_s3_buckets_and_directories(self.config.data.test_files)
        check_csv_only(all_files)
        check_local_nfs_only(all_files)
        return all_files

    def create_checkpoint_config(self, dir_path: Path):
        self.logger.info(f"Creating checkpoint config for directory: {dir_path}")
        return (
            ndb.CheckpointConfig(
                checkpoint_dir=dir_path,
                checkpoint_interval=self.ndb_options.checkpoint_interval,
                resume_from_checkpoint=dir_path.exists(),
            )
            if self.ndb_options.checkpoint_interval
            else None
        )

    def get_checkpoint_dir(self, base_checkpoint_dir: Path):
        self.logger.info(f"Getting checkpoint directory: {base_checkpoint_dir}")
        return base_checkpoint_dir

    def get_supervised_files(self, files: List[FileInfo]) -> List[ndb.Sup]:
        """
        Convert files to supervised NDB files.
        Args:
            files (List[FileInfo]): List of file infos for supervised training data.
        Returns:
            List[ndb.Sup]: List of converted supervised NDB files.
        """
        self.logger.info("Converting supervised files.")

        return [convert_supervised_to_ndb_file(file) for file in files]

    def get_ndb_path(self, model_id: str) -> Path:
        """
        Get the path to the NeuralDB checkpoint for a given model ID.
        Args:
            model_id (str): The model ID.
        Returns:
            Path: The path to the NeuralDB checkpoint.
        """
        path = Path(self.config.model_bazaar_dir) / "models" / model_id / "model.ndb"
        self.logger.info(f"NeuralDB path for model {model_id}: {path}")
        return path

    def load_db(self, model_id: str) -> ndb.NeuralDB:
        """
        Load the NeuralDB from a checkpoint.
        Args:
            model_id (str): The model ID.
        Returns:
            ndb.NeuralDB: The loaded NeuralDB instance.
        """
        self.logger.info(f"Loading NeuralDB from checkpoint for model {model_id}")
        return ndb.NeuralDB.from_checkpoint(self.get_ndb_path(model_id))

    def get_db(self) -> ndb.NeuralDB:
        """
        Get the NeuralDB instance, either by loading from a checkpoint or initializing a new one.
        Returns:
            ndb.NeuralDB: The NeuralDB instance.
        """
        if self.config.base_model_id:
            self.logger.info(f"Loading base model {self.config.base_model_id}")
            return self.load_db(self.config.base_model_id)
        self.logger.info("Initializing a new NeuralDB instance.")
        return self.initialize_db()

    def initialize_db(self):
        """
        Initialize a new NeuralDB instance. Must be implemented by subclasses with single training.
        """
        pass

    def get_num_params(self, db: ndb.NeuralDB):
        """
        Get the number of parameters in the model. Must be implemented by subclasses with single training.
        """
        pass

    def get_size_in_memory(self) -> int:
        """
        Get the size of the model in memory. Must be implemented by subclasses with single training
        """
        pass

    def get_latency(self, db: ndb.NeuralDB) -> float:
        """
        Get the latency of the db, Must be implemented by subclasses with single training
        """
        self.logger.info("Measuring latency of the NeuralDB instance.")
        start_time = time.time()

        db.search("Checking for latency", top_k=5)

        latency = time.time() - start_time
        self.logger.info(f"Latency measured: {latency} seconds.")
        return latency

    def save(self, db: ndb.NeuralDB):
        """
        Save the NeuralDB to disk.
        Args:
            db (ndb.NeuralDB): The NeuralDB instance to save.
        """
        self.logger.info(f"Saving NeuralDB to {self.model_save_path}")
        db.save(self.model_save_path)
        self.logger.info("NeuralDB saved successfully.")

    def finalize_training(self, db: ndb.NeuralDB, train_time: int):
        """
        Finalize the training process by saving the model and reporting completion.
        Args:
            db (ndb.NeuralDB): The NeuralDB instance.
        """
        self.logger.info("Finalizing training process.")
        num_params = self.get_num_params(db)

        size = get_directory_size(self.model_save_path)
        size_in_memory = self.get_size_in_memory()
        latency = self.get_latency(db)

        self.reporter.report_complete(
            model_id=self.config.model_id,
            metadata={
                "num_params": str(num_params),
                "size": str(size),
                "size_in_memory": str(size_in_memory),
                "thirdai_version": str(thirdai.__version__),
                "training_time": str(train_time),
                "latency": str(latency),
            },
        )
        self.logger.info("Training finalized and reported successfully.")
