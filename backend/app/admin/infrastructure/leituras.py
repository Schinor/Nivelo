"""Adaptadores do painel: a tabela de assinaturas, o auth-service e o log-service."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.application.metricas import (
    ContasDaPlataforma,
    EmpresaDaPlataforma,
    EventoDaPlataforma,
    LinhaDeAssinatura,
)
from app.assinaturas.domain.planos import Plano, StatusAssinatura
from app.assinaturas.infrastructure.modelos import AssinaturaModel
from app.core.config import settings
from app.shared.api.request_id import HEADER as REQUEST_ID_HEADER
from app.shared.api.request_id import obter_request_id
from app.shared.application.erros import DependenciaIndisponivel
from app.shared.infrastructure.tenancy import sem_tenant

logger = logging.getLogger("nivelo.api.admin")


class AssinaturasSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def linhas(self) -> list[LinhaDeAssinatura]:
        consulta = select(
            AssinaturaModel.empresa_id,
            AssinaturaModel.plano,
            AssinaturaModel.status,
            AssinaturaModel.valor_mensal_centavos,
        )
        with sem_tenant(self._session, "painel admin: soma as assinaturas de todas as empresas"):
            registros = self._session.execute(consulta).all()
        return [
            LinhaDeAssinatura(str(empresa_id), Plano(plano), StatusAssinatura.de_texto(status), valor)
            for empresa_id, plano, status, valor in registros
        ]


def _contas_de(corpo: dict[str, Any]) -> ContasDaPlataforma:
    usuarios: list[dict[str, Any]] = corpo["usuarios"]
    return ContasDaPlataforma(
        empresas=[
            EmpresaDaPlataforma(str(e["id"]), str(e["nome"]), frozenset(int(u) for u in e["usuario_ids"]))
            for e in corpo["empresas"]
        ],
        nomes_de_usuarios={int(u["id"]): str(u["nome"]) for u in usuarios},
        total_de_usuarios=sum(1 for u in usuarios if not u["admin"]),
    )


class ContasViaAuthService:
    def contas(self) -> ContasDaPlataforma:
        headers = {"X-Internal-Token": settings.AUTH_INTERNAL_TOKEN}
        request_id = obter_request_id()
        if request_id:
            headers[REQUEST_ID_HEADER] = request_id
        try:
            resp = httpx.get(
                f"{settings.AUTH_SERVICE_URL.rstrip('/')}/internal/metricas/contas", headers=headers, timeout=5.0
            )
            resp.raise_for_status()
            return _contas_de(resp.json())
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            logger.warning("auth-service não respondeu às contas do painel: confira AUTH_INTERNAL_TOKEN", exc_info=True)
            raise DependenciaIndisponivel("As contas estão indisponíveis agora.") from None


def _evento_de(bruto: dict[str, Any]) -> EventoDaPlataforma:
    ator = str(bruto.get("usuario_id") or "")
    return EventoDaPlataforma(
        tipo=bruto.get("tipo") or bruto.get("acao"),
        ator_id=int(ator) if ator.isdigit() else None,
        ator_papel=bruto.get("ator_papel") or None,
        empresa_id=bruto.get("empresa_id") or None,
        quando=bruto.get("timestamp"),
    )


class EventosViaLogService:
    def ultimos(self, limite: int) -> list[EventoDaPlataforma]:
        try:
            resp = httpx.get(
                f"{settings.LOG_SERVICE_URL.rstrip('/')}/eventos",
                params={"limit": limite},
                headers={"X-Internal-Token": settings.LOG_INTERNAL_TOKEN},
                timeout=5.0,
            )
            resp.raise_for_status()
            brutos: list[dict[str, Any]] = resp.json()
        except (httpx.HTTPError, ValueError):
            logger.warning("log-service não respondeu aos eventos do painel", exc_info=True)
            raise DependenciaIndisponivel("A auditoria está indisponível agora.") from None
        return [_evento_de(bruto) for bruto in brutos]
