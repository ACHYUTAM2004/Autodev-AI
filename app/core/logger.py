import logging
import os
import sys
from app.core.config import settings

def setup_logger(name: str = "autodev_ai", log_file: str = "system.log"):
    """
    Configures a logger that outputs to both console and a file.
    The file output is critical for the Debugger Agent to read error logs.
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Console Handler (for real-time monitoring)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler (for Debugger Agent & Output Contract )
    file_path = os.path.join(settings.LOG_DIR, log_file)
    file_handler = logging.FileHandler(file_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

logger = setup_logger()