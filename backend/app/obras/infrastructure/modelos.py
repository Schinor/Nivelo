"""Mapeamento ORM das tabelas de Gestão de Obras (revisão api_003_dominio).

Os modelos são detalhe de infraestrutura: o domínio (Fase 4) não os conhece.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CHAR,
    Date,
    DateTime,
    Enum,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
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
