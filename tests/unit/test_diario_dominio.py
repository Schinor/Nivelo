"""Agregado DiarioDeObra: cada invariante da Parte A.3, sem banco."""

import uuid
from datetime import UTC, date, datetime

import pytest

EMPRESA = uuid.UUID("0190f3a0-0000-7000-8000-00000000000a")
OUTRA_EMPRESA = uuid.UUID("0190f3a0-0000-7000-8000-00000000000b")
OBRA = uuid.UUID("0190f3a0-0000-7000-8000-0000000000a1")
HOJE = date(2026, 11, 4)
AGORA = datetime(2026, 11, 4, 18, 0, tzinfo=UTC)


@pytest.fixture
def d(api):
    class D:
        diario = api("app.obras.domain.diario")
        v = api("app.obras.domain.valores_do_diario")
        erros = api("app.obras.domain.erros")
        ids = api("app.obras.domain.ids")
        sids = api("app.shared.domain.ids")
        planos = api("app.assinaturas.domain.planos")

    return D


def U(d, n):
    return d.sids.UsuarioId(n)


def conteudo(d, **extras):
    v = d.v
    base = {
        "clima": v.Clima(v.Tempo.ENSOLARADO, v.Tempo.CHUVOSO),
        "condicao": v.CondicaoDeTrabalho.PRATICAVEL,
        "atividades": "Contrapiso da cozinha",
        "efetivo": 4,
    }
    return v.ConteudoDoDiario(**{**base, **extras})


def novo(d, data=HOJE, autor=2, **extras):
    return d.diario.DiarioDeObra.registrar(
        empresa_id=d.sids.EmpresaId(EMPRESA),
        obra_id=d.ids.ObraId(OBRA),
        data=data,
        conteudo=conteudo(d, **extras),
        autor=U(d, autor),
        hoje=HOJE,
    )


def publicado(d, **extras):
    diario = novo(d, **extras)
    diario.publicar(U(d, 2), AGORA)
    diario.puxar_eventos()
    return diario


def ocorrencia(d, descricao="Chuva forte às 13h", impacto=1):
    return d.v.Ocorrencia(d.v.TipoOcorrencia.CHUVA, descricao, impacto)


# ── Registro ─────────────────────────────────────────────────────────────────


def test_diario_nasce_rascunho_com_evento_e_um_evento_por_ocorrencia(d):
    diario = novo(d, ocorrencias=(ocorrencia(d),))
    assert diario.status is d.v.StatusDiario.RASCUNHO and diario.versao == 1 and not diario.publicado
    eventos = diario.puxar_eventos()
    assert [e.tipo for e in eventos] == ["diario.registrado", "ocorrencia.registrada"]
    assert eventos[0].recurso == "diario" and eventos[0].recurso_id == str(diario.id)
    assert eventos[0].dados() == {"obra_id": str(OBRA), "diario_id": str(diario.id), "data": "2026-11-04"}
    assert eventos[1].dados()["tipo"] == "chuva" and eventos[1].dados()["impacto_prazo_dias"] == 1


def test_diario_de_hoje_e_do_passado_vale_e_futuro_e_recusado(d):
    assert novo(d, data=date(2026, 10, 1))
    with pytest.raises(d.erros.DataDoDiarioFutura):
        novo(d, data=date(2026, 11, 5))


@pytest.mark.parametrize(
    "campo, valor",
    [("efetivo", -1), ("efetivo", 10_001), ("efetivo", True), ("atividades", "x" * 10_001)],
)
def test_conteudo_invalido_e_recusado(d, campo, valor):
    with pytest.raises(d.erros.DadoDoDiarioInvalido):
        conteudo(d, **{campo: valor})


def test_ocorrencia_exige_descricao_e_impacto_entre_0_e_365(d):
    with pytest.raises(d.erros.DadoDoDiarioInvalido):
        ocorrencia(d, descricao="  ")
    with pytest.raises(d.erros.DadoDoDiarioInvalido):
        ocorrencia(d, impacto=-1)
    with pytest.raises(d.erros.DadoDoDiarioInvalido):
        d.v.TipoOcorrencia.de_texto("enchente")
    assert ocorrencia(d, impacto=None).impacto_prazo_dias is None


def test_clima_e_condicao_aceitam_so_os_valores_do_glossario(d):
    with pytest.raises(d.erros.DadoDoDiarioInvalido):
        d.v.Tempo.de_texto("granizo")
    with pytest.raises(d.erros.DadoDoDiarioInvalido):
        d.v.CondicaoDeTrabalho.de_texto("mais_ou_menos")


# ── Rascunho e publicação ────────────────────────────────────────────────────


def test_editar_rascunho_registra_os_campos_e_mantem_o_id_das_ocorrencias_iguais(d):
    antiga = ocorrencia(d)
    diario = novo(d, ocorrencias=(antiga,))
    diario.puxar_eventos()
    nova = ocorrencia(d, "Faltou cimento", None)
    campos = diario.editar(
        conteudo=conteudo(d, efetivo=5, ocorrencias=(ocorrencia(d), nova)), data=HOJE, ator=U(d, 2), hoje=HOJE
    )
    assert campos == ("efetivo", "ocorrencias")
    assert [o.id for o in diario.conteudo.ocorrencias] == [antiga.id, nova.id]
    assert [e.tipo for e in diario.puxar_eventos()] == ["ocorrencia.registrada", "diario.editado"]


