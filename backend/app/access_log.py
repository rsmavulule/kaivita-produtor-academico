"""Access log do Uvicorn sem query string nem texto livre no caminho.

O formato de origem junta o caminho e a query. Este formato separa-os
e só conserva segmentos fixos da API ou identificadores UUID.
"""

import logging
import re
from urllib.parse import urlsplit

_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_KNOWN = frozenset(
    {
        "archive",
        "auth",
        "authorizations",
        "actors",
        "contacts",
        "deactivate",
        "docs",
        "health",
        "login",
        "me",
        "offers",
        "openapi.json",
        "products",
        "public",
        "publish",
        "redoc",
        "roles",
        "suspend",
        "withdraw",
    }
)
_OMITTED = "{omitido}"


def safe_access_path(full_path: str) -> str:
    """Caminho operacional. A query e os segmentos livres não entram."""

    path = urlsplit(full_path).path or "/"
    pieces = []
    for segment in path.split("/"):
        if segment == "" or segment in _KNOWN or _UUID.fullmatch(segment):
            pieces.append(segment)
        else:
            pieces.append(_OMITTED)
    rendered = "/".join(pieces)
    return rendered if rendered.startswith("/") else f"/{rendered}"


class QuietAccessFormatter(logging.Formatter):
    """Substitui o caminho antes de o formatador do Uvicorn o escrever."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        from uvicorn.logging import AccessFormatter

        self._access = AccessFormatter(*args, **kwargs)

    def format(self, record: logging.LogRecord) -> str:
        if isinstance(record.args, tuple) and len(record.args) >= 5:
            client_addr, method, full_path, http_version, status_code = record.args[:5]
            record.args = (
                client_addr,
                method,
                safe_access_path(str(full_path)),
                http_version,
                status_code,
            )
        return self._access.format(record)
