"""Adaptador do relay da outbox para o log-service (ADR 012).

O log-service é o dono do Redis Stream de auditoria: a API entrega o lote por HTTP, na rede
interna, com o mesmo token interno já usado pelos eventos técnicos. O log-service grava cada
evento no stream e ignora `event_id` repetido.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings

TIMEOUT_S = 5.0


class PublicadorNoLogService:
    def __init__(self, url: str | None = None, token: str | None = None) -> None:
        self._url = f"{(url or settings.LOG_SERVICE_URL).rstrip('/')}/eventos/negocio"
        self._token = settings.LOG_INTERNAL_TOKEN if token is None else token

    def __call__(self, eventos: list[dict[str, Any]]) -> None:
        resp = httpx.post(
            self._url, json={"eventos": eventos}, headers={"X-Internal-Token": self._token}, timeout=TIMEOUT_S
        )
        resp.raise_for_status()
