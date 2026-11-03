"""Casos de uso de obras com repositório e unidade de trabalho em memória (sem banco)."""

import copy
import uuid
from datetime import UTC, date, datetime

import pytest

EMPRESA = uuid.UUID("0190f3a0-0000-7000-8000-00000000000a")


@pytest.fixture
def m(api):
    class M:
        h = api("app.obras.application.handlers")
        c = api("app.obras.application.comandos")
        erros = api("app.obras.domain.erros")
        ids = api("app.shared.domain.ids")
        obra_ids = api("app.obras.domain.ids")
        planos = api("app.assinaturas.domain.planos")
        erros_base = api("app.shared.domain.erros")
        ctx = api("app.shared.application.contexto")

    return M


class Fakes:
    def __init__(self, m, plano="free", status="active"):
        self.m = m
        self.salvas = {}  # obra_id -> obra (retrato do "banco")
        self.commits = 0
        self.travou = 0
        self.plano, self.status = plano, status
        fakes = self

        class Repo:
            def obter(self, obra_id):
                obra = fakes.salvas.get(obra_id)
                if obra is None or obra.removida_em is not None:
                    raise m.erros.ObraNaoEncontrada()
                return copy.deepcopy(obra)

            def adicionar(self, obra):
                fakes.salvas[obra.id] = copy.deepcopy(obra)

            def salvar(self, obra):
                no_banco = fakes.salvas[obra.id]
                if no_banco.versao != obra.versao:
                    raise m.erros_base.ConflitoDeVersao(versao_atual=no_banco.versao)
                obra.versao += 1
                fakes.salvas[obra.id] = copy.deepcopy(obra)

            def contar_ativas(self):
                return sum(1 for o in fakes.salvas.values() if o.ativa)

        class Direitos:
            def travar_e_obter(self, empresa_id):
                fakes.travou += 1
                P = m.planos
                return P.direitos_efetivos(P.Plano(fakes.plano), P.StatusAssinatura(fakes.status))

        class Uow:
            obras = Repo()
            direitos = Direitos()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def commit(self):
                fakes.commits += 1

            def rollback(self):
                pass

        self.uow = Uow()


@pytest.fixture
def f(m):
    return Fakes(m)


def ctx(m, papel="dono", usuario=1):
    return m.ctx.TenantContext(empresa_id=m.ids.EmpresaId(EMPRESA), usuario_id=usuario, papel=papel)


def dados(m, nome="Casa do Jorge", **extras):
    base = {
        "nome": nome,
        "logradouro": "Rua 1",
        "cidade": "Marília",
        "uf": "SP",
        "cliente_nome": "Jorge",
        "data_inicio": date(2026, 11, 3),
        "previsao_termino": date(2027, 3, 31),
    }
    return m.c.DadosDaObra(**{**base, **extras})


def criar(m, f, nome="Casa do Jorge"):
    return m.h.criar_obra(m.c.CriarObra(dados(m, nome)), ctx(m), f.uow)


# ── Plano ────────────────────────────────────────────────────────────────────


def test_criar_trava_a_assinatura_e_o_free_para_na_primeira_obra(m, f):
    criar(m, f)
    assert f.travou == 1 and f.commits == 1
    with pytest.raises(m.planos.LimiteDoPlanoExcedido) as erro:
        criar(m, f, "Segunda")
    assert erro.value.atual == 1 and erro.value.limite == 1
    assert len(f.salvas) == 1 and f.commits == 1  # a segunda não foi gravada


def test_obra_pausada_ou_removida_libera_a_vaga(m, f):
    obra = criar(m, f)
    m.h.alterar_status_obra(m.c.AlterarStatusObra(obra.id, "pausada"), ctx(m), f.uow)
    segunda = criar(m, f, "Segunda")
    # Reativar a primeira esbarra no limite: a segunda ocupa a vaga
    with pytest.raises(m.planos.LimiteDoPlanoExcedido):
        m.h.alterar_status_obra(m.c.AlterarStatusObra(obra.id, "ativa"), ctx(m), f.uow)

    class Relogio:
        def agora(self):
            return datetime(2026, 11, 3, tzinfo=UTC)

    m.h.remover_obra(m.c.RemoverObra(segunda.id), ctx(m), f.uow, Relogio())
    m.h.alterar_status_obra(m.c.AlterarStatusObra(obra.id, "ativa"), ctx(m), f.uow)
    assert f.salvas[obra.id].status.value == "ativa"


