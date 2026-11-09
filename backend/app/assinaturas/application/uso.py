"""Porta para saber o quanto a empresa já usa do plano. Quem conta é o dono dos dados."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class UsoAtual:
    obras_ativas: int
    fotos_na_obra_mais_cheia: int
    membros_equipe: int | None  # None: não foi possível perguntar ao auth-service agora


class UsoDoPlano(Protocol):
    def uso_atual(self) -> UsoAtual: ...
