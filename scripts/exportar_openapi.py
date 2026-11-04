"""Exporta o OpenAPI da API para frontend/openapi.json, de onde o front gera o cliente
(`npm run api:gen`, com ng-openapi-gen). Não sobe servidor nem banco.

Uso: .venv/bin/python scripts/exportar_openapi.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "so-para-exportar-o-openapi")
sys.path.insert(0, str(RAIZ / "backend"))

from app.main import app  # noqa: E402

destino = RAIZ / "frontend" / "openapi.json"
destino.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"OpenAPI gravado em {destino.relative_to(RAIZ)} ({len(app.openapi()['paths'])} rotas)")
