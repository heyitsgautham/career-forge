"""
Auth schemas
============
Request and response models for the /api/auth routes.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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

    model_config = ConfigDict(from_attributes=True)


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
    achievements: Optional[list]

    model_config = ConfigDict(from_attributes=True)


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
    achievements: Optional[list] = None


class GitHubCallbackRequest(BaseModel):
    code: str
    installation_id: Optional[int] = None
    link_token: Optional[str] = None  # existing JWT — link GitHub to this user


class CognitoCallbackRequest(BaseModel):
    code: str


class LinkedInImportRequest(BaseModel):
    linkedin_url: Optional[str] = None  # If not provided, uses stored profile URL
