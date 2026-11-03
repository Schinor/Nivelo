import logging
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CollectorRegistry
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

import app.models  # força o registro dos models no metadata
from app.core.admin import garantir_admin
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.routes.auth import router as auth_router
from app.routes.convites import router as convites_router
from app.routes.identidade import router as identidade_router
from app.routes.premium import router as premium_router
from app.routes.users import router as users_router

# Loggers "auth-service.*" em INFO no stdout (ex.: eventos do Stripe aplicados).
# Sem isso só WARNING+ aparece, pelo handler de último recurso do Python.
_log_handler = logging.StreamHandler()
_log_handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s - %(message)s"))
logging.getLogger("auth-service").addHandler(_log_handler)
logging.getLogger("auth-service").setLevel(logging.INFO)


def init_db():
    # O esquema vem das migrações Alembic (alembic upgrade head roda antes do uvicorn; ver Dockerfile).
    # Aqui só garante o admin da plataforma.
    try:
        db = SessionLocal()
        garantir_admin(db, settings.ADMIN_EMAIL, settings.ADMIN_SENHA_INICIAL)
        db.close()
    except Exception as e:
        print(f"[auth-service] Aviso ao preparar o banco: {e}")


init_db()

app = FastAPI(
    title="Nivelo — Identidade e Acesso",
    description="Serviço interno de identidade: contas, empresas, vínculos, convites, senha e JWT.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/health",
    responses={
        503: {
            "description": "Banco de dados inacessível",
            "content": {
                "application/json": {
                    "example": {"status": "unhealthy", "db": "down", "service": "auth-service", "version": "2.0.0"}
                }
            },
        }
    },
)
def health():
    """Readiness: só responde 200 se o banco de dados estiver acessível."""
    info = {"service": "auth-service", "version": "2.0.0"}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "db": "down", **info})
    return {"status": "healthy", "db": "up", **info}


# Registry próprio evita colisão de métricas quando mais de um app é importado no mesmo processo
Instrumentator(registry=CollectorRegistry(), excluded_handlers=["/metrics", "/health"]).instrument(app).expose(
    app, include_in_schema=False
)


# Rotas
app.include_router(auth_router)
app.include_router(identidade_router)
app.include_router(convites_router)
app.include_router(users_router)
app.include_router(premium_router)
