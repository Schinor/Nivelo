"""Cria a tabela user_permissions (ajustes individuais de permissão por usuário)

Revision ID: 003_user_permissions
Revises: 002_rbac_system
Create Date: 2026-09-28 10:00:00.000000

"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.engine.reflection import Inspector

revision: str = "003_user_permissions"
down_revision: str | None = "002_rbac_system"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class _EstadoOffline:
    """No modo offline (exportar SQL) não há banco para inspecionar: o estado é o que as
    revisões anteriores deixam num banco vazio. No modo online nada muda."""

    def __init__(self, tabelas: dict[str, list[str]]) -> None:
        self._tabelas = tabelas

    def get_table_names(self) -> list[str]:
        return list(self._tabelas)

    def get_columns(self, tabela: str) -> list[dict[str, str]]:
        return [{"name": c} for c in self._tabelas.get(tabela, [])]


def _inspetor(estado_offline: dict[str, list[str]]) -> Any:
    if context.is_offline_mode():
        return _EstadoOffline(estado_offline)
    return Inspector.from_engine(op.get_bind())


_APOS_002 = {
    "usuarios": ["id", "nome", "email", "senha_hash", "role", "criado_em", "role_id"],
    "reset_tokens": [],
    "permissions": [],
    "roles": [],
    "role_permissions": [],
}


def upgrade() -> None:
    inspector = _inspetor(_APOS_002)

    if "user_permissions" not in inspector.get_table_names():
        op.create_table(
            "user_permissions",
            sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
            sa.Column(
                "permission_id", sa.Integer(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
            ),
            sa.Column("concedida", sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade() -> None:
    inspector = _inspetor(_APOS_002)

    if "user_permissions" in inspector.get_table_names():
        op.drop_table("user_permissions")
