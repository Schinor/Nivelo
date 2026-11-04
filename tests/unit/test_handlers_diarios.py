"""Casos de uso do diário com repositórios e unidade de trabalho em memória (sem banco)."""

import copy
import uuid
from datetime import UTC, date, datetime

import pytest

EMPRESA = uuid.UUID("0190f3a0-0000-7000-8000-00000000000a")
HOJE = date(2026, 11, 4)


@pytest.fixture
def m(api):
    class M:
        h = api("app.obras.application.handlers_diarios")
        c = api("app.obras.application.comandos")
        portas = api("app.obras.application.portas")
        erros = api("app.obras.domain.erros")
        obra = api("app.obras.domain.obra")
        valores = api("app.obras.domain.valores")
        ids = api("app.shared.domain.ids")
        obra_ids = api("app.obras.domain.ids")
        planos = api("app.assinaturas.domain.planos")
        ctx = api("app.shared.application.contexto")

    return M


class Relogio:
    def agora(self):
        return datetime(2026, 11, 4, 18, 0, tzinfo=UTC)

    def hoje(self):
        return HOJE


class Fakes:
    def __init__(self, m):
        self.diarios = {}
        self.commits = 0
        self.objetos = {}
        self.apagados = []
        fakes = self
        U = m.ids.UsuarioId
        v = m.valores
        self.obra = m.obra.Obra.criar(
            empresa_id=m.ids.EmpresaId(EMPRESA),
            nome="Casa",
            endereco=v.Endereco("Rua 1", "Marília", "SP"),
            cliente_nome="Jorge",
            periodo=v.Periodo(date(2026, 10, 1), date(2027, 1, 1)),
            ator=U(1),
        )
        self.obra.adicionar_membro(U(2), v.PapelDeMembro.ENCARREGADO, U(1))
        self.obra.adicionar_membro(U(3), v.PapelDeMembro.CLIENTE, U(1))

        class Obras:
            def obter(self, obra_id):
                if obra_id != fakes.obra.id:
                    raise m.erros.ObraNaoEncontrada()
                return fakes.obra

        class Diarios:
            def obter(self, diario_id):
                if diario_id not in fakes.diarios:
                    raise m.erros.DiarioNaoEncontrado()
                return copy.deepcopy(fakes.diarios[diario_id])

            def obter_pela_foto(self, foto_id):
                for d in fakes.diarios.values():
                    if any(f.id == foto_id for f in d.fotos):
                        return copy.deepcopy(d)
                raise m.erros.FotoNaoEncontrada()

            def existe_na_data(self, obra_id, data, exceto=None):
                return any(d.obra_id == obra_id and d.data == data and d.id != exceto for d in fakes.diarios.values())

            def adicionar(self, diario):
                fakes.diarios[diario.id] = copy.deepcopy(diario)

            def salvar(self, diario):
                if diario.removido:
                    del fakes.diarios[diario.id]
                    return
                diario.versao += 1
                fakes.diarios[diario.id] = copy.deepcopy(diario)

            def contar_fotos_da_obra(self, obra_id):
                return sum(len(d.fotos) for d in fakes.diarios.values() if d.obra_id == obra_id)

        class Direitos:
            def travar_e_obter(self, empresa_id):
                P = m.planos
                return P.direitos_efetivos(P.Plano.FREE, P.StatusAssinatura.ACTIVE)

        class Uow:
            obras = Obras()
            diarios = Diarios()
            direitos = Direitos()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def commit(self):
                fakes.commits += 1

            def rollback(self):
                pass

        class Storage:
            def url_para_enviar(self, chave, content_type, validade_s):
                return f"/storage/{chave}"

            def metadados(self, chave):
                return fakes.objetos.get(chave)

            def url_para_ler(self, chave, validade_s):
                return f"/storage/{chave}"

            def apagar(self, chave):
                fakes.apagados.append(chave)
                fakes.objetos.pop(chave, None)

        self.uow, self.storage = Uow(), Storage()


@pytest.fixture
def f(m):
    return Fakes(m)


def ctx(m, usuario=2, papel="encarregado"):
    return m.ctx.TenantContext(empresa_id=m.ids.EmpresaId(EMPRESA), usuario_id=usuario, papel=papel)


def registrar(m, f, data=date(2026, 11, 3), quem=None, **extras):
    dados = m.c.DadosDoDiario(data=data, atividades="Contrapiso", efetivo=3, **extras)
    return m.h.registrar_diario(m.c.RegistrarDiario(f.obra.id, dados), quem or ctx(m), f.uow, Relogio())


