"""Gestão de Obras: autorização por papel e tenant, isolamento entre empresas e a rede de
segurança do ORM (Fase 3). Tokens de verdade (JWT), sem substituir dependências. O CRUD da
Fase 4a está em test_obras_crud_api.py."""

import uuid

import pytest
from test_autenticacao_api import auth, token

# Tenancy, papéis e plano: rodam também no MariaDB (tests/banco_de_teste.py)
pytestmark = pytest.mark.mariadb

EMPRESA_A = "0190f3a0-0000-7000-8000-00000000000a"
EMPRESA_B = "0190f3a0-0000-7000-8000-00000000000b"
OBRA_A1 = "0190f3a0-0000-7000-8000-0000000000a1"
OBRA_A2 = "0190f3a0-0000-7000-8000-0000000000a2"
OBRA_B1 = "0190f3a0-0000-7000-8000-0000000000b1"

DONO_A, ENC_A, CLI_A, DONO_B, MULTI = 1, 2, 3, 4, 5


def tk(uid, empresa, papel):
    return auth(token(str(uid), empresa_id=empresa, papel=papel))


@pytest.fixture
def ctx(obras_ctx):
    """Obras das empresas A e B, com membros (ver tests/conftest.py)."""
    return obras_ctx


def nomes(resp):
    assert resp.status_code == 200, resp.text
    return sorted(o["nome"] for o in resp.json()["itens"])


# ── Token sem tenant (usuário sem vínculo) ──────────────────────────────────


@pytest.mark.parametrize(
    "metodo, rota",
    [("get", "/api/obras"), ("post", "/api/obras"), ("post", f"/api/obras/{OBRA_A1}/diarios")],
)
def test_token_sem_tenant_recebe_403_em_obras(ctx, metodo, rota):
    resp = getattr(ctx.client, metodo)(rota, headers=auth(token("9", empresa_id=None, papel=None)))
    assert resp.status_code == 403
    assert resp.json()["type"] == "https://nivelo/erros/sem-empresa-ativa"
    assert ctx.eventos[-1]["acao"] == "acesso.negado" and ctx.eventos[-1]["usuario_id"] == 9


def test_obras_sem_token_e_401(ctx):
    assert ctx.client.get("/api/obras").status_code == 401


# ── Papéis (403) ─────────────────────────────────────────────────────────────


def test_encarregado_criando_obra_recebe_403_e_gera_acesso_negado(ctx):
    resp = ctx.client.post("/api/obras", json={}, headers=tk(ENC_A, EMPRESA_A, "encarregado"))
    assert resp.status_code == 403
    assert resp.json()["type"] == "https://nivelo/erros/acesso-negado"
    assert ctx.eventos[-1] == {
        "acao": "acesso.negado",
        "usuario_id": ENC_A,
        "recurso": "POST /api/obras",
        "detalhes": "POST /api/obras",
    }


def test_cliente_registrando_diario_recebe_403(ctx):
    resp = ctx.client.post(f"/api/obras/{OBRA_A2}/diarios", json={}, headers=tk(CLI_A, EMPRESA_A, "cliente"))
    assert resp.status_code == 403
    assert ctx.eventos[-1]["acao"] == "acesso.negado"


def test_dono_e_encarregado_passam_pela_autorizacao_do_diario(ctx):
    # 501 = autorizado; o registro do diário chega na Fase 4b
    resp = ctx.client.post(f"/api/obras/{OBRA_A1}/diarios", json={}, headers=tk(ENC_A, EMPRESA_A, "encarregado"))
    assert resp.status_code == 501
    assert resp.json()["type"] == "https://nivelo/erros/em-construcao"
    resp = ctx.client.post(f"/api/obras/{OBRA_A1}/diarios", json={}, headers=tk(DONO_A, EMPRESA_A, "dono"))
    assert resp.status_code == 501


# ── Isolamento entre empresas ────────────────────────────────────────────────


