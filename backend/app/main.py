"""Aplicação FastAPI.

Expõe o estado do serviço, a autenticação, a representação de actores,
a criação do actor, o catálogo de papéis comerciais, o catálogo de
produtos, a gestão privada de ofertas, a gestão privada de contactos
comerciais, a autorização de divulgação e a descoberta pública de
ofertas e dos contactos autorizados.
A documentação está em /docs. Não há registo público. Publicar uma
oferta não divulga contactos.
"""

from typing import Literal

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.actors import router as actors_router
from app.auth import router as auth_router
from app.catalog import router as catalog_router
from app.contact_catalog import PrivateContactNoStore
from app.contact_catalog import router as contact_router
from app.offer_catalog import router as offer_router
from app.config import settings
from app.db import CommitBeforeResponse, check_database
from app.public_catalog import PublicNoStore
from app.public_catalog import router as public_offer_router
from app.publication_catalog import router as publication_router
from app.roles import router as roles_router

app = FastAPI(title=settings.app_name)
app.add_middleware(CommitBeforeResponse)
app.add_middleware(PublicNoStore)
app.add_middleware(PrivateContactNoStore)
app.include_router(auth_router)
app.include_router(actors_router)
app.include_router(catalog_router)
app.include_router(offer_router)
app.include_router(contact_router)
app.include_router(publication_router)
app.include_router(public_offer_router)
app.include_router(roles_router)


@app.exception_handler(RequestValidationError)
def hide_rejected_input(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Responde 422 sem devolver o corpo rejeitado.

    O corpo pode conter a palavra-passe. O erro indica o campo e o tipo,
    não o valor enviado.
    """

    details = [
        {
            "loc": list(error.get("loc", [])),
            "msg": str(error.get("msg", "Entrada inválida.")),
            "type": str(error.get("type", "value_error")),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": details},
    )


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
