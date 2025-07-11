import logging
import os
import json
from datetime import timedelta
from typing import List, Generator, Dict, Any, Optional

from fastapi import FastAPI, Depends, HTTPException, Request, Form, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from . import models, schemas, crud, auth, utils
from .database import get_db, init_db, get_mongo_client
from .scraper import scrape_imdb_movies

app = FastAPI()

# Initialize database tables
init_db()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Schedule background scraping job
utils.schedule_scraping()

@app.on_event("startup")
async def startup_event():
    # Initialize MongoDB
    _, _, movies_collection = get_mongo_client()
    
    # Initial data scraping if no movies exist
    if movies_collection.count_documents({}) == 0:
        scrape_imdb_movies()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, current_user: schemas.User = Depends(auth.get_current_admin_user)):
    upcoming_movies = crud.get_upcoming_movies(limit=5)
    latest_movies = crud.get_latest_movies(limit=5)
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "upcoming_movies": upcoming_movies,
        "latest_movies": latest_movies
    })

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
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
    return {"access_token": access_token, "token_type": "bearer"}

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The message to process")

class PayloadRequest(BaseModel):
    message: str

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

# Admin endpoints
@app.post("/api/admin/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(auth.get_current_admin_user)
):
    user = crud.update_user_status(db, user_id, False)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deactivated"}

@app.post("/api/admin/users/{user_id}/activate")
async def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(auth.get_current_admin_user)
):
    user = crud.update_user_status(db, user_id, True)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User activated"}

@app.post("/api/admin/report")
async def generate_movie_report(
    report_request: schemas.ReportRequest,
    current_user: schemas.User = Depends(auth.get_current_admin_user)
):
    report = crud.generate_movie_report(
        start_date=report_request.start_date,
        end_date=report_request.end_date,
        min_rating=report_request.min_rating
    )
    if not report:
        raise HTTPException(status_code=404, detail="No movies found matching criteria")
    return report

@app.get("/api/admin/report/download")
async def download_report(
    current_user: schemas.User = Depends(auth.get_current_admin_user)
):
    file_path = "static/movie_report.csv"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(file_path, filename="movie_report.csv")

@app.get("/api/admin/report/plot")
async def get_report_plot(
    current_user: schemas.User = Depends(auth.get_current_admin_user)
):
    file_path = "static/report_plot.png"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Plot not found")
    return FileResponse(file_path)