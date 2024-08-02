import pickle
import time
from pathlib import Path

import thirdai
from exceptional_handler import apply_exception_handler
from models.ndb_model_interface import NDBModel
from thirdai import data
from thirdai.neural_db.documents import DocumentDataSource
from thirdai.neural_db.models.mach import Mach
from thirdai.neural_db.supervised_datasource import SupDataSource
from thirdai.neural_db.trainer.training_data_manager import (
    InsertDataManager,
    SupervisedDataManager,
)
from thirdai.neural_db.trainer.training_progress_manager import (
    TrainingProgressManager as TPM,
)
from utils import no_op
from variables import MachVariables, ShardVariables


@apply_exception_handler
class ShardMach(NDBModel):
    report_failure_method = "report_shard_train_status"

    def __init__(self):
        """
        Initialize the ShardMach model with general, NeuralDB-specific, Mach-specific, and Shard-specific variables.
        """
        self.shard_variables: ShardVariables = ShardVariables.load_from_env()
        super().__init__()
        self.mach_variables: MachVariables = MachVariables.load_from_env()
        self.logger.info(
            "ShardMach initialized with Mach-specific and Shard-specific variables."
        )

    def get_checkpoint_dir(self, base_checkpoint_dir: Path):
        checkpoint_dir = base_checkpoint_dir / str(self.shard_variables.shard_num)
        self.logger.info(f"Checkpoint directory set to {checkpoint_dir}")
        return checkpoint_dir

    def get_model_path(self, model_id: str) -> Path:
        """
        Get the path to the model file for a given model ID.
        Args:
            model_id (str): The model ID.
        Returns:
            Path: The path to the model file.
        """
        model_path = (
            Path(self.get_ndb_path(model_id)).parent
            / str(self.shard_variables.shard_num)
            / "shard_mach_model.pkl"
        )
        self.logger.info(f"Model path for model ID {model_id} is {model_path}")
        return model_path

    def get_model(self, data_shard_num: int, model_num_in_shard: int) -> Mach:
        """
        Get the Mach model instance, either from a checkpoint or initialize a new one.
        Args:
            data_shard_num (int): The data shard number.
            model_num_in_shard (int): The model number within the shard.
        Returns:
            Mach: The Mach model instance.
        """
        if self.general_variables.base_model_id:
            base_model_path = self.get_model_path(self.general_variables.base_model_id)
            self.logger.info(f"Loading model from {base_model_path}")

            with base_model_path.open("rb") as pkl:
                model = pickle.load(pkl)
                self.logger.info(f"Loaded model from {base_model_path}")
                return model

        self.logger.info("Initializing a new Mach model instance.")
        return Mach(
            id_col="id",
            id_delimiter=" ",
            query_col="query",
            fhr=self.mach_variables.fhr,
            embedding_dimension=self.mach_variables.embedding_dim,
            extreme_output_dim=self.mach_variables.output_dim,
            extreme_num_hashes=self.mach_variables.extreme_num_hashes,
            mach_index_seed=data_shard_num * 341 + model_num_in_shard * 17,
            hybrid=(
                (self.ndb_variables.retriever == "hybrid")
                if model_num_in_shard == 0
                else False
            ),
            hidden_bias=self.mach_variables.hidden_bias,
            tokenizer=self.mach_variables.tokenizer,
        )

    def get_shard_data(self, path: Path) -> DocumentDataSource:
        """
        Get the shard data from a pickle file.
        Args:
            path (Path): The path to the pickle file.
        Returns:
            DocumentDataSource: The shard data.
        """
        self.logger.info(f"Loading shard data from {path}")
        with path.open("rb") as pkl:
            shard_picklable = pickle.load(pkl)
        shard = DocumentDataSource(
            shard_picklable["id_column"],
            shard_picklable["strong_column"],
            shard_picklable["weak_column"],
        )
        shard.documents = shard_picklable["documents"]
        shard._size = shard_picklable["_size"]
        for i, (doc, _) in enumerate(shard.documents):
            doc.path = Path(f"/shard_{self.shard_variables.shard_num}_doc_{i}.shard")
        self.logger.info(f"Loaded shard data from {path}")
        return shard

    def setup_logging(self):
        """
        Setup logging for training.
        """
        log_path = self.model_dir / f"train-shard-{self.shard_variables.shard_num}.log"
        thirdai.logging.setup(
            log_to_stderr=False,
            path=str(log_path),
            level="info",
        )
        self.logger.info(f"Thirdai logging setup completed. Log file: {log_path}")

    def load_shard_data(self, data_shard_num: int):
        """
        Load the intro and training shard data.
        Args:
            data_shard_num (int): The data shard number.
        Returns:
            tuple: Intro and training shard data.
        """
        self.logger.info(
            f"Loading intro and training shard data for shard number {data_shard_num}"
        )
        intro_shard_path = self.data_dir / f"intro_shard_{data_shard_num}.pkl"
        train_shard_path = self.data_dir / f"train_shard_{data_shard_num}.pkl"

        intro_shard = (
            self.get_shard_data(intro_shard_path) if intro_shard_path.exists() else None
        )
        train_shard = (
            self.get_shard_data(train_shard_path) if train_shard_path.exists() else None
        )

        self.logger.info(
            f"Loaded intro shard: {intro_shard_path.exists()}, training shard: {train_shard_path.exists()}"
        )
        return intro_shard, train_shard

    def get_unsupervised_training_manager(self, mach_model, intro_shard, train_shard):
        """
        Create or load an unsupervised training manager.
        Args:
            mach_model (Mach): The Mach model instance.
            intro_shard (DocumentDataSource): Intro shard data.
            train_shard (DocumentDataSource): Training shard data.
        Returns:
            TrainingProgressManager: The training progress manager instance.
        """
        self.logger.info("Creating unsupervised training manager.")
        if self.unsupervised_checkpoint_config.resume_from_checkpoint:
            datasource_manager = InsertDataManager(
                checkpoint_dir=None,
                intro_source=intro_shard,
                train_source=train_shard,
            )
            self.logger.info("Resuming from checkpoint for unsupervised training.")

            return TPM.from_checkpoint(
                original_mach_model=mach_model,
                checkpoint_config=self.unsupervised_checkpoint_config.get_mach_config(),
                for_supervised=False,
                datasource_manager=datasource_manager,
            )
        else:
            self.logger.info(
                "Creating training manager from scratch for unsupervised training."
            )
            training_manager = TPM.from_scratch_for_unsupervised(
                model=mach_model,
                intro_documents=intro_shard,
                train_documents=train_shard,
                should_train=self.train_variables.unsupervised_train,
                override_number_classes=self.shard_variables.num_classes,
                variable_length=data.transformations.VariableLengthConfig(),
                fast_approximation=self.train_variables.fast_approximation,
                num_buckets_to_sample=self.train_variables.num_buckets_to_sample,
                max_in_memory_batches=self.train_variables.max_in_memory_batches,
                epochs=self.train_variables.unsupervised_epochs,
                learning_rate=self.train_variables.learning_rate,
                batch_size=self.train_variables.batch_size,
                checkpoint_config=self.unsupervised_checkpoint_config.get_mach_config(),
            )
            training_manager.make_preindexing_checkpoint(save_datasource=False)
            self.logger.info("Unsupervised training manager created from scratch.")
            return training_manager

    def get_supervised_training_manager(
        self, mach_model: Mach, supervised_data_source: SupDataSource
    ):
        """
        Create or load a supervised training manager.
        Args:
            mach_model (Mach): The Mach model instance.
            supervised_data_source (SupDataSource): The supervised data source.
        Returns:
            TrainingProgressManager: The training progress manager instance.
        """
        self.logger.info("Creating supervised training manager.")
        if self.supervised_checkpoint_config.resume_from_checkpoint:
            datasource_manager = SupervisedDataManager(
                checkpoint_dir=None, train_source=supervised_data_source
            )
            self.logger.info("Resuming from checkpoint for supervised training.")

            return TPM.from_checkpoint(
                original_mach_model=mach_model,
                checkpoint_config=self.supervised_checkpoint_config.get_mach_config(),
                for_supervised=True,
                datasource_manager=datasource_manager,
            )
        else:
            self.logger.info(
                "Creating training manager from scratch for supervised training."
            )
            training_manager = TPM.from_scratch_for_supervised(
                model=mach_model,
                supervised_datasource=supervised_data_source,
                metrics=self.train_variables.metrics,
                checkpoint_config=self.supervised_checkpoint_config.get_mach_config(),
                learning_rate=self.train_variables.learning_rate,
                epochs=self.train_variables.supervised_epochs,
                max_in_memory_batches=self.train_variables.max_in_memory_batches,
                batch_size=self.train_variables.batch_size,
                disable_finetunable_retriever=self.train_variables.disable_finetunable_retriever,
            )
            training_manager.make_preindexing_checkpoint(save_datasource=False)
            self.logger.info("Supervised training manager created from scratch.")
            return training_manager

    def load_supervised_data(self, data_shard_num: int):
        """
        Load supervised shard data.
        Args:
            data_shard_num (int): The data shard number.
        Returns:
            SupDataSource: The supervised data source.
        """
        self.logger.info(f"Loading supervised shard data")
        supervised_shard_path = self.data_dir / f"supervised_shard_{data_shard_num}.pkl"
        if supervised_shard_path.exists():
            with supervised_shard_path.open("rb") as pkl:
                supervised_shard_picklable = pickle.load(pkl)

            supervised_data_source = SupDataSource(
                query_col=supervised_shard_picklable["query_column"],
                data=supervised_shard_picklable["data"],
                id_delimiter=supervised_shard_picklable["id_delimiter"],
                id_column=supervised_shard_picklable["id_column"],
            )
            self.logger.info("Loaded supervised shard data.")
            return supervised_data_source
        self.logger.info("No supervised shard data found.")
        return None

    def save_model(self, mach_model):
        """
        Save the Mach model to a file.
        Args:
            mach_model (Mach): The Mach model instance.
        """
        shard_model_path = self.get_model_path(self.general_variables.model_id)
        shard_model_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Saving Mach model to {shard_model_path}")
        with shard_model_path.open("wb") as pkl:
            pickle.dump(mach_model, pkl)
        self.logger.info("Saved Mach model")

    def train(self, **kwargs):
        """
        Train the ShardMach model.
        """
        self.logger.info("Training process started.")
        self.reporter.report_shard_train_status(
            self.general_variables.model_id,
            self.shard_variables.shard_num,
            "in_progress",
        )
        self.setup_logging()

        data_shard_num = int(
            self.shard_variables.shard_num / self.ndb_variables.num_models_per_shard
        )
        model_num_in_shard = (
            self.shard_variables.shard_num % self.ndb_variables.num_models_per_shard
        )

        self.logger.info(
            f"Getting model for data shard number {data_shard_num} and model number in shard {model_num_in_shard}"
        )
        start_time = time.time()
        mach_model = self.get_model(data_shard_num, model_num_in_shard)
        test_file = self.data_dir / "test" / f"shard_{data_shard_num}.csv"

        self.logger.info(f"Loading shard data for shard number {data_shard_num}")
        intro_shard, train_shard = self.load_shard_data(data_shard_num)

        if intro_shard and train_shard:
            self.logger.info(
                "Creating unsupervised training manager and indexing documents."
            )
            training_manager = self.get_unsupervised_training_manager(
                mach_model, intro_shard, train_shard
            )
            mach_model.index_documents_impl(
                training_progress_manager=training_manager,
                on_progress=no_op,
                cancel_state=None,
            )
            self.logger.info("Completed unsupervised training and indexing documents.")

            if test_file.exists():
                self.logger.info(f"Evaluating model with test file {test_file}")
                self.evaluate(mach_model, test_file)

        self.logger.info(f"Loading supervised data for shard number {data_shard_num}")
        supervised_data_source = self.load_supervised_data(data_shard_num)
        if supervised_data_source:
            self.logger.info("Creating supervised training manager and training model.")
            training_manager = self.get_supervised_training_manager(
                mach_model, supervised_data_source
            )
            mach_model.supervised_training_impl(
                supervised_progress_manager=training_manager, callbacks=[]
            )
            self.logger.info("Completed supervised training.")

            if test_file.exists():
                self.logger.info(f"Evaluating model with test file {test_file}")
                self.evaluate(mach_model, test_file)

        self.save_model(mach_model)
        total_time = time.time() - start_time
        self.reporter.report_shard_train_status(
            self.general_variables.model_id, self.shard_variables.shard_num, "complete"
        )
        self.logger.info("Training process completed successfully.")
        self.logger.info(f"Total training time: {total_time} seconds")

    def evaluate(self, model: Mach, file: Path, **kwargs):
        """
        Evaluate the Mach model with the given test file.
        Args:
            model (Mach): The Mach model instance.
            file (Path): The path to the test file.
        """
        self.logger.info(f"Evaluating model with file {file}")
        metrics = model.model.evaluate(
            str(file),
            metrics=self.train_variables.metrics,
        )
        self.logger.info(f"For file {file} the metrics are {metrics}")
        print(f"For file {file} the metrics are {metrics}")
