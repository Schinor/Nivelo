from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict, computed_field


class PermissaoOut(BaseModel):
    id: int
    action: str
    resource: str
    description: Optional[str] = None

    @computed_field
    @property
    def slug(self) -> str:
        return f"{self.action}:{self.resource}"

    model_config = ConfigDict(from_attributes=True)


class PapelOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    permissoes: List[PermissaoOut] = []

    model_config = ConfigDict(from_attributes=True)


class PapelCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    permission_ids: List[int] = []


class UsuarioCreate(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    role: Optional[str] = None


class UsuarioOut(BaseModel):
    id: int
    nome: str
    email: str
    role: str = "cliente"
    role_id: Optional[int] = None
    permissions: List[str] = []
    criado_em: Optional[datetime] = None
    premium: bool = False
    premium_desde: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Optional[UsuarioOut] = None


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
    email: Optional[str] = None
    message: Optional[str] = None


class UserRoleUpdate(BaseModel):
    role: str


class UserPermissionsUpdate(BaseModel):
    permissions: List[str]


class UserRoleOut(BaseModel):
    user_id: int
    role: str
    role_id: Optional[int] = None
    permissions: List[str] = []
