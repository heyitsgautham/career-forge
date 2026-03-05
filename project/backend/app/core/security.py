"""
Security Utilities
==================
JWT handling, password hashing, encryption.
"""

from datetime import datetime, timedelta
from typing import Optional
import secrets

from jose import JWTError, jwt
import bcrypt
from cryptography.fernet import Fernet
import base64
import hashlib

from app.core.config import settings


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
    Encrypt/decrypt sensitive tokens (like GitHub tokens) at rest.
    Uses Fernet symmetric encryption.
    """
    
    def __init__(self, secret_key: str = None):
        """Initialize encryptor with secret key."""
        key = secret_key or settings.SECRET_KEY
        # Derive a valid Fernet key from the secret
        derived_key = hashlib.sha256(key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(derived_key)
        self.fernet = Fernet(fernet_key)
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string and return base64-encoded ciphertext."""
        encrypted = self.fernet.encrypt(plaintext.encode())
        return encrypted.decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt base64-encoded ciphertext and return plaintext."""
        decrypted = self.fernet.decrypt(ciphertext.encode())
        return decrypted.decode()


# Global encryptor instance
token_encryptor = TokenEncryptor()


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)
