"""Concessão, revogação e histórico privado das autorizações de divulgação.

O actor e o contacto vêm do caminho. O operador é o utilizador
autenticado. O corpo da concessão não aceita canal, valor, actor,
contacto nem identificadores de operadores.

Os identificadores dos operadores ficam na resposta privada para
rastrear quem concedeu ou revogou. Não trazem email, nome nem outros
dados da conta. A consulta pública não os inclui.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.authorization import ActorUnavailable, actor_for_manage, actor_for_read
from app.contact_catalog import ACTOR_NOT_FOUND, CONTACT_NOT_FOUND
from app.contacts import ContactChannel, ContactUnavailable, contact_for_actor
from app.db import get_session
from app.identity import User
from app.publication import (
    CONFIRMATION_REQUIRED,
    NOTICE_UNSUPPORTED,
    NOTICE_VERSION,
    PURPOSE_UNSUPPORTED,
    DisclosurePurpose,
    PublicationAuthorization,
    RevocationReason,
    AuthorizationConflict,
    AuthorizationRejected,
    AuthorizationUnavailable,
    authorizations_of,
    grant_authorization,
    revoke_authorization,
)

router = APIRouter(prefix="/actors/{actor_id}/contacts", tags=["autorizações de divulgação"])

AUTHORIZATION_NOT_FOUND = "Autorização não encontrada."


class AuthorizationResponse(BaseModel):
    """Projecção privada. O valor do contacto não é repetido."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    contact_id: UUID
    contact_revision: int
    channel: ContactChannel
    purpose: DisclosurePurpose
    notice_version: str
    status: str
    granted_at: str
    granted_by_user_id: UUID = Field(
        description=(
            "Identificador do operador que concedeu a autorização. "
            "Serve o rastreio privado e não inclui outros dados da conta."
        )
    )
    revoked_at: str | None
    revoked_by_user_id: UUID | None = Field(
        description=(
            "Identificador do operador que revogou a autorização. "
            "Nulo enquanto ela estiver vigente."
        )
    )
    revocation_reason: RevocationReason | None


class AuthorizationListResponse(BaseModel):
    items: list[AuthorizationResponse]

    model_config = ConfigDict(extra="forbid")


class GrantRequest(BaseModel):
    """Confirmação explícita da revisão, da finalidade e do aviso."""

    model_config = ConfigDict(extra="forbid")

    contact_revision: StrictInt
    purpose: DisclosurePurpose
    notice_version: str
    confirmed: StrictBool

    @model_validator(mode="before")
    @classmethod
    def nulls_are_rejected(cls, data: object) -> object:
        if isinstance(data, dict):
            for field in ("contact_revision", "purpose", "notice_version", "confirmed"):
                if field in data and data[field] is None:
                    raise ValueError("O campo não pode ser nulo.")
        return data

    @model_validator(mode="after")
    def confirmation_is_explicit(self) -> "GrantRequest":
        if self.confirmed is not True:
            raise ValueError(CONFIRMATION_REQUIRED)
        if self.purpose is not DisclosurePurpose.COMMERCIAL_DISCOVERY:
            raise ValueError(PURPOSE_UNSUPPORTED)
        if self.notice_version != NOTICE_VERSION:
            raise ValueError(NOTICE_UNSUPPORTED)
        return self


def _missing_actor() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ACTOR_NOT_FOUND)


def _missing_contact() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=CONTACT_NOT_FOUND)


def _missing_authorization() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=AUTHORIZATION_NOT_FOUND,
    )


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _present(authorization: PublicationAuthorization) -> AuthorizationResponse:
    return AuthorizationResponse(
        id=authorization.id,
        contact_id=authorization.contact_id,
        contact_revision=authorization.contact_revision,
        channel=authorization.channel,
        purpose=authorization.purpose,
        notice_version=authorization.notice_version,
        status="granted" if authorization.revoked_at is None else "revoked",
        granted_at=authorization.granted_at.isoformat(),
        granted_by_user_id=authorization.granted_by_user_id,
        revoked_at=(
            None
            if authorization.revoked_at is None
            else authorization.revoked_at.isoformat()
        ),
        revoked_by_user_id=authorization.revoked_by_user_id,
        revocation_reason=authorization.revocation_reason,
    )


@router.get(
    "/{contact_id}/authorizations",
    response_model=AuthorizationListResponse,
    summary="Consultar o histórico de autorizações de um contacto",
)
def list_authorizations(
    actor_id: UUID,
    contact_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> AuthorizationListResponse:
    try:
        actor = actor_for_read(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    try:
        contact = contact_for_actor(session, actor, contact_id)
    except ContactUnavailable:
        raise _missing_contact() from None
    return AuthorizationListResponse(
        items=[_present(item) for item in authorizations_of(session, contact)]
    )


@router.post(
    "/{contact_id}/authorizations",
    response_model=AuthorizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Conceder autorização de divulgação",
    description=(
        "Cria uma autorização nova quando o representante manage confirma "
        "a revisão actual, a finalidade commercial_discovery e o aviso v1. "
        "Repetir a mesma concessão devolve a linha existente, sem mudar "
        "o operador nem o instante originais."
    ),
)
def grant_contact_authorization(
    actor_id: UUID,
    contact_id: UUID,
    body: GrantRequest,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> AuthorizationResponse:
    try:
        actor = actor_for_manage(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    try:
        outcome = grant_authorization(
            session,
            actor,
            contact_id,
            user.id,
            body.contact_revision,
            body.purpose.value,
            body.notice_version,
            body.confirmed,
        )
    except ContactUnavailable:
        raise _missing_contact() from None
    except AuthorizationConflict as exc:
        raise _conflict(exc.detail) from None
    except AuthorizationRejected as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.detail,
        ) from None
    if not outcome.created:
        response.status_code = status.HTTP_200_OK
    return _present(outcome.authorization)


@router.post(
    "/{contact_id}/authorizations/{authorization_id}/revoke",
    response_model=AuthorizationResponse,
    summary="Revogar uma autorização de divulgação",
)
def revoke_contact_authorization(
    actor_id: UUID,
    contact_id: UUID,
    authorization_id: UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> AuthorizationResponse:
    try:
        actor = actor_for_manage(session, user, actor_id)
    except ActorUnavailable:
        raise _missing_actor() from None
    try:
        authorization = revoke_authorization(
            session,
            actor,
            contact_id,
            authorization_id,
            user.id,
        )
    except ContactUnavailable:
        raise _missing_contact() from None
    except AuthorizationUnavailable:
        raise _missing_authorization() from None
    return _present(authorization)