def test_pro_cria_varias_e_pro_inadimplente_cai_no_limite_do_free(m):
    pro = Fakes(m, plano="pro")
    for i in range(3):
        criar(m, pro, f"Obra {i}")
    atrasado = Fakes(m, plano="pro", status="past_due")
    criar(m, atrasado)
    with pytest.raises(m.planos.LimiteDoPlanoExcedido):
        criar(m, atrasado, "Segunda")


def test_concluir_nao_passa_pelo_plano(m, f):
    obra = criar(m, f)
    travou = f.travou
    m.h.alterar_status_obra(m.c.AlterarStatusObra(obra.id, "concluida"), ctx(m), f.uow)
    assert f.travou == travou


# ── Versão ───────────────────────────────────────────────────────────────────


def test_editar_com_versao_velha_e_conflito(m, f):
    obra = criar(m, f)
    m.h.editar_obra(m.c.EditarObra(obra.id, 1, dados(m, "Nome novo")), ctx(m), f.uow)
    assert f.salvas[obra.id].versao == 2
    with pytest.raises(m.erros_base.ConflitoDeVersao) as erro:
        m.h.editar_obra(m.c.EditarObra(obra.id, 1, dados(m, "Outro nome")), ctx(m), f.uow)
    assert erro.value.status == 409 and erro.value.extras() == {"versao_atual": 2}


def test_status_desconhecido_e_422(m, f):
    obra = criar(m, f)
    with pytest.raises(m.erros.TransicaoDeStatusInvalida):
        m.h.alterar_status_obra(m.c.AlterarStatusObra(obra.id, "demolida"), ctx(m), f.uow)


# ── Membros ──────────────────────────────────────────────────────────────────


class Equipe:
    def __init__(self, papeis):
        self.papeis, self.consultas = papeis, 0

    def papel_de(self, usuario_id):
        self.consultas += 1
        return self.papeis.get(usuario_id.valor)


def test_membro_precisa_ser_da_empresa_com_o_mesmo_papel(m, f):
    obra = criar(m, f)
    equipe = Equipe({2: "encarregado", 3: "cliente"})
    U = m.ids.UsuarioId

    m.h.adicionar_membro(m.c.AdicionarMembro(obra.id, U(2), "encarregado"), ctx(m), f.uow, equipe)
    assert [mb.usuario_id.valor for mb in f.salvas[obra.id].membros] == [2]

    with pytest.raises(m.erros.MembroInvalido, match="não faz parte da empresa"):
        m.h.adicionar_membro(m.c.AdicionarMembro(obra.id, U(99), "cliente"), ctx(m), f.uow, equipe)
    with pytest.raises(m.erros.MembroInvalido, match="como cliente e não pode entrar na obra como encarregado"):
        m.h.adicionar_membro(m.c.AdicionarMembro(obra.id, U(3), "encarregado"), ctx(m), f.uow, equipe)
    with pytest.raises(m.erros.MembroDuplicado):
        m.h.adicionar_membro(m.c.AdicionarMembro(obra.id, U(2), "encarregado"), ctx(m), f.uow, equipe)


def test_obra_inexistente_responde_404_sem_consultar_a_equipe(m, f):
    equipe = Equipe({2: "encarregado"})
    cmd = m.c.AdicionarMembro(m.obra_ids.ObraId.novo(), m.ids.UsuarioId(2), "encarregado")
    with pytest.raises(m.erros.ObraNaoEncontrada):
        m.h.adicionar_membro(cmd, ctx(m), f.uow, equipe)
    assert equipe.consultas == 0


def test_remover_membro_que_nao_existe_e_404(m, f):
    obra = criar(m, f)
    with pytest.raises(m.erros.MembroNaoEncontrado):
        m.h.remover_membro(m.c.RemoverMembro(obra.id, m.ids.UsuarioId(5)), ctx(m), f.uow)
