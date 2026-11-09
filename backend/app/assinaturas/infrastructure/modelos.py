"""Mapeamento ORM das tabelas assinaturas e stripe_eventos (revisão api_003_dominio)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.infrastructure.tenancy import TemEmpresa
from app.shared.infrastructure.tipos import UUIDNativo


class AssinaturaModel(TemEmpresa, Base):
    __tablename__ = "assinaturas"

    # Uma assinatura por empresa: o empresa_id do mixin é a chave primária aqui
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), primary_key=True)
    plano: Mapped[str] = mapped_column(Enum("free", "pro", "construtora", name="plano"), nullable=False, default="free")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    stripe_price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    valor_mensal_centavos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    periodo_fim: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelar_no_fim: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class StripeEventoModel(Base):
    """Avisos já recebidos: é o que torna o webhook idempotente. Não pertence a uma empresa."""

    __tablename__ = "stripe_eventos"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)
    recebido_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    processado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
