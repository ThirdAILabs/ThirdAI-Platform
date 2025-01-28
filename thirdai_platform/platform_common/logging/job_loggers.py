import logging
from pathlib import Path
from typing import Dict, List, Union

from platform_common.logging.base_logger import WrappedLogger


class JobLogger(WrappedLogger):
    def __init__(
        self,
        log_dir: Path,
        log_prefix: str,
        service_type: str,
        model_id: str,
        model_type: str,
        user_id: str,
        level: int = logging.DEBUG,
        add_stream_handler: bool = True,
    ):
        super().__init__(log_dir, log_prefix, service_type, level, add_stream_handler)
        self.model_id = model_id
        self.user_id = user_id
        self.model_type = model_type

    @property
    def logger_keys(self) -> Dict[str, Union[str, int]]:
        return {
            "model_id": self.model_id,
            "model_type": self.model_type,
            "user_id": self.user_id,
        }

    @property
    def stream_fields(self) -> List[str]:
        # not using user_id as it can have high cardinality
        # one to one mapping from model_id to model_type hence, we don't need model_type
        return ["model_id", "service_type"]
