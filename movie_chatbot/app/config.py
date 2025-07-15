import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path('..') / '.env'
load_dotenv(dotenv_path=env_path)

# Scraper Configuration
SCRAPER_INTERVAL_MINUTES = int(os.getenv('SCRAPER_INTERVAL_MINUTES', '10'))  # Default to 10 minutes
REQUEST_DELAY = int(os.getenv('REQUEST_DELAY', '1'))  # Default to 1 second

# MongoDB Configuration
# In config.py, update the MongoDB configuration section:
is_docker = os.getenv('DOCKER', 'false').lower() == 'true'
MONGODB_HOST = 'mongo' if is_docker else 'localhost'
MONGODB_URL = os.getenv('MONGODB_URL', f'mongodb://{MONGODB_HOST}:27017/')
MONGODB_DB = os.getenv('MONGODB_DB', 'movie_chatbot')

# IMDB Scraper Settings
IMDB_TOP_MOVIES_URL = os.getenv('IMDB_TOP_MOVIES_URL', 'https://www.imdb.com/chart/top/')
SCRAPER_USER_AGENT = os.getenv('SCRAPER_USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36')

# Application Settings
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Logging Configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'level': 'INFO',
        },
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False
        },
        'app': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False
        },
    }
}
