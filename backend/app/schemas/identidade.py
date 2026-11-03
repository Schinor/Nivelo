"""Cadastro com empresa, vínculos e troca de empresa ativa (espelho dos schemas do auth-service)."""

import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.usuario import UsuarioOut

TipoPessoa = Literal["PF", "PJ"]
DIGITOS_DO_DOCUMENTO = {"PF": 11, "PJ": 14}


def _normalizar_documento(documento: str | None, tipo_pessoa: str) -> str | None:
    """Guarda só os dígitos. CPF (PF) tem 11; CNPJ (PJ) tem 14. Vazio vira None."""
    if documento is None:
        return None
    digitos = re.sub(r"\D", "", documento)
    if not digitos:
        return None
    esperado = DIGITOS_DO_DOCUMENTO[tipo_pessoa]
    if len(digitos) != esperado:
        rotulo = "CPF" if tipo_pessoa == "PF" else "CNPJ"
        raise ValueError(f"{rotulo} deve ter {esperado} dígitos")
    return digitos


class EmpresaIn(BaseModel):
    nome: str = Field(min_length=2, max_length=160, description="Nome da empresa ou nome profissional")
    tipo_pessoa: TipoPessoa = "PF"
    documento: str | None = Field(default=None, description="CPF (PF) ou CNPJ (PJ), opcional")

    @field_validator("nome")
    @classmethod
    def _aparar(cls, valor: str) -> str:
        return valor.strip()

    @model_validator(mode="after")
    def _documento(self) -> "EmpresaIn":
        self.documento = _normalizar_documento(self.documento, self.tipo_pessoa)
        return self


class CadastroIn(BaseModel):
    """Cadastro público: cria a empresa, o usuário e o vínculo `dono`. O papel nunca vem do corpo."""

    nome: str = Field(min_length=2, max_length=100)
    email: EmailStr
    senha: str = Field(min_length=6, max_length=72)
    empresa_nome: str = Field(min_length=2, max_length=160, description="Nome da sua empresa ou seu nome profissional")
    tipo_pessoa: TipoPessoa = "PF"
    documento: str | None = None

    @model_validator(mode="after")
    def _normalizar(self) -> "CadastroIn":
        self.nome = self.nome.strip()
        self.empresa_nome = self.empresa_nome.strip()
        self.documento = _normalizar_documento(self.documento, self.tipo_pessoa)
        return self


class EmpresaOut(BaseModel):
    id: uuid.UUID
    nome: str
    tipo_pessoa: TipoPessoa
    documento: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ContextoOut(BaseModel):
    """A empresa ativa do token. Ausente (null) = token sem tenant."""

    empresa_id: uuid.UUID
    empresa_nome: str
    papel: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UsuarioOut
    contexto: ContextoOut | None = None


class CadastroOut(BaseModel):
    usuario: UsuarioOut
    empresa: EmpresaOut
    papel: str = "dono"


class EmpresaCriadaOut(TokenOut):
    """Empresa nova do usuário logado, já como empresa ativa no token devolvido."""

    empresa: EmpresaOut


class VinculoOut(BaseModel):
    empresa_id: uuid.UUID
    empresa_nome: str
    tipo_pessoa: TipoPessoa
    papel: str
    ativa: bool = Field(description="É a empresa ativa do token usado na consulta")


class EmpresaAtivaIn(BaseModel):
    empresa_id: uuid.UUID
