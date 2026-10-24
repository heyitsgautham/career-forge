"""
Application Configuration
=========================
Centralized settings management using Pydantic Settings.

Secret loading order (highest priority wins):
1. AWS Secrets Manager  — fetched at startup for JWT_SECRET_KEY, SECRET_KEY,
                          GITHUB_APP_CLIENT_SECRET, COGNITO_APP_CLIENT_SECRET
2. Environment variables / .env file
3. Hard-coded defaults   — only safe for non-secret config; never for prod secrets
"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import model_validator
from functools import lru_cache
import logging
import os

logger = logging.getLogger(__name__)


def _fetch_secret(sm_client, secret_name: str) -> Optional[str]:
    """Fetch a single secret string from AWS Secrets Manager. Returns None on failure."""
    try:
        return sm_client.get_secret_value(SecretId=secret_name)["SecretString"]
    except Exception as exc:
        logger.warning("Secrets Manager: could not load '%s': %s", secret_name, exc)
        return None


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

    # AWS KMS — token encryption at rest
    KMS_KEY_ID: str = "alias/careerforge-tokens"

    # AWS Secrets Manager — secret names (not the secret values themselves)
    SM_JWT_SECRET_NAME: str = "careerforge/jwt-secret-key"
    SM_APP_SECRET_NAME: str = "careerforge/app-secret-key"
    SM_GITHUB_CLIENT_SECRET_NAME: str = "careerforge/github-app-client-secret"
    SM_COGNITO_CLIENT_SECRET_NAME: str = "careerforge/cognito-app-client-secret"
    # Set to false for local dev and tests so startup never calls AWS
    USE_SECRETS_MANAGER: bool = True

    # AWS Bedrock
    BEDROCK_MODEL_ID: str = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
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
    GITHUB_CALLBACK_URL: str = "http://localhost:3000/api/auth/callback/github"

    # AWS Cognito
    COGNITO_USER_POOL_ID: str = "us-east-1_Mtxh0HEPD"
    COGNITO_APP_CLIENT_ID: str = "2lac8ac29r2rnjbkk7q43p1hr2"
    # Never hardcode this. Set it in .env or store it in Secrets Manager.
    COGNITO_APP_CLIENT_SECRET: Optional[str] = None
    COGNITO_DOMAIN: str = "careerforge.auth.us-east-1.amazoncognito.com"
    COGNITO_CALLBACK_URL: str = "http://localhost:3000/api/auth/callback/cognito"

    # LinkedIn OAuth
    LINKEDIN_CLIENT_ID: Optional[str] = None
    LINKEDIN_CLIENT_SECRET: Optional[str] = None
    LINKEDIN_CALLBACK_URL: str = "http://localhost:3000/api/auth/callback/linkedin"

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

    @model_validator(mode="after")
    def _load_secrets_manager(self) -> "Settings":
        """
        Override secret fields with values from AWS Secrets Manager.
        Runs after env/default values are set, so SM always wins over .env defaults
        but env vars still serve as fallback when SM is unavailable (e.g. local dev
        without AWS credentials).
        """
        _SENTINEL = "change-me-in-production"

        if not self.USE_SECRETS_MANAGER:
            return self

        try:
            import boto3

            sm = boto3.client("secretsmanager", region_name=self.AWS_REGION)

            # JWT signing key
            if self.JWT_SECRET_KEY == _SENTINEL:
                val = _fetch_secret(sm, self.SM_JWT_SECRET_NAME)
                if val:
                    object.__setattr__(self, "JWT_SECRET_KEY", val)

            # App / Fernet fallback key
            if self.SECRET_KEY == _SENTINEL:
                val = _fetch_secret(sm, self.SM_APP_SECRET_NAME)
                if val:
                    object.__setattr__(self, "SECRET_KEY", val)

            # GitHub App client secret
            if not self.GITHUB_APP_CLIENT_SECRET:
                val = _fetch_secret(sm, self.SM_GITHUB_CLIENT_SECRET_NAME)
                if val:
                    object.__setattr__(self, "GITHUB_APP_CLIENT_SECRET", val)

            # Cognito App client secret
            if not self.COGNITO_APP_CLIENT_SECRET:
                val = _fetch_secret(sm, self.SM_COGNITO_CLIENT_SECRET_NAME)
                if val:
                    object.__setattr__(self, "COGNITO_APP_CLIENT_SECRET", val)

            logger.debug("Secrets Manager: secret overrides applied")

        except Exception as exc:
            logger.warning("Secrets Manager unavailable, using env/defaults: %s", exc)

        return self

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
