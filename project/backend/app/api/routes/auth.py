"""
Authentication Routes
====================
User authentication and GitHub OAuth.
"""

from datetime import timedelta, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel, EmailStr, Field
import httpx
import structlog

from app.core.database import get_db
from app.core.config import settings
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    token_encryptor,
)
from app.models.user import User, GithubConnection, LinkedInConnection
from app.api.deps import get_current_user
from app.services.document_parser import DocumentParserService
from app.services.bedrock_client import bedrock_client

logger = structlog.get_logger()


router = APIRouter()


# Pydantic models
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str = Field(default=None)
    full_name: str = Field(default=None)
    
    def get_name(self) -> str:
        return self.name or self.full_name or "User"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: Optional[str]
    is_verified: bool

    class Config:
        from_attributes = True


class UserProfileResponse(BaseModel):
    """Complete user profile with all fields"""
    id: str
    email: str
    name: Optional[str]
    headline: Optional[str]
    summary: Optional[str]
    location: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    linkedin_url: Optional[str]
    address_line1: Optional[str]
    address_line2: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]
    country: Optional[str]
    institution: Optional[str]
    degree: Optional[str]
    field_of_study: Optional[str]
    graduation_year: Optional[str]
    experience: Optional[list]
    education: Optional[list]
    skills: Optional[list]
    certifications: Optional[list]
    
    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    """Fields that can be updated in user profile"""
    name: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    location: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    graduation_year: Optional[str] = None
    experience: Optional[list] = None
    education: Optional[list] = None
    skills: Optional[list] = None
    certifications: Optional[list] = None


class GitHubCallbackRequest(BaseModel):
    code: str
    installation_id: Optional[int] = None
    link_token: Optional[str] = None  # existing JWT — link GitHub to this user


# Routes
@router.post("/register", response_model=TokenResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user with email and password."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service
        from boto3.dynamodb.conditions import Attr
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
        await dynamo_service.put_item("Users", {
            "userId": user_id,
            "email": user_data.email,
            "name": user_data.get_name(),
            "hashedPassword": get_password_hash(user_data.password),
            "isActive": True,
            "isVerified": False,
            "createdAt": now,
            "updatedAt": now,
        })
        access_token = create_access_token(
            data={"sub": user_id},
            expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return TokenResponse(access_token=access_token)

    # SQLite path
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
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
        from app.services.dynamo_service import dynamo_service
        from boto3.dynamodb.conditions import Attr
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
    result = await db.execute(
        select(User).where(User.email == credentials.email)
    )
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
        primary_email = next(
            (e["email"] for e in emails if e["primary"]),
            github_user.get("email")
        )
    
    if not primary_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not get email from GitHub",
        )
    
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service
        from boto3.dynamodb.conditions import Attr

        is_new_user = False
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
                    is_new_user = True
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
        select(GithubConnection).where(
            GithubConnection.github_user_id == github_user["id"]
        )
    )
    github_conn = result.scalar_one_or_none()
    
    if github_conn:
        # Update token
        github_conn.encrypted_token = token_encryptor.encrypt(github_token)
        user = await db.get(User, github_conn.user_id)
    else:
        # Check if user exists with this email
        result = await db.execute(
            select(User).where(User.email == primary_email)
        )
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


# ─── Cognito (Google sign-in) ───────────────────────────────────────────────


