"""Autorizações individuais de divulgação dos contactos.

Revisão incremental depois de 0005_contacts. Não altera as migrações
anteriores. Cria ``publication_authorizations``. Não concede
autorizações. Contactos que estivessem marcados como públicos passam
a privados, porque ainda não existe autorização que os justifique.

Revision ID: 0006_publication_authorizations
Revises: 0005_contacts
Create Date: 2026-11-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_publication_authorizations"
down_revision: Union[str, Sequence[str], None] = "0005_contacts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONTACT_COMMENT = (
    "Contacto comercial de um actor. Nasce privado. "
    "A divulgação depende de publication_authorizations. "
    "Não há authorization_id. "
    "A unicidade (id, actor_id) suporta a chave estrangeira composta."
)
VISIBILITY_COMMENT = (
    "private por omissão. A API só grava public ao conceder uma autorização coerente."
)
PREVIOUS_CONTACT_COMMENT = (
    "Contacto comercial privado de um actor. "
    "A autorização individual de divulgação fica para o incremento seguinte. "
    "A unicidade (id, actor_id) prepara a chave estrangeira composta."
)
PREVIOUS_VISIBILITY_COMMENT = (
    "private por omissão. Este incremento não grava public."
)


def upgrade() -> None:
    op.execute(
        """
        UPDATE public_contacts
        SET visibility = 'private',
            updated_at = CURRENT_TIMESTAMP
        WHERE visibility = 'public'
        """
    )
    op.create_table(
        "publication_authorizations",
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
            comment="Actor do contacto. Faz parte da chave estrangeira composta.",
        ),
        sa.Column(
            "contact_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
            comment="Contacto autorizado. Não há cópia do valor.",
        ),
        sa.Column(
            "contact_revision",
            sa.Integer(),
            nullable=False,
            comment="Revisão exacta do canal e do valor no momento da concessão.",
        ),
        sa.Column(
            "channel",
            sa.String(length=32),
            nullable=False,
            comment="Canal autorizado. Tem de coincidir com o canal actual para divulgação.",
        ),
        sa.Column(
            "purpose",
            sa.String(length=32),
            nullable=False,
            comment="Finalidade. Neste protótipo só commercial_discovery.",
        ),
        sa.Column(
            "notice_version",
            sa.Text(),
            nullable=False,
            comment="Versão do aviso confirmada pelo representante.",
        ),
        sa.Column(
            "granted_by_user_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
            comment=(
                "Operador da concessão. Identificador de rastreio, "
                "sem outros dados da conta."
            ),
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="Instante da concessão, com fuso horário.",
        ),
        sa.Column(
            "revoked_by_user_id",
            sa.Uuid(as_uuid=True),
            nullable=True,
            comment="Operador da revogação. Nulo enquanto a autorização estiver vigente.",
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Nulo significa autorização vigente. Não há outro campo de estado.",
        ),
        sa.Column(
            "revocation_reason",
            sa.String(length=32),
            nullable=True,
            comment="manual, contact_changed ou contact_deactivated. Nulo se estiver vigente.",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_publication_authorizations"),
        sa.ForeignKeyConstraint(
            ["contact_id", "actor_id"],
            ["public_contacts.id", "public_contacts.actor_id"],
            name="fk_publication_authorizations_contact_actor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["users.id"],
            name="fk_publication_authorizations_granted_by",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"],
            ["users.id"],
            name="fk_publication_authorizations_revoked_by",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "contact_revision >= 1",
            name="ck_publication_authorizations_revision",
        ),
        sa.CheckConstraint(
            "channel IN ('phone', 'email', 'whatsapp')",
            name="ck_publication_authorizations_channel",
        ),
        sa.CheckConstraint(
            "purpose IN ('commercial_discovery')",
            name="ck_publication_authorizations_purpose",
        ),
        sa.CheckConstraint(
            "char_length(notice_version) >= 1 "
            "AND char_length(notice_version) <= 32 "
            "AND notice_version = btrim(notice_version)",
            name="ck_publication_authorizations_notice",
        ),
        sa.CheckConstraint(
            "("
            "revoked_at IS NULL "
            "AND revoked_by_user_id IS NULL "
            "AND revocation_reason IS NULL"
            ") OR ("
            "revoked_at IS NOT NULL "
            "AND revoked_by_user_id IS NOT NULL "
            "AND revocation_reason IS NOT NULL "
            "AND revoked_at >= granted_at"
            ")",
            name="ck_publication_authorizations_revocation",
        ),
        sa.CheckConstraint(
            "revocation_reason IS NULL OR revocation_reason IN "
            "('manual', 'contact_changed', 'contact_deactivated')",
            name="ck_publication_authorizations_reason",
        ),
        comment=(
            "Autorização individual de divulgação. Não guarda o valor do contacto. "
            "A linha vigente tem revoked_at nulo. O actor vem do par do contacto, "
            "sem uma segunda chave estrangeira para actors."
        ),
    )
    op.create_index(
        "uq_publication_authorizations_current",
        "publication_authorizations",
        ["contact_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_publication_authorizations_contact_history",
        "publication_authorizations",
        ["contact_id", "granted_at", "id"],
    )
    op.execute(f"COMMENT ON TABLE public_contacts IS '{CONTACT_COMMENT}'")
    op.alter_column(
        "public_contacts",
        "visibility",
        existing_type=sa.String(length=32),
        existing_nullable=False,
        comment=VISIBILITY_COMMENT,
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE public_contacts
        SET visibility = 'private',
            updated_at = CURRENT_TIMESTAMP
        WHERE visibility = 'public'
        """
    )
    op.drop_index(
        "ix_publication_authorizations_contact_history",
        table_name="publication_authorizations",
    )
    op.drop_index(
        "uq_publication_authorizations_current",
        table_name="publication_authorizations",
    )
    op.drop_table("publication_authorizations")
    op.execute(
        f"COMMENT ON TABLE public_contacts IS '{PREVIOUS_CONTACT_COMMENT}'"
    )
    op.alter_column(
        "public_contacts",
        "visibility",
        existing_type=sa.String(length=32),
        existing_nullable=False,
        comment=PREVIOUS_VISIBILITY_COMMENT,
    )
