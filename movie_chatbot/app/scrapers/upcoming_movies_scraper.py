from typing import Optional
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from app.config import MONGODB_URL, MONGODB_DB
from app.utils import get_mongo_client
import logging
import os
import re

logger = logging.getLogger(__name__)

class UpcomingMoviesScraper:
    def __init__(self):
        self.base_url = "https://www.imdb.com/calendar/?region=us"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br'
        })

    def extract_movie_info(self, movie_item):
        """Extract movie information from a movie item element"""
        try:
            logger.debug(f"Processing movie item: {movie_item}")
            
            # Get the title element - using the new IMDb structure
            title_elem = movie_item.select_one('a.ipc-metadata-list-summary-item__t')
            if not title_elem:
                logger.warning("No title element found for movie item")
                return None
                
            title_text = title_elem.get_text(strip=True)
            if not title_text:
                logger.warning("No title text found")
                return None
            
            # Extract year from title (e.g., "Movie Title (2023)")
            year = ""
            year_match = re.search(r'\((\d{4})\)$', title_text)
            if year_match:
                year = year_match.group(1)
                title = title_text.replace(f"({year})", "").strip()
            else:
                title = title_text
            
            # Get the URL
            url_path = title_elem.get('href', '').split('?')[0]
            url = f"https://www.imdb.com{url_path}" if url_path.startswith('/') else url_path
            
            # Get release date from the movie title (e.g., "Jul 18, 2025")
            release_date = re.search(r'^(\w+ \d+, \d{4})', title_text)
            if release_date:
                release_date = release_date.group(1)
                logger.debug(f"Found release date in title: {release_date}")
            else:
                logger.warning(f"No release date found in title: {title_text}")
            
            # Get genres - they're in a list with specific classes
            genres = []
            genre_container = movie_item.select_one('ul.ipc-inline-list--show-dividers')
            if genre_container:
                genre_elems = genre_container.select('span.ipc-metadata-list-summary-item__li')
                for genre_elem in genre_elems:
                    genre = genre_elem.get_text(strip=True)
                    # Only add if it looks like a genre (capitalized, not too long)
                    if genre and genre[0].isupper() and len(genre) < 30:
                        genres.append(genre)
            
            # Get poster URL
            poster_url = ""
            poster_elem = movie_item.select_one('img.ipc-image')
            if poster_elem and 'src' in poster_elem.attrs:
                poster_url = poster_elem['src']
            
            # Get cast members if available
            cast = []
            cast_container = movie_item.select('ul.ipc-inline-list--show-dividers')
            if len(cast_container) > 1:  # Second list is usually cast
                cast_elems = cast_container[1].select('span.ipc-metadata-list-summary-item__li')
                for cast_elem in cast_elems:
                    cast_member = cast_elem.get_text(strip=True)
                    if cast_member and cast_member[0].isupper() and len(cast_member) < 50:
                        cast.append(cast_member)
            
            return {
                "title": title,
                "year": year,
                "url": url,
                "release_date": release_date,
                "type": "upcoming",
                "genres": genres,
                "poster_url": poster_url,
                "last_updated": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error extracting movie info: {str(e)}")
            return None
            
    def scrape_and_store_movies(self, movies_collection) -> int:
        """Scrape upcoming movies from IMDb and store them in MongoDB
        
        Args:
            movies_collection: MongoDB collection to store movies
            
        Returns:
            int: Number of movies scraped and stored
        """
        try:
            # Check if collection is valid
            if movies_collection is None:
                logger.error("Invalid MongoDB collection: collection is None")
                raise ValueError("Invalid MongoDB collection")
                
            logger.info("Starting to scrape upcoming movies from IMDb...")

            # Make request to IMDb with retries
            max_retries = 3
            response = None
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Attempting to fetch IMDb calendar (attempt {attempt + 1}/{max_retries})...")
                    
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Referer': 'https://www.imdb.com/',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1'
                    }
                    
                    response = self.session.get(
                        self.base_url,
                        headers=headers,
                        timeout=30
                    )
                    response.raise_for_status()
                    
                    # Check if we got a valid response
                    if 'captcha' in response.text.lower() or 'are you human' in response.text.lower():
                        logger.error("Detected CAPTCHA or blocking page in response")
                        if attempt < max_retries - 1:
                            wait_time = 5 * (attempt + 1)  # Longer wait for CAPTCHA
                            logger.warning(f"Got CAPTCHA, waiting {wait_time} seconds before retry...")
                            time.sleep(wait_time)
                            continue
                        return 0
                    
                    break  # Successfully got the page
                    
                except requests.RequestException as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to fetch {self.base_url} after {max_retries} attempts: {str(e)}")
                        return 0
                    wait_time = 2 ** (attempt + 1)  # Exponential backoff
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
            
            # Save the HTML for debugging
            debug_dir = '/app/debug'
            os.makedirs(debug_dir, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            debug_file = os.path.join(debug_dir, f'imdb_calendar_{timestamp}.html')
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            logger.info(f"Saved HTML to {debug_file} for debugging")
            
            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all movie sections - they're in articles with data-testid="calendar-section"
            movie_sections = soup.select('article[data-testid="calendar-section"]')
            logger.info(f"Found {len(movie_sections)} movie sections")
            
            if not movie_sections:
                logger.warning("No movie sections found. The page structure may have changed.")
                logger.info("Page title: %s", soup.title.string if soup.title else "No title")
                
                # Try to find any movie items directly as a fallback
                logger.info("Attempting to find movie items directly...")
                return self._scrape_movies_directly(soup, movies_collection)

            scraped_count = 0

            for movie_section in movie_sections:
                # Get the date for this section
                date_elem = movie_section.select_one('div[data-testid="release-date"]')
                release_date = date_elem.get_text(strip=True) if date_elem else "Unknown Date"
                logger.info(f"Processing movies for date: {release_date}")
                
                # Find all movie items in this section
                movie_items = movie_section.select('li.ipc-metadata-list-summary-item')
                
                # If no movies found with the main selector, try alternative selectors
                if not movie_items:
                    movie_items = movie_section.select('li[data-testid="coming-soon-entry"]')
                
                if not movie_items:
                    logger.warning(f"No movies found for date: {release_date}")
                    continue
                    
                logger.info(f"Found {len(movie_items)} movies for {release_date}")
                
                # Process each movie item
                for item in movie_items:
                    try:
                        movie_info = self.extract_movie_info(item)
                        if not movie_info:
                            logger.warning("Skipping movie - could not extract info")
                            continue
                            
                        # Add the release date if not already set
                        if not movie_info.get("release_date"):
                            movie_info["release_date"] = release_date
                            
                        # Add timestamp
                        movie_info["last_updated"] = datetime.utcnow().isoformat()
                        movie_info["type"] = "upcoming"
                        
                        # Log the movie being processed
                        logger.info(f"Processing movie: {movie_info.get('title', 'Unknown')} - {movie_info.get('release_date', 'No date')}")
                        
                        # Store or update movie in database
                        result = movies_collection.update_one(
                            {"url": movie_info["url"]},
                            {
                                "$set": movie_info,
                                "$setOnInsert": {"created_at": datetime.utcnow().isoformat()}
                            },
                            upsert=True
                        )
                        
                        if result.upserted_id:
                            logger.info(f"Added new movie: {movie_info.get('title', 'Unknown')}")
                            scraped_count += 1
                        elif result.modified_count > 0:
                            logger.info(f"Updated movie: {movie_info.get('title', 'Unknown')}")
                            scraped_count += 1
                            
                    except Exception as e:
                        logger.error(f"Error processing movie: {str(e)}")
                        continue
                        
            return scraped_count
            
        except Exception as e:
            logger.error(f"Error in scrape_and_store_movies: {str(e)}")
            raise
