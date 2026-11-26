"""Catálogo de produtos de um actor (incremento I3).

A SRS v1.1 §3 e o diagrama de classes fixam os atributos. Não fixam os
literais de ``ProductStatus``. ``active`` e ``archived`` são a decisão
deste incremento, repetida no CHECK da migração ``0003_products``.

Um actor tem zero ou mais produtos. Cada produto tem um único
``owner_actor_id``. Esse identificador vem do actor já autorizado no
caminho; o corpo do pedido não o escolhe.

O papel ``producer`` tem de estar entre os papéis do actor em cada
escrita. Pode coexistir com ``buyer`` e ``partner``. Não autoriza a
representação: quem não tem ``read`` ou ``manage`` activo continua de
fora. Não há preço, quantidade, entrega, oferta, tabela de categorias
nem ficheiro. Arquivar muda o estado e conserva a linha.

A migração ``0004_offers`` acrescenta ``uq_products_id_owner`` para a
chave estrangeira composta da oferta. ``0003_products`` não é editada.
"""

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from urllib.parse import urlsplit

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    select,
    text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base
from app.identity import Actor, ActorRole, Role, RoleCode, closed_text


class ProductStatus(StrEnum):
    """Estado do produto no catálogo do actor.

    Não é o estado de uma oferta nem o estado da identidade do actor.

    active: o produto está no catálogo.
    archived: foi arquivado; o registo e os restantes campos mantêm-se.
    """

    ACTIVE = "active"
    ARCHIVED = "archived"


class ProductUnavailable(Exception):
    """O produto não existe neste actor."""


class ProducerRoleMissing(Exception):
    """O actor autorizado não tem o papel comercial producer."""


class ImageDeclarationError(Exception):
    """A declaração de direitos não corresponde à fotografia indicada."""


IMAGE_REF_LIMIT = 2048
IMAGE_REF_INVALID = "Referência de imagem inválida."
IMAGE_DECLARATION_REQUIRED = "A declaração de direitos exige uma fotografia."


