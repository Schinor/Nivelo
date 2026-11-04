"""Implementação SQLAlchemy das consultas de obras. A sessão já vem presa ao tenant."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, exists, func, select
from sqlalchemy.orm import Session

from app.obras.application.consultas import MembroResumo, ObraDetalhe, ObraResumo
from app.obras.domain.erros import ObraNaoEncontrada
from app.obras.domain.ids import ObraId
from app.obras.infrastructure.modelos import ObraMembroModel, ObraModel
from app.shared.application.contexto import TenantContext
from app.shared.application.paginacao import Pagina, PedidoDePagina
from app.shared.infrastructure.tenancy import TemEmpresa, sem_tenant


def _decimal(valor: Any) -> Decimal | None:
    return None if valor is None else Decimal(str(valor))


def obras_visiveis(ctx: TenantContext, consulta: Select[Any]) -> Select[Any]:
    """Restringe `consulta` (que já envolve `ObraModel`) às obras que quem pede enxerga: da
    empresa, não removidas e, para encarregado e cliente, só aquelas em que são membros com o
    próprio papel."""
    consulta = consulta.where(ObraModel.empresa_id == ctx.empresa_id.valor, ObraModel.removida_em.is_(None))
    if ctx.papel != "dono":
        consulta = consulta.where(
            exists().where(
                ObraMembroModel.obra_id == ObraModel.id,
                ObraMembroModel.empresa_id == ObraModel.empresa_id,
                ObraMembroModel.usuario_id == ctx.usuario_id,
                ObraMembroModel.papel == ctx.papel,
            )
        )
    return consulta


class ConsultaDeObrasSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _visiveis(self, ctx: TenantContext, consulta: Select[Any]) -> Select[Any]:
        return obras_visiveis(ctx, consulta)

    def listar(
        self, ctx: TenantContext, status: str | None = None, pagina: PedidoDePagina | None = None
    ) -> Pagina[ObraResumo]:
        pagina = pagina or PedidoDePagina()
        filtro = self._visiveis(ctx, select(ObraModel))
        if status is not None:
            filtro = filtro.where(ObraModel.status == status)
        total = self._session.scalar(select(func.count()).select_from(filtro.subquery())) or 0
        consulta = (
            filtro.order_by(ObraModel.criado_em.desc(), ObraModel.nome, ObraModel.id)
            .offset(pagina.deslocamento)
            .limit(pagina.por_pagina)
        )
        itens = [
            ObraResumo(
                id=o.id,
                nome=o.nome,
                cidade=o.cidade,
                uf=o.uf,
                status=o.status,
                cliente_nome=o.cliente_nome,
                previsao_termino=o.previsao_termino,
            )
            for o in self._session.scalars(consulta)
        ]
        return Pagina(itens=itens, pagina=pagina.pagina, por_pagina=pagina.por_pagina, total=int(total))

    def detalhar(self, ctx: TenantContext, obra_id: ObraId) -> ObraDetalhe:
        o = self._session.scalars(self._visiveis(ctx, select(ObraModel)).where(ObraModel.id == obra_id.valor)).first()
        if o is None:
            raise ObraNaoEncontrada()
        membros = None
        if ctx.papel == "dono":
            membros = [
                MembroResumo(usuario_id=m.usuario_id, papel=m.papel, adicionado_em=m.adicionado_em)
                for m in self._session.scalars(
                    select(ObraMembroModel)
                    .where(ObraMembroModel.obra_id == o.id, ObraMembroModel.empresa_id == o.empresa_id)
                    .order_by(ObraMembroModel.papel, ObraMembroModel.usuario_id)
                )
            ]
        return ObraDetalhe(
            id=o.id,
            nome=o.nome,
            logradouro=o.logradouro,
            cidade=o.cidade,
            uf=o.uf,
            latitude=_decimal(o.latitude),
            longitude=_decimal(o.longitude),
            cliente_nome=o.cliente_nome,
            data_inicio=o.data_inicio,
            previsao_termino=o.previsao_termino,
            status=o.status,
            versao=o.versao,
            criado_em=o.criado_em,
            atualizado_em=o.atualizado_em,
            membros=membros,
        )


def de_outra_empresa(session: Session, modelo: type[TemEmpresa], id_: uuid.UUID, empresa_do_pedido: uuid.UUID) -> bool:
    """Para a auditoria do 404: o recurso existe, mas é de outra empresa? Nunca muda a resposta."""
    with sem_tenant(session, "auditoria do 404 por tenancy: só confere se o recurso existe em outra empresa"):
        dona = session.scalar(select(modelo.empresa_id).where(modelo.id == id_))  # type: ignore[attr-defined]
    return dona is not None and dona != empresa_do_pedido


def obra_de_outra_empresa(session: Session, obra_id: uuid.UUID, empresa_do_pedido: uuid.UUID) -> bool:
    return de_outra_empresa(session, ObraModel, obra_id, empresa_do_pedido)
