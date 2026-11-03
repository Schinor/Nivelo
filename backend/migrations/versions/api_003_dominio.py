"""Domínio do Nivelo: obras, diários, assinaturas e outbox

Revision ID: api_003_dominio
Revises: api_002_remove_catalogo
Create Date: 2026-11-03 10:00:00.000000

Decisões em docs/adr/010:
- `empresa_id` em toda tabela de domínio, e as filhas apontam para o pai por
  `(empresa_id, id)`: o banco recusa um diário de uma empresa ligado à obra de outra;
- sem FK para tabelas do auth-service (empresas, usuarios): cada serviço é dono das suas;
- `obras.removida_em` é soft delete; índices compostos começam por `empresa_id`.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from app.shared.infrastructure.tipos import UUIDNativo

revision: str = "api_003_dominio"
down_revision: str | None = "api_002_remove_catalogo"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIPOS_DE_OCORRENCIA = ("chuva", "falta_de_material", "pedido_do_cliente", "acidente", "outro")


def _criado_em(nome: str = "criado_em") -> sa.Column[Any]:
    return sa.Column(nome, sa.DateTime(), nullable=False, server_default=sa.func.now())


def _fk_tenant(pai: str, coluna: str, nome: str, ondelete: str | None = None) -> sa.ForeignKeyConstraint:
    """FK composta (empresa_id, <coluna>) → <pai>(empresa_id, id)."""
    return sa.ForeignKeyConstraint(
        ["empresa_id", coluna], [f"{pai}.empresa_id", f"{pai}.id"], name=nome, ondelete=ondelete
    )


def upgrade() -> None:
    # ── Gestão de Obras ───────────────────────────────────────────────────────
    op.create_table(
        "obras",
        sa.Column("id", UUIDNativo(), primary_key=True),
        sa.Column("empresa_id", UUIDNativo(), nullable=False),
        sa.Column("nome", sa.String(160), nullable=False),
        sa.Column("logradouro", sa.String(200), nullable=False),
        sa.Column("cidade", sa.String(120), nullable=False),
        sa.Column("uf", sa.CHAR(2), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("cliente_nome", sa.String(160), nullable=False),
        sa.Column("data_inicio", sa.Date(), nullable=False),
        sa.Column("previsao_termino", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ativa", "pausada", "concluida", name="status_obra"),
            nullable=False,
            server_default="ativa",
        ),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("removida_em", sa.DateTime(), nullable=True),
        sa.Column("criado_por", sa.Integer(), nullable=False),
        _criado_em(),
        _criado_em("atualizado_em"),
        sa.UniqueConstraint("empresa_id", "id", name="uq_obras_empresa_id"),
        sa.CheckConstraint("previsao_termino >= data_inicio", name="ck_obras_periodo"),
    )
    op.create_index("ix_obras_empresa_status", "obras", ["empresa_id", "status"])

    op.create_table(
        "obra_membros",
        sa.Column("obra_id", UUIDNativo(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", UUIDNativo(), nullable=False),
        sa.Column("papel", sa.Enum("encarregado", "cliente", name="papel_membro"), nullable=False),
        _criado_em("adicionado_em"),
        _fk_tenant("obras", "obra_id", "fk_obra_membros_obra", ondelete="CASCADE"),
    )
    op.create_index("ix_obra_membros_empresa_usuario", "obra_membros", ["empresa_id", "usuario_id"])

    op.create_table(
        "diarios",
        sa.Column("id", UUIDNativo(), primary_key=True),
        sa.Column("empresa_id", UUIDNativo(), nullable=False),
        sa.Column("obra_id", UUIDNativo(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("clima_manha", sa.String(20), nullable=True),
        sa.Column("clima_tarde", sa.String(20), nullable=True),
        sa.Column(
            "condicao",
            sa.Enum("praticavel", "impraticavel", name="condicao_trabalho"),
            nullable=False,
            server_default="praticavel",
        ),
        sa.Column("atividades", sa.Text(), nullable=True),
        sa.Column("efetivo", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("rascunho", "publicado", name="status_diario"),
            nullable=False,
            server_default="rascunho",
        ),
        sa.Column("autor_id", sa.Integer(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("publicado_em", sa.DateTime(), nullable=True),
        _criado_em(),
        _criado_em("atualizado_em"),
        sa.UniqueConstraint("obra_id", "data", name="uq_diarios_obra_data"),
        sa.UniqueConstraint("empresa_id", "id", name="uq_diarios_empresa_id"),
        sa.CheckConstraint("efetivo >= 0", name="ck_diarios_efetivo"),
        # Obra tem soft delete: o diário nunca perde a obra por cascata
        _fk_tenant("obras", "obra_id", "fk_diarios_obra"),
    )
    op.create_index("ix_diarios_empresa_obra_data", "diarios", ["empresa_id", "obra_id", "data"])

    op.create_table(
        "ocorrencias",
        sa.Column("id", UUIDNativo(), primary_key=True),
        sa.Column("empresa_id", UUIDNativo(), nullable=False),
        sa.Column("diario_id", UUIDNativo(), nullable=False),
        sa.Column("tipo", sa.Enum(*TIPOS_DE_OCORRENCIA, name="tipo_ocorrencia"), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("impacto_prazo_dias", sa.Integer(), nullable=True),
        _criado_em(),
        _fk_tenant("diarios", "diario_id", "fk_ocorrencias_diario", ondelete="CASCADE"),
    )

    op.create_table(
        "diario_fotos",
        sa.Column("id", UUIDNativo(), primary_key=True),
        sa.Column("empresa_id", UUIDNativo(), nullable=False),
        sa.Column("diario_id", UUIDNativo(), nullable=False),
        sa.Column("object_key", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("tamanho_bytes", sa.Integer(), nullable=False),
        sa.Column("legenda", sa.String(280), nullable=True),
        sa.Column("enviado_por", sa.Integer(), nullable=False),
        _criado_em(),
        sa.UniqueConstraint("object_key", name="uq_diario_fotos_object_key"),
        # Só rascunho pode ser apagado; a aplicação remove os objetos do bucket antes
        _fk_tenant("diarios", "diario_id", "fk_diario_fotos_diario", ondelete="CASCADE"),
    )

    op.create_table(
        "diario_revisoes",
        sa.Column("id", UUIDNativo(), primary_key=True),
        sa.Column("empresa_id", UUIDNativo(), nullable=False),
        sa.Column("diario_id", UUIDNativo(), nullable=False),
        sa.Column("versao_anterior", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("motivo", sa.String(500), nullable=False),
        sa.Column("autor_id", sa.Integer(), nullable=False),
        _criado_em(),
        # Sem cascata: a revisão é prova e só existe em diário publicado, que não se apaga
        _fk_tenant("diarios", "diario_id", "fk_diario_revisoes_diario"),
    )

    op.create_table(
        "comentarios",
        sa.Column("id", UUIDNativo(), primary_key=True),
        sa.Column("empresa_id", UUIDNativo(), nullable=False),
        sa.Column("diario_id", UUIDNativo(), nullable=False),
        sa.Column("autor_id", sa.Integer(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        _criado_em(),
        _fk_tenant("diarios", "diario_id", "fk_comentarios_diario"),
    )

    # ── Assinaturas ───────────────────────────────────────────────────────────
    op.create_table(
        "assinaturas",
        sa.Column("empresa_id", UUIDNativo(), primary_key=True),
        sa.Column(
            "plano",
            sa.Enum("free", "pro", "construtora", name="plano"),
            nullable=False,
            server_default="free",
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("stripe_price_id", sa.String(255), nullable=True),
        sa.Column("valor_mensal_centavos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("periodo_fim", sa.DateTime(), nullable=True),
        sa.Column("cancelar_no_fim", sa.Boolean(), nullable=False, server_default=sa.false()),
        _criado_em("atualizado_em"),
        sa.UniqueConstraint("stripe_customer_id", name="uq_assinaturas_customer"),
        sa.UniqueConstraint("stripe_subscription_id", name="uq_assinaturas_subscription"),
    )

    op.create_table(
        "stripe_eventos",
        sa.Column("event_id", sa.String(255), primary_key=True),
        sa.Column("tipo", sa.String(100), nullable=False),
        _criado_em("recebido_em"),
        sa.Column("processado_em", sa.DateTime(), nullable=True),
        sa.Column("erro", sa.Text(), nullable=True),
    )

    # ── Infraestrutura: outbox dos eventos de domínio (ADR 003) ───────────────
    op.create_table(
        "outbox",
        sa.Column("id", UUIDNativo(), primary_key=True),
        sa.Column("tipo", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("ocorrido_em", sa.DateTime(), nullable=False),
        sa.Column("publicado_em", sa.DateTime(), nullable=True),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_outbox_pendentes", "outbox", ["publicado_em", "ocorrido_em"])


def downgrade() -> None:
    # Ordem inversa das dependências; os índices saem junto com as tabelas
    for tabela in (
        "outbox",
        "stripe_eventos",
        "assinaturas",
        "comentarios",
        "diario_revisoes",
        "diario_fotos",
        "ocorrencias",
        "diarios",
        "obra_membros",
        "obras",
    ):
        op.drop_table(tabela)
