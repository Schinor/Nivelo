from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    # Admin da plataforma: não pertence a empresa nenhuma e não lê dados de obras (ADR 004)
    admin_plataforma: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())

    reset_tokens = relationship("ResetToken", back_populates="usuario", cascade="all, delete-orphan")
    # O ORM apaga os vínculos (o banco também tem ON DELETE CASCADE)
    vinculos = relationship("Vinculo", cascade="all, delete-orphan")

    @property
    def admin(self) -> bool:
        return bool(self.admin_plataforma)
