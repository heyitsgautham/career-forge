"""
Auth routes: linkedin
=====================
LinkedIn OAuth, profile import and certification scraping.
"""

from datetime import datetime
from typing import Optional

import httpx
import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    token_encryptor,
)
from app.models.user import LinkedInConnection, User
from app.schemas.auth import (
    LinkedInImportRequest,
)

logger = structlog.get_logger()

router = APIRouter()


@router.get("/linkedin/status")
async def get_linkedin_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get LinkedIn connection status for the current user."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service

        user_data = await dynamo_service.get_item("Users", {"userId": str(current_user.id)})
        if user_data and user_data.get("linkedinUserId"):
            return {
                "connected": True,
                "email": user_data.get("linkedinEmail"),
                "connected_at": user_data.get("updatedAt"),
            }
        return {"connected": False}

    # SQLite path
    result = await db.execute(
        select(LinkedInConnection).where(
            LinkedInConnection.user_id == current_user.id,
        )
    )
    linkedin_conn = result.scalar_one_or_none()

    if linkedin_conn:
        return {
            "connected": True,
            "email": linkedin_conn.linkedin_email,
            "connected_at": linkedin_conn.connected_at.isoformat(),
        }
    else:
        return {
            "connected": False,
        }


@router.get("/linkedin/authorize")
async def linkedin_authorize():
    """Get LinkedIn OAuth authorization URL."""
    if not settings.LINKEDIN_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn OAuth not configured. Please set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in environment variables.",
        )

    params = {
        "response_type": "code",
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "redirect_uri": settings.LINKEDIN_CALLBACK_URL,
        "scope": "openid profile email",
    }

    url = "https://www.linkedin.com/oauth/v2/authorization?" + "&".join(
        f"{k}={v}" for k, v in params.items()
    )

    return {"authorization_url": url}


