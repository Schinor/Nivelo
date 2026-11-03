"""Empresa (o tenant) e vínculo (usuário + empresa + papel). Ver docs/adr/004."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.ids import uuid7
from app.core.tipos import UUIDNativo

PAPEIS_DE_NEGOCIO = ("dono", "encarregado", "cliente")


def _agora() -> datetime:
    return datetime.now(UTC)


class Empresa(Base):
    __tablename__ = "empresas"
    __table_args__ = (UniqueConstraint("documento", name="uq_empresas_documento"),)

    id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), primary_key=True, default=uuid7)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    tipo_pessoa: Mapped[str] = mapped_column(Enum("PF", "PJ", name="tipo_pessoa"), nullable=False)
    documento: Mapped[str | None] = mapped_column(String(18), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_agora)


class Vinculo(Base):
    __tablename__ = "vinculos"

    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", name="fk_vinculos_usuario", ondelete="CASCADE"), primary_key=True
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUIDNativo(), ForeignKey("empresas.id", name="fk_vinculos_empresa", ondelete="CASCADE"), primary_key=True
    )
    papel: Mapped[str] = mapped_column(Enum(*PAPEIS_DE_NEGOCIO, name="papel_vinculo"), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_agora)

    empresa: Mapped[Empresa] = relationship(lazy="joined")
