import secrets

import redis.asyncio as redis
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from prometheus_client import CollectorRegistry
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

from app.config import settings

app = FastAPI(
    title="Nivelo — Auditoria",
    description="Serviço interno: recebe eventos de auditoria e os grava em um Redis Stream.",
    version="1.0.0",
)

r = redis.from_url(settings.REDIS_URL, decode_responses=True)
STREAM = "audit:events"


class Evento(BaseModel):
    usuario_id: int | None = None
    acao: str
    origem: str
    timestamp: str
    recurso: str | None = None
    detalhes: str | None = None
    ip: str | None = None
    request_id: str | None = None


def checar_token(token: str) -> None:
    if not secrets.compare_digest(token, settings.LOG_INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="token interno inválido")


@app.post("/eventos", status_code=202)
async def registrar(ev: Evento, x_internal_token: str = Header(...)):
    checar_token(x_internal_token)
    campos = {k: str(v) for k, v in ev.model_dump().items() if v is not None}
    await r.xadd(STREAM, campos, maxlen=100_000, approximate=True)
    return {"ok": True}


@app.get("/eventos")
async def listar(
    limit: int = Query(50, ge=1, le=500),
    x_internal_token: str = Header(...),
):
    checar_token(x_internal_token)
    itens = await r.xrevrange(STREAM, count=limit)  # mais recentes primeiro
    return [{"id": i, **campos} for i, campos in itens]


@app.get("/health")
async def health():
    try:
        await r.ping()
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "redis": "down"},
        )
    return {"status": "healthy", "redis": "up"}


# Registry próprio evita colisão de métricas quando mais de um app é importado no mesmo processo
Instrumentator(registry=CollectorRegistry(), excluded_handlers=["/metrics", "/health"]).instrument(app).expose(
    app, include_in_schema=False
)
