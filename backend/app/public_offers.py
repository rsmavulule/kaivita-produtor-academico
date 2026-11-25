"""Consulta pública de ofertas.

A elegibilidade é calculada na leitura. Não há coluna própria.
A mesma condição serve a lista, a contagem e a ficha.

Uma oferta é elegível quando, ao mesmo tempo:

- o estado é ``published``;
- o produto está ``active``;
- o actor está ``active``;
- o actor tem o papel ``producer``;
- a disponibilidade é ``available`` ou ``unavailable``.

``UserActorAccess`` não entra. Uma oferta ``unavailable``, mesmo com
quantidade zero, continua elegível. Perder o papel ``producer`` tira a
oferta da consulta e não muda o estado gravado.

A lista e o total saem de uma única instrução SQL. A página vazia
também devolve o total, pelo que os dois não divergem dentro do
pedido. A sessão continua em READ COMMITTED: o pedido vê o que já
estava confirmado quando a instrução começou.

A normalização da pesquisa usa um mapa explícito de acentos
portugueses e de ``A-Z``. Não depende da collation de ``lower()``.
Não há extensão PostgreSQL. Caracteres fora do mapa, incluindo
``ñ``, permanecem. Formas Unicode decompostas, como ``a`` seguido
de acento combinante, não são recompostas. No SQL, sequências de
espaço POSIX (``[[:space:]]``) passam a um espaço e ``btrim`` corta
os espaços das pontas. O termo é normalizado em Python com ``\\s``,
que também cobre espaços Unicode como o espaço não separável. Um
espaço desses gravado na coluna pode não coincidir com o termo.
"""

import re
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import (
    ColumnElement,
    Select,
    and_,
    func,
    or_,
    select,
    true,
)
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from app.contacts import ContactStatus, ContactVisibility, PublicContact
from app.identity import Actor, ActorRole, ActorStatus, Role, RoleCode
from app.offers import AvailabilityStatus, Offer, OfferStatus
from app.products import Product, ProductStatus
from app.publication import DisclosurePurpose, PublicationAuthorization

_ACCENTED = (
    ("áàâãÁÀÂÃ", "a"),
    ("éèêÉÈÊ", "e"),
    ("íìîÍÌÎ", "i"),
    ("óòôõÓÒÔÕ", "o"),
    ("úùûüÚÙÛÜ", "u"),
    ("çÇ", "c"),
)
FOLD_FROM = "".join(chars for chars, _base in _ACCENTED) + "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
FOLD_TO = "".join(base * len(chars) for chars, base in _ACCENTED) + "abcdefghijklmnopqrstuvwxyz"
if len(FOLD_FROM) != len(FOLD_TO) or len(set(FOLD_FROM)) != len(FOLD_FROM):
    raise RuntimeError("Mapa de normalização incoerente.")

_FOLD = str.maketrans(FOLD_FROM, FOLD_TO)
_WHITESPACE = re.compile(r"\s+")
_LIKE_ESCAPE = "\\"


@dataclass(frozen=True)
class PublicSearch:
    """Filtros já validados. Texto vazio significa filtro ausente."""

    text: str | None
    category: str | None
    location: str | None
    limit: int
    offset: int


@dataclass(frozen=True)
class PublicContactData:
    """Contacto divulgável. Só o canal e o valor canónico actual."""

    channel: str
    value: str


@dataclass(frozen=True)
class PublicOfferData:
    """Projecção pública. Não transporta o modelo ORM."""

    id: uuid.UUID
    price: str
    currency: str
    quantity: str
    unit: str
    availability: str
    delivery_terms: str | None
    product_name: str
    product_description: str
    product_category: str
    producer_name: str
    producer_kind: str
    producer_location: str | None


def normalize_search_text(value: str) -> str:
    """Minúsculas, acentos do mapa e espaços internos num só."""

    return _WHITESPACE.sub(" ", value.translate(_FOLD)).strip()


def like_pattern(normalized: str) -> str:
    """Pesquisa parcial. ``%``, ``_`` e a barra invertida ficam literais."""

    escaped = (
        normalized.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2)
        .replace("%", _LIKE_ESCAPE + "%")
        .replace("_", _LIKE_ESCAPE + "_")
    )
    return f"%{escaped}%"


