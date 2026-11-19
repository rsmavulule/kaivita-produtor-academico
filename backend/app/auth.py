"""Endpoints de autenticação. Não autorizam representação de actores."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.accounts import authenticate, email_is_valid, normalize_email
from app.config import settings
from app.db import get_session
from app.identity import User, UserStatus
from app.passwords import password_is_valid
from app.tokens import InvalidToken, decode_access_token, issue_access_token

router = APIRouter(prefix="/auth", tags=["autenticacao"])

BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def email_has_the_stored_shape(cls, value: str) -> str:
        normalized = normalize_email(value)
        if not email_is_valid(normalized):
            raise ValueError("Email inválido.")
        return normalized

    @field_validator("password")
    @classmethod
    def password_has_an_accepted_length(cls, value: str) -> str:
        if not password_is_valid(value):
            raise ValueError("Palavra-passe inválida.")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    expires_in: int


class MeResponse(BaseModel):
    id: UUID
    email: str
    status: UserStatus


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=BEARER_CHALLENGE,
    )


def _bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise InvalidToken
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or token == "" or " " in token:
        raise InvalidToken
    return token


def get_current_user(
    session: Session = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> User:
    try:
        user_id = decode_access_token(_bearer_token(authorization))
    except InvalidToken:
        raise _unauthorized("Token inválido.") from None

    user = session.get(User, user_id)
    if user is None or user.status is not UserStatus.ACTIVE:
        raise _unauthorized("Token inválido.")
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    user = authenticate(session, body.email, body.password)
    if user is None:
        raise _unauthorized("Credenciais inválidas.")
    return TokenResponse(
        access_token=issue_access_token(user.id),
        token_type="bearer",
        expires_in=settings.jwt_expires_in,
    )


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(id=user.id, email=user.email, status=user.status)
