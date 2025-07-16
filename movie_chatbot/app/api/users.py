from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user, get_admin_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/users/", response_model=List[schemas.User])
async def read_users(
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_admin_user)
):
    """
    Retrieve all users (admin only)
    """
    users = db.query(models.User).offset(skip).limit(limit).all()
    return users

@router.post("/users/", response_model=schemas.User)
async def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_admin_user)
):
    """
    Create a new user (admin only)
    """
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        is_active=user.is_active,
        is_admin=user.is_admin
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.get("/users/me/", response_model=schemas.User)
async def read_user_me(current_user: models.User = Depends(get_current_user)):
    """
    Get current user information
    """
    return current_user

@router.get("/users/{user_id}", response_model=schemas.User)
async def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_admin_user)
):
    """
    Get a specific user by ID (admin only)
    """
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@router.put("/users/{user_id}", response_model=schemas.User)
async def update_user(
    user_id: int,
    user: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_admin_user)
):
    """
    Update a user (admin only)
    """
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user.dict(exclude_unset=True)
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_admin_user)
):
    """
    Delete a user (admin only)
    """
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(db_user)
    db.commit()
    return {"ok": True}

def get_password_hash(password: str):
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)
