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
    try:
        # Build query based on filters
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
        
        # Get movies from database
        movies = list(movies_collection.find(query).sort("release_date", -1))
        
        if not movies:
            return None
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(movies)
        
        # Clean and convert data
        df['release_date'] = pd.to_datetime(df['release_date'], errors='coerce')
        df = df.dropna(subset=['release_date'])
        
        if df.empty:
            return None
        
        # Create directory for reports if it doesn't exist
        os.makedirs("static/reports", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate plot
        plt.figure(figsize=(14, 8))
        
        # Plot 1: Movies by Month
        plt.subplot(2, 1, 1)
        monthly_data = df.groupby(df['release_date'].dt.to_period('M')).size()
        monthly_data.plot(kind='bar', color='skyblue', ax=plt.gca())
        plt.title('Movies Released by Month')
        plt.xlabel('Month')
        plt.ylabel('Number of Movies')
        plt.xticks(rotation=45)
        
        # Plot 2: Rating Distribution
        plt.subplot(2, 1, 2)
        if 'rating' in df.columns:
            try:
                df['rating_num'] = pd.to_numeric(df['rating'], errors='coerce')
                df = df.dropna(subset=['rating_num'])
                if not df.empty:
                    df['rating_num'].plot(kind='hist', bins=10, color='lightgreen', ax=plt.gca())
                    plt.title('Rating Distribution')
                    plt.xlabel('Rating')
                    plt.ylabel('Count')
            except Exception as e:
                logger.error(f"Error processing ratings: {str(e)}")
        
        plt.tight_layout()
        
        # Save plot
        plot_path = f"static/reports/movie_report_{timestamp}.png"
        plt.savefig(plot_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        # Generate CSV with selected columns
        csv_path = f"static/reports/movie_report_{timestamp}.csv"
        columns_to_export = ['title', 'year', 'rating', 'genre', 'release_date', 'director', 'runtime']
        export_columns = [col for col in columns_to_export if col in df.columns]
        
        # Add any additional columns that might be useful
        additional_columns = [col for col in df.columns if col not in columns_to_export and col not in ['_id', 'cast']]
        export_columns.extend(additional_columns)
        
        # Export to CSV
        df[export_columns].to_csv(csv_path, index=False)
        
        # Clean up old reports (keep last 5)
        clean_up_old_reports()
        
        return {
            "plot_path": plot_path,
            "csv_path": csv_path,
            "movie_count": len(movies),
            "date_range": {
                "start": df['release_date'].min().strftime('%Y-%m-%d'),
                "end": df['release_date'].max().strftime('%Y-%m-%d')
            },
            "average_rating": df['rating'].mean() if 'rating' in df.columns and not df.empty else None
        }
    except Exception as e:
        logger.error(f"Error generating movie report: {str(e)}")
        return None

def clean_up_old_reports(max_files=5):
    """Keep only the most recent report files"""
    try:
        if not os.path.exists("static/reports"):
            return
            
        # Get all report files
        report_files = []
        for f in os.listdir("static/reports"):
            if f.startswith("movie_report_") and (f.endswith(".png") or f.endswith(".csv")):
                file_path = os.path.join("static/reports", f)
                report_files.append((file_path, os.path.getmtime(file_path)))
        
        # Sort by modification time (newest first)
        report_files.sort(key=lambda x: x[1], reverse=True)
        
        # Keep only the most recent files
        for file_path, _ in report_files[max_files*2:]:  # *2 because we have both .png and .csv
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Could not remove old report file {file_path}: {str(e)}")
    except Exception as e:
        logger.error(f"Error cleaning up old reports: {str(e)}")