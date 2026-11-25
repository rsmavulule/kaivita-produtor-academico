"""Autorização individual de divulgação de um contacto (incremento I7.2).

DA-I7-12 restringe o UML: uma autorização cobre um contacto, um canal
e uma finalidade. Não há ``authorization_id`` em ``public_contacts`` e
esta tabela não guarda o valor do telefone, do email ou do WhatsApp.
Depois de uma alteração, o histórico identifica a revisão e o canal,
mas não permite recuperar o valor anterior.

A finalidade deste protótipo é só ``commercial_discovery``. Cada
concessão nova cria uma linha nova. A linha vigente é a que tem
``revoked_at`` nulo. Não há um segundo campo de estado.

A ordem de bloqueio é sempre o contacto e depois a autorização.
A representação é verificada antes deste serviço. Uma revogação de
representação confirmada por outra transacção depois dessa leitura
e antes do commit não é reavaliada: é a limitação já existente nas
outras escritas. Suspender a oferta, arquivar o produto, perder o
papel producer ou inactivar o actor não revoga a autorização.
"""

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    Uuid,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.contacts import ContactChannel
from app.db import Base
from app.identity import closed_text

NOTICE_VERSION = "v1"
NOTICE_V1_TEXT = (
    "O representante confirma a divulgação do contacto comercial agora "
    "apresentado, no canal indicado. A finalidade é a descoberta comercial "
    "de ofertas. Qualquer visitante poderá consultar esse contacto. "
    "Terceiros poderão copiá-lo. A revogação impede consultas posteriores "
    "nesta plataforma, mas não apaga cópias já feitas por terceiros. "
    "O representante declara ter autorização adequada para divulgar o "
    "contacto. Esta confirmação operacional não prova, por si, o "
    "consentimento pessoal do titular nem a conformidade jurídica integral."
)
SUPPORTED_NOTICES = {NOTICE_VERSION: NOTICE_V1_TEXT}

STALE_REVISION = (
    "A revisão do contacto está desactualizada. Consulte o contacto novamente."
)
INACTIVE_DISCLOSURE = "O contacto inactivo não pode ser divulgado."
INCONSISTENT_AUTHORIZATION = (
    "A autorização vigente não corresponde ao contacto actual."
)
NOTICE_UNSUPPORTED = "Versão do aviso não suportada."
CONFIRMATION_REQUIRED = "A confirmação explícita é obrigatória."
PURPOSE_UNSUPPORTED = "Finalidade não suportada."
CURRENT_INDEX = "uq_publication_authorizations_current"


class DisclosurePurpose(StrEnum):
    """Finalidade única admitida. DA-I7-02."""

    COMMERCIAL_DISCOVERY = "commercial_discovery"


class RevocationReason(StrEnum):
    """Motivo controlado. Só existe numa autorização revogada."""

    MANUAL = "manual"
    CONTACT_CHANGED = "contact_changed"
    CONTACT_DEACTIVATED = "contact_deactivated"


class AuthorizationUnavailable(Exception):
    """A autorização não pertence a este contacto e actor."""


class AuthorizationConflict(Exception):
    """O estado actual impede a concessão. A mensagem é fixa."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class AuthorizationRejected(Exception):
    """A entrada da concessão não é aceite. Não transporta o contacto."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class GrantOutcome:
    """``created`` distingue 201 de uma repetição idempotente."""

    def __init__(self, authorization: "PublicationAuthorization", created: bool) -> None:
        self.authorization = authorization
        self.created = created


