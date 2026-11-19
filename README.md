# Kaivita Produtor Académico

Protótipo de Licenciatura em Desenvolvimento de Software. É um projecto
independente, construído de raiz para a monografia. Este repositório contém
apenas o **incremento I0 — fundação técnica**.

Não há autenticação, produtores, produtos, ofertas, filas, Redis, inteligência
artificial nem sincronização offline.

## Arquitectura

Três processos, um repositório:

| Serviço | Tecnologia | Função neste incremento |
| --- | --- | --- |
| `web` | Next.js e TypeScript | Página inicial com ligações à API |
| `api` | FastAPI e Python | `GET /health` e documentação em `/docs` |
| `db` | PostgreSQL 16 | Base vazia de domínio, com versão Alembic |

A interface não chama a API por JavaScript. Os botões abrem `/health` e
`/docs` no browser, por isso este incremento não configura CORS.

```text
browser ──► Next.js :3000
   │
   └──► FastAPI :8000 ──► PostgreSQL :5432
```

A API confirma a base com `SELECT 1`. Se o PostgreSQL responder, `/health`
devolve HTTP 200. Se a API estiver no ar mas a base não, devolve HTTP 503
com `"database": "down"`.

## Decisões técnicas

- **Monorepo com duas pastas.** `frontend/` e `backend/` mantêm um ciclo de
vida cada um, sem transformar a fundação em microsserviços.
- **SQLAlchemy 2 síncrono.** O código de ligação cabe numa função e é mais
directo de explicar na defesa do que uma stack assíncrona. O volume esperado
de um protótipo académico não justifica `async`.
- **Uma só URL de base de dados.** `app.config.Settings` lê `DATABASE_URL`.
O Alembic reutiliza essa definição e o mesmo motor SQLAlchemy.
- **Migração inicial vazia.** `0001_initial` não cria tabelas de negócio.
Aplica-se para criar `alembic_version` e fixar o ponto de partida do esquema.
- **Testes sem base obrigatória.** O pytest substitui `check_database` por um
duplo. O contacto real com o PostgreSQL é opcional (`RUN_DB_TESTS=1`) e
também pode ser visto ao abrir `/health` com o Compose no ar.
- **Credenciais só de desenvolvimento.** Os valores por omissão estão no
`compose.yaml` e no `.env.example`. O `.env` real fica de fora do Git.
A palavra-passe de desenvolvimento tem de ser segura para uma URL.
- **Dependências curtas.** Sem ORM de sessão, sem CORS, sem biblioteca de
componentes e sem cliente HTTP no frontend. Cada dependência corresponde a
uma peça pedida neste incremento.

## Árvore

```text
.
├── compose.yaml
├── .env.example
├── .gitignore
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── alembic.ini
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/0001_initial.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── db.py
│   │   └── main.py
│   └── tests/
│       ├── conftest.py
│       ├── test_api.py
│       └── test_foundation.py
└── frontend/
    ├── Dockerfile
    ├── .dockerignore
    ├── package.json
    ├── package-lock.json
    ├── tsconfig.json
    ├── next.config.ts
    ├── next-env.d.ts
    └── app/
        ├── layout.tsx
        ├── page.tsx
        └── globals.css
```

## Arranque com Docker Compose

Na raiz do repositório, com Docker Desktop a correr:

```powershell
docker compose up --build
```

Não é obrigatório criar `.env`: o `compose.yaml` tem valores por omissão.
Para os substituir:

```powershell
Copy-Item .env.example .env
```

Quando os três contentores estiverem saudáveis:

- Interface: http://localhost:3000
- Estado da API: http://localhost:8000/health
- Documentação: http://localhost:8000/docs

Se a porta 3000, 8000 ou 5432 já estiver ocupada, escolhe outras.
A interface grava o endereço da API no momento do build, por isso uma
porta nova da API exige `--build`:

```powershell
$env:WEB_PORT = "3010"
$env:API_PORT = "8010"
$env:POSTGRES_PORT = "5435"
docker compose up --build
```

O contentor da API executa `alembic upgrade head` antes de aceitar pedidos.
Para inspeccionar a base:

```powershell
docker compose exec db psql -U kaivita -d kaivita -c "\dt"
```

O resultado esperado é só a tabela `alembic_version`.

Para parar e remover os contentores, mantendo os dados:

```powershell
docker compose down
```

`docker compose down -v` apaga também o volume `pgdata`.

## Testes da API

Na pasta `backend`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest -v
```

Com o PostgreSQL do Compose já publicado em `localhost:5432`:

```powershell
$env:RUN_DB_TESTS = "1"
python -m pytest -v
```

Se a base estiver noutra porta, indica a URL antes do pytest. Exemplo para a
porta 5435:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://kaivita:kaivita_dev@localhost:5435/kaivita"
$env:RUN_DB_TESTS = "1"
python -m pytest -v
```

Sem essa variável, o teste de ligação real é ignorado. Os restantes não
precisam de base de dados.

## Interface sem Docker

Na pasta `frontend`, depois de `npm install`:

```powershell
npm run dev
```

A página fica em http://localhost:3000. As ligações apontam para
http://localhost:8000, por isso a API tem de estar no ar para esses destinos
responderem. A página em si não depende da API.

## Limitações deste incremento

- A migração `0001_initial` não cria tabelas de domínio. Depois de aplicada,
a base só tem `alembic_version`.
- `pytest` sem `RUN_DB_TESTS=1` não abre ligação ao PostgreSQL. Confirma o
contrato da API e os ficheiros de configuração.
- O Compose constrói a interface em modo de produção. Alterar a página
exige um novo `docker compose up --build`.
- `npm audit` reporta avisos no PostCSS que vem fechado dentro do Next.js
15.5.29. O cenário é um CSS de terceiros durante o build. O CSS deste
incremento é o nosso `globals.css`. A correcção publicada pede o Next.js 16,
que fica de fora para não mudar de geração sem necessidade.
- O FastAPI 0.162 traz `opentelemetry-api` como dependência transitiva.
Não há exportador nem telemetria configurada.

## Fora deste incremento

Autenticação, perfis, produtores, produtos, ofertas, carregamento de ficheiros,
filas e qualquer sincronização entre clientes. O próximo passo só deve
começar depois da validação do I0.
