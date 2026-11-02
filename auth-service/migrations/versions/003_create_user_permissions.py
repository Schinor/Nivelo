"""Cria a tabela user_permissions (ajustes individuais de permissão por usuário)

Revision ID: 003_user_permissions
Revises: 002_rbac_system
Create Date: 2026-09-28 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

revision: str = "003_user_permissions"
down_revision: str | None = "002_rbac_system"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

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
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    if "user_permissions" in inspector.get_table_names():
        op.drop_table("user_permissions")
