"""Contactos comerciais privados do actor.

Revisão incremental depois de 0004_offers. Não altera as migrações
anteriores. Cria ``public_contacts`` e a unicidade (id, actor_id) que
a autorização individual do incremento seguinte irá referenciar.
Não cria ``publication_authorizations``.

Revision ID: 0005_contacts
Revises: 0004_offers
Create Date: 2026-11-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_contacts"
down_revision: Union[str, Sequence[str], None] = "0004_offers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "public_contacts",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
            comment="Actor titular. Não é aceite no corpo do pedido.",
        ),
        sa.Column(
            "channel",
            sa.String(length=32),
            nullable=False,
            comment="phone, email ou whatsapp. O email de login da conta não entra aqui.",
        ),
        sa.Column(
            "value",
            sa.Text(),
            nullable=False,
            comment=(
                "Valor canónico. Telefone com + e algarismos; "
                "email com domínio em minúsculas."
            ),
        ),
        sa.Column(
            "visibility",
            sa.String(length=32),
            nullable=False,
            comment="private por omissão. Este incremento não grava public.",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            comment="active: em uso; inactive: desactivado, sem apagar o registo.",
        ),
        sa.Column(
            "revision",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
            comment="Versão do par canal/valor. A desactivação não a incrementa.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="Instante de criação, com fuso horário.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="Instante da última alteração efectiva do contacto.",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_public_contacts"),
        sa.UniqueConstraint(
            "id",
            "actor_id",
            name="uq_public_contacts_id_actor",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["actors.id"],
            name="fk_public_contacts_actor_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "channel IN ('phone', 'email', 'whatsapp')",
            name="ck_public_contacts_channel",
        ),
        sa.CheckConstraint(
            "visibility IN ('private', 'public')",
            name="ck_public_contacts_visibility",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_public_contacts_status",
        ),
        sa.CheckConstraint(
            "revision >= 1",
            name="ck_public_contacts_revision",
        ),
        sa.CheckConstraint(
            "char_length(value) >= 1 "
            "AND char_length(value) <= 320 "
            "AND value = btrim(value)",
            name="ck_public_contacts_value",
        ),
        sa.CheckConstraint(
            "status <> 'inactive' OR visibility <> 'public'",
            name="ck_public_contacts_inactive_private",
        ),
        comment=(
            "Contacto comercial privado de um actor. "
            "A autorização individual de divulgação fica para o incremento seguinte. "
            "A unicidade (id, actor_id) prepara a chave estrangeira composta."
        ),
    )
    op.create_index(
        "ix_public_contacts_actor_id",
        "public_contacts",
        ["actor_id"],
    )
    op.create_index(
        "uq_public_contacts_active_channel_value",
        "public_contacts",
        ["actor_id", "channel", "value"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_public_contacts_active_channel_value",
        table_name="public_contacts",
    )
    op.drop_index("ix_public_contacts_actor_id", table_name="public_contacts")
    op.drop_table("public_contacts")
