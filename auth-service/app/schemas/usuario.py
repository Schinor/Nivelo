from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, computed_field


class PermissaoOut(BaseModel):
    id: int
    action: str
    resource: str
    description: str | None = None

    @computed_field
    @property
    def slug(self) -> str:
        return f"{self.action}:{self.resource}"

    model_config = ConfigDict(from_attributes=True)


class PapelOut(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    permissoes: list[PermissaoOut] = []

    model_config = ConfigDict(from_attributes=True)


class PapelCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    permission_ids: list[int] = []


class UsuarioCreate(BaseModel):
    """Cadastro público. Sem campo de papel de propósito: quem se cadastra é sempre `dono`
    (campos extras como `role` ou `papel` são ignorados)."""

    nome: str
    email: EmailStr
    senha: str


class UsuarioOut(BaseModel):
    id: int
    nome: str
    email: str
    role: str = "cliente"
    role_id: int | None = None
    permissions: list[str] = []
    criado_em: datetime | None = None
    premium: bool = False
    premium_desde: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserRoleUpdate(BaseModel):
    role: str


class UserPermissionsUpdate(BaseModel):
    permissions: list[str]


class UserRoleOut(BaseModel):
    user_id: int
    role: str
    role_id: int | None = None
    permissions: list[str] = []