def test_registrar_grava_e_faz_commit(m, f):
    d = registrar(m, f)
    assert d.id in f.diarios and f.commits == 1 and d.autor_id.valor == 2


def test_diario_duplicado_no_mesmo_dia_e_recusado_antes_de_gravar(m, f):
    registrar(m, f)
    with pytest.raises(m.erros.DiarioDuplicado):
        registrar(m, f, quem=ctx(m, 1, "dono"))
    assert len(f.diarios) == 1 and f.commits == 1


def test_cliente_e_encarregado_de_fora_nao_enxergam_a_obra(m, f):
    with pytest.raises(m.erros.ObraNaoEncontrada):
        registrar(m, f, quem=ctx(m, 9, "encarregado"))
    d = registrar(m, f)
    with pytest.raises(m.erros.DiarioNaoEncontrado):
        m.h.diario_acessivel(f.uow, ctx(m, 3, "cliente"), d.id)  # rascunho
    m.h.publicar_diario(m.c.PublicarDiario(d.id), ctx(m), f.uow, Relogio())
    assert m.h.diario_acessivel(f.uow, ctx(m, 3, "cliente"), d.id).publicado


def test_editar_publicado_vira_revisao_e_exige_motivo(m, f):
    d = registrar(m, f)
    d = m.h.publicar_diario(m.c.PublicarDiario(d.id), ctx(m), f.uow, Relogio())
    dados = m.c.DadosDoDiario(data=d.data, atividades="Contrapiso", efetivo=5)
    with pytest.raises(m.erros.RevisaoSemMotivo):
        m.h.editar_diario(m.c.EditarDiario(d.id, d.versao, dados), ctx(m), f.uow, Relogio())
    revisado = m.h.editar_diario(
        m.c.EditarDiario(d.id, d.versao, dados, "Faltou um ajudante"), ctx(m), f.uow, Relogio()
    )
    assert revisado.conteudo.efetivo == 5


def test_encarregado_que_nao_e_o_autor_nao_revisa(m, f):
    d = registrar(m, f, quem=ctx(m, 1, "dono"))
    d = m.h.publicar_diario(m.c.PublicarDiario(d.id), ctx(m, 1, "dono"), f.uow, Relogio())
    dados = m.c.DadosDoDiario(data=d.data, atividades="Contrapiso", efetivo=5)
    with pytest.raises(m.erros.RevisaoNaoPermitida):
        m.h.editar_diario(m.c.EditarDiario(d.id, d.versao, dados, "Corrigir"), ctx(m), f.uow, Relogio())


def test_confirmar_foto_que_nao_chegou_ao_bucket_e_recusada(m, f):
    d = registrar(m, f)
    pedido = m.h.solicitar_upload_foto(m.c.SolicitarUploadFoto(d.id, "image/png", 1000), ctx(m), f.uow, f.storage)
    with pytest.raises(m.erros.FotoInvalida):
        m.h.confirmar_foto(m.c.ConfirmarFoto(d.id, pedido.object_key), ctx(m), f.uow, f.storage, Relogio())
    f.objetos[pedido.object_key] = m.portas.MetadadosDoObjeto(1000, "image/png")
    foto = m.h.confirmar_foto(m.c.ConfirmarFoto(d.id, pedido.object_key), ctx(m), f.uow, f.storage, Relogio())
    assert foto.id == pedido.foto_id and f.diarios[d.id].fotos == (foto,)


def test_remover_rascunho_apaga_as_fotos_do_bucket_depois_do_commit(m, f):
    d = registrar(m, f)
    pedido = m.h.solicitar_upload_foto(m.c.SolicitarUploadFoto(d.id, "image/jpeg", 1000), ctx(m), f.uow, f.storage)
    f.objetos[pedido.object_key] = m.portas.MetadadosDoObjeto(1000, "image/jpeg")
    m.h.confirmar_foto(m.c.ConfirmarFoto(d.id, pedido.object_key), ctx(m), f.uow, f.storage, Relogio())

    class StorageFora:
        def apagar(self, chave):
            raise ConnectionError("garage fora")

    # O storage fora do ar não desfaz a remoção (o objeto fica órfão, a referência sai)
    m.h.remover_diario(m.c.RemoverDiario(d.id), ctx(m, 1, "dono"), f.uow, StorageFora())
    assert d.id not in f.diarios
