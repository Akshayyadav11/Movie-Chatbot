import logging
import os
import json
from datetime import timedelta
from typing import List, Generator, Dict, Any, Optional
from urllib.parse import quote

from fastapi import FastAPI, Depends, HTTPException, Request, Form, status, Response
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from . import models, schemas, crud, auth, utils
from .database import get_db, init_db, get_mongo_client
from .scraper import scrape_imdb_movies

app = FastAPI()

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

import os

# Get absolute paths
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
TEMPLATES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "templates"))

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

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
async def admin_dashboard(
    request: Request,
    current_user: Optional[schemas.User] = Depends(auth.get_current_user)
):
    if not current_user:
        return RedirectResponse(url=f"/login?error={quote('Please login to access the admin panel')}")
    if not current_user.is_admin:
        return RedirectResponse(url=f"/login?error={quote('Admin privileges required')}")
        
    try:
        # Get database session
        db = next(get_db())
        
        # Get user statistics
        total_users = db.query(models.User).count()
        active_users = db.query(models.User).filter(models.User.is_active == True).count()
        
        # Get movie statistics from MongoDB
        _, _, movies_collection = get_mongo_client()
        total_movies = movies_collection.count_documents({})
        latest_movies = list(movies_collection.find().sort("release_date", -1).limit(5))
        
        # Get chat statistics (if you have a chat model)
        # total_chats = db.query(models.Chat).count()
        
        return templates.TemplateResponse("admin.html", {
            "request": request,
            "current_user": current_user,
            "total_users": total_users,
            "active_users": active_users,
            "total_movies": total_movies,
            "latest_movies": latest_movies,
            # "total_chats": total_chats,
        })
    except Exception as e:
        logger.error(f"Error loading admin dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error loading admin dashboard"
        )

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    # Check for error in query parameters
    error = request.query_params.get('error', None)
    
    # If user is already authenticated, redirect to admin
    try:
        current_user = await auth.get_current_user(request=request)
        if current_user and current_user.is_admin:
            return RedirectResponse(url="/admin")
    except Exception as e:
        # If there's an error (like invalid token), just continue to show login page
        pass
        
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error
    })

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    response: Response,
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
    
    # Set the access token in an HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False  # Set to True in production with HTTPS
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token", httponly=True, samesite="lax")
    return response

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
    try:
        report_data = crud.generate_movie_report()
        if not report_data or not os.path.exists(report_data["csv_path"]):
            raise HTTPException(status_code=404, detail="Report not found")
        
        # Log the download for audit purposes
        logger.info(f"Admin {current_user.username} downloaded the movie report")
        
        return FileResponse(
            report_data["csv_path"],
            media_type="text/csv",
            filename=f"movie_report_{datetime.now().strftime('%Y%m%d')}.csv"
        )
    except Exception as e:
        logger.error(f"Error downloading report: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating report")

@app.get("/api/admin/report/plot")
async def get_report_plot(
    current_user: schemas.User = Depends(auth.get_current_admin_user)
):
    try:
        report_data = crud.generate_movie_report()
        if not report_data or not os.path.exists(report_data["plot_path"]):
            # Return a default image if no plot is available
            default_plot = "static/default_plot.png"
            if not os.path.exists(default_plot):
                # Create a simple default plot if it doesn't exist
                import matplotlib.pyplot as plt
                plt.figure(figsize=(10, 6))
                plt.text(0.5, 0.5, 'No data available', 
                        horizontalalignment='center',
                        verticalalignment='center',
                        transform=plt.gca().transAxes)
                plt.axis('off')
                plt.savefig(default_plot)
                plt.close()
            return FileResponse(default_plot)
        
        # Set cache control headers
        return FileResponse(
            report_data["plot_path"],
            headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
        )
    except Exception as e:
        logger.error(f"Error generating plot: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating plot")