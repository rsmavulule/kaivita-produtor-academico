"""Área de actuação e declaração de direitos da fotografia.

Revisão incremental depois de 0006_publication_authorizations.
Não altera as migrações anteriores. Acrescenta ``actors.coverage_area``
e as colunas da declaração em ``products``. Não copia a localização
geral. Não marca fotografias existentes como autorizadas.

Revision ID: 0007_coverage_and_image_rights
Revises: 0006_publication_authorizations
Create Date: 2026-11-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_coverage_and_image_rights"
down_revision: Union[str, Sequence[str], None] = "0006_publication_authorizations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RIGHTS_CHECK = (
    "("
    "image_rights_declared_at IS NULL "
    "AND image_rights_declared_by IS NULL "
    "AND image_rights_ref IS NULL"
    ") OR ("
    "image_rights_declared_at IS NOT NULL "
    "AND image_rights_declared_by IS NOT NULL "
    "AND image_rights_ref IS NOT NULL "
    "AND image_ref IS NOT NULL "
    "AND image_ref = image_rights_ref"
    ")"
)


def upgrade() -> None:
    op.add_column(
        "actors",
        sa.Column(
            "coverage_area",
            sa.Text(),
            nullable=True,
            comment=(
                "Zonas em que o actor desenvolve a actividade. "
                "É independente da localização geral. NULL significa não indicada."
            ),
        ),
    )
    op.create_check_constraint(
        "ck_actors_coverage_area",
        "actors",
        "coverage_area IS NULL OR char_length(btrim(coverage_area)) > 0",
    )
    op.add_column(
        "products",
        sa.Column(
            "image_rights_ref",
            sa.Text(),
            nullable=True,
            comment="Fotografia exacta a que a declaração de direitos se refere.",
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "image_rights_declared_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Instante da afirmação do representante. Não é uma verificação jurídica.",
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "image_rights_declared_by",
            sa.Uuid(as_uuid=True),
            nullable=True,
            comment="Conta que afirmou os direitos. Não é mostrado na consulta pública.",
        ),
    )
    op.create_foreign_key(
        "fk_products_image_rights_declared_by",
        "products",
        "users",
        ["image_rights_declared_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_products_image_rights",
        "products",
        RIGHTS_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint("ck_products_image_rights", "products", type_="check")
    op.drop_constraint(
        "fk_products_image_rights_declared_by",
        "products",
        type_="foreignkey",
    )
    op.drop_column("products", "image_rights_declared_by")
    op.drop_column("products", "image_rights_declared_at")
    op.drop_column("products", "image_rights_ref")
    op.drop_constraint("ck_actors_coverage_area", "actors", type_="check")
    op.drop_column("actors", "coverage_area")
