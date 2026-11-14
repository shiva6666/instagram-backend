from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_.]+$")
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    bio: str | None = Field(default=None, max_length=500)
    is_private: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    bio: str | None
    avatar_key: str | None
    is_private: bool
    status: str
    created_at: datetime


class TokenResponse(BaseModel):
    token_type: str = "bearer"
    access_token: str
    expires_in: int
    refresh_token: str
    user: UserResponse


class MessageResponse(BaseModel):
    message: str
