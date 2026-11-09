"""Remove o premium por usuário: a assinatura agora é da empresa, no módulo Assinaturas da API

Revision ID: 008_remove_premium
Revises: 007_reset_token_hash
Create Date: 2026-11-08 21:00:00.000000

Identidade não sabe mais de cobrança (ADR 007). O downgrade recria a estrutura antiga, vazia:
quem era premium no modelo antigo não volta a ser.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008_remove_premium"
down_revision: str | None = "007_reset_token_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("usuarios", "premium")
    op.drop_column("usuarios", "stripe_customer_id")
    op.drop_column("usuarios", "stripe_subscription_id")
    op.drop_column("usuarios", "premium_desde")
    op.drop_table("stripe_eventos_processados")


def downgrade() -> None:
    op.create_table(
        "stripe_eventos_processados",
        sa.Column("event_id", sa.String(255), primary_key=True),
        sa.Column("tipo", sa.String(100), nullable=False),
        sa.Column("processado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.add_column("usuarios", sa.Column("premium", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("usuarios", sa.Column("stripe_customer_id", sa.String(255), nullable=True))
    op.add_column("usuarios", sa.Column("stripe_subscription_id", sa.String(255), nullable=True))
    op.add_column("usuarios", sa.Column("premium_desde", sa.DateTime(), nullable=True))
