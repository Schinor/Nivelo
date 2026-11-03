"""Porta da unidade de trabalho: uma transação por comando.

Uso nos handlers: `with uow: ...; uow.commit()`. Sair do bloco sem commit (ou com erro)
desfaz tudo. Na Fase 4b o commit também grava os eventos dos agregados na outbox, na mesma
transação.
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self


class UnidadeDeTrabalho(Protocol):
    def __enter__(self) -> Self: ...

    def __exit__(
        self, tipo: type[BaseException] | None, erro: BaseException | None, rastro: TracebackType | None
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
