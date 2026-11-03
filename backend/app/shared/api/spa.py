"""Entrega do front (SPA Angular) pela própria API.

Regras:
- arquivo estático existente dentro do diretório do build → o arquivo;
- caminho que tenta sair do diretório (`..`, inclusive codificado) → 404, nunca o arquivo;
- caminho da API (`api/...`) que não casou com nenhuma rota → 404 em Problem Details,
  não o index.html (o cliente da API não deve receber HTML);
- qualquer outro caminho → index.html (rotas do Angular, como /login e /obras).
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def resolver_caminho(static_dir: str, caminho: str) -> str | None:
    """Caminho absoluto dentro de `static_dir`, ou None se o pedido tenta sair dele."""
    raiz = os.path.realpath(static_dir)
    alvo = os.path.realpath(os.path.join(raiz, caminho))
    return alvo if os.path.commonpath([raiz, alvo]) == raiz else None


def registrar_spa(app: FastAPI, static_dir: str) -> None:
    """Registra a rota coringa da SPA. Deve ser a última rota do app."""
    index = os.path.join(static_dir, "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def servir_spa(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Rota da API não encontrada")

        alvo = resolver_caminho(static_dir, full_path)
        if alvo is None:
            raise HTTPException(status_code=404, detail="Não encontrado")
        if full_path and os.path.isfile(alvo):
            return FileResponse(alvo)
        if os.path.isfile(index):
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Não encontrado")
