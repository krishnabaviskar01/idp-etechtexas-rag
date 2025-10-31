"""
Loguru logging configuration
"""
import os
import sys
from datetime import datetime
from loguru import logger

from app.config import settings
from dotenv import load_dotenv
load_dotenv()


def initialize_logger():

    logger_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} |{level: <7}| "
        "{name}:{function}:{line} | {message}"
    )
    # Remove all existing sinks
    logger.remove()

    # Check if ENV is set to local
    env = os.getenv('ENV', '').lower()
    
    if env == 'local':
        # Local environment: use file logging with folder creation
        logs_folder = "logs"
        os.makedirs(logs_folder, exist_ok=True)

        file_path = (
            f"{logs_folder}/"
            f"{datetime.now().strftime('%Y-%m-%d')}/"
            f"{datetime.now().strftime('%H-%M')}.log"
        )
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        logger.add(
            sink=file_path,
            rotation="2 MB",
            retention="10 days",
            format=logger_format,
            level="DEBUG",
            enqueue=True
        )
    else:
        # Non-local environment: use standard output
        logger.add(
            sys.stdout,
            format=logger_format,
            level="DEBUG",
            enqueue=True
        )
    return logger

