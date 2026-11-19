"""Identidade e acesso: users, actors, roles, actor_roles, user_actor_access.

A revisão 0001_initial mantém-se vazia e é a antecessora desta.
Os CHECK abaixo são a fotografia dos enumerados em app.identity no I1.1.
Acrescentar um valor mais tarde é uma migração nova, não uma edição desta.

Revision ID: 0002_identity_access
Revises: 0001_initial
Create Date: 2026-11-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_identity_access"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "email",
            sa.Text(),
            nullable=False,
            comment="Login da conta, em minúsculas, único.",
        ),
        sa.Column(
            "password_hash",
            sa.Text(),
            nullable=False,
            comment="Resumo da palavra-passe. Este incremento não o calcula nem o verifica.",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            comment="active: conta utilizável; disabled: conta desactivada.",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint(
            "email = lower(btrim(email)) "
            "AND position('@' in email) > 1 "
            "AND position('@' in email) < char_length(email) "
            "AND position(' ' in email) = 0 "
            "AND char_length(email) <= 320",
            name="ck_users_email",
        ),
        sa.CheckConstraint(
            "char_length(btrim(password_hash)) > 0",
            name="ck_users_password_hash",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_users_status",
        ),
        comment=(
            "Conta de acesso. O email é o login. "
            "Este incremento não abre sessão nem verifica a palavra-passe."
        ),
    )
    op.create_table(
        "actors",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "kind",
            sa.String(length=32),
            nullable=False,
            comment="person: pessoa singular; organization: organização.",
        ),
        sa.Column(
            "display_name",
            sa.Text(),
            nullable=False,
            comment="Nome apresentado do actor.",
        ),
        sa.Column(
            "general_location",
            sa.Text(),
            nullable=True,
            comment="Localização geral quando é conhecida. NULL significa desconhecida.",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            comment="active: identidade em uso; inactive: retirada de uso, sem apagar o registo.",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_actors"),
        sa.CheckConstraint(
            "kind IN ('person', 'organization')",
            name="ck_actors_kind",
        ),
        sa.CheckConstraint(
            "char_length(btrim(display_name)) > 0",
            name="ck_actors_display_name",
        ),
        sa.CheckConstraint(
            "general_location IS NULL OR char_length(btrim(general_location)) > 0",
            name="ck_actors_general_location",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_actors_status",
        ),
        comment=(
            "Identidade de uma pessoa ou organização. "
            "Papel comercial e representação ficam nas tabelas de associação."
        ),
    )
    op.create_table(
        "roles",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "code",
            sa.String(length=32),
            nullable=False,
            comment="producer, buyer ou partner. Não é uma permissão de aplicação.",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("code", name="uq_roles_code"),
        sa.CheckConstraint(
            "code IN ('producer', 'buyer', 'partner')",
            name="ck_roles_code",
        ),
        comment="Catálogo fechado de papéis comerciais: producer, buyer e partner.",
    )
    op.create_table(
        "actor_roles",
        sa.Column("actor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("role_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("actor_id", "role_id", name="pk_actor_roles"),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["actors.id"],
            name="fk_actor_roles_actor_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name="fk_actor_roles_role_id",
            ondelete="RESTRICT",
        ),
        comment=(
            "Associação N:M. A chave primária (actor_id, role_id) "
            "é a unicidade pedida pela SRS."
        ),
    )
    op.create_index("ix_actor_roles_role_id", "actor_roles", ["role_id"])
    op.create_table(
        "user_actor_access",
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("actor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "access_level",
            sa.String(length=32),
            nullable=False,
            comment="read: consulta; manage: altera os dados do actor representado.",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            comment="active: autorização em vigor; revoked: retirada, sem apagar a linha.",
        ),
        sa.PrimaryKeyConstraint(
            "user_id",
            "actor_id",
            name="pk_user_actor_access",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_actor_access_user_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["actors.id"],
            name="fk_user_actor_access_actor_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "access_level IN ('read', 'manage')",
            name="ck_user_actor_access_level",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_user_actor_access_status",
        ),
        comment=(
            "Representação autorizada. Não substitui o papel comercial "
            "em actor_roles."
        ),
    )
    op.create_index(
        "ix_user_actor_access_actor_id",
        "user_actor_access",
        ["actor_id"],
    )

    from app.identity import seed_commercial_roles

    seed_commercial_roles(op.get_bind())


def downgrade() -> None:
    op.drop_index("ix_user_actor_access_actor_id", table_name="user_actor_access")
    op.drop_table("user_actor_access")
    op.drop_index("ix_actor_roles_role_id", table_name="actor_roles")
    op.drop_table("actor_roles")
    op.drop_table("roles")
    op.drop_table("actors")
    op.drop_table("users")
