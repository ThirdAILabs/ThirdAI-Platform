from abc import ABC
from pathlib import Path

from platform_common.logging import LoggerConfig
from platform_common.pydantic_models.deployment import DeploymentConfig


class Model(ABC):
    """
    Abstract base class for all models.
    """

    def __init__(self, config: DeploymentConfig) -> None:
        """
        Initializes model directories and reporter.
        """
        self.config = config

        self.model_dir = self.get_model_dir(self.config.model_id)
        self.data_dir = self.model_dir / "deployments" / "data"

        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.log_dir: Path = (
            Path(self.config.model_bazaar_dir) / "logs" / self.config.model_id
        )

        self.log_dir.mkdir(parents=True, exist_ok=True)

        logger_file_path = self.log_dir / "deployment.log"
        self.logger = LoggerConfig(logger_file_path).get_logger("deployment-logger")

    def get_model_dir(self, model_id: str):
        return Path(self.config.model_bazaar_dir) / "models" / model_id
