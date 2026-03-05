"""Services module initialization."""

from app.services.bedrock_client import BedrockClient, bedrock_client
from app.services.embedding_service import EmbeddingService, embedding_service
from app.services.vector_store import VectorStoreService, vector_store
from app.services.dynamo_service import DynamoService, dynamo_service
from app.services.s3_service import S3Service, s3_service

__all__ = [
    "BedrockClient",
    "bedrock_client",
    "EmbeddingService",
    "embedding_service",
    "VectorStoreService",
    "vector_store",
    "DynamoService",
    "dynamo_service",
    "S3Service",
    "s3_service",
]
