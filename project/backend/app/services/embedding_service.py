"""
Embedding Service
=================
Text embedding generation and management.
Uses AWS Bedrock Titan v2 for embeddings (1024 dimensions).
"""

from typing import List, Optional
import structlog

from app.services.bedrock_client import bedrock_client


logger = structlog.get_logger()


class EmbeddingService:
    """
    Service for generating text embeddings.
    Uses Bedrock Titan v2 (amazon.titan-embed-text-v2:0) — 1024 dimensions.
    """
    
    def __init__(self):
        self.dimension = 1024  # Titan v2 output dimension
    
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            1024-dimensional embedding vector
        """
        # Truncate very long texts (embedding model limit)
        max_chars = 25000
        if len(text) > max_chars:
            text = text[:max_chars]
            logger.warning(f"Text truncated to {max_chars} chars for embedding")
        
        return await bedrock_client.generate_embedding(text)
    
    async def embed_texts(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for API calls
            
        Returns:
            List of embedding vectors
        """
        return await bedrock_client.generate_embeddings_batch(texts, batch_size)
    
    def combine_texts_for_embedding(
        self,
        title: str,
        description: str,
        technologies: Optional[List[str]] = None,
        highlights: Optional[List[str]] = None,
    ) -> str:
        """
        Combine project fields into a single text for embedding.
        
        Args:
            title: Project title
            description: Project description
            technologies: List of technologies used
            highlights: List of highlight bullet points
            
        Returns:
            Combined text optimized for embedding
        """
        parts = [f"Title: {title}", f"Description: {description}"]
        
        if technologies:
            parts.append(f"Technologies: {', '.join(technologies)}")
        
        if highlights:
            parts.append("Key Achievements:")
            for h in highlights:
                parts.append(f"- {h}")
        
        return "\n".join(parts)


# Global instance
embedding_service = EmbeddingService()
