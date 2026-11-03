"""Comandos de Gestão de Obras: o que cada caso de uso recebe, já sem nada de HTTP."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.obras.domain.ids import ObraId
from app.shared.domain.ids import UsuarioId


@dataclass(frozen=True, slots=True)
class DadosDaObra:
    nome: str
    logradouro: str
    cidade: str
    uf: str
    cliente_nome: str
    data_inicio: date
    previsao_termino: date
    latitude: Decimal | None = None
    longitude: Decimal | None = None


@dataclass(frozen=True, slots=True)
class CriarObra:
    dados: DadosDaObra


@dataclass(frozen=True, slots=True)
class EditarObra:
    obra_id: ObraId
    versao_esperada: int
    dados: DadosDaObra


@dataclass(frozen=True, slots=True)
class AlterarStatusObra:
    obra_id: ObraId
    status: str
    versao_esperada: int | None = None


@dataclass(frozen=True, slots=True)
class RemoverObra:
    obra_id: ObraId
    versao_esperada: int | None = None


@dataclass(frozen=True, slots=True)
class AdicionarMembro:
    obra_id: ObraId
    usuario_id: UsuarioId
    papel: str


@dataclass(frozen=True, slots=True)
class RemoverMembro:
    obra_id: ObraId
    usuario_id: UsuarioId
