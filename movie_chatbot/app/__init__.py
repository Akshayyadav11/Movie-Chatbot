"""
Initialize the application and load configuration.
"""
from .config import LOGGING_CONFIG
import logging.config

# Configure logging when the package is imported
logging.config.dictConfig(LOGGING_CONFIG)

# Import key modules to make them available when importing the package
from .database import get_mongo_client
from .scraper import scrape_imdb_movies
from .scheduler import start_scheduler, init_scheduler, shutdown_scheduler, run_scheduler

__all__ = [
    'get_mongo_client',
    'scrape_imdb_movies',
    'start_scheduler',
    'init_scheduler',
    'shutdown_scheduler',
    'run_scheduler',
]
