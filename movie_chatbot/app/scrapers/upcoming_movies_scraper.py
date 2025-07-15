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

    def scrape_and_store_movies(self, movies_collection) -> None:
        """Scrape upcoming movies from IMDb and store them in MongoDB"""
        try:
            # Check if collection is valid
            if movies_collection is None:
                logger.error("Invalid MongoDB collection")
                return

            # Make request to IMDb calendar page
            response = self.session.get(self.base_url)
            if response.status_code != 200:
                logger.error(f"Failed to fetch IMDb calendar page: {response.status_code}")
                return

            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            logger.info(f"HTML content length: {len(response.text)}")
            
            # Find all date headers
            date_headers = soup.find_all('h3', class_='ipc-title__text')
            logger.info(f"Found {len(date_headers)} date headers")
            
            # Log the first few date headers for debugging
            for i, header in enumerate(date_headers[:3]):
                logger.info(f"Header {i+1} content: {header.text.strip()}")
                logger.info(f"Header {i+1} HTML: {header.prettify()[:200]}...")
            
            total_movies = 0
            movies_saved = 0
            
            for header in date_headers:
                # Get the date text
                release_date = header.text.strip()
                logger.info(f"Processing movies for date: {release_date}")
                
                # Find the parent section
                section = header.find_parent('section')
                if not section:
                    logger.warning(f"No section found for date: {release_date}")
                    continue
                    
                # Log section structure for debugging
                logger.info(f"Section HTML for date {release_date}: {section.prettify()[:500]}...")
                
                # Find the movie list
                movie_list = section.find('ul', class_='ipc-metadata-list')
                if not movie_list:
                    logger.warning(f"No movie list found for date: {release_date}")
                    continue
                    
                # Log movie list structure for debugging
                logger.info(f"Movie list HTML for date {release_date}: {movie_list.prettify()[:500]}...")
                
                # Find all movie items in this section
                movie_items = movie_list.find_all('li', class_='ipc-metadata-list-summary-item')
                total_movies += len(movie_items)
                logger.info(f"Found {len(movie_items)} movies for date: {release_date}")
                
                for item in movie_items:
                    # Find the title link
                    title_link = item.find('a', class_='ipc-metadata-list-summary-item__t')
                    if not title_link:
                        logger.warning(f"No title link found in item for date: {release_date}")
                        continue
                        
                    # Log movie item structure for debugging
                    logger.info(f"Movie item HTML: {item.prettify()[:500]}...")
                        
                    # Extract title and year from the text
                    title_text = title_link.text.strip()
                    title = title_text.split('(')[0].strip()
                    year = title_text.split('(')[1].split(')')[0] if '(' in title_text else None
                    
                    # Get URL
                    url = f"https://www.imdb.com{title_link.get('href')}"
                    
                    # Create movie dictionary with proper date format
                    try:
                        # Try to parse the date string
                        date_parts = release_date.split()
                        if len(date_parts) >= 2:
                            month = date_parts[0]
                            day = date_parts[1]
                            year = date_parts[2] if len(date_parts) > 2 else datetime.now().year
                            formatted_date = f"{month} {day}, {year}"
                        else:
                            formatted_date = release_date
                    except Exception as e:
                        logger.error(f"Error formatting date {release_date}: {str(e)}")
                        formatted_date = release_date

                    movie = {
                        "title": title,
                        "year": year,
                        "url": url,
                        "created_at": datetime.utcnow().isoformat(),
                        "last_updated": datetime.utcnow().isoformat(),
                        "release_date": formatted_date,
                        "type": 'upcoming'
                    }
                    
                    # Store or update movie
                    existing_movie = movies_collection.find_one({'title': movie['title'], 'type': 'upcoming'})
                    if existing_movie:
                        movies_collection.update_one(
                            {'_id': existing_movie['_id']},
                            {'$set': movie}
                        )
                        logger.info(f"Updated movie: {title} for date: {formatted_date}")
                    else:
                        movies_collection.insert_one(movie)
                        logger.info(f"Stored new movie: {title} for date: {formatted_date}")
                        movies_saved += 1
            
            logger.info(f"Total movies processed: {total_movies}")
            logger.info(f"Movies saved/updated: {movies_saved}")
            
        except Exception as e:
            logger.error(f"Error scraping movies: {str(e)}", exc_info=True)
            raise
