import os
import sys

# Garante que o diretório raiz do backend esteja no sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CollectorRegistry
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.exceptions import HTTPException as StarletteHTTPException

import app.models  # noqa: F401 — força o registro dos models no metadata
from app.dependencies import auditar_acesso_negado
from app.obras.api.rotas import router as obras_router
from app.routes.auth import router as auth_router
from app.routes.logs import router as logs_router
from app.routes.observability_proxy import router as observability_router
from app.routes.perfis import router as perfis_router
from app.routes.premium import router as premium_router
from app.routes.premium import webhook_router as stripe_webhook_router
from app.routes.storage_proxy import router as storage_router
from app.shared.api.health import router as health_router
from app.shared.api.problem_details import registrar_handlers
from app.shared.api.request_id import RequestIdMiddleware
from app.shared.api.spa import registrar_spa

# Loggers "nivelo.api.*" em INFO no stdout (ex.: event.id/tipo/usuario_id do webhook do Stripe).
# Sem isso só WARNING+ aparece, pelo handler de último recurso do Python.
_log_handler = logging.StreamHandler()
_log_handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s - %(message)s"))
logging.getLogger("nivelo.api").addHandler(_log_handler)
logging.getLogger("nivelo.api").setLevel(logging.INFO)

# O esquema vem das migrações Alembic (alembic upgrade head roda antes do uvicorn; ver Dockerfile)

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
    expose_headers=["X-Request-ID"],
)
# Por último = mais externo: o Request ID já existe quando qualquer outro middleware ou handler roda
app.add_middleware(RequestIdMiddleware)

# Rotas da API
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(obras_router)
app.include_router(logs_router)
app.include_router(perfis_router)
app.include_router(premium_router)
app.include_router(stripe_webhook_router)
# Precisam vir antes do fallback da SPA (abaixo) para /grafana, /prometheus e /storage não caírem no index.html.
app.include_router(observability_router)
app.include_router(storage_router)


async def auditar_403(request: Request, exc: StarletteHTTPException) -> None:
    """Ponto central da auditoria de negação: TODA resposta 403 gera 'acesso.negado'."""
    if exc.status_code == status.HTTP_403_FORBIDDEN:
        await auditar_acesso_negado(request)


registrar_handlers(app, antes_de_http=auditar_403)


# Registry próprio evita colisão de métricas quando mais de um app é importado no mesmo processo.
# Registrado antes do fallback da SPA para que /metrics não caia no index.html.
Instrumentator(
    registry=CollectorRegistry(),
    excluded_handlers=["/metrics", "/health", "/health/live", "/health/ready", "/health/deps"],
).instrument(app).expose(app, include_in_schema=False)

# Serve o frontend Angular (SPA fallback para suporte a HTML5 pushState routing)
STATIC_DIR = os.path.join(BASE_DIR, "static")
if not os.path.isdir(STATIC_DIR):
    STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

if os.path.isdir(STATIC_DIR):
    registrar_spa(app, STATIC_DIR)
