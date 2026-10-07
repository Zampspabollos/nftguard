from pydantic import BaseModel, field_validator


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SetupRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if not (3 <= len(v) <= 32):
            raise ValueError("username debe tener entre 3 y 32 caracteres")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password debe tener al menos 8 caracteres")
        if len(v.encode("utf-8")) > 72:
            raise ValueError("password no puede superar 72 bytes (límite de bcrypt)")
        return v
