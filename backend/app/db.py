"""Ligação à base de dados.

Importar este módulo não abre uma conexão. O SQLAlchemy só contacta
o PostgreSQL quando alguém pede uma ligação, por exemplo em /health
ou numa migração.
"""

import logging
from collections.abc import Iterator

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 3},
)


class Base(DeclarativeBase):
    """Base dos mapeamentos. As tabelas entram ao importar o módulo do modelo."""

    metadata = MetaData(
        naming_convention={"pk": "pk_%(table_name)s"},
    )


SESSION_SCOPE_KEY = "kaivita_session"


def get_session(request: Request) -> Iterator[Session]:
    """Abre uma sessão síncrona e fecha-a no fim do pedido.

    A sessão fica no scope para o commit poder ocorrer antes de o
    cliente receber a linha de estado. O commit deste gerador continua
    a ser a rede de segurança quando essa confirmação ainda não correu.
    """

    session = Session(engine)
    request.scope[SESSION_SCOPE_KEY] = session
    try:
        yield session
        if session.in_transaction():
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        request.scope.pop(SESSION_SCOPE_KEY, None)
        session.close()


class CommitBeforeResponse:
    """Confirma a transacção antes de enviar a resposta HTTP.

    O gerador de get_session só retoma depois de a resposta ter sido
    enviada. O servidor da interface pede logo a seguir o recurso acabado
    de criar. Sem este passo, esse pedido pode observar 404.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def send_committed(message: Message) -> None:
            if message["type"] == "http.response.start":
                session = scope.get(SESSION_SCOPE_KEY)
                if session is not None and session.in_transaction():
                    session.commit()
            await send(message)

        await self.app(scope, receive, send_committed)


def check_database() -> bool:
    """Devolve True se o PostgreSQL responder a SELECT 1."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        # A mensagem pode incluir a URL com a palavra-passe. Registamos só o tipo.
        logger.warning("Ligação à base de dados indisponível: %s", type(exc).__name__)
        return False
