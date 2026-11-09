"""Tradução dos objetos do Stripe para o nosso domínio, com a forma real da API."""

from datetime import datetime

import pytest

EMPRESA = "0190f3a0-0000-7000-8000-00000000000a"


@pytest.fixture
def g(api):
    return api("app.assinaturas.infrastructure.stripe_gateway")


def test_periodo_no_item_como_nas_versoes_novas_da_api(g):
    a = g.assinatura_de(
        {
            "id": "sub_1",
            "customer": "cus_1",
            "status": "active",
            "cancel_at_period_end": True,
            "metadata": {"empresa_id": EMPRESA, "usuario_id": "7"},
            "items": {
                "data": [{"price": {"id": "p1", "unit_amount": 2990}, "quantity": 2, "current_period_end": 1800000000}]
            },
        }
    )
    assert (a.price_id, a.valor_mensal_centavos, a.cancelar_no_fim) == ("p1", 5980, True)
    assert a.periodo_fim == datetime(2027, 1, 15, 8, 0) and a.status.value == "active"
    assert str(a.empresa_id) == EMPRESA and a.usuario_id.valor == 7


def test_periodo_na_raiz_como_nas_versoes_antigas(g):
    a = g.assinatura_de({"id": "s", "status": "trialing", "current_period_end": 1800000000, "items": {"data": [{}]}})
    assert a.periodo_fim == datetime(2027, 1, 15, 8, 0)


def test_status_desconhecido_e_metadados_ruins_nao_dao_direito(g):
    a = g.assinatura_de({"id": "s", "status": "novidade", "metadata": {"empresa_id": "x", "usuario_id": "abc"}})
    assert a.status.value == "incomplete" and a.empresa_id is None and a.usuario_id is None


def test_checkout_leva_a_empresa_da_referencia(g):
    e = g.evento_de(
        {
            "id": "evt",
            "type": "checkout.session.completed",
            "data": {"object": {"subscription": "sub_1", "customer": "cus_1", "client_reference_id": EMPRESA}},
        }
    )
    assert (e.subscription_id, e.customer_id, str(e.empresa_id)) == ("sub_1", "cus_1", EMPRESA)


def test_id_expandido_e_lido_de_dentro_do_objeto(g):
    e = g.evento_de(
        {"id": "evt", "type": "checkout.session.completed", "data": {"object": {"subscription": {"id": "sub_9"}}}}
    )
    assert e.subscription_id == "sub_9"
