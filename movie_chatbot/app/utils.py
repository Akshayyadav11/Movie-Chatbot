import logging
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import atexit
from typing import Dict, Any, List, Optional
from fuzzywuzzy import process
from .scraper import scrape_imdb_movies
from .config import SCRAPER_INTERVAL_MINUTES, LOGGING_CONFIG
from .database import get_mongo_client

# Configure logging
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# --- Database Utilities ---
def is_database_populated() -> bool:
    """Check if movies exist in database."""
    try:
        _, _, movies_collection = get_mongo_client()
        return movies_collection.count_documents({}) > 0
    except Exception as e:
        logger.error(f"Database check failed: {str(e)}")
        return False

def search_movie_by_title(title: str) -> Optional[Dict[str, Any]]:
    """Exact match search (case-insensitive)."""
    try:
        _, _, movies_collection = get_mongo_client()
        return movies_collection.find_one(
            {"title": {"$regex": f"^{title}$", "$options": "i"}}
        )
    except Exception as e:
        logger.error(f"Title search failed: {str(e)}")
        return None

def fuzzy_search_movie(query: str, threshold: int = 80) -> Optional[Dict[str, Any]]:
    """Fuzzy match movie titles."""
    try:
        _, _, movies_collection = get_mongo_client()
        all_titles = [movie["title"] for movie in movies_collection.find({}, {"title": 1})]
        best_match = process.extractOne(query, all_titles)
        if best_match and best_match[1] >= threshold:
            return search_movie_by_title(best_match[0])
        return None
    except Exception as e:
        logger.error(f"Fuzzy search failed: {str(e)}")
        return None

