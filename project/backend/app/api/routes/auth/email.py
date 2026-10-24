"""
Auth routes: email
==================
Email and password sign-up, login, the current user and session stubs.
"""

from datetime import timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)

logger = structlog.get_logger()

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user with email and password."""
    if settings.USE_DYNAMO:
        from boto3.dynamodb.conditions import Attr

        from app.services.dynamo_service import dynamo_service

        existing = await dynamo_service.scan(
            "Users", filter_expression=Attr("email").eq(user_data.email)
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        user_id = dynamo_service.generate_id()
        now = dynamo_service.now_iso()
        await dynamo_service.put_item(
            "Users",
            {
                "userId": user_id,
                "email": user_data.email,
                "name": user_data.get_name(),
                "hashedPassword": get_password_hash(user_data.password),
                "isActive": True,
                "isVerified": False,
                "createdAt": now,
                "updatedAt": now,
            },
        )
        access_token = create_access_token(
            data={"sub": user_id},
            expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return TokenResponse(access_token=access_token)

    # SQLite path
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        email=user_data.email,
        name=user_data.get_name(),
        hashed_password=get_password_hash(user_data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Login with email and password."""
    if settings.USE_DYNAMO:
        from boto3.dynamodb.conditions import Attr

        from app.services.dynamo_service import dynamo_service

        results = await dynamo_service.scan(
            "Users", filter_expression=Attr("email").eq(credentials.email)
        )
        if not results:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        user_data = results[0]
        if not user_data.get("hashedPassword"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        if not verify_password(credentials.password, user_data["hashedPassword"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        access_token = create_access_token(
            data={"sub": user_data["userId"]},
            expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return TokenResponse(access_token=access_token)

    # SQLite path
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        avatar_url=current_user.avatar_url,
        is_verified=current_user.is_verified,
    )


@router.get("/session")
async def get_session():
    """Next-auth session endpoint - returns null for our JWT-based auth."""
    return None


@router.post("/_log")
async def auth_log():
    """Next-auth logging endpoint - no-op for our implementation."""
    return {"ok": True}
