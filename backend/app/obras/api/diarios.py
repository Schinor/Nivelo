"""Rotas do Diário de Obra: diários, ocorrências, revisões, fotos e comentários.

- O papel é conferido aqui (`requer_papel`, 403 auditado); o resto das regras vem dos handlers.
- A empresa vem só do token. Diário de outra empresa, de obra sem acesso ou (para o cliente)
  em rascunho responde 404; quando é de outra empresa, a auditoria registra
  `recurso.nao_encontrado_outro_tenant` (a resposta não muda).
- Diário publicado não é sobrescrito: o PUT exige `motivo` e vira revisão. Encarregado só
  revisa os diários que ele registrou (403).
- Fotos: o navegador pede a URL (`upload-url`), faz PUT direto no storage pela ponte
  /storage e confirma (`POST .../fotos`); a API confere o objeto e grava a referência.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.obras.api.dependencias import (
    armazenamento_de_fotos,
    auditando_404,
    exigir_versao,
    relogio,
    unidade_de_trabalho,
    versao,
    versao_do_if_match,
)
from app.obras.api.schemas_diarios import (
    ClimaIn,
    ComentarioIn,
    ComentarioOut,
    DiarioEdicaoIn,
    DiarioIn,
    DiarioOut,
    FotoConfirmacaoIn,
    FotoOut,
    OcorrenciaOut,
    PaginaDeComentariosOut,
    PaginaDeDiariosOut,
    PedidoDeUploadIn,
    RevisaoOut,
    StatusDiarioTexto,
    UploadUrlOut,
    UrlDaFotoOut,
    VersaoIn,
)
from app.obras.application import handlers_diarios as h
from app.obras.application.comandos import (
    Comentar,
    ConfirmarFoto,
    EditarDiario,
    PublicarDiario,
    RegistrarDiario,
    RemoverDiario,
    RemoverFoto,
    SolicitarUploadFoto,
)
from app.obras.application.consultas import DiarioDetalhe
from app.obras.application.portas import ArmazenamentoDeFotos
from app.obras.domain.ids import DiarioId, FotoId, ObraId
from app.obras.infrastructure.consultas_de_diarios import ConsultaDeDiariosSQL
from app.obras.infrastructure.modelos import DiarioFotoModel, DiarioModel, ObraModel
from app.obras.infrastructure.unidade_de_trabalho import UnidadeDeTrabalhoDeObrasSQL
from app.shared.api.autenticacao import requer_papel, tenant
from app.shared.api.sessao import sessao_do_tenant
from app.shared.application.contexto import TenantContext
from app.shared.application.paginacao import POR_PAGINA_MAXIMO, POR_PAGINA_PADRAO, PedidoDePagina
from app.shared.domain.relogio import Relogio

router = APIRouter(prefix="/api", tags=["diarios"])

R = dict[int | str, dict[str, Any]]
SEM_TENANT_OU_PAPEL: R = {
    401: {"description": "Sem token ou token inválido"},
    403: {"description": "Token sem empresa ativa, ou papel sem permissão para a ação"},
}
DIARIO_404: R = {404: {"description": "Diário inexistente, de outra empresa, de obra sem acesso ou rascunho (cliente)"}}
FOTO_404: R = {404: {"description": "Foto inexistente, de outra empresa ou sem acesso"}}
INVALIDO: R = {422: {"description": "Dados inválidos ou regra do diário violada (Problem Details com type próprio)"}}
CONFLITO: R = {409: {"description": "Versão divergente, diário duplicado no dia, ou ação que não vale no status"}}
LIMITE: R = {402: {"description": "Limite de fotos por obra do plano (Problem Details com limite e uso)"}}

ESCREVE = requer_papel("dono", "encarregado")


def _saida(d: DiarioDetalhe, response: Response) -> DiarioOut:
    response.headers["ETag"] = f'"{d.versao}"'
    return DiarioOut(
        id=d.id,
        obra_id=d.obra_id,
        data=d.data,
        clima=ClimaIn.model_validate({"manha": d.clima_manha, "tarde": d.clima_tarde}),
        condicao=d.condicao,
        atividades=d.atividades,
        efetivo=d.efetivo,
        observacoes=d.observacoes,
        status=d.status,
        autor_id=d.autor_id,
        versao=d.versao,
        publicado_em=d.publicado_em,
        criado_em=d.criado_em,
        atualizado_em=d.atualizado_em,
        ocorrencias=[OcorrenciaOut.model_validate(asdict(o)) for o in d.ocorrencias],
        fotos=[FotoOut.model_validate(asdict(f)) for f in d.fotos],
        revisoes=d.revisoes,
    )


def _detalhe(db: Session, ctx: TenantContext, diario_id: DiarioId, response: Response) -> DiarioOut:
    return _saida(ConsultaDeDiariosSQL(db).detalhar(ctx, diario_id), response)


# ── Diários de uma obra ──────────────────────────────────────────────────────


@router.get(
    "/obras/{obra_id}/diarios",
    response_model=PaginaDeDiariosOut,
    responses={
        **SEM_TENANT_OU_PAPEL,
        404: {"description": "Obra inexistente, removida, de outra empresa ou sem acesso"},
    },
)
def listar_diarios(
    obra_id: uuid.UUID,
    request: Request,
    ctx: TenantContext = Depends(tenant),
    db: Session = Depends(sessao_do_tenant),
    status_: StatusDiarioTexto | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=POR_PAGINA_PADRAO, ge=1, le=POR_PAGINA_MAXIMO),
) -> Any:
    """Membros da obra e o dono, do dia mais recente para o mais antigo. O cliente só vê os
    publicados."""
    with auditando_404(request, db, ctx, {ObraModel: obra_id}):
        return ConsultaDeDiariosSQL(db).listar(ctx, ObraId(obra_id), status_, PedidoDePagina(page, por_pagina))


@router.post(
    "/obras/{obra_id}/diarios",
    status_code=status.HTTP_201_CREATED,
    response_model=DiarioOut,
    responses={
        **SEM_TENANT_OU_PAPEL,
        404: {"description": "Obra inexistente, removida, de outra empresa ou sem acesso"},
        409: {"description": "Já existe diário desta obra nesse dia"},
        **INVALIDO,
    },
)
def registrar_diario(
    obra_id: uuid.UUID,
    payload: DiarioIn,
    request: Request,
    response: Response,
    ctx: TenantContext = Depends(ESCREVE),
    uow: UnidadeDeTrabalhoDeObrasSQL = Depends(unidade_de_trabalho),
    db: Session = Depends(sessao_do_tenant),
    agora: Relogio = Depends(relogio),
) -> DiarioOut:
    """Dono e encarregado (nas obras em que é membro). O diário nasce rascunho."""
    with auditando_404(request, db, ctx, {ObraModel: obra_id}):
        diario = h.registrar_diario(RegistrarDiario(ObraId(obra_id), payload.para_dados()), ctx, uow, agora)
    response.headers["Location"] = f"/api/diarios/{diario.id}"
    return _detalhe(db, ctx, diario.id, response)


# ── Um diário ────────────────────────────────────────────────────────────────


@router.get("/diarios/{diario_id}", response_model=DiarioOut, responses={**SEM_TENANT_OU_PAPEL, **DIARIO_404})
def detalhar_diario(
    diario_id: uuid.UUID,
    request: Request,
    response: Response,
    ctx: TenantContext = Depends(tenant),
    db: Session = Depends(sessao_do_tenant),
) -> DiarioOut:
    """Membros da obra e o dono. O cliente só vê o diário publicado."""
    with auditando_404(request, db, ctx, {DiarioModel: diario_id}):
        return _detalhe(db, ctx, DiarioId(diario_id), response)


@router.put(
    "/diarios/{diario_id}",
    response_model=DiarioOut,
    responses={
        **SEM_TENANT_OU_PAPEL,
        **DIARIO_404,
        **CONFLITO,
        **INVALIDO,
        428: {"description": "Faltou a versão (If-Match ou campo versao)"},
    },
)
def editar_diario(
    diario_id: uuid.UUID,
    payload: DiarioEdicaoIn,
    request: Request,
    response: Response,
    if_match: str | None = Header(default=None, description='Versão lida, como "3"'),
    ctx: TenantContext = Depends(ESCREVE),
    uow: UnidadeDeTrabalhoDeObrasSQL = Depends(unidade_de_trabalho),
    db: Session = Depends(sessao_do_tenant),
    agora: Relogio = Depends(relogio),
) -> DiarioOut:
    """Dono e encarregado. Rascunho: edita direto. Publicado: exige `motivo`, guarda o retrato
    anterior numa revisão e gera `diario.revisado`; o encarregado só revisa os próprios."""
    cmd = EditarDiario(
        DiarioId(diario_id), exigir_versao(if_match, payload.versao), payload.para_dados(), payload.motivo
    )
    with auditando_404(request, db, ctx, {DiarioModel: diario_id}):
        h.editar_diario(cmd, ctx, uow, agora)
    return _detalhe(db, ctx, DiarioId(diario_id), response)


@router.post(
    "/diarios/{diario_id}/publicar",
    response_model=DiarioOut,
    responses={**SEM_TENANT_OU_PAPEL, **DIARIO_404, **CONFLITO, **INVALIDO},
)
def publicar_diario(
    diario_id: uuid.UUID,
    request: Request,
    response: Response,
    payload: VersaoIn | None = None,
    if_match: str | None = Header(default=None),
    ctx: TenantContext = Depends(ESCREVE),
    uow: UnidadeDeTrabalhoDeObrasSQL = Depends(unidade_de_trabalho),
    db: Session = Depends(sessao_do_tenant),
    agora: Relogio = Depends(relogio),
) -> DiarioOut:
    """Dono e encarregado. Exige as atividades preenchidas. A partir daqui o cliente vê."""
    cmd = PublicarDiario(DiarioId(diario_id), versao(if_match, payload.versao if payload else None))
    with auditando_404(request, db, ctx, {DiarioModel: diario_id}):
        h.publicar_diario(cmd, ctx, uow, agora)
    return _detalhe(db, ctx, DiarioId(diario_id), response)


@router.delete(
    "/diarios/{diario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={**SEM_TENANT_OU_PAPEL, **DIARIO_404, 409: {"description": "Diário publicado não é removido"}},
)
def remover_diario(
    diario_id: uuid.UUID,
    request: Request,
    if_match: str | None = Header(default=None),
    ctx: TenantContext = Depends(requer_papel("dono")),
    uow: UnidadeDeTrabalhoDeObrasSQL = Depends(unidade_de_trabalho),
    db: Session = Depends(sessao_do_tenant),
    armazenamento: ArmazenamentoDeFotos = Depends(armazenamento_de_fotos),
) -> Response:
    """Só o dono, e só rascunho (o publicado é registro de prova). Apaga as fotos junto."""
    cmd = RemoverDiario(DiarioId(diario_id), versao_do_if_match(if_match))
    with auditando_404(request, db, ctx, {DiarioModel: diario_id}):
        h.remover_diario(cmd, ctx, uow, armazenamento)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/diarios/{diario_id}/revisoes",
    response_model=list[RevisaoOut],
    responses={**SEM_TENANT_OU_PAPEL, **DIARIO_404},
)
def revisoes_do_diario(
    diario_id: uuid.UUID,
    request: Request,
    ctx: TenantContext = Depends(tenant),
    db: Session = Depends(sessao_do_tenant),
) -> Any:
    """Quem vê o diário vê as revisões (o histórico de prova), da mais recente para a mais antiga."""
    with auditando_404(request, db, ctx, {DiarioModel: diario_id}):
        return [asdict(r) for r in ConsultaDeDiariosSQL(db).revisoes(ctx, DiarioId(diario_id))]


# ── Fotos ────────────────────────────────────────────────────────────────────


@router.post(
    "/diarios/{diario_id}/fotos/upload-url",
    response_model=UploadUrlOut,
    responses={**SEM_TENANT_OU_PAPEL, **DIARIO_404, **LIMITE, **INVALIDO},
)
def pedir_upload_de_foto(
    diario_id: uuid.UUID,
    payload: PedidoDeUploadIn,
    request: Request,
    ctx: TenantContext = Depends(ESCREVE),
    uow: UnidadeDeTrabalhoDeObrasSQL = Depends(unidade_de_trabalho),
    db: Session = Depends(sessao_do_tenant),
    armazenamento: ArmazenamentoDeFotos = Depends(armazenamento_de_fotos),
) -> UploadUrlOut:
    """Dono e encarregado. Devolve uma URL de PUT válida por 5 min para JPEG, PNG ou WebP de até
    5 MB, já conferido o limite de fotos do plano. Depois do PUT, confirme em `POST .../fotos`."""
    cmd = SolicitarUploadFoto(DiarioId(diario_id), payload.content_type, payload.tamanho_bytes)
    with auditando_404(request, db, ctx, {DiarioModel: diario_id}):
        pedido = h.solicitar_upload_foto(cmd, ctx, uow, armazenamento)
    return UploadUrlOut(
        foto_id=pedido.foto_id.valor,
        object_key=pedido.object_key,
        url=pedido.url,
        headers={"Content-Type": pedido.content_type},
        expira_em_segundos=pedido.validade_s,
    )


@router.post(
    "/diarios/{diario_id}/fotos",
    status_code=status.HTTP_201_CREATED,
    response_model=FotoOut,
    responses={**SEM_TENANT_OU_PAPEL, **DIARIO_404, **LIMITE, **INVALIDO},
)
def confirmar_foto(
    diario_id: uuid.UUID,
    payload: FotoConfirmacaoIn,
    request: Request,
    ctx: TenantContext = Depends(ESCREVE),
    uow: UnidadeDeTrabalhoDeObrasSQL = Depends(unidade_de_trabalho),
    db: Session = Depends(sessao_do_tenant),
    armazenamento: ArmazenamentoDeFotos = Depends(armazenamento_de_fotos),
    agora: Relogio = Depends(relogio),
) -> FotoOut:
    """Dono e encarregado. Confere o objeto no bucket (tipo e tamanho) e anexa ao diário.
    Confirmar de novo a mesma foto devolve a que já está anexada."""
    cmd = ConfirmarFoto(DiarioId(diario_id), payload.object_key, payload.legenda)
    with auditando_404(request, db, ctx, {DiarioModel: diario_id}):
        foto = h.confirmar_foto(cmd, ctx, uow, armazenamento, agora)
    return FotoOut(
        id=foto.id.valor,
        content_type=foto.content_type,
        tamanho_bytes=foto.tamanho_bytes,
        legenda=foto.legenda,
        enviado_por=foto.enviado_por.valor,
        adicionada_em=foto.criado_em,
        adicionada_apos_publicacao=foto.apos_publicacao,
    )


@router.get("/fotos/{foto_id}/url", response_model=UrlDaFotoOut, responses={**SEM_TENANT_OU_PAPEL, **FOTO_404})
def url_da_foto(
    foto_id: uuid.UUID,
    request: Request,
    ctx: TenantContext = Depends(tenant),
    db: Session = Depends(sessao_do_tenant),
    armazenamento: ArmazenamentoDeFotos = Depends(armazenamento_de_fotos),
) -> UrlDaFotoOut:
    """Quem vê o diário vê a foto: URL de GET válida por 10 min."""
    with auditando_404(request, db, ctx, {DiarioFotoModel: foto_id}):
        chave = ConsultaDeDiariosSQL(db).chave_da_foto(ctx, FotoId(foto_id))
    return UrlDaFotoOut(
        url=armazenamento.url_para_ler(chave, h.VALIDADE_DA_LEITURA_S), expira_em_segundos=h.VALIDADE_DA_LEITURA_S
    )


@router.delete(
    "/fotos/{foto_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={**SEM_TENANT_OU_PAPEL, **FOTO_404, 409: {"description": "Foto de diário publicado não é removida"}},
)
def remover_foto(
    foto_id: uuid.UUID,
    request: Request,
    ctx: TenantContext = Depends(ESCREVE),
    uow: UnidadeDeTrabalhoDeObrasSQL = Depends(unidade_de_trabalho),
    db: Session = Depends(sessao_do_tenant),
    armazenamento: ArmazenamentoDeFotos = Depends(armazenamento_de_fotos),
) -> Response:
    """Dono e encarregado, só em rascunho. Remove a referência e o objeto do bucket."""
    with auditando_404(request, db, ctx, {DiarioFotoModel: foto_id}):
        h.remover_foto(RemoverFoto(FotoId(foto_id)), ctx, uow, armazenamento)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Comentários ──────────────────────────────────────────────────────────────


@router.get(
    "/diarios/{diario_id}/comentarios",
    response_model=PaginaDeComentariosOut,
    responses={**SEM_TENANT_OU_PAPEL, **DIARIO_404},
)
def listar_comentarios(
    diario_id: uuid.UUID,
    request: Request,
    ctx: TenantContext = Depends(tenant),
    db: Session = Depends(sessao_do_tenant),
    page: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=POR_PAGINA_PADRAO, ge=1, le=POR_PAGINA_MAXIMO),
) -> Any:
    """Membros da obra e o dono, do mais antigo para o mais novo."""
    with auditando_404(request, db, ctx, {DiarioModel: diario_id}):
        pagina = ConsultaDeDiariosSQL(db).comentarios(ctx, DiarioId(diario_id), PedidoDePagina(page, por_pagina))
    return asdict(pagina)


@router.post(
    "/diarios/{diario_id}/comentarios",
    status_code=status.HTTP_201_CREATED,
    response_model=ComentarioOut,
    responses={
        **SEM_TENANT_OU_PAPEL,
        **DIARIO_404,
        409: {"description": "Só diário publicado recebe comentário"},
        **INVALIDO,
    },
)
def comentar(
    diario_id: uuid.UUID,
    payload: ComentarioIn,
    request: Request,
    ctx: TenantContext = Depends(tenant),
    uow: UnidadeDeTrabalhoDeObrasSQL = Depends(unidade_de_trabalho),
    db: Session = Depends(sessao_do_tenant),
    agora: Relogio = Depends(relogio),
) -> ComentarioOut:
    """Qualquer membro da obra e o dono, só em diário publicado."""
    with auditando_404(request, db, ctx, {DiarioModel: diario_id}):
        c = h.comentar(Comentar(DiarioId(diario_id), payload.texto), ctx, uow, agora)
    return ComentarioOut(id=c.id.valor, autor_id=c.autor_id.valor, texto=c.texto, criado_em=c.criado_em)
