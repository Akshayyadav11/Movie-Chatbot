import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# SQL Database (for users)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sql_app.db")
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# MongoDB (for movie data)
MONGO_DB_URL = os.getenv("MONGO_DB_URL", "mongodb://mongo:27017/")
mongo_client = None
mongo_db = None
movies_collection = None

def get_mongo_client():
    global mongo_client, mongo_db, movies_collection
    try:
        if mongo_client is None:
            mongo_client = MongoClient(MONGO_DB_URL, serverSelectionTimeoutMS=5000)
            mongo_db = mongo_client["movie_chatbot"]
            movies_collection = mongo_db["movies"]
            
            # Create text index if it doesn't exist
            try:
                # Drop existing text index if any
                current_indexes = movies_collection.index_information()
                for index_name in current_indexes:
                    if any('text' in idx for idx in current_indexes[index_name].get('key', [])):
                        movies_collection.drop_index(index_name)
                
                # Create new text index on title, plot, and genres
                movies_collection.create_index([
                    ("title", "text"),
                    ("plot", "text"),
                    ("genres", "text")
                ])
            except Exception as e:
                logger.error(f"Error creating text index: {str(e)}")
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {str(e)}")
        return None, None, None
    return mongo_client, mongo_db, movies_collection

# Dependency to get DB session
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from .models import Base
    Base.metadata.create_all(bind=engine)