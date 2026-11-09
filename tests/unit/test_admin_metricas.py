"""Regras do painel admin: o que conta como ativo, inadimplente e em cada plano."""

import pytest


@pytest.fixture
def m(api):
    return api("app.admin.application.metricas")


@pytest.fixture
def planos(api):
    return api("app.assinaturas.domain.planos")


def _linha(m, planos, empresa, plano="pro", status="active", valor=2990):
    return m.LinhaDeAssinatura(empresa, planos.Plano(plano), planos.StatusAssinatura(status), valor)


def _fontes(m, linhas, contas=None, eventos=()):
    class Assinaturas:
        def linhas(self):
            return linhas

    class Contas:
        def contas(self):
            if contas is None:
                raise IndisponivelFalso
            return contas

    class Eventos:
        def ultimos(self, limite):
            if eventos is None:
                raise IndisponivelFalso
            return list(eventos)[:limite]

    IndisponivelFalso = m.DependenciaIndisponivel("fora do ar")
    return Assinaturas(), Contas(), Eventos()


def _contas(m, *empresas, nomes=None, total=None):
    pessoas = {u for _, _, ids in empresas for u in ids}
    return m.ContasDaPlataforma(
        empresas=[m.EmpresaDaPlataforma(i, nome, frozenset(ids)) for i, nome, ids in empresas],
        nomes_de_usuarios=nomes or {},
        total_de_usuarios=len(pessoas) if total is None else total,
    )


@pytest.mark.parametrize(
    ("centavos", "esperado"),
    [(0, "R$ 0,00"), (2990, "R$ 29,90"), (6990, "R$ 69,90"), (129900, "R$ 1.299,00"), (123456789, "R$ 1.234.567,89")],
)
def test_formata_em_reais(m, centavos, esperado):
    assert m.formatar_reais(centavos) == esperado


def test_mrr_soma_so_as_pagas_com_status_active(m, planos):
    resumo = m.resumir_cobranca(
        [
            _linha(m, planos, "a"),
            _linha(m, planos, "b", "construtora", valor=6990),
            _linha(m, planos, "c", status="trialing"),
            _linha(m, planos, "d", status="past_due"),
            _linha(m, planos, "e", status="canceled", valor=0),
            _linha(m, planos, "f", "free", valor=0),
        ]
    )
    assert (resumo.assinaturas_ativas, resumo.mrr_centavos) == (2, 9980)


@pytest.mark.parametrize(("status", "esperado"), [("past_due", 1), ("unpaid", 1), ("canceled", 0), ("active", 0)])
def test_inadimplente_e_plano_pago_com_pagamento_pendente(m, planos, status, esperado):
    assert m.resumir_cobranca([_linha(m, planos, "a", status=status)]).inadimplentes == esperado


def test_free_com_status_estranho_nao_e_inadimplente(m, planos):
    assert m.resumir_cobranca([_linha(m, planos, "a", "free", "past_due", 0)]).inadimplentes == 0


def test_empresa_sem_linha_de_assinatura_conta_no_free(m, planos):
    contas = _contas(m, ("a", "A", {1, 2}), ("b", "B", {3}))
    fontes = _fontes(m, [_linha(m, planos, "a")], contas)

    r = m.consultar_metricas(*fontes)

    assert {p.plano: (p.empresas, p.usuarios) for p in r.por_plano} == {
        "free": (1, 1),
        "pro": (1, 2),
        "construtora": (0, 0),
    }
    assert (r.empresas_total, r.usuarios_total) == (2, 3)


def test_quem_tem_vinculo_em_duas_empresas_conta_uma_vez_por_plano(m, planos):
    contas = _contas(m, ("a", "A", {1, 9}), ("b", "B", {2, 9}), ("c", "C", {9}))
    linhas = [_linha(m, planos, "a"), _linha(m, planos, "b")]

    r = m.consultar_metricas(*_fontes(m, linhas, contas))

    assert {p.plano: p.usuarios for p in r.por_plano} == {"free": 1, "pro": 3, "construtora": 0}
    assert r.usuarios_total == 3


def test_sem_o_auth_service_a_cobranca_continua_e_os_usuarios_ficam_nulos(m, planos):
    r = m.consultar_metricas(*_fontes(m, [_linha(m, planos, "a")], None))

    assert r.usuarios_total is None and all(p.usuarios is None for p in r.por_plano)
    assert (r.empresas_total, r.mrr_formatado) == (1, "R$ 29,90")


def test_sem_o_log_service_os_eventos_ficam_nulos(m, planos):
    r = m.consultar_metricas(*_fontes(m, [], _contas(m), None))
    assert r.eventos is None


def test_evento_ganha_o_nome_do_ator_e_da_empresa(m):
    contas = _contas(m, ("a", "Rocha Reformas", {1}), nomes={1: "Jorge"})
    evento = m.EventoDaPlataforma("obra.criada", 1, "dono", "a", "2026-11-09T10:00:00Z")

    [no_painel] = m.consultar_metricas(*_fontes(m, [], contas, [evento])).eventos

    assert (no_painel.ator_nome, no_painel.empresa_nome) == ("Jorge", "Rocha Reformas")
    assert no_painel.quando == "2026-11-09T10:00:00Z"


def test_evento_de_quem_nao_existe_mais_mantem_os_ids(m):
    evento = m.EventoDaPlataforma("login", 7, None, "x", None)

    [no_painel] = m.consultar_metricas(*_fontes(m, [], _contas(m), [evento])).eventos

    assert (no_painel.ator_id, no_painel.ator_nome, no_painel.empresa_id, no_painel.empresa_nome) == (
        7,
        None,
        "x",
        None,
    )


def test_pede_no_maximo_os_ultimos_20_eventos(m):
    eventos = [m.EventoDaPlataforma(f"e{i}", None, None, None, None) for i in range(30)]
    assert len(m.consultar_metricas(*_fontes(m, [], _contas(m), eventos)).eventos) == 20
