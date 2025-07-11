from sqlalchemy.orm import Session
from . import models, schemas
from .database import movies_collection
from datetime import datetime
from typing import List
import pandas as pd
import matplotlib.pyplot as plt
import os

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_status(db: Session, user_id: int, is_active: bool):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user:
        db_user.is_active = is_active
        db.commit()
        db.refresh(db_user)
        return db_user
    return None

def get_movie(movie_id: str):
    return movies_collection.find_one({"_id": movie_id})

def get_movies(skip: int = 0, limit: int = 100):
    return list(movies_collection.find().skip(skip).limit(limit))

def search_movies(query: str, limit: int = 10):
    return list(movies_collection.find({
        "$text": {"$search": query}
    }, {
        "score": {"$meta": "textScore"}
    }).sort([("score", {"$meta": "textScore"})]).limit(limit))

def get_latest_movies(limit: int = 10):
    return list(movies_collection.find().sort("release_date", -1).limit(limit))

def get_upcoming_movies(limit: int = 10):
    today = datetime.now().date()
    return list(movies_collection.find({
        "release_date": {"$gt": today.isoformat()}
    }).sort("release_date", 1).limit(limit))

def generate_movie_report(start_date=None, end_date=None, min_rating=None):
    query = {}
    if start_date:
        query["release_date"] = {"$gte": start_date.isoformat()}
    if end_date:
        if "release_date" in query:
            query["release_date"]["$lte"] = end_date.isoformat()
        else:
            query["release_date"] = {"$lte": end_date.isoformat()}
    if min_rating is not None:
        query["rating"] = {"$gte": min_rating}
    
    movies = list(movies_collection.find(query))
    
    if not movies:
        return None
    
    df = pd.DataFrame(movies)
    df['release_date'] = pd.to_datetime(df['release_date'])
    
    # Generate plot
    plt.figure(figsize=(10, 6))
    df.groupby(df['release_date'].dt.to_period('M')).size().plot(kind='bar')
    plt.title('Movies Released by Month')
    plt.xlabel('Month')
    plt.ylabel('Number of Movies')
    plt.tight_layout()
    
    plot_path = "static/report_plot.png"
    plt.savefig(plot_path)
    plt.close()
    
    # Generate CSV
    csv_path = "static/movie_report.csv"
    df.to_csv(csv_path, index=False)
    
    return {
        "plot_path": plot_path,
        "csv_path": csv_path,
        "movie_count": len(movies)
    }