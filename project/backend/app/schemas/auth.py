"""
Auth schemas
============
Request and response models for the /api/auth routes.
"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas.limits import (
    Name,
    NewPassword,
    Paragraph,
    Password,
    ShortText,
    TagList,
    Url,
    bounded_list,
)


class UserCreate(BaseModel):
    email: EmailStr
    password: NewPassword
    name: Optional[Name] = None
    full_name: Optional[Name] = None

    def get_name(self) -> str:
        return self.name or self.full_name or "User"


class UserLogin(BaseModel):
    email: EmailStr
    password: Password


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

    name: Optional[ShortText] = None
    headline: Optional[ShortText] = None
    summary: Optional[Paragraph] = None
    location: Optional[ShortText] = None
    phone: Optional[ShortText] = None
    website: Optional[Url] = None
    linkedin_url: Optional[Url] = None
    address_line1: Optional[ShortText] = None
    address_line2: Optional[ShortText] = None
    city: Optional[ShortText] = None
    state: Optional[ShortText] = None
    zip_code: Optional[ShortText] = None
    country: Optional[ShortText] = None
    institution: Optional[ShortText] = None
    degree: Optional[ShortText] = None
    field_of_study: Optional[ShortText] = None
    graduation_year: Optional[ShortText] = None
    experience: Optional[bounded_list(Any)] = None
    education: Optional[bounded_list(Any)] = None
    skills: Optional[TagList] = None
    certifications: Optional[bounded_list(Any)] = None
    achievements: Optional[bounded_list(Any)] = None


class GitHubCallbackRequest(BaseModel):
    code: str
    installation_id: Optional[int] = None
    link_token: Optional[str] = None  # existing JWT — link GitHub to this user


class CognitoCallbackRequest(BaseModel):
    code: str


class LinkedInImportRequest(BaseModel):
    linkedin_url: Optional[Url] = None  # If not provided, uses stored profile URL
