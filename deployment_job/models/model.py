from abc import ABC, abstractmethod
from pathlib import Path

from logger import LoggerConfig


class Model(ABC):
    """
    Abstract base class for all models.
    """

    def __init__(self, model_bazaar_dir: str, model_id: str) -> None:
        """
        Initializes model directories and reporter.
        """
        self.model_bazaar_dir = model_bazaar_dir
        self.model_id = model_id

        self.model_dir = self.get_model_dir(model_id)
        self.data_dir = self.model_dir / "deployments" / "data"

        self.data_dir.mkdir(parents=True, exist_ok=True)

        logger_file_path = self.data_dir / "deployment.log"
        self.logger = LoggerConfig(logger_file_path).get_logger("deployment-logger")

    def get_model_dir(self, model_id: str):
        return Path(self.model_bazaar_dir) / "models" / model_id

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
