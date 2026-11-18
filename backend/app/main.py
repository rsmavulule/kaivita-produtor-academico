"""Aplicação FastAPI do incremento I0.

Expõe o estado do serviço e a documentação gerada pelo FastAPI em /docs.
Não há rotas de autenticação, produtores, produtos ou ofertas.
"""

from typing import Literal

from fastapi import FastAPI, Response, status
from pydantic import BaseModel

from app.config import settings
from app.db import check_database

app = FastAPI(title=settings.app_name)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["up", "down"]


@app.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
def health(response: Response) -> HealthResponse:
    database_ok = check_database()
    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        database="up" if database_ok else "down",
    )
