from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict
from app.database import get_db, get_mongo_client
from app.config import MONGODB_DB
from app.models import MovieBase
from app.auth import get_current_user
from app.scrapers.upcoming_movies_scraper import UpcomingMoviesScraper
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upcoming-movies/scrape-upcoming-movies")
async def scrape_upcoming_movies(current_user: dict = Depends(get_current_user)):
    """Scrape upcoming movies from IMDb and store them in MongoDB"""
    try:
        # Get MongoDB client and collection using the global variables
        from app.database import mongo_client, mongo_db, movies_collection, get_mongo_client
        
        # Initialize the MongoDB connection if not already done
        if mongo_client is None:
            get_mongo_client()
        
        # Verify collection exists
        if movies_collection is None:
            raise HTTPException(status_code=500, detail="Failed to access movies collection")
        
        # Initialize scraper
        scraper = UpcomingMoviesScraper()
        
        # Scrape and store movies
        count = scraper.scrape_and_store_movies(movies_collection)
        
        # Get the total count of upcoming movies
        total_count = movies_collection.count_documents({'type': 'upcoming'})
        
        return {
            "message": "Successfully scraped and stored upcoming movies",
            "count": count,
            "total_count": total_count
        }
        
    except Exception as e:
        logger.error(f"Error scraping upcoming movies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/upcoming-movies")
async def get_upcoming_movies(force_scrape: bool = False):
    """Get upcoming movies data. If force_scrape is True, will scrape fresh data."""
    try:
        # Get MongoDB collection using the global variables
        from app.database import mongo_client, mongo_db, movies_collection, get_mongo_client
        
        # Initialize the MongoDB connection if not already done
        if mongo_client is None:
            get_mongo_client()
            
        # Verify collection exists
        if movies_collection is None:
            raise HTTPException(status_code=500, detail="Failed to access movies collection")
            
        # If force_scrape is true or no movies exist, trigger a scrape
        if force_scrape or not list(movies_collection.find({'type': 'upcoming'}).limit(1)):
            scraper = UpcomingMoviesScraper()
            scraper.scrape_and_store_movies(movies_collection)
            
            # Wait a moment for the scraping to complete
            import time
            time.sleep(1)
            
            # Check if movies were actually stored
            movies = list(movies_collection.find({'type': 'upcoming'}))
            if not movies:
                logger.error("No movies found after scraping")
                raise HTTPException(status_code=500, detail="Failed to scrape movies")
        else:
            # Get all upcoming movies
            movies = list(movies_collection.find({'type': 'upcoming'}))
            
        # Convert ObjectId to string for JSON response
        for movie in movies:
            movie["_id"] = str(movie["_id"])
        
        return movies

    except Exception as e:
        logger.error(f"Error getting upcoming movies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
