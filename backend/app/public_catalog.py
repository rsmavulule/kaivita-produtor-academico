"""Rotas públicas de descoberta de ofertas.

Não usam ``get_current_user`` nem ``UserActorAccess``. Um cabeçalho
``Authorization`` não alarga o schema. O contrato privado permanece
em ``offer_catalog``.

Os parâmetros desconhecidos e os escalares repetidos são recusados
aqui. O FastAPI, por omissão, ignora os primeiros e fica com o último
valor dos segundos. Os erros de tipo, gama e tamanho continuam a ser
os do FastAPI e passam pelo tratamento que omite ``input``.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field
from pydantic_core import core_schema
from sqlalchemy.orm import Session
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.contacts import ContactChannel
from app.db import get_session
from app.identity import ActorKind
from app.offers import AvailabilityStatus
from app.public_offers import (
    PublicContactData,
    PublicOfferData,
    PublicSearch,
    normalize_search_text,
    public_offer,
    public_offer_contacts,
    public_offer_page,
)

router = APIRouter(prefix="/public/offers", tags=["descoberta pública"])

NOT_FOUND = "Oferta não encontrada."
TEXT_LIMIT = 100
ALLOWED_QUERY = frozenset({"q", "category", "location", "limit", "offset"})


class OfferPath(str):
    """UUID do caminho. A mensagem de erro não inclui o texto recebido."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: object, handler: object):
        def parse(value: object) -> uuid.UUID:
            if not isinstance(value, str):
                raise ValueError("UUID inválido.")
            try:
                return uuid.UUID(value)
            except ValueError:
                raise ValueError("UUID inválido.") from None

        return core_schema.no_info_after_validator_function(
            parse,
            core_schema.str_schema(),
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, schema: object, handler: object):
        return {"type": "string", "format": "uuid"}


class PublicProduct(BaseModel):
    """Texto do produto visível na descoberta. Sem identificador nem fotografia."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    category: str


class PublicProducer(BaseModel):
    """Identificação comercial do produtor. Sem conta nem contactos."""

    model_config = ConfigDict(extra="forbid")

    display_name: str
    kind: ActorKind
    general_location: str | None


class PublicOffer(BaseModel):
    """Oferta elegível. O schema privado não é reutilizado."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    price: Annotated[str, Field(examples=["150.00"])]
    currency: str
    quantity: Annotated[str, Field(examples=["2.50"])]
    unit: str
    availability: AvailabilityStatus
    delivery_terms: str | None
    product: PublicProduct
    producer: PublicProducer


class PublicOfferPage(BaseModel):
    """Página limitada. ``total`` conta só o predicado e os filtros."""

    model_config = ConfigDict(extra="forbid")

    items: list[PublicOffer]
    limit: int
    offset: int
    total: int


class PublicDisclosedContact(BaseModel):
    """Contacto autorizado. Não transporta identificadores nem histórico."""

    model_config = ConfigDict(extra="forbid")

    channel: ContactChannel
    value: str


class PublicContactList(BaseModel):
    """Lista da oferta elegível. Vazia quando nada é divulgável."""

    model_config = ConfigDict(extra="forbid")

    items: list[PublicDisclosedContact]


