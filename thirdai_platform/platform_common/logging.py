import logging
from pathlib import Path

from colorlog import ColoredFormatter


def setup_logger(log_dir: Path, log_prefix: str, level=logging.INFO):
    log_dir.mkdir(parents=True, exist_ok=True)

    logger_file_path = log_dir / f"{log_prefix}.log"

    # Define log format
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Formatter for file logs (no colors)
    file_formatter = logging.Formatter(log_format, datefmt=date_format)

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

    # File handler setup
    file_handler = logging.FileHandler(logger_file_path, mode="a+")
    file_handler.setFormatter(file_formatter)

    # Console handler setup
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(colored_formatter)

    # Basic configuration with multiple handlers
    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt=date_format,
        handlers=[file_handler, console_handler],
    )


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
