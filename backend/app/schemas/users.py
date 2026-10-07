from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


def _validate_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("password debe tener al menos 8 caracteres")
    if len(v.encode("utf-8")) > 72:
        raise ValueError("password no puede superar 72 bytes (límite de bcrypt)")
    return v


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_admin: bool
    created_at: datetime


class UserCreate(BaseModel):
    username: str
    password: str
    is_admin: bool = False

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if not (3 <= len(v) <= 32):
            raise ValueError("username debe tener entre 3 y 32 caracteres")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        return _validate_password(v)


class AdminPasswordReset(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        return _validate_password(v)


class SelfPasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        return _validate_password(v)
