"""Contactos comerciais privados de um actor (incremento I7.1).

A SRS v1.1 §3 e o diagrama de classes prevêem ``PublicContact``.
O contacto pertence ao actor, não à conta. O email de login não é copiado
para aqui. Nasce ``private`` e ``active``, com revisão 1.

A cardinalidade do UML admite uma autorização a cobrir vários contactos.
DA-I7-12 restringe o protótipo: a autorização futura é individual por
contacto, canal e finalidade. Este incremento não cria essa tabela nem
``authorization_id``. A unicidade ``(id, actor_id)`` fica para a chave
estrangeira composta da migração seguinte.

O papel ``producer`` não é exigido. A representação é que autoriza a
leitura ou a escrita. A divulgação pública não é decidida aqui.
"""

import re
import uuid
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base
from app.identity import Actor, closed_text

PHONE_PATTERN = re.compile(r"\+[1-9][0-9]{7,14}")
PHONE_SEPARATORS = " -.()"
PHONE_INVALID = "Telefone inválido."
WHATSAPP_INVALID = "WhatsApp inválido."
EMAIL_INVALID = "Email inválido."
DUPLICATE_CONTACT = "Já existe um contacto activo com este canal e valor."
INACTIVE_CONTACT = "O contacto inactivo não pode ser alterado."
VALUE_MAX_LENGTH = 320


class ContactChannel(StrEnum):
    """Canal comercial fechado. DA-I7-03."""

    PHONE = "phone"
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class ContactVisibility(StrEnum):
    """Intenção de divulgação. Neste incremento a API só grava ``private``."""

    PRIVATE = "private"
    PUBLIC = "public"


class ContactStatus(StrEnum):
    """Presença operacional do contacto. Desactivar não apaga a linha."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class ContactUnavailable(Exception):
    """O contacto não existe neste actor."""


class ContactRejected(Exception):
    """O canal ou o valor não passam a validação. A linha não muda."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ContactDuplicate(Exception):
    """Já há um contacto activo com o mesmo canal e valor neste actor."""

    def __init__(self) -> None:
        super().__init__(DUPLICATE_CONTACT)
        self.detail = DUPLICATE_CONTACT


class ContactInactive(Exception):
    """Um contacto inactivo não aceita correcção de canal ou valor."""

    def __init__(self) -> None:
        super().__init__(INACTIVE_CONTACT)
        self.detail = INACTIVE_CONTACT


