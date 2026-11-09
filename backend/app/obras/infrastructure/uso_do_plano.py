"""Quanto a empresa ativa usa do plano. Implementa a porta `UsoDoPlano` de Assinaturas."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assinaturas.application.uso import UsoAtual
from app.obras.application.portas import EquipeDaEmpresa
from app.obras.domain.valores import StatusObra
from app.obras.infrastructure.modelos import DiarioFotoModel, DiarioModel, ObraModel
from app.shared.application.erros import DependenciaIndisponivel
from app.shared.domain.ids import EmpresaId


class UsoDoPlanoSQL:
    def __init__(self, session: Session, empresa_id: EmpresaId, equipe: EquipeDaEmpresa) -> None:
        self._session = session
        self._empresa_id = empresa_id.valor
        self._equipe = equipe

    def uso_atual(self) -> UsoAtual:
        return UsoAtual(
            obras_ativas=self._obras_ativas(),
            fotos_na_obra_mais_cheia=self._fotos_na_obra_mais_cheia(),
            membros_equipe=self._membros_equipe(),
        )

    def _obras_ativas(self) -> int:
        consulta = (
            select(func.count())
            .select_from(ObraModel)
            .where(
                ObraModel.empresa_id == self._empresa_id,
                ObraModel.status == StatusObra.ATIVA.value,
                ObraModel.removida_em.is_(None),
            )
        )
        return int(self._session.scalar(consulta) or 0)

    def _fotos_na_obra_mais_cheia(self) -> int:
        por_obra = (
            select(func.count().label("fotos"))
            .select_from(DiarioFotoModel)
            .join(
                DiarioModel,
                (DiarioModel.id == DiarioFotoModel.diario_id) & (DiarioModel.empresa_id == DiarioFotoModel.empresa_id),
            )
            .where(DiarioFotoModel.empresa_id == self._empresa_id)
            .group_by(DiarioModel.obra_id)
            .subquery()
        )
        return int(self._session.scalar(select(func.max(por_obra.c.fotos))) or 0)

    def _membros_equipe(self) -> int | None:
        try:
            return self._equipe.pessoas_que_contam_no_plano()
        except DependenciaIndisponivel:
            return None
