"""Pedidos privados dos contactos comerciais de um actor.

A representação usa ``actor_for_read`` e ``actor_for_manage``.
Actor inacessível e nível insuficiente respondem 404, como no I1.3.
O contacto de outro actor, no caminho de um actor autorizado, responde
404 sem devolver o valor.

O dono é o actor do caminho. O corpo não escolhe actor, estado,
visibilidade, revisão nem autorização. A concessão e a revogação
estão em ``publication_catalog``. A resposta privada continua sem
o valor histórico das autorizações.
"""

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator
from sqlalchemy.orm import Session
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.auth import get_current_user
from app.authorization import ActorUnavailable, actor_for_manage, actor_for_read
from app.contacts import (
    ContactChannel,
    ContactDuplicate,
    ContactInactive,
    ContactRejected,
    ContactStatus,
    ContactUnavailable,
    ContactVisibility,
    PublicContact,
    contact_for_actor,
    contacts_of,
    create_contact,
    deactivate_contact,
    normalize_contact_value,
    update_contact,
)
from app.db import get_session
from app.identity import User

router = APIRouter(prefix="/actors/{actor_id}/contacts", tags=["contactos"])

ACTOR_NOT_FOUND = "Actor não encontrado."
CONTACT_NOT_FOUND = "Contacto não encontrado."
_CONTACT_PATH = re.compile(r"^/actors/[^/]+/contacts(?:/.*)?$")


class ContactResponse(BaseModel):
    id: UUID
    channel: ContactChannel
    value: str
    visibility: ContactVisibility
    status: ContactStatus
    revision: int
    created_at: str
    updated_at: str

    model_config = ConfigDict(extra="forbid")


class ContactListResponse(BaseModel):
    items: list[ContactResponse]

    model_config = ConfigDict(extra="forbid")


class ContactCreate(BaseModel):
    """Canal e valor. O actor, o estado e a visibilidade não vêm no corpo."""

    model_config = ConfigDict(extra="forbid")

    channel: ContactChannel
    value: str

    @field_validator("channel")
    @classmethod
    def channel_is_present(cls, value: ContactChannel | None) -> ContactChannel:
        if value is None:
            raise ValueError("O campo não pode ser nulo.")
        return value

    @field_validator("value")
    @classmethod
    def value_is_canonical(cls, value: str | None, info: ValidationInfo) -> str:
        if value is None:
            raise ValueError("O campo não pode ser nulo.")
        channel = info.data.get("channel")
        if not isinstance(channel, ContactChannel):
            raise ValueError("Contacto inválido.")
        return normalize_contact_value(channel, value)


class ContactUpdate(BaseModel):
    """Correcção de canal ou valor. Os restantes campos ficam de fora."""

    model_config = ConfigDict(extra="forbid")

    channel: ContactChannel | None = None
    value: str | None = None

    @model_validator(mode="before")
    @classmethod
    def nulls_are_rejected(cls, data: object) -> object:
        if isinstance(data, dict):
            for field in ("channel", "value"):
                if field in data and data[field] is None:
                    raise ValueError("O campo não pode ser nulo.")
        return data


class PrivateContactNoStore:
    """Acrescenta ``Cache-Control: private, no-store`` às rotas de contactos.

    Cobre o sucesso e os erros destes caminhos, incluindo 401, 404 e 422.
    As outras rotas, incluindo ``/public/``, não são alteradas por aqui.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope.get("type") != "http" or not _contact_path(path):
            await self.app(scope, receive, send)
            return

        async def send_private(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["cache-control"] = "private, no-store"
            await send(message)

        await self.app(scope, receive, send_private)


def _contact_path(path: object) -> bool:
    return isinstance(path, str) and _CONTACT_PATH.fullmatch(path) is not None


def _missing_actor() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ACTOR_NOT_FOUND)


def _missing_contact() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=CONTACT_NOT_FOUND,
    )


def _rejected(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=detail,
    )


def _present(contact: PublicContact) -> ContactResponse:
    return ContactResponse(
        id=contact.id,
        channel=contact.channel,
        value=contact.value,
        visibility=contact.visibility,
        status=contact.status,
        revision=contact.revision,
        created_at=contact.created_at.isoformat(),
        updated_at=contact.updated_at.isoformat(),
    )


def _changes(body: ContactUpdate) -> dict[str, ContactChannel | str]:
    changes: dict[str, ContactChannel | str] = {}
    if "channel" in body.model_fields_set and body.channel is not None:
        changes["channel"] = body.channel
    if "value" in body.model_fields_set and body.value is not None:
        changes["value"] = body.value
    return changes


@router.get("", response_model=ContactListResponse)
def list_contacts(
    actor_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ContactListResponse:
    try:
        actor = actor_for_read(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    return ContactListResponse(items=[_present(contact) for contact in contacts_of(session, actor)])


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def add_contact(
    actor_id: UUID,
    body: ContactCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ContactResponse:
    try:
        actor = actor_for_manage(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    try:
        contact = create_contact(session, actor, body.channel, body.value)
    except ContactDuplicate as exc:
        raise _rejected(exc.detail) from None
    return _present(contact)


@router.get("/{contact_id}", response_model=ContactResponse)
def read_contact(
    actor_id: UUID,
    contact_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ContactResponse:
    try:
        actor = actor_for_read(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    try:
        contact = contact_for_actor(session, actor, contact_id)
    except ContactUnavailable:
        raise _missing_contact() from None
    return _present(contact)


@router.patch("/{contact_id}", response_model=ContactResponse)
def edit_contact(
    actor_id: UUID,
    contact_id: UUID,
    body: ContactUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ContactResponse:
    try:
        actor = actor_for_manage(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    try:
        contact = update_contact(
            session,
            actor,
            contact_id,
            _changes(body),
            operator_id=user.id,
        )
    except ContactUnavailable:
        raise _missing_contact() from None
    except ContactInactive as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.detail,
        ) from None
    except ContactRejected as exc:
        raise _rejected(exc.detail) from None
    except ContactDuplicate as exc:
        raise _rejected(exc.detail) from None
    return _present(contact)


@router.post("/{contact_id}/deactivate", response_model=ContactResponse)
def deactivate_actor_contact(
    actor_id: UUID,
    contact_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ContactResponse:
    try:
        actor = actor_for_manage(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    try:
        contact = deactivate_contact(
            session,
            actor,
            contact_id,
            operator_id=user.id,
        )
    except ContactUnavailable:
        raise _missing_contact() from None
    return _present(contact)
