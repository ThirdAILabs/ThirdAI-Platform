from abc import ABC
from logging import Logger
from pathlib import Path

from platform_common.pydantic_models.cloud_credentials import CredentialRegistry
from platform_common.pydantic_models.deployment import DeploymentConfig


class Model(ABC):
    """
    Abstract base class for all models.
    """

    def __init__(self, config: DeploymentConfig, logger: Logger) -> None:
        """
        Initializes model directories and reporter.
        """
        self.config = config
        self.logger = logger

        self.model_dir = self.get_model_dir(self.config.model_id)

        self.logger.info(
            f"Model initialized with model_id: {self.config.model_id} at {self.model_dir}"
        )
        self.data_dir = self.model_dir / "deployments" / "data"

        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Data directory created or exists at {self.data_dir}")

        self.credentials_registry_path = (
            Path(self.config.model_bazaar_dir) / "credentials.json"
        )

        if self.credentials_registry_path.exists():
            with open(self.credentials_registry_path) as file:
                self.credentials_registry = CredentialRegistry.model_validate_json(
                    file.read()
                )
        else:
            self.credentials_registry = CredentialRegistry()

    def get_model_dir(self, model_id: str):
        return Path(self.config.model_bazaar_dir) / "models" / model_id
