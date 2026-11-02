"""Remove as tabelas favoritos e comentarios do domínio antigo

Revision ID: api_002_remove_catalogo
Revises: api_001_perfis
Create Date: 2026-11-02 21:05:00.000000

As tabelas do catálogo antigo saem do banco. `DROP TABLE IF EXISTS` funciona no
MariaDB e no SQLite e não depende de inspecionar o banco, então o script também
pode ser exportado offline (db/000_remove_catalogo.sql). O downgrade não recria
nada: a remoção é definitiva.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "api_002_remove_catalogo"
down_revision: str | None = "api_001_perfis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS favoritos")
    op.execute("DROP TABLE IF EXISTS comentarios")


def downgrade() -> None:
    # Irreversível de propósito: os dados do domínio antigo saíram do produto e do
    # repositório. Voltar para antes desta revisão só restaura a marca de versão.
    pass
