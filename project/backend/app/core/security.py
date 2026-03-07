"""
Security Utilities
==================
JWT handling, password hashing, encryption.

Encryption strategy:
- KmsTokenEncryptor  : preferred path — uses AWS KMS (CloudTrail audit, no key material in app)
- TokenEncryptor     : legacy Fernet encryptor, kept only for decrypting pre-KMS tokens
- token_encryptor    : global instance is KmsTokenEncryptor; transparently falls back to
                       Fernet on decrypt so existing DynamoDB ciphertext keeps working.
"""

from datetime import datetime, timedelta
from typing import Optional
import secrets
import logging

from jose import JWTError, jwt
import bcrypt
from cryptography.fernet import Fernet, InvalidToken
import base64
import hashlib
import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return bcrypt.hashpw(
        password.encode('utf-8'), 
        bcrypt.gensalt()
    ).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.JWT_SECRET_KEY, 
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT access token."""
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


class TokenEncryptor:
    """
    Legacy Fernet encryptor — kept only for decrypting tokens encrypted before KMS migration.
    Do NOT use for new encryptions; use KmsTokenEncryptor instead.
    """

    def __init__(self, secret_key: str = None):
        key = secret_key or settings.SECRET_KEY
        derived_key = hashlib.sha256(key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(derived_key)
        self.fernet = Fernet(fernet_key)

    def encrypt(self, plaintext: str) -> str:
        encrypted = self.fernet.encrypt(plaintext.encode())
        return encrypted.decode()

    def decrypt(self, ciphertext: str) -> str:
        decrypted = self.fernet.decrypt(ciphertext.encode())
        return decrypted.decode()


class KmsTokenEncryptor:
    """
    AWS KMS-backed encryptor for sensitive tokens (GitHub, LinkedIn) stored in DynamoDB.

    - encrypt()  : calls KMS GenerateDataKey-less Encrypt API; ciphertext blob is stored.
    - decrypt()  : calls KMS Decrypt API; if the ciphertext was produced by the legacy Fernet
                   encryptor, falls back to TokenEncryptor so existing rows keep working
                   without a forced migration.

    The KMS key ID is read from settings.KMS_KEY_ID (alias/careerforge-tokens by default).
    Every encrypt/decrypt is recorded in CloudTrail automatically.
    """

    # Prefix that marks a KMS-encrypted blob so we can distinguish from Fernet ciphertext
    _KMS_PREFIX = "KMS:"

    def __init__(self):
        self._kms = boto3.client("kms", region_name=settings.AWS_REGION)
        self._key_id = settings.KMS_KEY_ID
        # Lazy-loaded legacy fallback
        self._fernet_fallback: Optional[TokenEncryptor] = None

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string using KMS and return a prefixed base64 string.
        Format: "KMS:<base64(CiphertextBlob)>"
        """
        response = self._kms.encrypt(
            KeyId=self._key_id,
            Plaintext=plaintext.encode(),
        )
        blob = base64.b64encode(response["CiphertextBlob"]).decode()
        return f"{self._KMS_PREFIX}{blob}"

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt a ciphertext string.

        - If prefixed with "KMS:" → use KMS Decrypt.
        - Otherwise → legacy Fernet path (transparent backward compatibility).
        """
        if ciphertext.startswith(self._KMS_PREFIX):
            blob = base64.b64decode(ciphertext[len(self._KMS_PREFIX):])
            response = self._kms.decrypt(CiphertextBlob=blob)
            return response["Plaintext"].decode()

        # Legacy Fernet ciphertext — decrypt with old key
        if self._fernet_fallback is None:
            self._fernet_fallback = TokenEncryptor()
        try:
            return self._fernet_fallback.decrypt(ciphertext)
        except (InvalidToken, Exception) as exc:
            logger.error("KmsTokenEncryptor: failed to decrypt legacy Fernet ciphertext", exc_info=exc)
            raise ValueError("Unable to decrypt token: not a valid KMS or Fernet ciphertext") from exc


# Global encryptor instance — KMS-backed, Fernet fallback for legacy rows
token_encryptor = KmsTokenEncryptor()


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)
