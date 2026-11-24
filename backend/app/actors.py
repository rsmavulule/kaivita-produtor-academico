"""Actores representados e os seus papéis comerciais.

GET e PATCH verificam a representação, como no I1.3.
POST cria o actor, os papéis e o acesso ``manage`` do utilizador
autenticado. O pedido não escolhe o utilizador, o identificador,
o nível nem o estado dessa autorização.

A consulta e a substituição dos papéis usam o mesmo 404 do I1.3
quando o actor não existe ou a conta não o pode usar.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

from app.actor_roles import (
    create_represented_actor,
    parse_role_codes,
    replace_actor_roles,
    roles_of,
)
from app.auth import get_current_user
from app.authorization import (
    ActorUnavailable,
    accessible_actors,
    actor_for_manage,
    actor_for_read,
    represented_actor,
)
from app.db import get_session
from app.identity import (
    AccessLevel,
    Actor,
    ActorKind,
    ActorStatus,
    RoleCode,
    User,
)
from app.roles import RoleResponse

router = APIRouter(prefix="/actors", tags=["actores"])

NOT_FOUND = "Actor não encontrado."


class ActorResponse(BaseModel):
    id: UUID
    kind: ActorKind
    display_name: str
    general_location: str | None
    status: ActorStatus

    model_config = ConfigDict(from_attributes=True)


class ActorView(BaseModel):
    """Consulta do actor com o nível desta conta. Não serve para criar nem editar."""

    id: UUID
    kind: ActorKind
    display_name: str
    general_location: str | None
    status: ActorStatus
    representation: AccessLevel


class ActorCreate(BaseModel):
    """Identidade e papéis. A representação inicial não vem no corpo."""

    model_config = ConfigDict(extra="forbid")

    kind: ActorKind
    display_name: str
    general_location: str | None = None
    roles: list[RoleCode]

    @field_validator("display_name")
    @classmethod
    def name_is_present(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("Nome inválido.")
        return value

    @field_validator("general_location")
    @classmethod
    def location_is_present_or_unknown(cls, value: str | None) -> str | None:
        if value is not None and value.strip() == "":
            raise ValueError("Localização inválida.")
        return value

    @field_validator("roles", mode="before")
    @classmethod
    def roles_follow_the_catalog(cls, value: object) -> list[RoleCode]:
        return parse_role_codes(value)


class RoleUpdate(BaseModel):
    """Conjunto completo de papéis pretendidos."""

    model_config = ConfigDict(extra="forbid")

    roles: list[RoleCode]

    @field_validator("roles", mode="before")
    @classmethod
    def roles_follow_the_catalog(cls, value: object) -> list[RoleCode]:
        return parse_role_codes(value)


class ActorCreatedResponse(BaseModel):
    id: UUID
    kind: ActorKind
    display_name: str
    general_location: str | None
    status: ActorStatus
    roles: list[RoleResponse]


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


def _view(actor: Actor, representation: AccessLevel) -> ActorView:
    return ActorView(
        id=actor.id,
        kind=actor.kind,
        display_name=actor.display_name,
        general_location=actor.general_location,
        status=actor.status,
        representation=representation,
    )


def _roles(roles) -> list[RoleResponse]:
    return [RoleResponse.model_validate(role) for role in roles]


def _reject_roles(exc: ValueError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(exc),
    )


@router.post(
    "",
    response_model=ActorCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_actor(
    body: ActorCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ActorCreatedResponse:
    # O modelo já recusou a lista. A função volta a verificá-la e lê
    # o catálogo antes de abrir o savepoint. user.id vem do token.
    try:
        actor, roles = create_represented_actor(
            session,
            user,
            body.kind,
            body.display_name,
            body.general_location,
            body.roles,
        )
    except ValueError as exc:
        raise _reject_roles(exc) from None
    return ActorCreatedResponse(
        id=actor.id,
        kind=actor.kind,
        display_name=actor.display_name,
        general_location=actor.general_location,
        status=actor.status,
        roles=_roles(roles),
    )


@router.get("", response_model=list[ActorView])
def list_actors(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[ActorView]:
    return [_view(actor, level) for actor, level in accessible_actors(session, user)]


@router.get("/{actor_id}", response_model=ActorView)
def read_actor(
    actor_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ActorView:
    try:
        actor, level = represented_actor(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    return _view(actor, level)


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


@router.get("/{actor_id}/roles", response_model=list[RoleResponse])
def read_actor_roles(
    actor_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[RoleResponse]:
    try:
        actor = actor_for_read(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    return _roles(roles_of(session, actor))


@router.put("/{actor_id}/roles", response_model=list[RoleResponse])
def update_actor_roles(
    actor_id: UUID,
    body: RoleUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[RoleResponse]:
    # A mesma sessão lê a autorização e substitui actor_roles.
    # Não há bloqueio da linha, como no PATCH do I1.3.
    try:
        actor = actor_for_manage(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    try:
        roles = replace_actor_roles(session, actor, body.roles)
    except ValueError as exc:
        raise _reject_roles(exc) from None
    return _roles(roles)
