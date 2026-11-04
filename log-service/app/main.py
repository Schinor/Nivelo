import json
import secrets
import uuid
from typing import Any

import redis.asyncio as redis
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from prometheus_client import CollectorRegistry
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

from app.config import settings

app = FastAPI(
    title="Nivelo — Auditoria",
    description="Serviço interno: recebe eventos de auditoria e os grava em um Redis Stream.",
    version="1.0.0",
)

r = redis.from_url(settings.REDIS_URL, decode_responses=True)
STREAM = "audit:events"
# Marca de "já gravado" de cada event_id: o relay da API entrega pelo menos uma vez
VISTO = "audit:evento:{}"
VISTO_TTL_S = 30 * 24 * 3600
# Quantas entradas, no máximo, a listagem filtrada percorre (das mais recentes para trás)
VARREDURA_MAXIMA = 20_000


class Evento(BaseModel):
    usuario_id: int | None = None
    acao: str
    origem: str
    timestamp: str
    recurso: str | None = None
    detalhes: str | None = None
    ip: str | None = None
    request_id: str | None = None
    empresa_id: str | None = None


class EventoDeNegocio(BaseModel):
    """Formato único dos eventos de negócio (outbox da API, Parte A.4 do roteiro)."""

    event_id: uuid.UUID
    tipo: str = Field(min_length=3, max_length=100)
    empresa_id: str
    ator_id: int | None = None
    ator_papel: str | None = None
    recurso: str
    recurso_id: str
    ocorrido_em: str
    request_id: str | None = None
    dados: dict[str, Any] = Field(default_factory=dict)


class LoteDeEventos(BaseModel):
    eventos: list[EventoDeNegocio] = Field(max_length=500)


def _campos_do_stream(ev: EventoDeNegocio) -> dict[str, str]:
    """Achata o evento no stream. `acao`, `usuario_id`, `timestamp` e `recurso` mantêm a
    listagem antiga funcionando; `obra_id` fica no topo para o histórico da obra filtrar."""
    obra_id = ev.recurso_id if ev.recurso == "obra" else ev.dados.get("obra_id")
    campos = {
        "event_id": str(ev.event_id),
        "acao": ev.tipo,
        "tipo": ev.tipo,
        "origem": "api",
        "timestamp": ev.ocorrido_em,
        "usuario_id": ev.ator_id,
        "ator_papel": ev.ator_papel,
        "empresa_id": ev.empresa_id,
        "recurso": f"{ev.recurso}:{ev.recurso_id}",
        "recurso_id": ev.recurso_id,
        "obra_id": obra_id,
        "request_id": ev.request_id,
        "dados": json.dumps(ev.dados, ensure_ascii=False, separators=(",", ":")),
    }
    return {k: str(v) for k, v in campos.items() if v is not None}


def checar_token(token: str) -> None:
    if not secrets.compare_digest(token, settings.LOG_INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="token interno inválido")


@app.post("/eventos", status_code=202)
async def registrar(ev: Evento, x_internal_token: str = Header(...)):
    checar_token(x_internal_token)
    campos = {k: str(v) for k, v in ev.model_dump().items() if v is not None}
    await r.xadd(STREAM, campos, maxlen=100_000, approximate=True)
    return {"ok": True}


@app.post("/eventos/negocio", status_code=202)
async def registrar_negocio(lote: LoteDeEventos, x_internal_token: str = Header(...)):
    """Lote do relay da outbox. Idempotente: `event_id` já gravado é ignorado."""
    checar_token(x_internal_token)
    gravados = duplicados = 0
    for ev in lote.eventos:
        chave = VISTO.format(ev.event_id)
        if not await r.set(chave, "1", nx=True, ex=VISTO_TTL_S):
            duplicados += 1
            continue
        try:
            await r.xadd(STREAM, _campos_do_stream(ev), maxlen=100_000, approximate=True)
        except Exception:
            # Sem a marca, o relay reenvia o lote e o evento entra na próxima vez
            await r.delete(chave)
            raise HTTPException(status_code=503, detail="não foi possível gravar o evento") from None
        gravados += 1
    return {"gravados": gravados, "duplicados": duplicados}


def _confere(campos: dict[str, str], filtros: dict[str, str]) -> bool:
    return all(campos.get(k) == v for k, v in filtros.items())


@app.get("/eventos")
async def listar(
    limit: int = Query(50, ge=1, le=500),
    empresa_id: str | None = Query(None, description="Só os eventos desta empresa"),
    obra_id: str | None = Query(None, description="Só os eventos desta obra (e dos diários e fotos dela)"),
    x_internal_token: str = Header(...),
):
    checar_token(x_internal_token)
    filtros = {k: v for k, v in {"empresa_id": empresa_id, "obra_id": obra_id}.items() if v}
    if not filtros:
        itens = await r.xrevrange(STREAM, count=limit)  # mais recentes primeiro
        return [{"id": i, **campos} for i, campos in itens]
    # Com filtro, percorre o stream do mais recente para trás, em blocos, até achar `limit`
    achados: list[dict[str, str]] = []
    fim, vistos = "+", 0
    while len(achados) < limit and vistos < VARREDURA_MAXIMA:
        bloco = await r.xrevrange(STREAM, max=fim, count=500)
        if fim != "+" and bloco and bloco[0][0] == fim:
            bloco = bloco[1:]  # o limite superior do XREVRANGE é inclusivo
        if not bloco:
            break
        vistos += len(bloco)
        achados.extend({"id": i, **campos} for i, campos in bloco if _confere(campos, filtros))
        fim = bloco[-1][0]
    return achados[:limit]


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