def test_editar_sem_mudanca_nao_gera_evento(d):
    diario = novo(d)
    diario.puxar_eventos()
    assert diario.editar(conteudo=conteudo(d), data=HOJE, ator=U(d, 2), hoje=HOJE) == ()
    assert diario.puxar_eventos() == []


def test_editar_para_data_futura_e_recusado(d):
    with pytest.raises(d.erros.DataDoDiarioFutura):
        novo(d).editar(conteudo=conteudo(d), data=date(2026, 11, 5), ator=U(d, 2), hoje=HOJE)


def test_publicar_exige_atividades(d):
    diario = novo(d, atividades="   ")
    with pytest.raises(d.erros.PublicacaoSemAtividades):
        diario.publicar(U(d, 2), AGORA)
    assert not diario.publicado


def test_publicar_muda_o_status_e_gera_evento_e_nao_publica_duas_vezes(d):
    diario = novo(d)
    diario.puxar_eventos()
    diario.publicar(U(d, 2), AGORA)
    assert diario.publicado and diario.publicado_em == AGORA
    assert [e.tipo for e in diario.puxar_eventos()] == ["diario.publicado"]
    with pytest.raises(d.erros.DiarioJaPublicado):
        diario.publicar(U(d, 2), AGORA)


def test_remover_so_rascunho(d):
    rascunho = novo(d)
    rascunho.puxar_eventos()
    rascunho.remover(U(d, 1))
    assert rascunho.removido and [e.tipo for e in rascunho.puxar_eventos()] == ["diario.removido"]
    with pytest.raises(d.erros.DiarioJaPublicado):
        publicado(d).remover(U(d, 1))


# ── Publicado: revisão com motivo ────────────────────────────────────────────


def test_editar_publicado_sem_revisao_e_recusado(d):
    diario = publicado(d)
    with pytest.raises(d.erros.DiarioJaPublicado):
        diario.editar(conteudo=conteudo(d, efetivo=9), data=HOJE, ator=U(d, 2), hoje=HOJE)
    assert diario.conteudo.efetivo == 4


@pytest.mark.parametrize("motivo", [None, "", "   ", "abc", "x" * 501])
def test_revisar_publicado_sem_motivo_valido_e_recusado(d, motivo):
    diario = publicado(d)
    with pytest.raises(d.erros.RevisaoSemMotivo):
        diario.revisar(conteudo=conteudo(d, efetivo=9), data=HOJE, motivo=motivo, ator=U(d, 2), quando=AGORA, hoje=HOJE)
    assert diario.conteudo.efetivo == 4 and diario.puxar_revisoes_novas() == []


def test_revisar_guarda_o_retrato_anterior_e_gera_diario_revisado(d):
    diario = publicado(d, ocorrencias=(ocorrencia(d),))
    revisao = diario.revisar(
        conteudo=conteudo(d, efetivo=6, ocorrencias=(ocorrencia(d),)),
        data=HOJE,
        motivo="Faltou contar 2 ajudantes",
        ator=U(d, 1),
        quando=AGORA,
        hoje=HOJE,
    )
    assert diario.conteudo.efetivo == 6 and diario.publicado
    assert revisao.versao_anterior == 1 and revisao.motivo == "Faltou contar 2 ajudantes"
    assert revisao.retrato["efetivo"] == 4 and revisao.retrato["data"] == "2026-11-04"
    assert revisao.retrato["ocorrencias"][0]["tipo"] == "chuva"
    assert diario.puxar_revisoes_novas() == [revisao]
    eventos = diario.puxar_eventos()
    assert [e.tipo for e in eventos] == ["diario.revisado"]
    assert eventos[0].dados()["campos"] == "efetivo" and eventos[0].dados()["versao_anterior"] == 1


def test_revisao_sem_mudanca_e_recusada(d):
    diario = publicado(d)
    with pytest.raises(d.erros.RevisaoSemMudanca):
        diario.revisar(conteudo=conteudo(d), data=HOJE, motivo="Só conferindo", ator=U(d, 1), quando=AGORA, hoje=HOJE)


def test_revisao_nao_pode_apagar_as_atividades_nem_valer_para_rascunho(d):
    with pytest.raises(d.erros.PublicacaoSemAtividades):
        publicado(d).revisar(
            conteudo=conteudo(d, atividades=None),
            data=HOJE,
            motivo="Apagar tudo",
            ator=U(d, 1),
            quando=AGORA,
            hoje=HOJE,
        )
    with pytest.raises(d.erros.DiarioNaoPublicado):
        novo(d).revisar(
            conteudo=conteudo(d, efetivo=9), data=HOJE, motivo="Rascunho", ator=U(d, 1), quando=AGORA, hoje=HOJE
        )


