"""
Defines the abstract base class for models.
"""

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict

import redis  # type: ignore
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
        self.model_dir: Path = self.get_model_dir(
            model_id=self.general_variables.model_id
        )
        self.data_dir: Path = self.model_dir / "deployments" / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.telemetry_path = self.data_dir / "telemetry_logs.json"

        if not self.telemetry_path.exists():
            with open(self.telemetry_path, "w") as f:
                json.dump([], f)

        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)
        self.permissions = Permissions()
        logger_file_path = self.data_dir / "deployment.log"
        self.logger = LoggerConfig(logger_file_path).get_logger("deployment-logger")

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

    def redis_publish(self, task_id: str, task_data: Dict):
        # Store task data in Redis Hash
        self.redis_client.hset(f"task:{task_id}", mapping=task_data)

        # Index task by model_id in Redis Set
        self.redis_client.sadd(
            f"tasks_by_model:{self.general_variables.model_id}", task_id
        )

    @abstractmethod
    def save(self, **kwargs):
        pass

    @abstractmethod
    def load(self, **kwargs):
        pass
