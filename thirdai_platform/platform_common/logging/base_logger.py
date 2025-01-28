import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union

from colorlog import ColoredFormatter

"""
Similar to Loki, VictoriaLogs supports full-text search over the logs. Since, the number of logs can be very large,
it also supports assigning (key,value) pairs to the logs which can be used for filtering the logs.

To make search efficient and more customizable, it also supports marking certain fields as "stream fields".
Searching over stream fields is significantly faster than doing a full text search or simple key-value pair search.

WrappedLogger and all its derived classes should have two methods:
1. logger_keys: Returns a dictionary of key,value pairs enabling searching over logs.
2. stream_fields: Returns a list of fields which should be marked as stream fields in VictoriaLogs.

The fields in stream_fields should not have very high cardinality (i.e. number of unique values should be limited).

Check out this doc to read about how VictoriaLogs stores and retrieves logs:
https://docs.victoriametrics.com/victorialogs/keyconcepts/#stream-fields
"""


class JSONFormatter(logging.Formatter):
    """Formatter that outputs JSON strings with datetime for log files"""

    def format(self, record) -> str:
        # Format the time as string
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # Basic log entry with required fields
        log_entry = {
            "level": record.levelname,
            "service_type": record.name,
            # reserved fields name for VictoriaLogs
            "_time": timestamp,
            "_msg": str(record.msg),
        }

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        return json.dumps(log_entry)


class WrappedLogger:
    """
    A different approach from Python's Logger to make adding extra fields while logging easier.

    ex :
    Python's Logger : logger.info("Hello Shubh", extra={"code": LogCode.CHAT})
    WrappedLogger : logger.info("Hello Shubh", code=LogCode.CHAT)

    Also stores extra fields added to log records which can be used for filtering logs.
    """

    def __init__(
        self,
        log_dir: Path,
        log_prefix: str,
        service_type: str,
        level=logging.INFO,
        add_stream_handler: bool = True,
    ):
        self.logger = self._setup_logger(
            log_dir, log_prefix, service_type, level, add_stream_handler
        )

    @property
    def logger_keys(self) -> Dict[str, Union[str, int]]:
        """Returns key,value pairs that can be used to filter logs"""
        return {}

    @property
    def stream_fields(self) -> List[str]:
        # TODO: Remove stream_fields from Vector Configs and use these keys for indexing logs into unique streams in VictoriaLogs
        """Returns keys used for indexing logs into unique streams in VictoriaLogs"""
        return []

    def _setup_logger(
        self,
        log_dir: Path,
        log_prefix: str,
        service_type: str,
        level: int,
        add_stream_handler: bool,
    ) -> logging.Logger:
        log_dir.mkdir(parents=True, exist_ok=True)
        logger_file_path = log_dir / f"{log_prefix}.log"

        logger = logging.getLogger(service_type)
        logger.setLevel(level)

        # clear any existing handlers
        logger.handlers = []

        file_handler = logging.FileHandler(logger_file_path, mode="a+")
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)

        if add_stream_handler:
            console_formatter = ColoredFormatter(
                "%(log_color)s%(asctime)s - %(levelname)s - %(msg)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red,bg_white",
                },
            )

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
        return logger

    def _log_with_level(self, level: int, msg: str, **extra_fields):
        """Log a message with the specified level and extra fields"""
        logger_keys = self.logger_keys
        extra_fields.update(logger_keys)
        self.logger.log(level, msg, extra={"extra_fields": extra_fields})

    def info(self, msg: str, **extra_fields):
        """Log an info message with extra fields"""
        self._log_with_level(logging.INFO, msg, **extra_fields)

    def debug(self, msg: str, **extra_fields):
        """Log a debug message with extra fields"""
        self._log_with_level(logging.DEBUG, msg, **extra_fields)

    def warning(self, msg: str, **extra_fields):
        """Log a warning message with extra fields"""
        self._log_with_level(logging.WARNING, msg, **extra_fields)

    def error(self, msg: str, **extra_fields):
        """Log an error message with extra fields"""
        self._log_with_level(logging.ERROR, msg, **extra_fields)

    def critical(self, msg: str, **extra_fields):
        """Log a critical message with extra fields"""
        self._log_with_level(logging.CRITICAL, msg, **extra_fields)
