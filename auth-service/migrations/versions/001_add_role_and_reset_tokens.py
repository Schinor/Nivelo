"""Adiciona coluna role em usuarios e cria tabela reset_tokens

Revision ID: 001_auth_service
Revises:
Create Date: 2026-08-27 21:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

revision: str = "001_auth_service"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # 1. Se a tabela usuarios existir, adiciona a coluna role caso ainda nao exista
    if "usuarios" in tables:
        columns = [col["name"] for col in inspector.get_columns("usuarios")]
        if "role" not in columns:
            op.add_column(
                "usuarios",
                sa.Column("role", sa.String(length=20), nullable=False, server_default="usuario"),
            )
    else:
        # Se usuarios nao existir, cria a tabela completa
        op.create_table(
            "usuarios",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("nome", sa.String(length=100), nullable=False),
            sa.Column("email", sa.String(length=150), nullable=False, unique=True),
            sa.Column("senha_hash", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False, server_default="usuario"),
            sa.Column("criado_em", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    # 2. Cria tabela reset_tokens caso nao exista
    if "reset_tokens" not in tables:
        op.create_table(
            "reset_tokens",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("token", sa.String(length=128), nullable=False, unique=True, index=True),
            sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
            sa.Column("criado_em", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("expira_em", sa.DateTime(), nullable=False),
            sa.Column("usado", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if "reset_tokens" in tables:
        op.drop_table("reset_tokens")

    if "usuarios" in tables:
        columns = [col["name"] for col in inspector.get_columns("usuarios")]
        if "role" in columns:
            op.drop_column("usuarios", "role")
