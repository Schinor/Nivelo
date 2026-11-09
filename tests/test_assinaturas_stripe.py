"""Checkout, portal e webhook do Stripe. A rede é simulada; a assinatura do webhook é de verdade."""

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime

import pytest
from conftest import CLI_A, DONO_A, DONO_B, EMPRESA_A, EMPRESA_B, ENC_A
from test_obras_api import tk

pytestmark = pytest.mark.mariadb

SEGREDO = "segredo-do-webhook-de-teste"
PRECO_PRO, PRECO_CONSTRUTORA = "price_pro", "price_construtora"
DONO = tk(DONO_A, EMPRESA_A, "dono")


@pytest.fixture
def ctx(obras_ctx):
    from app.assinaturas.api import rotas
    from app.assinaturas.api.dependencias import gateway_de_pagamentos, precos_dos_planos
    from app.assinaturas.domain.assinatura import PrecosDosPlanos
    from app.assinaturas.infrastructure.stripe_gateway import StripeGateway, assinatura_de
    from app.main import app

    class GatewayFalso(StripeGateway):
        """Valida a assinatura de verdade; só as chamadas de rede são simuladas."""

        def __init__(self):
            super().__init__("chave", SEGREDO, "https://nivelo.test")
            self.assinaturas, self.customers, self.checkouts = {}, [], []
            self.falhar = False

        def criar_customer(self, empresa_id, email, nome):
            self.customers.append((str(empresa_id), email))
            return f"cus_{len(self.customers)}"

        def criar_checkout_assinatura(self, customer_id, empresa_id, usuario_id, price_id):
            self.checkouts.append((customer_id, str(empresa_id), usuario_id.valor, price_id))
            return "https://checkout.test/sessao"

        def criar_sessao_portal(self, customer_id):
            return f"https://portal.test/{customer_id}"

        def buscar_assinatura(self, subscription_id):
            if self.falhar:
                raise RuntimeError("fora do ar")
            return assinatura_de(self.assinaturas[subscription_id])

    gateway = GatewayFalso()
    app.dependency_overrides[gateway_de_pagamentos] = lambda: gateway
    app.dependency_overrides[precos_dos_planos] = lambda: PrecosDosPlanos(PRECO_PRO, PRECO_CONSTRUTORA)
    rotas._avisos_recentes.clear()
    obras_ctx.gateway = gateway
    yield obras_ctx
    app.dependency_overrides.pop(gateway_de_pagamentos, None)
    app.dependency_overrides.pop(precos_dos_planos, None)


def _assinar(corpo, segredo=SEGREDO):
    agora = int(time.time())
    assinatura = hmac.new(segredo.encode(), f"{agora}.".encode() + corpo, hashlib.sha256).hexdigest()
    return f"t={agora},v1={assinatura}"


def _enviar(ctx, evento, segredo=SEGREDO):
    corpo = json.dumps(evento).encode()
    return ctx.client.post("/webhooks/stripe", content=corpo, headers={"stripe-signature": _assinar(corpo, segredo)})


def _evento(tipo, objeto, event_id=None):
    return {"id": event_id or f"evt_{uuid.uuid4().hex}", "type": tipo, "data": {"object": objeto}}


def _no_stripe(ctx, sub="sub_1", preco=PRECO_PRO, status="active", valor=2990, empresa=EMPRESA_A, cancelar=False):
    ctx.gateway.assinaturas[sub] = {
        "id": sub,
        "customer": "cus_1",
        "status": status,
        "cancel_at_period_end": cancelar,
        "metadata": {"empresa_id": empresa, "usuario_id": str(DONO_A)},
        "items": {
            "data": [{"price": {"id": preco, "unit_amount": valor}, "quantity": 1, "current_period_end": 1800000000}]
        },
    }


def _checkout_concluido(event_id=None, sub="sub_1", empresa=EMPRESA_A):
    return _evento(
        "checkout.session.completed",
        {"subscription": sub, "customer": "cus_1", "client_reference_id": empresa},
        event_id,
    )


def _linha(ctx, empresa=EMPRESA_A):
    from app.assinaturas.infrastructure.modelos import AssinaturaModel
    from app.shared.infrastructure.tenancy import sem_tenant

    db = ctx.SessionLocal()
    with sem_tenant(db, "conferência do teste"):
        return db.get(AssinaturaModel, uuid.UUID(empresa))


def _eventos_de_assinatura(ctx):
    from app.shared.infrastructure.outbox import OutboxModel

    db = ctx.SessionLocal()
    tipos = [o.tipo for o in db.query(OutboxModel).order_by(OutboxModel.id) if o.tipo.startswith("assinatura.")]
    db.close()
    return tipos


# ── Webhook ──────────────────────────────────────────────────────────────────