def test_dono_ve_todas_as_obras_da_propria_empresa_e_nenhuma_de_outra(ctx):
    assert nomes(ctx.client.get("/api/obras", headers=tk(DONO_A, EMPRESA_A, "dono"))) == [
        "Casa do Jorge",
        "Muro da escola",
    ]
    assert nomes(ctx.client.get("/api/obras", headers=tk(DONO_B, EMPRESA_B, "dono"))) == ["Ampliação Alves"]


def test_encarregado_e_cliente_veem_so_as_obras_em_que_sao_membros(ctx):
    assert nomes(ctx.client.get("/api/obras", headers=tk(ENC_A, EMPRESA_A, "encarregado"))) == ["Casa do Jorge"]
    assert nomes(ctx.client.get("/api/obras", headers=tk(CLI_A, EMPRESA_A, "cliente"))) == ["Muro da escola"]


def test_mesmo_usuario_em_duas_empresas_ve_so_a_empresa_ativa(ctx):
    com_a = nomes(ctx.client.get("/api/obras", headers=tk(MULTI, EMPRESA_A, "encarregado")))
    com_b = nomes(ctx.client.get("/api/obras", headers=tk(MULTI, EMPRESA_B, "cliente")))
    assert com_a == ["Casa do Jorge"]
    assert com_b == ["Ampliação Alves"]


def test_empresa_no_corpo_ou_na_query_e_ignorada(ctx):
    resp = ctx.client.get(f"/api/obras?empresa_id={EMPRESA_B}", headers=tk(DONO_A, EMPRESA_A, "dono"))
    assert "Ampliação Alves" not in nomes(resp)


# ── Rede de segurança do ORM ─────────────────────────────────────────────────


def test_consulta_orm_sem_tenant_definido_levanta_erro(ctx):
    from sqlalchemy import select

    from app.obras.infrastructure.modelos import ObraModel
    from app.shared.infrastructure.tenancy import TenantNaoDefinido

    db = ctx.SessionLocal()
    with pytest.raises(TenantNaoDefinido):
        db.scalars(select(ObraModel)).all()
    db.close()


def test_sessao_com_tenant_so_enxerga_a_propria_empresa_mesmo_sem_filtro(ctx):
    from sqlalchemy import select, update

    from app.obras.infrastructure.modelos import ObraModel
    from app.shared.infrastructure.tenancy import definir_tenant

    db = ctx.SessionLocal()
    definir_tenant(db, uuid.UUID(EMPRESA_B))
    # Consulta "esquecida" sem where de empresa: a rede de segurança filtra
    assert [o.nome for o in db.scalars(select(ObraModel))] == ["Ampliação Alves"]
    assert db.get(ObraModel, uuid.UUID(OBRA_A1)) is None
    # Update em massa também fica preso ao tenant
    db.execute(update(ObraModel).values(status="pausada"))
    db.commit()
    db.close()

    db = ctx.SessionLocal()
    definir_tenant(db, uuid.UUID(EMPRESA_A))
    assert {o.status for o in db.scalars(select(ObraModel))} == {"ativa"}
    db.close()


def test_gravar_dado_de_outra_empresa_e_recusado(ctx):
    from app.obras.infrastructure.modelos import ObraMembroModel
    from app.shared.infrastructure.tenancy import TenantDivergente, definir_tenant

    db = ctx.SessionLocal()
    definir_tenant(db, uuid.UUID(EMPRESA_A))
    db.add(ObraMembroModel(obra_id=uuid.UUID(OBRA_B1), usuario_id=77, empresa_id=uuid.UUID(EMPRESA_B), papel="cliente"))
    with pytest.raises(TenantDivergente):
        db.flush()
    db.rollback()
    db.close()


def test_sem_tenant_exige_motivo(ctx):
    from app.shared.infrastructure.tenancy import sem_tenant

    db = ctx.SessionLocal()
    with pytest.raises(ValueError), sem_tenant(db, "  "):
        pass
    db.close()
