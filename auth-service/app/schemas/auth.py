from pydantic import BaseModel, EmailStr

from app.schemas.usuario import UsuarioOut


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UsuarioOut


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    token: str
    nova_senha: str


class ResetPasswordResponse(BaseModel):
    message: str


class ValidateTokenResponse(BaseModel):
    valid: bool
    email: str | None = None
    message: str | None = None
