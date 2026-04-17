import faiss
import numpy as np
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.movie import Movie
import asyncio
from PIL import Image
import io
import httpx
import os
import json
import uuid

class VectorService:
    def __init__(self):
        # CLIP model: Excellent for Image-to-Image comparison
        self.model = SentenceTransformer('clip-ViT-B-32')
        self.index = None
        self.movie_ids = []
        self.index_path = "movie_vectors.index"
        self.ids_path = "movie_ids.json"

    def _initialize_index(self, dimension: int):
        # Using Inner Product (Cosine Similarity) instead of L2 for better CLIP matching
        self.index = faiss.IndexFlatIP(dimension)

    async def _download_image(self, url: str, client: httpx.AsyncClient) -> Optional[Image.Image]:
        try:
            response = await client.get(url)
            if response.status_code == 200:
                return Image.open(io.BytesIO(response.content))
        except Exception as e:
            print(f"Failed to download visual {url}: {e}")
        return None

    async def _process_movie_visuals(self, movie: Movie, client: httpx.AsyncClient, semaphore: asyncio.Semaphore):
        async with semaphore:
            visuals = []
            if movie.poster_path:
                visuals.append(f"https://image.tmdb.org/t/p/w300{movie.poster_path}")
            if movie.backdrop_path:
                # w780 is faster than w1280 and still great for recognition
                visuals.append(f"https://image.tmdb.org/t/p/w780{movie.backdrop_path}")

            results = []
            for url in visuals:
                img = await self._download_image(url, client)
                if img:
                    results.append((img, movie.id))
            return results

    async def index_movies(self, db: AsyncSession, force: bool = False):
        """
        Populate FAISS index. Loads from disk if available, otherwise indexes from DB.
        """
        # 1. Try loading from disk first
        if not force and os.path.exists(self.index_path) and os.path.exists(self.ids_path):
            try:
                print("Loading existing movie index from disk...")
                self.index = faiss.read_index(self.index_path)
                with open(self.ids_path, 'r') as f:
                    id_strs = json.load(f)
                    self.movie_ids = [uuid.UUID(i) for i in id_strs]
                print(f"Successfully loaded index with {len(self.movie_ids)} vectors.")
                return
            except Exception as e:
                print(f"Failed to load index from disk: {e}. Re-indexing...")

        # 2. Re-index from DB
        print("Indexing movie visuals into FAISS (this may take a few minutes)...")
        result = await db.execute(select(Movie))
        movies = result.scalars().all()

        if not movies:
            print("No movies found in DB to index.")
            return

        all_images = []
        all_ids = []
        
        # Parallel downloads with concurrency limit
        semaphore = asyncio.Semaphore(10) # 10 parallel downloads
        async with httpx.AsyncClient(timeout=15.0) as client:
            tasks = [self._process_movie_visuals(m, client, semaphore) for m in movies]
            batch_results = await asyncio.gather(*tasks)
            
            for res_list in batch_results:
                for img, mid in res_list:
                    all_images.append(img)
                    all_ids.append(mid)

        if not all_images:
            print("No visuals could be downloaded.")
            return

        print(f"Encoding {len(all_images)} visuals... (CPU intensive)")
        
        # Encode in batches to manage memory
        valid_embeddings = []
        batch_size = 64
        loop = asyncio.get_event_loop()
        
        for i in range(0, len(all_images), batch_size):
            batch = all_images[i : i + batch_size]
            print(f"Processing batch {i//batch_size + 1}/{(len(all_images)-1)//batch_size + 1}...")
            # CLIP model handles batches natively and efficiently
            emb = await loop.run_in_executor(None, lambda b=batch: self.model.encode(b))
            valid_embeddings.extend(emb)

        embeddings_np = np.array(valid_embeddings).astype('float32')
        faiss.normalize_L2(embeddings_np)
        
        self._initialize_index(embeddings_np.shape[1])
        self.index.add(embeddings_np)
        self.movie_ids = all_ids

        # 3. Save to disk for next time
        try:
            faiss.write_index(self.index, self.index_path)
            with open(self.ids_path, 'w') as f:
                json.dump([str(i) for i in self.movie_ids], f)
            print("Index saved to disk for future use.")
        except Exception as e:
            print(f"Failed to save index to disk: {e}")

        print(f"Successfully indexed {len(self.movie_ids)} visual vectors.")

    async def find_movie_by_frames(self, frame_bytes_list: List[bytes], top_k: int = 1) -> Optional[Movie]:
        """
        Find the most similar movie by comparing video frames to indexed visuals.
        Instead of averaging, we check each frame individually for the 'best' match.
        """
        if not self.index or not self.movie_ids:
            return None

        # Convert bytes to PIL Images
        images = []
        for b in frame_bytes_list:
            try:
                images.append(Image.open(io.BytesIO(b)))
            except:
                continue
        
        if not images:
            return None
            
        # Generate image embeddings for all frames at once
        loop = asyncio.get_event_loop()
        image_embeddings = await loop.run_in_executor(None, lambda: self.model.encode(images))
        
        # Ensure it's a 2D array even for a single image
        if len(image_embeddings.shape) == 1:
            image_embeddings = image_embeddings.reshape(1, -1)
            
        # Search FAISS index for each frame
        image_embeddings_np = image_embeddings.astype('float32')
        faiss.normalize_L2(image_embeddings_np)
        
        distances, indices = self.index.search(image_embeddings_np, 1)
        
        # Find the single best frame match (maximum similarity)
        best_score_idx = np.argmax(distances)
        best_score = distances[best_score_idx][0]
        best_match_idx = indices[best_score_idx][0]
        
        print(f"Visual Match Best Confidence: {best_score:.4f}")

        # CLIP Cross-domain threshold (Poster/Backdrop vs Frame): 0.32 is usually safe
        # Backdrops make this much more reliable than posters alone.
        if best_match_idx < 0 or best_match_idx >= len(self.movie_ids) or best_score < 0.32:
            return None
            
        return self.movie_ids[best_match_idx]

vector_service = VectorService()
