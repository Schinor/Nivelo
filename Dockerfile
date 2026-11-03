# ── Stage 1: Build do Angular ─────────────────────────────────────────────────
FROM node:22-alpine AS frontend-builder

WORKDIR /frontend

# Instala dependências
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps

# Copia o código e faz o build de produção
COPY frontend/ ./
RUN npx ng build --configuration production

# ── Stage 2: Backend Python (FastAPI) ─────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libmariadb-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código do backend e os scripts SQL (o seed de desenvolvimento é lido de /app/db)
COPY backend/ .
COPY db/ ./db/

# Copia os arquivos estáticos do Angular para o diretório que o FastAPI vai servir
COPY --from=frontend-builder /frontend/dist/frontend/browser ./static

# Expõe a porta (configurada via ENV PORT)
EXPOSE ${PORT:-8000}

# Migrações antes de aceitar tráfego: se o alembic falhar, o container não sobe
# O seed só age com SEED=true (dados de desenvolvimento; nunca em produção)
CMD ["sh", "-c", "alembic upgrade head && python -m app.shared.infrastructure.seed && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
