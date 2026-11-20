"""Ofertas comerciais de um actor (incremento I4).

A SRS v1.1 §3 e o diagrama de classes fixam os atributos. Os literais
de OfferStatus e AvailabilityStatus vêm do diagrama de estados
aprovado para este incremento. O rascunho pode ficar incompleto.
Publicar exige preço, moeda, quantidade, unidade e disponibilidade.

A oferta referencia um produto do mesmo actor. O dono vem do caminho.
O papel producer é exigido em cada escrita e não autoriza a representação.
Publicar muda só o estado. Não abre consulta pública nem divulga contactos.
"""

import re
import uuid
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
    select,
    text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base
from app.identity import Actor, closed_text
from app.products import (
    Product,
    ProductStatus,
    ProductUnavailable,
    require_producer_role,
)

CURRENCY = re.compile(r"^[A-Z]{3}$")
ARCHIVED_PRODUCT = "O produto está arquivado."
WITHDRAWN_OFFER = "A oferta retirada não pode ser alterada."
TRANSITION_REJECTED = "Transição de estado não permitida."
NOT_PUBLISHABLE = (
    "A publicação exige preço, moeda, quantidade, unidade e disponibilidade válidos."
)
ZERO_AVAILABLE = "Quantidade zero não pode estar disponível."
PUBLISHED_MUST_STAY_VALID = "A oferta publicada tem de permanecer válida."


class OfferStatus(StrEnum):
    """Ciclo de vida da oferta. Não é a disponibilidade comercial."""

    DRAFT = "draft"
    PUBLISHED = "published"
    SUSPENDED = "suspended"
    WITHDRAWN = "withdrawn"


class AvailabilityStatus(StrEnum):
    """Disponibilidade física ou comercial. Não é o estado de publicação."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class OfferUnavailable(Exception):
    """A oferta não existe neste actor."""


class OfferRejected(Exception):
    """A escrita viola uma regra da oferta. A linha não muda."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _values(enum_cls: type[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in enum_cls)


def _optional_text(enum_cls: type[StrEnum], comment: str):
    """Texto fechado e anulável. NULL significa que o rascunho ainda não o tem."""

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


class Offer(Base):
    """Oferta de um produto do mesmo actor. A consulta pública não está aqui."""

    __tablename__ = "offers"
    __table_args__ = (
        CheckConstraint("price IS NULL OR price >= 0", name="ck_offers_price"),
        CheckConstraint(
            "quantity IS NULL OR quantity >= 0",
            name="ck_offers_quantity",
        ),
        CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'",
            name="ck_offers_currency",
        ),
        CheckConstraint(
            "unit IS NULL OR char_length(btrim(unit)) > 0",
            name="ck_offers_unit",
        ),
        CheckConstraint(
            "delivery_terms IS NULL OR char_length(btrim(delivery_terms)) > 0",
            name="ck_offers_delivery_terms",
        ),
        CheckConstraint(
            f"availability IS NULL OR availability IN ({_values(AvailabilityStatus)})",
            name="ck_offers_availability",
        ),
        CheckConstraint(
            f"status IN ({_values(OfferStatus)})",
            name="ck_offers_status",
        ),
        CheckConstraint(
            "NOT (quantity = 0 AND availability = 'available')",
            name="ck_offers_quantity_availability",
        ),
        CheckConstraint(
            "status <> 'published' OR ("
            "price IS NOT NULL AND price >= 0 AND "
            "currency IS NOT NULL AND currency ~ '^[A-Z]{3}$' AND "
            "quantity IS NOT NULL AND quantity >= 0 AND "
            "unit IS NOT NULL AND char_length(btrim(unit)) > 0 AND "
            "availability IS NOT NULL AND "
            "NOT (quantity = 0 AND availability = 'available'))",
            name="ck_offers_published",
        ),
        ForeignKeyConstraint(
            ["product_id", "owner_actor_id"],
            ["products.id", "products.owner_actor_id"],
            name="fk_offers_product_owner",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        Index("ix_offers_owner_actor_id", "owner_actor_id"),
        Index("ix_offers_product_id", "product_id"),
        {
            "comment": (
                "Oferta comercial de um produto do mesmo actor. "
                "Publicar, suspender e retirar mudam o estado e mantêm a linha."
            )
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        comment="Produto referenciado. Tem de pertencer ao mesmo actor.",
    )
    owner_actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "actors.id",
            name="fk_offers_owner_actor_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        comment="Actor proprietário. Não é aceite no corpo do pedido.",
    )
    price: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
        comment="Preço em decimal exacto. NULL no rascunho. Não é ponto flutuante.",
    )
    currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        comment="Código de três letras maiúsculas. NULL no rascunho.",
    )
    quantity: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
        comment="Quantidade conhecida. Zero é valor, não ausência. NULL no rascunho.",
    )
    unit: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Unidade em texto livre. NULL no rascunho.",
    )
    availability: Mapped[AvailabilityStatus | None] = _optional_text(
        AvailabilityStatus,
        "Disponibilidade comercial. Distinta do estado de publicação. NULL no rascunho.",
    )
    delivery_terms: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Condições informativas de entrega. NULL significa ausência.",
    )
    status: Mapped[OfferStatus] = closed_text(
        OfferStatus,
        "draft: rascunho; published: publicada; suspended: suspensa; "
        "withdrawn: retirada, sem apagar o registo.",
    )


