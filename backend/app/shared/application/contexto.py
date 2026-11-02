"""Quem está agindo e em nome de qual empresa. Montado a partir do JWT, nunca do corpo."""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.ids import EmpresaId

PAPEIS_DE_NEGOCIO = frozenset({"dono", "encarregado", "cliente"})


@dataclass(frozen=True, slots=True)
class TenantContext:
    empresa_id: EmpresaId
    usuario_id: int
    papel: str

    def __post_init__(self) -> None:
        if self.papel not in PAPEIS_DE_NEGOCIO:
            raise ValueError(f"papel de negócio desconhecido: {self.papel!r}")
