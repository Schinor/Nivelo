"""Consultas de Gestão de Obras (CQRS leve: listagens vão direto a DTOs, sem montar agregado)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.shared.application.contexto import TenantContext


@dataclass(frozen=True, slots=True)
class ObraResumo:
    id: uuid.UUID
    nome: str
    cidade: str
    uf: str
    status: str


class ConsultaDeObras(Protocol):
    def listar(self, ctx: TenantContext) -> list[ObraResumo]:
        """Obras visíveis para quem pede: o dono vê todas da empresa; encarregado e cliente,
        só as obras em que são membros com o próprio papel. Obras removidas não aparecem."""
        ...
