"""Comando local para criar uma conta de teste.

A palavra-passe não é um argumento: num terminal pede-se duas vezes;
num pipe lê-se uma linha de stdin. Não é impressa, nem o seu resumo.

Uso, a partir de ``backend``:

    python -m app.create_user --email pessoa@example.com
"""

import sys
from argparse import ArgumentParser
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from getpass import getpass

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.accounts import AccountExists, create_active_user
from app.db import engine


class CommandError(Exception):
    """Argumentos rejeitados, sem terminar o processo aqui."""


class CommandParser(ArgumentParser):
    def error(self, message: str) -> None:
        raise CommandError("Argumentos inválidos. Use apenas --email.")


def read_password(
    stdin,
    *,
    isatty: bool,
    prompter: Callable[[str], str] = getpass,
) -> str:
    if isatty:
        password = prompter("Palavra-passe: ")
        confirmation = prompter("Repetir palavra-passe: ")
        if password != confirmation:
            raise ValueError("As palavras-passe não coincidem.")
        return password

    line = stdin.readline()
    if line == "":
        raise ValueError("Palavra-passe em falta.")
    return line.rstrip("\n")


@contextmanager
def _default_sessions() -> Iterator[Session]:
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


def main(
    argv: list[str] | None = None,
    *,
    password_reader: Callable[[], str] | None = None,
    session_factory: Callable[[], Iterator[Session]] | None = None,
) -> int:
    received = list(sys.argv[1:] if argv is None else argv)
    if any(item == "--password" or item.startswith("--password=") for item in received):
        print("A palavra-passe não é um argumento.", file=sys.stderr)
        return 1

    parser = CommandParser(prog="python -m app.create_user")
    parser.add_argument("--email", required=True)
    try:
        arguments = parser.parse_args(received)
        password = (
            read_password(sys.stdin, isatty=sys.stdin.isatty())
            if password_reader is None
            else password_reader()
        )
        factory = _default_sessions if session_factory is None else session_factory
        with factory() as session:
            try:
                user = create_active_user(session, arguments.email, password)
                created_email = user.email
                session.commit()
            except AccountExists as exc:
                session.rollback()
                print(str(exc), file=sys.stderr)
                return 1
    except CommandError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OperationalError:
        print("Base de dados indisponível.", file=sys.stderr)
        return 1

    print(f"Conta criada para {created_email}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
