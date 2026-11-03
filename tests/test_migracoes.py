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


def test_banco_recusa_diario_de_uma_empresa_na_obra_de_outra(dominio):
    with conectar(dominio) as conn:
        _obra(conn)
        with pytest.raises(sqlite3.IntegrityError):
            _diario(conn, empresa=EMPRESA_B)  # a obra é da empresa A


def test_um_diario_por_obra_por_dia(dominio):
    with conectar(dominio) as conn:
        _obra(conn)
        _diario(conn)
        with pytest.raises(sqlite3.IntegrityError):
            _diario(conn, diario_id="0190f3a0-0000-7000-8000-0000000000d2")


def test_previsao_de_termino_nao_pode_ser_antes_do_inicio(dominio):
    with conectar(dominio) as conn, pytest.raises(sqlite3.IntegrityError):
        _obra(conn, inicio="2026-12-01", termino="2026-11-01")


def test_ocorrencias_saem_com_o_diario_e_revisao_impede_apagar(dominio):
    with conectar(dominio) as conn:
        _obra(conn)
        _diario(conn)
        conn.execute(
            "INSERT INTO ocorrencias (id, empresa_id, diario_id, tipo, descricao) VALUES ('o1', ?, ?, 'chuva', 'Chuva forte')",
            (EMPRESA_A, DIARIO_A),
        )
        conn.execute("DELETE FROM diarios WHERE id = ?", (DIARIO_A,))
        assert conn.execute("SELECT COUNT(*) FROM ocorrencias").fetchone()[0] == 0

        _diario(conn)
        conn.execute(
            "INSERT INTO diario_revisoes (id, empresa_id, diario_id, versao_anterior, snapshot, motivo, autor_id)"
            " VALUES ('r1', ?, ?, 1, '{}', 'Corrigir efetivo', 1)",
            (EMPRESA_A, DIARIO_A),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM diarios WHERE id = ?", (DIARIO_A,))


def test_dominio_downgrade_e_upgrade_de_novo(dominio):
    alembic("api", dominio, "downgrade", "-1")
    assert not TABELAS_DO_DOMINIO & tabelas(dominio)
    assert "perfis" in tabelas(dominio)
    alembic("api", dominio, "upgrade", "head")
    assert TABELAS_DO_DOMINIO <= tabelas(dominio)
    assert "Running upgrade" not in alembic("api", dominio, "upgrade", "head")
