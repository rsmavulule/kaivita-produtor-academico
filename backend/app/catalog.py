"""Pedidos do catálogo de produtos de um actor.

A representação usa ``actor_for_read`` e ``actor_for_manage``.
Actor inacessível, associação revogada e nível insuficiente respondem
404, como no I1.3. O produto de outro actor, no caminho de um actor
autorizado, responde 404 sem devolver os dados desse produto.

O dono é o actor do caminho. ``owner_actor_id`` no corpo é recusado.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.authorization import ActorUnavailable, actor_for_manage, actor_for_read
from app.db import get_session
from app.identity import User
from app.products import (
    IMAGE_DECLARATION_REQUIRED,
    ImageDeclarationError,
    ProducerRoleMissing,
    Product,
    ProductStatus,
    ProductUnavailable,
    archive_product,
    create_product,
    normalize_image_ref,
    product_for_actor,
    products_of,
    update_product,
)

router = APIRouter(prefix="/actors/{actor_id}/products", tags=["produtos"])

ACTOR_NOT_FOUND = "Actor não encontrado."
PRODUCT_NOT_FOUND = "Produto não encontrado."
PRODUCER_REQUIRED = "O actor não tem o papel producer."


class ProductResponse(BaseModel):
    id: UUID
    owner_actor_id: UUID
    name: str
    description: str
    category: str
    image_ref: str | None
    image_use_confirmed: bool
    status: ProductStatus

    model_config = ConfigDict(from_attributes=True)


class ProductCreate(BaseModel):
    """Nome, descrição e categoria. A fotografia e a declaração são opcionais."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    category: str
    image_ref: str | None = None
    image_use_confirmed: bool = False

    @field_validator("name")
    @classmethod
    def name_is_present(cls, value: str) -> str:
        return _required_text(value, "Nome inválido.")

    @field_validator("description")
    @classmethod
    def description_is_present(cls, value: str) -> str:
        return _required_text(value, "Descrição inválida.")

    @field_validator("category")
    @classmethod
    def category_is_present(cls, value: str) -> str:
        return _required_text(value, "Categoria inválida.")

    @field_validator("image_ref")
    @classmethod
    def image_ref_is_https_or_absent(cls, value: str | None) -> str | None:
        return normalize_image_ref(value)

    @field_validator("image_use_confirmed")
    @classmethod
    def declaration_needs_the_photograph(cls, value: bool, info) -> bool:
        if value and info.data.get("image_ref") is None:
            raise ValueError(IMAGE_DECLARATION_REQUIRED)
        return value


class ProductUpdate(BaseModel):
    """Campos descritivos. O estado muda só em /archive."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    category: str | None = None
    image_ref: str | None = None
    image_use_confirmed: bool | None = None

    @field_validator("name")
    @classmethod
    def name_is_present(cls, value: str | None) -> str | None:
        return _required_text(value, "Nome inválido.")

    @field_validator("description")
    @classmethod
    def description_is_present(cls, value: str | None) -> str | None:
        return _required_text(value, "Descrição inválida.")

    @field_validator("category")
    @classmethod
    def category_is_present(cls, value: str | None) -> str | None:
        return _required_text(value, "Categoria inválida.")

    @field_validator("image_ref")
    @classmethod
    def image_ref_is_https_or_absent(cls, value: str | None) -> str | None:
        return normalize_image_ref(value)


def _required_text(value: str | None, message: str) -> str:
    if value is None or value.strip() == "":
        raise ValueError(message)
    return value


def _missing_actor() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ACTOR_NOT_FOUND)


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


def _reject_image(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=message,
    )


def _present(product: Product) -> ProductResponse:
    return ProductResponse.model_validate(product)


def _changes(body: ProductUpdate, declared_by: UUID) -> dict[str, object]:
    fields: dict[str, object] = {
        name: getattr(body, name)
        for name in ("name", "description", "category", "image_ref")
        if name in body.model_fields_set
    }
    if "image_use_confirmed" in body.model_fields_set:
        fields["image_use_confirmed"] = body.image_use_confirmed
        fields["declared_by"] = declared_by
    return fields


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def add_product(
    actor_id: UUID,
    body: ProductCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ProductResponse:
    try:
        actor = actor_for_manage(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    try:
        product = create_product(
            session,
            actor,
            body.name,
            body.description,
            body.category,
            body.image_ref,
            body.image_use_confirmed,
            user.id,
        )
    except ProducerRoleMissing:
        raise _missing_producer_role() from None
    except ImageDeclarationError as exc:
        raise _reject_image(str(exc)) from None
    return _present(product)


@router.get("", response_model=list[ProductResponse])
def list_products(
    actor_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[ProductResponse]:
    try:
        actor = actor_for_read(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    return [_present(product) for product in products_of(session, actor)]


@router.get("/{product_id}", response_model=ProductResponse)
def read_product(
    actor_id: UUID,
    product_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ProductResponse:
    try:
        actor = actor_for_read(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    try:
        product = product_for_actor(session, actor, product_id)
    except ProductUnavailable:
        raise _missing_product() from None
    return _present(product)


@router.patch("/{product_id}", response_model=ProductResponse)
def edit_product(
    actor_id: UUID,
    product_id: UUID,
    body: ProductUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ProductResponse:
    try:
        actor = actor_for_manage(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    try:
        product = product_for_actor(session, actor, product_id)
    except ProductUnavailable:
        raise _missing_product() from None
    try:
        update_product(session, actor, product, _changes(body, user.id))
    except ProducerRoleMissing:
        raise _missing_producer_role() from None
    except ImageDeclarationError as exc:
        raise _reject_image(str(exc)) from None
    return _present(product)


@router.post("/{product_id}/archive", response_model=ProductResponse)
def archive_actor_product(
    actor_id: UUID,
    product_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ProductResponse:
    try:
        actor = actor_for_manage(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    try:
        product = product_for_actor(session, actor, product_id)
    except ProductUnavailable:
        raise _missing_product() from None
    try:
        archive_product(session, actor, product)
    except ProducerRoleMissing:
        raise _missing_producer_role() from None
    return _present(product)
