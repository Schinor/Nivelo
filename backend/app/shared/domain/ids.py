"""Identificadores públicos em UUID v7.

UUID v7 começa pelo instante de criação em milissegundos: fica ordenável (bom para índice)
e não é sequencial como um autoincremento (não facilita enumerar recursos pela URL).
O Python 3.12 ainda não tem `uuid.uuid7`, então a geração segue a RFC 9562 aqui.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Self


def uuid7(agora_ms: int | None = None) -> uuid.UUID:
    """Gera um UUID v7: 48 bits de timestamp (ms), versão 7, variante RFC e 74 bits aleatórios."""
    ms = int(time.time() * 1000) if agora_ms is None else agora_ms
    if not 0 <= ms < 1 << 48:
        raise ValueError("timestamp fora do intervalo de 48 bits")
    aleatorio = int.from_bytes(os.urandom(10), "big")
    rand_a = aleatorio >> 62 & 0xFFF
    rand_b = aleatorio & ((1 << 62) - 1)
    valor = ms << 80 | 0x7 << 76 | rand_a << 64 | 0b10 << 62 | rand_b
    return uuid.UUID(int=valor)


@dataclass(frozen=True, slots=True)
class Identificador:
    """Base dos identificadores de domínio: um UUID imutável, comparado por valor e por tipo."""

    valor: uuid.UUID

    def __post_init__(self) -> None:
        if not isinstance(self.valor, uuid.UUID):
            raise TypeError(f"{type(self).__name__} espera um UUID, recebeu {type(self.valor).__name__}")

    @classmethod
    def novo(cls) -> Self:
        return cls(uuid7())

    @classmethod
    def de_texto(cls, texto: str) -> Self:
        try:
            return cls(uuid.UUID(texto))
        except (ValueError, AttributeError, TypeError) as erro:
            raise ValueError(f"{cls.__name__} inválido: {texto!r}") from erro

    def __str__(self) -> str:
        return str(self.valor)


@dataclass(frozen=True, slots=True)
class EmpresaId(Identificador):
    """Identifica o tenant (a conta contratante)."""
