"""Health checks.

- `/health/live`: o processo responde. Não consulta nada (reiniciar não resolve dependência fora).
- `/health/ready`: pronto para tráfego. 200 só se as dependências **obrigatórias** (banco,
  auth-service e object storage) responderem; senão 503 com o que caiu.
- `/health`: mesmo que o ready, mantido para o healthcheck do compose e o CI.
- `/health/deps`: só informativo, sempre 200. Mostra todas as dependências, inclusive as
  opcionais. A auditoria (log-service, que checa o Redis) é opcional de propósito: com a
  outbox (ADR 003) a API grava o evento no banco e segue funcionando sem o log-service.
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


OBRIGATORIAS = ("db", "auth_service", "storage")
OPCIONAIS = ("auditoria",)


async def checar_dependencias(*, incluir_opcionais: bool = False) -> dict[str, bool]:
    verificacoes = {
        "db": asyncio.to_thread(_banco_ok),
        "auth_service": _http_ok(f"{settings.AUTH_SERVICE_URL.rstrip('/')}/health"),
        # Sem credenciais o Garage responde 403: o que importa aqui é ele estar de pé
        "storage": _http_ok(settings.STORAGE_ENDPOINT, aceitar_qualquer_resposta=True),
    }
    if incluir_opcionais:
        verificacoes["auditoria"] = _http_ok(f"{settings.LOG_SERVICE_URL.rstrip('/')}/health")
    resultados = await asyncio.gather(*verificacoes.values())
    return dict(zip(verificacoes, resultados, strict=True))


def _rotular(estado: dict[str, bool]) -> dict[str, str]:
    return {nome: "up" if ok else "down" for nome, ok in estado.items()}


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "live"}


@router.get("/health/ready")
@router.get("/health")
async def ready() -> Any:
    estado = await checar_dependencias()
    if not all(estado.values()):
        return JSONResponse(status_code=503, content={"status": "unhealthy", **_rotular(estado)})
    return {"status": "healthy", **_rotular(estado)}


@router.get("/health/deps")
async def deps() -> dict[str, Any]:
    estado = await checar_dependencias(incluir_opcionais=True)
    return {
        "obrigatorias": _rotular({k: estado[k] for k in OBRIGATORIAS}),
        "opcionais": _rotular({k: estado[k] for k in OPCIONAIS}),
        "pronto": all(estado[k] for k in OBRIGATORIAS),
    }
