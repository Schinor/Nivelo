"""Adaptador da porta `HistoricoDaObra`: consulta os eventos da obra no log-service.

O log-service guarda os eventos de negócio que o relay da outbox entregou (ADR 012). O filtro
vai sempre com a empresa do token, então uma obra de outra empresa não traz nada mesmo que o
id seja adivinhado (e a rota já respondeu 404 antes de chegar aqui).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.obras.domain.ids import ObraId
from app.shared.application.contexto import TenantContext
from app.shared.application.erros import DependenciaIndisponivel

logger = logging.getLogger("nivelo.api.historico")


def _evento(bruto: dict[str, Any]) -> dict[str, object]:
    try:
        dados = json.loads(bruto.get("dados") or "{}")
    except ValueError:
        dados = {}
    usuario = bruto.get("usuario_id")
    return {
        "event_id": bruto.get("event_id"),
        "tipo": bruto.get("tipo") or bruto.get("acao"),
        "ator_id": int(usuario) if usuario and str(usuario).isdigit() else None,
        "ator_papel": bruto.get("ator_papel"),
        "recurso": str(bruto.get("recurso", "")).split(":", 1)[0] or None,
        "recurso_id": bruto.get("recurso_id"),
        "ocorrido_em": bruto.get("timestamp"),
        "request_id": bruto.get("request_id"),
        "dados": dados,
    }


class HistoricoViaLogService:
    def eventos(self, ctx: TenantContext, obra_id: ObraId, limite: int) -> list[dict[str, object]]:
        try:
            resp = httpx.get(
                f"{settings.LOG_SERVICE_URL.rstrip('/')}/eventos",
                params={"empresa_id": str(ctx.empresa_id), "obra_id": str(obra_id), "limit": limite},
                headers={"X-Internal-Token": settings.LOG_INTERNAL_TOKEN},
                timeout=5.0,
            )
            resp.raise_for_status()
            brutos: list[dict[str, Any]] = resp.json()
        except (httpx.HTTPError, ValueError):
            logger.warning("log-service não respondeu à consulta do histórico", exc_info=True)
            raise DependenciaIndisponivel("O histórico da obra está indisponível agora. Tente de novo.") from None
        # Defesa em profundidade: descarta o que não for da empresa do token
        return [_evento(b) for b in brutos if b.get("empresa_id") == str(ctx.empresa_id)]
