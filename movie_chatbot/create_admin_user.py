from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from passlib.context import CryptContext

# Import models directly to avoid circular imports
from app.models import Base, User
from app.database import SessionLocal

# Create password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_admin():
    # Get database session
    db = SessionLocal()
    
    # Create tables if they don't exist
    Base.metadata.create_all(bind=db.bind)
    
    try:
        # Check if admin user already exists
        admin_username = "admin@example.com"
        admin_password = "admin123"
        
        # Check if user exists
        existing_user = db.query(User).filter(User.username == admin_username).first()
        
        if existing_user:
            print(f"Admin user '{admin_username}' already exists. Updating password...")
            # Update existing user
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
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
