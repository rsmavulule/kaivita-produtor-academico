"""Pedidos privados das ofertas de um actor.

A representação usa ``actor_for_read`` e ``actor_for_manage``.
Actor inacessível, associação revogada e nível insuficiente respondem
404, como no I1.3. A oferta ou o produto de outro actor, no caminho de
um actor autorizado, responde 404 sem devolver os dados desse recurso.

O dono é o actor do caminho. ``owner_actor_id`` no corpo é recusado.
Publicar, suspender e retirar mudam o estado. Não há rota pública.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.authorization import ActorUnavailable, actor_for_manage, actor_for_read
from app.db import get_session
from app.identity import User
from app.offers import (
    AvailabilityStatus,
    Offer,
    OfferRejected,
    OfferStatus,
    OfferUnavailable,
    create_offer,
    offer_for_actor,
    offers_of,
    publish_offer,
    suspend_offer,
    update_offer,
    withdraw_offer,
)
from app.products import ProducerRoleMissing, ProductUnavailable, product_for_actor

router = APIRouter(prefix="/actors/{actor_id}/offers", tags=["ofertas"])

ACTOR_NOT_FOUND = "Actor não encontrado."
OFFER_NOT_FOUND = "Oferta não encontrada."
PRODUCT_NOT_FOUND = "Produto não encontrado."
PRODUCER_REQUIRED = "O actor não tem o papel producer."
DECIMAL_TEXT = re.compile(r"^\d+(\.\d+)?$")
_MUTABLE = (
    "price",
    "currency",
    "quantity",
    "unit",
    "availability",
    "delivery_terms",
)


def _decimal(value: object, message: str) -> str | None:
    """Aceita texto decimal ou inteiro. Recusa ponto flutuante.

    O resultado é texto canónico. O esquema OpenAPI fica string, para o
    cliente não enviar um número JSON com casa decimal.
    """

    if value is None:
        return None
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(message)
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, int):
        number = Decimal(value)
    elif isinstance(value, str) and DECIMAL_TEXT.fullmatch(value):
        try:
            number = Decimal(value)
        except InvalidOperation:
            raise ValueError(message) from None
    else:
        raise ValueError(message)
    if not number.is_finite() or number < 0:
        raise ValueError(message)
    return format(number, "f")


def _price(value: object) -> Decimal | None:
    return _decimal(value, "Preço inválido.")


def _quantity(value: object) -> Decimal | None:
    return _decimal(value, "Quantidade inválida.")


def _optional_text(value: str | None, message: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(message)
    return value


class OfferResponse(BaseModel):
    id: UUID
    product_id: UUID
    owner_actor_id: UUID
    price: Annotated[str | None, Field(examples=["150.00"])]
    currency: str | None
    quantity: Annotated[str | None, Field(examples=["2.50"])]
    unit: str | None
    availability: AvailabilityStatus | None
    delivery_terms: str | None
    status: OfferStatus


class OfferCreate(BaseModel):
    """Produto obrigatório. Os restantes campos podem esperar pela publicação."""

    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    price: Annotated[str | None, BeforeValidator(_price), Field(examples=["150.00"])] = None
    currency: str | None = None
    quantity: Annotated[
        str | None,
        BeforeValidator(_quantity),
        Field(examples=["2.50"]),
    ] = None
    unit: str | None = None
    availability: AvailabilityStatus | None = None
    delivery_terms: str | None = None

    @field_validator("currency")
    @classmethod
    def currency_is_a_code(cls, value: str | None) -> str | None:
        return _currency(value)

    @field_validator("unit")
    @classmethod
    def unit_is_present_or_absent(cls, value: str | None) -> str | None:
        return _optional_text(value, "Unidade inválida.")

    @field_validator("delivery_terms")
    @classmethod
    def delivery_is_present_or_absent(cls, value: str | None) -> str | None:
        return _optional_text(value, "Condições de entrega inválidas.")


class OfferUpdate(BaseModel):
    """Campos comerciais. O estado muda só nas rotas de transição."""

    model_config = ConfigDict(extra="forbid")

    price: Annotated[str | None, BeforeValidator(_price), Field(examples=["150.00"])] = None
    currency: str | None = None
    quantity: Annotated[
        str | None,
        BeforeValidator(_quantity),
        Field(examples=["2.50"]),
    ] = None
    unit: str | None = None
    availability: AvailabilityStatus | None = None
    delivery_terms: str | None = None

    @field_validator("currency")
    @classmethod
    def currency_is_a_code(cls, value: str | None) -> str | None:
        return _currency(value)

    @field_validator("unit")
    @classmethod
    def unit_is_present_or_absent(cls, value: str | None) -> str | None:
        return _optional_text(value, "Unidade inválida.")

    @field_validator("delivery_terms")
    @classmethod
    def delivery_is_present_or_absent(cls, value: str | None) -> str | None:
        return _optional_text(value, "Condições de entrega inválidas.")


def _currency(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or re.fullmatch(r"[A-Z]{3}", value) is None:
        raise ValueError("Moeda inválida.")
    return value


def _missing_actor() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ACTOR_NOT_FOUND)


def _missing_offer() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=OFFER_NOT_FOUND)


def _missing_product() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=PRODUCT_NOT_FOUND,
    )


def _missing_producer_role() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=PRODUCER_REQUIRED,
    )


def _rejected(exc: OfferRejected) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=exc.detail,
    )


def _as_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(value)


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _present(offer: Offer) -> OfferResponse:
    return OfferResponse(
        id=offer.id,
        product_id=offer.product_id,
        owner_actor_id=offer.owner_actor_id,
        price=_decimal_text(offer.price),
        currency=offer.currency,
        quantity=_decimal_text(offer.quantity),
        unit=offer.unit,
        availability=offer.availability,
        delivery_terms=offer.delivery_terms,
        status=offer.status,
    )


def _changes(
    body: OfferUpdate,
) -> dict[str, Decimal | str | AvailabilityStatus | None]:
    values: dict[str, Decimal | str | AvailabilityStatus | None] = {}
    for name in _MUTABLE:
        if name not in body.model_fields_set:
            continue
        value = getattr(body, name)
        if name in ("price", "quantity"):
            value = _as_decimal(value)
        values[name] = value
    return values


@router.post("", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
def add_offer(
    actor_id: UUID,
    body: OfferCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> OfferResponse:
    try:
        actor = actor_for_manage(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    try:
        product = product_for_actor(session, actor, body.product_id)
    except ProductUnavailable:
        raise _missing_product() from None
    try:
        offer = create_offer(
            session,
            actor,
            product,
            _as_decimal(body.price),
            body.currency,
            _as_decimal(body.quantity),
            body.unit,
            body.availability,
            body.delivery_terms,
        )
    except ProducerRoleMissing:
        raise _missing_producer_role() from None
    except OfferRejected as exc:
        raise _rejected(exc) from None
    return _present(offer)


@router.get("", response_model=list[OfferResponse])
def list_offers(
    actor_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[OfferResponse]:
    try:
        actor = actor_for_read(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    return [_present(offer) for offer in offers_of(session, actor)]


@router.get("/{offer_id}", response_model=OfferResponse)
def read_offer(
    actor_id: UUID,
    offer_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> OfferResponse:
    try:
        actor = actor_for_read(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    try:
        offer = offer_for_actor(session, actor, offer_id)
    except OfferUnavailable:
        raise _missing_offer() from None
    return _present(offer)


@router.patch("/{offer_id}", response_model=OfferResponse)
def edit_offer(
    actor_id: UUID,
    offer_id: UUID,
    body: OfferUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> OfferResponse:
    try:
        actor = actor_for_manage(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    try:
        offer = offer_for_actor(session, actor, offer_id)
    except OfferUnavailable:
        raise _missing_offer() from None
    try:
        update_offer(session, actor, offer, _changes(body))
    except ProducerRoleMissing:
        raise _missing_producer_role() from None
    except OfferRejected as exc:
        raise _rejected(exc) from None
    return _present(offer)


def _change_status(action, actor_id: UUID, offer_id: UUID, session: Session, user: User):
    try:
        actor = actor_for_manage(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    try:
        offer = offer_for_actor(session, actor, offer_id)
    except OfferUnavailable:
        raise _missing_offer() from None
    try:
        action(session, actor, offer)
    except ProducerRoleMissing:
        raise _missing_producer_role() from None
    except OfferRejected as exc:
        raise _rejected(exc) from None
    return _present(offer)


@router.post("/{offer_id}/publish", response_model=OfferResponse)
def publish_actor_offer(
    actor_id: UUID,
    offer_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> OfferResponse:
    return _change_status(publish_offer, actor_id, offer_id, session, user)


@router.post("/{offer_id}/suspend", response_model=OfferResponse)
def suspend_actor_offer(
    actor_id: UUID,
    offer_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> OfferResponse:
    return _change_status(suspend_offer, actor_id, offer_id, session, user)


@router.post("/{offer_id}/withdraw", response_model=OfferResponse)
def withdraw_actor_offer(
    actor_id: UUID,
    offer_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> OfferResponse:
    return _change_status(withdraw_offer, actor_id, offer_id, session, user)
