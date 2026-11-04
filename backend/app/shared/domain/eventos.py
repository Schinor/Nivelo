"""Eventos de domínio. Os contextos herdam e acrescentam os próprios campos."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar

from app.shared.domain.ids import EmpresaId, UsuarioId, uuid7

Dados = dict[str, str | int | None]


@dataclass(frozen=True, kw_only=True)
class EventoDeDominio:
    """Algo que aconteceu no domínio. `tipo` segue o padrão `recurso.verbo_no_particípio`."""

    tipo: str
    event_id: uuid.UUID = field(default_factory=uuid7)
    ocorrido_em: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if "." not in self.tipo:
            raise ValueError(f"tipo de evento deve ser 'recurso.acao', recebeu {self.tipo!r}")


@dataclass(frozen=True, kw_only=True)
class EventoDeNegocio(EventoDeDominio):
    """Evento de uma empresa, feito por alguém, sobre um recurso. É o que vai para a outbox e
    para a auditoria, no formato da Parte A.4 do roteiro (`ator_papel` e `request_id` são
    acrescentados na gravação, porque vêm da requisição e não do domínio)."""

    recurso: ClassVar[str]

    empresa_id: EmpresaId
    ator_id: UsuarioId

    @property
    def recurso_id(self) -> str:
        raise NotImplementedError

    def dados(self) -> Dados:
        return {}
