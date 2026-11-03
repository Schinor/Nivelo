"""Identidade do Nivelo: empresas, vínculos, convites e admin da plataforma

Revision ID: 005_identidade
Revises: 004_premium_stripe
Create Date: 2026-11-03 09:00:00.000000

Fase de *expansão* (docs/adr/009): cria as estruturas novas e converte quem já é admin.
A coluna antiga de papel e as tabelas de RBAC continuam até a Fase 3, quando o código
deixa de usá-las e uma revisão de contração as remove.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.tipos import UUIDNativo

revision: str = "005_identidade"
down_revision: str | None = "004_premium_stripe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PAPEIS_DO_VINCULO = ("dono", "encarregado", "cliente")
PAPEIS_DO_CONVITE = ("encarregado", "cliente")


def upgrade() -> None:
    op.create_table(
        "empresas",
        sa.Column("id", UUIDNativo(), primary_key=True),
        sa.Column("nome", sa.String(160), nullable=False),
        sa.Column("tipo_pessoa", sa.Enum("PF", "PJ", name="tipo_pessoa"), nullable=False),
        # CPF ou CNPJ, opcional; único quando informado (NULL não colide no índice único)
        sa.Column("documento", sa.String(18), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("documento", name="uq_empresas_documento"),
    )

    op.add_column(
        "usuarios",
        sa.Column("admin_plataforma", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Conversão: quem tinha o papel admin vira admin da plataforma (idempotente)
    op.execute("UPDATE usuarios SET admin_plataforma = TRUE WHERE role = 'admin'")

    op.create_table(
        "vinculos",
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", name="fk_vinculos_usuario", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "empresa_id",
            UUIDNativo(),
            sa.ForeignKey("empresas.id", name="fk_vinculos_empresa", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("papel", sa.Enum(*PAPEIS_DO_VINCULO, name="papel_vinculo"), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_vinculos_empresa_papel", "vinculos", ["empresa_id", "papel"])

    op.create_table(
        "convites",
        sa.Column("id", UUIDNativo(), primary_key=True),
        sa.Column(
            "empresa_id",
            UUIDNativo(),
            sa.ForeignKey("empresas.id", name="fk_convites_empresa", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(150), nullable=False),
        sa.Column("papel", sa.Enum(*PAPEIS_DO_CONVITE, name="papel_convite"), nullable=False),
        # Obra da API: sem FK entre serviços (docs/adr/010)
        sa.Column("obra_id", UUIDNativo(), nullable=True),
        # SHA-256 em hexadecimal; o token em claro só existe no e-mail
        sa.Column("token_hash", sa.CHAR(64), nullable=False),
        sa.Column("expira_em", sa.DateTime(), nullable=False),
        sa.Column("usado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "criado_por",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", name="fk_convites_criado_por"),
            nullable=False,
        ),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("token_hash", name="uq_convites_token_hash"),
    )
    op.create_index("ix_convites_empresa_email", "convites", ["empresa_id", "email"])


def downgrade() -> None:
    # Os índices saem junto com as tabelas (no MariaDB, um índice usado por FK não sai antes)
    op.drop_table("convites")
    op.drop_table("vinculos")
    op.drop_column("usuarios", "admin_plataforma")
    op.drop_table("empresas")
