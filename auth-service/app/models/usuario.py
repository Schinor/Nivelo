from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="cliente")
    role_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    # Plano Premium (atividade 7). Só muda pelo webhook do Stripe com assinatura validada.
    # Do Stripe guardamos apenas os IDs — nenhum dado de cartão passa por aqui.
    premium: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    premium_desde: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Admin da plataforma: não pertence a empresa nenhuma e não lê dados de obras (ADR 004)
    admin_plataforma: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())

    papel = relationship("Papel", back_populates="usuarios", lazy="joined")
    reset_tokens = relationship("ResetToken", back_populates="usuario", cascade="all, delete-orphan")
    ajustes_permissao = relationship(
        "UsuarioPermissao", back_populates="usuario", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def admin(self) -> bool:
        return bool(self.admin_plataforma)

    @property
    def permissions(self) -> list[str]:
        """Permissões efetivas: as do papel, mais as concedidas e menos as revogadas individualmente."""
        base = [f"{p.action}:{p.resource}" for p in self.papel.permissoes] if self.papel else []
        concedidas = [a.permissao.slug for a in self.ajustes_permissao if a.concedida]
        revogadas = {a.permissao.slug for a in self.ajustes_permissao if not a.concedida}
        efetivas = [p for p in base if p not in revogadas]
        return efetivas + [p for p in concedidas if p not in efetivas]

    @property
    def permissions_list(self) -> list[str]:
        return self.permissions
