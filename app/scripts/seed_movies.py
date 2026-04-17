import sys
import asyncio
from pathlib import Path
from sqlalchemy.future import select

# Ensure project root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.movie import Movie
from app.db.database import AsyncSessionLocal
from app.services.tmdb_service import tmdb_service
from app.config import settings

async def seed():
    if not settings.tmdb_api_key:
        print("TMDB_API_KEY not found. Cannot seed real movies.")
        return

    print("Fetching Top 2000 popular movies from TMDB...")

    async with AsyncSessionLocal() as session:
        added_count = 0
        # TMDB returns 20 movies per page. 100 pages = 2000 movies.
        for page in range(1, 101):
            print(f"Processing page {page}/25...")
            movies_data = await tmdb_service.get_popular_movies(page=page)
            
            if not movies_data:
                print(f"Failed to fetch data for page {page}. Stopping.")
                break

            for movie_data in movies_data:
                tmdb_id = movie_data["id"]
                
                # Check if movie already exists
                result = await session.execute(select(Movie).where(Movie.tmdb_id == tmdb_id))
                if result.scalar_one_or_none():
                    continue
                
                # Map and add movie
                db_movie = tmdb_service.map_to_movie_model(movie_data)
                session.add(db_movie)
                added_count += 1
            
            # Commit every page to avoid massive transactions
            await session.commit()
            
        print(f"Seed complete! Added {added_count} new movies from TMDB.")

if __name__ == "__main__":
    asyncio.run(seed())