def test_assinatura_invalida_responde_400_e_nao_muda_nada(ctx):
    _no_stripe(ctx)

    assert _enviar(ctx, _checkout_concluido(), segredo="outro-segredo").status_code == 400

    assert _linha(ctx) is None
    assert ctx.eventos[-1]["acao"] == "webhook.assinatura_invalida"


def test_webhook_sem_cabecalho_responde_400(ctx):
    assert ctx.client.post("/webhooks/stripe", content=b"{}").status_code == 400


def test_checkout_concluido_vira_pro_a_partir_do_estado_no_stripe(ctx):
    _no_stripe(ctx)

    assert _enviar(ctx, _checkout_concluido()).status_code == 200

    linha = _linha(ctx)
    assert (linha.plano, linha.status, linha.valor_mensal_centavos) == ("pro", "active", 2990)
    assert (linha.stripe_customer_id, linha.stripe_subscription_id) == ("cus_1", "sub_1")
    assert linha.periodo_fim == datetime(2027, 1, 15, 8, 0)
    assert _eventos_de_assinatura(ctx) == ["assinatura.iniciada"]


def test_mesmo_evento_duas_vezes_tem_um_efeito_so(ctx):
    _no_stripe(ctx)
    evento = _checkout_concluido("evt_repetido")

    assert _enviar(ctx, evento).status_code == 200
    # Se fosse reprocessado, leria este estado novo
    _no_stripe(ctx, preco=PRECO_CONSTRUTORA, valor=6990)
    assert _enviar(ctx, evento).status_code == 200

    assert _linha(ctx).plano == "pro"
    assert _eventos_de_assinatura(ctx) == ["assinatura.iniciada"]


def test_subscription_updated_troca_o_plano(ctx):
    _no_stripe(ctx)
    _enviar(ctx, _checkout_concluido())
    _no_stripe(ctx, preco=PRECO_CONSTRUTORA, valor=6990)

    assert (
        _enviar(ctx, _evento("customer.subscription.updated", {"id": "sub_1", "customer": "cus_1"})).status_code == 200
    )

    linha = _linha(ctx)
    assert (linha.plano, linha.valor_mensal_centavos) == ("construtora", 6990)
    assert _eventos_de_assinatura(ctx) == ["assinatura.iniciada", "assinatura.alterada"]


def test_subscription_deleted_volta_para_o_free(ctx):
    _no_stripe(ctx)
    _enviar(ctx, _checkout_concluido())
    _no_stripe(ctx, status="canceled")

    assert (
        _enviar(ctx, _evento("customer.subscription.deleted", {"id": "sub_1", "customer": "cus_1"})).status_code == 200
    )

    linha = _linha(ctx)
    assert (linha.plano, linha.status, linha.valor_mensal_centavos) == ("free", "canceled", 0)
    assert linha.stripe_subscription_id is None and linha.stripe_customer_id == "cus_1"
    assert _eventos_de_assinatura(ctx) == ["assinatura.iniciada", "assinatura.cancelada"]


@pytest.mark.parametrize(
    "fatura",
    [
        {"subscription": "sub_1", "customer": "cus_1"},
        {"parent": {"subscription_details": {"subscription": "sub_1"}}, "customer": "cus_1"},
    ],
)
def test_pagamento_falho_deixa_inadimplente_e_avisa_o_dono(ctx, monkeypatch, fatura):
    chamadas = []

    async def fake_forward(method, path, json_data=None, **kw):
        chamadas.append((path, json_data, kw.get("interno")))

    monkeypatch.setattr("app.assinaturas.api.rotas.forward_request", fake_forward)
    _no_stripe(ctx)
    _enviar(ctx, _checkout_concluido())
    _no_stripe(ctx, status="past_due")

    assert _enviar(ctx, _evento("invoice.payment_failed", fatura)).status_code == 200

    assert _linha(ctx).status == "past_due"
    assert _eventos_de_assinatura(ctx) == ["assinatura.iniciada", "assinatura.inadimplente"]
    assert chamadas == [("/internal/avisos/inadimplencia", {"empresa_id": EMPRESA_A}, True)]


def test_inadimplente_perde_os_direitos_do_pro_na_hora(ctx):
    _no_stripe(ctx)
    _enviar(ctx, _checkout_concluido())
    obra = {
        "nome": "Mais uma",
        "endereco": {"logradouro": "Rua 2", "cidade": "Marília", "uf": "SP"},
        "cliente_nome": "C",
        "data_inicio": "2026-11-03",
        "previsao_termino": "2027-03-31",
    }
    assert ctx.client.post("/api/obras", json=obra, headers=DONO).status_code == 201

    _no_stripe(ctx, status="past_due")
    _enviar(ctx, _evento("customer.subscription.updated", {"id": "sub_1", "customer": "cus_1"}))

    assert ctx.client.post("/api/obras", json=obra, headers=DONO).status_code == 402


