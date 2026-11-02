"""Fundação da API (Fase 1): Request ID e erros no formato Problem Details (RFC 9457)."""
import uuid

import pytest

from test_backend_proxy import setup_api_app

PROBLEM = "application/problem+json"


@pytest.fixture
def api():
    app, _, current_user, TestClient = setup_api_app()
    return app, TestClient(app, raise_server_exceptions=False)


def test_request_id_e_gerado_quando_nao_vem(api):
    _, client = api
    resp = client.get("/health/live")
    assert uuid.UUID(resp.headers["X-Request-ID"])


def test_request_id_valido_e_devolvido_igual(api):
    _, client = api
    resp = client.get("/health/live", headers={"X-Request-ID": "clique-123-abc"})
    assert resp.headers["X-Request-ID"] == "clique-123-abc"


@pytest.mark.parametrize("ruim", ["curto", "tem espaco e <tag>", "x" * 200])
def test_request_id_invalido_e_substituido(api, ruim):
    _, client = api
    resp = client.get("/health/live", headers={"X-Request-ID": ruim})
    assert resp.headers["X-Request-ID"] != ruim
    assert uuid.UUID(resp.headers["X-Request-ID"])


def test_404_vira_problem_details_com_request_id(api):
    _, client = api
    resp = client.get("/api/rota-que-nao-existe", headers={"X-Request-ID": "rastreio-404-teste"})

    assert resp.status_code == 404
    assert resp.headers["content-type"] == PROBLEM
    corpo = resp.json()
    assert corpo["type"] == "https://nivelo/erros/nao-encontrado"
    assert corpo["status"] == 404 and corpo["title"] == "Not Found"
    assert corpo["instance"] == "/api/rota-que-nao-existe"
    assert corpo["request_id"] == "rastreio-404-teste"


def test_401_mantem_detail_e_header_www_authenticate(api):
    _, client = api
    resp = client.post("/api/auth/logout")

    assert resp.status_code == 401
    assert resp.headers["content-type"] == PROBLEM
    assert resp.headers["www-authenticate"] == "Bearer"
    assert resp.json()["type"] == "https://nivelo/erros/nao-autenticado"
    assert resp.json()["detail"] == "Token não enviado"


def test_422_lista_os_campos_invalidos(api):
    _, client = api
    resp = client.post("/api/auth/cadastro", json={"email": "nao-e-email"})

    assert resp.status_code == 422
    corpo = resp.json()
    assert corpo["type"] == "https://nivelo/erros/validacao"
    campos = {e["campo"] for e in corpo["errors"]}
    assert {"nome", "email", "senha"} <= campos
    assert isinstance(corpo["detail"], str) and "senha" in corpo["detail"]


def test_erros_de_dominio_viram_problem_details(api):
    app, client = api
    from app.shared.domain.erros import ErroDeDominio, RecursoNaoEncontrado

    class ObraConcluida(ErroDeDominio):
        codigo = "obra-concluida"

    def regra():
        raise ObraConcluida("Obra concluída não volta a ficar ativa")

    def sumiu():
        raise RecursoNaoEncontrado("Obra não encontrada")

    app.add_api_route("/api/_teste/regra", regra)
    app.add_api_route("/api/_teste/sumiu", sumiu)

    regra_resp = client.get("/api/_teste/regra")
    assert regra_resp.status_code == 422
    assert regra_resp.json()["type"] == "https://nivelo/erros/obra-concluida"
    assert regra_resp.json()["detail"] == "Obra concluída não volta a ficar ativa"

    sumiu_resp = client.get("/api/_teste/sumiu")
    assert sumiu_resp.status_code == 404
    assert sumiu_resp.json()["type"] == "https://nivelo/erros/nao-encontrado"


def test_erro_inesperado_vira_500_sem_vazar_detalhe(api):
    app, client = api

    def quebra():
        raise RuntimeError("senha do banco: segredo")

    app.add_api_route("/api/_teste/quebra", quebra)
    resp = client.get("/api/_teste/quebra")

    assert resp.status_code == 500
    assert resp.json()["type"] == "https://nivelo/erros/erro-interno"
    assert "segredo" not in resp.text


def test_request_id_e_repassado_ao_auth_service(monkeypatch):
    import asyncio

    import httpx

    setup_api_app()
    from app.clients import auth_client
    from app.shared.api.request_id import request_id_atual

    recebidos = {}

    def handler(request):
        recebidos.update(request.headers)
        return httpx.Response(200, json={"ok": True})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.clients.auth_client.httpx.AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    token = request_id_atual.set("rastreio-auth-123")
    try:
        asyncio.run(auth_client.forward_request("GET", "/me"))
    finally:
        request_id_atual.reset(token)

    assert recebidos["x-request-id"] == "rastreio-auth-123"
