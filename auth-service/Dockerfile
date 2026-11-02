FROM python:3.12-slim

WORKDIR /app

# Dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libmariadb-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código do serviço de autenticação
COPY . .

# Expõe a porta interna (configurada via ENV PORT, padrão 8001)
EXPOSE ${PORT:-8001}

# Migrações antes de aceitar tráfego: se o alembic falhar, o container não sobe
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