def test_aviso_atrasado_de_assinatura_antiga_nao_derruba_a_nova(ctx):
    _no_stripe(ctx, sub="sub_novo")
    _enviar(ctx, _checkout_concluido(sub="sub_novo"))
    _no_stripe(ctx, sub="sub_velho", status="canceled")

    assert _enviar(ctx, _evento("customer.subscription.deleted", {"id": "sub_velho"})).status_code == 200

    assert _linha(ctx).plano == "pro" and _linha(ctx).stripe_subscription_id == "sub_novo"


def test_preco_desconhecido_nao_da_direito_a_nada(ctx):
    _no_stripe(ctx, preco="price_de_outro_produto")
    _enviar(ctx, _checkout_concluido())
    assert _linha(ctx).plano == "free"


def test_falha_ao_processar_responde_500_e_o_reenvio_aplica(ctx):
    _no_stripe(ctx)
    evento = _checkout_concluido("evt_com_falha")
    ctx.gateway.falhar = True
    assert _enviar(ctx, evento).status_code == 500
    assert _linha(ctx) is None

    ctx.gateway.falhar = False
    assert _enviar(ctx, evento).status_code == 200
    assert _linha(ctx).plano == "pro"


def test_evento_que_nao_interessa_responde_200_sem_efeito(ctx):
    assert _enviar(ctx, _evento("customer.created", {"id": "cus_9"})).status_code == 200
    assert _linha(ctx) is None


def test_webhook_tem_limite_por_origem(ctx, monkeypatch):
    monkeypatch.setattr("app.assinaturas.api.rotas.AVISOS_POR_MINUTO", 1)
    assert _enviar(ctx, _evento("customer.created", {"id": "cus_9"})).status_code == 200
    assert _enviar(ctx, _evento("customer.created", {"id": "cus_9"})).status_code == 429


# ── Checkout e portal ────────────────────────────────────────────────────────


def test_checkout_cria_o_customer_e_nao_muda_o_plano(ctx):
    resp = ctx.client.post("/api/assinaturas/checkout", json={"plano": "pro"}, headers=DONO)

    assert resp.status_code == 200 and resp.json() == {"url": "https://checkout.test/sessao"}
    assert ctx.gateway.checkouts == [("cus_1", EMPRESA_A, DONO_A, PRECO_PRO)]
    linha = _linha(ctx)
    assert linha.stripe_customer_id == "cus_1" and linha.plano == "free"


def test_segundo_checkout_reaproveita_o_customer(ctx):
    for _ in range(2):
        ctx.client.post("/api/assinaturas/checkout", json={"plano": "construtora"}, headers=DONO)
    assert len(ctx.gateway.customers) == 1 and ctx.gateway.checkouts[1][3] == PRECO_CONSTRUTORA


def test_empresa_com_assinatura_vai_ao_portal_e_nao_a_outro_checkout(ctx):
    _no_stripe(ctx)
    _enviar(ctx, _checkout_concluido())

    resp = ctx.client.post("/api/assinaturas/checkout", json={"plano": "construtora"}, headers=DONO)

    assert resp.status_code == 409
    assert resp.json()["type"] == "https://nivelo/erros/assinatura-ja-vigente"


def test_plano_que_nao_se_compra_e_recusado(ctx):
    assert ctx.client.post("/api/assinaturas/checkout", json={"plano": "free"}, headers=DONO).status_code == 422


def test_empresa_vem_do_token_e_nao_do_corpo(ctx):
    corpo = {"plano": "pro", "empresa_id": EMPRESA_B}
    ctx.client.post("/api/assinaturas/checkout", json=corpo, headers=DONO)
    assert ctx.gateway.checkouts[0][1] == EMPRESA_A


def test_portal_devolve_a_url_do_customer_da_propria_empresa(ctx):
    ctx.client.post("/api/assinaturas/checkout", json={"plano": "pro"}, headers=DONO)

    assert ctx.client.post("/api/assinaturas/portal", headers=DONO).json() == {"url": "https://portal.test/cus_1"}
    # A empresa B não herda o cliente da A: para ela, ainda não há assinatura
    assert ctx.client.post("/api/assinaturas/portal", headers=tk(DONO_B, EMPRESA_B, "dono")).status_code == 409


@pytest.mark.parametrize("rota", ["/api/assinaturas/checkout", "/api/assinaturas/portal"])
@pytest.mark.parametrize("uid,papel", [(ENC_A, "encarregado"), (CLI_A, "cliente")])
def test_so_o_dono_assina_ou_gerencia(ctx, rota, uid, papel):
    assert ctx.client.post(rota, json={"plano": "pro"}, headers=tk(uid, EMPRESA_A, papel)).status_code == 403
    assert ctx.gateway.checkouts == []


def test_sem_stripe_configurado_responde_503(obras_ctx):
    resp = obras_ctx.client.post("/api/assinaturas/checkout", json={"plano": "pro"}, headers=DONO)
    assert resp.status_code == 503
