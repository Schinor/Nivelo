"""Health checks.

- `/health/live`: o processo responde. Não consulta nada (reiniciar não resolve dependência fora).
- `/health/ready`: pronto para tráfego. 200 só se banco, auth-service, auditoria (log-service,
  que checa o Redis) e object storage responderem; senão 503 com o que caiu.
- `/health`: mesmo que o ready, mantido para o healthcheck do compose e o CI.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core import database
from app.core.config import settings

router = APIRouter(tags=["health"], include_in_schema=False)


def _banco_ok() -> bool:
    try:
        with database.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _http_ok(url: str, aceitar_qualquer_resposta: bool = False) -> bool:
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            resp = await client.get(url)
    except httpx.HTTPError:
        return False
    return resp.status_code < 500 if aceitar_qualquer_resposta else resp.status_code == 200


async def checar_dependencias() -> dict[str, bool]:
    banco, auth, auditoria, storage = await asyncio.gather(
        asyncio.to_thread(_banco_ok),
        _http_ok(f"{settings.AUTH_SERVICE_URL.rstrip('/')}/health"),
        _http_ok(f"{settings.LOG_SERVICE_URL.rstrip('/')}/health"),
        # Sem credenciais o Garage responde 403: o que importa aqui é ele estar de pé
        _http_ok(settings.STORAGE_ENDPOINT, aceitar_qualquer_resposta=True),
    )
    return {"db": banco, "auth_service": auth, "auditoria": auditoria, "storage": storage}


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "live"}


@router.get("/health/ready")
@router.get("/health")
async def ready() -> Any:
    estado = await checar_dependencias()
    corpo = {nome: "up" if ok else "down" for nome, ok in estado.items()}
    if not all(estado.values()):
        return JSONResponse(status_code=503, content={"status": "unhealthy", **corpo})
    return {"status": "healthy", **corpo}
