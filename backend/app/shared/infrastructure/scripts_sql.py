"""Aplica arquivos .sql de db/ (esquema exportado e seed) num banco, comando por comando.

Os arquivos são gerados pelo Alembic ou escritos à mão com uma regra simples: cada comando
termina com `;` no fim da linha. Ponto e vírgula dentro de texto só é aceito no meio da
linha. Linhas de comentário (`--`) são ignoradas.

Uso: python -m app.shared.infrastructure.scripts_sql <DATABASE_URL> <arquivo.sql> [...]
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

_FIM_DE_COMANDO = re.compile(r";[ \t]*(?:\r?\n|$)")


def dividir(script: str) -> list[str]:
    """Separa o script em comandos, sem os comentários de linha inteira."""
    sem_comentarios = "\n".join(linha for linha in script.splitlines() if not linha.lstrip().startswith("--"))
    return [cmd.strip() for cmd in _FIM_DE_COMANDO.split(sem_comentarios) if cmd.strip()]


def aplicar(conn: Connection, arquivos: Iterable[Path]) -> int:
    """Executa os comandos de cada arquivo, na ordem. Devolve quantos comandos rodaram."""
    total = 0
    for arquivo in arquivos:
        for comando in dividir(arquivo.read_text(encoding="utf-8")):
            # exec_driver_sql não interpreta ":nome" como parâmetro (o SQL pode ter "dd:mm")
            conn.exec_driver_sql(comando)
            total += 1
    return total


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    engine = create_engine(argv[0])
    with engine.begin() as conn:
        total = aplicar(conn, [Path(a) for a in argv[1:]])
        conn.execute(text("SELECT 1"))
    print(f"{total} comandos aplicados de {len(argv) - 1} arquivo(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