def offers_of(session: Session, actor: Actor) -> list[Offer]:
    """Ofertas deste actor, em qualquer estado, por id."""

    statement = (
        select(Offer)
        .where(Offer.owner_actor_id == actor.id)
        .order_by(Offer.id)
    )
    return list(session.scalars(statement))


def offer_for_actor(
    session: Session,
    actor: Actor,
    offer_id: uuid.UUID,
) -> Offer:
    """Só devolve a oferta quando o dono é o actor do caminho."""

    offer = session.scalar(
        select(Offer).where(
            Offer.id == offer_id,
            Offer.owner_actor_id == actor.id,
        )
    )
    if offer is None:
        raise OfferUnavailable
    return offer


def create_offer(
    session: Session,
    actor: Actor,
    product: Product,
    price: Decimal | None,
    currency: str | None,
    quantity: Decimal | None,
    unit: str | None,
    availability: AvailabilityStatus | None,
    delivery_terms: str | None,
) -> Offer:
    """Grava um rascunho do produto do actor autorizado."""

    require_producer_role(session, actor)
    if product.owner_actor_id != actor.id:
        raise ProductUnavailable
    if product.status is ProductStatus.ARCHIVED:
        raise OfferRejected(ARCHIVED_PRODUCT)
    _reject_zero_available(quantity, availability)
    offer = Offer(
        product_id=product.id,
        owner_actor_id=actor.id,
        price=price,
        currency=currency,
        quantity=quantity,
        unit=unit,
        availability=availability,
        delivery_terms=delivery_terms,
        status=OfferStatus.DRAFT,
    )
    with session.begin_nested():
        session.add(offer)
        remember_new_offer(session, offer)
    return offer


def remember_new_offer(session: Session, offer: Offer) -> None:
    session.flush()


def update_offer(
    session: Session,
    actor: Actor,
    offer: Offer,
    fields: dict[str, Decimal | str | AvailabilityStatus | None],
) -> Offer:
    """Altera os campos presentes. O estado, o produto e o dono ficam quietos."""

    require_producer_role(session, actor)
    if offer.status is OfferStatus.WITHDRAWN:
        raise OfferRejected(WITHDRAWN_OFFER)
    if not fields:
        return offer
    values = _resulting(offer, fields)
    _reject_zero_available(values["quantity"], values["availability"])
    if offer.status is OfferStatus.PUBLISHED and not _publishable(values):
        raise OfferRejected(PUBLISHED_MUST_STAY_VALID)
    with session.begin_nested():
        apply_offer_changes(session, offer, fields)
    return offer


