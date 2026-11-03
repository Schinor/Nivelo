from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.api_responses import LOG_SERVICE_INDISPONIVEL, UNAUTHORIZED, forbidden
from app.core.config import settings
from app.dependencies import exigir_admin

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get(
    "",
    responses={**UNAUTHORIZED, **forbidden("admin da plataforma"), **LOG_SERVICE_INDISPONIVEL},
)
async def listar_logs(
    limit: int = Query(50, ge=1, le=500),
    _admin: dict = Depends(exigir_admin),
) -> list[dict[str, Any]]:
    """Trilha de auditoria global (mais recentes primeiro). Só o admin da plataforma."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(
                f"{settings.LOG_SERVICE_URL.rstrip('/')}/eventos",
                params={"limit": limit},
                headers={"X-Internal-Token": settings.LOG_INTERNAL_TOKEN},
            )
        resp.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de auditoria indisponível",
        )
    return resp.json()
