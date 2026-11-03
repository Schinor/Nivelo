"""Rotas de Gestão de Obras.

Fase 3: a autorização de todas as rotas já vale (tenant do token e papel do vínculo), e a
listagem é real. Criar obra e registrar diário respondem 501 até a Fase 4 implementar os
casos de uso; com isso, os 403 por papel já são verificáveis.
"""

from __future__ import annotations

import uuid
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.obras.application.consultas import ObraResumo
from app.obras.infrastructure.consultas import ConsultaDeObrasSQL
from app.shared.api.autenticacao import requer_papel, tenant
from app.shared.api.sessao import sessao_do_tenant
from app.shared.application.contexto import TenantContext

router = APIRouter(prefix="/api/obras", tags=["obras"])

SEM_TENANT_OU_PAPEL: dict[int | str, dict[str, Any]] = {
    401: {"description": "Sem token ou token inválido"},
    403: {"description": "Token sem empresa ativa, ou papel sem permissão para a ação"},
}


class ObraResumoOut(BaseModel):
    id: uuid.UUID
    nome: str
    cidade: str
    uf: str
    status: str


class EmConstrucao(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Disponível na próxima versão")
        self.problem_type = "https://nivelo/erros/em-construcao"


@router.get("", response_model=list[ObraResumoOut], responses=SEM_TENANT_OU_PAPEL)
def listar_obras(ctx: TenantContext = Depends(tenant), db: Session = Depends(sessao_do_tenant)) -> list[ObraResumo]:
    """Dono: todas as obras da empresa. Encarregado e cliente: só as obras em que são membros."""
    return ConsultaDeObrasSQL(db).listar(ctx)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
    responses={**SEM_TENANT_OU_PAPEL, 501: {"description": "Chega na Fase 4"}},
)
def criar_obra(_request: Request, _ctx: TenantContext = Depends(requer_papel("dono"))) -> NoReturn:
    """Só o dono. O caso de uso chega na Fase 4."""
    raise EmConstrucao()


@router.post(
    "/{obra_id}/diarios",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
    responses={**SEM_TENANT_OU_PAPEL, 501: {"description": "Chega na Fase 4"}},
)
def registrar_diario(
    obra_id: uuid.UUID, _ctx: TenantContext = Depends(requer_papel("dono", "encarregado"))
) -> NoReturn:
    """Dono e encarregado. O caso de uso (com o 404 de obra de outra empresa) chega na Fase 4."""
    raise EmConstrucao()