def _values(enum_cls: type[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in enum_cls)


def _optional_text(enum_cls: type[StrEnum], comment: str):
    return mapped_column(
        Enum(
            enum_cls,
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=True,
        comment=comment,
    )


class PublicationAuthorization(Base):
    """Histórico de autorização de um contacto. O valor não é copiado."""

    __tablename__ = "publication_authorizations"
    __table_args__ = (
        CheckConstraint(
            "contact_revision >= 1",
            name="ck_publication_authorizations_revision",
        ),
        CheckConstraint(
            f"channel IN ({_values(ContactChannel)})",
            name="ck_publication_authorizations_channel",
        ),
        CheckConstraint(
            f"purpose IN ({_values(DisclosurePurpose)})",
            name="ck_publication_authorizations_purpose",
        ),
        CheckConstraint(
            "char_length(notice_version) >= 1 "
            "AND char_length(notice_version) <= 32 "
            "AND notice_version = btrim(notice_version)",
            name="ck_publication_authorizations_notice",
        ),
        CheckConstraint(
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
        CheckConstraint(
            "revocation_reason IS NULL "
            f"OR revocation_reason IN ({_values(RevocationReason)})",
            name="ck_publication_authorizations_reason",
        ),
        ForeignKeyConstraint(
            ["contact_id", "actor_id"],
            ["public_contacts.id", "public_contacts.actor_id"],
            name="fk_publication_authorizations_contact_actor",
            ondelete="RESTRICT",
        ),
        Index(
            CURRENT_INDEX,
            "contact_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "ix_publication_authorizations_contact_history",
            "contact_id",
            "granted_at",
            "id",
        ),
        {
            "comment": (
                "Autorização individual de divulgação. Não guarda o valor do contacto. "
                "A linha vigente tem revoked_at nulo. O actor vem do par do contacto, "
                "sem uma segunda chave estrangeira para actors."
            )
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        comment="Actor do contacto. Faz parte da chave estrangeira composta.",
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        comment="Contacto autorizado. Não há cópia do valor.",
    )
    contact_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Revisão exacta do canal e do valor no momento da concessão.",
    )
    channel: Mapped[ContactChannel] = closed_text(
        ContactChannel,
        "Canal autorizado. Tem de coincidir com o canal actual para divulgação.",
    )
    purpose: Mapped[DisclosurePurpose] = closed_text(
        DisclosurePurpose,
        "Finalidade. Neste protótipo só commercial_discovery.",
    )
    notice_version: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Versão do aviso confirmada pelo representante.",
    )
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_publication_authorizations_granted_by",
            ondelete="RESTRICT",
        ),
        nullable=False,
        comment="Operador da concessão. Identificador de rastreio, sem outros dados da conta.",
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="Instante da concessão, com fuso horário.",
    )
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_publication_authorizations_revoked_by",
            ondelete="RESTRICT",
        ),
        nullable=True,
        comment="Operador da revogação. Nulo enquanto a autorização estiver vigente.",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Nulo significa autorização vigente. Não há outro campo de estado.",
    )
    revocation_reason: Mapped[RevocationReason | None] = _optional_text(
        RevocationReason,
        "manual, contact_changed ou contact_deactivated. Nulo se estiver vigente.",
    )


def authorizations_of(session: Session, contact) -> list[PublicationAuthorization]:
    """Histórico deste contacto, da concessão mais recente para a mais antiga."""

    statement = (
        select(PublicationAuthorization)
        .where(
            PublicationAuthorization.contact_id == contact.id,
            PublicationAuthorization.actor_id == contact.actor_id,
        )
        .order_by(
            PublicationAuthorization.granted_at.desc(),
            PublicationAuthorization.id.asc(),
        )
    )
    return list(session.scalars(statement))


