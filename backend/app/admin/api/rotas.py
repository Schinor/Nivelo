"""Painel da plataforma: só o admin, só leitura e nenhum dado de obra."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.admin.api.schemas import MetricasOut
from app.admin.application.metricas import LeituraDeContas, LeituraDeEventos, consultar_metricas
from app.admin.infrastructure.leituras import AssinaturasSQL, ContasViaAuthService, EventosViaLogService
from app.core.database import get_db
from app.shared.api.autenticacao import Identidade, requer_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


def contas_da_plataforma() -> LeituraDeContas:
    return ContasViaAuthService()


def eventos_da_plataforma() -> LeituraDeEventos:
    return EventosViaLogService()


@router.get(
    "/metricas",
    response_model=MetricasOut,
    responses={401: {"description": "Sem token válido"}, 403: {"description": "Só o admin da plataforma"}},
)
def consultar_painel(
    _admin: Identidade = Depends(requer_admin),
    db: Session = Depends(get_db),
    contas: LeituraDeContas = Depends(contas_da_plataforma),
    eventos: LeituraDeEventos = Depends(eventos_da_plataforma),
) -> MetricasOut:
    """Empresas e usuários por plano, assinaturas ativas, MRR de teste, inadimplentes e últimos eventos."""
    return MetricasOut.model_validate(consultar_metricas(AssinaturasSQL(db), contas, eventos))