class PublicNoStore:
    """Acrescenta ``Cache-Control: no-store`` às respostas de ``/public/``.

    Cobre o sucesso e os erros destas rotas, incluindo 404 e 422.
    As outras rotas não recebem este cabeçalho por aqui.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope.get("type") != "http" or not _public_path(path):
            await self.app(scope, receive, send)
            return

        async def send_no_store(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["cache-control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_no_store)


def _public_path(path: object) -> bool:
    return isinstance(path, str) and path.startswith("/public/")


def _query_error(name: str, message: str, error_type: str) -> dict[str, object]:
    return {"loc": ("query", name), "msg": message, "type": error_type}


def _reject_unexpected(request: Request, allowed: frozenset[str]) -> None:
    """Recusa nomes desconhecidos e a repetição de um escalar.

    O valor recebido não entra no erro. O nome fica em ``loc``, como
    nos restantes erros de parâmetro.
    """

    errors: list[dict[str, object]] = []
    seen: set[str] = set()
    for name, _value in request.query_params.multi_items():
        if name in seen:
            errors.append(_query_error(name, "Parâmetro repetido.", "value_error"))
            continue
        seen.add(name)
        if name not in allowed:
            errors.append(_query_error(name, "Parâmetro desconhecido.", "extra_forbidden"))
    if errors:
        raise RequestValidationError(errors)


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_search_text(value)
    if normalized == "":
        return None
    return normalized


def read_public_query(
    request: Request,
    q: Annotated[
        str | None,
        Query(
            max_length=TEXT_LIMIT,
            description=(
                "Texto parcial do nome ou da descrição do produto. "
                "Vazio depois da normalização equivale a filtro ausente."
            ),
        ),
    ] = None,
    category: Annotated[
        str | None,
        Query(
            max_length=TEXT_LIMIT,
            description="Texto parcial da categoria do produto.",
        ),
    ] = None,
    location: Annotated[
        str | None,
        Query(
            max_length=TEXT_LIMIT,
            description=(
                "Texto parcial da localização geral do actor. "
                "Localização vazia na base não satisfaz este filtro."
            ),
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=50, description="Número máximo de ofertas na página."),
    ] = 20,
    offset: Annotated[
        int,
        Query(
            ge=0,
            le=1000,
            description=(
                "Ofertas a saltar. O máximo é 1000: a paginação não é ilimitada."
            ),
        ),
    ] = 0,
) -> PublicSearch:
    _reject_unexpected(request, ALLOWED_QUERY)
    return PublicSearch(
        text=_optional_text(q),
        category=_optional_text(category),
        location=_optional_text(location),
        limit=limit,
        offset=offset,
    )


def reject_detail_query(request: Request) -> None:
    """A ficha não aceita query string."""

    _reject_unexpected(request, frozenset())


def _view(offer: PublicOfferData) -> PublicOffer:
    return PublicOffer(
        id=offer.id,
        price=offer.price,
        currency=offer.currency,
        quantity=offer.quantity,
        unit=offer.unit,
        availability=AvailabilityStatus(offer.availability),
        delivery_terms=offer.delivery_terms,
        product=PublicProduct(
            name=offer.product_name,
            description=offer.product_description,
            category=offer.product_category,
        ),
        producer=PublicProducer(
            display_name=offer.producer_name,
            kind=ActorKind(offer.producer_kind),
            general_location=offer.producer_location,
        ),
    )


def _missing() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)


@router.get(
    "",
    response_model=PublicOfferPage,
    summary="Listar ofertas públicas",
    description=(
        "Lista ofertas elegíveis, sem autenticação. A ordenação é o nome "
        "normalizado do produto e, em empate, o identificador da oferta. "
        "O total aplica o mesmo predicado e os mesmos filtros da página."
    ),
)
def list_public_offers(
    search: Annotated[PublicSearch, Depends(read_public_query)],
    session: Session = Depends(get_session),
) -> PublicOfferPage:
    items, total = public_offer_page(session, search)
    return PublicOfferPage(
        items=[_view(item) for item in items],
        limit=search.limit,
        offset=search.offset,
        total=total,
    )


@router.get(
    "/{offer_id}",
    response_model=PublicOffer,
    summary="Consultar uma oferta pública",
    description=(
        "Devolve a oferta quando o identificador é válido e a oferta é "
        "elegível. Identificador desconhecido e oferta inelegível respondem "
        "o mesmo 404."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Oferta inexistente ou inelegível.",
            "content": {
                "application/json": {
                    "example": {"detail": NOT_FOUND},
                }
            },
        }
    },
    dependencies=[Depends(reject_detail_query)],
)
def read_public_offer(
    offer_id: Annotated[
        OfferPath,
        Path(description="Identificador UUID da oferta."),
    ],
    session: Session = Depends(get_session),
) -> PublicOffer:
    parsed = offer_id if isinstance(offer_id, uuid.UUID) else uuid.UUID(str(offer_id))
    found = public_offer(session, parsed)
    if found is None:
        raise _missing()
    return _view(found)


def _disclosed(contact: PublicContactData) -> PublicDisclosedContact:
    return PublicDisclosedContact(
        channel=ContactChannel(contact.channel),
        value=contact.value,
    )


@router.get(
    "/{offer_id}/contacts",
    response_model=PublicContactList,
    summary="Consultar contactos autorizados de uma oferta",
    description=(
        "Devolve só o canal e o valor dos contactos com autorização vigente "
        "coerente com a revisão e o canal actuais. A oferta usa o mesmo "
        "predicado de elegibilidade da ficha. Oferta inexistente ou "
        "inelegível responde 404. Oferta elegível sem contactos divulgáveis "
        "responde uma lista vazia. Não exige autenticação."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Oferta inexistente ou inelegível.",
            "content": {
                "application/json": {
                    "example": {"detail": NOT_FOUND},
                }
            },
        }
    },
    dependencies=[Depends(reject_detail_query)],
)
def read_public_offer_contacts(
    offer_id: Annotated[
        OfferPath,
        Path(description="Identificador UUID da oferta."),
    ],
    session: Session = Depends(get_session),
) -> PublicContactList:
    parsed = offer_id if isinstance(offer_id, uuid.UUID) else uuid.UUID(str(offer_id))
    found = public_offer_contacts(session, parsed)
    if found is None:
        raise _missing()
    return PublicContactList(items=[_disclosed(item) for item in found])
