"""Catálogo comercial fechado.

Devolve as três linhas semeadas no I1.1. Não cria papéis e não lê actores.
Não exige autenticação: a resposta só tem o identificador e o código,
sem dados de contas nem de representação.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.actor_roles import catalog
from app.db import get_session
from app.identity import RoleCode

router = APIRouter(prefix="/roles", tags=["papeis"])


class RoleResponse(BaseModel):
    id: UUID
    code: RoleCode

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[RoleResponse])
def list_roles(session: Session = Depends(get_session)) -> list[RoleResponse]:
    return [RoleResponse.model_validate(role) for role in catalog(session)]
