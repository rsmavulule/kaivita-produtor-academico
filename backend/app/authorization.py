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


def accessible_actors(session: Session, user: User) -> list[tuple[Actor, AccessLevel]]:
    """Actores com representação ``active`` deste utilizador, e o nível dessa linha.

    A consulta não lê acessos de outras contas. Cada par utilizador/actor
    aparece uma só vez.
    """

    statement = (
        select(Actor, UserActorAccess.access_level)
        .join(UserActorAccess, UserActorAccess.actor_id == Actor.id)
        .where(
            UserActorAccess.user_id == user.id,
            UserActorAccess.status == AccessStatus.ACTIVE,
        )
        .order_by(Actor.display_name, Actor.id)
    )
    return [(actor, level) for actor, level in session.execute(statement)]


def represented_actor(
    session: Session, user: User, actor_id: uuid.UUID
) -> tuple[Actor, AccessLevel]:
    """O actor e o nível activo desta conta. A mesma leitura autoriza a consulta."""

    access = session.get(UserActorAccess, (user.id, actor_id))
    if access is None or access.status is not AccessStatus.ACTIVE:
        raise ActorUnavailable
    if access.access_level not in (AccessLevel.READ, AccessLevel.MANAGE):
        raise ActorUnavailable
    actor = session.get(Actor, actor_id)
    if actor is None:
        raise ActorUnavailable
    return actor, access.access_level


def actor_for_read(session: Session, user: User, actor_id: uuid.UUID) -> Actor:
    actor, _level = represented_actor(session, user, actor_id)
    return actor


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
