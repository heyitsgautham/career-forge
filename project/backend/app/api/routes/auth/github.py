"""
Auth routes: github
===================
GitHub OAuth and GitHub App sign-in, plus the connection status.
"""

from datetime import timedelta

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    token_encryptor,
)
from app.models.user import GithubConnection, User
from app.schemas.auth import (
    GitHubCallbackRequest,
    TokenResponse,
)

logger = structlog.get_logger()

router = APIRouter()


@router.get("/github/authorize")
async def github_authorize():
    """Get GitHub OAuth authorization URL for login."""
    # Always use standard OAuth flow for login.
    # GitHub App installation (repo selection) happens post-login via a separate endpoint.
    client_id = settings.GITHUB_APP_CLIENT_ID or settings.GITHUB_CLIENT_ID
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth not configured",
        )

    params = {
        "client_id": client_id,
        "redirect_uri": settings.GITHUB_CALLBACK_URL,
        "scope": "read:user user:email repo",
        "state": "random_state_string",
    }

    url = "https://github.com/login/oauth/authorize?" + "&".join(
        f"{k}={v}" for k, v in params.items()
    )

    return {"authorization_url": url}


@router.post("/github/callback", response_model=TokenResponse)
async def github_callback(
    callback_data: GitHubCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Handle GitHub OAuth callback (supports both GitHub App and legacy OAuth App)."""
    # Use GitHub App credentials if available, else legacy OAuth
    client_id = settings.GITHUB_APP_CLIENT_ID or settings.GITHUB_CLIENT_ID
    client_secret = settings.GITHUB_APP_CLIENT_SECRET or settings.GITHUB_CLIENT_SECRET
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth not configured",
        )

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": callback_data.code,
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_response.json()

    if "error" in token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub OAuth error: {token_data.get('error_description', token_data['error'])}",
        )

    github_token = token_data["access_token"]

    # Get GitHub user info
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {github_token}"},
        )
        github_user = user_response.json()

        # Get primary email
        emails_response = await client.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"token {github_token}"},
        )
        emails = emails_response.json()
        primary_email = next((e["email"] for e in emails if e["primary"]), github_user.get("email"))

    if not primary_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not get email from GitHub",
        )

    if settings.USE_DYNAMO:
        from boto3.dynamodb.conditions import Attr

        from app.services.dynamo_service import dynamo_service

        encrypted_token = token_encryptor.encrypt(github_token)
        installation_id = callback_data.installation_id

        # If link_token is set, the user is already logged in (e.g. via Google)
        # and is connecting GitHub from the dashboard. Link to that user directly.
        link_user_id = None
        if callback_data.link_token:
            from app.core.security import decode_access_token as _decode

            payload = _decode(callback_data.link_token)
            if payload and payload.get("sub"):
                link_user_id = payload["sub"]

        if link_user_id:
            # Link GitHub to the existing logged-in user
            user_id = link_user_id
            update_fields = {
                "githubUserId": str(github_user["id"]),
                "githubUsername": github_user["login"],
                "githubAvatarUrl": github_user.get("avatar_url"),
                "githubToken": encrypted_token,
                "updatedAt": dynamo_service.now_iso(),
            }
            if installation_id:
                update_fields["githubInstallationId"] = installation_id
            await dynamo_service.update_item("Users", {"userId": user_id}, update_fields)
        else:
            # Standard flow: find or create user by GitHub identity
            # Check if user already linked to this GitHub account
            existing = await dynamo_service.scan(
                "Users", filter_expression=Attr("githubUserId").eq(str(github_user["id"]))
            )
            if existing:
                user_id = existing[0]["userId"]
                update_fields = {
                    "githubToken": encrypted_token,
                    "githubUsername": github_user["login"],
                    "githubAvatarUrl": github_user.get("avatar_url"),
                    "updatedAt": dynamo_service.now_iso(),
                }
                if installation_id:
                    update_fields["githubInstallationId"] = installation_id
                await dynamo_service.update_item("Users", {"userId": user_id}, update_fields)
            else:
                # Look up by email
                email_users = await dynamo_service.scan(
                    "Users", filter_expression=Attr("email").eq(primary_email)
                )
                if email_users:
                    user_id = email_users[0]["userId"]
                else:
                    # Create new user
                    user_id = dynamo_service.generate_id()
                    now = dynamo_service.now_iso()
                    new_user_item = {
                        "userId": user_id,
                        "email": primary_email,
                        "name": github_user.get("name") or github_user["login"],
                        "avatarUrl": github_user.get("avatar_url"),
                        "isActive": True,
                        "isVerified": True,
                        "ingestionStatus": "none",
                        "createdAt": now,
                        "updatedAt": now,
                    }
                    await dynamo_service.put_item("Users", new_user_item)
                # Store GitHub connection info on user record
                update_fields = {
                    "githubUserId": str(github_user["id"]),
                    "githubUsername": github_user["login"],
                    "githubAvatarUrl": github_user.get("avatar_url"),
                    "githubToken": encrypted_token,
                    "updatedAt": dynamo_service.now_iso(),
                }
                if installation_id:
                    update_fields["githubInstallationId"] = installation_id
                await dynamo_service.update_item("Users", {"userId": user_id}, update_fields)

        access_token = create_access_token(
            data={"sub": user_id},
            expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return TokenResponse(access_token=access_token)

    # SQLite path
    # Check if GitHub connection exists
    result = await db.execute(
        select(GithubConnection).where(GithubConnection.github_user_id == github_user["id"])
    )
    github_conn = result.scalar_one_or_none()

    if github_conn:
        # Update token
        github_conn.encrypted_token = token_encryptor.encrypt(github_token)
        user = await db.get(User, github_conn.user_id)
    else:
        # Check if user exists with this email
        result = await db.execute(select(User).where(User.email == primary_email))
        user = result.scalar_one_or_none()

        if not user:
            # Create new user
            user = User(
                email=primary_email,
                name=github_user.get("name") or github_user["login"],
                avatar_url=github_user.get("avatar_url"),
                is_verified=True,
            )
            db.add(user)
            await db.flush()

        # Create GitHub connection
        github_conn = GithubConnection(
            user_id=user.id,
            github_user_id=github_user["id"],
            github_username=github_user["login"],
            github_avatar_url=github_user.get("avatar_url"),
            encrypted_token=token_encryptor.encrypt(github_token),
            is_primary=True,
            scopes=["read:user", "user:email", "repo"],
        )
        db.add(github_conn)

    await db.commit()

    # Generate JWT
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return TokenResponse(access_token=access_token)


@router.get("/github/status")
async def get_github_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get GitHub connection status for the current user."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service

        user_data = await dynamo_service.get_item("Users", {"userId": str(current_user.id)})
        if user_data and user_data.get("githubUserId"):
            return {
                "connected": True,
                "username": user_data.get("githubUsername"),
                "avatar_url": user_data.get("githubAvatarUrl"),
                "connected_at": user_data.get("updatedAt"),
            }
        return {"connected": False}

    # SQLite path
    result = await db.execute(
        select(GithubConnection).where(
            GithubConnection.user_id == current_user.id,
            GithubConnection.is_primary.is_(True),
        )
    )
    github_conn = result.scalar_one_or_none()

    if github_conn:
        return {
            "connected": True,
            "username": github_conn.github_username,
            "avatar_url": github_conn.github_avatar_url,
            "connected_at": github_conn.connected_at.isoformat(),
        }
    else:
        return {
            "connected": False,
        }
