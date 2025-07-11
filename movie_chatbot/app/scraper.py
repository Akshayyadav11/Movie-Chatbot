from bs4 import BeautifulSoup
import requests
from datetime import datetime
from typing import List, Dict, Optional
import time
import logging
import json
from urllib.parse import urljoin, urlparse
import re
import os
from .database import get_mongo_client
from .models import Movie as MovieModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_http_session():
    """Create and return a requests session with appropriate headers."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    })
    return session

def scrape_imdb_movies():
    """Scrape top 50 movies from IMDB and save them to the database."""
    logger.info("Starting IMDB scraping...")
    
    # Get MongoDB collection
    _, _, movies_collection = get_mongo_client()
    
    try:
        # Create a session with proper headers
        session = get_http_session()
        
        # Scrape top movies
        url = "https://www.imdb.com/chart/top/"
        logger.info(f"Fetching IMDB top movies from {url}")
        
        response = session.get(url, timeout=30)
        response.raise_for_status()
        
        # Check if we got a valid response
        if not response.text.strip():
            raise Exception("Received empty response from IMDB")
            
        soup = BeautifulSoup(response.text, 'html.parser')
        movie_links = []
        
        # Get top 50 movies
        logger.info("Looking for movie links in the page...")
        movie_elements = soup.select('ul.ipc-metadata-list li')
        
        for elem in movie_elements[:50]:
            link = elem.select_one('a.ipc-title-link-wrapper')
            if link and link.get('href'):
                full_url = f"https://www.imdb.com{link['href'].split('?')[0]}"
                if '/title/tt' in full_url and full_url not in movie_links:
                    movie_links.append(full_url)
        
        logger.info(f"Found {len(movie_links)} movies to scrape")
        
        if not movie_links:
            logger.warning("No movie links found to scrape")
            return
            
        # Scrape each movie page
        for i, url in enumerate(movie_links, 1):
            try:
                logger.info(f"Scraping movie {i}/{len(movie_links)}: {url}")
                movie_data = scrape_movie_page(session, url)
                
                if movie_data:
                    save_movie_data(movie_data, movies_collection)
                    time.sleep(1)  # Be nice to the server
            except Exception as e:
                logger.error(f"Error scraping {url}: {str(e)}", exc_info=True)
                continue
                
        logger.info("Finished scraping IMDB")
            
    except Exception as e:
        logger.error(f"Error in scrape_imdb_movies: {str(e)}", exc_info=True)
        raise

def scrape_movie_page(session, url: str) -> Optional[Dict]:
    """Scrape detailed information for a single movie using requests and BeautifulSoup."""
    try:
        logger.info(f"Scraping movie page: {url}")
        
        # Get the page content with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = session.get(url, timeout=30)
                response.raise_for_status()
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to fetch {url} after {max_retries} attempts: {str(e)}")
                    return None
                logger.warning(f"Retry {attempt + 1} for {url}")
                time.sleep(2)
        
        if not response.text.strip():
            logger.warning(f"Empty response received for {url}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Helper function to safely extract text from elements
        def safe_extract(selector: str, attribute: str = 'text', default=None):
            try:
                element = soup.select_one(selector)
                if not element:
                    return default
                if attribute == 'text':
                    return element.get_text(strip=True)
                return element.get(attribute, default)
            except Exception as e:
                logger.debug(f"Error extracting {selector}: {str(e)}")
                return default
        
        # Extract basic information
        title = safe_extract('h1[data-testid="hero-title-block__title"]', 'text', 'Unknown Title')
        year = safe_extract('a[href*="releaseinfo"]', 'text')
        
        # Extract rating
        rating_text = safe_extract('div[data-testid="hero-rating-bar__aggregate-rating__score"] span', 'text')
        rating = float(rating_text) if rating_text and rating_text.replace('.', '').isdigit() else None
        
        # Extract genres
        genre_elems = soup.select('div[data-testid="genres"] a')
        genres = [genre.get_text(strip=True) for genre in genre_elems if genre.get_text(strip=True)]
        
        # Extract plot
        plot = safe_extract('p[data-testid="plot"]', 'text')
        
        # Extract director and cast
        director = safe_extract('a[href*="tt_ov_dr"]', 'text')
        cast_elems = soup.select('a[data-testid="title-cast-item__actor"]')
        cast = [actor.get_text(strip=True) for actor in cast_elems[:5] if actor.get_text(strip=True)]
        
        # Extract poster URL
        poster_url = safe_extract('img[data-testid="hero-media__poster"]', 'src')
        
        # Extract IMDB ID from URL
        imdb_id = url.split('/')[-2] if '/title/tt' in url else None
        
        movie_data = {
            'title': title,
            'year': year,
            'rating': rating,
            'genres': genres,
            'plot': plot,
            'director': director,
            'cast': cast,
            'poster_url': poster_url,
            'imdb_id': imdb_id,
            'imdb_url': url,
            'scraped_at': datetime.utcnow(),
            'source': 'imdb',
            'scraped_with': 'requests'
        }
        
        logger.debug(f"Scraped movie data: {movie_data}")
        return movie_data
        
    except Exception as e:
        logger.error(f"Error scraping movie page {url}: {str(e)}", exc_info=True)
        return None

def save_movie_data(movie_data: Dict, movies_collection):
    if not movie_data or not movie_data.get("title"):
        return
    
    # Create a unique ID from the title and year
    movie_id = f"{movie_data['title'].lower().replace(' ', '-')}-{movie_data['year']}"
    
    # Update or insert the movie data
    movies_collection.update_one(
        {"_id": movie_id},
        {"$set": movie_data},
        upsert=True
    )