"""Identificadores públicos em UUID v7.

UUID v7 começa pelo instante de criação em milissegundos: fica ordenável (bom para índice)
e não é sequencial como um autoincremento (não facilita enumerar recursos pela URL).
O Python 3.12 ainda não tem `uuid.uuid7`, então a geração segue a RFC 9562 aqui.

Dentro do processo a geração é monotônica (RFC 9562, seção 6.2, método 1): os 12 bits de
`rand_a` viram um contador quando dois ids caem no mesmo milissegundo. Assim, dois eventos do
mesmo comando saem da outbox na ordem em que aconteceram, mesmo com o `ocorrido_em` do banco
sem fração de segundo.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Self

_trava = threading.Lock()
_ultimo_ms = -1
_contador = 0
_CONTADOR_MAXIMO = 0xFFF


def _montar(ms: int, rand_a: int, rand_b: int) -> uuid.UUID:
    return uuid.UUID(int=ms << 80 | 0x7 << 76 | rand_a << 64 | 0b10 << 62 | rand_b)


def uuid7(agora_ms: int | None = None) -> uuid.UUID:
    """Gera um UUID v7: 48 bits de timestamp (ms), versão 7, variante RFC, 12 bits de
    contador/aleatório (`rand_a`) e 62 bits aleatórios (`rand_b`).

    Sem `agora_ms`, os ids gerados no processo são estritamente crescentes. Com `agora_ms`
    (testes), o id usa exatamente esse instante, sem contador."""
    global _ultimo_ms, _contador
    aleatorio = int.from_bytes(os.urandom(10), "big")
    rand_b = aleatorio & ((1 << 62) - 1)
    if agora_ms is not None:
        if not 0 <= agora_ms < 1 << 48:
            raise ValueError("timestamp fora do intervalo de 48 bits")
        return _montar(agora_ms, aleatorio >> 62 & _CONTADOR_MAXIMO, rand_b)
    with _trava:
        ms = int(time.time() * 1000)
        if ms > _ultimo_ms:
            # Contador começa na metade de baixo: sobra espaço para os ids do mesmo milissegundo
            _ultimo_ms, _contador = ms, aleatorio >> 63 & 0x7FF
        elif _contador < _CONTADOR_MAXIMO:
            _contador += 1
        else:
            # Mais de ~2 mil ids no mesmo milissegundo (ou o relógio voltou): avança 1 ms
            _ultimo_ms, _contador = _ultimo_ms + 1, 0
        return _montar(_ultimo_ms, _contador, rand_b)


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


@dataclass(frozen=True, slots=True)
class UsuarioId:
    """Identifica o usuário global (auth-service). É inteiro porque a conta veio do projeto
    anterior; nunca aparece sozinho numa URL de recurso de empresa."""

    valor: int

    def __post_init__(self) -> None:
        if isinstance(self.valor, bool) or not isinstance(self.valor, int) or self.valor <= 0:
            raise ValueError(f"UsuarioId inválido: {self.valor!r}")

    def __str__(self) -> str:
        return str(self.valor)
