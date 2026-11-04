"""Rotas de obras e membros (os diários e as fotos estão em `diarios.py`).

- O papel é conferido aqui (`requer_papel`, 403 auditado); o resto das regras vem dos handlers.
- A empresa vem só do token. Obra de outra empresa, removida ou de que a pessoa não é membro
  responde 404; quando é de outra empresa, a auditoria registra
  `recurso.nao_encontrado_outro_tenant` (a resposta não muda).
- Edição com concorrência otimista: `If-Match: "<versao>"` ou o campo `versao`; 409 se divergir.
- Criar e reativar obra passam pela política de plano (402).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.obras.api.dependencias import (
    auditando_404,
    equipe_da_empresa,
    exigir_versao,
    relogio,
    unidade_de_trabalho,
    versao,
    versao_do_if_match,
)
from app.obras.api.dependencias import historico_da_obra as historico_da_obra_dep
from app.obras.api.schemas import (
    EnderecoOut,
    EventoDoHistoricoOut,
    MembroIn,
    MembroOut,
    ObraEdicaoIn,
    ObraIn,
    ObraOut,
    PaginaDeObrasOut,
    StatusIn,
    StatusObraTexto,
)
from app.obras.application import handlers
from app.obras.application.comandos import (
    AdicionarMembro,
    AlterarStatusObra,
    CriarObra,
    EditarObra,
    RemoverMembro,
    RemoverObra,
)
from app.obras.application.consultas import HistoricoDaObra, ObraDetalhe
from app.obras.application.portas import EquipeDaEmpresa
from app.obras.domain.ids import ObraId
from app.obras.infrastructure.consultas import ConsultaDeObrasSQL
from app.obras.infrastructure.modelos import ObraModel
from app.obras.infrastructure.unidade_de_trabalho import UnidadeDeTrabalhoDeObrasSQL
from app.shared.api.autenticacao import requer_papel, tenant
from app.shared.api.sessao import sessao_do_tenant
from app.shared.application.contexto import TenantContext
from app.shared.application.paginacao import POR_PAGINA_MAXIMO, POR_PAGINA_PADRAO, PedidoDePagina
from app.shared.domain.ids import UsuarioId
from app.shared.domain.relogio import Relogio

router = APIRouter(prefix="/api/obras", tags=["obras"])

R = dict[int | str, dict[str, Any]]
SEM_TENANT_OU_PAPEL: R = {
    401: {"description": "Sem token ou token inválido"},
    403: {"description": "Token sem empresa ativa, ou papel sem permissão para a ação"},
}
NAO_ENCONTRADA: R = {404: {"description": "Obra inexistente, removida, de outra empresa ou sem acesso"}}
DADOS_INVALIDOS: R = {422: {"description": "Dados inválidos ou regra da obra violada (ex.: transição de status)"}}
LIMITE_DO_PLANO: R = {402: {"description": "Limite de obras ativas do plano (Problem Details com limite e uso)"}}
CONFLITO: R = {409: {"description": "A obra mudou depois de lida (versão divergente)"}}


# ── Dependências ─────────────────────────────────────────────────────────────


def consulta(db: Session = Depends(sessao_do_tenant)) -> ConsultaDeObrasSQL:
    return ConsultaDeObrasSQL(db)


@contextmanager
def _auditando_404(request: Request, db: Session, ctx: TenantContext, obra_id: uuid.UUID) -> Iterator[None]:
    with auditando_404(request, db, ctx, {ObraModel: obra_id}):
        yield


def _saida(d: ObraDetalhe, response: Response) -> ObraOut:
    response.headers["ETag"] = f'"{d.versao}"'
    return ObraOut(
        id=d.id,
        nome=d.nome,
        endereco=EnderecoOut(
            logradouro=d.logradouro, cidade=d.cidade, uf=d.uf, latitude=d.latitude, longitude=d.longitude
        ),
        cliente_nome=d.cliente_nome,
        data_inicio=d.data_inicio,
        previsao_termino=d.previsao_termino,
        status=d.status,
        versao=d.versao,
        criado_em=d.criado_em,
        atualizado_em=d.atualizado_em,
        membros=None
        if d.membros is None
        else [MembroOut(usuario_id=m.usuario_id, papel=m.papel, adicionado_em=m.adicionado_em) for m in d.membros],
    )


# ── Leitura ──────────────────────────────────────────────────────────────────


@router.get("", response_model=PaginaDeObrasOut, responses=SEM_TENANT_OU_PAPEL)
def listar_obras(
    ctx: TenantContext = Depends(tenant),
    consultas: ConsultaDeObrasSQL = Depends(consulta),
    status_: StatusObraTexto | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=POR_PAGINA_PADRAO, ge=1, le=POR_PAGINA_MAXIMO),
) -> Any:
    """Dono: todas as obras da empresa. Encarregado e cliente: só as obras em que são membros."""
    return consultas.listar(ctx, status_, PedidoDePagina(page, por_pagina))


@router.get("/{obra_id}", response_model=ObraOut, responses={**SEM_TENANT_OU_PAPEL, **NAO_ENCONTRADA})
def detalhar_obra(
    obra_id: uuid.UUID,
    request: Request,
    response: Response,
    ctx: TenantContext = Depends(tenant),
    db: Session = Depends(sessao_do_tenant),
) -> ObraOut:
    """Membros da obra e o dono. A lista de membros só vem para o dono."""
    with _auditando_404(request, db, ctx, obra_id):
        return _saida(ConsultaDeObrasSQL(db).detalhar(ctx, ObraId(obra_id)), response)


# ── Escrita (só o dono) ──────────────────────────────────────────────────────


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ObraOut,
    responses={**SEM_TENANT_OU_PAPEL, **LIMITE_DO_PLANO, **DADOS_INVALIDOS},
)
def criar_obra(
    payload: ObraIn,
    response: Response,
    ctx: TenantContext = Depends(requer_papel("dono")),
    uow: UnidadeDeTrabalhoDeObrasSQL = Depends(unidade_de_trabalho),
    consultas: ConsultaDeObrasSQL = Depends(consulta),
) -> ObraOut:
    """Só o dono. A obra nasce ativa e ocupa uma vaga do plano (Free: 1 obra ativa)."""
    obra = handlers.criar_obra(CriarObra(payload.para_dados()), ctx, uow)
    response.headers["Location"] = f"/api/obras/{obra.id}"
    return _saida(consultas.detalhar(ctx, obra.id), response)


@router.put(
    "/{obra_id}",
    response_model=ObraOut,
    responses={
        **SEM_TENANT_OU_PAPEL,
        **NAO_ENCONTRADA,
        **CONFLITO,
        **DADOS_INVALIDOS,
        428: {"description": "Faltou a versão (If-Match ou campo versao)"},
    },
)
def editar_obra(
    obra_id: uuid.UUID,
    payload: ObraEdicaoIn,
    request: Request,
    response: Response,
    if_match: str | None = Header(default=None, description='Versão lida, como "3"'),
    ctx: TenantContext = Depends(requer_papel("dono")),
    uow: UnidadeDeTrabalhoDeObrasSQL = Depends(unidade_de_trabalho),
    db: Session = Depends(sessao_do_tenant),
) -> ObraOut:
    """Só o dono. Exige a versão lida; se outra pessoa salvou antes, 409."""
    lida = exigir_versao(if_match, payload.versao)
    with _auditando_404(request, db, ctx, obra_id):
        obra = handlers.editar_obra(EditarObra(ObraId(obra_id), lida, payload.para_dados()), ctx, uow)
    return _saida(ConsultaDeObrasSQL(db).detalhar(ctx, obra.id), response)


@router.patch(
    "/{obra_id}/status",
    response_model=ObraOut,
    responses={**SEM_TENANT_OU_PAPEL, **NAO_ENCONTRADA, **CONFLITO, **LIMITE_DO_PLANO, **DADOS_INVALIDOS},
)
def alterar_status(
    obra_id: uuid.UUID,
    payload: StatusIn,
    request: Request,
    response: Response,
    if_match: str | None = Header(default=None),
    ctx: TenantContext = Depends(requer_papel("dono")),
    uow: UnidadeDeTrabalhoDeObrasSQL = Depends(unidade_de_trabalho),
    db: Session = Depends(sessao_do_tenant),
) -> ObraOut:
    """Só o dono. ativa ↔ pausada, ativa|pausada → concluida. Reativar passa pelo plano."""
    cmd = AlterarStatusObra(ObraId(obra_id), payload.status, versao(if_match, payload.versao))
    with _auditando_404(request, db, ctx, obra_id):
        obra = handlers.alterar_status_obra(cmd, ctx, uow)
    return _saida(ConsultaDeObrasSQL(db).detalhar(ctx, obra.id), response)


@router.delete(
    "/{obra_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={**SEM_TENANT_OU_PAPEL, **NAO_ENCONTRADA, **CONFLITO},
)
def remover_obra(
    obra_id: uuid.UUID,
    request: Request,
    if_match: str | None = Header(default=None),
    ctx: TenantContext = Depends(requer_papel("dono")),
    uow: UnidadeDeTrabalhoDeObrasSQL = Depends(unidade_de_trabalho),
    db: Session = Depends(sessao_do_tenant),
    agora: Relogio = Depends(relogio),
) -> Response:
    """Só o dono. Soft delete: a obra some das listagens e do limite; o histórico fica."""
    with _auditando_404(request, db, ctx, obra_id):
        handlers.remover_obra(RemoverObra(ObraId(obra_id), versao_do_if_match(if_match)), ctx, uow, agora)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Membros (só o dono) ──────────────────────────────────────────────────────


@router.post(
    "/{obra_id}/membros",
    status_code=status.HTTP_201_CREATED,
    response_model=MembroOut,
    responses={
        **SEM_TENANT_OU_PAPEL,
        **NAO_ENCONTRADA,
        409: {"description": "Já é membro da obra"},
        422: {"description": "A pessoa não é da empresa, ou o papel não bate com o vínculo"},
        503: {"description": "auth-service indisponível para conferir a equipe"},
    },
)
def adicionar_membro(
    obra_id: uuid.UUID,
    payload: MembroIn,
    request: Request,
    ctx: TenantContext = Depends(requer_papel("dono")),
    uow: UnidadeDeTrabalhoDeObrasSQL = Depends(unidade_de_trabalho),
    db: Session = Depends(sessao_do_tenant),
    equipe: EquipeDaEmpresa = Depends(equipe_da_empresa),
) -> MembroOut:
    """Só o dono. A pessoa precisa ter vínculo ativo na empresa com o mesmo papel (quem ainda
    não é da empresa entra por convite: POST /api/convites)."""
    cmd = AdicionarMembro(ObraId(obra_id), UsuarioId(payload.usuario_id), payload.papel)
    with _auditando_404(request, db, ctx, obra_id):
        obra = handlers.adicionar_membro(cmd, ctx, uow, equipe)
    membro = next(m for m in obra.membros if m.usuario_id.valor == payload.usuario_id)
    return MembroOut(usuario_id=membro.usuario_id.valor, papel=membro.papel.value)


@router.delete(
    "/{obra_id}/membros/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={**SEM_TENANT_OU_PAPEL, 404: {"description": "Obra não encontrada, ou a pessoa não é membro"}},
)
def remover_membro(
    obra_id: uuid.UUID,
    usuario_id: int,
    request: Request,
    ctx: TenantContext = Depends(requer_papel("dono")),
    uow: UnidadeDeTrabalhoDeObrasSQL = Depends(unidade_de_trabalho),
    db: Session = Depends(sessao_do_tenant),
) -> Response:
    """Só o dono. A pessoa continua na empresa; só deixa de ver esta obra."""
    if usuario_id < 1:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Essa pessoa não é membro da obra")
    with _auditando_404(request, db, ctx, obra_id):
        handlers.remover_membro(RemoverMembro(ObraId(obra_id), UsuarioId(usuario_id)), ctx, uow)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Histórico (só o dono) ────────────────────────────────────────────────────


@router.get(
    "/{obra_id}/historico",
    response_model=list[EventoDoHistoricoOut],
    responses={
        **SEM_TENANT_OU_PAPEL,
        **NAO_ENCONTRADA,
        503: {"description": "Auditoria (log-service) indisponível"},
    },
)
def historico_da_obra(
    obra_id: uuid.UUID,
    request: Request,
    limite: int = Query(default=100, ge=1, le=500),
    ctx: TenantContext = Depends(requer_papel("dono")),
    db: Session = Depends(sessao_do_tenant),
    historico: HistoricoDaObra = Depends(historico_da_obra_dep),
) -> Any:
    """Só o dono. Eventos de negócio da obra e dos diários e fotos dela, do mais recente para o
    mais antigo (vêm da auditoria, alimentada pela outbox; podem chegar com ~1 s de atraso)."""
    with _auditando_404(request, db, ctx, obra_id):
        ConsultaDeObrasSQL(db).detalhar(ctx, ObraId(obra_id))
    return historico.eventos(ctx, ObraId(obra_id), limite)
