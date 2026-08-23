from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.passwords import PASSWORD_REQUIREMENT, password_meets_policy
from app.core.roles import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    remember_me: bool = False


class RegisterRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def validate_password_policy(cls, value: str) -> str:
        if not password_meets_policy(value):
            raise ValueError(PASSWORD_REQUIREMENT)
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    disclaimer: str


class CurrentUserResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    lawyer_request_status: str
    enrollment_number: str | None = None
    disclaimer: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    detail: str


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16)
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def validate_password_policy(cls, value: str) -> str:
        if not password_meets_policy(value):
            raise ValueError(PASSWORD_REQUIREMENT)
        return value
