"""Consultas de Gestão de Obras (CQRS leve: listagens vão direto a DTOs, sem montar agregado)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.obras.domain.ids import ObraId
from app.shared.application.contexto import TenantContext
from app.shared.application.paginacao import Pagina, PedidoDePagina


@dataclass(frozen=True, slots=True)
class ObraResumo:
    id: uuid.UUID
    nome: str
    cidade: str
    uf: str
    status: str
    cliente_nome: str
    previsao_termino: date


@dataclass(frozen=True, slots=True)
class MembroResumo:
    usuario_id: int
    papel: str
    adicionado_em: datetime | None


@dataclass(frozen=True, slots=True)
class ObraDetalhe:
    id: uuid.UUID
    nome: str
    logradouro: str
    cidade: str
    uf: str
    latitude: Decimal | None
    longitude: Decimal | None
    cliente_nome: str
    data_inicio: date
    previsao_termino: date
    status: str
    versao: int
    criado_em: datetime
    atualizado_em: datetime
    # Só o dono vê a lista de membros; encarregado e cliente recebem None
    membros: list[MembroResumo] | None


class ConsultaDeObras(Protocol):
    def listar(self, ctx: TenantContext, status: str | None, pagina: PedidoDePagina) -> Pagina[ObraResumo]:
        """Obras visíveis para quem pede: o dono vê todas da empresa; encarregado e cliente,
        só as obras em que são membros com o próprio papel. Obras removidas não aparecem."""
        ...

    def detalhar(self, ctx: TenantContext, obra_id: ObraId) -> ObraDetalhe:
        """A obra, se for visível para quem pede; senão `ObraNaoEncontrada` (404)."""
        ...
