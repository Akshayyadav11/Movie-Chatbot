import logging
from apscheduler.schedulers.background import BackgroundScheduler
from .scraper import scrape_imdb_movies
import atexit

# Configure logger
logger = logging.getLogger(__name__)

def schedule_scraping():
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=scrape_imdb_movies, trigger="interval", days=1)
    scheduler.start()
    
    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())

from .database import get_mongo_client
from .crud import get_latest_movies
from typing import List, Dict, Any

def process_chat_message(message: str) -> str:
    # Simple keyword-based responses
    message_lower = message.lower()
    
    if any(word in message_lower for word in ["hello", "hi", "hey"]):
        return "Hello! How can I help you with movies today?"
    
    if any(word in message_lower for word in ["recommend", "suggest", "good movie"]):
        return "I can recommend some popular movies. What genre are you interested in?"
    
    if any(word in message_lower for word in ["action", "comedy", "drama", "horror", "sci-fi"]):
        genre = next(word for word in ["action", "comedy", "drama", "horror", "sci-fi"] if word in message_lower)
        return f"Here are some great {genre} movies I can recommend..."
    
    if any(word in message_lower for word in ["director", "directed by"]):
        return "I can provide information about movie directors. Which movie are you asking about?"
    
    if any(word in message_lower for word in ["cast", "actor", "actress"]):
        return "I can tell you about the cast of movies. Which movie are you interested in?"
    
    if any(word in message_lower for word in ["plot", "story", "about"]):
        return "I can summarize movie plots. Which movie would you like to know about?"
    
    if any(word in message_lower for word in ["rating", "score"]):
        return "I can provide movie ratings. Which movie's rating are you asking about?"
    
    if any(word in message_lower for word in ["new", "latest", "recent"]):
        return get_latest_movies_response()
    
    if any(word in message_lower for word in ["upcoming", "coming soon", "future"]):
        return get_upcoming_movies_response()
    
    return "I'm a movie chatbot. I can help you with information about movies, directors, actors, and more. How can I assist you?"

def get_latest_movies_response(limit: int = 5) -> str:
    """Generate a response with the latest movies from the database."""
    try:
        movies = get_latest_movies(limit)
        if not movies:
            return "I couldn't find any recent movies in the database. Please try again later or check back soon for updates."
        
        response = ["Here are the latest movies I found:"]
        for i, movie in enumerate(movies, 1):
            title = movie.get('title', 'Unknown Title')
            year = movie.get('year', 'N/A')
            rating = movie.get('rating', 'N/A')
            response.append(f"{i}. {title} ({year}) - ⭐ {rating}/10")
        
        return "\n".join(response)
    except Exception as e:
        logger.error(f"Error getting latest movies: {str(e)}")
        return "I'm having trouble fetching the latest movies right now. Please try again later."

def get_upcoming_movies_response(limit: int = 5) -> str:
    """Generate a response with upcoming movies from the database."""
    try:
        # Get MongoDB collection
        _, _, movies_collection = get_mongo_client()
        
        # Find upcoming movies (release date in the future)
        from datetime import datetime
        upcoming_movies = list(movies_collection.find({
            "release_date": {"$gte": datetime.now()}
        }).sort("release_date", 1).limit(limit))
        
        if not upcoming_movies:
            return "I couldn't find any upcoming movies in the database. Please check back later for updates."
        
        response = ["Here are some upcoming movies you might be interested in:"]
        for i, movie in enumerate(upcoming_movies, 1):
            title = movie.get('title', 'Unknown Title')
            release_date = movie.get('release_date', 'Coming soon')
            if isinstance(release_date, str):
                release_str = release_date
            else:
                release_str = release_date.strftime("%B %d, %Y") if hasattr(release_date, 'strftime') else 'Coming soon'
            
            response.append(f"{i}. {title} - {release_str}")
        
        return "\n".join(response)
    except Exception as e:
        logger.error(f"Error getting upcoming movies: {str(e)}")
        return "I'm having trouble fetching upcoming movies right now. Please try again later."