"""Evento de domínio base. Os contextos herdam e acrescentam os próprios campos."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.shared.domain.ids import uuid7


@dataclass(frozen=True, kw_only=True)
class EventoDeDominio:
    """Algo que aconteceu no domínio. `tipo` segue o padrão `recurso.verbo_no_particípio`."""

    tipo: str
    event_id: uuid.UUID = field(default_factory=uuid7)
    ocorrido_em: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if "." not in self.tipo:
            raise ValueError(f"tipo de evento deve ser 'recurso.acao', recebeu {self.tipo!r}")
