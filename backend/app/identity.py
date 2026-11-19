"""Modelo persistente de identidade e acesso (incremento I1.1).

Cinco tabelas, alinhadas com a SRS v1.1 §3 e com o diagrama de classes:

- ``users`` — conta autenticável. O UML diz ``login``; a SRS diz
  ``email/login``. A coluna ``email`` é esse identificador.
- ``actors`` — pessoa ou organização. O papel comercial não fica aqui.
- ``roles`` — catálogo fechado: producer, buyer, partner.
- ``actor_roles`` — associação N:M. A chave é o par (actor, papel).
- ``user_actor_access`` — autorização para representar um actor.
  Não é um papel comercial.

Não há registo público. O hash Argon2id, o JWT e os endpoints de
autenticação estão no incremento I1.2 (``app.passwords``, ``app.tokens``
e ``app.auth``). As operações UML ``canManage`` e ``matches`` continuam
por implementar. A conta activa corresponde a ``UserStatus.ACTIVE``.
A unicidade do par actor/papel é uma restrição da base.

Os literais de ``ActorStatus``, ``UserStatus``, ``AccessLevel`` e
``AccessStatus`` não vêm listados na SRS nem no diagrama. Os valores
abaixo são a decisão deste incremento e estão repetidos em CHECK
na migração ``0002_identity_access``. Um valor novo exige migração nova.
"""

import uuid
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ActorKind(StrEnum):
    """SRS §3: pessoa singular ou organização."""

    PERSON = "person"
    ORGANIZATION = "organization"


class ActorStatus(StrEnum):
    """Estado da identidade do actor.

    Não é o estado de publicação de uma oferta.

    active: a identidade está em uso.
    inactive: a identidade foi retirada de uso; o registo mantém-se.
    """

    ACTIVE = "active"
    INACTIVE = "inactive"


class UserStatus(StrEnum):
    """Estado da conta.

    active: a conta pode ser usada quando existir autenticação.
    disabled: a conta está desactivada e não deve autenticar.
    """

    ACTIVE = "active"
    DISABLED = "disabled"


class RoleCode(StrEnum):
    """Catálogo comercial fechado. SRS §3 e RF-09."""

    PRODUCER = "producer"
    BUYER = "buyer"
    PARTNER = "partner"


class AccessLevel(StrEnum):
    """Nível de representação. Distinto de ``RoleCode``.

    read: consulta os dados do actor.
    manage: altera os dados do actor representado (RB-10).
    """

    READ = "read"
    MANAGE = "manage"


class AccessStatus(StrEnum):
    """Validade da autorização de representação.

    active: a autorização está em vigor (RB-10).
    revoked: a autorização foi retirada; a linha conserva-se.
    """

    ACTIVE = "active"
    REVOKED = "revoked"


# Identificadores estáveis do catálogo. Mudá-los depois de aplicado
# o 0002 é uma migração nova: o INSERT não reescreve uma linha existente.
COMMERCIAL_ROLE_IDS: dict[RoleCode, uuid.UUID] = {
    RoleCode.PRODUCER: uuid.UUID("11111111-1111-4111-8111-111111111111"),
    RoleCode.BUYER: uuid.UUID("22222222-2222-4222-8222-222222222222"),
    RoleCode.PARTNER: uuid.UUID("33333333-3333-4333-8333-333333333333"),
}


