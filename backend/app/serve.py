"""Arranque da API com o access log redigido.

O contentor chama este módulo depois da migração. O caminho sem query
e sem texto livre continua disponível para diagnosticar o estado HTTP.
"""

import copy

import uvicorn
from uvicorn.config import LOGGING_CONFIG


def main() -> None:
    logging_config = copy.deepcopy(LOGGING_CONFIG)
    logging_config["formatters"]["access"]["()"] = "app.access_log.QuietAccessFormatter"
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        log_config=logging_config,
    )


if __name__ == "__main__":
    main()
