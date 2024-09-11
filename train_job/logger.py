import logging

from colorlog import ColoredFormatter


class LoggerConfig:
    _is_configured = False

    def __init__(self, log_file, level=logging.INFO):
        self.log_file = log_file
        self.level = level
        self.setup_logging()

    def setup_logging(self):
        """Set up the logging configuration if it hasn't been done yet."""
        if LoggerConfig._is_configured:
            return

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
        file_handler = logging.FileHandler(self.log_file, mode="a+")
        file_handler.setFormatter(file_formatter)

        # Console handler setup
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(colored_formatter)

        # Basic configuration with multiple handlers
        logging.basicConfig(
            level=self.level,
            format=log_format,
            datefmt=date_format,
            handlers=[file_handler, console_handler],
        )

        LoggerConfig._is_configured = True

    @staticmethod
    def get_logger(name):
        """Retrieve the logger with the given name."""
        logger = logging.getLogger(name)
        if not logger.hasHandlers():
            logger.addHandler(logging.StreamHandler())
        logger.info("Started logging service")
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
