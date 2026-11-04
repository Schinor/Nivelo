"""Identificadores do contexto de Gestão de Obras."""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.ids import Identificador


@dataclass(frozen=True, slots=True)
class ObraId(Identificador):
    """Identifica uma obra (UUID v7)."""


@dataclass(frozen=True, slots=True)
class DiarioId(Identificador):
    """Identifica um diário de obra (UUID v7)."""


@dataclass(frozen=True, slots=True)
class OcorrenciaId(Identificador):
    """Identifica uma ocorrência de um diário."""


@dataclass(frozen=True, slots=True)
class FotoId(Identificador):
    """Identifica uma foto do diário. É também o nome do objeto no bucket."""


@dataclass(frozen=True, slots=True)
class RevisaoId(Identificador):
    """Identifica uma revisão de diário publicado."""


@dataclass(frozen=True, slots=True)
class ComentarioId(Identificador):
    """Identifica um comentário num diário publicado."""
