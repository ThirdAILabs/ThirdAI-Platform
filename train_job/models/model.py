from abc import ABC, abstractmethod
from logging import Logger
from pathlib import Path

from config import TrainConfig
from exceptional_handler import apply_exception_handler
from reporter import Reporter

from platform_common.logging import LoggerConfig


@apply_exception_handler
class Model(ABC):
    """
    Abstract base class for a model.
    Provides common initialization and abstract methods for training and evaluation.
    """

    report_failure_method = "report_status"
    logger: Logger = None

    def __init__(self, config: TrainConfig, reporter: Reporter):
        """
        Initialize the model with general and training options, create necessary
        directories, and set up a reporter for status updates.
        """
        self.config: TrainConfig = config
        self.reporter: Reporter = reporter

        # Directory for storing data
        self.data_dir: Path = (
            Path(self.config.model_bazaar_dir) / "data" / self.config.data_id
        )
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Directory for storing model outputs
        self.model_dir: Path = (
            Path(self.config.model_bazaar_dir) / "models" / self.config.model_id
        )
        self.model_dir.mkdir(parents=True, exist_ok=True)

        logger_file_path = self.model_dir / "train.log"
        self.__class__.logger = LoggerConfig(logger_file_path).get_logger(
            "train-logger"
        )

        self.unsupervised_checkpoint_dir: Path = (
            self.model_dir / "checkpoints" / "unsupervised"
        )
        self.supervised_checkpoint_dir: Path = (
            self.model_dir / "checkpoints" / "supervised"
        )

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
