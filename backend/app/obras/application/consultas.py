"""Consultas de Gestão de Obras (CQRS leve: listagens vão direto a DTOs, sem montar agregado)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.obras.domain.ids import DiarioId, FotoId, ObraId
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


# ── Diário de obra ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DiarioResumo:
    id: uuid.UUID
    obra_id: uuid.UUID
    data: date
    status: str
    condicao: str
    efetivo: int
    autor_id: int
    publicado_em: datetime | None
    fotos: int
    ocorrencias: int


@dataclass(frozen=True, slots=True)
class OcorrenciaDTO:
    id: uuid.UUID
    tipo: str
    descricao: str
    impacto_prazo_dias: int | None


@dataclass(frozen=True, slots=True)
class FotoDTO:
    id: uuid.UUID
    content_type: str
    tamanho_bytes: int
    legenda: str | None
    enviado_por: int
    adicionada_em: datetime
    adicionada_apos_publicacao: bool


@dataclass(frozen=True, slots=True)
class DiarioDetalhe:
    id: uuid.UUID
    obra_id: uuid.UUID
    data: date
    clima_manha: str | None
    clima_tarde: str | None
    condicao: str
    atividades: str | None
    efetivo: int
    observacoes: str | None
    status: str
    autor_id: int
    versao: int
    publicado_em: datetime | None
    criado_em: datetime
    atualizado_em: datetime
    ocorrencias: list[OcorrenciaDTO]
    fotos: list[FotoDTO]
    revisoes: int


@dataclass(frozen=True, slots=True)
class RevisaoDTO:
    id: uuid.UUID
    versao_anterior: int
    motivo: str
    autor_id: int
    criado_em: datetime
    retrato: dict[str, object]


@dataclass(frozen=True, slots=True)
class ComentarioDTO:
    id: uuid.UUID
    autor_id: int
    texto: str
    criado_em: datetime


class ConsultaDeDiarios(Protocol):
    """Só o que quem pede enxerga: diários das obras visíveis para ele; o cliente, só os
    publicados. Fora disso, 404 (`ObraNaoEncontrada`, `DiarioNaoEncontrado`, `FotoNaoEncontrada`)."""

    def listar(
        self, ctx: TenantContext, obra_id: ObraId, status: str | None, pagina: PedidoDePagina
    ) -> Pagina[DiarioResumo]: ...

    def detalhar(self, ctx: TenantContext, diario_id: DiarioId) -> DiarioDetalhe: ...

    def revisoes(self, ctx: TenantContext, diario_id: DiarioId) -> list[RevisaoDTO]: ...

    def comentarios(self, ctx: TenantContext, diario_id: DiarioId, pagina: PedidoDePagina) -> Pagina[ComentarioDTO]: ...

    def chave_da_foto(self, ctx: TenantContext, foto_id: FotoId) -> str:
        """A `object_key` da foto, se quem pede enxerga o diário dela."""
        ...


class HistoricoDaObra(Protocol):
    """Eventos de negócio da obra e dos diários dela, vindos da auditoria (log-service)."""

    def eventos(self, ctx: TenantContext, obra_id: ObraId, limite: int) -> list[dict[str, object]]: ...
