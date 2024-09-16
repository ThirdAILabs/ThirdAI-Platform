from abc import ABC, abstractmethod
from pathlib import Path

from logger import LoggerConfig
from permissions import Permissions
from reporter import Reporter
from variables import GeneralVariables


class Model(ABC):
    """
    Abstract base class for all models.
    """

    def __init__(self) -> None:
        """
        Initializes model directories and reporter.
        """
        self.general_variables: GeneralVariables = GeneralVariables.load_from_env()
        self.reporter: Reporter = Reporter(self.general_variables.model_bazaar_endpoint)
        self.model_dir: Path = self.general_variables.get_model_dir()

        self.data_dir: Path = self.general_variables.get_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.permissions = Permissions()
        logger_file_path = self.data_dir / "deployment.log"
        self.logger = LoggerConfig(logger_file_path).get_logger("deployment-logger")

    @abstractmethod
    def predict(self, **kwargs):
        """
        Abstract method for prediction.
        """
        pass

    @abstractmethod
    def save(self, **kwargs):
        pass

    @abstractmethod
    def load(self, **kwargs):
        pass
