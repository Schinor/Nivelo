import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import Request

from app.core.config import settings
from app.shared.api.request_id import obter_request_id

logger = logging.getLogger("nivelo.api.log_client")


async def registrar(
    acao: str,
    request: Optional[Request] = None,
    usuario_id: Optional[int] = None,
    recurso: Optional[str] = None,
    detalhes: Optional[str] = None,
) -> None:
    """Envia um evento de auditoria ao log-service.

    Auditoria não pode derrubar funcionalidade: qualquer falha vira apenas um warning.
    """
    payload = {
        "usuario_id": usuario_id,
        "acao": acao,
        "origem": "api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "recurso": recurso,
        "detalhes": detalhes,
        "ip": request.client.host if request and request.client else None,
        "request_id": obter_request_id(),
    }
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.post(
                f"{settings.LOG_SERVICE_URL.rstrip('/')}/eventos",
                json=payload,
                headers={"X-Internal-Token": settings.LOG_INTERNAL_TOKEN},
            )
            if resp.status_code >= 400:
                logger.warning("log-service recusou o evento %s (HTTP %s)", acao, resp.status_code)
    except Exception:
        logger.warning("log-service indisponível; evento %s perdido", acao)
