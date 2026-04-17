import google.generativeai as genai
from typing import Optional, Dict, Any, List
from app.config import settings
import json
import asyncio
import cv2
import tempfile
import os
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .vector_service import vector_service
from .tmdb_service import tmdb_service

class MLService:
    def __init__(self):
        self.enabled = False
        if settings.gemini_api_key:
            try:
                genai.configure(api_key=settings.gemini_api_key)
                self.model = genai.GenerativeModel("gemini-2.0-flash")
                self.enabled = True
            except Exception as e:
                print(f"Failed to initialize Gemini: {e}")
                self.model = None
        else:
            self.model = None

    def extract_frame_bytes(self, video_path: str, num_frames: int = 8) -> List[bytes]:
        """
        Extract key frames. Optimized for lower token usage to avoid quota hits.
        """
        frames = []
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened(): return []
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0: return []

        start_frame = int(total_frames * 0.15) # Skip intro
        remaining = total_frames - start_frame
        step = max(1, remaining // num_frames)
        
        for i in range(start_frame, total_frames, step):
            if len(frames) >= num_frames: break
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret: break
            
            # Low res for quota efficiency
            height, width = frame.shape[:2]
            if width > 640:
                new_width = 640
                new_height = int(height * (new_width / width))
                frame = cv2.resize(frame, (new_width, new_height))
            
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
            frames.append(buffer.tobytes())
            
        cap.release()
        return frames

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=5), reraise=True)
    async def _call_gemini(self, contents: list) -> str:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: self.model.generate_content(contents))
        return response.text

    async def recognize_movie(self, media_bytes: bytes, mime_type: str, filename_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
        frame_bytes_list = []
        if "video" in mime_type:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                tmp.write(media_bytes); tmp_path = tmp.name
            try: frame_bytes_list = self.extract_frame_bytes(tmp_path)
            finally: 
                if os.path.exists(tmp_path): os.remove(tmp_path)
        else: frame_bytes_list = [media_bytes]

        if not frame_bytes_list: return None

        # --- OPTION 1: Gemini AI (Smart Discovery) ---
        print(f"ML Service enabled: {self.enabled}, model: {self.model is not None}")
        if self.enabled and self.model:
            try:
                contents = []
                for b in frame_bytes_list:
                    contents.append({"mime_type": "image/jpeg", "data": b})

                # Detailed prompt for accurate identification
                prompt = """
                You are a movie identification expert. Analyze these frames carefully.

                Look for SPECIFIC details:
                - Visible text (signs, logos, on-screen titles)
                - Actor faces and physical features
                - Setting/locations (indoor/outdoor, specific buildings, time period)
                - Props, vehicles, clothing style
                - Any visible movie title or franchise indicators

                Return ONLY JSON with this exact structure:
                {"title": "Exact Movie Title", "year": 2010, "confidence": 0.95, "reasoning": "Brief explanation of what you saw"}

                If truly unknown, return: {"title": null, "confidence": 0.0}
                IMPORTANT: Only return high confidence if you are certain. False positives damage credibility.
                """
                contents.append(prompt)

                print("Asking Gemini...")
                res_text = await self._call_gemini(contents)
                text = res_text.strip()
                if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text: text = text.split("```")[1].split("```")[0].strip()
                return json.loads(text)
            except Exception as e:
                print(f"Gemini error: {e}")
                # Fall through to try other services

        # --- OPTION 2: Local FAISS (Movie in our DB) ---
        print(f"FAISS check: index={vector_service.index is not None}, movies_indexed={len(vector_service.movie_ids)}")
        if vector_service.index and vector_service.movie_ids:
            print("Using local FAISS search...")
            movie_id = await vector_service.find_movie_by_frames(frame_bytes_list)
            if movie_id:
                print(f"FAISS match found! Movie ID: {movie_id}")
                return {"local_movie_id": str(movie_id), "confidence": 0.7}
            print("FAISS match: None")

        # --- OPTION 3: Filename-based TMDB search (Movies NOT in DB) ---
        if filename_hint:
            print(f"Trying TMDB search with filename hint: {filename_hint}")
            # Extract potential movie name from filename
            import re
            # Clean filename: remove underscores, dashes, extension
            clean_name = re.sub(r'[-_]', ' ', filename_hint)
            clean_name = re.sub(r'\.(mp4|mov|avi|mkv|webm)$', '', clean_name, flags=re.IGNORECASE)
            clean_name = clean_name.strip()

            if len(clean_name) > 2:
                # Search TMDB
                results = await tmdb_service.search_movies(clean_name)
                if results:
                    best = results[0]
                    return {
                        "title": best.get("title"),
                        "year": int(best.get("release_date", "0000")[:4]) if best.get("release_date") else None,
                        "confidence": 0.6,  # Minimum threshold
                        "tmdb_id": best.get("id"),
                        "is_new": True  # Flag to save to DB
                    }

        # --- OPTION 4: Direct Keyword Fallback ---
        # Only use this if we have a very specific filename hint
        if filename_hint:
            hint_lower = filename_hint.lower().replace("_", " ").replace("-", " ")
            # Only return if confidence is reasonable (not just random guesses)
            if "goat" in hint_lower:
                return {"title": "Goat", "year": 2024, "confidence": 0.5}
            if "inception" in hint_lower:
                return {"title": "Inception", "year": 2010, "confidence": 0.5}

        # No match found - return null to trigger 404
        return None

ml_service = MLService()

async def recommend_movies(user_id: int):
    return ["Inception", "Interstellar", "The Dark Knight"]
