from abc import ABC, abstractmethod
from logging import Logger
from pathlib import Path

from exceptional_handler import apply_exception_handler
from logger import LoggerConfig
from reporter import Reporter
from options import BaseOptions


@apply_exception_handler
class Model(ABC):
    """
    Abstract base class for a model.
    Provides common initialization and abstract methods for training and evaluation.
    """

    report_failure_method = "report_status"
    logger: Logger = None

    def __init__(self, options: BaseOptions, reporter: Reporter):
        """
        Initialize the model with general and training options, create necessary
        directories, and set up a reporter for status updates.
        """
        self.options: BaseOptions = options
        self.reporter: Reporter = reporter

        # Directory for storing data
        self.data_dir: Path = (
            Path(self.options.model_bazaar_dir) / "data" / self.options.data_id
        )
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Directory for storing model outputs
        self.model_dir: Path = (
            Path(self.options.model_bazaar_dir) / "models" / self.options.model_id
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
