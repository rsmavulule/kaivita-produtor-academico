"""Consulta e alteração do actor representado.

Não cria actores, não concede acessos e não gere papéis comerciais.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.authorization import (
    ActorUnavailable,
    accessible_actors,
    actor_for_manage,
    actor_for_read,
)
from app.db import get_session
from app.identity import Actor, ActorKind, ActorStatus, User

router = APIRouter(prefix="/actors", tags=["actores"])

NOT_FOUND = "Actor não encontrado."


class ActorResponse(BaseModel):
    id: UUID
    kind: ActorKind
    display_name: str
    general_location: str | None
    status: ActorStatus

    model_config = ConfigDict(from_attributes=True)


class ActorUpdate(BaseModel):
    """Só o nome e a localização geral. Os outros campos ficam de fora."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    general_location: str | None = None

    @field_validator("display_name")
    @classmethod
    def name_is_present(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            raise ValueError("Nome inválido.")
        return value

    @field_validator("general_location")
    @classmethod
    def location_is_present_or_unknown(cls, value: str | None) -> str | None:
        if value is not None and value.strip() == "":
            raise ValueError("Localização inválida.")
        return value


def _missing_actor() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)


def _present(actor: Actor) -> ActorResponse:
    return ActorResponse.model_validate(actor)


@router.get("", response_model=list[ActorResponse])
def list_actors(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[ActorResponse]:
    return [_present(actor) for actor in accessible_actors(session, user)]


@router.get("/{actor_id}", response_model=ActorResponse)
def read_actor(
    actor_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ActorResponse:
    try:
        actor = actor_for_read(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    return _present(actor)


@router.patch("/{actor_id}", response_model=ActorResponse)
def update_actor(
    actor_id: UUID,
    body: ActorUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ActorResponse:
    # A conta autenticada, a autorização e esta escrita partilham a sessão
    # de get_session. O commit no fim do pedido confirma as três ou desfaz
    # as três. Não há bloqueio da linha: com READ COMMITTED, uma revogação
    # confirmada por outro pedido depois desta leitura pode chegar tarde.
    try:
        actor = actor_for_manage(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None

    if "display_name" in body.model_fields_set:
        actor.display_name = body.display_name
    if "general_location" in body.model_fields_set:
        actor.general_location = body.general_location
    session.flush()
    return _present(actor)
