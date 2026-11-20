"""Produtos do actor.

Revisão incremental depois de 0002_identity_access. Não altera as
tabelas de identidade. Não cria ofertas, categorias nem ficheiros.

O índice em owner_actor_id serve a listagem por actor. A consulta de
um produto usa a chave primária e confirma o mesmo dono na query.

Revision ID: 0003_products
Revises: 0002_identity_access
Create Date: 2026-11-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_products"
down_revision: Union[str, Sequence[str], None] = "0002_identity_access"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "owner_actor_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
            comment="Actor proprietário. Não é aceite no corpo do pedido.",
        ),
        sa.Column(
            "name",
            sa.Text(),
            nullable=False,
            comment="Nome do produto.",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            comment="Descrição do produto.",
        ),
        sa.Column(
            "category",
            sa.Text(),
            nullable=False,
            comment="Categoria em texto livre. Não é uma tabela de categorias.",
        ),
        sa.Column(
            "image_ref",
            sa.Text(),
            nullable=True,
            comment="Referência opcional da fotografia. Não é um ficheiro guardado.",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            comment="active: no catálogo; archived: arquivado, sem apagar o registo.",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.ForeignKeyConstraint(
            ["owner_actor_id"],
            ["actors.id"],
            name="fk_products_owner_actor_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "char_length(btrim(name)) > 0",
            name="ck_products_name",
        ),
        sa.CheckConstraint(
            "char_length(btrim(description)) > 0",
            name="ck_products_description",
        ),
        sa.CheckConstraint(
            "char_length(btrim(category)) > 0",
            name="ck_products_category",
        ),
        sa.CheckConstraint(
            "image_ref IS NULL OR char_length(btrim(image_ref)) > 0",
            name="ck_products_image_ref",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_products_status",
        ),
        comment=(
            "Produto de um actor. Não inclui preço, quantidade nem entrega. "
            "Arquivar muda o estado e mantém a linha."
        ),
    )
    op.create_index(
        "ix_products_owner_actor_id",
        "products",
        ["owner_actor_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_products_owner_actor_id", table_name="products")
    op.drop_table("products")
