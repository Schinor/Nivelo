from datetime import UTC, datetime

from sqlalchemy import CHAR, Boolean, DateTime, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ResetToken(Base):
    """Pedido de redefinição de senha. O token sai só no e-mail; aqui fica o SHA-256 dele."""

    __tablename__ = "reset_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_reset_tokens_token_hash"),
        Index("ix_reset_tokens_usuario_criado", "usuario_id", "criado_em"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", name="fk_reset_tokens_usuario", ondelete="CASCADE"), nullable=False
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    expira_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    usado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    usuario = relationship("Usuario", back_populates="reset_tokens")
