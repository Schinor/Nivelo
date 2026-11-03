"""Paginação das listagens (CQRS leve: a consulta devolve DTOs já paginados)."""

from __future__ import annotations

from dataclasses import dataclass

POR_PAGINA_PADRAO = 20
POR_PAGINA_MAXIMO = 100


@dataclass(frozen=True, slots=True)
class PedidoDePagina:
    pagina: int = 1
    por_pagina: int = POR_PAGINA_PADRAO

    def __post_init__(self) -> None:
        if self.pagina < 1:
            raise ValueError("a página começa em 1")
        if not 1 <= self.por_pagina <= POR_PAGINA_MAXIMO:
            raise ValueError(f"por_pagina vai de 1 a {POR_PAGINA_MAXIMO}")

    @property
    def deslocamento(self) -> int:
        return (self.pagina - 1) * self.por_pagina


@dataclass(frozen=True, slots=True)
class Pagina[T]:
    itens: list[T]
    pagina: int
    por_pagina: int
    total: int
