"""Backoff do relay da outbox e foto anexada depois da publicação

Revision ID: api_004_outbox_e_fotos
Revises: api_003_dominio
Create Date: 2026-11-04 12:00:00.000000

- `outbox.proxima_tentativa_em`: depois de uma falha, a linha só volta a ser lida a partir
  daqui (backoff exponencial pelas `tentativas`, ADR 012). Nula = pode ir já.
- `outbox.ultimo_erro`: o motivo da última falha, para quem investiga a fila.
- `diario_fotos.apos_publicacao`: a foto entrou depois de o diário ser publicado. Gravado no
  momento do anexo, e não deduzido das datas (o DATETIME do MariaDB não guarda fração de
  segundo, e publicar e anexar no mesmo segundo empatariam).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "api_004_outbox_e_fotos"
down_revision: str | None = "api_003_dominio"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("outbox", sa.Column("proxima_tentativa_em", sa.DateTime(), nullable=True))
    op.add_column("outbox", sa.Column("ultimo_erro", sa.String(500), nullable=True))
    op.add_column("diario_fotos", sa.Column("apos_publicacao", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("diario_fotos", "apos_publicacao")
    op.drop_column("outbox", "ultimo_erro")
    op.drop_column("outbox", "proxima_tentativa_em")
