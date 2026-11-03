"""Plano Premium (Stripe): colunas em usuarios e tabela de eventos processados

Revision ID: 004_premium_stripe
Revises: 003_user_permissions
Create Date: 2026-10-11 10:00:00.000000

"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.engine.reflection import Inspector

revision: str = "004_premium_stripe"
down_revision: str | None = "003_user_permissions"
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


_APOS_003 = {
    "usuarios": ["id", "nome", "email", "senha_hash", "role", "criado_em", "role_id"],
    "reset_tokens": [],
    "permissions": [],
    "roles": [],
    "role_permissions": [],
    "user_permissions": [],
}

COLUNAS = [
    sa.Column("premium", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("stripe_customer_id", sa.String(255), nullable=True),
    sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
    sa.Column("premium_desde", sa.DateTime(), nullable=True),
]


def upgrade() -> None:
    inspector = _inspetor(_APOS_003)

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
    inspector = _inspetor(_APOS_003)

    if "stripe_eventos_processados" in inspector.get_table_names():
        op.drop_table("stripe_eventos_processados")

    existentes = {c["name"] for c in inspector.get_columns("usuarios")}
    for coluna in reversed(COLUNAS):
        if coluna.name in existentes:
            op.drop_column("usuarios", coluna.name)
