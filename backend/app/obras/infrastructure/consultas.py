"""Implementação SQLAlchemy das consultas de obras. A sessão já vem presa ao tenant."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.obras.application.consultas import ObraResumo
from app.obras.infrastructure.modelos import ObraMembroModel, ObraModel
from app.shared.application.contexto import TenantContext


class ConsultaDeObrasSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def listar(self, ctx: TenantContext) -> list[ObraResumo]:
        consulta = select(ObraModel).where(
            ObraModel.empresa_id == ctx.empresa_id.valor, ObraModel.removida_em.is_(None)
        )
        if ctx.papel != "dono":
            consulta = consulta.join(
                ObraMembroModel,
                (ObraMembroModel.obra_id == ObraModel.id) & (ObraMembroModel.empresa_id == ObraModel.empresa_id),
            ).where(ObraMembroModel.usuario_id == ctx.usuario_id, ObraMembroModel.papel == ctx.papel)
        consulta = consulta.order_by(ObraModel.criado_em.desc(), ObraModel.nome)
        return [
            ObraResumo(id=o.id, nome=o.nome, cidade=o.cidade, uf=o.uf, status=o.status)
            for o in self._session.scalars(consulta)
        ]
