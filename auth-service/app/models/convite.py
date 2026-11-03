"""Convite para entrar numa empresa com um papel (e, opcionalmente, numa obra)."""

import uuid
from datetime import datetime

from sqlalchemy import CHAR, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.ids import uuid7
from app.core.tipos import UUIDNativo
from app.models.empresa import Empresa, _agora


class Convite(Base):
    __tablename__ = "convites"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_convites_token_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), primary_key=True, default=uuid7)
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUIDNativo(), ForeignKey("empresas.id", name="fk_convites_empresa", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(150), nullable=False)
    papel: Mapped[str] = mapped_column(Enum("encarregado", "cliente", name="papel_convite"), nullable=False)
    # Obra da API: sem FK entre serviços (a API confere a obra antes de pedir o convite)
    obra_id: Mapped[uuid.UUID | None] = mapped_column(UUIDNativo(), nullable=True)
    token_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    usado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    criado_por: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", name="fk_convites_criado_por"), nullable=False
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_agora)

    empresa: Mapped[Empresa] = relationship(lazy="joined")
