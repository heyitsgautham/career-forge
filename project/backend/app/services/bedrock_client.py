"""
Bedrock Client
==============
AWS Bedrock API client using the model-agnostic Converse API.
Replaces gemini_client.py for AWS migration.
Works with any Bedrock model (Anthropic, Amazon Nova, etc.)
"""

import asyncio
import json
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
import structlog
import boto3
from botocore.exceptions import ClientError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.core.config import settings


logger = structlog.get_logger()


# Only retry on transient errors, not auth/config problems
_RETRYABLE_ERRORS = (
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceUnavailableException",
    "InternalServerException",
)


def _is_retryable(exc: BaseException) -> bool:
    """Return True only for transient Bedrock errors."""
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        return code in _RETRYABLE_ERRORS
    return False


class BedrockClient:
    """
    AWS Bedrock API client using the Converse API.

    Features:
    - Uses the model-agnostic Converse API (works with any model)
    - Retries with exponential backoff (3 attempts) for transient errors
    - Handles throttling gracefully
    - Supports text and JSON generation
    - Supports Titan embeddings via invoke_model
    """

    def __init__(self):
        self._client = None
        self._initialized = False

    def _get_client(self):
        """Get or create Bedrock runtime client."""
        if self._client is None:
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=settings.AWS_REGION,
            )
            self._initialized = True
            logger.info("Initialized Bedrock client", region=settings.AWS_REGION)
        return self._client

    # ------------------------------------------------------------------
    # Text generation via Converse API
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ClientError),
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate text content using the Bedrock Converse API.

        Args:
            prompt: The user prompt
            system_prompt: Optional system instruction
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Returns:
            Generated text content
        """
        client = self._get_client()

        kwargs: Dict[str, Any] = {
            "modelId": settings.BEDROCK_MODEL_ID,
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            "inferenceConfig": {
                "maxTokens": max_tokens or settings.BEDROCK_MAX_TOKENS,
                "temperature": temperature if temperature is not None else settings.BEDROCK_TEMPERATURE,
            },
        }

        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]

        try:
            response = await asyncio.to_thread(client.converse, **kwargs)

            content = (
                response.get("output", {})
                .get("message", {})
                .get("content", [])
            )
            if content:
                return content[0].get("text", "")
            return ""

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in _RETRYABLE_ERRORS:
                logger.warning("Bedrock throttled, will retry", error=str(e))
            else:
                logger.error("Bedrock API error", error=str(e), code=error_code)
            raise
        except Exception as e:
            logger.error("Bedrock generation failed", error=str(e))
            raise

    async def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_mime_type: str = "text/plain",
    ) -> str:
        """
        Generate content - compatible interface with GeminiClient.generate_content().

        Args:
            prompt: The user prompt
            system_instruction: System prompt for context
            temperature: Override default temperature
            max_tokens: Override default max tokens
            response_mime_type: Response format hint

        Returns:
            Generated text content
        """
        full_prompt = prompt
        if response_mime_type == "application/json":
            full_prompt += (
                "\n\nIMPORTANT: Return ONLY valid JSON, no markdown, "
                "no code blocks, no extra text."
            )

        return await self.generate(
            prompt=full_prompt,
            system_prompt=system_instruction,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generate JSON content using Bedrock.

        Args:
            prompt: The user prompt
            system_instruction: System prompt for context
            temperature: Override default temperature

        Returns:
            Parsed JSON response
        """
        response = await self.generate_content(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=temperature or 0.1,
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

    # ------------------------------------------------------------------
    # Embeddings (Titan uses invoke_model, not Converse)
    # ------------------------------------------------------------------

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using Bedrock Titan v2.

        Args:
            text: Text to embed

        Returns:
            Embedding vector (1024 dimensions)
        """
        client = self._get_client()

        max_chars = 25000
        if len(text) > max_chars:
            text = text[:max_chars]
            logger.warning(f"Text truncated to {max_chars} chars for embedding")

        body = {"inputText": text}

        try:
            response = await asyncio.to_thread(
                client.invoke_model,
                modelId=settings.BEDROCK_EMBED_MODEL_ID,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            return response_body["embedding"]

        except ClientError as e:
            logger.error("Bedrock embedding error", error=str(e))
            raise
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            raise

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 10,
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
            batch = texts[i : i + batch_size]
            batch_embeddings = await asyncio.gather(
                *[self.generate_embedding(text) for text in batch]
            )
            embeddings.extend(batch_embeddings)

            if i + batch_size < len(texts):
                await asyncio.sleep(0.5)

        return embeddings


# Global instance
bedrock_client = BedrockClient()
