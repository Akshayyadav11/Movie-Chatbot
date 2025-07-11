from app.database import SessionLocal, init_db
from app.models import User
from app.auth import get_password_hash

def create_admin_user(username: str, password: str):
    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"User '{username}' already exists. Updating to admin...")
            existing_user.hashed_password = get_password_hash(password)
            existing_user.is_admin = True
            existing_user.is_active = True
        else:
            # Create new admin user
            hashed_password = get_password_hash(password)
            admin_user = User(
                username=username,
                hashed_password=hashed_password,
                is_admin=True,
                is_active=True
            )
            db.add(admin_user)
        
        db.commit()
        print(f"Admin user '{username}' has been created/updated successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error creating admin user: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Initialize the database
    init_db()
    
    # Create admin user
    admin_username = "admin"
    admin_password = "admin123"  # In production, use a more secure password
    
    create_admin_user(admin_username, admin_password)
