from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Permissao(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)

    roles = relationship("Papel", secondary="role_permissions", back_populates="permissoes")

    __table_args__ = (UniqueConstraint("action", "resource", name="uq_permission_action_resource"),)

    @property
    def slug(self) -> str:
        return f"{self.action}:{self.resource}"
