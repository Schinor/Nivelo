"""Mapeamento ORM das tabelas de Gestão de Obras (revisão api_003_dominio).

Os modelos são detalhe de infraestrutura: o domínio não os conhece. As constraints (FKs
compostas por empresa, CHECKs, índices únicos) vêm das migrações; aqui ficam só as que o
ORM precisa conhecer.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CHAR,
    JSON,
    Date,
    DateTime,
    Enum,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.domain.ids import uuid7
from app.shared.infrastructure.tenancy import TemEmpresa
from app.shared.infrastructure.tipos import UUIDNativo


class ObraModel(TemEmpresa, Base):
    __tablename__ = "obras"
    __table_args__ = (UniqueConstraint("empresa_id", "id", name="uq_obras_empresa_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), primary_key=True, default=uuid7)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    logradouro: Mapped[str] = mapped_column(String(200), nullable=False)
    cidade: Mapped[str] = mapped_column(String(120), nullable=False)
    uf: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    cliente_nome: Mapped[str] = mapped_column(String(160), nullable=False)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    previsao_termino: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("ativa", "pausada", "concluida", name="status_obra"), nullable=False, default="ativa"
    )
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    removida_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    criado_por: Mapped[int] = mapped_column(Integer, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class ObraMembroModel(TemEmpresa, Base):
    __tablename__ = "obra_membros"
    __table_args__ = (
        ForeignKeyConstraint(
            ["empresa_id", "obra_id"],
            ["obras.empresa_id", "obras.id"],
            name="fk_obra_membros_obra",
            ondelete="CASCADE",
        ),
    )

    obra_id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    papel: Mapped[str] = mapped_column(Enum("encarregado", "cliente", name="papel_membro"), nullable=False)
    adicionado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class DiarioModel(TemEmpresa, Base):
    __tablename__ = "diarios"
    __table_args__ = (
        UniqueConstraint("obra_id", "data", name="uq_diarios_obra_data"),
        UniqueConstraint("empresa_id", "id", name="uq_diarios_empresa_id"),
        ForeignKeyConstraint(["empresa_id", "obra_id"], ["obras.empresa_id", "obras.id"], name="fk_diarios_obra"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), primary_key=True)
    obra_id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    clima_manha: Mapped[str | None] = mapped_column(String(20), nullable=True)
    clima_tarde: Mapped[str | None] = mapped_column(String(20), nullable=True)
    condicao: Mapped[str] = mapped_column(
        Enum("praticavel", "impraticavel", name="condicao_trabalho"), nullable=False, default="praticavel"
    )
    atividades: Mapped[str | None] = mapped_column(Text, nullable=True)
    efetivo: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("rascunho", "publicado", name="status_diario"), nullable=False, default="rascunho"
    )
    autor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    publicado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


def _fk_do_diario(nome: str, ondelete: str | None = None) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["empresa_id", "diario_id"], ["diarios.empresa_id", "diarios.id"], name=nome, ondelete=ondelete
    )


class OcorrenciaModel(TemEmpresa, Base):
    __tablename__ = "ocorrencias"
    __table_args__ = (_fk_do_diario("fk_ocorrencias_diario", "CASCADE"),)

    id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), primary_key=True)
    diario_id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), nullable=False)
    tipo: Mapped[str] = mapped_column(
        Enum("chuva", "falta_de_material", "pedido_do_cliente", "acidente", "outro", name="tipo_ocorrencia"),
        nullable=False,
    )
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    impacto_prazo_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class DiarioFotoModel(TemEmpresa, Base):
    __tablename__ = "diario_fotos"
    __table_args__ = (
        UniqueConstraint("object_key", name="uq_diario_fotos_object_key"),
        _fk_do_diario("fk_diario_fotos_diario", "CASCADE"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), primary_key=True)
    diario_id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), nullable=False)
    object_key: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    tamanho_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    legenda: Mapped[str | None] = mapped_column(String(280), nullable=True)
    enviado_por: Mapped[int] = mapped_column(Integer, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class DiarioRevisaoModel(TemEmpresa, Base):
    __tablename__ = "diario_revisoes"
    __table_args__ = (_fk_do_diario("fk_diario_revisoes_diario"),)

    id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), primary_key=True)
    diario_id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), nullable=False)
    versao_anterior: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    motivo: Mapped[str] = mapped_column(String(500), nullable=False)
    autor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class ComentarioModel(TemEmpresa, Base):
    __tablename__ = "comentarios"
    __table_args__ = (_fk_do_diario("fk_comentarios_diario"),)

    id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), primary_key=True)
    diario_id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), nullable=False)
    autor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
