"""
API Dependencies
================
Shared dependencies for API routes.
Supports both SQLite (legacy) and DynamoDB (AWS) backends.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uuid

from app.core.config import settings
from app.core.security import decode_access_token


security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Get current authenticated user from JWT token.
    Supports both DynamoDB and SQLite backends.
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service
        
        user = await dynamo_service.get_item("Users", {"userId": user_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        
        if not user.get("isActive", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled",
            )
        
        # Return a dict-like object that mimics the SQLAlchemy User fields
        return DynamoUser(user)
    else:
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy import select
        from app.core.database import get_db, AsyncSessionLocal
        from app.models.user import User

        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user ID in token",
            )

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User).where(User.id == user_uuid)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                )
            
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is disabled",
                )
            
            return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> Optional[object]:
    """Get current user if authenticated, None otherwise."""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


class DynamoUser:
    """
    Wrapper around DynamoDB user dict to provide attribute-style access.
    Mimics SQLAlchemy User model interface for compatibility.
    """
    
    def __init__(self, data: dict):
        self._data = data
    
    @property
    def id(self):
        return self._data.get("userId")
    
    @property
    def email(self):
        return self._data.get("email", "")
    
    @property
    def name(self):
        return self._data.get("name", "")
    
    @property
    def avatar_url(self):
        return self._data.get("avatarUrl")
    
    @property
    def hashed_password(self):
        return self._data.get("hashedPassword")
    
    @property
    def headline(self):
        return self._data.get("headline")
    
    @property
    def summary(self):
        return self._data.get("summary")
    
    @property
    def location(self):
        return self._data.get("location")
    
    @property
    def phone(self):
        return self._data.get("phone")
    
    @property
    def website(self):
        return self._data.get("website")
    
    @property
    def linkedin_url(self):
        return self._data.get("linkedinUrl")
    
    @property
    def address_line1(self):
        return self._data.get("addressLine1")
    
    @property
    def address_line2(self):
        return self._data.get("addressLine2")
    
    @property
    def city(self):
        return self._data.get("city")
    
    @property
    def state(self):
        return self._data.get("state")
    
    @property
    def zip_code(self):
        return self._data.get("zipCode")
    
    @property
    def country(self):
        return self._data.get("country")
    
    @property
    def institution(self):
        return self._data.get("institution")
    
    @property
    def degree(self):
        return self._data.get("degree")
    
    @property
    def field_of_study(self):
        return self._data.get("fieldOfStudy")
    
    @property
    def graduation_year(self):
        return self._data.get("graduationYear")
    
    @property
    def experience(self):
        return self._data.get("experience")
    
    @property
    def education(self):
        return self._data.get("education")
    
    @property
    def skills(self):
        return self._data.get("skills")
    
    @property
    def certifications(self):
        return self._data.get("certifications")
    
    @property
    def is_active(self):
        return self._data.get("isActive", True)
    
    @property
    def is_verified(self):
        return self._data.get("isVerified", False)
    
    @property
    def created_at(self):
        return self._data.get("createdAt")
    
    @property
    def updated_at(self):
        return self._data.get("updatedAt")
    
    def get(self, key, default=None):
        return self._data.get(key, default)
    
    def __getitem__(self, key):
        return self._data[key]
    
    def to_dict(self):
        return self._data
