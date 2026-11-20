"""Ofertas comerciais do actor.

Revisão incremental depois de 0003_products. Não altera as migrações
anteriores. Acrescenta a unicidade (id, owner_actor_id) em products
para a chave estrangeira composta. As linhas de produtos já existentes
permanecem válidas, porque id já é único.

Revision ID: 0004_offers
Revises: 0003_products
Create Date: 2026-11-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_offers"
down_revision: Union[str, Sequence[str], None] = "0003_products"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_products_id_owner",
        "products",
        ["id", "owner_actor_id"],
    )
    op.create_table(
        "offers",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
            comment="Produto referenciado. Tem de pertencer ao mesmo actor.",
        ),
        sa.Column(
            "owner_actor_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
            comment="Actor proprietário. Não é aceite no corpo do pedido.",
        ),
        sa.Column(
            "price",
            sa.Numeric(),
            nullable=True,
            comment="Preço em decimal exacto. NULL no rascunho. Não é ponto flutuante.",
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=True,
            comment="Código de três letras maiúsculas. NULL no rascunho.",
        ),
        sa.Column(
            "quantity",
            sa.Numeric(),
            nullable=True,
            comment="Quantidade conhecida. Zero é valor, não ausência. NULL no rascunho.",
        ),
        sa.Column(
            "unit",
            sa.Text(),
            nullable=True,
            comment="Unidade em texto livre. NULL no rascunho.",
        ),
        sa.Column(
            "availability",
            sa.String(length=32),
            nullable=True,
            comment=(
                "Disponibilidade comercial. Distinta do estado de publicação. "
                "NULL no rascunho."
            ),
        ),
        sa.Column(
            "delivery_terms",
            sa.Text(),
            nullable=True,
            comment="Condições informativas de entrega. NULL significa ausência.",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            comment=(
                "draft: rascunho; published: publicada; suspended: suspensa; "
                "withdrawn: retirada, sem apagar o registo."
            ),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_offers"),
        sa.ForeignKeyConstraint(
            ["owner_actor_id"],
            ["actors.id"],
            name="fk_offers_owner_actor_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id", "owner_actor_id"],
            ["products.id", "products.owner_actor_id"],
            name="fk_offers_product_owner",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.CheckConstraint(
            "price IS NULL OR price >= 0",
            name="ck_offers_price",
        ),
        sa.CheckConstraint(
            "quantity IS NULL OR quantity >= 0",
            name="ck_offers_quantity",
        ),
        sa.CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'",
            name="ck_offers_currency",
        ),
        sa.CheckConstraint(
            "unit IS NULL OR char_length(btrim(unit)) > 0",
            name="ck_offers_unit",
        ),
        sa.CheckConstraint(
            "delivery_terms IS NULL OR char_length(btrim(delivery_terms)) > 0",
            name="ck_offers_delivery_terms",
        ),
        sa.CheckConstraint(
            "availability IS NULL OR availability IN ('available', 'unavailable')",
            name="ck_offers_availability",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'suspended', 'withdrawn')",
            name="ck_offers_status",
        ),
        sa.CheckConstraint(
            "NOT (quantity = 0 AND availability = 'available')",
            name="ck_offers_quantity_availability",
        ),
        sa.CheckConstraint(
            "status <> 'published' OR ("
            "price IS NOT NULL AND price >= 0 AND "
            "currency IS NOT NULL AND currency ~ '^[A-Z]{3}$' AND "
            "quantity IS NOT NULL AND quantity >= 0 AND "
            "unit IS NOT NULL AND char_length(btrim(unit)) > 0 AND "
            "availability IS NOT NULL AND "
            "NOT (quantity = 0 AND availability = 'available'))",
            name="ck_offers_published",
        ),
        comment=(
            "Oferta comercial de um produto do mesmo actor. "
            "Publicar, suspender e retirar mudam o estado e mantêm a linha."
        ),
    )
    op.create_index("ix_offers_owner_actor_id", "offers", ["owner_actor_id"])
    op.create_index("ix_offers_product_id", "offers", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_offers_product_id", table_name="offers")
    op.drop_index("ix_offers_owner_actor_id", table_name="offers")
    op.drop_table("offers")
    op.drop_constraint("uq_products_id_owner", "products", type_="unique")
