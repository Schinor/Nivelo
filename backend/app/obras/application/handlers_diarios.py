"""Casos de uso de escrita do Diário de Obra: um handler por comando.

O papel de quem chama já foi conferido na borda (`requer_papel`). Aqui ficam as regras que
dependem do estado:
- acesso: a obra é da empresa (o repositório só enxerga o tenant), não foi removida e quem
  pede a enxerga (dono: todas; encarregado e cliente: as obras em que são membros). Sem
  acesso, 404, igual a "não existe". Cliente não enxerga rascunho;
- um diário por obra por dia (409), versão (409), plano de fotos (402) e as invariantes do
  agregado;
- revisão de diário publicado: dono revisa qualquer um, encarregado só os próprios (403).

Os objetos do bucket são apagados depois do commit, sem derrubar o caso de uso se o
storage falhar: um objeto órfão é melhor que uma referência para um objeto que sumiu.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.assinaturas.domain.planos import PoliticaDePlano
from app.obras.application.comandos import (
    Comentar,
    ConfirmarFoto,
    DadosDoDiario,
    EditarDiario,
    PublicarDiario,
    RegistrarDiario,
    RemoverDiario,
    RemoverFoto,
    SolicitarUploadFoto,
)
from app.obras.application.portas import ArmazenamentoDeFotos, UnidadeDeTrabalhoDeObras
from app.obras.domain.diario import Comentario, DiarioDeObra
from app.obras.domain.erros import (
    DiarioDuplicado,
    DiarioNaoEncontrado,
    FotoInvalida,
    FotoNaoEncontrada,
    ObraNaoEncontrada,
    RevisaoNaoPermitida,
)
from app.obras.domain.ids import DiarioId, FotoId, ObraId
from app.obras.domain.obra import Obra
from app.obras.domain.valores_do_diario import (
    Clima,
    CondicaoDeTrabalho,
    ConteudoDoDiario,
    FotoDoDiario,
    ObjectKey,
    Ocorrencia,
    Tempo,
    TipoOcorrencia,
    exigir_imagem_aceita,
)
from app.shared.application.contexto import TenantContext
from app.shared.domain.erros import ConflitoDeVersao
from app.shared.domain.ids import UsuarioId
from app.shared.domain.relogio import Relogio

logger = logging.getLogger("nivelo.api.diarios")

VALIDADE_DO_UPLOAD_S = 5 * 60
VALIDADE_DA_LEITURA_S = 10 * 60


def _ator(ctx: TenantContext) -> UsuarioId:
    return UsuarioId(ctx.usuario_id)


def conteudo_de(d: DadosDoDiario) -> ConteudoDoDiario:
    return ConteudoDoDiario(
        clima=Clima(
            Tempo.de_texto(d.clima_manha) if d.clima_manha else None,
            Tempo.de_texto(d.clima_tarde) if d.clima_tarde else None,
        ),
        condicao=CondicaoDeTrabalho.de_texto(d.condicao),
        atividades=d.atividades,
        efetivo=d.efetivo,
        observacoes=d.observacoes,
        ocorrencias=tuple(
            Ocorrencia(TipoOcorrencia.de_texto(o.tipo), o.descricao, o.impacto_prazo_dias) for o in d.ocorrencias
        ),
    )


def obra_acessivel(uow: UnidadeDeTrabalhoDeObras, ctx: TenantContext, obra_id: ObraId) -> Obra:
    obra = uow.obras.obter(obra_id)
    if not obra.visivel_para(_ator(ctx), ctx.papel):
        raise ObraNaoEncontrada()
    return obra


def _acessivel(uow: UnidadeDeTrabalhoDeObras, ctx: TenantContext, diario: DiarioDeObra) -> DiarioDeObra:
    try:
        obra_acessivel(uow, ctx, diario.obra_id)
    except ObraNaoEncontrada:
        raise DiarioNaoEncontrado() from None
    if ctx.papel == "cliente" and not diario.publicado:
        raise DiarioNaoEncontrado()
    return diario


def diario_acessivel(uow: UnidadeDeTrabalhoDeObras, ctx: TenantContext, diario_id: DiarioId) -> DiarioDeObra:
    return _acessivel(uow, ctx, uow.diarios.obter(diario_id))


def _conferir_versao(diario: DiarioDeObra, esperada: int | None) -> None:
    if esperada is not None and esperada != diario.versao:
        raise ConflitoDeVersao(versao_atual=diario.versao)


def _apagar_do_bucket(armazenamento: ArmazenamentoDeFotos, chaves: list[str]) -> None:
    for chave in chaves:
        try:
            armazenamento.apagar(chave)
        except Exception:
            logger.warning("não foi possível apagar o objeto %s do bucket (fica órfão)", chave, exc_info=True)


# ── Diário ───────────────────────────────────────────────────────────────────


def registrar_diario(
    cmd: RegistrarDiario, ctx: TenantContext, uow: UnidadeDeTrabalhoDeObras, relogio: Relogio
) -> DiarioDeObra:
    conteudo = conteudo_de(cmd.dados)
    with uow:
        obra = obra_acessivel(uow, ctx, cmd.obra_id)
        diario = DiarioDeObra.registrar(
            empresa_id=ctx.empresa_id,
            obra_id=obra.id,
            data=cmd.dados.data,
            conteudo=conteudo,
            autor=_ator(ctx),
            hoje=relogio.hoje(),
        )
        if uow.diarios.existe_na_data(obra.id, diario.data):
            raise DiarioDuplicado()
        uow.diarios.adicionar(diario)
        uow.commit()
    return diario


def editar_diario(
    cmd: EditarDiario, ctx: TenantContext, uow: UnidadeDeTrabalhoDeObras, relogio: Relogio
) -> DiarioDeObra:
    conteudo = conteudo_de(cmd.dados)
    with uow:
        diario = diario_acessivel(uow, ctx, cmd.diario_id)
        _conferir_versao(diario, cmd.versao_esperada)
        ator = _ator(ctx)
        if diario.publicado and not diario.pode_ser_revisado_por(ator, ctx.papel):
            raise RevisaoNaoPermitida()
        if cmd.dados.data != diario.data and uow.diarios.existe_na_data(diario.obra_id, cmd.dados.data, diario.id):
            raise DiarioDuplicado()
        if diario.publicado:
            diario.revisar(
                conteudo=conteudo,
                data=cmd.dados.data,
                motivo=cmd.motivo,
                ator=ator,
                quando=relogio.agora(),
                hoje=relogio.hoje(),
            )
        else:
            diario.editar(conteudo=conteudo, data=cmd.dados.data, ator=ator, hoje=relogio.hoje())
        uow.diarios.salvar(diario)
        uow.commit()
    return diario


def publicar_diario(
    cmd: PublicarDiario, ctx: TenantContext, uow: UnidadeDeTrabalhoDeObras, relogio: Relogio
) -> DiarioDeObra:
    with uow:
        diario = diario_acessivel(uow, ctx, cmd.diario_id)
        _conferir_versao(diario, cmd.versao_esperada)
        diario.publicar(_ator(ctx), relogio.agora())
        uow.diarios.salvar(diario)
        uow.commit()
    return diario


def remover_diario(
    cmd: RemoverDiario, ctx: TenantContext, uow: UnidadeDeTrabalhoDeObras, armazenamento: ArmazenamentoDeFotos
) -> None:
    with uow:
        diario = diario_acessivel(uow, ctx, cmd.diario_id)
        _conferir_versao(diario, cmd.versao_esperada)
        chaves = [str(f.object_key) for f in diario.fotos]
        diario.remover(_ator(ctx))
        uow.diarios.salvar(diario)
        uow.commit()
    _apagar_do_bucket(armazenamento, chaves)


def comentar(cmd: Comentar, ctx: TenantContext, uow: UnidadeDeTrabalhoDeObras, relogio: Relogio) -> Comentario:
    with uow:
        diario = diario_acessivel(uow, ctx, cmd.diario_id)
        comentario = diario.comentar(cmd.texto, _ator(ctx), relogio.agora())
        uow.diarios.salvar(diario)
        uow.commit()
    return comentario


# ── Fotos ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PedidoDeUpload:
    foto_id: FotoId
    object_key: str
    url: str
    content_type: str
    validade_s: int


def _exigir_vaga_de_foto(uow: UnidadeDeTrabalhoDeObras, ctx: TenantContext, diario: DiarioDeObra) -> None:
    # Trava a assinatura antes de contar, como nas obras (ADR 006 e 011)
    efetivos = uow.direitos.travar_e_obter(ctx.empresa_id)
    PoliticaDePlano.exigir_vaga_de_foto(efetivos, uow.diarios.contar_fotos_da_obra(diario.obra_id))


def solicitar_upload_foto(
    cmd: SolicitarUploadFoto, ctx: TenantContext, uow: UnidadeDeTrabalhoDeObras, armazenamento: ArmazenamentoDeFotos
) -> PedidoDeUpload:
    """Só assina a URL: nada é gravado até a confirmação. O plano é conferido aqui, para não
    deixar enviar o que vai ser recusado, e de novo na confirmação, que é quem grava."""
    exigir_imagem_aceita(cmd.content_type, cmd.tamanho_bytes)
    with uow:
        diario = diario_acessivel(uow, ctx, cmd.diario_id)
        _exigir_vaga_de_foto(uow, ctx, diario)
    foto_id = FotoId.novo()
    chave = ObjectKey.para_foto(ctx.empresa_id, diario.obra_id, diario.id, foto_id, cmd.content_type)
    url = armazenamento.url_para_enviar(str(chave), cmd.content_type, VALIDADE_DO_UPLOAD_S)
    return PedidoDeUpload(
        foto_id=foto_id, object_key=str(chave), url=url, content_type=cmd.content_type, validade_s=VALIDADE_DO_UPLOAD_S
    )


def confirmar_foto(
    cmd: ConfirmarFoto,
    ctx: TenantContext,
    uow: UnidadeDeTrabalhoDeObras,
    armazenamento: ArmazenamentoDeFotos,
    relogio: Relogio,
) -> FotoDoDiario:
    """Confere o objeto no bucket (`HEAD`) e grava a referência. Idempotente."""
    chave = ObjectKey(cmd.object_key)
    with uow:
        diario = diario_acessivel(uow, ctx, cmd.diario_id)
        if not chave.pertence_a(ctx.empresa_id, diario.obra_id, diario.id):
            raise FotoInvalida("Essa foto não foi enviada para este diário.")
        ja_anexada = next((f for f in diario.fotos if f.id == chave.foto_id), None)
        if ja_anexada is not None:
            return ja_anexada
        meta = armazenamento.metadados(str(chave))
        if meta is None:
            raise FotoInvalida("A foto ainda não chegou ao armazenamento. Envie o arquivo pela URL e confirme de novo.")
        try:
            foto = FotoDoDiario(
                id=chave.foto_id,
                object_key=chave,
                content_type=meta.content_type,
                tamanho_bytes=meta.tamanho_bytes,
                enviado_por=_ator(ctx),
                legenda=cmd.legenda,
                criado_em=relogio.agora(),
            )
            _exigir_vaga_de_foto(uow, ctx, diario)
        except Exception:
            # O objeto enviado não vai ser usado: não deixa lixo no bucket
            _apagar_do_bucket(armazenamento, [str(chave)])
            raise
        foto = diario.anexar_foto(foto, _ator(ctx))
        uow.diarios.salvar(diario)
        uow.commit()
    return foto


def remover_foto(
    cmd: RemoverFoto, ctx: TenantContext, uow: UnidadeDeTrabalhoDeObras, armazenamento: ArmazenamentoDeFotos
) -> None:
    with uow:
        try:
            diario = _acessivel(uow, ctx, uow.diarios.obter_pela_foto(cmd.foto_id))
        except DiarioNaoEncontrado:
            raise FotoNaoEncontrada() from None
        foto = diario.remover_foto(cmd.foto_id, _ator(ctx))
        uow.diarios.salvar(diario)
        uow.commit()
    _apagar_do_bucket(armazenamento, [str(foto.object_key)])
