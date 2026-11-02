"""Atividade 7 — Plano Premium com Stripe (lado do catálogo).

A assinatura do webhook é gerada de verdade (HMAC-SHA256, mesmo esquema do Stripe),
então a validação real de stripe.Webhook.construct_event é exercitada. O auth-service
é trocado por um fake em memória que imita a rota interna e sua idempotência.
"""
import hashlib
import hmac
import json
import time

import pytest

from test_backend_proxy import _capturar_eventos, _usuario, setup_api_app

WHSEC = "whsec_teste_123"


def _assinar(corpo: bytes, segredo: str = WHSEC, t: int | None = None) -> str:
    t = t or int(time.time())
    assinatura = hmac.new(segredo.encode(), f"{t}.".encode() + corpo, hashlib.sha256).hexdigest()
    return f"t={t},v1={assinatura}"


def _evento_checkout(event_id, usuario_id, payment_status="paid"):
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "mode": "subscription",
                "payment_status": payment_status,
                "client_reference_id": str(usuario_id),
                "metadata": {"usuario_id": str(usuario_id)},
                "customer": "cus_teste",
                "subscription": "sub_teste",
            }
        },
    }


@pytest.fixture
def ctx(monkeypatch):
    app, SessionLocal, current_user, TestClient = setup_api_app()
    from app.core.config import settings

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", WHSEC)
    monkeypatch.setattr(settings, "STRIPE_PRICE_ID", "price_fake")

    class Ctx:
        pass

    c = Ctx()
    c.usuarios = {1: {"id": 1, "nome": "Ana", "email": "ana@teste.com", "premium": False, "premium_desde": None}}
    c.processados = set()
    c.chamadas_internas = []

    async def fake_forward(method, path, json_data=None, interno=False, **kw):
        if path == "/internal/premium/eventos":
            assert interno is True
            c.chamadas_internas.append(json_data)
            if json_data["event_id"] in c.processados:
                return {"duplicado": True, "aplicado": False, "usuario_id": None, "premium": None}
            c.processados.add(json_data["event_id"])
            u = c.usuarios.get(json_data.get("usuario_id"))
            if json_data["tipo"] == "checkout.session.completed" and u:
                u["premium"] = True
                return {"duplicado": False, "aplicado": True, "usuario_id": u["id"], "premium": True}
            return {"duplicado": False, "aplicado": False, "usuario_id": None, "premium": None}
        uid = int(path.rsplit("/", 1)[1])
        return dict(c.usuarios[uid])

    monkeypatch.setattr("app.routes.premium.forward_request", fake_forward)
    monkeypatch.setattr("app.clients.auth_client.forward_request", fake_forward)

    c.app, c.settings, c.SessionLocal = app, settings, SessionLocal
    c.eventos = _capturar_eventos(monkeypatch)
    c.client = TestClient(app)
    app.dependency_overrides[current_user] = lambda: _usuario(1, "dono", [])

    def webhook(evento, assinatura=None):
        corpo = json.dumps(evento).encode()
        return c.client.post(
            "/webhooks/stripe",
            content=corpo,
            headers={"Stripe-Signature": assinatura or _assinar(corpo), "Content-Type": "application/json"},
        )

    c.webhook = webhook
    return c


# ── Configuração ──────────────────────────────────────────────────────────────

def test_chave_live_e_recusada_na_inicializacao():
    setup_api_app()
    from pydantic import ValidationError
    from app.core.config import Settings

    with pytest.raises(ValidationError, match="LIVE"):
        Settings(STRIPE_SECRET_KEY="sk_live_abc")
    assert Settings(STRIPE_SECRET_KEY="sk_test_abc").STRIPE_SECRET_KEY == "sk_test_abc"


def test_sem_stripe_configurado_checkout_e_webhook_respondem_503(ctx, monkeypatch):
    monkeypatch.setattr(ctx.settings, "STRIPE_SECRET_KEY", "")
    assert ctx.client.post("/api/premium/checkout").status_code == 503
    assert ctx.webhook(_evento_checkout("evt_x", 1)).status_code == 503


# ── Checkout ──────────────────────────────────────────────────────────────────

def test_checkout_cria_sessao_com_usuario_e_devolve_url(ctx, monkeypatch):
    import stripe

    capturado = {}

    class Sessao:
        url = "https://checkout.stripe.com/c/pay/cs_test_1"

    def fake_create(**kwargs):
        capturado.update(kwargs)
        return Sessao()

    monkeypatch.setattr(stripe.checkout.Session, "create", fake_create)
    monkeypatch.setattr(ctx.settings, "FRONTEND_URL", "http://localhost:4200/")

    resp = ctx.client.post("/api/premium/checkout")
    assert resp.status_code == 200
    assert resp.json() == {"url": Sessao.url}
    assert capturado["mode"] == "subscription"
    assert capturado["line_items"] == [{"price": "price_fake", "quantity": 1}]
    assert capturado["client_reference_id"] == "1"
    assert capturado["metadata"] == {"usuario_id": "1"}
    assert capturado["customer_email"] == "ana@teste.com"
    assert capturado["success_url"] == "http://localhost:4200/premium/sucesso?session_id={CHECKOUT_SESSION_ID}"
    assert capturado["cancel_url"] == "http://localhost:4200/premium/cancelado"
    # Checkout NÃO torna ninguém premium
    assert ctx.usuarios[1]["premium"] is False
    assert {"acao": "premium_checkout_iniciado", "usuario_id": 1, "recurso": None, "detalhes": None} in ctx.eventos


