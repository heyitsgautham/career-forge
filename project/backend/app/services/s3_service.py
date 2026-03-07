"""
S3 Service
==========
AWS S3 file storage service.
Replaces local filesystem storage for PDFs and LaTeX files.
"""

from typing import Optional
import structlog
import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


logger = structlog.get_logger()


class S3Service:
    """
    S3 file storage service for CareerForge.

    Handles PDF and LaTeX file uploads with presigned URL generation.
    Key pattern: {userId}/{resumeId}.pdf and {userId}/{resumeId}.tex
    """

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Get or create S3 client."""
        if self._client is None:
            self._client = boto3.client(
                "s3",
                region_name=settings.AWS_REGION,
            )
            logger.info("Initialized S3 client", bucket=settings.S3_BUCKET)
        return self._client

    async def upload_file(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        """
        Upload a file to S3.

        Args:
            key: S3 object key (e.g., "{userId}/{resumeId}.pdf")
            data: File content as bytes
            content_type: MIME type

        Returns:
            S3 URI (s3://bucket/key)
        """
        client = self._get_client()

        try:
            client.put_object(
                Bucket=settings.S3_BUCKET,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
            s3_uri = f"s3://{settings.S3_BUCKET}/{key}"
            logger.info("S3 upload success", key=key, content_type=content_type)
            return s3_uri
        except ClientError as e:
            logger.error("S3 upload failed", key=key, error=str(e))
            raise

    async def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        filename: str | None = None,
        inline: bool = False,
    ) -> str:
        """
        Generate a presigned URL for a file.

        Args:
            key: S3 object key
            expires_in: URL expiry in seconds (default: 1 hour)
            filename: If provided, sets Content-Disposition filename.
            inline: If True, sets Content-Disposition: inline (browser renders).
                    If False with filename, sets Content-Disposition: attachment.

        Returns:
            Presigned URL string
        """
        client = self._get_client()

        params: dict = {"Bucket": settings.S3_BUCKET, "Key": key}
        if inline:
            disposition = f'inline; filename="{filename}"' if filename else "inline"
            params["ResponseContentDisposition"] = disposition
            params["ResponseContentType"] = "application/pdf"
        elif filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        try:
            url = client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expires_in,
            )
            logger.debug("Generated presigned URL", key=key, expires_in=expires_in)
            return url
        except ClientError as e:
            logger.error("S3 presigned URL failed", key=key, error=str(e))
            raise

    async def delete_file(self, key: str) -> None:
        """
        Delete a file from S3.

        Args:
            key: S3 object key
        """
        client = self._get_client()

        try:
            client.delete_object(
                Bucket=settings.S3_BUCKET,
                Key=key,
            )
            logger.info("S3 delete success", key=key)
        except ClientError as e:
            logger.error("S3 delete failed", key=key, error=str(e))
            raise

    async def file_exists(self, key: str) -> bool:
        """
        Check if a file exists in S3.

        Args:
            key: S3 object key

        Returns:
            True if file exists
        """
        client = self._get_client()

        try:
            client.head_object(Bucket=settings.S3_BUCKET, Key=key)
            return True
        except ClientError:
            return False

    async def list_objects(self, prefix: str) -> list:
        """
        List all objects under a prefix in S3.

        Args:
            prefix: S3 key prefix (e.g., "{userId}/")

        Returns:
            List of S3 object keys
        """
        client = self._get_client()
        keys = []

        try:
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=settings.S3_BUCKET, Prefix=prefix):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
            return keys
        except ClientError as e:
            logger.error("S3 list_objects failed", prefix=prefix, error=str(e))
            raise

    async def download_file(self, key: str) -> bytes:
        """
        Download a file from S3.

        Args:
            key: S3 object key

        Returns:
            File content as bytes
        """
        client = self._get_client()

        try:
            response = client.get_object(Bucket=settings.S3_BUCKET, Key=key)
            return response["Body"].read()
        except ClientError as e:
            logger.error("S3 download failed", key=key, error=str(e))
            raise

    def get_key_for_resume(
        self,
        user_id: str,
        resume_id: str,
        extension: str = "pdf",
    ) -> str:
        """
        Generate S3 key for a resume file.

        Args:
            user_id: User ID
            resume_id: Resume ID
            extension: File extension (pdf or tex)

        Returns:
            S3 key string
        """
        return f"{user_id}/{resume_id}.{extension}"


# Global instance
s3_service = S3Service()