def grant_authorization(
    session: Session,
    actor,
    contact_id: uuid.UUID,
    operator_id: uuid.UUID,
    contact_revision: int,
    purpose: str,
    notice_version: str,
    confirmed: bool,
) -> GrantOutcome:
    """Concede ou repete a autorização vigente, com o contacto bloqueado."""

    from app.contacts import ContactStatus, ContactVisibility, contact_for_actor

    if confirmed is not True:
        raise AuthorizationRejected(CONFIRMATION_REQUIRED)
    if purpose != DisclosurePurpose.COMMERCIAL_DISCOVERY.value:
        raise AuthorizationRejected(PURPOSE_UNSUPPORTED)
    if notice_version not in SUPPORTED_NOTICES:
        raise AuthorizationRejected(NOTICE_UNSUPPORTED)

    contact = contact_for_actor(session, actor, contact_id, lock=True)
    if contact.status is not ContactStatus.ACTIVE:
        raise AuthorizationConflict(INACTIVE_DISCLOSURE)
    if contact.revision != contact_revision:
        raise AuthorizationConflict(STALE_REVISION)

    current = _locked_current(session, contact)
    if current is not None:
        if _same_grant(current, contact, notice_version):
            return GrantOutcome(current, False)
        raise AuthorizationConflict(INCONSISTENT_AUTHORIZATION)

    now = datetime.now(timezone.utc)
    authorization = PublicationAuthorization(
        actor_id=contact.actor_id,
        contact_id=contact.id,
        contact_revision=contact.revision,
        channel=contact.channel,
        purpose=DisclosurePurpose.COMMERCIAL_DISCOVERY,
        notice_version=notice_version,
        granted_by_user_id=operator_id,
        granted_at=now,
    )
    try:
        with session.begin_nested():
            session.add(authorization)
            if contact.visibility is not ContactVisibility.PUBLIC:
                contact.visibility = ContactVisibility.PUBLIC
                contact.updated_at = now
            session.flush()
    except IntegrityError as exc:
        session.expire_all()
        if authorization in session:
            session.expunge(authorization)
        if not _is_current_duplicate(exc):
            raise
        current = _locked_current(session, contact)
        if current is not None and _same_grant(current, contact, notice_version):
            return GrantOutcome(current, False)
        raise AuthorizationConflict(INCONSISTENT_AUTHORIZATION) from exc
    return GrantOutcome(authorization, True)


def revoke_authorization(
    session: Session,
    actor,
    contact_id: uuid.UUID,
    authorization_id: uuid.UUID,
    operator_id: uuid.UUID,
) -> PublicationAuthorization:
    """Revoga a linha indicada. Repetir não mexe numa concessão posterior."""

    from app.contacts import ContactVisibility, contact_for_actor

    contact = contact_for_actor(session, actor, contact_id, lock=True)
    authorization = session.scalar(
        select(PublicationAuthorization)
        .where(
            PublicationAuthorization.id == authorization_id,
            PublicationAuthorization.contact_id == contact.id,
            PublicationAuthorization.actor_id == contact.actor_id,
        )
        .with_for_update()
    )
    if authorization is None:
        raise AuthorizationUnavailable
    if authorization.revoked_at is not None:
        return authorization

    now = datetime.now(timezone.utc)
    authorization.revoked_at = now
    authorization.revoked_by_user_id = operator_id
    authorization.revocation_reason = RevocationReason.MANUAL
    if contact.visibility is not ContactVisibility.PRIVATE:
        contact.visibility = ContactVisibility.PRIVATE
        contact.updated_at = now
    session.flush()
    return authorization


def revoke_current_authorization(
    session: Session,
    contact,
    operator_id: uuid.UUID | None,
    reason: RevocationReason,
    at: datetime,
) -> PublicationAuthorization | None:
    """Revoga a autorização vigente dentro da transacção de quem chamou.

    Não faz flush. A alteração do contacto e esta revogação confirmam-se
    juntas. Se o chamador estiver num savepoint, a falha desfaz as duas.
    """

    authorization = _locked_current(session, contact)
    if authorization is None:
        return None
    if operator_id is None:
        raise RuntimeError("A revogação automática exige o operador.")
    authorization.revoked_at = at
    authorization.revoked_by_user_id = operator_id
    authorization.revocation_reason = reason
    return authorization


def _locked_current(session: Session, contact) -> PublicationAuthorization | None:
    return session.scalar(
        select(PublicationAuthorization)
        .where(
            PublicationAuthorization.contact_id == contact.id,
            PublicationAuthorization.actor_id == contact.actor_id,
            PublicationAuthorization.revoked_at.is_(None),
        )
        .with_for_update()
    )


def _same_grant(
    authorization: PublicationAuthorization,
    contact,
    notice_version: str,
) -> bool:
    return (
        authorization.revoked_at is None
        and authorization.contact_revision == contact.revision
        and authorization.channel == contact.channel
        and authorization.purpose is DisclosurePurpose.COMMERCIAL_DISCOVERY
        and authorization.notice_version == notice_version
    )


def _is_current_duplicate(exc: IntegrityError) -> bool:
    origin = exc.orig
    return CURRENT_INDEX in str(origin)