def public_offer_page(
    session: Session,
    search: PublicSearch,
) -> tuple[list[PublicOfferData], int]:
    """Uma instrução devolve a página e o total do mesmo predicado."""

    rows = session.execute(_page_statement(search)).all()
    if not rows or rows[0].id is None:
        total = int(rows[0].total) if rows else 0
        return [], total
    return [_present(row) for row in rows], int(rows[0].total)


def public_offer(session: Session, offer_id: uuid.UUID) -> PublicOfferData | None:
    """A ficha usa o mesmo predicado da lista. None é inelegível ou ausente."""

    row = session.execute(_detail_statement(offer_id)).one_or_none()
    if row is None:
        return None
    return _present(row)


def public_offer_contacts(
    session: Session,
    offer_id: uuid.UUID,
) -> list[PublicContactData] | None:
    """Contactos divulgáveis da oferta, na mesma instrução da elegibilidade.

    None significa oferta inexistente ou inelegível. A lista vazia
    significa oferta elegível sem contacto que cumpra o predicado.
    A sessão está em READ COMMITTED: a instrução vê um snapshot.
    Outra instrução posterior pode ver uma revogação entretanto confirmada.
    """

    rows = session.execute(_contact_statement(offer_id)).all()
    if not rows:
        return None
    disclosed: list[PublicContactData] = []
    for row in rows:
        channel = _code(row.channel) if row.channel is not None else None
        value = row.value if isinstance(row.value, str) else None
        if channel is None or value is None:
            continue
        disclosed.append(PublicContactData(channel=channel, value=value))
    return disclosed


def _folded(column: ColumnElement[str]) -> ColumnElement[str]:
    translated = func.translate(column, FOLD_FROM, FOLD_TO)
    collapsed = func.regexp_replace(translated, "[[:space:]]+", " ", "g")
    return func.btrim(collapsed)


def _producer_exists():
    return (
        select(Role.id)
        .select_from(Role)
        .join(ActorRole, ActorRole.role_id == Role.id)
        .where(
            ActorRole.actor_id == Offer.owner_actor_id,
            Role.code == RoleCode.PRODUCER,
        )
        .exists()
    )


def _eligible():
    return and_(
        Offer.status == OfferStatus.PUBLISHED,
        Product.status == ProductStatus.ACTIVE,
        Actor.status == ActorStatus.ACTIVE,
        _producer_exists(),
        Offer.availability.in_(
            (AvailabilityStatus.AVAILABLE, AvailabilityStatus.UNAVAILABLE)
        ),
    )


def _joined(statement: Select[tuple]) -> Select[tuple]:
    return statement.join(
        Product,
        and_(
            Product.id == Offer.product_id,
            Product.owner_actor_id == Offer.owner_actor_id,
        ),
    ).join(Actor, Actor.id == Offer.owner_actor_id)


def _columns() -> tuple:
    return (
        Offer.id.label("id"),
        Offer.price.label("price"),
        Offer.currency.label("currency"),
        Offer.quantity.label("quantity"),
        Offer.unit.label("unit"),
        Offer.availability.label("availability"),
        Offer.delivery_terms.label("delivery_terms"),
        Product.name.label("product_name"),
        Product.description.label("product_description"),
        Product.category.label("product_category"),
        Actor.display_name.label("producer_name"),
        Actor.kind.label("producer_kind"),
        Actor.general_location.label("producer_location"),
        _folded(Product.name).label("sort_name"),
    )


def _catalog(search: PublicSearch | None, offer_id: uuid.UUID | None) -> Select[tuple]:
    statement = _joined(select(*_columns())).where(_eligible())
    if offer_id is not None:
        statement = statement.where(Offer.id == offer_id)
    if search is not None:
        statement = _filtered(statement, search)
    return statement


def _filtered(statement: Select[tuple], search: PublicSearch) -> Select[tuple]:
    if search.text is not None:
        pattern = like_pattern(search.text)
        statement = statement.where(
            or_(
                _folded(Product.name).ilike(pattern, escape=_LIKE_ESCAPE),
                _folded(Product.description).ilike(pattern, escape=_LIKE_ESCAPE),
            )
        )
    if search.category is not None:
        statement = statement.where(
            _folded(Product.category).ilike(
                like_pattern(search.category),
                escape=_LIKE_ESCAPE,
            )
        )
    if search.location is not None:
        statement = statement.where(
            _folded(Actor.general_location).ilike(
                like_pattern(search.location),
                escape=_LIKE_ESCAPE,
            )
        )
    return statement


