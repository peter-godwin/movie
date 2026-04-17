import uuid
from sqlalchemy import Column, String, DateTime, func, Integer, Text, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base

class Movie(Base):
    __tablename__ = "movies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tmdb_id = Column(Integer, unique=True, index=True, nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    release_date = Column(Date, nullable=True)
    poster_path = Column(String(255), nullable=True)
    backdrop_path = Column(String(255), nullable=True)
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

class RecognitionHistory(Base):
    __tablename__ = "recognition_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    movie_id = Column(UUID(as_uuid=True), ForeignKey("movies.id"), nullable=False)
    
    media_url = Column(String(512), nullable=True)
    confidence_score = Column(String(50), nullable=True)
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="recognition_history")
    movie = relationship("Movie")

class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    movie_id = Column(UUID(as_uuid=True), ForeignKey("movies.id"), nullable=False)
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="favorites")
    movie = relationship("Movie")
