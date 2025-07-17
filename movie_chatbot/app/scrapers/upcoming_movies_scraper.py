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

            # Make request to IMDb calendar page
            response = self.session.get(self.base_url)
            if response.status_code != 200:
                logger.error(f"Failed to fetch IMDb calendar page: {response.status_code}")
                return 0
                
            scraped_count = 0

            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all date headers
            date_headers = soup.find_all('h3', class_='ipc-title__text')
            
            for header in date_headers:
                # Get the date text
                release_date = header.text.strip()
                logger.info(f"Processing movies for date: {release_date}")
                
                # Find the next sibling div that contains the movies
                next_div = header.find_next_sibling('div')
                if not next_div:
                    continue
                    
                # Find all movie items in this section
                movie_items = next_div.find_all('li', class_='ipc-metadata-list-summary-item')
                for item in movie_items:
                    try:
                        # Find the title link
                        title_link = item.find('a', class_='ipc-metadata-list-summary-item__t')
                        if not title_link:
                            continue
                            
                        # Extract title and year from the text
                        title_text = title_link.text.strip()
                        title = title_text.split('(')[0].strip()
                        year = title_text.split('(')[1].split(')')[0] if '(' in title_text else None
                        
                        # Get URL
                        url = f"https://www.imdb.com{title_link.get('href')}"
                        
                        # Create movie dictionary
                        movie = {
                            "title": title,
                            "year": year,
                            "url": url,
                            "created_at": datetime.utcnow().isoformat(),
                            "last_updated": datetime.utcnow().isoformat(),
                            "release_date": release_date,
                            "type": "upcoming"
                        }
                        
                        # Store or update movie in database
                        result = movies_collection.update_one(
                            {"url": url},
                            {"$set": movie},
                            upsert=True
                        )
                        
                        if result.upserted_id or result.modified_count > 0:
                            scraped_count += 1
                            
                    except Exception as e:
                        logger.error(f"Error processing movie {title_text if 'title_text' in locals() else 'unknown'}: {str(e)}")
                        continue
                        
            return scraped_count

        except Exception as e:
            logger.error(f"Error in scrape_and_store_movies: {str(e)}")
            raise
