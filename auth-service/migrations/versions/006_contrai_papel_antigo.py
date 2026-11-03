"""Contração: remove o papel antigo de usuarios e as tabelas de RBAC

Revision ID: 006_contrai_papel_antigo
Revises: 005_identidade
Create Date: 2026-11-03 14:00:00.000000

Segunda metade do expandir e contrair (docs/adr/009). Entra no mesmo commit em que o código
deixa de usar `usuarios.role`, `usuarios.role_id` e as tabelas `roles`, `permissions`,
`role_permissions` e `user_permissions`. O papel de negócio agora mora em `vinculos`, e o
admin em `usuarios.admin_plataforma`.

O downgrade recria a estrutura vazia: a matriz antiga de permissões não volta.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "006_contrai_papel_antigo"
down_revision: str | None = "005_identidade"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Nome que o MariaDB dá à FK sem nome criada pela revisão 002 num banco vazio (db/000).
# Online, o nome real é lido do banco (a produção pode ter outro, vindo do create_all antigo).
FK_PADRAO_ROLE_ID = "usuarios_ibfk_1"


def _fks_de_role_id() -> list[str]:
    if context.is_offline_mode():
        return [FK_PADRAO_ROLE_ID]
    inspetor = sa.inspect(op.get_bind())
    return [
        fk["name"]
        for fk in inspetor.get_foreign_keys("usuarios")
        if fk.get("name") and fk["constrained_columns"] == ["role_id"]
    ]


def upgrade() -> None:
    dialeto = op.get_bind().dialect.name if not context.is_offline_mode() else "mysql"
    if dialeto != "sqlite":  # no SQLite a coluna nasceu sem FK (revisão 002)
        for nome in _fks_de_role_id():
            op.drop_constraint(nome, "usuarios", type_="foreignkey")
    op.drop_column("usuarios", "role_id")
    op.drop_column("usuarios", "role")

    op.drop_table("user_permissions")
    op.drop_table("role_permissions")
    op.drop_table("roles")
    op.drop_table("permissions")


def downgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("resource", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.UniqueConstraint("action", "resource", name="uq_permission_action_resource"),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False, unique=True, index=True),
        sa.Column("description", sa.String(length=255), nullable=True),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "user_permissions",
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("concedida", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("usuarios", sa.Column("role", sa.String(length=50), nullable=False, server_default="cliente"))
    op.add_column("usuarios", sa.Column("role_id", sa.Integer(), nullable=True))
    # O papel que ainda dá para reconstruir: admin
    op.execute("UPDATE usuarios SET role = 'admin' WHERE admin_plataforma = TRUE")
