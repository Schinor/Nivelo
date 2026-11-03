"""Convites (espelho dos schemas do auth-service)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ConviteIn(BaseModel):
    email: EmailStr
    papel: Literal["encarregado", "cliente"]
    obra_id: uuid.UUID | None = None


class ConviteOut(BaseModel):
    """Sem o token: ele só existe no e-mail do convidado."""

    id: uuid.UUID
    email: str
    papel: str
    obra_id: uuid.UUID | None = None
    expira_em: datetime

    model_config = ConfigDict(from_attributes=True)


class AceiteIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    # Só para quem ainda não tem conta com o e-mail do convite
    nome: str | None = Field(default=None, min_length=2, max_length=100)
    senha: str | None = Field(default=None, min_length=6, max_length=72)


class AceiteOut(BaseModel):
    usuario_id: int
    empresa_id: uuid.UUID
    papel: str
    obra_id: uuid.UUID | None = None
    novo_usuario: bool
