"""
Auth routes: profile
====================
Resume upload parsing and the editable user profile.
"""

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    UserProfileResponse,
    UserProfileUpdate,
)
from app.services.bedrock_client import bedrock_client
from app.services.document_parser import DocumentParserService

logger = structlog.get_logger()

router = APIRouter()


@router.post("/upload-resume")
async def upload_resume_for_profile(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload an existing resume to extract profile information.
    Uses AI to parse the resume and populate user profile fields.
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = file.filename.lower().split(".")[-1]
    if ext not in ["pdf", "docx", "doc", "txt"]:
        raise HTTPException(
            status_code=400, detail="Unsupported file type. Please upload PDF, DOCX, or TXT files."
        )

    try:
        # Read file content
        content = await file.read()

        # Extract text from document
        parser = DocumentParserService()
        text = await parser.extract_text(file.filename, content)

        if not text or len(text.strip()) < 50:
            raise HTTPException(
                status_code=400, detail="Could not extract meaningful text from the document"
            )

        logger.info(f"Extracted {len(text)} characters from resume")

        # Use Gemini to parse resume and extract structured data
        prompt = f"""Extract profile information from this resume text:

{text[:3500]}

Return a JSON object with these fields (use null for any field not found):
- name: Full name
- email: Email address
- phone: Phone number
- location: City and state
- city: City
- state: State
- country: Country
- headline: Professional title
- summary: Brief professional summary
- institution: Educational institution name (legacy field)
- degree: Degree name (legacy field)
- field_of_study: Major or field (legacy field)
- graduation_year: Year only (legacy field)
- linkedin_url: LinkedIn URL
- website: Portfolio URL
- skills: Array of technical skills
- experience: Array of work experience entries. Each entry should have:
  * company: Company name
  * title: Job title
  * dates: Employment dates (e.g., "Jan 2020 - Present")
  * location: Job location (optional)
  * highlights: Array of 3-4 key achievements or responsibilities
- education: Array of education entries. Each entry should have:
  * school: Institution name
  * degree: Degree type (e.g., "Bachelor of Science")
  * field: Field of study
  * dates: Education dates (e.g., "2018 - 2022")
  * location: School location (optional)
  * gpa: GPA if mentioned (optional)

Extract only information clearly present. For experience and education, extract ALL entries found in the resume."""

        try:
            logger.info("Attempting to parse resume with Gemini...")

            # Try the generate_json method first
            try:
                extracted_data = await bedrock_client.generate_json(
                    prompt=prompt,
                    system_instruction="You are a professional resume parser. Return valid JSON only.",
                    temperature=0.1,
                )
                logger.info(f"Successfully parsed resume with {len(extracted_data)} fields")

            except Exception as json_error:
                logger.warning(f"generate_json failed: {json_error}, trying generate_content...")

                # Fallback to generate_content with manual JSON parsing
                import json

                full_prompt = (
                    prompt + "\n\nReturn ONLY a valid JSON object, no markdown, no extra text."
                )
                response_text = await bedrock_client.generate_content(
                    prompt=full_prompt,
                    system_instruction="You are a professional resume parser.",
                    temperature=0.1,
                    max_tokens=1500,
                )

                # Clean and extract JSON
                cleaned = response_text.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

                # Extract JSON by finding the JSON object boundaries
                start_idx = cleaned.find(chr(123))  # chr(123) is '{'
                end_idx = cleaned.rfind(chr(125))  # chr(125) is '}'
                if start_idx != -1 and end_idx != -1:
                    cleaned = cleaned[start_idx : end_idx + 1]

                extracted_data = json.loads(cleaned)
                logger.info("Successfully parsed with fallback method")

        except Exception as e:
            logger.error(f"All parsing attempts failed: {type(e).__name__}: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse resume with AI. Error: {str(e)[:100]}. Please try again.",
            ) from e

        # Update user profile with extracted data (only non-null values)
        _FIELD_MAP = {
            "linkedin_url": "linkedinUrl",
            "address_line1": "addressLine1",
            "address_line2": "addressLine2",
            "zip_code": "zipCode",
            "field_of_study": "fieldOfStudy",
            "graduation_year": "graduationYear",
        }
        _KNOWN_FIELDS = {
            "name",
            "email",
            "phone",
            "location",
            "city",
            "state",
            "country",
            "headline",
            "summary",
            "institution",
            "degree",
            "field_of_study",
            "graduation_year",
            "linkedin_url",
            "website",
            "skills",
            "experience",
            "education",
            "address_line1",
            "address_line2",
            "zip_code",
        }
        update_values = {}
        for field, value in extracted_data.items():
            if value is None or value == "" or field not in _KNOWN_FIELDS:
                continue
            if field == "email" and current_user.email:
                continue
            if field == "name" and current_user.name and value.lower() in ["user", "name"]:
                continue
            update_values[field] = value

        if update_values:
            if settings.USE_DYNAMO:
                from app.services.dynamo_service import dynamo_service

                dynamo_updates = {_FIELD_MAP.get(k, k): v for k, v in update_values.items()}
                dynamo_updates["updatedAt"] = dynamo_service.now_iso()
                await dynamo_service.update_item(
                    "Users", {"userId": str(current_user.id)}, dynamo_updates
                )
            else:
                await db.execute(
                    update(User).where(User.id == current_user.id).values(**update_values)
                )
                await db.commit()
                await db.refresh(current_user)

        logger.info(f"Updated {len(update_values)} profile fields for user {current_user.id}")

        return {
            "message": "Resume parsed successfully",
            "fields_updated": len(update_values),
            "extracted_data": extracted_data,
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing resume: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing resume: {str(e)}") from e


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's complete profile."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service

        # Re-fetch fresh data from DynamoDB
        user_data = await dynamo_service.get_item("Users", {"userId": str(current_user.id)})
        if user_data:
            from app.api.deps import DynamoUser

            current_user = DynamoUser(user_data)
    else:
        await db.refresh(current_user)

    return UserProfileResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        headline=current_user.headline,
        summary=current_user.summary,
        location=current_user.location,
        phone=current_user.phone,
        website=current_user.website,
        linkedin_url=current_user.linkedin_url,
        address_line1=current_user.address_line1,
        address_line2=current_user.address_line2,
        city=current_user.city,
        state=current_user.state,
        zip_code=current_user.zip_code,
        country=current_user.country,
        institution=current_user.institution,
        degree=current_user.degree,
        field_of_study=current_user.field_of_study,
        graduation_year=current_user.graduation_year,
        experience=current_user.experience,
        education=current_user.education,
        skills=current_user.skills,
        certifications=current_user.certifications,
        achievements=current_user.achievements,
    )


@router.put("/profile", response_model=UserProfileResponse)
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's profile."""
    # Build update dict with only provided fields
    update_values = {}
    for field, value in profile_data.model_dump(exclude_unset=True).items():
        if value is not None:
            update_values[field] = value

    if settings.USE_DYNAMO:
        from app.api.deps import DynamoUser
        from app.services.dynamo_service import dynamo_service

        # Map snake_case SQLAlchemy field names to DynamoDB camelCase attribute names
        _FIELD_MAP = {
            "linkedin_url": "linkedinUrl",
            "address_line1": "addressLine1",
            "address_line2": "addressLine2",
            "zip_code": "zipCode",
            "field_of_study": "fieldOfStudy",
            "graduation_year": "graduationYear",
            "avatar_url": "avatarUrl",
        }
        dynamo_updates = {_FIELD_MAP.get(k, k): v for k, v in update_values.items()}
        if dynamo_updates:
            dynamo_updates["updatedAt"] = dynamo_service.now_iso()
            await dynamo_service.update_item(
                "Users", {"userId": str(current_user.id)}, dynamo_updates
            )
        # Re-fetch fresh data
        user_data = await dynamo_service.get_item("Users", {"userId": str(current_user.id)})
        if user_data:
            current_user = DynamoUser(user_data)
        logger.info(f"Updated {len(dynamo_updates)} profile fields for user {current_user.id}")
    else:
        if update_values:
            await db.execute(update(User).where(User.id == current_user.id).values(**update_values))
            await db.commit()
            await db.refresh(current_user)
        logger.info(f"Updated {len(update_values)} profile fields for user {current_user.id}")

    return UserProfileResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        headline=current_user.headline,
        summary=current_user.summary,
        location=current_user.location,
        phone=current_user.phone,
        website=current_user.website,
        linkedin_url=current_user.linkedin_url,
        address_line1=current_user.address_line1,
        address_line2=current_user.address_line2,
        city=current_user.city,
        state=current_user.state,
        zip_code=current_user.zip_code,
        country=current_user.country,
        institution=current_user.institution,
        degree=current_user.degree,
        field_of_study=current_user.field_of_study,
        graduation_year=current_user.graduation_year,
        experience=current_user.experience,
        education=current_user.education,
        skills=current_user.skills,
        certifications=current_user.certifications,
        achievements=current_user.achievements,
    )
