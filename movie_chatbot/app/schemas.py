from pydantic import BaseModel
from typing import Optional, List
from datetime import date

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None

class UserCreate(UserBase):
    password: str
    is_active: bool = True
    is_admin: bool = False

class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None

class User(UserBase):
    id: int
    is_active: bool
    is_admin: bool

    class Config:
        from_attributes = True

class MovieBase(BaseModel):
    title: str
    year: int
    rating: float
    genres: List[str]
    directors: List[str]
    cast: List[str]
    plot: str
    release_date: Optional[date] = None
    duration: Optional[int] = None  # in minutes

class Movie(MovieBase):
    id: str

    class Config:
        from_attributes = True

class ChatMessage(BaseModel):
    message: str
    is_user: bool

class ReportRequest(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    min_rating: Optional[float] = None