class CognitoCallbackRequest(BaseModel):
    code: str


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

    if not settings.COGNITO_APP_CLIENT_ID or not settings.COGNITO_DOMAIN:
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

    # ── Find or create user in DynamoDB ──
    from app.services.dynamo_service import dynamo_service
    from boto3.dynamodb.conditions import Attr

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
        email_match = await dynamo_service.scan(
            "Users", filter_expression=Attr("email").eq(email)
        )
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
            await dynamo_service.put_item("Users", {
                "userId": user_id,
                "email": email,
                "name": name or email.split("@")[0],
                "cognitoSub": cognito_sub,
                "isActive": True,
                "isVerified": True,
                "ingestionStatus": "none",
                "createdAt": now,
                "updatedAt": now,
            })

    access_token = create_access_token(
        data={"sub": user_id},
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(access_token=access_token)


# Next-auth compatibility endpoints
@router.get("/session")
async def get_session():
    """Next-auth session endpoint - returns null for our JWT-based auth."""
    return None


@router.post("/_log")
async def auth_log():
    """Next-auth logging endpoint - no-op for our implementation."""
    return {"ok": True}


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
            status_code=400,
            detail=f"Unsupported file type. Please upload PDF, DOCX, or TXT files."
        )
    
    try:
        # Read file content
        content = await file.read()
        
        # Extract text from document
        parser = DocumentParserService()
        text = await parser.extract_text(file.filename, content)
        
        if not text or len(text.strip()) < 50:
            raise HTTPException(
                status_code=400,
                detail="Could not extract meaningful text from the document"
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
            logger.info(f"Attempting to parse resume with Gemini...")
            
            
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
                import re
                
                full_prompt = prompt + "\n\nReturn ONLY a valid JSON object, no markdown, no extra text."
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
                    cleaned = cleaned[start_idx:end_idx + 1]
                
                extracted_data = json.loads(cleaned)
                logger.info("Successfully parsed with fallback method")
            
        except Exception as e:
            logger.error(f"All parsing attempts failed: {type(e).__name__}: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse resume with AI. Error: {str(e)[:100]}. Please try again."
            )
        
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
            "name", "email", "phone", "location", "city", "state", "country",
            "headline", "summary", "institution", "degree", "field_of_study",
            "graduation_year", "linkedin_url", "website", "skills", "experience",
            "education", "address_line1", "address_line2", "zip_code",
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
                await dynamo_service.update_item("Users", {"userId": str(current_user.id)}, dynamo_updates)
            else:
                await db.execute(
                    update(User)
                    .where(User.id == current_user.id)
                    .values(**update_values)
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
        raise HTTPException(
            status_code=500,
            detail=f"Error processing resume: {str(e)}"
        )


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
        from app.services.dynamo_service import dynamo_service
        from app.api.deps import DynamoUser
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
            await dynamo_service.update_item("Users", {"userId": str(current_user.id)}, dynamo_updates)
        # Re-fetch fresh data
        user_data = await dynamo_service.get_item("Users", {"userId": str(current_user.id)})
        if user_data:
            current_user = DynamoUser(user_data)
        logger.info(f"Updated {len(dynamo_updates)} profile fields for user {current_user.id}")
    else:
        if update_values:
            await db.execute(
                update(User)
                .where(User.id == current_user.id)
                .values(**update_values)
            )
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
    )


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
            GithubConnection.is_primary == True,
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
        await dynamo_service.update_item("Users", {"userId": str(current_user.id)}, {
            "linkedinUserId": linkedin_user_id,
            "linkedinEmail": linkedin_email,
            "linkedinToken": token_encryptor.encrypt(access_token),
            "updatedAt": dynamo_service.now_iso(),
        })
        return {"message": "LinkedIn connected successfully"}

    # SQLite path
    result = await db.execute(
        select(LinkedInConnection).where(
            LinkedInConnection.user_id == current_user.id
        )
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Scrape certifications from user's LinkedIn profile URL using Playwright.
    Uses the linkedin_url from user's profile.
    """
    from app.services.linkedin_scraper import scrape_linkedin_certifications, parse_linkedin_url
    
    if not current_user.linkedin_url:
        raise HTTPException(
            status_code=400,
            detail="No LinkedIn URL found in profile. Please add your LinkedIn URL first."
        )
    
    # Validate and normalize URL
    linkedin_url = parse_linkedin_url(current_user.linkedin_url)
    if not linkedin_url:
        raise HTTPException(
            status_code=400,
            detail="Invalid LinkedIn URL format"
        )
    
    try:
        # Scrape certifications using Playwright
        logger.info(f"Starting LinkedIn scrape for: {linkedin_url}")
        certifications = await scrape_linkedin_certifications(linkedin_url)
        logger.info(f"Scrape returned {len(certifications)} certifications: {certifications}")
        
        if not certifications:
            return {
                "success": True,
                "message": "No certifications found on LinkedIn profile. Make sure you're on the correct profile and have certifications listed.",
                "certifications": []
            }
        
        # Merge with existing certifications (avoid duplicates)
        existing_certs = current_user.certifications or []
        existing_names = {cert.get('name', '').lower() for cert in existing_certs}
        
        new_certs = [
            cert for cert in certifications
            if cert.get('name', '').lower() not in existing_names
        ]
        
        logger.info(f"Adding {len(new_certs)} new certifications (filtered from {len(certifications)})")
        
        # Update user certifications using direct SQL/DynamoDB update for reliability
        updated_certs = existing_certs + new_certs
        if settings.USE_DYNAMO:
            from app.services.dynamo_service import dynamo_service
            await dynamo_service.update_item("Users", {"userId": str(current_user.id)}, {
                "certifications": updated_certs,
                "updatedAt": dynamo_service.now_iso(),
            })
        else:
            await db.execute(
                update(User)
                .where(User.id == current_user.id)
                .values(certifications=updated_certs)
            )
            await db.commit()
            # Refresh user to get updated data
            await db.refresh(current_user)

        logger.info(f"Successfully saved certifications. Total: {len(updated_certs)}")
        
        return {
            "success": True,
            "message": f"Imported {len(new_certs)} new certifications from LinkedIn",
            "certifications": new_certs,
            "total_certifications": len(updated_certs)
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error scraping LinkedIn certifications: {str(e)}\n{error_details}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to scrape certifications: {str(e)}"
        )


class LinkedInImportRequest(BaseModel):
    linkedin_url: Optional[str] = None  # If not provided, uses stored profile URL


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
    from app.services.linkedin_scraper import scrape_linkedin_profile, parse_linkedin_url

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
        raise HTTPException(status_code=500, detail=f"Failed to import LinkedIn profile: {str(e)}")

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
            e for e in data["education"]
            if e.get("school") and e["school"].lower() not in existing_schools
        ]
        update_fields["education"] = existing_edu + new_edu

    # Merge certifications — avoid duplicates by name
    if data.get("certifications"):
        existing_certs: list = current_user.certifications or []
        existing_names = {c.get("name", "").lower() for c in existing_certs}
        new_certs = [
            c for c in data["certifications"]
            if c.get("name") and c["name"].lower() not in existing_names
        ]
        update_fields["certifications"] = existing_certs + new_certs

    # Compute counts BEFORE writing to DB (current_user may be refreshed after)
    new_edu_count   = len(update_fields.get("education",       [])) - len(current_user.education       or []) if "education"       in update_fields else 0
    new_certs_count = len(update_fields.get("certifications",  [])) - len(current_user.certifications  or []) if "certifications"  in update_fields else 0

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
            await db.execute(
                update(User).where(User.id == current_user.id).values(**update_fields)
            )
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
            "education": (update_fields.get("education") or [])[-new_edu_count:] if new_edu_count > 0 else [],
            "certifications_added": new_certs_count,
        },
        "data": data,
    }