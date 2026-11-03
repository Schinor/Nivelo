"""Identificadores do contexto de Gestão de Obras."""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.ids import Identificador


@dataclass(frozen=True, slots=True)
class ObraId(Identificador):
    """Identifica uma obra (UUID v7)."""
