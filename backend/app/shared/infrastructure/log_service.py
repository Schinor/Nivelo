"""Adaptador do relay da outbox para o log-service (ADR 012).

O log-service é o dono do Redis Stream de auditoria: a API entrega o lote por HTTP, na rede
interna, com o mesmo token interno (`X-Internal-Token` = `LOG_INTERNAL_TOKEN`) já usado pelos
eventos técnicos. O log-service grava cada evento no stream e ignora `event_id` repetido.

- 2xx: entregue.
- 400, 413 ou 422: o conteúdo foi recusado (`EntregaRecusada`); o relay separa os eventos.
- Qualquer outra coisa (queda, 5xx, 401 de token errado): o lote inteiro espera o backoff.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.shared.infrastructure.outbox import EntregaRecusada

TIMEOUT_S = 5.0
CONTEUDO_RECUSADO = frozenset({400, 413, 422})


class PublicadorNoLogService:
    def __init__(self, url: str | None = None, token: str | None = None) -> None:
        self._url = f"{(url or settings.LOG_SERVICE_URL).rstrip('/')}/eventos/negocio"
        self._token = settings.LOG_INTERNAL_TOKEN if token is None else token

    def __call__(self, eventos: list[dict[str, Any]]) -> None:
        resp = httpx.post(
            self._url, json={"eventos": eventos}, headers={"X-Internal-Token": self._token}, timeout=TIMEOUT_S
        )
        if resp.status_code in CONTEUDO_RECUSADO:
            raise EntregaRecusada(f"log-service recusou o lote (HTTP {resp.status_code}): {resp.text[:200]}")
        resp.raise_for_status()
