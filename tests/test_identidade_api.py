"""Ponte da API para a identidade (cadastro com empresa, vínculos, empresa nova e troca)."""

import pytest
from test_backend_proxy import setup_api_app


@pytest.fixture
def ctx(monkeypatch):
    app, SessionLocal, _, TestClient = setup_api_app()
    chamadas = []

    async def fake_forward(method, path, json_data=None, headers=None, **kw):
        chamadas.append({"method": method, "path": path, "json": json_data, "headers": headers})
        return {"ok": True}

    monkeypatch.setattr("app.routes.auth.forward_request", fake_forward)

    class Ctx:
        pass

    c = Ctx()
    c.client, c.chamadas, c.SessionLocal = TestClient(app), chamadas, SessionLocal
    return c


def test_cadastro_repassa_empresa_e_ignora_papel(ctx, monkeypatch):
    async def cadastro_ok(method, path, json_data=None, **kw):
        ctx.chamadas.append(json_data)
        return {
            "usuario": {"id": 1, "nome": "Valdir", "email": "v@exemplo.com"},
            "empresa": {"id": "0190f3a0-0000-7000-8000-00000000000a", "nome": "Rocha", "tipo_pessoa": "PJ"},
            "papel": "dono",
        }

    monkeypatch.setattr("app.routes.auth.forward_request", cadastro_ok)
    resp = ctx.client.post(
        "/api/auth/cadastro",
        json={
            "nome": " Valdir ",
            "email": "v@exemplo.com",
            "senha": "senha123",
            "empresa_nome": "Rocha",
            "tipo_pessoa": "PJ",
            "documento": "12.345.678/0001-90",
            "papel": "admin",
        },
    )
    assert resp.status_code == 201
    enviado = ctx.chamadas[-1]
    assert "papel" not in enviado and "role" not in enviado
    assert enviado["documento"] == "12345678000190" and enviado["nome"] == "Valdir"


def test_cadastro_valida_documento_antes_de_chamar_o_auth(ctx):
    resp = ctx.client.post(
        "/api/auth/cadastro",
        json={"nome": "Ana", "email": "a@exemplo.com", "senha": "senha123", "empresa_nome": "Ana", "documento": "1"},
    )
    assert resp.status_code == 422
    assert resp.json()["type"] == "https://nivelo/erros/validacao"
    assert ctx.chamadas == []


@pytest.mark.parametrize(
    "metodo, rota, corpo",
    [
        ("get", "/api/auth/vinculos", None),
        ("post", "/api/auth/empresas", {"nome": "Nova"}),
        ("post", "/api/auth/empresa-ativa", {"empresa_id": "0190f3a0-0000-7000-8000-00000000000a"}),
    ],
)
def test_rotas_de_vinculo_exigem_token_e_o_repassam(ctx, monkeypatch, metodo, rota, corpo):
    sem_token = getattr(ctx.client, metodo)(rota, **({"json": corpo} if corpo else {}))
    assert sem_token.status_code == 401
    assert ctx.chamadas == []

    async def responde(method, path, json_data=None, headers=None, **kw):
        ctx.chamadas.append({"path": path, "headers": headers, "json": json_data})
        if path == "/vinculos":
            return []
        base = {"access_token": "t", "token_type": "bearer", "user": {"id": 1, "nome": "A", "email": "a@a.com"}}
        if path == "/empresas":
            return {
                **base,
                "empresa": {"id": "0190f3a0-0000-7000-8000-00000000000b", "nome": "Nova", "tipo_pessoa": "PF"},
            }
        return base

    monkeypatch.setattr("app.routes.auth.forward_request", responde)
    com_token = getattr(ctx.client, metodo)(
        rota, headers={"Authorization": "Bearer abc"}, **({"json": corpo} if corpo else {})
    )
    assert com_token.status_code in (200, 201)
    assert ctx.chamadas[-1]["headers"] == {"authorization": "Bearer abc"}


def _assinaturas(ctx):
    from app.assinaturas.infrastructure.modelos import AssinaturaModel
    from app.shared.infrastructure.tenancy import sem_tenant

    db = ctx.SessionLocal()
    with sem_tenant(db, "conferência do teste"):
        linhas = [(str(a.empresa_id), a.plano, a.status) for a in db.query(AssinaturaModel).all()]
    db.close()
    return linhas