@router.post("/linkedin/callback")
async def linkedin_callback(
    code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Handle LinkedIn OAuth callback and store access token."""
    if not settings.LINKEDIN_CLIENT_ID or not settings.LINKEDIN_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn OAuth not configured",
        )

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.LINKEDIN_CLIENT_ID,
                "client_secret": settings.LINKEDIN_CLIENT_SECRET,
                "redirect_uri": settings.LINKEDIN_CALLBACK_URL,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token_data = token_response.json()

    if "error" in token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"LinkedIn OAuth error: {token_data.get('error_description', token_data['error'])}",
        )

    access_token = token_data["access_token"]

    # Get LinkedIn user profile
    async with httpx.AsyncClient() as client:
        profile_response = await client.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        profile_data = profile_response.json()

    linkedin_user_id = profile_data["sub"]
    linkedin_email = profile_data.get("email")

    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service

        await dynamo_service.update_item(
            "Users",
            {"userId": str(current_user.id)},
            {
                "linkedinUserId": linkedin_user_id,
                "linkedinEmail": linkedin_email,
                "linkedinToken": token_encryptor.encrypt(access_token),
                "updatedAt": dynamo_service.now_iso(),
            },
        )
        return {"message": "LinkedIn connected successfully"}

    # SQLite path
    result = await db.execute(
        select(LinkedInConnection).where(LinkedInConnection.user_id == current_user.id)
    )
    linkedin_conn = result.scalar_one_or_none()

    if linkedin_conn:
        # Update existing connection
        linkedin_conn.encrypted_token = token_encryptor.encrypt(access_token)
        linkedin_conn.linkedin_user_id = linkedin_user_id
        linkedin_conn.linkedin_email = linkedin_email
        linkedin_conn.token_updated_at = datetime.utcnow()
    else:
        # Create new connection
        linkedin_conn = LinkedInConnection(
            user_id=current_user.id,
            linkedin_user_id=linkedin_user_id,
            linkedin_email=linkedin_email,
            encrypted_token=token_encryptor.encrypt(access_token),
            scopes=["openid", "profile", "email", "w_member_social"],
        )
        db.add(linkedin_conn)

    await db.commit()

    return {"message": "LinkedIn connected successfully"}


@router.post("/linkedin/scrape-certifications")
async def scrape_linkedin_certifications_endpoint(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Scrape certifications from user's LinkedIn profile URL using Playwright.
    Uses the linkedin_url from user's profile.
    """
    from app.services.linkedin_scraper import parse_linkedin_url, scrape_linkedin_certifications

    if not current_user.linkedin_url:
        raise HTTPException(
            status_code=400,
            detail="No LinkedIn URL found in profile. Please add your LinkedIn URL first.",
        )

    # Validate and normalize URL
    linkedin_url = parse_linkedin_url(current_user.linkedin_url)
    if not linkedin_url:
        raise HTTPException(status_code=400, detail="Invalid LinkedIn URL format")

    try:
        # Scrape certifications using Playwright
        logger.info(f"Starting LinkedIn scrape for: {linkedin_url}")
        certifications = await scrape_linkedin_certifications(linkedin_url)
        logger.info(f"Scrape returned {len(certifications)} certifications: {certifications}")

        if not certifications:
            return {
                "success": True,
                "message": "No certifications found on LinkedIn profile. Make sure you're on the correct profile and have certifications listed.",
                "certifications": [],
            }

        # Merge with existing certifications (avoid duplicates)
        existing_certs = current_user.certifications or []
        existing_names = {cert.get("name", "").lower() for cert in existing_certs}

        new_certs = [
            cert for cert in certifications if cert.get("name", "").lower() not in existing_names
        ]

        logger.info(
            f"Adding {len(new_certs)} new certifications (filtered from {len(certifications)})"
        )

        # Update user certifications using direct SQL/DynamoDB update for reliability
        updated_certs = existing_certs + new_certs
        if settings.USE_DYNAMO:
            from app.services.dynamo_service import dynamo_service

            await dynamo_service.update_item(
                "Users",
                {"userId": str(current_user.id)},
                {
                    "certifications": updated_certs,
                    "updatedAt": dynamo_service.now_iso(),
                },
            )
        else:
            await db.execute(
                update(User).where(User.id == current_user.id).values(certifications=updated_certs)
            )
            await db.commit()
            # Refresh user to get updated data
            await db.refresh(current_user)

        logger.info(f"Successfully saved certifications. Total: {len(updated_certs)}")

        return {
            "success": True,
            "message": f"Imported {len(new_certs)} new certifications from LinkedIn",
            "certifications": new_certs,
            "total_certifications": len(updated_certs),
        }

    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        logger.error(f"Error scraping LinkedIn certifications: {str(e)}\n{error_details}")
        raise HTTPException(
            status_code=500, detail=f"Failed to scrape certifications: {str(e)}"
        ) from e


@router.post("/linkedin/import-profile")
async def import_linkedin_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Optional[LinkedInImportRequest] = Body(default=None),
):
    """
    Scrape a LinkedIn profile and import: summary, website, contact info,
    education, and certifications into the user's profile.

    Accepts an optional linkedin_url in the body; falls back to the
    linkedin_url already stored on the user record.
    """
    from app.services.linkedin_scraper import parse_linkedin_url, scrape_linkedin_profile

    # Resolve which URL to use — body is optional; fallback to stored profile URL
    req_url = request.linkedin_url if request else None
    raw_url = req_url or current_user.linkedin_url
    if not raw_url:
        raise HTTPException(
            status_code=400,
            detail="No LinkedIn URL provided. Pass linkedin_url in the request body.",
        )

    linkedin_url = parse_linkedin_url(raw_url)
    if not linkedin_url:
        raise HTTPException(status_code=400, detail="Invalid LinkedIn URL format")

    try:
        logger.info(f"Starting LinkedIn profile import for: {linkedin_url}")
        data = await scrape_linkedin_profile(linkedin_url)
    except Exception as e:
        import traceback

        logger.error(f"LinkedIn profile import failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail=f"Failed to import LinkedIn profile: {str(e)}"
        ) from e

    # ── Merge extracted data into user profile ───────────────────────────
    update_fields: dict = {}

    # Always persist the (possibly new) LinkedIn URL
    update_fields["linkedin_url"] = linkedin_url

    # Personal details — only fill if not already set
    if data.get("name") and not current_user.name:
        update_fields["name"] = data["name"]
    if data.get("headline"):
        update_fields["headline"] = data["headline"]
    if data.get("location") and not current_user.location:
        update_fields["location"] = data["location"]

    if data.get("summary"):
        update_fields["summary"] = data["summary"]

    if data.get("website") and not current_user.website:
        update_fields["website"] = data["website"]

    if data.get("phone") and not current_user.phone:
        update_fields["phone"] = data["phone"]

    if data.get("email") and not current_user.email:
        update_fields["email"] = data["email"]

    # Merge education — avoid duplicates by school name
    if data.get("education"):
        existing_edu: list = current_user.education or []
        existing_schools = {e.get("school", "").lower() for e in existing_edu}
        new_edu = [
            e
            for e in data["education"]
            if e.get("school") and e["school"].lower() not in existing_schools
        ]
        update_fields["education"] = existing_edu + new_edu

    # Merge certifications — avoid duplicates by name
    if data.get("certifications"):
        existing_certs: list = current_user.certifications or []
        existing_names = {c.get("name", "").lower() for c in existing_certs}
        new_certs = [
            c
            for c in data["certifications"]
            if c.get("name") and c["name"].lower() not in existing_names
        ]
        update_fields["certifications"] = existing_certs + new_certs

    # Compute counts BEFORE writing to DB (current_user may be refreshed after)
    new_edu_count = (
        len(update_fields.get("education", [])) - len(current_user.education or [])
        if "education" in update_fields
        else 0
    )
    new_certs_count = (
        len(update_fields.get("certifications", [])) - len(current_user.certifications or [])
        if "certifications" in update_fields
        else 0
    )

    # Write to DB (DynamoDB or SQL)
    _FIELD_MAP = {
        "linkedin_url": "linkedinUrl",
    }
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service

        dynamo_updates = {_FIELD_MAP.get(k, k): v for k, v in update_fields.items()}
        await dynamo_service.update_item(
            "Users",
            {"userId": str(current_user.id)},
            {**dynamo_updates, "updatedAt": dynamo_service.now_iso()},
        )
    else:
        if update_fields:
            await db.execute(update(User).where(User.id == current_user.id).values(**update_fields))
            await db.commit()
            await db.refresh(current_user)

    logger.info(f"LinkedIn profile import complete. Updated fields: {list(update_fields.keys())}")

    return {
        "success": True,
        "message": "LinkedIn profile imported successfully",
        "imported": {
            "name": data.get("name"),
            "headline": data.get("headline"),
            "location": data.get("location"),
            "summary": bool(data.get("summary")),
            "website": data.get("website"),
            "phone": data.get("phone"),
            "email": data.get("email"),
            "education_added": new_edu_count,
            "education": (update_fields.get("education") or [])[-new_edu_count:]
            if new_edu_count > 0
            else [],
            "certifications_added": new_certs_count,
        },
        "data": data,
    }
