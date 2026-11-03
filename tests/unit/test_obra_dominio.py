"""Agregado Obra: cada invariante da Parte A.3, sem banco."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

EMPRESA = uuid.UUID("0190f3a0-0000-7000-8000-00000000000a")


@pytest.fixture
def d(api):
    """Módulos do domínio de obras."""

    class D:
        obra = api("app.obras.domain.obra")
        valores = api("app.obras.domain.valores")
        erros = api("app.obras.domain.erros")
        eventos = api("app.obras.domain.eventos")
        ids = api("app.shared.domain.ids")

    return D


def nova_obra(d, **extras):
    v = d.valores
    dados = {
        "empresa_id": d.ids.EmpresaId(EMPRESA),
        "nome": "Casa do Jorge",
        "endereco": v.Endereco("Rua das Acácias, 120", "Marília", "SP"),
        "cliente_nome": "Jorge",
        "periodo": v.Periodo(date(2026, 11, 3), date(2027, 3, 31)),
        "ator": d.ids.UsuarioId(1),
        **extras,
    }
    return d.obra.Obra.criar(**dados)


# ── Criação e value objects ──────────────────────────────────────────────────


def test_obra_nasce_ativa_com_versao_1_e_evento_obra_criada(d):
    obra = nova_obra(d)
    assert obra.status is d.valores.StatusObra.ATIVA and obra.ativa and obra.versao == 1
    eventos = obra.puxar_eventos()
    assert [e.tipo for e in eventos] == ["obra.criada"]
    assert eventos[0].ator_id.valor == 1 and eventos[0].empresa_id.valor == EMPRESA
    assert eventos[0].recurso == "obra" and eventos[0].recurso_id == str(obra.id)
    assert eventos[0].dados() == {"nome": "Casa do Jorge"}
    assert obra.puxar_eventos() == []  # puxar esvazia


def test_previsao_de_termino_antes_do_inicio_e_recusada(d):
    with pytest.raises(d.erros.PeriodoInvalido):
        d.valores.Periodo(date(2026, 11, 3), date(2026, 11, 2))
    assert d.valores.Periodo(date(2026, 11, 3), date(2026, 11, 3))  # mesmo dia vale


@pytest.mark.parametrize("uf", ["XX", "", "S", "São Paulo"])
def test_uf_precisa_ser_um_estado(d, uf):
    with pytest.raises(d.erros.DadoDaObraInvalido):
        d.valores.Endereco("Rua 1", "Marília", uf)


def test_endereco_normaliza_e_valida_coordenadas(d):
    e = d.valores.Endereco("  Rua 1 ", " Marília ", "sp", Decimal("-22.2"), Decimal("-49.9"))
    assert (e.logradouro, e.cidade, e.uf) == ("Rua 1", "Marília", "SP")
    with pytest.raises(d.erros.DadoDaObraInvalido):
        d.valores.Endereco("Rua 1", "Marília", "SP", Decimal("-22.2"), None)
    with pytest.raises(d.erros.DadoDaObraInvalido):
        d.valores.Endereco("Rua 1", "Marília", "SP", Decimal("91"), Decimal("0"))


@pytest.mark.parametrize("campo", ["nome", "cliente_nome"])
def test_nome_e_cliente_sao_obrigatorios(d, campo):
    with pytest.raises(d.erros.DadoDaObraInvalido):
        nova_obra(d, **{campo: "   "})


# ── Status ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "caminho",
    [["pausada"], ["pausada", "ativa"], ["concluida"], ["pausada", "concluida"], ["pausada", "ativa", "pausada"]],
)
def test_transicoes_validas(d, caminho):
    obra = nova_obra(d)
    obra.puxar_eventos()
    for status in caminho:
        obra.alterar_status(d.valores.StatusObra(status), d.ids.UsuarioId(1))
    assert obra.status.value == caminho[-1]
    eventos = obra.puxar_eventos()
    assert [e.tipo for e in eventos] == ["obra.status_alterado"] * len(caminho)
    assert eventos[-1].dados()["para"] == caminho[-1]


@pytest.mark.parametrize("depois", ["ativa", "pausada"])
def test_concluida_e_final(d, depois):
    obra = nova_obra(d)
    obra.alterar_status(d.valores.StatusObra.CONCLUIDA, d.ids.UsuarioId(1))
    with pytest.raises(d.erros.TransicaoDeStatusInvalida, match="concluída"):
        obra.alterar_status(d.valores.StatusObra(depois), d.ids.UsuarioId(1))


def test_mesmo_status_e_transicao_invalida(d):
    with pytest.raises(d.erros.TransicaoDeStatusInvalida, match="já está ativa"):
        nova_obra(d).alterar_status(d.valores.StatusObra.ATIVA, d.ids.UsuarioId(1))


# ── Edição e remoção ─────────────────────────────────────────────────────────


def test_editar_registra_so_os_campos_que_mudaram(d):
    obra = nova_obra(d)
    obra.puxar_eventos()
    obra.editar(
        nome="Casa do Jorge (2º piso)",
        endereco=obra.endereco,
        cliente_nome="Jorge",
        periodo=obra.periodo,
        ator=d.ids.UsuarioId(1),
    )
    [evento] = obra.puxar_eventos()
    assert evento.tipo == "obra.editada" and evento.dados() == {"campos": "nome"}

    # Sem mudança, sem evento
    obra.editar(
        nome=obra.nome, endereco=obra.endereco, cliente_nome="Jorge", periodo=obra.periodo, ator=d.ids.UsuarioId(1)
    )
    assert obra.puxar_eventos() == []


def test_obra_removida_nao_muda_mais(d):
    obra = nova_obra(d)
    obra.remover(d.ids.UsuarioId(1), datetime(2026, 11, 3, tzinfo=UTC))
    assert not obra.ativa and obra.puxar_eventos()[-1].tipo == "obra.removida"
    with pytest.raises(d.erros.ObraNaoEncontrada):
        obra.alterar_status(d.valores.StatusObra.PAUSADA, d.ids.UsuarioId(1))
    with pytest.raises(d.erros.ObraNaoEncontrada):
        obra.remover(d.ids.UsuarioId(1), datetime(2026, 11, 4, tzinfo=UTC))
    assert not obra.visivel_para(d.ids.UsuarioId(1), "dono")


# ── Membros ──────────────────────────────────────────────────────────────────


def test_membro_so_encarregado_ou_cliente(d):
    assert d.valores.PapelDeMembro.de_texto("cliente") is d.valores.PapelDeMembro.CLIENTE
    for papel in ("dono", "admin", ""):
        with pytest.raises(d.erros.MembroInvalido):
            d.valores.PapelDeMembro.de_texto(papel)


def test_mesmo_usuario_nao_entra_duas_vezes_nem_com_outro_papel(d):
    obra = nova_obra(d)
    P = d.valores.PapelDeMembro
    obra.adicionar_membro(d.ids.UsuarioId(2), P.ENCARREGADO, d.ids.UsuarioId(1))
    with pytest.raises(d.erros.MembroDuplicado):
        obra.adicionar_membro(d.ids.UsuarioId(2), P.ENCARREGADO, d.ids.UsuarioId(1))
    with pytest.raises(d.erros.MembroDuplicado):
        obra.adicionar_membro(d.ids.UsuarioId(2), P.CLIENTE, d.ids.UsuarioId(1))
    assert len(obra.membros) == 1


def test_adicionar_e_remover_membro_geram_eventos(d):
    obra = nova_obra(d)
    obra.puxar_eventos()
    obra.adicionar_membro(d.ids.UsuarioId(3), d.valores.PapelDeMembro.CLIENTE, d.ids.UsuarioId(1))
    obra.remover_membro(d.ids.UsuarioId(3), d.ids.UsuarioId(1))
    eventos = obra.puxar_eventos()
    assert [e.tipo for e in eventos] == ["obra.membro_adicionado", "obra.membro_removido"]
    assert eventos[0].dados() == {"usuario_id": 3, "papel": "cliente"}
    with pytest.raises(d.erros.MembroNaoEncontrado):
        obra.remover_membro(d.ids.UsuarioId(3), d.ids.UsuarioId(1))


def test_visibilidade_dono_ve_tudo_membro_so_com_o_proprio_papel(d):
    obra = nova_obra(d)
    obra.adicionar_membro(d.ids.UsuarioId(2), d.valores.PapelDeMembro.ENCARREGADO, d.ids.UsuarioId(1))
    assert obra.visivel_para(d.ids.UsuarioId(99), "dono")
    assert obra.visivel_para(d.ids.UsuarioId(2), "encarregado")
    assert not obra.visivel_para(d.ids.UsuarioId(2), "cliente")  # vínculo de outra empresa, papel diferente
    assert not obra.visivel_para(d.ids.UsuarioId(3), "cliente")


def test_usuario_id_precisa_ser_inteiro_positivo(d):
    for valor in (0, -1, True, "2"):
        with pytest.raises(ValueError):
            d.ids.UsuarioId(valor)
