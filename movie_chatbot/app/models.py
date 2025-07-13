from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.types import TypeDecorator, String as SQLString
from sqlalchemy.ext.declarative import declarative_base
import json

# SQLAlchemy Base
Base = declarative_base()

# Pydantic models (for request/response validation)
class MovieBase(BaseModel):
    title: str
    year: str
    rating: str
    genre: str
    director: str
    cast: List[str]
    plot: str
    image: str
    url: str
    runtime: str
    awards: str

class MovieCreate(MovieBase):
    pass

class MovieUpdate(BaseModel):
    title: Optional[str] = None
    year: Optional[str] = None
    rating: Optional[str] = None
    genre: Optional[str] = None
    director: Optional[str] = None
    cast: Optional[List[str]] = None
    plot: Optional[str] = None
    image: Optional[str] = None
    url: Optional[str] = None
    runtime: Optional[str] = None
    awards: Optional[str] = None

# SQLAlchemy models
class JSONEncodedDict(TypeDecorator):
    """Represents an immutable structure as a json-encoded string."""
    impl = SQLString

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    year = Column(String)
    rating = Column(String)
    genre = Column(String)
    director = Column(String)
    cast = Column(JSONEncodedDict)  # Store as JSON string
    plot = Column(String)
    image = Column(String)
    url = Column(String, unique=True)
    runtime = Column(String)
    awards = Column(String)
