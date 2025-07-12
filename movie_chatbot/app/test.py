# test.py
import sys
import os
import logging
from pathlib import Path

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Now use relative imports
from .scraper import scrape_imdb_movies
from .utils import get_movies_from_chart, get_movies_by_genre, get_latest_movies

def test_scraper_and_db():
    print("🕷️ Running IMDb Scraper...")
    saved, skipped, errors = scrape_imdb_movies()
    print(f"✅ Scraping Done: Saved={saved}, Skipped={skipped}, Errors={errors}")

    print("\n🎬 Fetching Top Movies...")
    top_movies = get_movies_from_chart("top", limit=5)
    for movie in top_movies:
        print(f"- {movie['title']} ({movie.get('year', 'N/A')})")

    print("\n🔥 Fetching Popular Movies...")
    popular_movies = get_movies_from_chart("popular", limit=5)
    for movie in popular_movies:
        print(f"- {movie['title']} ({movie.get('year', 'N/A')})")

    print("\n🎭 Fetching Action Movies...")
    action_movies = get_movies_by_genre("action", limit=5)
    for movie in action_movies:
        print(f"- {movie['title']} ({movie.get('year', 'N/A')})")

    print("\n🆕 Fetching Latest Movies...")
    latest = get_latest_movies(limit=5)
    for movie in latest:
        print(f"- {movie['title']} (Scraped At: {movie.get('scraped_at')})")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_scraper_and_db()