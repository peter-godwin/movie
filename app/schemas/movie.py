from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from uuid import UUID
from typing import Optional, List

class MovieBase(BaseModel):
    title: str
    tmdb_id: Optional[int] = None
    description: Optional[str] = None
    release_date: Optional[date] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None

class MovieCreate(MovieBase):
    pass

class MovieUpdate(BaseModel):
    title: Optional[str] = None
    tmdb_id: Optional[int] = None
    description: Optional[str] = None
    release_date: Optional[date] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None

class MovieOut(MovieBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class RecognitionHistoryOut(BaseModel):
    id: UUID
    movie: MovieOut
    media_url: Optional[str] = None
    confidence_score: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FavoriteOut(BaseModel):
    id: UUID
    movie: MovieOut
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
