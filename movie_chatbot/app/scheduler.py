import time
import logging
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from .scraper import scrape_imdb_movies
from .config import LOG_LEVEL, LOG_FORMAT

# Configure logging
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

def run_scheduler():
    """Configure and start the scheduler."""
    # Create the scheduler
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
    atexit.register(lambda: scheduler.shutdown())
    
    try:
        # Start the scheduler
        scheduler.start()
        logger.info("Scheduler started. Press Ctrl+C to exit.")
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()
        logger.info("Scheduler shut down successfully.")

if __name__ == "__main__":
    # Run the scraper immediately when started
    logger.info("Running initial scrape...")
    scrape_imdb_movies()
    
    # Then start the scheduler
    run_scheduler()
