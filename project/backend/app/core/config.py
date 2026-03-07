"""
Application Configuration
=========================
Centralized settings management using Pydantic Settings.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "careerforge"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-production"
    
    # API Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # AWS Configuration
    AWS_REGION: str = "us-east-1"
    
    # AWS Bedrock
    BEDROCK_MODEL_ID: str = "amazon.nova-lite-v1:0"
    BEDROCK_EMBED_MODEL_ID: str = "amazon.titan-embed-text-v2:0"
    BEDROCK_TEMPERATURE: float = 0.2
    BEDROCK_MAX_TOKENS: int = 8192
    
    # AWS DynamoDB
    USE_DYNAMO: bool = True
    DYNAMO_TABLE_PREFIX: str = ""
    
    # AWS S3
    S3_BUCKET: str = "careerforge-pdfs-602664593597"
    
    # Database (SQLite for local dev fallback)
    DATABASE_URL: str = "sqlite+aiosqlite:///./latex_agent.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # ChromaDB
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_data"
    
    # Gemini API Keys (legacy — kept for fallback)
    GEMINI_API_KEY_1: Optional[str] = None
    GEMINI_API_KEY_2: Optional[str] = None
    GEMINI_API_KEY_3: Optional[str] = None
    GEMINI_API_KEY_4: Optional[str] = None
    GEMINI_API_KEY_5: Optional[str] = None
    GEMINI_API_KEY_6: Optional[str] = None
    
    # Gemini Model Configuration (legacy)
    GEMINI_MODEL: str = "gemini-2.0-flash-lite"
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"
    GEMINI_TEMPERATURE: float = 0.2
    GEMINI_MAX_TOKENS: int = 8192
    
    # GitHub App (replaces OAuth App — see M1.6)
    GITHUB_APP_ID: Optional[str] = None
    GITHUB_APP_SLUG: str = "careerforge"
    GITHUB_APP_CLIENT_ID: Optional[str] = None
    GITHUB_APP_CLIENT_SECRET: Optional[str] = None
    GITHUB_APP_PRIVATE_KEY_SECRET: str = "careerforge/github-app-private-key"
    # Legacy OAuth (kept for backward-compat during migration)
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    GITHUB_CALLBACK_URL: str = "http://localhost:3001/api/auth/callback/github"
    
    # LinkedIn OAuth
    LINKEDIN_CLIENT_ID: Optional[str] = None
    LINKEDIN_CLIENT_SECRET: Optional[str] = None
    LINKEDIN_CALLBACK_URL: str = "http://localhost:3001/api/auth/callback/linkedin"
    
    # JWT Configuration
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    
    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    
    # LaTeX Compilation
    LATEX_COMPILER_TIMEOUT: int = 30
    LATEX_COMPILER_MEMORY_LIMIT: str = "256m"
    
    @property
    def gemini_api_keys(self) -> List[str]:
        """Get all configured Gemini API keys."""
        keys = [
            self.GEMINI_API_KEY_1,
            self.GEMINI_API_KEY_2,
            self.GEMINI_API_KEY_3,
            self.GEMINI_API_KEY_4,
            self.GEMINI_API_KEY_5,
            self.GEMINI_API_KEY_6,
        ]
        return [k for k in keys if k]
    
    @property
    def max_upload_size_bytes(self) -> int:
        """Get max upload size in bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