def apply_offer_changes(
    session: Session,
    offer: Offer,
    fields: dict[str, Decimal | str | AvailabilityStatus | None],
) -> None:
    for name in (
        "price",
        "currency",
        "quantity",
        "unit",
        "availability",
        "delivery_terms",
    ):
        if name in fields:
            setattr(offer, name, fields[name])
    session.flush()


def publish_offer(session: Session, actor: Actor, offer: Offer) -> Offer:
    """Muda só o estado para published.

    Não publica contactos nem abre consulta pública. Um produto arquivado
    recusa a publicação e a republicação. Se o produto for arquivado
    depois, a oferta publicada mantém o estado e deixa de ser elegível
    para a consulta pública de um incremento futuro.
    """

    require_producer_role(session, actor)
    if offer.status not in (OfferStatus.DRAFT, OfferStatus.SUSPENDED):
        raise OfferRejected(TRANSITION_REJECTED)
    product = session.get(Product, offer.product_id)
    if product is None or product.status is ProductStatus.ARCHIVED:
        raise OfferRejected(ARCHIVED_PRODUCT)
    if not _publishable(_commercial(offer)):
        raise OfferRejected(NOT_PUBLISHABLE)
    with session.begin_nested():
        mark_published(session, offer)
    return offer


def suspend_offer(session: Session, actor: Actor, offer: Offer) -> Offer:
    """Muda só o estado, de published para suspended."""

    require_producer_role(session, actor)
    if offer.status is not OfferStatus.PUBLISHED:
        raise OfferRejected(TRANSITION_REJECTED)
    with session.begin_nested():
        mark_suspended(session, offer)
    return offer


def withdraw_offer(session: Session, actor: Actor, offer: Offer) -> Offer:
    """Termina o ciclo. A linha permanece e não volta a outro estado."""

    require_producer_role(session, actor)
    if offer.status not in (
        OfferStatus.DRAFT,
        OfferStatus.PUBLISHED,
        OfferStatus.SUSPENDED,
    ):
        raise OfferRejected(TRANSITION_REJECTED)
    with session.begin_nested():
        mark_withdrawn(session, offer)
    return offer


def mark_published(session: Session, offer: Offer) -> None:
    offer.status = OfferStatus.PUBLISHED
    session.flush()


def mark_suspended(session: Session, offer: Offer) -> None:
    offer.status = OfferStatus.SUSPENDED
    session.flush()


def mark_withdrawn(session: Session, offer: Offer) -> None:
    offer.status = OfferStatus.WITHDRAWN
    session.flush()


def _commercial(offer: Offer) -> dict[str, Decimal | str | AvailabilityStatus | None]:
    return {
        "price": offer.price,
        "currency": offer.currency,
        "quantity": offer.quantity,
        "unit": offer.unit,
        "availability": offer.availability,
        "delivery_terms": offer.delivery_terms,
    }


def _resulting(
    offer: Offer,
    fields: dict[str, Decimal | str | AvailabilityStatus | None],
) -> dict[str, Decimal | str | AvailabilityStatus | None]:
    values = _commercial(offer)
    values.update(fields)
    return values


def _reject_zero_available(
    quantity: Decimal | None,
    availability: AvailabilityStatus | None,
) -> None:
    if (
        quantity is not None
        and quantity == 0
        and availability is AvailabilityStatus.AVAILABLE
    ):
        raise OfferRejected(ZERO_AVAILABLE)


def _publishable(
    values: dict[str, Decimal | str | AvailabilityStatus | None],
) -> bool:
    price = values["price"]
    currency = values["currency"]
    quantity = values["quantity"]
    unit = values["unit"]
    availability = values["availability"]
    if not isinstance(price, Decimal) or price < 0:
        return False
    if not isinstance(currency, str) or CURRENCY.fullmatch(currency) is None:
        return False
    if not isinstance(quantity, Decimal) or quantity < 0:
        return False
    if not isinstance(unit, str) or unit.strip() == "":
        return False
    if availability not in (AvailabilityStatus.AVAILABLE, AvailabilityStatus.UNAVAILABLE):
        return False
    if quantity == 0 and availability is AvailabilityStatus.AVAILABLE:
        return False
    return True
