"""
Defines the abstract base class for models.
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path

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
        self.model_dir: Path = self.get_model_dir(
            model_id=self.general_variables.model_id
        )
        self.data_dir: Path = self.model_dir / "deployments" / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.telemetry_path = self.data_dir / "telemetry_logs.json"
        self.permissions = Permissions()

        if not self.telemetry_path.exists():
            with open(self.telemetry_path, "w") as f:
                json.dump([], f)

    @abstractmethod
    def predict(self, **kwargs):
        """
        Abstract method for prediction.
        """
        pass

    def get_model_dir(self, model_id: str) -> Path:
        """
        Returns the directory path for the given model ID.
        """
        return Path(self.general_variables.model_bazaar_dir) / "models" / model_id
