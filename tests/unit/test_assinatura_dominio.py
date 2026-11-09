"""Como a assinatura acompanha o Stripe e o que a auditoria registra em cada mudança."""

import uuid

import pytest


@pytest.fixture
def d(api):
    return api("app.assinaturas.domain.assinatura")


def _empresa(api):
    return api("app.shared.domain.ids").EmpresaId(uuid.UUID("0190f3a0-0000-7000-8000-00000000000a"))


@pytest.fixture
def base(api, d):
    p = api("app.assinaturas.domain.planos")
    return d.AssinaturaDaEmpresa(
        empresa_id=_empresa(api),
        plano=p.Plano.FREE,
        status=p.StatusAssinatura.ACTIVE,
        stripe_customer_id="cus",
        stripe_subscription_id=None,
        stripe_price_id=None,
        valor_mensal_centavos=0,
        periodo_fim=None,
        cancelar_no_fim=False,
    )


def _externa(api, d, status="active", preco="pp", sub="sub"):
    p = api("app.assinaturas.domain.planos")
    return d.AssinaturaNoPagamento(
        subscription_id=sub,
        customer_id="cus",
        price_id=preco,
        status=p.StatusAssinatura(status),
        periodo_fim=None,
        cancelar_no_fim=False,
        valor_mensal_centavos=2990,
        empresa_id=None,
        usuario_id=None,
    )


def _precos(d):
    return d.PrecosDosPlanos("pp", "pc")


def _tipo(api, d, antes, depois, aviso):
    ator = api("app.shared.domain.ids").UsuarioId(1)
    e = d.evento_da_mudanca(antes, depois, aviso, ator)
    return e.tipo if e else None


def test_sincronizar_duas_vezes_da_no_mesmo(api, d, base):
    uma = base.sincronizada_com(_externa(api, d), _precos(d))
    assert uma.sincronizada_com(_externa(api, d), _precos(d)) == uma
    assert uma.plano.value == "pro"


def test_preco_desconhecido_e_free(d):
    assert _precos(d).plano_de("outro").value == "free" and _precos(d).plano_de(None).value == "free"


def test_inadimplente_mantem_o_contrato_e_perde_os_direitos(api, d, base):
    a = base.sincronizada_com(_externa(api, d, "past_due"), _precos(d))
    assert a.plano.value == "pro" and a.efetivos.plano.value == "free" and a.tem_assinatura_vigente


@pytest.mark.parametrize("status", ["canceled", "incomplete_expired"])
def test_encerrada_volta_para_o_free_e_libera_novo_checkout(api, d, base, status):
    ativa = base.sincronizada_com(_externa(api, d), _precos(d))
    fim = ativa.sincronizada_com(_externa(api, d, status), _precos(d))
    assert (fim.plano.value, fim.status.value, fim.valor_mensal_centavos) == ("free", "canceled", 0)
    assert not fim.tem_assinatura_vigente and fim.stripe_customer_id == "cus"


def test_so_a_assinatura_diferente_e_encerrada_e_antiga(api, d, base):
    ativa = base.sincronizada_com(_externa(api, d, sub="nova"), _precos(d))
    assert ativa.e_assinatura_antiga(_externa(api, d, "canceled", sub="velha"))
    assert not ativa.e_assinatura_antiga(_externa(api, d, "canceled", sub="nova"))
    assert not ativa.e_assinatura_antiga(_externa(api, d, "active", sub="outra"))


def test_eventos_de_auditoria_por_mudanca(api, d, base):
    p = _precos(d)
    pro = base.sincronizada_com(_externa(api, d), p)
    construtora = pro.sincronizada_com(_externa(api, d, preco="pc"), p)
    atrasada = pro.sincronizada_com(_externa(api, d, "past_due"), p)
    cancelada = pro.sincronizada_com(_externa(api, d, "canceled"), p)

    assert _tipo(api, d, base, pro, d.EVENTO_CHECKOUT_CONCLUIDO) == "assinatura.iniciada"
    assert _tipo(api, d, pro, pro, d.EVENTO_ASSINATURA_ALTERADA) is None
    assert _tipo(api, d, pro, construtora, d.EVENTO_ASSINATURA_ALTERADA) == "assinatura.alterada"
    assert _tipo(api, d, pro, atrasada, d.EVENTO_PAGAMENTO_FALHOU) == "assinatura.inadimplente"
    assert _tipo(api, d, pro, cancelada, d.EVENTO_ASSINATURA_REMOVIDA) == "assinatura.cancelada"
