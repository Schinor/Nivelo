"""Schemas Pydantic de entrada e saída dos diários, fotos e comentários. Nenhum aceita
`empresa_id` nem `autor_id`: a empresa e o autor vêm só do token."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.obras.application.comandos import DadosDaOcorrencia, DadosDoDiario

TempoTexto = Literal["ensolarado", "nublado", "chuvoso", "tempestade"]
CondicaoTexto = Literal["praticavel", "impraticavel"]
TipoOcorrenciaTexto = Literal["chuva", "falta_de_material", "pedido_do_cliente", "acidente", "outro"]
StatusDiarioTexto = Literal["rascunho", "publicado"]
TipoDeImagemTexto = Literal["image/jpeg", "image/png", "image/webp"]

EXEMPLO_DIARIO: dict[str, Any] = {
    "data": "2026-11-04",
    "clima": {"manha": "ensolarado", "tarde": "chuvoso"},
    "condicao": "praticavel",
    "atividades": "Contrapiso da cozinha e assentamento do piso do banheiro.",
    "efetivo": 4,
    "observacoes": "Caçamba trocada às 10h.",
    "ocorrencias": [{"tipo": "chuva", "descricao": "Chuva forte a partir das 15h", "impacto_prazo_dias": 0}],
}


class ClimaIn(BaseModel):
    manha: TempoTexto | None = None
    tarde: TempoTexto | None = None


class OcorrenciaIn(BaseModel):
    tipo: TipoOcorrenciaTexto
    descricao: str = Field(min_length=1, max_length=2000)
    impacto_prazo_dias: int | None = Field(default=None, ge=0, le=365, description="Atraso no prazo, em dias")


class DiarioIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [EXEMPLO_DIARIO]})

    data: date = Field(description="Dia do registro. Não pode ser futuro; um diário por obra por dia")
    clima: ClimaIn = Field(default_factory=ClimaIn)
    condicao: CondicaoTexto = "praticavel"
    atividades: str | None = Field(default=None, max_length=10_000, description="Obrigatório para publicar")
    efetivo: int = Field(default=0, ge=0, le=10_000, description="Quantas pessoas trabalharam no dia")
    observacoes: str | None = Field(default=None, max_length=5_000)
    ocorrencias: list[OcorrenciaIn] = Field(default_factory=list, max_length=50)

    def para_dados(self) -> DadosDoDiario:
        return DadosDoDiario(
            data=self.data,
            atividades=self.atividades,
            efetivo=self.efetivo,
            condicao=self.condicao,
            clima_manha=self.clima.manha,
            clima_tarde=self.clima.tarde,
            observacoes=self.observacoes,
            ocorrencias=tuple(DadosDaOcorrencia(o.tipo, o.descricao, o.impacto_prazo_dias) for o in self.ocorrencias),
        )


class DiarioEdicaoIn(DiarioIn):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {**EXEMPLO_DIARIO, "efetivo": 5, "versao": 2, "motivo": "Faltou contar o ajudante que chegou às 9h"}
            ]
        }
    )

    versao: int | None = Field(default=None, ge=1, description="Versão lida. Obrigatória aqui ou no If-Match")
    motivo: str | None = Field(
        default=None,
        max_length=500,
        description="Obrigatório se o diário já foi publicado: a alteração vira uma revisão com este motivo",
    )


class VersaoIn(BaseModel):
    versao: int | None = Field(default=None, ge=1, description="Opcional: confere a versão lida (409 se divergir)")


class PedidoDeUploadIn(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"content_type": "image/jpeg", "tamanho_bytes": 412_000}]}
    )

    content_type: TipoDeImagemTexto
    tamanho_bytes: int = Field(gt=0, le=5 * 1024 * 1024, description="Até 5 MB")


class FotoConfirmacaoIn(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "object_key": "empresas/<empresa>/obras/<obra>/diarios/<diario>/<foto>.jpg",
                    "legenda": "Contrapiso pronto",
                }
            ]
        }
    )

    object_key: str = Field(max_length=255, description="A chave devolvida pelo upload-url")
    legenda: str | None = Field(default=None, max_length=280)


class ComentarioIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"texto": "Pode seguir com o contrapiso."}]})

    texto: str = Field(min_length=1, max_length=2000)


# ── Saída ────────────────────────────────────────────────────────────────────


class OcorrenciaOut(BaseModel):
    id: uuid.UUID
    tipo: str
    descricao: str
    impacto_prazo_dias: int | None


class FotoOut(BaseModel):
    id: uuid.UUID
    content_type: str
    tamanho_bytes: int
    legenda: str | None
    enviado_por: int
    criado_em: datetime | None = None


class DiarioResumoOut(BaseModel):
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


class PaginaDeDiariosOut(BaseModel):
    itens: list[DiarioResumoOut]
    pagina: int
    por_pagina: int
    total: int


class DiarioOut(BaseModel):
    id: uuid.UUID
    obra_id: uuid.UUID
    data: date
    clima: ClimaIn
    condicao: str
    atividades: str | None
    efetivo: int
    observacoes: str | None
    status: str
    autor_id: int
    versao: int = Field(description="Mande de volta no If-Match (ou no campo versao) ao editar")
    publicado_em: datetime | None
    criado_em: datetime
    atualizado_em: datetime
    ocorrencias: list[OcorrenciaOut]
    fotos: list[FotoOut]
    revisoes: int = Field(description="Quantas vezes o diário publicado foi revisado")


class RevisaoOut(BaseModel):
    id: uuid.UUID
    versao_anterior: int
    motivo: str
    autor_id: int
    criado_em: datetime
    retrato: dict[str, Any] = Field(description="Como o diário estava antes desta revisão")


class UploadUrlOut(BaseModel):
    foto_id: uuid.UUID
    object_key: str
    url: str = Field(description="URL relativa à API (/storage/...): faça PUT do arquivo nela")
    metodo: Literal["PUT"] = "PUT"
    headers: dict[str, str] = Field(description="Cabeçalhos obrigatórios no PUT")
    expira_em_segundos: int


class UrlDaFotoOut(BaseModel):
    url: str
    expira_em_segundos: int


class ComentarioOut(BaseModel):
    id: uuid.UUID
    autor_id: int
    texto: str
    criado_em: datetime


class PaginaDeComentariosOut(BaseModel):
    itens: list[ComentarioOut]
    pagina: int
    por_pagina: int
    total: int