CADASTRO = {"nome": "Ana", "email": "a@exemplo.com", "senha": "senha123", "empresa_nome": "Ana Reformas"}
EMPRESA_NOVA = "0190f3a0-0000-7000-8000-0000000000aa"


def _auth_responde_empresa(monkeypatch, empresa_id=EMPRESA_NOVA):
    async def responde(method, path, **kw):
        base = {"access_token": "t", "token_type": "bearer", "user": {"id": 1, "nome": "A", "email": "a@a.com"}}
        empresa = {"id": empresa_id, "nome": "X", "tipo_pessoa": "PF"}
        if path == "/cadastro":
            return {"usuario": base["user"], "empresa": empresa, "papel": "dono"}
        return {**base, "empresa": empresa}

    monkeypatch.setattr("app.routes.auth.forward_request", responde)


def test_cadastro_cria_a_assinatura_free_da_empresa(ctx, monkeypatch):
    _auth_responde_empresa(monkeypatch)
    assert ctx.client.post("/api/auth/cadastro", json=CADASTRO).status_code == 201
    assert _assinaturas(ctx) == [(EMPRESA_NOVA, "free", "active")]


def test_empresa_nova_do_usuario_logado_tambem_nasce_free(ctx, monkeypatch):
    _auth_responde_empresa(monkeypatch)
    resp = ctx.client.post("/api/auth/empresas", json={"nome": "Nova"}, headers={"Authorization": "Bearer abc"})
    assert resp.status_code == 201
    assert _assinaturas(ctx) == [(EMPRESA_NOVA, "free", "active")]


def test_assinatura_free_e_idempotente(ctx):
    from app.assinaturas.application.assinatura_free import garantir_assinatura_free
    from app.assinaturas.infrastructure.repositorio import RepositorioDeAssinaturasSQL
    from app.shared.domain.ids import EmpresaId

    db = ctx.SessionLocal()
    empresa = EmpresaId.de_texto(EMPRESA_NOVA)
    assert garantir_assinatura_free(RepositorioDeAssinaturasSQL(db), empresa) is True
    assert garantir_assinatura_free(RepositorioDeAssinaturasSQL(db), empresa) is False
    db.close()
    assert len(_assinaturas(ctx)) == 1


def test_falha_na_assinatura_nao_desfaz_o_cadastro(ctx, monkeypatch):
    _auth_responde_empresa(monkeypatch)

    def quebra(*a, **kw):
        raise RuntimeError("banco fora")

    monkeypatch.setattr("app.routes.auth.garantir_assinatura_free", quebra)
    assert ctx.client.post("/api/auth/cadastro", json=CADASTRO).status_code == 201


def test_equipe_so_para_o_dono_e_repassa_o_token(ctx, monkeypatch):
    from test_autenticacao_api import auth, token

    async def fake_equipe(method, path, json_data=None, headers=None, **kw):
        ctx.chamadas.append({"path": path, "headers": headers})
        return [
            {"usuario_id": 2, "nome": "Zé", "email": "ze@x.com", "papel": "encarregado", "desde": "2026-11-03T10:00:00"}
        ]

    monkeypatch.setattr("app.routes.auth.forward_request", fake_equipe)

    empresa = "0190f3a0-0000-7000-8000-00000000000a"
    dono = auth(token("1", empresa_id=empresa, papel="dono"))
    assert ctx.client.get("/api/auth/equipe", headers=dono).status_code == 200
    assert ctx.chamadas[-1]["path"] == "/equipe"
    assert ctx.chamadas[-1]["headers"]["authorization"] == dono["Authorization"]

    antes = len(ctx.chamadas)
    encarregado = auth(token("2", empresa_id=empresa, papel="encarregado"))
    assert ctx.client.get("/api/auth/equipe", headers=encarregado).status_code == 403
    assert ctx.client.get("/api/auth/equipe", headers=auth(token("9", empresa_id=None, papel=None))).status_code == 403
    assert len(ctx.chamadas) == antes  # o 403 sai da API, sem chamar o auth-service
