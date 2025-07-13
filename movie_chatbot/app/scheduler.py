import time
import logging
import atexit
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from .scraper import scrape_imdb_movies
from .config import LOGGING_CONFIG

# Configure logging
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None

def init_scheduler():
    """Initialize and return the scheduler with jobs."""
    global scheduler
    if scheduler and scheduler.running:
        return scheduler
        
    scheduler = BackgroundScheduler()
    
    # Add the job to run daily at 3 AM
    scheduler.add_job(
        func=scrape_imdb_movies,
        trigger='cron',
        hour=3,  # 3 AM
        minute=0,
        name='scrape_imdb_movies',
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
