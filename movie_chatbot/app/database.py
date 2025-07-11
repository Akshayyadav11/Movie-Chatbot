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
    if mongo_client is None:
        mongo_client = MongoClient(MONGO_DB_URL, serverSelectionTimeoutMS=5000)
        mongo_db = mongo_client["movie_chatbot"]
        movies_collection = mongo_db["movies"]
    return mongo_client, mongo_db, movies_collection

# Initialize MongoDB connection
get_mongo_client()

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