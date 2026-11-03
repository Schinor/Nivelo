"""Ponte da API para a identidade (cadastro com empresa, vínculos, empresa nova e troca)."""

import pytest
from test_backend_proxy import setup_api_app


@pytest.fixture
def ctx(monkeypatch):
    app, _, _, TestClient = setup_api_app()
    chamadas = []

    async def fake_forward(method, path, json_data=None, headers=None, **kw):
        chamadas.append({"method": method, "path": path, "json": json_data, "headers": headers})
        return {"ok": True}

    monkeypatch.setattr("app.routes.auth.forward_request", fake_forward)

    class Ctx:
        pass

    c = Ctx()
    c.client, c.chamadas = TestClient(app), chamadas
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
