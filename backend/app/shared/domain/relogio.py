"""Relógio do domínio. As regras que dependem de "agora" ou "hoje" recebem um relógio, para
os testes fixarem a data sem mexer no relógio do sistema."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

FUSO_DO_NEGOCIO = ZoneInfo("America/Sao_Paulo")


class Relogio(Protocol):
    def agora(self) -> datetime:
        """Instante atual, com fuso (UTC)."""
        ...

    def hoje(self) -> date:
        """Data de hoje no fuso do negócio (o canteiro está no Brasil)."""
        ...


class RelogioDoSistema:
    def agora(self) -> datetime:
        return datetime.now(UTC)

    def hoje(self) -> date:
        return datetime.now(FUSO_DO_NEGOCIO).date()
