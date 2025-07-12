#!/usr/bin/env python3
import os
import pymongo
from pymongo import MongoClient
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def get_mongo_client():
    """Get MongoDB client and database."""
    try:
        # Use the same connection logic as in your app
        mongo_uri = os.getenv('MONGODB_URL', 'mongodb://localhost:27017/')
        client = MongoClient(mongo_uri)
        db = client[os.getenv('MONGO_DB', 'movie_chatbot')]
        return client, db, db.movies
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise

def main():
    try:
        # Get MongoDB connection
        client, db, movies_collection = get_mongo_client()
        
        # Get database stats
        stats = db.command('dbstats')
        logger.info(f"Database: {db.name}")
        logger.info(f"Collections: {db.list_collection_names()}")
        logger.info(f"Total documents: {stats['objects']}")
        logger.info(f"Total size: {stats['dataSize'] / (1024*1024):.2f} MB")
        
        # Get movie count
        movie_count = movies_collection.count_documents({})
        logger.info(f"Total movies in collection: {movie_count}")
        
        # Get sample movies
        if movie_count > 0:
            logger.info("\nSample movies:")
            for movie in movies_collection.find().limit(3):
                print(f"\nTitle: {movie.get('title', 'N/A')}")
                print(f"Year: {movie.get('year', 'N/A')}")
                print(f"Rating: {movie.get('rating', 'N/A')}")
                print(f"Genres: {', '.join(movie.get('genres', ['N/A']))}")
                print(f"IMDb URL: {movie.get('url', 'N/A')}")
        
        # Get movie count by source
        if movie_count > 0:
            pipeline = [
                {"$group": {"_id": "$source", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            logger.info("\nMovies by source:")
            for stat in movies_collection.aggregate(pipeline):
                print(f"{stat['_id']}: {stat['count']} movies")
        
    except Exception as e:
        logger.error(f"Error checking MongoDB: {e}")
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    main()
