"""Plano Premium (Stripe): colunas em usuarios e tabela de eventos processados

Revision ID: 004_premium_stripe
Revises: 003_user_permissions
Create Date: 2026-10-11 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

revision: str = "004_premium_stripe"
down_revision: str | None = "003_user_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUNAS = [
    sa.Column("premium", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("stripe_customer_id", sa.String(255), nullable=True),
    sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
    sa.Column("premium_desde", sa.DateTime(), nullable=True),
]


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    existentes = {c["name"] for c in inspector.get_columns("usuarios")}
    for coluna in COLUNAS:
        if coluna.name not in existentes:
            op.add_column("usuarios", coluna)

    if "stripe_eventos_processados" not in inspector.get_table_names():
        op.create_table(
            "stripe_eventos_processados",
            sa.Column("event_id", sa.String(255), primary_key=True),
            sa.Column("tipo", sa.String(100), nullable=False),
            sa.Column("processado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    if "stripe_eventos_processados" in inspector.get_table_names():
        op.drop_table("stripe_eventos_processados")

    existentes = {c["name"] for c in inspector.get_columns("usuarios")}
    for coluna in reversed(COLUNAS):
        if coluna.name in existentes:
            op.drop_column("usuarios", coluna.name)
