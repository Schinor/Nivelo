"""GET /api/admin/metricas e os gauges da cobrança."""

import uuid

import pytest
from conftest import DONO_A, EMPRESA_A, EMPRESA_B, ENC_A
from test_autenticacao_api import auth, token
from test_obras_api import tk

pytestmark = pytest.mark.mariadb

ADMIN = auth(token("99", admin=True))
EMPRESA_C = "0190f3a0-0000-7000-8000-00000000000c"


@pytest.fixture
def ctx(obras_ctx):
    from app.admin.api.rotas import contas_da_plataforma, eventos_da_plataforma
    from app.admin.application.metricas import ContasDaPlataforma, EmpresaDaPlataforma, EventoDaPlataforma
    from app.main import app

    class Contas:
        def contas(self):
            return ContasDaPlataforma(
                empresas=[
                    EmpresaDaPlataforma(EMPRESA_A, "Rocha Reformas", frozenset({DONO_A, ENC_A})),
                    EmpresaDaPlataforma(EMPRESA_B, "Alves Obras", frozenset({4})),
                ],
                nomes_de_usuarios={DONO_A: "Jorge"},
                total_de_usuarios=3,
            )

    class Eventos:
        def ultimos(self, limite):
            return [EventoDaPlataforma("assinatura.iniciada", DONO_A, "dono", EMPRESA_A, "2026-11-09T10:00:00Z")]

    app.dependency_overrides[contas_da_plataforma] = Contas
    app.dependency_overrides[eventos_da_plataforma] = Eventos
    yield obras_ctx
    app.dependency_overrides.pop(contas_da_plataforma, None)
    app.dependency_overrides.pop(eventos_da_plataforma, None)


def _assinatura(ctx, empresa, **campos):
    from app.assinaturas.infrastructure.modelos import AssinaturaModel
    from app.shared.infrastructure.tenancy import sem_tenant

    db = ctx.SessionLocal()
    with sem_tenant(db, "carga dos dados de teste"):
        db.merge(AssinaturaModel(empresa_id=uuid.UUID(empresa), **campos))
        db.commit()
    db.close()


def test_sem_token_responde_401(ctx):
    assert ctx.client.get("/api/admin/metricas").status_code == 401


@pytest.mark.parametrize("papel", ["dono", "encarregado", "cliente"])
def test_so_o_admin_da_plataforma_ve_o_painel(ctx, papel):
    assert ctx.client.get("/api/admin/metricas", headers=tk(DONO_A, EMPRESA_A, papel)).status_code == 403


def test_painel_soma_o_que_pertence_a_todas_as_empresas(ctx):
    _assinatura(ctx, EMPRESA_A, plano="pro", status="active", valor_mensal_centavos=2990)
    _assinatura(ctx, EMPRESA_B, plano="construtora", status="past_due", valor_mensal_centavos=6990)
    _assinatura(ctx, EMPRESA_C, plano="pro", status="active", valor_mensal_centavos=2990)

    resp = ctx.client.get("/api/admin/metricas", headers=ADMIN)

    assert resp.status_code == 200, resp.text
    corpo = resp.json()
    assert corpo["mrr_centavos"] == 5980 and corpo["mrr_formatado"] == "R$ 59,80"
    assert (corpo["assinaturas_ativas"], corpo["inadimplentes"]) == (2, 1)
    assert (corpo["empresas_total"], corpo["usuarios_total"]) == (3, 3)
    assert {p["plano"]: (p["empresas"], p["usuarios"]) for p in corpo["por_plano"]} == {
        "free": (0, 0),
        "pro": (2, 2),
        "construtora": (1, 1),
    }


def test_evento_mostra_quem_empresa_e_quando_sem_os_dados_da_obra(ctx):
    [evento] = ctx.client.get("/api/admin/metricas", headers=ADMIN).json()["eventos"]

    assert evento["tipo"] == "assinatura.iniciada"
    assert (evento["ator_nome"], evento["ator_papel"]) == ("Jorge", "dono")
    assert (evento["empresa_nome"], evento["quando"]) == ("Rocha Reformas", "2026-11-09T10:00:00Z")
    assert "dados" not in evento


def test_servicos_fora_do_ar_nao_derrubam_o_painel(ctx, monkeypatch):
    import httpx

    from app.admin.api.rotas import contas_da_plataforma, eventos_da_plataforma
    from app.admin.infrastructure import leituras
    from app.main import app

    def fora_do_ar(*_, **__):
        raise httpx.ConnectError("sem rota")

    monkeypatch.setattr(leituras.httpx, "get", fora_do_ar)
    app.dependency_overrides.pop(contas_da_plataforma)
    app.dependency_overrides.pop(eventos_da_plataforma)
    _assinatura(ctx, EMPRESA_A, plano="pro", status="active", valor_mensal_centavos=2990)

    resp = ctx.client.get("/api/admin/metricas", headers=ADMIN)

    assert resp.status_code == 200, resp.text
    corpo = resp.json()
    assert corpo["mrr_formatado"] == "R$ 29,90"
    assert corpo["usuarios_total"] is None and corpo["eventos"] is None


def test_le_o_formato_real_do_auth_service_e_do_log_service(ctx, monkeypatch):
    from app.admin.infrastructure import leituras

    class Resposta:
        def __init__(self, corpo):
            self.corpo = corpo

        def raise_for_status(self):
            return None

        def json(self):
            return self.corpo

    contas = {
        "empresas": [{"id": EMPRESA_A, "nome": "Rocha", "usuario_ids": [1, 2]}],
        "usuarios": [{"id": 1, "nome": "Ana", "admin": False}, {"id": 99, "nome": "Plataforma", "admin": True}],
    }
    negocio = {
        "tipo": "obra.criada",
        "acao": "obra.criada",
        "usuario_id": "1",
        "empresa_id": EMPRESA_A,
        "timestamp": "t",
    }
    antigo = {"acao": "login", "usuario_id": "", "timestamp": "u"}
    monkeypatch.setattr(
        leituras.httpx, "get", lambda url, **_: Resposta(contas if "/internal/" in url else [negocio, antigo])
    )

    lidas = leituras.ContasViaAuthService().contas()
    eventos = leituras.EventosViaLogService().ultimos(20)

    assert lidas.total_de_usuarios == 1 and lidas.nomes_de_usuarios[99] == "Plataforma"
    assert lidas.empresas[0].usuario_ids == frozenset({1, 2})
    assert [(e.tipo, e.ator_id, e.empresa_id, e.quando) for e in eventos] == [
        ("obra.criada", 1, EMPRESA_A, "t"),
        ("login", None, None, "u"),
    ]


def test_gauges_do_prometheus(ctx):
    from app.admin.infrastructure.prometheus import ColetorDeAssinaturas

    _assinatura(ctx, EMPRESA_A, plano="pro", status="active", valor_mensal_centavos=2990)
    _assinatura(ctx, EMPRESA_B, plano="free", status="active", valor_mensal_centavos=0)

    valores = {m.name: m.samples[0].value for m in ColetorDeAssinaturas(ctx.SessionLocal).collect()}

    assert valores == {"nivelo_mrr_centavos": 2990, "nivelo_assinaturas_ativas": 1}


def test_banco_fora_do_ar_nao_derruba_as_metricas():
    from sqlalchemy.exc import OperationalError
    from test_backend_proxy import setup_api_app

    setup_api_app()
    from app.admin.infrastructure.prometheus import ColetorDeAssinaturas

    def sem_banco():
        raise OperationalError("SELECT 1", {}, Exception("fora do ar"))

    assert list(ColetorDeAssinaturas(sem_banco).collect()) == []
