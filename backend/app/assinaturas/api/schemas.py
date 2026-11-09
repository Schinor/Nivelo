"""Entrada e saída das rotas de Assinaturas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class DireitosOut(BaseModel):
    max_obras_ativas: int | None
    max_fotos_por_obra: int | None
    max_membros_equipe: int | None
    logo_no_relatorio: bool


class UsoOut(BaseModel):
    obras_ativas: int
    fotos_na_obra_mais_cheia: int
    membros_equipe: int | None


class AssinaturaOut(BaseModel):
    plano: str
    plano_efetivo: str
    status: str
    tem_assinatura_vigente: bool
    periodo_fim: datetime | None
    cancelar_no_fim: bool
    direitos: DireitosOut
    uso: UsoOut


class CheckoutIn(BaseModel):
    plano: Literal["pro", "construtora"]


class UrlOut(BaseModel):
    url: str
