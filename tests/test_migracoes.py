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
    assert "admin_plataforma" in colunas
    # Contração (ADR 009, revisão 006): o papel antigo e o RBAC saíram
    assert not {"role", "role_id"} & colunas
    assert not {"roles", "permissions", "role_permissions", "user_permissions"} & tabelas(banco)


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


def test_contracao_downgrade_recria_estrutura_e_reconstroi_admin(banco):
    alembic("auth", banco, "upgrade", "head")
    with conectar(banco) as conn:
        conn.execute(
            "INSERT INTO usuarios (nome, email, senha_hash, admin_plataforma) VALUES ('Admin', 'adm@x.com', 'h', 1)"
        )
    alembic("auth", banco, "downgrade", "005_identidade")
    assert {"roles", "permissions", "role_permissions", "user_permissions"} <= tabelas(banco)
    with conectar(banco) as conn:
        assert conn.execute("SELECT role FROM usuarios").fetchone()[0] == "admin"
    alembic("auth", banco, "upgrade", "head")
    assert "roles" not in tabelas(banco)


def test_reset_token_vira_hash_e_invalida_os_tokens_antigos(banco):
    alembic("auth", banco, "upgrade", "006_contrai_papel_antigo")
    with conectar(banco) as conn:
        conn.execute("INSERT INTO usuarios (nome, email, senha_hash) VALUES ('Ana', 'ana@x.com', 'h')")
        conn.execute(
            "INSERT INTO reset_tokens (token, usuario_id, expira_em, usado) "
            "VALUES ('token-em-claro', 1, '2999-01-01 00:00:00', 0)"
        )

    alembic("auth", banco, "upgrade", "head")
    with conectar(banco) as conn:
        colunas = {r[1] for r in conn.execute("PRAGMA table_info(reset_tokens)")}
        restantes = conn.execute("SELECT COUNT(*) FROM reset_tokens").fetchone()[0]
    assert "token" not in colunas and "token_hash" in colunas
    assert restantes == 0  # o token em claro emitido antes não vale mais

    alembic("auth", banco, "downgrade", "006_contrai_papel_antigo")
    with conectar(banco) as conn:
        assert "token" in {r[1] for r in conn.execute("PRAGMA table_info(reset_tokens)")}
    alembic("auth", banco, "upgrade", "head")


def test_identidade_downgrade_e_upgrade_de_novo(banco):
    alembic("auth", banco, "upgrade", "head")
    alembic("auth", banco, "downgrade", "005_identidade")
    alembic("auth", banco, "downgrade", "-1")
    assert not {"empresas", "vinculos", "convites"} & tabelas(banco)
    alembic("auth", banco, "upgrade", "head")
    assert {"empresas", "vinculos", "convites"} <= tabelas(banco)


def test_vinculo_exige_usuario_e_empresa_existentes_e_papel_valido(banco):
    alembic("auth", banco, "upgrade", "head")
    empresa = "0190f3a0-0000-7000-8000-000000000001"
    with conectar(banco) as conn:
        conn.execute("INSERT INTO usuarios (nome, email, senha_hash) VALUES ('Ana', 'a@x.com', 'h')")
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


# ── Domínio (API) ────────────────────────────────────────────────────────────

EMPRESA_A = "0190f3a0-0000-7000-8000-00000000000a"
EMPRESA_B = "0190f3a0-0000-7000-8000-00000000000b"
OBRA_A = "0190f3a0-0000-7000-8000-0000000000a1"
DIARIO_A = "0190f3a0-0000-7000-8000-0000000000d1"

TABELAS_DO_DOMINIO = {
    "obras",
    "obra_membros",
    "diarios",
    "ocorrencias",
    "diario_fotos",
    "diario_revisoes",
    "comentarios",
    "assinaturas",
    "stripe_eventos",
    "outbox",
}


def _obra(conn, obra_id=OBRA_A, empresa=EMPRESA_A, inicio="2026-10-01", termino="2026-12-20"):
    conn.execute(
        "INSERT INTO obras (id, empresa_id, nome, logradouro, cidade, uf, cliente_nome, data_inicio,"
        " previsao_termino, criado_por) VALUES (?, ?, 'Casa da Rua 7', 'Rua 7, 100', 'Marília', 'SP',"
        " 'Sr. Jorge', ?, ?, 1)",
        (obra_id, empresa, inicio, termino),
    )


def _diario(conn, diario_id=DIARIO_A, empresa=EMPRESA_A, obra=OBRA_A, data="2026-11-02"):
    conn.execute(
        "INSERT INTO diarios (id, empresa_id, obra_id, data, autor_id) VALUES (?, ?, ?, ?, 1)",
        (diario_id, empresa, obra, data),
    )


@pytest.fixture
def dominio(banco):
    alembic("api", banco, "upgrade", "head")
    return banco


def test_dominio_cria_as_tabelas_com_empresa_id(dominio):
    assert TABELAS_DO_DOMINIO <= tabelas(dominio)
    with conectar(dominio) as conn:
        for tabela in TABELAS_DO_DOMINIO - {"stripe_eventos", "outbox"}:
            colunas = {r[1] for r in conn.execute(f"PRAGMA table_info({tabela})")}
            assert "empresa_id" in colunas, tabela


def test_dominio_tem_tres_ou_mais_tabelas_com_chave_estrangeira(dominio):
    with conectar(dominio) as conn:
        com_fk = {t for t in TABELAS_DO_DOMINIO if conn.execute(f"PRAGMA foreign_key_list({t})").fetchall()}
    assert {"obra_membros", "diarios", "ocorrencias", "diario_fotos", "diario_revisoes", "comentarios"} <= com_fk


# As constraints (FK composta, únicos, CHECKs, cascatas) estão em test_constraints_dominio.py,
# que roda no SQLite e no MariaDB.


def test_backoff_da_outbox_e_foto_apos_publicacao_descem_e_sobem(dominio):
    def colunas(tabela):
        with conectar(dominio) as conn:
            return {r[1] for r in conn.execute(f"PRAGMA table_info({tabela})")}

    assert {"proxima_tentativa_em", "ultimo_erro"} <= colunas("outbox")
    assert "apos_publicacao" in colunas("diario_fotos")
    alembic("api", dominio, "downgrade", "-1")
    assert not {"proxima_tentativa_em", "ultimo_erro"} & colunas("outbox")
    assert "apos_publicacao" not in colunas("diario_fotos")
    alembic("api", dominio, "upgrade", "head")
    assert "apos_publicacao" in colunas("diario_fotos")


def test_dominio_downgrade_e_upgrade_de_novo(dominio):
    alembic("api", dominio, "downgrade", "api_002_remove_catalogo")
    assert not TABELAS_DO_DOMINIO & tabelas(dominio)
    assert "perfis" in tabelas(dominio)
    alembic("api", dominio, "upgrade", "head")
    assert TABELAS_DO_DOMINIO <= tabelas(dominio)
    assert "Running upgrade" not in alembic("api", dominio, "upgrade", "head")


def test_premium_por_usuario_sai_e_o_downgrade_recria_a_estrutura(banco):
    alembic("auth", banco, "upgrade", "head")
    assert "stripe_eventos_processados" not in tabelas(banco)
    with conectar(banco) as conn:
        colunas = {linha[1] for linha in conn.execute("PRAGMA table_info(usuarios)")}
    assert not colunas & {"premium", "premium_desde", "stripe_customer_id", "stripe_subscription_id"}

    alembic("auth", banco, "downgrade", "007_reset_token_hash")
    assert "stripe_eventos_processados" in tabelas(banco)
    alembic("auth", banco, "upgrade", "head")
