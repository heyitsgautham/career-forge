"""
Vector Store Service
====================
ChromaDB integration for semantic search.
"""

from typing import List, Optional, Dict, Any
import uuid
import structlog
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings


logger = structlog.get_logger()


class VectorStoreService:
    """
    Vector store service using ChromaDB.
    Manages collections for projects, documents, and job descriptions.
    """
    
    COLLECTION_PROJECTS = "projects"
    COLLECTION_DOCUMENTS = "documents"
    COLLECTION_JOB_DESCRIPTIONS = "job_descriptions"
    
    def __init__(self):
        self._client: Optional[chromadb.Client] = None
        self._collections: Dict[str, chromadb.Collection] = {}
    
    def _get_client(self) -> chromadb.Client:
        """Get or create ChromaDB client."""
        if self._client is None:
            try:
                # Try to connect to remote ChromaDB
                self._client = chromadb.HttpClient(
                    host=settings.CHROMA_HOST,
                    port=settings.CHROMA_PORT,
                    settings=ChromaSettings(
                        anonymized_telemetry=False
                    )
                )
                logger.info(f"Connected to ChromaDB at {settings.CHROMA_HOST}:{settings.CHROMA_PORT}")
            except Exception as e:
                logger.warning(f"Could not connect to remote ChromaDB: {e}. Using persistent local client.")
                self._client = chromadb.PersistentClient(
                    path=settings.CHROMA_PERSIST_DIRECTORY,
                    settings=ChromaSettings(
                        anonymized_telemetry=False
                    )
                )
        return self._client
    
    def _get_collection(self, name: str) -> chromadb.Collection:
        """Get or create a collection."""
        if name not in self._collections:
            client = self._get_client()
            self._collections[name] = client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )
        return self._collections[name]
    
    async def add_embedding(
        self,
        collection_name: str,
        embedding_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        document: str,
    ) -> str:
        """
        Add an embedding to a collection.
        
        Args:
            collection_name: Name of the collection
            embedding_id: Unique ID for the embedding
            embedding: The embedding vector
            metadata: Additional metadata (must be flat dict with str/int/float/bool values)
            document: The original text document
            
        Returns:
            The embedding ID
        """
        collection = self._get_collection(collection_name)
        
        # ChromaDB metadata must be flat
        flat_metadata = self._flatten_metadata(metadata)
        
        collection.add(
            ids=[embedding_id],
            embeddings=[embedding],
            metadatas=[flat_metadata],
            documents=[document]
        )
        
        logger.debug(f"Added embedding {embedding_id} to {collection_name}")
        return embedding_id
    
    async def update_embedding(
        self,
        collection_name: str,
        embedding_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        document: str,
    ):
        """Update an existing embedding."""
        collection = self._get_collection(collection_name)
        flat_metadata = self._flatten_metadata(metadata)
        
        collection.update(
            ids=[embedding_id],
            embeddings=[embedding],
            metadatas=[flat_metadata],
            documents=[document]
        )
    
    async def delete_embedding(self, collection_name: str, embedding_id: str):
        """Delete an embedding from a collection."""
        collection = self._get_collection(collection_name)
        collection.delete(ids=[embedding_id])
        logger.debug(f"Deleted embedding {embedding_id} from {collection_name}")
    
    async def search_similar(
        self,
        collection_name: str,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar embeddings.
        
        Args:
            collection_name: Name of the collection
            query_embedding: Query embedding vector
            n_results: Number of results to return
            where: Optional filter conditions
            
        Returns:
            List of results with id, distance, metadata, and document
        """
        collection = self._get_collection(collection_name)
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["distances", "metadatas", "documents"]
        )
        
        # Format results
        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, id_ in enumerate(results["ids"][0]):
                formatted.append({
                    "id": id_,
                    "distance": results["distances"][0][i] if results["distances"] else None,
                    "similarity": 1 - results["distances"][0][i] if results["distances"] else None,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "document": results["documents"][0][i] if results["documents"] else None,
                })
        
        return formatted
    
    async def get_by_id(
        self, 
        collection_name: str, 
        embedding_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a single embedding by ID."""
        collection = self._get_collection(collection_name)
        
        results = collection.get(
            ids=[embedding_id],
            include=["embeddings", "metadatas", "documents"]
        )
        
        if not results["ids"]:
            return None
        
        return {
            "id": results["ids"][0],
            "embedding": results["embeddings"][0] if results["embeddings"] else None,
            "metadata": results["metadatas"][0] if results["metadatas"] else {},
            "document": results["documents"][0] if results["documents"] else None,
        }
    
    def _flatten_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten metadata dict for ChromaDB (only supports str/int/float/bool)."""
        flat = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                flat[key] = value
            elif isinstance(value, list):
                # Convert list to comma-separated string
                flat[key] = ",".join(str(v) for v in value)
            elif value is None:
                continue
            else:
                flat[key] = str(value)
        return flat
    
    def generate_embedding_id(self) -> str:
        """Generate a unique embedding ID."""
        return str(uuid.uuid4())


# Global instance
vector_store = VectorStoreService()
