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
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
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
) -> Product:
    """Grava o produto do actor autorizado.

    O savepoint desfaz a linha se a escrita falhar. Quem confirma o
    pedido é a sessão de ``get_session``, uma única vez, no fim.
    """

    require_producer_role(session, actor)
    product = Product(
        owner_actor_id=actor.id,
        name=name,
        description=description,
        category=category,
        image_ref=image_ref,
        status=ProductStatus.ACTIVE,
    )
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
    fields: dict[str, str | None],
) -> Product:
    """Altera só os campos presentes. O estado e o dono ficam quietos."""

    require_producer_role(session, actor)
    with session.begin_nested():
        apply_product_changes(session, product, fields)
    return product


def apply_product_changes(
    session: Session,
    product: Product,
    fields: dict[str, str | None],
) -> None:
    for name in ("name", "description", "category", "image_ref"):
        if name in fields:
            setattr(product, name, fields[name])
    session.flush()


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
