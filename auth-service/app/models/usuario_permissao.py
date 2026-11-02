from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UsuarioPermissao(Base):
    """Ajuste individual de permissão: concede (concedida=True) ou revoga (False) em relação ao papel."""

    __tablename__ = "user_permissions"

    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )
    concedida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    permissao = relationship("Permissao", lazy="joined")
    usuario = relationship("Usuario", back_populates="ajustes_permissao")