def get_movies_from_chart(chart_type: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Get movies by their original chart.
    
    Args:
        chart_type: The type of chart to get movies from ('top_250', 'popular', 'trending')
        limit: Maximum number of movies to return
    """
    try:
        _, _, movies_collection = get_mongo_client()
        
        # Map user-friendly chart names to database values
        chart_mapping = {
            'top': 'top_250',
            'popular': 'popular',
            'trending': 'trending'
        }
        
        # Use the mapped value or the original if not found
        db_chart_type = chart_mapping.get(chart_type.lower(), chart_type)
        
        return list(movies_collection.find(
            {"chart_type": db_chart_type}
        ).limit(limit))
    except Exception as e:
        logger.error(f"Chart query failed for {chart_type}: {str(e)}")
        return []

def get_movies_by_genre(genre: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Get movies filtered by genre."""
    try:
        _, _, movies_collection = get_mongo_client()
        
        # Clean the genre input
        search_genre = genre.lower().strip()
        
        # First try exact match
        movies = list(movies_collection.find(
            {"genres": search_genre}
        ).limit(limit))
        
        # If no results, try partial matches
        if not movies:
            movies = list(movies_collection.find(
                {"genres": {"$regex": f".*{search_genre}.*", "$options": "i"}}
            ).limit(limit))
        
        logger.info(f"Genre search for '{genre}' found {len(movies)} movies")
        return movies
    except Exception as e:
        logger.error(f"Genre query failed: {str(e)}")
        return []

def get_latest_movies(limit: int = 5) -> List[Dict[str, Any]]:
    """Get newest movies by scraped_at date."""
    try:
        _, _, movies_collection = get_mongo_client()
        return list(movies_collection.find().sort("scraped_at", -1).limit(limit))
    except Exception as e:
        logger.error(f"Latest movies query failed: {str(e)}")
        return []

# --- Response Formatting ---
def format_movie_response(movie: Dict[str, Any]) -> str:
    """Convert movie dict to a well-formatted string for chat display."""
    try:
        # Format basic info
        title = movie.get('title', 'Unknown Title')
        year = movie.get('year', 'N/A')
        rating = movie.get('rating', 'N/A')
        
        # Format genres with emojis
        genres = movie.get('genres', [])
        genre_emojis = {
            'action': '💥', 'adventure': '🏝️', 'animation': '🎨', 'comedy': '😂', 
            'crime': '🔫', 'documentary': '📽️', 'drama': '🎭', 'family': '👨‍👩‍👧‍👦',
            'fantasy': '🧙', 'history': '📜', 'horror': '👻', 'music': '🎵',
            'mystery': '🕵️', 'romance': '💘', 'sci-fi': '🚀', 'thriller': '😱',
            'war': '⚔️', 'western': '🤠'
        }
        
        formatted_genres = []
        for genre in genres:
            genre_lower = genre.lower()
            emoji = genre_emojis.get(genre_lower, '🎬')
            formatted_genres.append(f"{emoji} {genre}")
        
        # Format cast (limit to 3 main actors)
        cast = movie.get('cast', ['N/A'])
        main_cast = cast[:3] if len(cast) > 3 else cast
        
        # Format plot (limit to 2 sentences)
        plot = movie.get('plot', 'No summary available.')
        sentences = plot.split('. ')
        short_plot = '. '.join(sentences[:2])
        if len(sentences) > 2 or len(short_plot) < len(plot):
            short_plot += '...'
        
        # Build the response
        response = [
            f"🎬 **{title}** ({year}) ⭐ {rating}",
            "",
            f"📅 **Year**: {year}",
            f"🌟 **Rating**: {rating}/10",
            f"🎭 **Genres**: {' • '.join(formatted_genres) if formatted_genres else 'N/A'}",
            f"🎥 **Director**: {movie.get('director', 'N/A')}",
            f"👥 **Cast**: {', '.join(main_cast)}",
            "",
            f"📖 **Plot**: {short_plot}",
            f"🔗 [View on IMDb]({movie.get('url', '')})"
        ]
        
        return "\n".join(response)
    except Exception as e:
        logger.error(f"Formatting failed: {str(e)}")
        return "❌ Couldn't format movie information. Please try another query."

def format_movie_list(movies: List[Dict[str, Any]]) -> str:
    """Format multiple movies in a clean, readable list."""
    if not movies:
        return "❌ No movies found. Please try another search."
    
    formatted_movies = []
    for i, movie in enumerate(movies[:5], 1):  # Limit to top 5 for readability
        title = movie.get('title', 'Unknown Title')
        year = movie.get('year', 'N/A')
        rating = movie.get('rating', 'N/A')
        
        # Get first genre for the emoji
        genre_emoji = '🎬'  # Default movie emoji
        if 'genres' in movie and movie['genres']:
            first_genre = movie['genres'][0].lower()
            genre_emojis = {
                'action': '💥', 'adventure': '🏝️', 'animation': '🎨', 
                'comedy': '😂', 'crime': '🔫', 'documentary': '📽️', 
                'drama': '🎭', 'family': '👨‍👩‍👧‍👦', 'fantasy': '🧙', 
                'horror': '👻', 'romance': '💘', 'sci-fi': '🚀', 'thriller': '😱'
            }
            genre_emoji = genre_emojis.get(first_genre, '🎬')
        
        formatted_movies.append(
            f"{i}. {genre_emoji} **{title}** ({year}) • ⭐ {rating}"
        )
    
    # Add a helpful note if there are more results
    if len(movies) > 5:
        formatted_movies.append("\n💡 Showing top 5 results. Try being more specific for better results!")
    
    return "\n".join(formatted_movies)

# --- Chat Processing ---
def process_chat_message(message: str) -> str:
    """Handle user queries about movies."""
    # Initialize database check flag if not exists
    if not hasattr(process_chat_message, '_db_checked'):
        process_chat_message._db_checked = True
        if not is_database_populated():
            # Start async scraping if empty
            import threading
            threading.Thread(target=scrape_imdb_movies).start()
            return "⏳ Loading movie database for the first time (this may take 2-3 minutes)..." 
    
    message_lower = message.lower().strip()
    
    # Greetings
    if any(word in message_lower for word in ["hello", "hi", "hey"]):
        return "🎬 Hello! I'm your movie bot. Ask me about movies, actors, or get recommendations!"
    
    # Help command
    if any(word in message_lower for word in ["help", "what can you do", "options"]):
        return (
            "🎥 **How I can help you**:\n\n"
            "• **Search movies**: 'Tell me about The Dark Knight'\n"
            "• **Top 250**: 'Show top movies' or 'IMDb top 250'\n"
            "• **Popular movies**: 'What's popular?' or 'Trending movies'\n"
            "• **By genre**: 'Horror movies', 'Action movies', 'Comedy films'\n"
            "• **New releases**: 'What's new?' or 'Latest movies'\n\n"
            "Try asking me anything about movies!"
        )
    
    # Exact title match
    if len(message.split()) > 1:  # Only search for titles if message has multiple words
        movie = search_movie_by_title(message.strip()) or fuzzy_search_movie(message.strip())
        if movie:
            return format_movie_response(movie)
    
    # Chart-specific queries
    if any(term in message_lower for term in ["top 250", "top movies", "best movies"]):
        movies = get_movies_from_chart("top_250", limit=5)
        if not movies:
            return "🔍 Couldn't find top movies. The database might be updating. Please try again in a moment."
        return "🏆 **IMDb Top 5 Movies**:\n" + format_movie_list(movies) + "\n\n💡 Ask for more details about any movie!"
    
    if any(term in message_lower for term in ["popular", "trending", "what's hot"]):
        movies = get_movies_from_chart("popular", limit=5)
        if not movies:
            movies = get_movies_from_chart("trending", limit=5)
        if not movies:
            return "🔍 Couldn't find popular movies. The database might be updating. Please try again in a moment."
        return "🔥 **Popular Movies Right Now**:\n" + format_movie_list(movies)
    
    # Genre queries
    genre_map = {
        "horror": ["horror", "scary", "frightening", "terrifying"],
        "action": ["action", "adventure", "fight", "battle", "explosion"],
        "comedy": ["comedy", "funny", "humor", "hilarious"],
        "drama": ["drama", "emotional", "serious"],
        "sci-fi": ["sci-fi", "science fiction", "space", "future", "alien"],
        "romance": ["romance", "romantic", "love story", "rom com"],
        "thriller": ["thriller", "suspense", "mystery", "crime"],
        "animation": ["animation", "animated", "cartoon"],
        "documentary": ["documentary", "docu", "real life"],
        "fantasy": ["fantasy", "magic", "sword", "dragon"]
    }
    
    for genre, keywords in genre_map.items():
        if any(kw in message_lower for kw in keywords):
            movies = get_movies_by_genre(genre, limit=5)
            if not movies:
                return f"🔍 Couldn't find any {genre} movies. Try another genre or check back later."
            return f"🎭 **Top {genre.capitalize()} Movies**:\n" + format_movie_list(movies)
    
    # Latest movies
    if any(word in message_lower for word in ["new", "latest", "recent", "just added"]):
        movies = get_latest_movies(limit=5)
        if not movies:
            return "🔍 Couldn't find recent movies. The database might be updating. Please try again in a moment."
        return "🆕 **Recently Added Movies**:\n" + format_movie_list(movies)
    
    # If we got here, we didn't understand the query
    return (
        "🤔 I'm not sure I understand. Here's what I can help with:\n\n"
        "• Search for specific movies by title\n"
        "• Show top rated movies\n"
        "• Find popular/trending movies\n"
        "• Recommend movies by genre\n"
        "• Show latest releases\n\n"
        "Try something like: 'Show me action movies' or 'What's new?'"
    )

# --- Scraper Scheduling ---
def schedule_scraping():
    """Schedule the IMDB scraper to run at intervals."""
    try:
        scheduler = BackgroundScheduler()
        
        # Immediate first run
        scheduler.add_job(
            func=scrape_imdb_movies,
            trigger='date',
            next_run_time=datetime.now(),
            id='imdb_scraper_initial_run'
        )
        
        # Periodic runs
        scheduler.add_job(
            func=scrape_imdb_movies,
            trigger='interval',
            minutes=SCRAPER_INTERVAL_MINUTES,
            id='imdb_scraper_interval'
        )
        
        scheduler.start()
        atexit.register(lambda: scheduler.shutdown())
        logger.info(f"Scheduled IMDB scraper to run every {SCRAPER_INTERVAL_MINUTES} minutes")
        
        # Log initial database status
        _, _, movies_collection = get_mongo_client()
        count = movies_collection.count_documents({})
        logger.info(f"Initial database contains {count} movies")
    except Exception as e:
        logger.error(f"Failed to schedule scraping: {str(e)}")