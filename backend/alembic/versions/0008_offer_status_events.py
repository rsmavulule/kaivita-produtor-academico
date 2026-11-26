"""Eventos das transições de estado das ofertas.

Revisão incremental depois de 0007_coverage_and_image_rights.
Não altera as migrações anteriores. Cria ``offer_status_events``.
Não inventa eventos para ofertas já gravadas.

Revision ID: 0008_offer_status_events
Revises: 0007_coverage_and_image_rights
Create Date: 2026-11-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_offer_status_events"
down_revision: Union[str, Sequence[str], None] = "0007_coverage_and_image_rights"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUS_VALUES = "'draft', 'published', 'suspended', 'withdrawn'"


def upgrade() -> None:
    op.create_table(
        "offer_status_events",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "offer_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
            comment="Oferta cuja transição foi efectivada.",
        ),
        sa.Column(
            "previous_status",
            sa.String(length=32),
            nullable=False,
            comment="Estado imediatamente antes da transição.",
        ),
        sa.Column(
            "new_status",
            sa.String(length=32),
            nullable=False,
            comment="Estado gravado por esta transição.",
        ),
        sa.Column(
            "performed_by_user_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
            comment="Conta que efectuou a transição. Não é mostrada na consulta pública.",
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Instante em que a transição foi gravada.",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_offer_status_events"),
        sa.ForeignKeyConstraint(
            ["offer_id"],
            ["offers.id"],
            name="fk_offer_status_events_offer_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["performed_by_user_id"],
            ["users.id"],
            name="fk_offer_status_events_performed_by_user_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            f"previous_status IN ({STATUS_VALUES})",
            name="ck_offer_status_events_previous_status",
        ),
        sa.CheckConstraint(
            f"new_status IN ({STATUS_VALUES})",
            name="ck_offer_status_events_new_status",
        ),
        sa.CheckConstraint(
            "(previous_status = 'draft' AND new_status = 'published') "
            "OR (previous_status = 'suspended' AND new_status = 'published') "
            "OR (previous_status = 'published' AND new_status = 'suspended') "
            "OR (previous_status = 'draft' AND new_status = 'withdrawn') "
            "OR (previous_status = 'published' AND new_status = 'withdrawn') "
            "OR (previous_status = 'suspended' AND new_status = 'withdrawn')",
            name="ck_offer_status_events_transition",
        ),
        comment=(
            "Registo append-only de uma mudança de estado da oferta. "
            "Não copia preço, quantidade, textos nem contactos."
        ),
    )
    op.create_index(
        "ix_offer_status_events_offer_id",
        "offer_status_events",
        ["offer_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_offer_status_events_offer_id", table_name="offer_status_events")
    op.drop_table("offer_status_events")
