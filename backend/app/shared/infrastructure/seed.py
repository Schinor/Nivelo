"""Seed de desenvolvimento: aplica db/900_seed_dev.sql quando SEED=true.

Roda no boot da API, depois das migrações (ver Dockerfile). Sem SEED=true não faz nada.
O seed é idempotente (INSERT IGNORE), então reiniciar o container não duplica dados.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from sqlalchemy import create_engine

from app.shared.infrastructure.scripts_sql import aplicar

logger = logging.getLogger("nivelo.api.seed")

ARQUIVO = "900_seed_dev.sql"
VERDADEIRO = {"1", "true", "sim", "yes", "on"}


def seed_ligado(valor: str | None) -> bool:
    return (valor or "").strip().lower() in VERDADEIRO


def localizar_seed(de: Path | None = None) -> Path:
    """Procura db/900_seed_dev.sql na imagem (/app/db) ou no repositório (raiz/db)."""
    aqui = (de or Path(__file__)).resolve()
    for pasta in aqui.parents:
        candidato = pasta / "db" / ARQUIVO
        if candidato.is_file():
            return candidato
    raise FileNotFoundError(f"db/{ARQUIVO} não encontrado acima de {aqui}")


def executar(database_url: str, seed: str | None) -> int:
    """Aplica o seed se `seed` estiver ligado. Devolve quantos comandos rodaram (0 se desligado)."""
    if not seed_ligado(seed):
        return 0
    arquivo = localizar_seed()
    engine = create_engine(database_url)
    with engine.begin() as conn:
        total = aplicar(conn, [arquivo])
    logger.warning("SEED=true: %s comandos de %s aplicados (dados de desenvolvimento)", total, arquivo.name)
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    executar(os.environ["DATABASE_URL"], os.environ.get("SEED"))
