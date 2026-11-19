"""Autorização de representação. O JWT não traz estas permissões.

Cada consulta lê ``user_actor_access`` na base. ``read`` e ``manage``
activos permitem ver o actor. Só ``manage`` activo permite alterá-lo.
Associação em falta, revogada ou de nível insuficiente recusam da
mesma forma: o chamador não fica a saber se o actor existe.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity import (
    AccessLevel,
    AccessStatus,
    Actor,
    User,
    UserActorAccess,
)


class ActorUnavailable(Exception):
    """O actor não existe ou esta conta não o pode usar nesta operação."""


def accessible_actors(session: Session, user: User) -> list[Actor]:
    """Actores com representação ``active``, seja ``read`` ou ``manage``."""

    statement = (
        select(Actor)
        .join(UserActorAccess, UserActorAccess.actor_id == Actor.id)
        .where(
            UserActorAccess.user_id == user.id,
            UserActorAccess.status == AccessStatus.ACTIVE,
        )
        .order_by(Actor.display_name, Actor.id)
    )
    return list(session.scalars(statement))


def actor_for_read(session: Session, user: User, actor_id: uuid.UUID) -> Actor:
    return _actor_for(session, user, actor_id, manage=False)


def actor_for_manage(session: Session, user: User, actor_id: uuid.UUID) -> Actor:
    return _actor_for(session, user, actor_id, manage=True)


def _actor_for(
    session: Session,
    user: User,
    actor_id: uuid.UUID,
    *,
    manage: bool,
) -> Actor:
    access = session.get(UserActorAccess, (user.id, actor_id))
    if access is None or access.status is not AccessStatus.ACTIVE:
        raise ActorUnavailable
    if manage and access.access_level is not AccessLevel.MANAGE:
        raise ActorUnavailable
    if access.access_level not in (AccessLevel.READ, AccessLevel.MANAGE):
        raise ActorUnavailable

    actor = session.get(Actor, actor_id)
    if actor is None:
        raise ActorUnavailable
    return actor
