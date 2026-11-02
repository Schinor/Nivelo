"""Linha de base da API: tabela perfis

Revision ID: api_001_perfis
Revises:
Create Date: 2026-11-02 21:00:00.000000

Até aqui a API criava as tabelas com `create_all` no boot. Esta revisão cria `perfis`
só se ela ainda não existir, para o banco de produção (que já a tem) e um banco vazio
chegarem ao mesmo ponto.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "api_001_perfis"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _existe(tabela: str) -> bool:
    if context.is_offline_mode():
        return False
    return tabela in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _existe("perfis"):
        return
    op.create_table(
        "perfis",
        sa.Column("usuario_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("bio", sa.String(280), nullable=True),
        sa.Column("foto_key", sa.String(255), nullable=True),
        sa.Column("foto_bytes", sa.Integer(), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("perfis")
