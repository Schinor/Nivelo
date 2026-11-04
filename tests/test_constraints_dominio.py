"""Constraints do esquema de domínio (revisão api_003): o banco recusa o que a aplicação já
recusa, como última linha de defesa.

Roda num SQLite migrado pelo Alembic e, com `NIVELO_TESTES_NO_MARIADB=1`, no MariaDB do CI
(onde as FKs compostas, os CHECKs e os índices únicos são os da produção).
"""

import os
import subprocess
import sys
import uuid

import pytest
from banco_de_teste import PASTA_DA_API, no_mariadb
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import DataError, IntegrityError, OperationalError

pytestmark = pytest.mark.mariadb

# CHECK violado: o SQLite dá IntegrityError; o MariaDB, o erro 4025 (OperationalError no PyMySQL).
# Valor fora de um ENUM no MariaDB em modo estrito: erro 1265 (DataError).
RECUSADO = (IntegrityError, OperationalError, DataError)

EMPRESA_A = "0190f3a0-0000-7000-8000-00000000000a"
EMPRESA_B = "0190f3a0-0000-7000-8000-00000000000b"
OBRA_A = "0190f3a0-0000-7000-8000-0000000000a1"
DIARIO_A = "0190f3a0-0000-7000-8000-0000000000d1"


def _id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def banco(tmp_path):
    if no_mariadb():
        from banco_de_teste import motor_da_api
        from test_backend_proxy import setup_api_app

        setup_api_app()  # importa a API e esvazia o banco
        from app.core.database import Base

        yield motor_da_api(Base.metadata)
        return
    arquivo = tmp_path / "constraints.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{arquivo}", "SECRET_KEY": "teste"}
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=PASTA_DA_API, env=env, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr[-2000:]
    motor = create_engine(f"sqlite:///{arquivo}")
    event.listen(motor, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys = ON"))
    yield motor
    motor.dispose()


def obra(c, obra_id=OBRA_A, empresa=EMPRESA_A, inicio="2026-10-01", termino="2026-12-20"):
    c.execute(
        text(
            "INSERT INTO obras (id, empresa_id, nome, logradouro, cidade, uf, cliente_nome, data_inicio,"
            " previsao_termino, criado_por) VALUES (:id, :e, 'Casa da Rua 7', 'Rua 7, 100', 'Marília', 'SP',"
            " 'Sr. Jorge', :i, :t, 1)"
        ),
        {"id": obra_id, "e": empresa, "i": inicio, "t": termino},
    )


def diario(c, diario_id=DIARIO_A, empresa=EMPRESA_A, obra_id=OBRA_A, data="2026-11-02", efetivo=0):
    c.execute(
        text("INSERT INTO diarios (id, empresa_id, obra_id, data, autor_id, efetivo) VALUES (:id, :e, :o, :d, 1, :ef)"),
        {"id": diario_id, "e": empresa, "o": obra_id, "d": data, "ef": efetivo},
    )


def foto(c, empresa=EMPRESA_A, diario_id=DIARIO_A, chave="empresas/a/obras/o/diarios/d/1.jpg"):
    c.execute(
        text(
            "INSERT INTO diario_fotos (id, empresa_id, diario_id, object_key, content_type, tamanho_bytes,"
            " enviado_por) VALUES (:id, :e, :d, :k, 'image/jpeg', 1000, 1)"
        ),
        {"id": _id(), "e": empresa, "d": diario_id, "k": chave},
    )


def recusa(banco, *passos):
    """Os `passos` anteriores ao último gravam; o último precisa ser recusado pelo banco."""
    with banco.begin() as c:
        for passo in passos[:-1]:
            passo(c)
    with pytest.raises(RECUSADO), banco.begin() as c:
        passos[-1](c)


def test_banco_recusa_diario_de_uma_empresa_na_obra_de_outra(banco):
    recusa(banco, obra, lambda c: diario(c, empresa=EMPRESA_B))


def test_banco_recusa_membro_de_uma_empresa_na_obra_de_outra(banco):
    recusa(
        banco,
        obra,
        lambda c: c.execute(
            text("INSERT INTO obra_membros (obra_id, usuario_id, empresa_id, papel) VALUES (:o, 2, :e, 'cliente')"),
            {"o": OBRA_A, "e": EMPRESA_B},
        ),
    )


def test_banco_recusa_foto_de_uma_empresa_no_diario_de_outra(banco):
    recusa(banco, obra, diario, lambda c: foto(c, empresa=EMPRESA_B))


def test_um_diario_por_obra_por_dia(banco):
    recusa(banco, obra, diario, lambda c: diario(c, diario_id=_id()))


def test_previsao_de_termino_nao_pode_ser_antes_do_inicio(banco):
    recusa(banco, lambda c: obra(c, inicio="2026-12-01", termino="2026-11-01"))


def test_efetivo_nao_pode_ser_negativo(banco):
    recusa(banco, obra, lambda c: diario(c, efetivo=-1))


def test_object_key_da_foto_e_unica(banco):
    recusa(banco, obra, diario, foto, foto)


@pytest.mark.skipif(not no_mariadb(), reason="o SQLite não impõe ENUM; só o MariaDB recusa")
def test_status_fora_do_enum_e_recusado(banco):
    recusa(banco, obra, lambda c: c.execute(text("UPDATE obras SET status = 'arquivada' WHERE id = :o"), {"o": OBRA_A}))


def test_ocorrencias_e_fotos_saem_com_o_diario_e_revisao_impede_apagar(banco):
    with banco.begin() as c:
        obra(c)
        diario(c)
        foto(c)
        c.execute(
            text(
                "INSERT INTO ocorrencias (id, empresa_id, diario_id, tipo, descricao)"
                " VALUES (:id, :e, :d, 'chuva', 'Chuva forte')"
            ),
            {"id": _id(), "e": EMPRESA_A, "d": DIARIO_A},
        )
    with banco.begin() as c:
        c.execute(text("DELETE FROM diarios WHERE id = :d"), {"d": DIARIO_A})
        assert c.execute(text("SELECT COUNT(*) FROM ocorrencias")).scalar() == 0
        assert c.execute(text("SELECT COUNT(*) FROM diario_fotos")).scalar() == 0

    def revisao(c):
        c.execute(
            text(
                "INSERT INTO diario_revisoes (id, empresa_id, diario_id, versao_anterior, snapshot, motivo, autor_id)"
                " VALUES (:id, :e, :d, 1, '{}', 'Corrigir efetivo', 1)"
            ),
            {"id": _id(), "e": EMPRESA_A, "d": DIARIO_A},
        )

    recusa(banco, diario, revisao, lambda c: c.execute(text("DELETE FROM diarios WHERE id = :d"), {"d": DIARIO_A}))


def test_obra_nao_e_apagada_de_verdade_enquanto_tem_diario(banco):
    """Obra tem soft delete; o DELETE físico não leva os diários junto."""
    recusa(banco, obra, diario, lambda c: c.execute(text("DELETE FROM obras WHERE id = :o"), {"o": OBRA_A}))
