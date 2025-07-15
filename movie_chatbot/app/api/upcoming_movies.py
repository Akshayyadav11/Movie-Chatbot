from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict
from app.database import get_db, get_mongo_client
from app.models import User
from fastapi.templating import Jinja2Templates
from app.scrapers.upcoming_movies_scraper import UpcomingMoviesScraper
from app.auth import get_current_user
import logging

# Initialize templates
templates = Jinja2Templates(directory="app/templates")

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/scrape-upcoming-movies")
async def scrape_upcoming_movies(current_user: dict = Depends(get_current_user)):
    """Scrape upcoming movies from IMDb and store them in MongoDB"""
    try:
        # Initialize scraper
        scraper = UpcomingMoviesScraper()
        
        # Scrape and store movies
        scraper.scrape_and_store_movies()
        
        return {"message": "Successfully scraped and stored upcoming movies"}
        
    except Exception as e:
        logger.error(f"Error scraping upcoming movies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/upcoming-movies")
async def upcoming_movies_list(request: Request, force_scrape: bool = False):
    """Render the upcoming movies list page"""
    try:
        # Get MongoDB collection
        _, _, movies_collection = get_mongo_client()
        if movies_collection is None:
            raise HTTPException(status_code=500, detail="Failed to connect to MongoDB")

        # Force scrape if requested
        if force_scrape:
            logger.info("Force scrape requested")
            scraper = UpcomingMoviesScraper()
            scraper.scrape_and_store_movies(movies_collection)
            time.sleep(2)  # Give some time for the scrape to complete

        # Get upcoming movies
        movies = list(movies_collection.find({"type": "upcoming"}))
        logger.info(f"Found {len(movies)} upcoming movies in database")

        # Sort all movies by title
        movies.sort(key=lambda x: x.get("title", ""))
        logger.info(f"Found {len(movies)} upcoming movies in database")
        
        # Log all movies being included
        for movie in movies:
            logger.info(f"Including movie: {movie.get('title')}")
        
        # Render template with all movies
        return templates.TemplateResponse("upcoming_movies.html", {
            "request": request,
            "movies": movies
        })

    except Exception as e:
        logger.error(f"Error getting upcoming movies: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/upcoming-movies-graph")
async def upcoming_movies_graph(request: Request, force_scrape: bool = False):
    """Render the upcoming movies graph page"""
    try:
        # Get MongoDB collection
        _, _, movies_collection = get_mongo_client()
        if movies_collection is None:
            raise HTTPException(status_code=500, detail="Failed to connect to MongoDB")

        # Force scrape if requested
        if force_scrape:
            logger.info("Force scrape requested")
            scraper = UpcomingMoviesScraper()
            scraper.scrape_and_store_movies(movies_collection)
            time.sleep(2)  # Give some time for the scrape to complete

        # Get upcoming movies
        movies = list(movies_collection.find({"type": "upcoming"}))
        logger.info(f"Found {len(movies)} upcoming movies in database")

        # Sort all movies by title
        movies.sort(key=lambda x: x.get("title", ""))
        logger.info(f"Found {len(movies)} upcoming movies in database")
        
        # Log all movies being included
        for movie in movies:
            logger.info(f"Including movie: {movie.get('title')}")
        
        # Prepare data for the graph template
        movies_by_date = {}
        for movie in movies:
            release_date = movie.get("release_date")
            if release_date:
                if release_date not in movies_by_date:
                    movies_by_date[release_date] = 0
                movies_by_date[release_date] += 1

        # Sort dates
        sorted_dates = sorted(movies_by_date.keys())
        
        # Format dates and counts for display
        formatted_data = {
            "dates": [],
            "counts": []
        }
        
        for date in sorted_dates:
            try:
                month, year = date.split()[:2]
                formatted_date = f"{month} {year}"
            except:
                formatted_date = date
            
            formatted_data["dates"].append(formatted_date)
            formatted_data["counts"].append(movies_by_date[date])

        # Add debug info
        debug_info = {
            "total_movies": len(movies),
            "movies_with_dates": len(movies_by_date),
            "movies_by_date": movies_by_date
        }
        
        # Render template with all movies
        return templates.TemplateResponse("upcoming_movies_graph.html", {
            "request": request,
            "movies": movies,
            "movies_by_date": formatted_data,
            "debug_info": debug_info
        })

    except Exception as e:
        logger.error(f"Error getting upcoming movies: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/upcoming-movies")
async def get_upcoming_movies(force_scrape: bool = False):
    """Get upcoming movies data. If force_scrape is True, will scrape fresh data."""
    try:
        # Get MongoDB collection
        _, _, movies_collection = get_mongo_client()
        if movies_collection is None:
            raise HTTPException(status_code=500, detail="Failed to connect to MongoDB")
            
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
            
        # Group movies by release date
        movies_by_date = {}
        for movie in movies:
            release_date = movie.get("release_date")
            if release_date:
                if release_date not in movies_by_date:
                    movies_by_date[release_date] = []
                movies_by_date[release_date].append(movie)
        
        # Sort movies within each date group by title
        for date_group in movies_by_date.values():
            date_group.sort(key=lambda x: x.get("title", ""))
        
        # Sort date groups by date
        sorted_movies_by_date = dict(sorted(movies_by_date.items()))
        
        # Convert ObjectId to string for JSON response
        for date_group in sorted_movies_by_date.values():
            for movie in date_group:
                movie["_id"] = str(movie["_id"])
        
        return {"movies_by_date": sorted_movies_by_date}

    except Exception as e:
        logger.error(f"Error getting upcoming movies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
