"""Contrato do painel da plataforma."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PlanoNoPainelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plano: str
    rotulo: str
    empresas: int
    usuarios: int | None


class EventoNoPainelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tipo: str | None
    ator_id: int | None
    ator_nome: str | None
    ator_papel: str | None
    empresa_id: str | None
    empresa_nome: str | None
    quando: str | None


class MetricasOut(BaseModel):
    """`usuarios` e `eventos` vêm nulos quando o serviço que os guarda não responde."""

    model_config = ConfigDict(from_attributes=True)

    empresas_total: int
    usuarios_total: int | None
    por_plano: list[PlanoNoPainelOut]
    assinaturas_ativas: int
    mrr_centavos: int
    mrr_formatado: str
    inadimplentes: int
    eventos: list[EventoNoPainelOut] | None
