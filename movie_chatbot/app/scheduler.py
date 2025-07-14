import time
import logging
import atexit
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from .scrapers.upcoming_movies_scraper import UpcomingMoviesScraper
from .config import LOGGING_CONFIG
from .database import get_mongo_client

# Configure logging
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None

# Initialize scraper instance
global_scraper = UpcomingMoviesScraper()

def init_scheduler():
    """Initialize and return the scheduler with jobs."""
    global scheduler
    if scheduler and scheduler.running:
        return scheduler
        
    scheduler = BackgroundScheduler()
    
    # Get MongoDB collection
    _, _, movies_collection = get_mongo_client()
    
    # Add the job to run daily at 3 AM
    scheduler.add_job(
        func=lambda: global_scraper.scrape_and_store_movies(movies_collection),
        trigger='cron',
        hour=3,  # 3 AM
        minute=0,
        name='scrape_and_store_movies',
        replace_existing=True
    )
    
    # Handle shutdown
    atexit.register(shutdown_scheduler)
    
    return scheduler

def start_scheduler():
    """Start the scheduler in a separate thread."""
    global scheduler
    scheduler = init_scheduler()
    
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started successfully.")
    
    return scheduler

def shutdown_scheduler():
    """Shut down the scheduler."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler shut down successfully.")

def run_scheduler():
    """Run the scheduler in the main thread (for testing)."""
    scheduler = start_scheduler()
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        shutdown_scheduler()

if __name__ == "__main__":
    # Start the scheduler without initial run
    logger.info("Starting scheduler...")
    run_scheduler()
