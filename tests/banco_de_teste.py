"""Banco dos testes da API: SQLite em memória por padrão, ou o MariaDB de verdade.

Com `NIVELO_TESTES_NO_MARIADB=1` e `MARIADB_URL` definidos, os testes marcados com `mariadb`
(tenancy, política de plano e constraints) rodam num banco criado pelas migrações do Alembic,
com as mesmas FKs compostas, CHECKs, índices únicos, travas e isolamento da produção. O banco
nasce uma vez por execução e é esvaziado antes de cada teste.

No CI: `NIVELO_TESTES_NO_MARIADB=1 pytest -m mariadb` (ver .github/workflows/ci-cd.yml).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

PASTA_DA_API = Path(__file__).resolve().parents[1] / "backend"
BANCO = "nivelo_testes_api"

_motor_mariadb: Engine | None = None


def no_mariadb() -> bool:
    return os.environ.get("NIVELO_TESTES_NO_MARIADB") == "1" and bool(os.environ.get("MARIADB_URL"))


def _criar_mariadb() -> Engine:
    url = os.environ["MARIADB_URL"].rstrip("/")
    with create_engine(url).begin() as c:
        c.exec_driver_sql(f"DROP DATABASE IF EXISTS {BANCO}")
        c.exec_driver_sql(f"CREATE DATABASE {BANCO} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    env = {**os.environ, "DATABASE_URL": f"{url}/{BANCO}", "SECRET_KEY": "teste"}
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=PASTA_DA_API, env=env, capture_output=True, text=True
    )
    if r.returncode != 0:
        raise RuntimeError(f"alembic upgrade head falhou no MariaDB:\n{r.stderr[-2000:]}")
    return create_engine(f"{url}/{BANCO}", pool_pre_ping=True)


def _esvaziar(motor: Engine) -> None:
    """Apaga as linhas de todas as tabelas do banco (não só as que têm modelo ORM), menos a
    versão do Alembic."""
    with motor.begin() as c:
        tabelas = c.execute(
            text(
                "SELECT table_name FROM information_schema.tables"
                " WHERE table_schema = DATABASE() AND table_name NOT LIKE 'alembic_version%'"
            )
        ).scalars()
        c.exec_driver_sql("SET FOREIGN_KEY_CHECKS = 0")
        for tabela in list(tabelas):
            c.exec_driver_sql(f"DELETE FROM `{tabela}`")
        c.exec_driver_sql("SET FOREIGN_KEY_CHECKS = 1")


def motor_da_api(metadata) -> Engine:
    """Motor limpo para um teste. `metadata` é o `Base.metadata` da API já importada."""
    global _motor_mariadb
    if no_mariadb():
        if _motor_mariadb is None:
            _motor_mariadb = _criar_mariadb()
        _esvaziar(_motor_mariadb)
        return _motor_mariadb
    motor = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    metadata.create_all(bind=motor)
    return motor