def _page_statement(search: PublicSearch) -> Select[tuple]:
    eligible = _catalog(search, None).cte("eligible")
    page = (
        select(eligible)
        .order_by(eligible.c.sort_name.asc(), eligible.c.id.asc())
        .limit(search.limit)
        .offset(search.offset)
        .lateral("page_rows")
    )
    totals = (
        select(func.count().label("total"))
        .select_from(eligible)
        .subquery("totals")
    )
    columns = [page.c[name] for name in eligible.c.keys() if name != "sort_name"]
    return (
        select(*columns, totals.c.total)
        .select_from(totals)
        .outerjoin(page, true())
        .add_cte(eligible)
    )


def _detail_statement(offer_id: uuid.UUID) -> Select[tuple]:
    return _catalog(None, offer_id)


def _contact_statement(offer_id: uuid.UUID) -> Select[tuple]:
    """Uma instrução distingue oferta inelegível de oferta sem contactos.

    A oferta elegível fica num subselect. Os contactos divulgáveis ficam
    noutro, já filtrados pela autorização vigente. O LEFT JOIN entre os
    dois preserva a oferta quando não há contacto que cumpra o predicado.
    """

    eligible = (
        _joined(
            select(
                Offer.id.label("offer_id"),
                Offer.owner_actor_id.label("owner_actor_id"),
            )
        )
        .where(_eligible(), Offer.id == offer_id)
        .subquery("eligible_offer")
    )
    disclosed = (
        select(
            PublicContact.actor_id.label("actor_id"),
            PublicContact.id.label("contact_id"),
            PublicContact.channel.label("channel"),
            PublicContact.value.label("value"),
        )
        .join(
            PublicationAuthorization,
            and_(
                PublicationAuthorization.contact_id == PublicContact.id,
                PublicationAuthorization.actor_id == PublicContact.actor_id,
                PublicationAuthorization.revoked_at.is_(None),
                PublicationAuthorization.contact_revision == PublicContact.revision,
                PublicationAuthorization.channel == PublicContact.channel,
                PublicationAuthorization.purpose == DisclosurePurpose.COMMERCIAL_DISCOVERY,
            ),
        )
        .where(
            PublicContact.status == ContactStatus.ACTIVE,
            PublicContact.visibility == ContactVisibility.PUBLIC,
        )
        .subquery("disclosed_contacts")
    )
    return (
        select(
            eligible.c.offer_id,
            disclosed.c.channel.label("channel"),
            disclosed.c.value.label("value"),
        )
        .select_from(eligible)
        .outerjoin(disclosed, disclosed.c.actor_id == eligible.c.owner_actor_id)
        .order_by(
            disclosed.c.channel.asc().nulls_last(),
            disclosed.c.value.asc(),
            disclosed.c.contact_id.asc(),
        )
    )


def _text(value: object) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise RuntimeError("A projecção pública recebeu texto vazio.")
    return value


def _decimal_text(value: object) -> str:
    if not isinstance(value, Decimal):
        raise RuntimeError("A projecção pública recebeu um preço ou quantidade inválidos.")
    return format(value, "f")


def _code(value: object) -> str:
    code = getattr(value, "value", value)
    if not isinstance(code, str) or code == "":
        raise RuntimeError("A projecção pública recebeu um código vazio.")
    return code


def _present(row: Row[object]) -> PublicOfferData:
    mapping = row._mapping
    return PublicOfferData(
        id=mapping["id"],
        price=_decimal_text(mapping["price"]),
        currency=_text(mapping["currency"]),
        quantity=_decimal_text(mapping["quantity"]),
        unit=_text(mapping["unit"]),
        availability=_code(mapping["availability"]),
        delivery_terms=mapping["delivery_terms"],
        product_name=_text(mapping["product_name"]),
        product_description=_text(mapping["product_description"]),
        product_category=_text(mapping["product_category"]),
        producer_name=_text(mapping["producer_name"]),
        producer_kind=_code(mapping["producer_kind"]),
        producer_location=mapping["producer_location"],
    )
