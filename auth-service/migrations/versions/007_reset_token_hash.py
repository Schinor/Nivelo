"""Token de redefinição de senha guardado só como hash SHA-256

Revision ID: 007_reset_token_hash
Revises: 006_contrai_papel_antigo
Create Date: 2026-11-03 18:00:00.000000

Igual aos convites: o token sai só no e-mail e o banco guarda o SHA-256 dele (64 caracteres
hexadecimais). A tabela é recriada, e isso invalida de propósito todo token emitido antes:
eles estavam em texto puro, e quem leu o banco não pode usá-los. Quem tinha um link aberto
pede outro (a validade era de 30 minutos).

Recriar em vez de ALTER evita depender do nome do índice único antigo, que na produção pode
ter vindo do create_all do projeto anterior. O downgrade recria a estrutura antiga, vazia.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007_reset_token_hash"
down_revision: str | None = "006_contrai_papel_antigo"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("reset_tokens")
    op.create_table(
        "reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("token_hash", sa.CHAR(64), nullable=False),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", name="fk_reset_tokens_usuario", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expira_em", sa.DateTime(), nullable=False),
        sa.Column("usado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("token_hash", name="uq_reset_tokens_token_hash"),
    )
    op.create_index("ix_reset_tokens_usuario_criado", "reset_tokens", ["usuario_id", "criado_em"])


def downgrade() -> None:
    op.drop_table("reset_tokens")
    op.create_table(
        "reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(length=128), nullable=False, unique=True, index=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expira_em", sa.DateTime(), nullable=False),
        sa.Column("usado", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
