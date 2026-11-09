from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UsuarioOut(BaseModel):
    id: int
    nome: str
    email: str
    admin: bool = False
    criado_em: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


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
