"""Autenticação da API a partir do JWT de verdade (sem substituir dependências)."""

import os

import pytest
from jose import jwt
from test_backend_proxy import _capturar_eventos, setup_api_app

EMPRESA = "0190f3a0-0000-7000-8000-00000000000a"


def token(sub="1", **claims):
    return jwt.encode({"sub": sub, **claims}, os.environ["SECRET_KEY"], algorithm="HS256")


def auth(tk):
    return {"Authorization": f"Bearer {tk}"}


@pytest.fixture
def api(monkeypatch):
    app, _, _, TestClient = setup_api_app()
    eventos = _capturar_eventos(monkeypatch)
    return TestClient(app), eventos


def test_token_sem_tenant_recebe_403_com_type_proprio_e_e_auditado(api):
    client, eventos = api
    resp = client.get("/api/obras", headers=auth(token(empresa_id=None, papel=None)))

    assert resp.status_code == 403
    assert resp.json()["type"] == "https://nivelo/erros/sem-empresa-ativa"
    assert "/api/auth/empresas" in resp.json()["detail"]
    assert eventos[-1]["acao"] == "acesso.negado" and eventos[-1]["usuario_id"] == 1


def test_token_sem_tenant_ainda_faz_logout(api):
    client, _ = api
    assert client.post("/api/auth/logout", headers=auth(token())).status_code == 204


def test_admin_sem_tenant_tambem_nao_entra_em_rota_de_empresa(api):
    client, _ = api
    resp = client.get("/api/obras", headers=auth(token(admin=True)))
    assert resp.status_code == 403


@pytest.mark.parametrize(
    "claims",
    [
        {"empresa_id": EMPRESA},  # empresa sem papel
        {"papel": "dono"},  # papel sem empresa
        {"empresa_id": EMPRESA, "papel": "admin"},  # papel que não é de negócio
        {"empresa_id": "123", "papel": "dono"},  # empresa que não é UUID
    ],
)
def test_claims_incoerentes_invalidam_o_token(api, claims):
    client, _ = api
    resp = client.get("/api/perfis/me", headers=auth(token(**claims)))
    assert resp.status_code == 401


def test_token_assinado_com_outra_chave_e_recusado(api):
    client, _ = api
    falso = jwt.encode({"sub": "1", "empresa_id": EMPRESA, "papel": "dono"}, "outra-chave", algorithm="HS256")
    assert client.get("/api/perfis/me", headers=auth(falso)).status_code == 401


def test_logs_so_para_admin(api, monkeypatch):
    client, _ = api
    dono = auth(token(empresa_id=EMPRESA, papel="dono"))
    assert client.get("/api/logs", headers=dono).status_code == 403


def test_requer_papel_recusa_papel_desconhecido_na_definicao():
    setup_api_app()
    from app.shared.api.autenticacao import requer_papel

    with pytest.raises(ValueError):
        requer_papel("admin")
    with pytest.raises(ValueError):
        requer_papel()
