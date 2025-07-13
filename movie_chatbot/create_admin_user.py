from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, User
from app.auth import get_password_hash
import os

# Create engine and session
SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_admin():
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Check if admin user already exists
        admin_username = "admin@example.com"
        admin_password = "admin123"
        
        existing_user = db.query(User).filter(User.username == admin_username).first()
        if existing_user:
            print(f"Admin user '{admin_username}' already exists. Updating password...")
            existing_user.hashed_password = get_password_hash(admin_password)
            existing_user.is_admin = True
            existing_user.is_active = True
        else:
            # Create new admin user
            hashed_password = get_password_hash(admin_password)
            admin_user = User(
                username=admin_username,
                email=admin_username,
                hashed_password=hashed_password,
                is_admin=True,
                is_active=True
            )
            db.add(admin_user)
            print(f"Created new admin user: {admin_username}")
        
        db.commit()
        print("Admin user creation/update successful!")
    except Exception as e:
        db.rollback()
        print(f"Error creating admin user: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
