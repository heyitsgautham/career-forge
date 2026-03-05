"""
Gemini Client
=============
Google Gemini API client with automatic key rotation.
"""

import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import structlog

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings


logger = structlog.get_logger()


@dataclass
class APIKeyState:
    """Track state of an API key."""
    key: str
    last_used: Optional[datetime] = None
    error_count: int = 0
    is_rate_limited: bool = False
    rate_limit_reset: Optional[datetime] = None


class GeminiClient:
    """
    Gemini API client with automatic key rotation and rate limit handling.
    
    Features:
    - Rotates through multiple API keys
    - Handles rate limiting gracefully
    - Retries with exponential backoff
    - Tracks key health and errors
    """
    
    def __init__(self):
        self.api_keys: List[APIKeyState] = []
        self.current_key_index: int = 0
        self._lock = asyncio.Lock()
        self._initialized = False
        
        # Safety settings for all requests
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
    
    def initialize(self):
        """Initialize API keys from settings."""
        if self._initialized:
            return
            
        keys = settings.gemini_api_keys
        if not keys:
            raise ValueError("No Gemini API keys configured")
        
        self.api_keys = [APIKeyState(key=k) for k in keys]
        logger.info(f"Initialized Gemini client with {len(keys)} API keys")
        self._initialized = True
    
    def _get_available_key(self) -> APIKeyState:
        """Get the next available API key, skipping rate-limited ones."""
        now = datetime.utcnow()
        
        for _ in range(len(self.api_keys)):
            key_state = self.api_keys[self.current_key_index]
            
            # Check if rate limit has expired
            if key_state.is_rate_limited:
                if key_state.rate_limit_reset and now > key_state.rate_limit_reset:
                    key_state.is_rate_limited = False
                    key_state.rate_limit_reset = None
                    logger.info(f"API key {self.current_key_index} rate limit reset")
            
            # Use this key if not rate limited
            if not key_state.is_rate_limited:
                return key_state
            
            # Try next key
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        
        # All keys are rate limited
        raise Exception("All API keys are rate limited")
    
    def _rotate_key(self):
        """Rotate to the next API key."""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
    
    def _mark_rate_limited(self, key_state: APIKeyState, duration_seconds: int = 60):
        """Mark a key as rate limited."""
        key_state.is_rate_limited = True
        key_state.rate_limit_reset = datetime.utcnow() + timedelta(seconds=duration_seconds)
        key_state.error_count += 1
        logger.warning(f"API key marked as rate limited for {duration_seconds}s")
        self._rotate_key()
    
    def _configure_genai(self, api_key: str):
        """Configure the genai library with the given API key."""
        genai.configure(api_key=api_key)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,))
    )
    async def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_mime_type: str = "text/plain",
    ) -> str:
        """
        Generate content using Gemini with automatic key rotation.
        
        Args:
            prompt: The user prompt
            system_instruction: System prompt for context
            temperature: Override default temperature
            max_tokens: Override default max tokens
            response_mime_type: Response format (text/plain or application/json)
            
        Returns:
            Generated text content
        """
        self.initialize()
        
        async with self._lock:
            key_state = self._get_available_key()
            self._configure_genai(key_state.key)
        
        try:
            # Build generation config
            generation_config = {
                "temperature": temperature or settings.GEMINI_TEMPERATURE,
                "max_output_tokens": max_tokens or settings.GEMINI_MAX_TOKENS,
            }
            
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                safety_settings=self.safety_settings,
                generation_config=generation_config,
            )
            
            # Build the full prompt with system instruction
            full_prompt = prompt
            if system_instruction:
                full_prompt = f"{system_instruction}\n\n---\n\n{prompt}"
            
            # For JSON responses, add instruction to return JSON
            if response_mime_type == "application/json":
                full_prompt += "\n\nIMPORTANT: Return ONLY valid JSON, no markdown, no code blocks, no extra text."
            
            response = await asyncio.to_thread(
                model.generate_content,
                full_prompt
            )
            
            key_state.last_used = datetime.utcnow()
            key_state.error_count = 0
            
            # Rotate key for load distribution
            self._rotate_key()
            
            return response.text
            
        except Exception as e:
            error_str = str(e).lower()
            
            if "rate limit" in error_str or "quota" in error_str or "429" in error_str:
                self._mark_rate_limited(key_state, duration_seconds=60)
            else:
                key_state.error_count += 1
            
            logger.error(f"Gemini API error: {e}")
            raise
    
    async def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generate JSON content using Gemini.
        
        Args:
            prompt: The user prompt
            system_instruction: System prompt for context
            temperature: Override default temperature
            
        Returns:
            Parsed JSON response
        """
        import json
        import re
        
        response = await self.generate_content(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=temperature or 0.1,  # Lower temp for structured output
            response_mime_type="application/json",
        )
        
        # Clean up response - remove markdown code blocks if present
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        return json.loads(cleaned)
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using Gemini embedding model.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector (768 dimensions)
        """
        self.initialize()
        
        async with self._lock:
            key_state = self._get_available_key()
            self._configure_genai(key_state.key)
        
        try:
            result = await asyncio.to_thread(
                genai.embed_content,
                model=f"models/{settings.GEMINI_EMBEDDING_MODEL}",
                content=text,
                task_type="retrieval_document",
            )
            
            key_state.last_used = datetime.utcnow()
            self._rotate_key()
            
            return result["embedding"]
            
        except Exception as e:
            error_str = str(e).lower()
            
            if "rate limit" in error_str or "quota" in error_str:
                self._mark_rate_limited(key_state)
            
            logger.error(f"Embedding error: {e}")
            raise
    
    async def generate_embeddings_batch(
        self, 
        texts: List[str], 
        batch_size: int = 10
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts with batching.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = await asyncio.gather(
                *[self.generate_embedding(text) for text in batch]
            )
            embeddings.extend(batch_embeddings)
            
            # Small delay between batches
            if i + batch_size < len(texts):
                await asyncio.sleep(0.5)
        
        return embeddings
    
    def get_key_stats(self) -> List[Dict[str, Any]]:
        """Get statistics for all API keys."""
        return [
            {
                "index": i,
                "last_used": ks.last_used.isoformat() if ks.last_used else None,
                "error_count": ks.error_count,
                "is_rate_limited": ks.is_rate_limited,
                "rate_limit_reset": ks.rate_limit_reset.isoformat() if ks.rate_limit_reset else None,
            }
            for i, ks in enumerate(self.api_keys)
        ]


# Global client instance
gemini_client = GeminiClient()
