"""Convites pela API: a obra precisa ser da empresa ativa, só o dono convida, e o aceite
coloca a pessoa na obra."""

import pytest
from test_autenticacao_api import auth, token
from test_obras_api import DONO_A, EMPRESA_A, EMPRESA_B, ENC_A, OBRA_A2, OBRA_B1, nomes, tk


@pytest.fixture
def ctx(obras_ctx):
    return obras_ctx


class Chamadas(list):
    """Chamadas ao auth-service; `resposta` é o que o aceite devolve."""

    resposta: dict | None = None


@pytest.fixture
def chamadas(monkeypatch):
    feitas = Chamadas()

    async def fake_forward(method, path, json_data=None, headers=None, **kw):
        feitas.append({"path": path, "json": json_data, "headers": headers})
        if path == "/convites":
            return {**json_data, "id": "0190f3a0-0000-7000-8000-0000000000c9", "expira_em": "2026-11-06T12:00:00"}
        return feitas.resposta

    monkeypatch.setattr("app.obras.api.convites.forward_request", fake_forward)
    return feitas


def test_dono_convida_para_obra_da_propria_empresa(ctx, chamadas):
    resp = ctx.client.post(
        "/api/convites",
        json={"email": "ze@exemplo.com", "papel": "encarregado", "obra_id": OBRA_A2},
        headers=tk(DONO_A, EMPRESA_A, "dono"),
    )
    assert resp.status_code == 201, resp.text
    assert chamadas[-1]["path"] == "/convites"
    assert chamadas[-1]["json"]["obra_id"] == OBRA_A2
    assert chamadas[-1]["headers"]["authorization"].startswith("Bearer ")
    assert "empresa_id" not in chamadas[-1]["json"]  # a empresa vem do token, no auth-service


def test_obra_de_outra_empresa_responde_404_sem_convidar(ctx, chamadas):
    resp = ctx.client.post(
        "/api/convites",
        json={"email": "ze@exemplo.com", "papel": "encarregado", "obra_id": OBRA_B1},
        headers=tk(DONO_A, EMPRESA_A, "dono"),
    )
    assert resp.status_code == 404
    assert chamadas == []


def test_encarregado_e_token_sem_tenant_nao_convidam(ctx, chamadas):
    corpo = {"email": "x@exemplo.com", "papel": "cliente"}
    assert ctx.client.post("/api/convites", json=corpo, headers=tk(ENC_A, EMPRESA_A, "encarregado")).status_code == 403
    sem_tenant = auth(token("9", empresa_id=None, papel=None))
    assert ctx.client.post("/api/convites", json=corpo, headers=sem_tenant).status_code == 403
    assert chamadas == []


def test_aceite_coloca_a_pessoa_na_obra_e_e_idempotente(ctx, chamadas):
    chamadas.resposta = {
        "usuario_id": 42,
        "empresa_id": EMPRESA_A,
        "papel": "encarregado",
        "obra_id": OBRA_A2,
        "novo_usuario": True,
    }
    corpo = {"token": "t" * 43, "nome": "Zé", "senha": "senha123"}
    assert ctx.client.post("/api/convites/aceitar", json=corpo).status_code == 200
    assert ctx.client.post("/api/convites/aceitar", json=corpo).status_code == 200

    assert nomes(ctx.client.get("/api/obras", headers=tk(42, EMPRESA_A, "encarregado"))) == ["Muro da escola"]


def test_aceite_de_quem_ja_e_dono_nao_vira_membro(ctx, chamadas):
    chamadas.resposta = {
        "usuario_id": DONO_A,
        "empresa_id": EMPRESA_A,
        "papel": "dono",
        "obra_id": OBRA_A2,
        "novo_usuario": False,
    }
    assert ctx.client.post("/api/convites/aceitar", json={"token": "t" * 43}).status_code == 200
    # O dono segue vendo todas as obras da empresa, sem virar membro
    assert len(nomes(ctx.client.get("/api/obras", headers=tk(DONO_A, EMPRESA_A, "dono")))) == 2


def test_aceite_com_obra_de_outra_empresa_nao_cria_membro(ctx, chamadas):
    chamadas.resposta = {
        "usuario_id": 43,
        "empresa_id": EMPRESA_A,
        "papel": "cliente",
        "obra_id": OBRA_B1,
        "novo_usuario": True,
    }
    assert ctx.client.post("/api/convites/aceitar", json={"token": "t" * 43}).status_code == 200
    assert nomes(ctx.client.get("/api/obras", headers=tk(43, EMPRESA_A, "cliente"))) == []
    assert nomes(ctx.client.get("/api/obras", headers=tk(43, EMPRESA_B, "cliente"))) == []
