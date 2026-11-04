"""Dependências FastAPI das rotas de Gestão de Obras (obras, diários e fotos)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.obras.application.consultas import HistoricoDaObra
from app.obras.application.portas import ArmazenamentoDeFotos, EquipeDaEmpresa
from app.obras.domain.erros import DiarioNaoEncontrado, FotoNaoEncontrada, ObraNaoEncontrada
from app.obras.infrastructure.armazenamento import ArmazenamentoNoGarage
from app.obras.infrastructure.consultas import de_outra_empresa
from app.obras.infrastructure.equipe import EquipeViaAuthService
from app.obras.infrastructure.historico import HistoricoViaLogService
from app.obras.infrastructure.modelos import DiarioFotoModel, DiarioModel, ObraModel
from app.obras.infrastructure.unidade_de_trabalho import UnidadeDeTrabalhoDeObrasSQL
from app.shared.api.autenticacao import tenant
from app.shared.api.request_id import obter_request_id
from app.shared.api.sessao import sessao_do_tenant
from app.shared.application.contexto import TenantContext
from app.shared.domain.relogio import Relogio, RelogioDoSistema
from app.shared.infrastructure.outbox import MetadadosDaRequisicao
from app.shared.infrastructure.tenancy import TemEmpresa


def unidade_de_trabalho(
    request: Request, ctx: TenantContext = Depends(tenant), db: Session = Depends(sessao_do_tenant)
) -> UnidadeDeTrabalhoDeObrasSQL:
    # A implementação dos direitos (Assinaturas) é ligada no main.py: Obras só conhece a porta
    fabrica_de_direitos = request.app.state.consulta_direitos
    metadados = MetadadosDaRequisicao(ator_papel=ctx.papel, request_id=obter_request_id())
    return UnidadeDeTrabalhoDeObrasSQL(db, ctx.empresa_id, fabrica_de_direitos(db), metadados)


def equipe_da_empresa(authorization: str = Header(default="")) -> EquipeDaEmpresa:
    return EquipeViaAuthService(authorization)


def armazenamento_de_fotos() -> ArmazenamentoDeFotos:
    return ArmazenamentoNoGarage()


def historico_da_obra() -> HistoricoDaObra:
    return HistoricoViaLogService()


def relogio() -> Relogio:
    return RelogioDoSistema()


# ── 404 auditado ─────────────────────────────────────────────────────────────

_NOME_DO_RECURSO: dict[type[TemEmpresa], str] = {ObraModel: "obra", DiarioModel: "diario", DiarioFotoModel: "foto"}


@contextmanager
def auditando_404(
    request: Request, db: Session, ctx: TenantContext, ids: dict[type[TemEmpresa], uuid.UUID]
) -> Iterator[None]:
    """Repassa o 404. Se o recurso pedido existe em outra empresa, anota para a auditoria
    registrar `recurso.nao_encontrado_outro_tenant` (ver main.py); a resposta não muda.

    `ids` liga o modelo ao id da URL (ex.: `{DiarioModel: diario_id}`)."""
    try:
        yield
    except (ObraNaoEncontrada, DiarioNaoEncontrado, FotoNaoEncontrada) as erro:
        for modelo, id_ in ids.items():
            if de_outra_empresa(db, modelo, id_, ctx.empresa_id.valor):
                request.state.nao_encontrado_outro_tenant = {
                    "usuario_id": ctx.usuario_id,
                    "empresa_id": str(ctx.empresa_id),
                    "recurso": f"{_NOME_DO_RECURSO[modelo]}:{id_}",
                }
                break
        raise erro


# ── Versão (If-Match) ────────────────────────────────────────────────────────


def versao_do_if_match(if_match: str | None) -> int | None:
    if if_match is None or not if_match.strip():
        return None
    valor = if_match.strip().removeprefix("W/").strip('"')
    if not valor.isdigit() or int(valor) < 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'If-Match deve ser a versão do recurso, como "3"')
    return int(valor)


def versao(if_match: str | None, do_corpo: int | None) -> int | None:
    do_cabecalho = versao_do_if_match(if_match)
    if do_cabecalho is not None and do_corpo is not None and do_cabecalho != do_corpo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "If-Match e o campo versao divergem")
    return do_cabecalho if do_cabecalho is not None else do_corpo


def exigir_versao(if_match: str | None, do_corpo: int | None) -> int:
    v = versao(if_match, do_corpo)
    if v is None:
        raise HTTPException(
            status.HTTP_428_PRECONDITION_REQUIRED, 'Mande a versão lida no If-Match (ex.: "3") ou no campo versao'
        )
    return v