def test_dono_revisa_qualquer_diario_e_encarregado_so_os_proprios(d):
    diario = publicado(d, autor=2)
    assert diario.pode_ser_revisado_por(U(d, 1), "dono")
    assert diario.pode_ser_revisado_por(U(d, 2), "encarregado")
    assert not diario.pode_ser_revisado_por(U(d, 7), "encarregado")
    assert not diario.pode_ser_revisado_por(U(d, 2), "cliente")


# ── Fotos ────────────────────────────────────────────────────────────────────


def foto(d, diario, content_type="image/jpeg", empresa=EMPRESA, tamanho=200_000):
    foto_id = d.ids.FotoId.novo()
    chave = d.v.ObjectKey.para_foto(d.sids.EmpresaId(empresa), diario.obra_id, diario.id, foto_id, content_type)
    return d.v.FotoDoDiario(
        id=foto_id, object_key=chave, content_type=content_type, tamanho_bytes=tamanho, enviado_por=U(d, 2)
    )


def test_object_key_segue_o_formato_e_diz_a_quem_pertence(d):
    diario = novo(d)
    f = foto(d, diario, "image/webp")
    assert str(f.object_key) == f"empresas/{EMPRESA}/obras/{OBRA}/diarios/{diario.id}/{f.id}.webp"
    assert f.object_key.foto_id == f.id and f.object_key.content_type == "image/webp"
    assert f.object_key.pertence_a(diario.empresa_id, diario.obra_id, diario.id)
    for ruim in ["../etc/passwd", f"empresas/{EMPRESA}/x.jpg", str(f.object_key).replace(".webp", ".gif")]:
        with pytest.raises(d.erros.FotoInvalida):
            d.v.ObjectKey(ruim)


@pytest.mark.parametrize(
    "content_type, tamanho", [("image/gif", 1000), ("image/jpeg", 0), ("image/jpeg", 5 * 1024 * 1024 + 1)]
)
def test_foto_so_jpeg_png_webp_ate_5_mb(d, content_type, tamanho):
    with pytest.raises(d.erros.FotoInvalida):
        d.v.exigir_imagem_aceita(content_type, tamanho)


def test_anexar_foto_gera_evento_e_e_idempotente(d):
    diario = novo(d)
    diario.puxar_eventos()
    f = foto(d, diario)
    diario.anexar_foto(f, U(d, 2))
    assert diario.anexar_foto(f, U(d, 2)) is f and diario.fotos == (f,)
    eventos = diario.puxar_eventos()
    assert [e.tipo for e in eventos] == ["foto.anexada"]
    assert eventos[0].recurso == "foto" and eventos[0].recurso_id == str(f.id)
    assert eventos[0].dados()["object_key"] == str(f.object_key)


def test_foto_de_outro_diario_ou_de_outra_empresa_nao_e_anexada(d):
    diario, outro = novo(d), novo(d, data=date(2026, 11, 3))
    with pytest.raises(d.erros.FotoInvalida):
        diario.anexar_foto(foto(d, outro), U(d, 2))
    with pytest.raises(d.erros.FotoInvalida):
        diario.anexar_foto(foto(d, diario, empresa=OUTRA_EMPRESA), U(d, 2))


def test_publicado_aceita_foto_nova_mas_nao_remove_foto(d):
    diario = publicado(d)
    f = diario.anexar_foto(foto(d, diario), U(d, 2))
    with pytest.raises(d.erros.DiarioJaPublicado):
        diario.remover_foto(f.id, U(d, 2))
    rascunho = novo(d)
    g = rascunho.anexar_foto(foto(d, rascunho), U(d, 2))
    assert rascunho.remover_foto(g.id, U(d, 2)) is g and rascunho.fotos == ()
    with pytest.raises(d.erros.FotoNaoEncontrada):
        rascunho.remover_foto(g.id, U(d, 2))


def test_politica_de_fotos_do_plano(d):
    p = d.planos
    free = p.direitos_efetivos(p.Plano.FREE, p.StatusAssinatura.ACTIVE)
    p.PoliticaDePlano.exigir_vaga_de_foto(free, 29)
    with pytest.raises(p.LimiteDoPlanoExcedido) as erro:
        p.PoliticaDePlano.exigir_vaga_de_foto(free, 30)
    assert erro.value.extras()["limite"] == 30 and erro.value.extras()["plano_sugerido"] == "pro"
    p.PoliticaDePlano.exigir_vaga_de_foto(p.direitos_efetivos(p.Plano.PRO, p.StatusAssinatura.ACTIVE), 5000)


# ── Comentários ──────────────────────────────────────────────────────────────


def test_comentario_so_em_diario_publicado_e_com_texto(d):
    with pytest.raises(d.erros.DiarioNaoPublicado):
        novo(d).comentar("Ficou ótimo", U(d, 3), AGORA)
    diario = publicado(d)
    with pytest.raises(d.erros.ComentarioInvalido):
        diario.comentar("   ", U(d, 3), AGORA)
    c = diario.comentar("  Ficou ótimo  ", U(d, 3), AGORA)
    assert c.texto == "Ficou ótimo" and diario.puxar_comentarios_novos() == [c]
    assert [e.tipo for e in diario.puxar_eventos()] == ["comentario.registrado"]
