from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
import uuid
import re

from app.models.movie import Movie, RecognitionHistory, Favorite
from app.schemas.movie import MovieCreate, MovieOut, RecognitionHistoryOut, FavoriteOut
from app.db import get_db
from app.services.ml_service import ml_service, recommend_movies
from app.services.tmdb_service import tmdb_service
from app.services.auth_service import get_current_user
from app.models.user import User

from sqlalchemy import or_


router = APIRouter(prefix="/movies", tags=["movies"])

@router.get("/search", response_model=List[MovieOut])
async def search_movies(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Movie).where(Movie.title.ilike(f"%{q}%")).limit(20)
    )
    return result.scalars().all()

@router.get("/recommendations", response_model=List[MovieOut])
async def get_recommendations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    recommended_titles = await recommend_movies(user.id)
    
    # Try to find these movies in our DB
    result = await db.execute(
        select(Movie).where(Movie.title.in_(recommended_titles))
    )
    return result.scalars().all()

@router.post("/recognize", response_model=MovieOut)
async def recognize_movie(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Limit upload size (10MB)
    MAX_SIZE = 10 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")
    
    # Recognize movie using ML service (Gemini or local FAISS fallback)
    recognition_result = await ml_service.recognize_movie(content, file.content_type, filename_hint=file.filename)
    
    if not recognition_result:
        raise HTTPException(status_code=404, detail="Movie not recognized")

    # ── CASE 1: Local FAISS Match ─────────────────────────────────────────
    if "local_movie_id" in recognition_result:
        movie_id = uuid.UUID(recognition_result["local_movie_id"])
        result = await db.execute(select(Movie).where(Movie.id == movie_id))
        db_movie = result.scalar_one_or_none()
        
        if db_movie:
            # Save to history
            history_entry = RecognitionHistory(
                user_id=user.id,
                movie_id=db_movie.id,
                confidence_score=str(recognition_result.get("confidence", "0.85")),
            )
            db.add(history_entry)
            await db.commit()
            return db_movie

    # ── CASE 2: Text Recognition (TMDB-based or Gemini) ─────────────────────────────────
    title = recognition_result.get("title")
    confidence = recognition_result.get("confidence", 0.0)
    is_new = recognition_result.get("is_new", False)

    # Reject low confidence results to avoid wrong matches
    # But allow filename-based TMDB searches (confidence 0.5+)
    min_confidence = 0.5 if is_new else 0.6
    if not title or confidence < min_confidence:
        print(f"Low confidence ({confidence}), rejecting match")
        raise HTTPException(status_code=404, detail="Movie not recognized with sufficient confidence.")

    year = recognition_result.get("year")
    confidence_str = str(confidence)

    # TMDB Search Strategy
    tmdb_results = await tmdb_service.search_movies(title, year=year)
    if not tmdb_results and year:
        tmdb_results = await tmdb_service.search_movies(title)
    if not tmdb_results and ("(" in title or "—" in title or ":" in title):
        clean_title = re.split(r'\(|—|:', title)[0].strip()
        tmdb_results = await tmdb_service.search_movies(clean_title, year=year)
        if not tmdb_results:
            tmdb_results = await tmdb_service.search_movies(clean_title)

    if not tmdb_results:
        raise HTTPException(status_code=404, detail=f"Recognized as '{title}', but details not found in database.")

    tmdb_data = tmdb_results[0]
    tmdb_id = tmdb_data["id"]

    # Check if exists
    result = await db.execute(select(Movie).where(Movie.tmdb_id == tmdb_id))
    db_movie = result.scalar_one_or_none()

    if not db_movie:
        full_details = await tmdb_service.get_movie_details(tmdb_id)
        db_movie = tmdb_service.map_to_movie_model(full_details or tmdb_data)
        db.add(db_movie)
        await db.commit()
        await db.refresh(db_movie)

    # Save to history
    history_entry = RecognitionHistory(
        user_id=user.id,
        movie_id=db_movie.id,
        confidence_score=confidence_str,
    )
    db.add(history_entry)
    await db.commit()

    return db_movie

@router.get("/history", response_model=List[RecognitionHistoryOut])
async def get_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(RecognitionHistory)
        .where(RecognitionHistory.user_id == user.id)
        .order_by(RecognitionHistory.created_at.desc())
    )
    return result.scalars().all()

@router.get("/favorites", response_model=List[FavoriteOut])
async def get_favorites(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Favorite)
        .where(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc())
    )
    return result.scalars().all()

@router.get("/", response_model=List[MovieOut])
async def list_movies(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * size
    result = await db.execute(
        select(Movie)
        .order_by(Movie.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    return result.scalars().all()

@router.post("/{movie_id}/favorite", status_code=status.HTTP_201_CREATED)
async def add_favorite(
    movie_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if movie exists
    result = await db.execute(select(Movie).where(Movie.id == movie_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Movie not found")

    # Check if already favorited
    result = await db.execute(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.movie_id == movie_id)
    )
    if result.scalar_one_or_none():
        return {"message": "Already in favorites"}

    favorite = Favorite(user_id=user.id, movie_id=movie_id)
    db.add(favorite)
    await db.commit()
    return {"message": "Added to favorites"}

@router.delete("/{movie_id}/favorite")
async def remove_favorite(
    movie_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.movie_id == movie_id)
    )
    favorite = result.scalar_one_or_none()
    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")

    await db.delete(favorite)
    await db.commit()
    return {"message": "Removed from favorites"}

@router.get("/{movie_id}", response_model=MovieOut)
async def get_movie(movie_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie
