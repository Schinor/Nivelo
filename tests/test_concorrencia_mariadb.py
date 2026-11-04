"""Concorrência e isolamento no MariaDB de verdade (o SQLite não trava linha). Roda quando MARIADB_URL
existe (CI e `docker run ... mariadb:11.8` local); senão, é pulado.

Duas criações de obra ao mesmo tempo numa empresa Free: o `FOR UPDATE` na assinatura e o
READ COMMITTED da unidade de trabalho (ADR 011) deixam passar só uma; a outra recebe 402.
"""

import os
import threading
import uuid
from datetime import date

import pytest
from test_migracoes import PASTAS

MARIADB_URL = os.environ.get("MARIADB_URL")
pytestmark = pytest.mark.skipif(not MARIADB_URL, reason="defina MARIADB_URL para os testes no MariaDB")
BANCO = "nivelo_concorrencia"


@pytest.fixture(scope="module")
def motor():
    import subprocess
    import sys

    from sqlalchemy import create_engine

    with create_engine(MARIADB_URL).begin() as c:
        c.exec_driver_sql(f"DROP DATABASE IF EXISTS {BANCO}")
        c.exec_driver_sql(f"CREATE DATABASE {BANCO} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    env = {**os.environ, "DATABASE_URL": f"{MARIADB_URL}/{BANCO}", "SECRET_KEY": "teste"}
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=PASTAS["api"], env=env, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr[-2000:]
    engine = create_engine(f"{MARIADB_URL}/{BANCO}", pool_size=4)
    yield engine
    engine.dispose()
    with create_engine(MARIADB_URL).begin() as c:
        c.exec_driver_sql(f"DROP DATABASE IF EXISTS {BANCO}")


def _corrida(motor, ja_tem_assinatura):
    from test_backend_proxy import setup_api_app

    setup_api_app()  # garante o pacote app da API
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    from app.assinaturas.domain.planos import LimiteDoPlanoExcedido
    from app.assinaturas.infrastructure.direitos import ConsultaDireitosSQL
    from app.obras.application import handlers
    from app.obras.application.comandos import CriarObra, DadosDaObra
    from app.obras.infrastructure.unidade_de_trabalho import UnidadeDeTrabalhoDeObrasSQL
    from app.shared.application.contexto import TenantContext
    from app.shared.domain.ids import EmpresaId
    from app.shared.infrastructure.tenancy import definir_tenant

    empresa = EmpresaId(uuid.uuid4())
    if ja_tem_assinatura:
        with motor.begin() as c:
            c.execute(
                text("INSERT INTO assinaturas (empresa_id, plano, status) VALUES (:e, 'free', 'active')"),
                {"e": str(empresa.valor)},
            )
    ctx = TenantContext(empresa_id=empresa, usuario_id=1, papel="dono")
    Sessao = sessionmaker(bind=motor, autoflush=False)
    barreira = threading.Barrier(2)
    resultados = []

    def criar(nome):
        with Sessao() as s:
            definir_tenant(s, empresa.valor)
            uow = UnidadeDeTrabalhoDeObrasSQL(s, empresa, ConsultaDireitosSQL(s))
            dados = DadosDaObra(nome, "Rua 1", "Marília", "SP", "Jorge", date(2026, 11, 3), date(2027, 1, 1))
            barreira.wait()
            try:
                handlers.criar_obra(CriarObra(dados), ctx, uow)
                resultados.append("criou")
            except LimiteDoPlanoExcedido:
                resultados.append("402")
            except Exception as erro:  # o teste quer ver o erro, não um 500 escondido
                resultados.append(repr(erro)[:300])

    threads = [threading.Thread(target=criar, args=(f"Obra {i}",)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    with motor.connect() as c:
        gravadas = c.execute(
            text("SELECT COUNT(*) FROM obras WHERE empresa_id = :e"), {"e": str(empresa.valor)}
        ).scalar()
    return sorted(resultados), gravadas


@pytest.mark.parametrize("ja_tem_assinatura", [True, False], ids=["assinatura-existente", "assinatura-a-criar"])
def test_duas_criacoes_simultaneas_no_free_so_uma_passa(motor, ja_tem_assinatura):
    for _ in range(5):
        resultados, gravadas = _corrida(motor, ja_tem_assinatura)
        assert resultados == ["402", "criou"] and gravadas == 1


def test_read_committed_vale_so_na_transacao_do_comando(motor):
    """ADR 011: a unidade de trabalho pede READ COMMITTED na própria conexão; a conexão volta ao
    pool no isolamento padrão e as consultas fora do comando continuam em REPEATABLE READ."""
    from test_backend_proxy import setup_api_app

    setup_api_app()
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from app.assinaturas.infrastructure.direitos import ConsultaDireitosSQL
    from app.obras.infrastructure.unidade_de_trabalho import UnidadeDeTrabalhoDeObrasSQL
    from app.shared.domain.ids import EmpresaId
    from app.shared.infrastructure.tenancy import definir_tenant

    # Uma conexão só no pool: a consulta depois do comando reaproveita a mesma conexão
    um_so = create_engine(motor.url, pool_size=1, max_overflow=0)
    isolamento = text("SELECT @@transaction_isolation")
    empresa = EmpresaId(uuid.uuid4())
    try:
        with Session(um_so) as s:
            definir_tenant(s, empresa.valor)
            with UnidadeDeTrabalhoDeObrasSQL(s, empresa, ConsultaDireitosSQL(s)):
                assert s.scalar(isolamento) == "READ-COMMITTED"
        with Session(um_so) as s:
            assert s.scalar(isolamento) == "REPEATABLE-READ"
    finally:
        um_so.dispose()
