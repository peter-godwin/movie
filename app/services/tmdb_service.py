import httpx
from typing import Optional, Dict, Any, List
from app.config import settings
from app.models.movie import Movie
from datetime import datetime

class TMDBService:
    def __init__(self):
        self.api_key = settings.tmdb_api_key
        self.base_url = "https://api.themoviedb.org/3"
        self.headers = {
            "accept": "application/json",
        }

    async def get_movie_details(self, tmdb_id: int) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/movie/{tmdb_id}?api_key={self.api_key}&language=en-US"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    return response.json()
                return None
        except Exception as e:
            print(f"TMDB connection error (get_details): {e}")
            return None

    async def search_movies(self, query: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/search/movie?api_key={self.api_key}&query={query}&language=en-US&page=1"
        if year:
            url += f"&year={year}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    return response.json().get("results", [])
                return []
        except Exception as e:
            print(f"TMDB connection error (search): {e}")
            return []

    async def get_popular_movies(self, page: int = 1) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/movie/popular?api_key={self.api_key}&language=en-US&page={page}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    return response.json().get("results", [])
                return []
        except Exception as e:
            print(f"TMDB connection error (popular): {e}")
            return []

    def map_to_movie_model(self, tmdb_data: Dict[str, Any]) -> Movie:
        release_date = None
        if tmdb_data.get("release_date"):
            try:
                release_date = datetime.strptime(tmdb_data["release_date"], "%Y-%m-%d").date()
            except ValueError:
                pass

        return Movie(
            tmdb_id=tmdb_data.get("id"),
            title=tmdb_data.get("title"),
            description=tmdb_data.get("overview"),
            release_date=release_date,
            poster_path=tmdb_data.get("poster_path"),
            backdrop_path=tmdb_data.get("backdrop_path"),
        )

tmdb_service = TMDBService()
