"""Ligação à base de dados.

Importar este módulo não abre uma conexão. O SQLAlchemy só contacta
o PostgreSQL quando alguém pede uma ligação, por exemplo em /health
ou numa migração.
"""

import logging
from collections.abc import Iterator

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session

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


def get_session() -> Iterator[Session]:
    """Abre uma sessão síncrona e fecha-a no fim do pedido."""

    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


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
