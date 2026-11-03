"""Schemas Pydantic de entrada e saída das rotas de obras. Nenhum aceita `empresa_id`: a
empresa vem só do token (campos desconhecidos no corpo são ignorados)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.obras.application.comandos import DadosDaObra

StatusObraTexto = Literal["ativa", "pausada", "concluida"]
PapelDeMembroTexto = Literal["encarregado", "cliente"]

EXEMPLO_ENDERECO: dict[str, Any] = {"logradouro": "Rua das Acácias, 120", "cidade": "Marília", "uf": "SP"}
EXEMPLO_OBRA: dict[str, Any] = {
    "nome": "Casa do Jorge",
    "endereco": EXEMPLO_ENDERECO,
    "cliente_nome": "Jorge Alves",
    "data_inicio": "2026-11-03",
    "previsao_termino": "2027-03-31",
}


class EnderecoIn(BaseModel):
    logradouro: str = Field(min_length=1, max_length=200)
    cidade: str = Field(min_length=1, max_length=120)
    uf: str = Field(min_length=2, max_length=2, description="Sigla do estado, como SP")
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)


class ObraIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [EXEMPLO_OBRA]})

    nome: str = Field(min_length=1, max_length=160)
    endereco: EnderecoIn
    cliente_nome: str = Field(min_length=1, max_length=160, description="Nome de quem contratou a obra")
    data_inicio: date
    previsao_termino: date = Field(description="Não pode ser antes de data_inicio")

    def para_dados(self) -> DadosDaObra:
        e = self.endereco
        return DadosDaObra(
            nome=self.nome,
            logradouro=e.logradouro,
            cidade=e.cidade,
            uf=e.uf,
            latitude=e.latitude,
            longitude=e.longitude,
            cliente_nome=self.cliente_nome,
            data_inicio=self.data_inicio,
            previsao_termino=self.previsao_termino,
        )


class ObraEdicaoIn(ObraIn):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{**EXEMPLO_OBRA, "nome": "Casa do Jorge (2º piso)", "versao": 1}]}
    )

    versao: int | None = Field(default=None, ge=1, description="Versão lida. Obrigatória aqui ou no cabeçalho If-Match")


class StatusIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "pausada", "versao": 1}]})

    status: StatusObraTexto
    versao: int | None = Field(default=None, ge=1, description="Opcional: confere a versão lida (409 se divergir)")


class MembroIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"usuario_id": 2, "papel": "encarregado"}]})

    usuario_id: int = Field(gt=0, description="Pessoa da equipe (GET /api/auth/equipe)")
    papel: PapelDeMembroTexto


class EnderecoOut(BaseModel):
    logradouro: str
    cidade: str
    uf: str
    latitude: Decimal | None = None
    longitude: Decimal | None = None


class MembroOut(BaseModel):
    usuario_id: int
    papel: str
    adicionado_em: datetime | None = None


class ObraResumoOut(BaseModel):
    id: uuid.UUID
    nome: str
    cidade: str
    uf: str
    status: str
    cliente_nome: str
    previsao_termino: date


class PaginaDeObrasOut(BaseModel):
    itens: list[ObraResumoOut]
    pagina: int
    por_pagina: int
    total: int


class ObraOut(BaseModel):
    id: uuid.UUID
    nome: str
    endereco: EnderecoOut
    cliente_nome: str
    data_inicio: date
    previsao_termino: date
    status: str
    versao: int = Field(description="Mande de volta no If-Match (ou no campo versao) ao editar")
    criado_em: datetime
    atualizado_em: datetime
    membros: list[MembroOut] | None = Field(default=None, description="Só para o dono")
