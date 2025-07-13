from bs4 import BeautifulSoup
import requests
from datetime import datetime
from typing import List, Dict, Optional
import time
import logging
import re
from urllib.parse import urljoin
from .database import get_mongo_client
from .config import (
    REQUEST_DELAY,
    IMDB_TOP_MOVIES_URL,
    SCRAPER_USER_AGENT,
    LOGGING_CONFIG
)

# Configure logging
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

def get_http_session():
    """Create a session with realistic browser headers."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.imdb.com/',
        'DNT': '1',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
    })
    return session

def scrape_imdb_chart(chart_type='top'):
    """Scrape movies from IMDB charts with updated selectors."""
    charts = {
        'top_250': {
            'url': 'https://www.imdb.com/chart/top/',
            'selector': 'li.ipc-metadata-list-summary-item',
            'title_selector': 'h3.ipc-title__text',
            'link_selector': 'a.ipc-title-link-wrapper',
            'limit': 250,  # Top 250 movies
            'source': 'imdb_top_250'
        },
        'popular': {
            'url': 'https://www.imdb.com/chart/moviemeter/',
            'selector': 'li.ipc-metadata-list-summary-item',
            'title_selector': 'h3.ipc-title__text',
            'link_selector': 'a.ipc-title-link-wrapper',
            'limit': 100,  # Top 100 popular movies
            'source': 'imdb_popular'
        },
        'trending': {
            'url': 'https://www.imdb.com/chart/moviemeter/?ref_=nv_mv_mpm',
            'selector': 'li.ipc-metadata-list-summary-item',
            'title_selector': 'h3.ipc-title__text',
            'link_selector': 'a.ipc-title-link-wrapper',
            'limit': 50,  # Top 50 trending movies
            'source': 'imdb_trending'
        },
        'action': {
            'url': 'https://www.imdb.com/search/title/?genres=action&tags=action&title_type=feature&languages=en&count=100',
            'selector': 'li.ipc-metadata-list-summary-item',
            'title_selector': 'h3.ipc-title__text',
            'link_selector': 'a.ipc-title-link-wrapper',
            'limit': 100,  # Top 100 action movies
            'source': 'imdb_action'
        },
        'comedy': {
            'url': 'https://www.imdb.com/search/title/?genres=comedy&tags=comedy&title_type=feature&languages=en&count=100',
            'selector': 'li.ipc-metadata-list-summary-item',
            'title_selector': 'h3.ipc-title__text',
            'link_selector': 'a.ipc-title-link-wrapper',
            'limit': 100,  # Top 100 comedy movies
            'source': 'imdb_comedy'
        },
        'horror': {
            'url': 'https://www.imdb.com/search/title/?genres=horror&tags=horror&title_type=feature&languages=en&count=100',
            'selector': 'li.ipc-metadata-list-summary-item',
            'title_selector': 'h3.ipc-title__text',
            'link_selector': 'a.ipc-title-link-wrapper',
            'limit': 100,  # Top 100 horror movies
            'source': 'imdb_horror'
        }
    }

    if chart_type not in charts:
        logger.error(f"Invalid chart type: {chart_type}")
        return []

    chart = charts[chart_type]
    logger.info(f"Fetching {chart_type} chart from {chart['url']}")
    
    session = get_http_session()
    try:
        # Add delay to mimic human behavior
        time.sleep(2)
        
        response = session.get(
            chart['url'],
            headers={'Referer': 'https://www.imdb.com/'},
            timeout=30
        )
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        movie_links = []
        
        # Find all movie containers
        movie_containers = soup.select(chart['selector'])
        logger.info(f"Found {len(movie_containers)} movie containers")
        
        # Extract movie links
        for container in movie_containers[:chart['limit']]:
            try:
                # Try to find link element
                link_elem = container.select_one(chart.get('link_selector', 'a'))
                if not link_elem:
                    continue
                    
                # Get the href attribute
                href = link_elem.get('href', '')
                if not href or '/title/tt' not in href:
                    continue
                    
                # Clean and format the URL
                full_url = f"https://www.imdb.com{href.split('?')[0]}"
                if full_url not in movie_links:
                    movie_links.append(full_url)
                    
            except Exception as e:
                logger.warning(f"Error processing movie container: {e}")
                continue
        
        logger.info(f"Found {len(movie_links)} valid movie links")
        return movie_links
        
    except Exception as e:
        logger.error(f"Failed to scrape {chart_type} chart: {str(e)}", exc_info=True)
        return []
# def scrape_imdb_chart(chart_type='top'):
#     """Working IMDb scraper as of July 2024"""
#     charts = {
#         'top': {
#             'url': 'https://www.imdb.com/chart/top/',
#             'selector': 'div.ipc-title-link-wrapper',  # Updated selector
#             'limit': 10
#         },
#         'popular': {
#             'url': 'https://www.imdb.com/chart/moviemeter/',
#             'selector': 'div.ipc-title-link-wrapper',  # Same selector works for both
#             'limit': 10
#         }
#     }
    
#     session = get_http_session()
#     try:
#         response = session.get(
#             charts[chart_type]['url'],
#             headers={'Referer': 'https://www.imdb.com/'},
#             timeout=10
#         )
#         response.raise_for_status()
        
#         soup = BeautifulSoup(response.text, 'html.parser')
#         movie_links = []
        
#         # New reliable extraction method
#         for link in soup.select(charts[chart_type]['selector']):
#             href = link.find('a')['href'] if link.find('a') else None
#             if href and '/title/tt' in href:
#                 full_url = f"https://www.imdb.com{href.split('?')[0]}"
#                 if full_url not in movie_links:
#                     movie_links.append(full_url)
        
#         return movie_links[:charts[chart_type]['limit']]
    
#     except Exception as e:
#         logger.error(f"Scrape failed: {str(e)}")
#         return []

def scrape_movie_page(session, url: str, source: str = 'imdb', chart_type: str = None) -> Optional[Dict]:
    """Scrape detailed movie data with robust error handling.
    
    Args:
        session: The HTTP session to use for requests
        url: The URL of the movie page to scrape
        source: The source of the movie (e.g., 'imdb_top_250')
        chart_type: The type of chart the movie was found in (e.g., 'top_250', 'popular')
    """
    try:
        logger.info(f"Scraping: {url}")
        
        # Extract IMDb ID from URL
        imdb_match = re.search(r'title\/(tt\d+)\/?', url)
        if not imdb_match:
            logger.error(f"Invalid IMDB URL: {url}")
            return None
        imdb_id = imdb_match.group(1)
        
        # Make the HTTP request with retries
        for attempt in range(3):
            try:
                response = session.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': 'https://www.imdb.com/'
                }, timeout=30)
                response.raise_for_status()
                break  # If successful, exit the retry loop
            except Exception as e:
                if attempt == 2:  # If this was the last attempt
                    logger.error(f"Failed to fetch {url} after 3 attempts: {e}")
                    return None
                time.sleep(2)  # Wait before retrying
        
        # Parse the HTML response
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Helper function to safely get text from selector
        def get_text(selector, attr='text', default=None):
            try:
                elem = soup.select_one(selector)
                if not elem:
                    return default
                if attr == 'text':
                    return elem.get_text(strip=True)
                return elem.get(attr, default)
            except Exception as e:
                logger.debug(f"Error getting {selector}: {e}")
                return default
        
        # Extract movie data with more robust selectors
        title = get_text('h1[data-testid="hero__pageTitle"]')
        if not title:  # Fallback for different page structure
            title = get_text('h1')
        
        year = get_text('a[href*="releaseinfo"]')
        if not year:  # Try alternative year selector
            year = get_text('span[data-testid="title-details-releasedate"] a')
        
        rating = get_text('div[data-testid="hero-rating-bar__aggregate-rating__score"]')
        if not rating:  # Try alternative rating selector
            rating = get_text('span.sc-7ab21ed2-1.jGRxWM')
        
        plot = get_text('span[data-testid="plot-xl"]')
        if not plot:  # Fallback to shorter plot
            plot = get_text('span[data-testid="plot-l"]')
        
        # Try multiple genre selectors
        genres = []
        
        # Try new genre selector (IMDB's current format)
        genre_section = soup.find('div', {'class': 'ipc-chip-list'})
        if genre_section:
            genres = [g.get_text(strip=True) for g in genre_section.find_all('a')]
            if genres:
                logger.debug(f"Found genres using ipc-chip-list selector: {genres}")
                
        # Try genre selector in title block
        if not genres:
            title_block = soup.find('div', {'class': 'sc-52d569c6-0'})
            if title_block:
                genres = [g.get_text(strip=True) for g in title_block.find_all('a') if '/genres=' in g.get('href', '')]
                if genres:
                    logger.debug(f"Found genres using title block selector: {genres}")
                    
        # Try genre selector in title details
        if not genres:
            title_details = soup.find('div', {'data-testid': 'title-details-section'})
            if title_details:
                genres = [g.get_text(strip=True) for g in title_details.find_all('a') if '/genres=' in g.get('href', '')]
                if genres:
                    logger.debug(f"Found genres using title details selector: {genres}")
                    
        # Try genre selector in title story
        if not genres:
            title_story = soup.find('div', {'data-testid': 'storyline-genres'})
            if title_story:
                genres = [g.get_text(strip=True) for g in title_story.find_all('a')]
                if genres:
                    logger.debug(f"Found genres using storyline selector: {genres}")
                    
        # Try genre selector in title info
        if not genres:
            title_info = soup.find('div', {'data-testid': 'title-genres'})
            if title_info:
                genres = [g.get_text(strip=True) for g in title_info.find_all('a')]
                if genres:
                    logger.debug(f"Found genres using title info selector: {genres}")
                    
        # Clean up genres
        genres = [g.lower().strip() for g in genres if g]
        if not genres:
            logger.warning(f"No genres found for {title}")
        else:
            logger.info(f"Found genres for {title}: {genres}")
        
        # Get release date
        release_date = None
        release_info = soup.find('li', {'data-testid': 'title-details-releasedate'})
        if release_info:
            date_text = release_info.find('a').get_text(strip=True)
            try:
                # Try to parse date in format "Month DD, YYYY"
                date_obj = datetime.strptime(date_text, '%B %d, %Y')
                release_date = date_obj.strftime('%Y-%m-%d')
                # Store only the year
                movie['year'] = str(date_obj.year)
            except ValueError:
                logger.warning(f"Could not parse release date for {title}: {date_text}")
        
        director = get_text('a[href*="tt_ov_dr"]')
        if not director:  # Fallback for director
            director_elem = soup.find('a', {'data-testid': 'title-pc-principal-credit'})
            if director_elem:
                director = director_elem.get_text(strip=True)
        
        cast = [actor.get_text(strip=True) for actor in soup.select('a[data-testid="title-cast-item__actor"]')]
        if not cast:  # Fallback for cast
            cast = [a.get_text(strip=True) for a in soup.select('a[href*="/name/nm"][data-testid="title-cast-item__actor"]')]
        
        poster = get_text('img[data-testid="hero-media__poster"]', 'src')
        if not poster:  # Fallback for poster
            poster_elem = soup.find('img', {'class': 'ipc-image'})
            if poster_elem:
                poster = poster_elem.get('src')
        
        data = {
            'imdb_id': imdb_id,
            'title': title,
            'year': year,
            'rating': rating,
            'plot': plot,
            'genres': genres,
            'director': director,
            'cast': cast[:10],  # Limit to top 10 cast members
            'poster': poster,
            'url': url,
            'source': source,  # e.g., 'imdb_top_250'
            'chart_type': chart_type,  # e.g., 'top_250', 'popular', 'trending'
            'last_updated': datetime.utcnow(),
            'scraped_at': datetime.utcnow(),
            'release_date': release_date
        }
        
        return {k: v for k, v in data.items() if v}  # Remove None values
        
    except Exception as e:
        logger.error(f"Error scraping {url}: {str(e)}", exc_info=True)
        return None

def scrape_imdb_movies():
    """Main scraping function with enhanced logging and scheduling."""
    try:
        logger.info("Starting IMDB scraping session")
        
        _, _, movies_collection = get_mongo_client()
        session = get_http_session()
        
        # Scrape all charts
        # Define all chart types including genres
        chart_types = ['top_250', 'popular', 'trending', 'action', 'comedy', 'horror']
        total_saved = 0
        total_errors = 0
        
        for chart_type in chart_types:
            try:
                # For genre-specific charts, use the source as the chart type
                source = chart_type if chart_type in ['action', 'comedy', 'horror'] else chart_type
                
                logger.info(f"Processing {chart_type} chart...")
                movie_urls = scrape_imdb_chart(chart_type)
                if not movie_urls:
                    logger.warning(f"No movies found in {chart_type} chart")
                    continue
                
                saved_count = 0
                error_count = 0
                
                # Process each movie URL
                for i, url in enumerate(movie_urls, 1):
                    try:
                        # Use the source directly for genre-specific charts
                        source = f'imdb_{chart_type}'
                        
                        movie_data = scrape_movie_page(
                            session=session,
                            url=url,
                            source=source,
                            chart_type=chart_type  # Pass the chart_type to scrape_movie_page
                        )
                        if not movie_data:
                            error_count += 1
                            continue
                        
                        # Update or insert movie
                        result = movies_collection.update_one(
                            {'imdb_id': movie_data['imdb_id']},
                            {'$set': movie_data},
                            upsert=True
                        )
                        
                        if result.upserted_id:
                            saved_count += 1
                        
                        logger.debug(f"Processed {i}/{len(movie_urls)} from {chart_type}: {movie_data.get('title')}")
                        
                        # Be nice to IMDB
                        time.sleep(1.5)  # Slightly longer delay to avoid rate limiting
                        
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Error processing {url}: {str(e)}")
                
                logger.info(f"{chart_type}: Saved {saved_count}, Errors {error_count}")
                total_saved += saved_count
                total_errors += error_count
                
            except Exception as e:
                logger.error(f"Failed to process {chart_type} chart: {str(e)}")
                continue
        
        logger.info(f"Scraping complete. Total saved: {total_saved}, Total errors: {total_errors}")
        
    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}", exc_info=True)
    finally:
        if 'session' in locals():
            session.close()