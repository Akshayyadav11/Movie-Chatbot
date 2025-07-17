import logging
import os
import json
from datetime import datetime, timedelta
from typing import List, Generator, Dict, Any, Optional
from urllib.parse import quote

from fastapi import FastAPI, Depends, HTTPException, Request, Form, status, Response, Cookie
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from fastapi.security import OAuth2PasswordRequestForm
from . import auth, database, models, schemas
from .auth import verify_token

# Initialize templates
from fastapi.templating import Jinja2Templates
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
from .scrapers.upcoming_movies_scraper import UpcomingMoviesScraper
from .api.upcoming_movies import router as upcoming_movies_router
from .api.users import router as users_router

app = FastAPI(
    title="Movie Chatbot API",
    description="API for Movie Chatbot application with Admin Panel",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://0.0.0.0:8000"],  # Replace with your actual frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Set-Cookie"],
)

# Token endpoint
@app.post("/api/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # First check if user exists
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Please contact an administrator.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Now verify password
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Create response with cookie
    response = JSONResponse({"access_token": access_token, "token_type": "bearer"})
    response.set_cookie(
        key="token",
        value=access_token,
        httponly=True,  # Prevent JavaScript access for security
        samesite="Lax",  # Allow cross-site requests
        max_age=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert minutes to seconds
        secure=False,  # Set to True in production
        path="/"
    )
    return response

# Admin login route
@app.get("/admin/login")
async def admin_login(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})

# Include routers
# User management route
@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    current_user: models.User = Depends(auth.get_session_user)
):
    return templates.TemplateResponse("admin_users.html", {"request": request})

@app.get("/upcoming-movies", response_class=HTMLResponse)
async def upcoming_movies(
    request: Request,
    current_user: models.User = Depends(auth.get_session_user),
    db: Session = Depends(get_db)
):
    # Get MongoDB collection
    _, _, movies_collection = get_mongo_client()
    if movies_collection is None:
        raise HTTPException(status_code=500, detail="Failed to connect to MongoDB")
        
    from datetime import datetime
    
    # Get current date
    current_date = datetime.now()
    
    # Get all upcoming movies
    movies = list(movies_collection.find({'type': 'upcoming'}))
    
    # Organize movies by release date and filter out past dates
    movies_by_date = {}
    for movie in movies:
        release_date = movie.get('release_date', 'Unknown')
        
        # Skip if release date is None or empty
        if not release_date:
            release_date = 'Unknown'
        
        # Handle known date formats
        if release_date != 'Unknown':
            try:
                # Try parsing with the expected format
                release_dt = datetime.strptime(release_date, '%b %d, %Y')
                
                # Only include movies from today onwards
                if release_dt.date() < current_date.date():
                    continue
                    
                # Format the date consistently
                release_date = release_dt.strftime('%b %d, %Y')
                    
            except (ValueError, TypeError) as e:
                # If date parsing fails, log the error but keep the movie
                logger.warning(f"Could not parse date '{release_date}': {str(e)}")
                release_date = 'Unknown'
            
        if release_date not in movies_by_date:
            movies_by_date[release_date] = []
            
        movies_by_date[release_date].append({
            'title': movie.get('title', ''),
            'url': movie.get('url', ''),
            'release_date': release_date
        })
    
    # Sort movies by release date
    def get_sort_key(date_str):
        try:
            return datetime.strptime(date_str, '%b %d, %Y')
        except (ValueError, TypeError):
            # For 'Unknown' or invalid dates, put them at the end
            return datetime.max
    
    # Sort the dictionary by date
    movies_by_date = dict(sorted(movies_by_date.items(), key=lambda x: get_sort_key(x[0])))
    
    # Calculate total movie count
    total_movies = sum(len(movies) for movies in movies_by_date.values())
    
    return templates.TemplateResponse("upcoming_movies.html", {
        "request": request,
        "movies_by_date": movies_by_date,
        "total_movies": total_movies
    })

# Include routers
app.include_router(upcoming_movies_router, prefix="/api", tags=["upcoming_movies"])
app.include_router(users_router, prefix="/api", tags=["users"])

# Configure static files and templates
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
TEMPLATES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "templates"))

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Configure templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Initialize database tables
init_db()