def _values(enum_cls: type[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in enum_cls)


def closed_text(enum_cls: type[StrEnum], comment: str):
    """Texto fechado: grava ``active``, não o nome Python ``ACTIVE``."""

    return mapped_column(
        Enum(
            enum_cls,
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        comment=comment,
    )


class User(Base):
    """Conta autenticável. O email é o login."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint(
            "email = lower(btrim(email)) "
            "AND position('@' in email) > 1 "
            "AND position('@' in email) < char_length(email) "
            "AND position(' ' in email) = 0 "
            "AND char_length(email) <= 320",
            name="ck_users_email",
        ),
        CheckConstraint(
            "char_length(btrim(password_hash)) > 0",
            name="ck_users_password_hash",
        ),
        CheckConstraint(
            f"status IN ({_values(UserStatus)})",
            name="ck_users_status",
        ),
        {
            "comment": (
                "Conta de acesso. O email é o login. "
                "Este incremento não abre sessão nem verifica a palavra-passe."
            )
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Login da conta, em minúsculas, único.",
    )
    password_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Resumo da palavra-passe. Este incremento não o calcula nem o verifica.",
    )
    status: Mapped[UserStatus] = closed_text(
        UserStatus,
        "active: conta utilizável; disabled: conta desactivada.",
    )

    accesses: Mapped[list["UserActorAccess"]] = relationship(
        back_populates="user",
        passive_deletes=True,
    )


class Actor(Base):
    """Pessoa singular ou organização. Os papéis estão em actor_roles."""

    __tablename__ = "actors"
    __table_args__ = (
        CheckConstraint(
            f"kind IN ({_values(ActorKind)})",
            name="ck_actors_kind",
        ),
        CheckConstraint(
            "char_length(btrim(display_name)) > 0",
            name="ck_actors_display_name",
        ),
        CheckConstraint(
            "general_location IS NULL OR char_length(btrim(general_location)) > 0",
            name="ck_actors_general_location",
        ),
        CheckConstraint(
            f"status IN ({_values(ActorStatus)})",
            name="ck_actors_status",
        ),
        {
            "comment": (
                "Identidade de uma pessoa ou organização. "
                "Papel comercial e representação ficam nas tabelas de associação."
            )
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    kind: Mapped[ActorKind] = closed_text(
        ActorKind,
        "person: pessoa singular; organization: organização.",
    )
    display_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Nome apresentado do actor.",
    )
    general_location: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Localização geral quando é conhecida. NULL significa desconhecida.",
    )
    status: Mapped[ActorStatus] = closed_text(
        ActorStatus,
        "active: identidade em uso; inactive: retirada de uso, sem apagar o registo.",
    )

    role_links: Mapped[list["ActorRole"]] = relationship(
        back_populates="actor",
        passive_deletes=True,
    )
    accesses: Mapped[list["UserActorAccess"]] = relationship(
        back_populates="actor",
        passive_deletes=True,
    )


class Role(Base):
    """Um código do catálogo comercial."""

    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("code", name="uq_roles_code"),
        CheckConstraint(
            f"code IN ({_values(RoleCode)})",
            name="ck_roles_code",
        ),
        {
            "comment": (
                "Catálogo fechado de papéis comerciais: producer, buyer e partner."
            )
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    code: Mapped[RoleCode] = closed_text(
        RoleCode,
        "producer, buyer ou partner. Não é uma permissão de aplicação.",
    )

    assignments: Mapped[list["ActorRole"]] = relationship(
        back_populates="role",
        passive_deletes=True,
    )


class ActorRole(Base):
    """Par actor/papel. A chave primária impede a repetição (RB-01)."""

    __tablename__ = "actor_roles"
    __table_args__ = (
        Index("ix_actor_roles_role_id", "role_id"),
        {
            "comment": (
                "Associação N:M. A chave primária (actor_id, role_id) "
                "é a unicidade pedida pela SRS."
            )
        },
    )

    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "actors.id",
            name="fk_actor_roles_actor_id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "roles.id",
            name="fk_actor_roles_role_id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )

    actor: Mapped[Actor] = relationship(back_populates="role_links")
    role: Mapped[Role] = relationship(back_populates="assignments")


class UserActorAccess(Base):
    """Autorização de um utilizador para representar um actor.

    A chave primária (user_id, actor_id) é o UNIQUE da SRS.
    Um actor pode ter vários representantes e um utilizador pode
    representar vários actores, desde que cada par exista uma só vez.
    """

    __tablename__ = "user_actor_access"
    __table_args__ = (
        CheckConstraint(
            f"access_level IN ({_values(AccessLevel)})",
            name="ck_user_actor_access_level",
        ),
        CheckConstraint(
            f"status IN ({_values(AccessStatus)})",
            name="ck_user_actor_access_status",
        ),
        Index("ix_user_actor_access_actor_id", "actor_id"),
        {
            "comment": (
                "Representação autorizada. Não substitui o papel comercial "
                "em actor_roles."
            )
        },
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_user_actor_access_user_id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "actors.id",
            name="fk_user_actor_access_actor_id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    access_level: Mapped[AccessLevel] = closed_text(
        AccessLevel,
        "read: consulta; manage: altera os dados do actor representado.",
    )
    status: Mapped[AccessStatus] = closed_text(
        AccessStatus,
        "active: autorização em vigor; revoked: retirada, sem apagar a linha.",
    )

    user: Mapped[User] = relationship(back_populates="accesses")
    actor: Mapped[Actor] = relationship(back_populates="accesses")


def seed_commercial_roles(connection) -> None:
    """Garante producer, buyer e partner.

    Pode ser chamada mais do que uma vez. Se o código já existir,
    a linha fica como está, incluindo o id original.
    """

    statement = text(
        """
        INSERT INTO roles (id, code)
        VALUES (:id, :code)
        ON CONFLICT ON CONSTRAINT uq_roles_code DO NOTHING
        """
    )
    for code, role_id in COMMERCIAL_ROLE_IDS.items():
        connection.execute(statement, {"id": role_id, "code": code.value})
