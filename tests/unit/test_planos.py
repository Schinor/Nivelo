"""Planos, direitos efetivos por status e a política de obras ativas (Parte A.7)."""

import pytest


@pytest.fixture
def p(api):
    return api("app.assinaturas.domain.planos")


@pytest.mark.parametrize("plano", ["free", "pro", "construtora"])
@pytest.mark.parametrize(
    "status, vale",
    [
        ("active", True),
        ("trialing", True),
        ("past_due", False),
        ("unpaid", False),
        ("canceled", False),
        ("incomplete", False),
        ("incomplete_expired", False),
        ("paused", False),
        ("status_que_nao_existe", False),
    ],
)
def test_direitos_do_plano_pago_so_valem_com_pagamento_em_dia(p, plano, status, vale):
    efetivos = p.direitos_efetivos(p.Plano(plano), p.StatusAssinatura.de_texto(status))
    esperado = p.Plano(plano) if vale else p.Plano.FREE
    assert efetivos.plano is esperado
    assert efetivos.direitos == p.DIREITOS_DO_PLANO[esperado]


def test_tabela_de_direitos(p):
    D = p.DIREITOS_DO_PLANO
    assert (
        D[p.Plano.FREE].max_obras_ativas,
        D[p.Plano.FREE].max_fotos_por_obra,
        D[p.Plano.FREE].max_membros_equipe,
    ) == (
        1,
        30,
        2,
    )
    assert D[p.Plano.PRO].max_obras_ativas is None and D[p.Plano.PRO].max_membros_equipe == 5
    assert D[p.Plano.CONSTRUTORA].max_membros_equipe is None and D[p.Plano.CONSTRUTORA].logo_no_relatorio


def test_free_com_uma_obra_ativa_nao_cria_a_segunda(p):
    free = p.direitos_efetivos(p.Plano.FREE, p.StatusAssinatura.ACTIVE)
    p.PoliticaDePlano.exigir_vaga_de_obra_ativa(free, 0)  # passa
    with pytest.raises(p.LimiteDoPlanoExcedido) as erro:
        p.PoliticaDePlano.exigir_vaga_de_obra_ativa(free, 1)
    e = erro.value
    assert e.status == 402 and e.codigo == "plano-limite-excedido"
    assert e.titulo == "Limite do plano Free atingido"
    assert e.mensagem == (
        "O plano Free permite 1 obra ativa e você já tem 1. "
        "Conclua ou pause uma obra, ou assine o Pro para ter obras ilimitadas."
    )
    assert e.extras() == {
        "limite": 1,
        "atual": 1,
        "plano_atual": "free",
        "plano_sugerido": "pro",
        "acao": "/assinatura",
    }


def test_pro_ativo_tem_obras_ilimitadas_e_pro_inadimplente_cai_no_free(p):
    pro = p.direitos_efetivos(p.Plano.PRO, p.StatusAssinatura.ACTIVE)
    p.PoliticaDePlano.exigir_vaga_de_obra_ativa(pro, 500)
    atrasado = p.direitos_efetivos(p.Plano.PRO, p.StatusAssinatura.PAST_DUE)
    with pytest.raises(p.LimiteDoPlanoExcedido):
        p.PoliticaDePlano.exigir_vaga_de_obra_ativa(atrasado, 1)