# Create admin user if it doesn't exist
@app.on_event("startup")
async def create_admin_user():
    from .database import SessionLocal
    from .models import User
    from .auth import get_password_hash
    
    db = SessionLocal()
    try:
        admin_username = "admin@example.com"
        admin_password = "admin123"
        
        # Check if admin user exists
        existing_user = db.query(User).filter(User.username == admin_username).first()
        
        if not existing_user:
            # Create new admin user
            hashed_password = get_password_hash(admin_password)
            admin_user = User(
                username=admin_username,
                email=admin_username,
                hashed_password=hashed_password,
                is_admin=True,
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            logger.info(f"Created new admin user: {admin_username}")
        else:
            logger.info(f"Admin user {admin_username} already exists")
            
    except Exception as e:
        logger.error(f"Error creating admin user: {str(e)}")
    finally:
        db.close()

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
            
        # Initialize and start the scheduler (will run at 3 AM daily)
        from .scheduler import start_scheduler
        start_scheduler()
        
        # Log when the next run will be
        from apscheduler.job import Job
        jobs = start_scheduler().get_jobs()
        if jobs:
            next_run = jobs[0].next_run_time
            logger.info(f"Next scheduled scrape at: {next_run}")
        
        # Log database status
        movie_count = movies_collection.count_documents({})
        logger.info(f"Found {movie_count} movies in database")
        if movie_count == 0:
            logger.info("No movies found in database. First scheduled scrape will run at 3 AM.")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}", exc_info=True)
        raise

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Serve the home page for all users (no authentication required)
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/chat", response_class=HTMLResponse)
async def chat_interface(request: Request, token: str = Cookie(None)):
    # Require authentication for the chatbot interface
    if not token or not verify_token(token):
        return RedirectResponse(url="/admin/login")
    
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
            return {"data": [], "labels": [], "movies": []}
            
        # Group movies by release date
        movie_counts = {}
        for movie in movies:
            if "release_date" in movie:
                try:
                    date_str = movie["release_date"]
                    # Remove any extra spaces
                    date_str = date_str.strip()
                    # Split into month/day and year
                    parts = date_str.split(',')
                    if len(parts) == 2:
                        date_part = parts[0].strip()
                        year = parts[1].strip()
                        full_date_str = f"{date_part}, {year}"
                        movie_counts[full_date_str] = movie_counts.get(full_date_str, 0) + 1
                except Exception as e:
                    logger.error(f"Error processing movie date {date_str}: {str(e)}")
                    continue
        
        # Sort dates in chronological order
        dates = sorted(movie_counts.keys(), key=lambda x: datetime.strptime(x, "%b %d, %Y"))
        
        # Prepare data for chart
        labels = dates
        data = [movie_counts[date] for date in dates]
            
        # Prepare chart data
        chart_data = {
            "labels": labels,
            "data": data
        }
        
        return chart_data
        
    except Exception as e:
        logger.error(f"Error getting movie graph data: {str(e)}")
        return {"data": [], "labels": []}  # Return empty data instead of raising error

@app.get("/movie-graph")
async def movie_graph_page(request: Request):
    """Render the movie graph page"""
    return templates.TemplateResponse("movie_graph.html", {"request": request})
                
               

@app.get("/api/report/download")
async def download_public_report():
    try:
        # Get MongoDB client
        _, _, movies_collection = get_mongo_client()
        if movies_collection is None:
            raise HTTPException(status_code=500, detail="Failed to connect to MongoDB")
            
        # Get current year as both string and integer for comparison
        current_year = datetime.now().year
        current_year_str = str(current_year)
        
        # First try to find movies where year matches as string or integer
        latest_movies = list(movies_collection.find({
            "$and": [
                {
                    "$or": [
                        {"year": current_year},
                        {"year": current_year_str}
                    ]
                },
                {"type": {"$ne": "upcoming"}}  # Exclude upcoming movies
            ]
        })
        .sort("rating", -1)  # Sort by rating (highest first)
        .limit(100))  # Get up to 100 top-rated movies
        
        if not latest_movies:
            # If no movies found for current year, get the latest available movies as fallback
            latest_movies = list(movies_collection.find({"year": {"$ne": None}})
                .sort("year", -1)
                .limit(20))
                
            logger.info(f"No movies found for current year {current_year}, falling back to latest movies")
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