def _values(enum_cls: type[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in enum_cls)


class PublicContact(Base):
    """Contacto comercial de um actor. A publicação não está neste incremento."""

    __tablename__ = "public_contacts"
    __table_args__ = (
        CheckConstraint(
            f"channel IN ({_values(ContactChannel)})",
            name="ck_public_contacts_channel",
        ),
        CheckConstraint(
            f"visibility IN ({_values(ContactVisibility)})",
            name="ck_public_contacts_visibility",
        ),
        CheckConstraint(
            f"status IN ({_values(ContactStatus)})",
            name="ck_public_contacts_status",
        ),
        CheckConstraint(
            "revision >= 1",
            name="ck_public_contacts_revision",
        ),
        CheckConstraint(
            "char_length(value) >= 1 "
            "AND char_length(value) <= 320 "
            "AND value = btrim(value)",
            name="ck_public_contacts_value",
        ),
        CheckConstraint(
            "status <> 'inactive' OR visibility <> 'public'",
            name="ck_public_contacts_inactive_private",
        ),
        UniqueConstraint(
            "id",
            "actor_id",
            name="uq_public_contacts_id_actor",
        ),
        Index("ix_public_contacts_actor_id", "actor_id"),
        Index(
            "uq_public_contacts_active_channel_value",
            "actor_id",
            "channel",
            "value",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        {
            "comment": (
                "Contacto comercial privado de um actor. "
                "A autorização individual de divulgação fica para o incremento seguinte. "
                "A unicidade (id, actor_id) prepara a chave estrangeira composta."
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
        ForeignKey(
            "actors.id",
            name="fk_public_contacts_actor_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        comment="Actor titular. Não é aceite no corpo do pedido.",
    )
    channel: Mapped[ContactChannel] = closed_text(
        ContactChannel,
        "phone, email ou whatsapp. O email de login da conta não entra aqui.",
    )
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Valor canónico. Telefone com + e algarismos; email com domínio em minúsculas.",
    )
    visibility: Mapped[ContactVisibility] = closed_text(
        ContactVisibility,
        "private por omissão. Este incremento não grava public.",
    )
    status: Mapped[ContactStatus] = closed_text(
        ContactStatus,
        "active: em uso; inactive: desactivado, sem apagar o registo.",
    )
    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Versão do par canal/valor. A desactivação não a incrementa.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="Instante de criação, com fuso horário.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="Instante da última alteração efectiva do contacto.",
    )


def normalize_contact_value(channel: ContactChannel, value: str) -> str:
    """Devolve o valor canónico ou recusa sem o incluir na mensagem.

    Telefone e WhatsApp ficam com ``+`` e 8 a 15 algarismos ASCII.
    O primeiro algarismo não é zero. Espaço, hífen, ponto e parêntesis
    ASCII são removidos. Não se infere indicativo de país.

    O email perde espaços exteriores e o domínio passa a minúsculas.
    A parte local conserva a forma introduzida. Não se reutiliza
    ``normalize_email`` da conta porque essa função também põe a parte
    local em minúsculas, e o login não é um contacto comercial.
    """

    if channel is ContactChannel.EMAIL:
        return _normalize_email(value)
    message = PHONE_INVALID if channel is ContactChannel.PHONE else WHATSAPP_INVALID
    return _normalize_phone(value, message)


def _normalize_phone(value: str, message: str) -> str:
    if any(_is_control(character) for character in value):
        raise ValueError(message)
    compact_source = value.strip()
    if compact_source == "" or any(character not in _phone_alphabet() for character in compact_source):
        raise ValueError(message)
    compact = "".join(
        character for character in compact_source if character not in PHONE_SEPARATORS
    )
    if PHONE_PATTERN.fullmatch(compact) is None:
        raise ValueError(message)
    return compact


def _phone_alphabet() -> set[str]:
    return set("0123456789" + "+" + PHONE_SEPARATORS)


def _normalize_email(value: str) -> str:
    if any(_is_control(character) for character in value):
        raise ValueError(EMAIL_INVALID)
    stripped = value.strip()
    if (
        stripped == ""
        or any(character.isspace() for character in stripped)
        or any(character in _email_forbidden() for character in stripped)
        or stripped.count("@") != 1
    ):
        raise ValueError(EMAIL_INVALID)
    local, domain = stripped.split("@")
    normalized = f"{local}@{domain.lower()}"
    if not _email_shape_is_valid(normalized):
        raise ValueError(EMAIL_INVALID)
    return normalized


def _email_forbidden() -> set[str]:
    return set("<>()[] ,;:\\\"'?#&=%/")


def _email_shape_is_valid(email: str) -> bool:
    """A mesma forma estrutural de ``ck_users_email``, com a parte local intacta."""

    if not 3 <= len(email) <= VALUE_MAX_LENGTH or " " in email:
        return False
    at_sign = email.find("@")
    if at_sign <= 0 or at_sign != email.rfind("@") or at_sign == len(email) - 1:
        return False
    local, domain = email.split("@")
    return local != "" and domain != "" and domain == domain.lower()


def _is_control(character: str) -> bool:
    code = ord(character)
    return code < 32 or code == 127


def contacts_of(session: Session, actor: Actor) -> list[PublicContact]:
    """Contactos deste actor, activos e inactivos, por canal, valor e id."""

    statement = (
        select(PublicContact)
        .where(PublicContact.actor_id == actor.id)
        .order_by(PublicContact.channel, PublicContact.value, PublicContact.id)
    )
    return list(session.scalars(statement))


def contact_for_actor(
    session: Session,
    actor: Actor,
    contact_id: uuid.UUID,
    *,
    lock: bool = False,
) -> PublicContact:
    """Só devolve o contacto quando o titular é o actor do caminho."""

    statement = select(PublicContact).where(
        PublicContact.id == contact_id,
        PublicContact.actor_id == actor.id,
    )
    if lock:
        statement = statement.with_for_update()
    contact = session.scalar(statement)
    if contact is None:
        raise ContactUnavailable
    return contact


def create_contact(
    session: Session,
    actor: Actor,
    channel: ContactChannel,
    value: str,
) -> PublicContact:
    """Cria um contacto privado e activo. O actor vem do caminho."""

    normalized = normalize_contact_value(channel, value)
    now = datetime.now(timezone.utc)
    contact = PublicContact(
        actor_id=actor.id,
        channel=channel,
        value=normalized,
        visibility=ContactVisibility.PRIVATE,
        status=ContactStatus.ACTIVE,
        revision=1,
        created_at=now,
        updated_at=now,
    )
    try:
        with session.begin_nested():
            session.add(contact)
            session.flush()
    except IntegrityError as exc:
        if contact in session:
            session.expunge(contact)
        if _is_duplicate(exc):
            raise ContactDuplicate from exc
        raise
    return contact


def update_contact(
    session: Session,
    actor: Actor,
    contact_id: uuid.UUID,
    changes: dict[str, ContactChannel | str],
) -> PublicContact:
    """Corrige canal ou valor. A revisão só avança quando o canónico muda.

    A linha fica bloqueada até ao fim da transacção. A concessão futura
    há-de usar o mesmo bloqueio e comparar a revisão confirmada.
    Uma revogação de representação confirmada depois desta leitura e
    antes do commit continua a ser a limitação já existente do pedido.
    """

    contact = contact_for_actor(session, actor, contact_id, lock=True)
    if contact.status is not ContactStatus.ACTIVE:
        raise ContactInactive
    if not changes:
        return contact

    channel = changes.get("channel", contact.channel)
    if not isinstance(channel, ContactChannel):
        channel = ContactChannel(channel)
    raw_value = changes.get("value", contact.value)
    if not isinstance(raw_value, str):
        raise ContactRejected(EMAIL_INVALID if channel is ContactChannel.EMAIL else PHONE_INVALID)
    try:
        normalized = normalize_contact_value(channel, raw_value)
    except ValueError as exc:
        raise ContactRejected(str(exc)) from exc

    if channel is contact.channel and normalized == contact.value:
        return contact

    now = datetime.now(timezone.utc)
    try:
        with session.begin_nested():
            contact.channel = channel
            contact.value = normalized
            contact.visibility = ContactVisibility.PRIVATE
            contact.revision += 1
            contact.updated_at = now
            session.flush()
    except IntegrityError as exc:
        session.expire(contact)
        if _is_duplicate(exc):
            raise ContactDuplicate from exc
        raise
    return contact


def deactivate_contact(
    session: Session,
    actor: Actor,
    contact_id: uuid.UUID,
) -> PublicContact:
    """Marca o contacto como inactivo. Repetir a operação não altera a linha."""

    contact = contact_for_actor(session, actor, contact_id, lock=True)
    if contact.status is ContactStatus.INACTIVE:
        return contact
    contact.status = ContactStatus.INACTIVE
    contact.visibility = ContactVisibility.PRIVATE
    contact.updated_at = datetime.now(timezone.utc)
    session.flush()
    return contact


def _is_duplicate(exc: IntegrityError) -> bool:
    origin = exc.orig
    state = getattr(origin, "sqlstate", None) or getattr(origin, "pgcode", None)
    if state == "23505":
        return True
    return "uq_public_contacts_active_channel_value" in str(origin)
