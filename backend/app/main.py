import sys
import os

# Garante que o diretório raiz do backend esteja no sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import asyncio
import logging

import httpx
from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from prometheus_client import CollectorRegistry
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.core.config import settings
from app.core.database import Base, engine
from app.dependencies import auditar_acesso_negado
import app.models  # noqa: F401 — força o registro dos models no metadata

from app.routes.auth import router as auth_router
from app.routes.logs import router as logs_router
from app.routes.observability_proxy import router as observability_router
from app.routes.perfis import router as perfis_router
from app.routes.premium import router as premium_router, webhook_router as stripe_webhook_router
from app.routes.storage_proxy import router as storage_router

# Loggers "nivelo.api.*" em INFO no stdout (ex.: event.id/tipo/usuario_id do webhook do Stripe).
# Sem isso só WARNING+ aparece, pelo handler de último recurso do Python.
_log_handler = logging.StreamHandler()
_log_handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s - %(message)s"))
logging.getLogger("nivelo.api").addHandler(_log_handler)
logging.getLogger("nivelo.api").setLevel(logging.INFO)

# Cria as tabelas (idempotente se já existirem)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Nivelo API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas da API
app.include_router(auth_router)
app.include_router(logs_router)
app.include_router(perfis_router)
app.include_router(premium_router)
app.include_router(stripe_webhook_router)
# Precisam vir antes do fallback da SPA (abaixo) para /grafana, /prometheus e /storage não caírem no index.html.
app.include_router(observability_router)
app.include_router(storage_router)



@app.exception_handler(StarletteHTTPException)
async def auditar_403(request: Request, exc: StarletteHTTPException):
    """Ponto central da auditoria de negação: TODA resposta 403 gera 'acesso_negado'."""
    if exc.status_code == status.HTTP_403_FORBIDDEN:
        await auditar_acesso_negado(request)
    return await http_exception_handler(request, exc)


def _banco_ok() -> bool:
    try:
        with engine.connect() as conn:
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


@app.get("/health", include_in_schema=False)
async def health():
    """Readiness: 200 só se banco, auth-service e object storage responderem; senão 503."""
    banco, auth, storage = await asyncio.gather(
        asyncio.to_thread(_banco_ok),
        _http_ok(f"{settings.AUTH_SERVICE_URL.rstrip('/')}/health"),
        # Sem credenciais o Garage responde 403: o que importa aqui é ele estar de pé
        _http_ok(settings.STORAGE_ENDPOINT, aceitar_qualquer_resposta=True),
    )
    corpo = {
        "db": "up" if banco else "down",
        "auth_service": "up" if auth else "down",
        "storage": "up" if storage else "down",
    }
    if not (banco and auth and storage):
        return JSONResponse(status_code=503, content={"status": "unhealthy", **corpo})
    return {"status": "healthy", **corpo}


# Registry próprio evita colisão de métricas quando mais de um app é importado no mesmo processo.
# Registrado antes do fallback da SPA para que /metrics não caia no index.html.
Instrumentator(registry=CollectorRegistry(), excluded_handlers=["/metrics", "/health"]).instrument(app).expose(
    app, include_in_schema=False
)

# Serve o frontend Angular (SPA fallback para suporte a HTML5 pushState routing)
STATIC_DIR = os.path.join(BASE_DIR, "static")
if not os.path.isdir(STATIC_DIR):
    STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

if os.path.isdir(STATIC_DIR):
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Se for um arquivo estático existente (JS, CSS, PNG, ICO, etc.)
        target = os.path.join(STATIC_DIR, full_path)
        if full_path and os.path.isfile(target):
            return FileResponse(target)

        # Para qualquer rota do cliente (ex: /reset-password, /login), serve o index.html
        index_file = os.path.join(STATIC_DIR, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        return FileResponse(target)