def test_checkout_de_quem_ja_e_premium_retorna_409(ctx):
    ctx.usuarios[1]["premium"] = True
    assert ctx.client.post("/api/premium/checkout").status_code == 409


def test_checkout_com_erro_do_stripe_retorna_502(ctx, monkeypatch):
    import stripe

    def falha(**kwargs):
        raise stripe.AuthenticationError("chave inválida")

    monkeypatch.setattr(stripe.checkout.Session, "create", falha)
    assert ctx.client.post("/api/premium/checkout").status_code == 502


def test_checkout_exige_login():
    app, _, _, TestClient = setup_api_app()
    assert TestClient(app).post("/api/premium/checkout").status_code == 401


# ── Webhook ───────────────────────────────────────────────────────────────────

def test_webhook_sem_assinatura_ou_com_assinatura_invalida_retorna_400(ctx):
    resp = ctx.client.post("/webhooks/stripe", json={"fake": True})
    assert resp.status_code == 400

    evento = _evento_checkout("evt_forjado", 1)
    assert ctx.webhook(evento, assinatura=_assinar(b"outro corpo")).status_code == 400
    assert ctx.webhook(evento, assinatura=_assinar(json.dumps(evento).encode(), segredo="whsec_errado")).status_code == 400
    # Assinatura antiga (fora da tolerância de 5 min do Stripe): replay recusado
    velha = _assinar(json.dumps(evento).encode(), t=int(time.time()) - 3600)
    assert ctx.webhook(evento, assinatura=velha).status_code == 400

    assert ctx.chamadas_internas == []
    assert ctx.usuarios[1]["premium"] is False


def test_webhook_valido_torna_usuario_premium_e_repassa_so_ids(ctx):
    resp = ctx.webhook(_evento_checkout("evt_ok", 1))
    assert resp.status_code == 200
    assert ctx.usuarios[1]["premium"] is True
    assert ctx.chamadas_internas == [
        {
            "event_id": "evt_ok",
            "tipo": "checkout.session.completed",
            "usuario_id": 1,
            "customer_id": "cus_teste",
            "subscription_id": "sub_teste",
        }
    ]
    assert any(e["acao"] == "premium_ativado" and e["usuario_id"] == 1 for e in ctx.eventos)


def test_webhook_duplicado_e_aplicado_uma_vez(ctx):
    evento = _evento_checkout("evt_dup", 1)
    assert ctx.webhook(evento).status_code == 200
    assert ctx.webhook(evento).status_code == 200
    assert [e["acao"] for e in ctx.eventos].count("premium_ativado") == 1


def test_webhook_ignora_eventos_nao_tratados_e_checkout_nao_pago(ctx):
    outro = {"id": "evt_inv", "type": "invoice.paid", "data": {"object": {}}}
    assert ctx.webhook(outro).status_code == 200
    assert ctx.webhook(_evento_checkout("evt_unpaid", 1, payment_status="unpaid")).status_code == 200
    assert ctx.chamadas_internas == []
    assert ctx.usuarios[1]["premium"] is False


def test_webhook_cancelamento_repassa_a_assinatura(ctx):
    evento = {"id": "evt_del", "type": "customer.subscription.deleted", "data": {"object": {"id": "sub_teste"}}}
    assert ctx.webhook(evento).status_code == 200
    assert ctx.chamadas_internas == [
        {"event_id": "evt_del", "tipo": "customer.subscription.deleted", "subscription_id": "sub_teste"}
    ]


def test_webhook_com_auth_service_fora_retorna_500_para_o_stripe_reenviar(ctx, monkeypatch):
    from fastapi import HTTPException

    async def fora(*a, **kw):
        raise HTTPException(status_code=503, detail="Serviço de autenticação inacessível")

    monkeypatch.setattr("app.routes.premium.forward_request", fora)
    assert ctx.webhook(_evento_checkout("evt_500", 1)).status_code == 500


# ── Status do plano ───────────────────────────────────────────────────────────





def test_status_vem_do_banco_e_nao_do_jwt(ctx):
    """Mesmo com um JWT que diga premium=true, o status consulta o auth-service (banco)."""
    from app.dependencies import current_user

    ctx.app.dependency_overrides[current_user] = lambda: {**_usuario(1, "dono", []), "premium": True}
    assert ctx.client.get("/api/premium/status").json() == {"premium": False, "premium_desde": None}


def test_premium_via_webhook_aparece_no_status(ctx):
    ctx.webhook(_evento_checkout("evt_libera", 1))
    assert ctx.client.get("/api/premium/status").json()["premium"] is True


def test_perfil_exibe_selo_premium(ctx, monkeypatch):
    async def fake_conta(method, path, **kw):
        return dict(ctx.usuarios[1])

    monkeypatch.setattr("app.routes.perfis.forward_request", fake_conta)
    assert ctx.client.get("/api/perfis/1").json()["premium"] is False
    ctx.webhook(_evento_checkout("evt_selo", 1))
    assert ctx.client.get("/api/perfis/1").json()["premium"] is True
