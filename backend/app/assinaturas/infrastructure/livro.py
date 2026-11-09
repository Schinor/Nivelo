"""Implementação SQLAlchemy do livro do webhook. Roda numa sessão `sem_tenant`, aberta na rota."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import CursorResult, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.assinaturas.domain.assinatura import AssinaturaDaEmpresa
from app.assinaturas.domain.eventos import EventoDaAssinatura
from app.assinaturas.domain.planos import Plano, StatusAssinatura
from app.assinaturas.infrastructure.modelos import AssinaturaModel, StripeEventoModel
from app.assinaturas.infrastructure.repositorio import para_dominio
from app.shared.domain.ids import EmpresaId
from app.shared.infrastructure.outbox import MetadadosDaRequisicao, gravar_na_outbox


def _agora() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class LivroDoWebhookSQL:
    def __init__(self, session: Session, metadados: MetadadosDaRequisicao) -> None:
        self._session = session
        self._metadados = metadados

    def registrar_recebimento(self, event_id: str, tipo: str) -> bool:
        self._session.add(StripeEventoModel(event_id=event_id, tipo=tipo))
        try:
            self._session.commit()
            return True
        except IntegrityError:
            self._session.rollback()
        existente = self._session.get(StripeEventoModel, event_id, populate_existing=True)
        return existente is not None and existente.processado_em is None

    def marcar_processado(self, event_id: str) -> bool:
        resultado = self._session.execute(
            update(StripeEventoModel)
            .where(StripeEventoModel.event_id == event_id, StripeEventoModel.processado_em.is_(None))
            .values(processado_em=_agora(), erro=None)
        )
        return cast("CursorResult[object]", resultado).rowcount == 1

    def registrar_erro(self, event_id: str, erro: str) -> None:
        self._session.execute(
            update(StripeEventoModel).where(StripeEventoModel.event_id == event_id).values(erro=erro[:500])
        )
        self._session.commit()

    def empresa_da_assinatura(self, subscription_id: str, customer_id: str | None) -> EmpresaId | None:
        condicoes = [AssinaturaModel.stripe_subscription_id == subscription_id]
        if customer_id:
            condicoes.append(AssinaturaModel.stripe_customer_id == customer_id)
        empresa = self._session.scalars(select(AssinaturaModel.empresa_id).where(or_(*condicoes))).first()
        return EmpresaId(empresa) if empresa else None

    def _modelo_travado(self, empresa_id: EmpresaId) -> AssinaturaModel | None:
        return self._session.scalars(
            select(AssinaturaModel)
            .where(AssinaturaModel.empresa_id == empresa_id.valor)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).one_or_none()

    def travar(self, empresa_id: EmpresaId) -> AssinaturaDaEmpresa:
        modelo = self._modelo_travado(empresa_id)
        if modelo is not None:
            return para_dominio(modelo)
        return AssinaturaDaEmpresa(
            empresa_id=empresa_id,
            plano=Plano.FREE,
            status=StatusAssinatura.ACTIVE,
            stripe_customer_id=None,
            stripe_subscription_id=None,
            stripe_price_id=None,
            valor_mensal_centavos=0,
            periodo_fim=None,
            cancelar_no_fim=False,
        )

    def salvar(self, assinatura: AssinaturaDaEmpresa) -> None:
        modelo = self._session.get(AssinaturaModel, assinatura.empresa_id.valor)
        if modelo is None:
            modelo = AssinaturaModel(empresa_id=assinatura.empresa_id.valor)
            self._session.add(modelo)
        modelo.plano = assinatura.plano.value
        modelo.status = assinatura.status.value
        modelo.stripe_customer_id = assinatura.stripe_customer_id
        modelo.stripe_subscription_id = assinatura.stripe_subscription_id
        modelo.stripe_price_id = assinatura.stripe_price_id
        modelo.valor_mensal_centavos = assinatura.valor_mensal_centavos
        modelo.periodo_fim = assinatura.periodo_fim
        modelo.cancelar_no_fim = assinatura.cancelar_no_fim
        modelo.atualizado_em = _agora()

    def publicar(self, eventos: Iterable[EventoDaAssinatura]) -> None:
        gravar_na_outbox(self._session, eventos, self._metadados)

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
