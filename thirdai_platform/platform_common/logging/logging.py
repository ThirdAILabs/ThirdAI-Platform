import logging
import logging.handlers
from pathlib import Path

from colorlog import ColoredFormatter


def setup_logger(
    log_dir: Path,
    log_prefix: str,
    level=logging.INFO,
    configure_root: bool = True,
    rotate: bool = True,
):
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
    if rotate:
        file_handler = logging.handlers.RotatingFileHandler(
            logger_file_path, mode="a+", maxBytes=10**7, backupCount=10
        )
    else:
        file_handler = logging.FileHandler(logger_file_path, mode="a+")
    file_handler.setFormatter(file_formatter)

    # Console handler setup
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(colored_formatter)

    if configure_root:
        # Basic configuration with multiple handlers
        logging.basicConfig(
            level=level,
            format=log_format,
            datefmt=date_format,
            handlers=[file_handler, console_handler],
        )
    else:
        logger = logging.getLogger(log_prefix)
        logger.setLevel(level)
        logger.addHandler(file_handler)
        logger.propagate = False
        return logger
