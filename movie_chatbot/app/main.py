import logging
import os
import json
from datetime import datetime, timedelta
from typing import List, Generator, Dict, Any, Optional
from urllib.parse import quote

from fastapi import FastAPI, Depends, HTTPException, Request, Form, status, Response
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Initialize templates
templates = Jinja2Templates(directory="app/templates")

# Import config first to set up logging
from .config import LOGGING_CONFIG
import logging.config

# Configure logging
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# Import other modules after logging is configured
from . import models, schemas, crud, utils
from .database import get_db, init_db, get_mongo_client
from .scraper import scrape_imdb_movies

app = FastAPI(
    title="Movie Chatbot API",
    description="API for Movie Chatbot application",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database tables
init_db()

# Configure static files
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
TEMPLATES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "templates"))

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

logger.info("Configuring background tasks...")

@app.on_event("startup")
async def startup_event():
    logger.info("Starting application...")
    
    # Initialize MongoDB
    try:
        _, _, movies_collection = get_mongo_client()
        if movies_collection is None:
            logger.error("Failed to initialize MongoDB connection")
            raise Exception("Failed to initialize MongoDB connection")
            
        # Schedule the scraper to run at configured intervals
        utils.schedule_scraping()
        
        # Initial data scraping if no movies exist
        if movies_collection.count_documents({}) == 0:
            logger.info("No movies found in database. Starting initial data scraping...")
            try:
                scrape_imdb_movies()
            except Exception as e:
                logger.error(f"Error during initial scraping: {str(e)}", exc_info=True)
        else:
            logger.info(f"Found {movies_collection.count_documents({})} movies in database")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}", exc_info=True)
        raise

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/graph")
async def get_graph_page(request: Request):
    """
    Render the movie graph page
    """
    return templates.TemplateResponse("movie_graph.html", {"request": request})

@app.post("/api/chat", response_model=schemas.ChatMessage)
async def chat(request: Dict[str, Any]):
    # Debug: Log the incoming request
    logger.info(f"Received chat request: {request}")
    
    # Handle different request formats
    message_text = None
    
    # Case 1: Direct message format
    if 'message' in request:
        message_text = request['message']
    # Case 2: Payload format from frontend
    elif 'payload' in request and isinstance(request['payload'], dict) and 'message' in request['payload']:
        message_text = request['payload']['message']
    # Case 3: Nested message in payload
    elif 'payload' in request and isinstance(request['payload'], str):
        try:
            payload = json.loads(request['payload'])
            if 'message' in payload:
                message_text = payload['message']
        except (json.JSONDecodeError, TypeError):
            pass
    
    if not message_text:
        # No valid message found
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Invalid message format",
                "received_request": request,
                "expected_formats": [
                    {"message": "your message"},
                    {"payload": {"message": "your message"}},
                    "form-data: message=your+message"
                ]
            }
        )
    
    try:
        logger.info(f"Processing message: {message_text}")
        response = utils.process_chat_message(message_text)
        return {"message": response, "is_user": False}
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Error processing your message", "details": str(e)}
        )

@app.get("/api/movies/search")
async def search_movies(query: str, limit: int = 5):
    movies = crud.search_movies(query, limit)
    return movies

@app.get("/api/movies/latest")
async def get_latest_movies(limit: int = 5):
    movies = crud.get_latest_movies(limit)
    return movies

@app.get("/api/movies/upcoming")
async def get_upcoming_movies(limit: int = 5):
    movies = crud.get_upcoming_movies(limit)
    return movies

@app.get("/api/movie/graph")
async def get_movie_graph_data():
    """
    Get movie data for the graph page
    Returns movie release counts per year for current and next year
    """
    try:
        # Get MongoDB client
        _, _, movies_collection = get_mongo_client()
        if movies_collection is None:
            raise HTTPException(status_code=500, detail="Failed to connect to MongoDB")
            
        # Get current year and next year
        current_year = datetime.now().year
        next_year = current_year + 1
        
        # Query movies for current and next year
        movies = list(movies_collection.find({
            "year": {"$exists": True},
            "$or": [
                {"year": {"$regex": f"{current_year}"}},
                {"year": {"$regex": f"{next_year}"}}
            ]
        }).sort("year", 1))
        
        if not movies:
            return {
                "labels": [],
                "data": [],
                "movies": []
            }
        
        # Prepare data for chart
        chart_data = {
            "labels": [],
            "data": [],
            "movies": []
        }
        
        # Group movies by year
        year_movies = {}
        for movie in movies:
            try:
                year = movie.get('year', '')
                title = movie.get('title', '')
                genres = movie.get('genres', [])
                
                if year not in year_movies:
                    year_movies[year] = []
                
                # Store the original year for display
                year_movies[year].append({
                    "title": title,
                    "year": year,  # Store original year
                    "genres": genres
                })
            except Exception as e:
                logger.error(f"Error processing movie {title}: {str(e)}")
                continue
        
        # Prepare chart data
        for year in sorted(year_movies.keys()):
            try:
                # Count movies for this year
                movie_count = len(year_movies[year])
                
                chart_data["labels"].append(year)
                chart_data["data"].append(movie_count)
                chart_data["movies"].extend(year_movies[year])
            except Exception as e:
                logger.error(f"Error processing year {year}: {str(e)}")
                continue
        
        return chart_data
    except Exception as e:
        logger.error(f"Error in get_movie_graph_data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/report/download")
async def download_public_report():
    try:
        # Get MongoDB client
        _, _, movies_collection = get_mongo_client()
        if movies_collection is None:
            raise HTTPException(status_code=500, detail="Failed to connect to MongoDB")
            
        # Get latest movies sorted by year
        latest_movies = list(movies_collection.find({"year": {"$ne": None}})
            .sort("year", -1)
            .limit(20))
        
        if not latest_movies:
            raise HTTPException(status_code=404, detail="No movies found")
            
        # Prepare CSV content
        csv_content = "Title,Year,Rating,Genres\n"
        for movie in latest_movies:
            try:
                title = movie.get('title', '').replace(',', '')
                year = str(movie.get('year', ''))
                rating = str(movie.get('rating', ''))
                genres = '|'.join(movie.get('genres', [])).replace(',', '')
                csv_content += f"{title},{year},{rating},{genres}\n"
            except Exception as e:
                logger.error(f"Error processing movie {movie.get('title', '')}: {str(e)}")
                continue
                
        # Create response
        headers = {
            'Content-Disposition': f'attachment; filename=latest_movies_{datetime.now().strftime("%Y%m%d")}.csv'
        }
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers=headers
        )
    except Exception as e:
        logger.error(f"Error generating public report: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Error generating report: {str(e)}"
        )
