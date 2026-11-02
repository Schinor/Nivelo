"""Cria tabelas de permissions, roles, role_permissions e adiciona role_id em usuarios

Revision ID: 002_rbac_system
Revises: 001_auth_service
Create Date: 2026-09-13 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

revision: str = "002_rbac_system"
down_revision: str | None = "001_auth_service"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # 1. Cria tabela permissions
    if "permissions" not in tables:
        op.create_table(
            "permissions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("action", sa.String(length=50), nullable=False),
            sa.Column("resource", sa.String(length=50), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.UniqueConstraint("action", "resource", name="uq_permission_action_resource"),
        )

    # 2. Cria tabela roles
    if "roles" not in tables:
        op.create_table(
            "roles",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("slug", sa.String(length=50), nullable=False, unique=True, index=True),
            sa.Column("description", sa.String(length=255), nullable=True),
        )

    # 3. Cria tabela role_permissions
    if "role_permissions" not in tables:
        op.create_table(
            "role_permissions",
            sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
            sa.Column(
                "permission_id", sa.Integer(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
            ),
        )

    # 4. Adiciona coluna role_id em usuarios se nao existir
    if "usuarios" in tables:
        columns = [col["name"] for col in inspector.get_columns("usuarios")]
        if "role_id" not in columns:
            # SQLite (CI e testes) não aceita ALTER com constraint: lá a coluna entra sem a FK
            fk = [] if conn.dialect.name == "sqlite" else [sa.ForeignKey("roles.id", ondelete="SET NULL")]
            op.add_column("usuarios", sa.Column("role_id", sa.Integer(), *fk, nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if "usuarios" in tables:
        columns = [col["name"] for col in inspector.get_columns("usuarios")]
        if "role_id" in columns:
            op.drop_column("usuarios", "role_id")

    if "role_permissions" in tables:
        op.drop_table("role_permissions")

    if "roles" in tables:
        op.drop_table("roles")

    if "permissions" in tables:
        op.drop_table("permissions")
