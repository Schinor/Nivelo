"""Migrações do Alembic dos dois serviços, num SQLite temporário (o MariaDB roda no CI).

O Alembic roda em subprocesso, porque a API e o auth-service têm, cada um, um pacote `app`.
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
PASTAS = {"auth": RAIZ / "auth-service", "api": RAIZ / "backend"}


def alembic(servico: str, banco: Path, *args: str) -> str:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{banco}", "SECRET_KEY": "teste"}
    resultado = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=PASTAS[servico],
        env=env,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr[-2000:]
    return resultado.stderr + resultado.stdout


def conectar(banco: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(banco)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def tabelas(banco: Path) -> set[str]:
    with conectar(banco) as conn:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


@pytest.fixture
def banco(tmp_path: Path) -> Path:
    return tmp_path / "nivelo.db"


# ── Identidade (auth-service) ────────────────────────────────────────────────


def test_identidade_cria_empresas_vinculos_convites_e_admin_plataforma(banco):
    alembic("auth", banco, "upgrade", "head")

    assert {"empresas", "vinculos", "convites"} <= tabelas(banco)
    with conectar(banco) as conn:
        colunas = {r[1] for r in conn.execute("PRAGMA table_info(usuarios)")}
    # Expansão (ADR 009): a coluna nova entra e a antiga ainda fica
    assert {"admin_plataforma", "role"} <= colunas


def test_identidade_converte_admin_e_e_idempotente(banco):
    alembic("auth", banco, "upgrade", "004_premium_stripe")
    with conectar(banco) as conn:
        conn.execute(
            "INSERT INTO usuarios (nome, email, senha_hash, role) VALUES "
            "('Admin', 'admin@nivelo.app', 'h', 'admin'), ('Ana', 'ana@nivelo.app', 'h', 'cliente')"
        )

    alembic("auth", banco, "upgrade", "head")
    saida = alembic("auth", banco, "upgrade", "head")
    assert "Running upgrade" not in saida

    with conectar(banco) as conn:
        admins = dict(conn.execute("SELECT email, admin_plataforma FROM usuarios"))
    assert admins == {"admin@nivelo.app": 1, "ana@nivelo.app": 0}


def test_identidade_downgrade_e_upgrade_de_novo(banco):
    alembic("auth", banco, "upgrade", "head")
    alembic("auth", banco, "downgrade", "-1")
    assert not {"empresas", "vinculos", "convites"} & tabelas(banco)
    alembic("auth", banco, "upgrade", "head")
    assert {"empresas", "vinculos", "convites"} <= tabelas(banco)


def test_vinculo_exige_usuario_e_empresa_existentes_e_papel_valido(banco):
    alembic("auth", banco, "upgrade", "head")
    empresa = "0190f3a0-0000-7000-8000-000000000001"
    with conectar(banco) as conn:
        conn.execute("INSERT INTO usuarios (nome, email, senha_hash, role) VALUES ('Ana', 'a@x.com', 'h', 'cliente')")
        conn.execute("INSERT INTO empresas (id, nome, tipo_pessoa) VALUES (?, 'Rocha Reformas', 'PJ')", (empresa,))
        conn.execute("INSERT INTO vinculos (usuario_id, empresa_id, papel) VALUES (1, ?, 'dono')", (empresa,))

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO vinculos (usuario_id, empresa_id, papel) VALUES (1, ?, 'dono')", (empresa,)
            )  # mesmo usuário na mesma empresa duas vezes
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO vinculos (usuario_id, empresa_id, papel) VALUES (99, ?, 'cliente')", (empresa,)
            )  # usuário inexistente


def test_documento_da_empresa_e_opcional_e_unico_quando_informado(banco):
    alembic("auth", banco, "upgrade", "head")
    with conectar(banco) as conn:
        conn.execute("INSERT INTO empresas (id, nome, tipo_pessoa) VALUES ('a', 'Autônomo 1', 'PF')")
        conn.execute("INSERT INTO empresas (id, nome, tipo_pessoa) VALUES ('b', 'Autônomo 2', 'PF')")
        conn.execute(
            "INSERT INTO empresas (id, nome, tipo_pessoa, documento) VALUES ('c', 'Construtora', 'PJ', '12345678000190')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO empresas (id, nome, tipo_pessoa, documento) VALUES ('d', 'Cópia', 'PJ', '12345678000190')"
            )
