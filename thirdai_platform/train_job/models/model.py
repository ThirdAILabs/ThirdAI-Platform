from abc import ABC, abstractmethod
from logging import Logger
from pathlib import Path

import thirdai
from platform_common.pydantic_models.training import TrainConfig
from train_job.exceptional_handler import apply_exception_handler
from train_job.reporter import Reporter


@apply_exception_handler
class Model(ABC):
    """
    Abstract base class for a model.
    Provides common initialization and abstract methods for training and evaluation.
    """

    report_failure_method = "report_status"
    logger: Logger = None

    def __init__(self, config: TrainConfig, reporter: Reporter, logger: Logger):
        """
        Initialize the model with general and training options, create necessary
        directories, and set up a reporter for status updates.
        """
        self.config: TrainConfig = config
        self.reporter: Reporter = reporter
        self.__class__.logger = logger

        self.logger.info(f"THIRDAI VERSION {thirdai.__version__}")

        # Directory for storing data
        self.data_dir: Path = (
            Path(self.config.model_bazaar_dir) / "data" / self.config.data_id
        )
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Data directory created at: {self.data_dir}")

        # Directory for storing model outputs
        self.model_dir: Path = (
            Path(self.config.model_bazaar_dir) / "models" / self.config.model_id
        )
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Model directory created at: {self.model_dir}")

        self.unsupervised_checkpoint_dir: Path = (
            self.model_dir / "checkpoints" / "unsupervised"
        )
        self.supervised_checkpoint_dir: Path = (
            self.model_dir / "checkpoints" / "supervised"
        )

        credentials_registry_path = (
            Path(self.config.model_bazaar_dir) / "credentials.json"
        )

        self.config.populate_credential_registry_and_save(
            registry_path=credentials_registry_path
        )

        self.logger.info(f"Saved credentials at {credentials_registry_path}")

        self.logger.info("Model initialization complete.")

    @abstractmethod
    def train(self, **kwargs):
        """
        Abstract method for training the model. Must be implemented by subclasses.
        """
        pass

    @abstractmethod
    def evaluate(self, **kwargs):
        """
        Abstract method for evaluating the model. Must be implemented by subclasses.
        """
        pass
