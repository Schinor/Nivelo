"""Eventos de negócio da assinatura. Viram linhas da outbox no formato da Parte A.4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from app.shared.domain.eventos import Dados, EventoDeNegocio


@dataclass(frozen=True, kw_only=True)
class EventoDaAssinatura(EventoDeNegocio):
    recurso: ClassVar[str] = "assinatura"

    plano: str
    status: str

    @property
    def recurso_id(self) -> str:
        return str(self.empresa_id)

    def dados(self) -> Dados:
        return {"plano": self.plano, "status": self.status}


@dataclass(frozen=True, kw_only=True)
class AssinaturaIniciada(EventoDaAssinatura):
    tipo: str = "assinatura.iniciada"


@dataclass(frozen=True, kw_only=True)
class AssinaturaAlterada(EventoDaAssinatura):
    tipo: str = "assinatura.alterada"


@dataclass(frozen=True, kw_only=True)
class AssinaturaCancelada(EventoDaAssinatura):
    tipo: str = "assinatura.cancelada"


@dataclass(frozen=True, kw_only=True)
class AssinaturaInadimplente(EventoDaAssinatura):
    tipo: str = "assinatura.inadimplente"