def _values(enum_cls: type[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in enum_cls)


class Product(Base):
    """Produto pertencente a um actor. A oferta comercial não está aqui."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(name)) > 0",
            name="ck_products_name",
        ),
        CheckConstraint(
            "char_length(btrim(description)) > 0",
            name="ck_products_description",
        ),
        CheckConstraint(
            "char_length(btrim(category)) > 0",
            name="ck_products_category",
        ),
        CheckConstraint(
            "image_ref IS NULL OR char_length(btrim(image_ref)) > 0",
            name="ck_products_image_ref",
        ),
        CheckConstraint(
            "("
            "image_rights_declared_at IS NULL "
            "AND image_rights_declared_by IS NULL "
            "AND image_rights_ref IS NULL"
            ") OR ("
            "image_rights_declared_at IS NOT NULL "
            "AND image_rights_declared_by IS NOT NULL "
            "AND image_rights_ref IS NOT NULL "
            "AND image_ref IS NOT NULL "
            "AND image_ref = image_rights_ref"
            ")",
            name="ck_products_image_rights",
        ),
        CheckConstraint(
            f"status IN ({_values(ProductStatus)})",
            name="ck_products_status",
        ),
        UniqueConstraint(
            "id",
            "owner_actor_id",
            name="uq_products_id_owner",
        ),
        Index("ix_products_owner_actor_id", "owner_actor_id"),
        {
            "comment": (
                "Produto de um actor. Não inclui preço, quantidade nem entrega. "
                "Arquivar muda o estado e mantém a linha."
            )
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    owner_actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "actors.id",
            name="fk_products_owner_actor_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        comment="Actor proprietário. Não é aceite no corpo do pedido.",
    )
    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Nome do produto.",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Descrição do produto.",
    )
    category: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Categoria em texto livre. Não é uma tabela de categorias.",
    )
    image_ref: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Referência opcional da fotografia. Não é um ficheiro guardado.",
    )
    status: Mapped[ProductStatus] = closed_text(
        ProductStatus,
        "active: no catálogo; archived: arquivado, sem apagar o registo.",
    )
    image_rights_ref: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Fotografia exacta a que a declaração de direitos se refere.",
    )
    image_rights_declared_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Instante da afirmação do representante. Não é uma verificação jurídica.",
    )
    image_rights_declared_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_products_image_rights_declared_by",
            ondelete="RESTRICT",
        ),
        nullable=True,
        comment="Conta que afirmou os direitos. Não é mostrado na consulta pública.",
    )

    @property
    def image_use_confirmed(self) -> bool:
        """A declaração vigente refere-se à fotografia actualmente gravada."""

        return (
            self.image_ref is not None
            and self.image_rights_ref == self.image_ref
            and self.image_rights_declared_at is not None
            and self.image_rights_declared_by is not None
        )


def is_public_image_ref(value: str) -> bool:
    """URL HTTPS absoluto, sem credenciais. Não contacta o endereço."""

    if len(value) > IMAGE_REF_LIMIT or "\\" in value:
        return False
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value):
        return False
    parts = urlsplit(value)
    if parts.scheme != "https":
        return False
    if parts.username is not None or parts.password is not None:
        return False
    host = parts.hostname
    return host is not None and host.strip(".") != ""


def normalize_image_ref(value: str | None) -> str | None:
    """Aceita ausência ou um URL HTTPS. Rejeita o resto sem o repetir."""

    if value is None:
        return None
    text = value.strip()
    if text == "" or not is_public_image_ref(text):
        raise ValueError(IMAGE_REF_INVALID)
    return text


def public_image_ref(
    image_ref: str | None,
    rights_ref: str | None,
    declared_at: datetime | None,
) -> str | None:
    """A fotografia pública exige a referência válida e a declaração dessa referência."""

    if image_ref is None or declared_at is None or rights_ref != image_ref:
        return None
    if not is_public_image_ref(image_ref):
        return None
    return image_ref


def has_producer_role(session: Session, actor: Actor) -> bool:
    """O papel producer pode estar acompanhado de outros papéis."""

    found = session.scalar(
        select(Role.id)
        .join(ActorRole, ActorRole.role_id == Role.id)
        .where(
            ActorRole.actor_id == actor.id,
            Role.code == RoleCode.PRODUCER,
        )
    )
    return found is not None


def require_producer_role(session: Session, actor: Actor) -> None:
    if not has_producer_role(session, actor):
        raise ProducerRoleMissing


def products_of(session: Session, actor: Actor) -> list[Product]:
    """Produtos deste actor, incluindo arquivados, por nome e id."""

    statement = (
        select(Product)
        .where(Product.owner_actor_id == actor.id)
        .order_by(Product.name, Product.id)
    )
    return list(session.scalars(statement))


def product_for_actor(
    session: Session,
    actor: Actor,
    product_id: uuid.UUID,
) -> Product:
    """Só devolve o produto quando o dono é o actor do caminho."""

    product = session.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.owner_actor_id == actor.id,
        )
    )
    if product is None:
        raise ProductUnavailable
    return product


def create_product(
    session: Session,
    actor: Actor,
    name: str,
    description: str,
    category: str,
    image_ref: str | None,
    image_use_confirmed: bool = False,
    declared_by: uuid.UUID | None = None,
) -> Product:
    """Grava o produto do actor autorizado.

    O savepoint desfaz a linha se a escrita falhar. Quem confirma o
    pedido é a sessão de ``get_session``, uma única vez, no fim.
    A declaração, quando vem no mesmo pedido, fica ligada à fotografia.
    """

    require_producer_role(session, actor)
    product = Product(
        owner_actor_id=actor.id,
        name=name,
        description=description,
        category=category,
        image_ref=normalize_image_ref(image_ref),
        status=ProductStatus.ACTIVE,
    )
    if image_use_confirmed:
        _grant_image_rights(product, declared_by)
    with session.begin_nested():
        session.add(product)
        remember_new_product(session, product)
    return product


def remember_new_product(session: Session, product: Product) -> None:
    session.flush()


def update_product(
    session: Session,
    actor: Actor,
    product: Product,
    fields: dict[str, object],
) -> Product:
    """Altera só os campos presentes. O estado e o dono ficam quietos."""

    require_producer_role(session, actor)
    with session.begin_nested():
        apply_product_changes(session, product, fields)
    return product


def apply_product_changes(
    session: Session,
    product: Product,
    fields: dict[str, object],
) -> None:
    for name in ("name", "description", "category"):
        if name in fields:
            setattr(product, name, fields[name])
    if "image_ref" in fields or "image_use_confirmed" in fields:
        _apply_image(product, fields)
    session.flush()


def _apply_image(product: Product, fields: dict[str, object]) -> None:
    """Uma fotografia nova ou retirada invalida a declaração anterior.

    Confirmar no mesmo pedido vale como a nova declaração dessa fotografia.
    Repetir a confirmação da mesma referência conserva a evidência já gravada.
    """

    ref_set = "image_ref" in fields
    confirmed = bool(fields.get("image_use_confirmed"))
    raw_ref = fields["image_ref"] if ref_set else None
    if ref_set and raw_ref is not None and not isinstance(raw_ref, str):
        raise ImageDeclarationError(IMAGE_REF_INVALID)
    target = normalize_image_ref(raw_ref if isinstance(raw_ref, str) else None) if ref_set else product.image_ref
    if ref_set and target != product.image_ref:
        _clear_image_rights(product)
        product.image_ref = target
    if target is None:
        if confirmed:
            raise ImageDeclarationError(IMAGE_DECLARATION_REQUIRED)
        _clear_image_rights(product)
        return
    if "image_use_confirmed" in fields and not confirmed:
        _clear_image_rights(product)
        return
    if confirmed:
        _grant_image_rights(product, fields.get("declared_by"))


def _grant_image_rights(product: Product, declared_by: uuid.UUID | None) -> None:
    if product.image_ref is None:
        raise ImageDeclarationError(IMAGE_DECLARATION_REQUIRED)
    if not is_public_image_ref(product.image_ref):
        raise ImageDeclarationError(IMAGE_REF_INVALID)
    if not isinstance(declared_by, uuid.UUID):
        raise ImageDeclarationError(IMAGE_DECLARATION_REQUIRED)
    if product.image_use_confirmed:
        return
    product.image_rights_ref = product.image_ref
    product.image_rights_declared_at = datetime.now(timezone.utc)
    product.image_rights_declared_by = declared_by


def _clear_image_rights(product: Product) -> None:
    product.image_rights_ref = None
    product.image_rights_declared_at = None
    product.image_rights_declared_by = None


def archive_product(session: Session, actor: Actor, product: Product) -> Product:
    """Arquiva sem apagar. Repetir a operação não mexe nos outros campos."""

    require_producer_role(session, actor)
    if product.status is ProductStatus.ARCHIVED:
        return product
    with session.begin_nested():
        mark_archived(session, product)
    return product


def mark_archived(session: Session, product: Product) -> None:
    product.status = ProductStatus.ARCHIVED
    session.flush()
