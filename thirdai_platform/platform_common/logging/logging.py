import logging
from pathlib import Path

from colorlog import ColoredFormatter


def setup_logger(
    log_dir: Path, log_prefix: str, level=logging.INFO, add_console_handler: bool = True
):
    log_dir.mkdir(parents=True, exist_ok=True)

    logger_file_path = log_dir / f"{log_prefix}.log"

    # Get the specific logger
    logger = logging.getLogger(log_prefix)
    logger.setLevel(level)

    # Define log format
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Formatter for file logs (no colors)
    file_formatter = logging.Formatter(log_format, datefmt=date_format)

    # File handler setup
    file_handler = logging.FileHandler(logger_file_path, mode="a+")
    file_handler.setFormatter(file_formatter)

    # Add handlers to the logger
    logger.addHandler(file_handler)

    if add_console_handler:
        # Colored Formatter for console output
        colored_formatter = ColoredFormatter(
            "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
            datefmt=date_format,
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
        )

        # Console handler setup
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(colored_formatter)

        logger.addHandler(console_handler)

    # To avoid duplicate logs by disabling propagation
    logger.propagate = False

    return logger


def get_default_logger():
    """Set up and return a default logger."""
    logger = logging.getLogger("default-logger")
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    return logger
