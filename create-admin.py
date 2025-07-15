import os
import sys
from dotenv import load_dotenv

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()  # Load environment variables

from app.database import SessionLocal, engine
from app import models, auth

def create_admin_user():
    db = SessionLocal()
    
    # Check if admin already exists
    admin = db.query(models.User).filter(models.User.username == "admin").first()
    if admin:
        print("Admin user already exists!")
        return
    
    # Create new admin user
    hashed_password = auth.get_password_hash("admin123")
    db_user = models.User(
        username="admin",
        hashed_password=hashed_password,
        is_active=True,
        is_admin=True
    )
    
    db.add(db_user)
    db.commit()
    print("Admin user created successfully!")
    
    db.close()

if __name__ == "__main__":
    # Ensure tables are created
    models.Base.metadata.create_all(bind=engine)
    create_admin_user()