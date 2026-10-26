"""
Auth routes: cognito
====================
Google sign-in through the AWS Cognito hosted UI.
"""

from datetime import timedelta

import httpx
import structlog
from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.core.security import (
    create_access_token,
)
from app.schemas.auth import (
    CognitoCallbackRequest,
    TokenResponse,
)

logger = structlog.get_logger()

router = APIRouter()


@router.get("/cognito/authorize")
async def cognito_authorize():
    """Get Cognito hosted-UI authorization URL (Google sign-in)."""
    if not settings.COGNITO_APP_CLIENT_ID or not settings.COGNITO_DOMAIN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cognito not configured",
        )
    params = {
        "client_id": settings.COGNITO_APP_CLIENT_ID,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": settings.COGNITO_CALLBACK_URL,
        "identity_provider": "Google",
    }
    url = f"https://{settings.COGNITO_DOMAIN}/oauth2/authorize?" + "&".join(
        f"{k}={v}" for k, v in params.items()
    )
    return {"authorization_url": url}


@router.post("/cognito/callback", response_model=TokenResponse)
async def cognito_callback(callback_data: CognitoCallbackRequest):
    """
    Exchange Cognito authorization code for tokens, then find-or-create
    the user in DynamoDB and return our app JWT.
    """
    import base64 as _b64

    if (
        not settings.COGNITO_APP_CLIENT_ID
        or not settings.COGNITO_APP_CLIENT_SECRET
        or not settings.COGNITO_DOMAIN
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cognito not configured",
        )

    # Build Basic auth header for the token endpoint
    basic = _b64.b64encode(
        f"{settings.COGNITO_APP_CLIENT_ID}:{settings.COGNITO_APP_CLIENT_SECRET}".encode()
    ).decode()

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            f"https://{settings.COGNITO_DOMAIN}/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "code": callback_data.code,
                "redirect_uri": settings.COGNITO_CALLBACK_URL,
                "client_id": settings.COGNITO_APP_CLIENT_ID,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {basic}",
            },
        )
        token_data = token_resp.json()

    if "error" in token_data:
        logger.error("Cognito token exchange failed", detail=token_data)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cognito error: {token_data.get('error_description', token_data['error'])}",
        )

    id_token = token_data.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="No id_token in Cognito response")

    # Decode the id_token (signature is already validated by Cognito)
    # We only need the claims — email, name, sub
    import json as _json

    parts = id_token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="Malformed id_token")

    # id_token payload is Base64url-encoded JSON
    payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)  # pad
    claims = _json.loads(_b64.urlsafe_b64decode(payload_b64))

    cognito_sub = claims.get("sub")
    email = claims.get("email")
    name = claims.get("name", "")

    if not email:
        raise HTTPException(status_code=400, detail="No email in Cognito token")
    # Accounts are matched by email, so only an address the provider verified may join one.
    # Cognito sends this claim as a boolean or as the string "true" or "false".
    if str(claims.get("email_verified", "true")).lower() != "true":
        raise HTTPException(status_code=400, detail="Email not verified by the identity provider")

    # ── Find or create user in DynamoDB ──
    from boto3.dynamodb.conditions import Attr

    from app.services.dynamo_service import dynamo_service

    # First check by cognitoSub
    existing = await dynamo_service.scan(
        "Users", filter_expression=Attr("cognitoSub").eq(cognito_sub)
    )
    if existing:
        user_id = existing[0]["userId"]
        await dynamo_service.update_item(
            "Users",
            {"userId": user_id},
            {"updatedAt": dynamo_service.now_iso()},
        )
    else:
        # Check by email
        email_match = await dynamo_service.scan("Users", filter_expression=Attr("email").eq(email))
        if email_match:
            user_id = email_match[0]["userId"]
            await dynamo_service.update_item(
                "Users",
                {"userId": user_id},
                {
                    "cognitoSub": cognito_sub,
                    "name": name or email_match[0].get("name", ""),
                    "updatedAt": dynamo_service.now_iso(),
                },
            )
        else:
            # New user
            user_id = dynamo_service.generate_id()
            now = dynamo_service.now_iso()
            await dynamo_service.put_item(
                "Users",
                {
                    "userId": user_id,
                    "email": email,
                    "name": name or email.split("@")[0],
                    "cognitoSub": cognito_sub,
                    "isActive": True,
                    "isVerified": True,
                    "ingestionStatus": "none",
                    "createdAt": now,
                    "updatedAt": now,
                },
            )

    access_token = create_access_token(
        data={"sub": user_id},
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(access_token=access_token)


# Next-auth compatibility endpoints
