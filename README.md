# Kaivita Produtor Académico

Protótipo de Licenciatura em Desenvolvimento de Software. É um projecto
independente, construído de raiz para a monografia. O repositório contém a
fundação técnica (I0), o modelo de identidade (I1.1), a autenticação (I1.2),
a autorização de representação (I1.3) e a gestão de actores e papéis
comerciais (I2).

Não há registo público, recuperação de palavra-passe, refresh tokens,
concessão de acessos a outros utilizadores, produtos, ofertas, filas, Redis,
inteligência artificial nem sincronização offline.

## Arquitectura

Três processos, um repositório:

| Serviço | Tecnologia | Função neste incremento |
| --- | --- | --- |
| `web` | Next.js e TypeScript | Página inicial com ligações à API |
| `api` | FastAPI e Python | Saúde, autenticação, actores e papéis comerciais |
| `db` | PostgreSQL 16 | Identidade e acesso, versão Alembic `0002_identity_access` |

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
O ficheiro não é editado nos incrementos seguintes.
- **Identidade na migração seguinte.** `0002_identity_access` cria o modelo
de acesso e semeia os três papéis comerciais. As restrições ficam na base.
- **Testes sem base obrigatória.** O pytest substitui `check_database` por um
duplo. O contacto real com o PostgreSQL é opcional (`RUN_DB_TESTS=1`) e
também pode ser visto ao abrir `/health` com o Compose no ar.
- **Segredo JWT obrigatório.** ``JWT_SECRET`` não tem valor por omissão.
Sem ele, a API não arranca. A expiração inicial é 30 minutos e o emissor
é ``kaivita-produtor-academico``.
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
│   │   └── versions/
│   │       ├── 0001_initial.py
│   │       └── 0002_identity_access.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── identity.py
│   │   ├── passwords.py
│   │   ├── tokens.py
│   │   ├── accounts.py
│   │   ├── auth.py
│   │   ├── authorization.py
│   │   ├── actors.py
│   │   ├── actor_roles.py
│   │   ├── roles.py
│   │   ├── create_user.py
│   │   └── main.py
│   └── tests/
│       ├── conftest.py
│       ├── test_api.py
│       ├── test_auth.py
│       ├── test_authorization.py
│       ├── test_actor_roles.py
│       ├── test_foundation.py
│       └── test_identity.py
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

Depois do I1.1, `\dt` mostra `alembic_version`, `users`, `actors`, `roles`,
`actor_roles` e `user_actor_access`. A revisão Alembic corrente é
`0002_identity_access`.

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

Sem essa variável, o teste de ligação real e os testes de integridade do
modelo são ignorados. Os restantes não precisam de base de dados.
A cabeça do Alembic esperada é `0002_identity_access`; `0001_initial`
continua a ser a revisão vazia de partida.

## Interface sem Docker

Na pasta `frontend`, depois de `npm install`:

```powershell
npm run dev
```

A página fica em http://localhost:3000. As ligações apontam para
http://localhost:8000, por isso a API tem de estar no ar para esses destinos
responderem. A página em si não depende da API.

## Incremento I1.1 — identidade e acesso

O modelo persistente está em `backend/app/identity.py`. A autenticação
entra no I1.2 e a representação no I1.3.

| Tabela | Chave | Função |
| --- | --- | --- |
| `users` | `id` | Conta. `email` é o login e é único |
| `actors` | `id` | Pessoa (`person`) ou organização (`organization`) |
| `roles` | `id` | Catálogo `producer`, `buyer`, `partner` |
| `actor_roles` | `(actor_id, role_id)` | Papéis comerciais do actor |
| `user_actor_access` | `(user_id, actor_id)` | Quem representa o actor, e com que nível |

Estados fechados na base: conta `active` ou `disabled`; actor `active` ou
`inactive`; representação `read` ou `manage`, com estado `active` ou
`revoked`. A migração insere os três papéis. Repetir essa inserção não
duplica linhas.

`general_location` pode ser nula: ausência significa localização desconhecida.
Apagar um utilizador, um actor ou um papel que ainda tenha associação é
recusado pela chave estrangeira.

## Incremento I1.2 — autenticação

O login é `POST /auth/login`. A consulta da conta é `GET /auth/me`, com
`Authorization: Bearer`. No `/docs`, o cadeado pede só o `access_token`;
a página acrescenta `Bearer`. O token HS256 expira ao fim de 30 minutos e
leva apenas o UUID do utilizador, o emissor, `iat` e `exp`.

A palavra-passe fica como resumo Argon2id. Não há endpoint de registo.
Uma conta de teste cria-se na pasta `backend`, com o segredo já definido:

```powershell
python -m app.create_user --email pessoa@example.com
```

A palavra-passe é pedida no terminal, ou lida de uma linha de stdin.
Não entra nos argumentos e não é impressa.

Para gerar o segredo, uma vez, e colá-lo no `.env` local:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Incremento I1.3 — representação

`GET /actors` lista os actores cuja associação do utilizador autenticado
está `active`. `GET /actors/{actor_id}` exige essa associação com nível
`read` ou `manage`. `PATCH /actors/{actor_id}` só altera `display_name` e
`general_location`, e exige `manage` activo.

A decisão é lida na base em cada pedido. O JWT continua a trazer apenas a
conta. Actor inexistente, associação em falta, associação `revoked` e nível
insuficiente respondem 404 com o mesmo texto. Token ausente ou inválido,
e conta `disabled`, respondem 401.

Não há endpoint para conceder ou revogar acessos. A criação do actor
entra no I2. As linhas de teste deste incremento criam-se directamente
na base. Um PATCH com `{}` não altera o actor. Um identificador que não
é UUID responde 422.

A autorização e a escrita do mesmo pedido partilham uma sessão e um commit.
Não há bloqueio da linha: outra transacção pode revogar o acesso depois da
leitura e antes da escrita.

## Incremento I2 — actores e papéis comerciais

`POST /actors` cria uma pessoa ou uma organização, associa pelo menos um
papel comercial e dá ao utilizador autenticado acesso `manage` activo.
O identificador, o nível e o estado dessa autorização não vêm no pedido.

`GET /roles` devolve as três linhas já semeadas: `producer`, `buyer` e
`partner`, com os mesmos UUID. `GET /actors/{actor_id}/roles` exige
representação `read` ou `manage` activa. `PUT /actors/{actor_id}/roles`
substitui o conjunto e exige `manage` activo. A lista vazia, o código
desconhecido e a repetição são recusados antes de alterar associações.

O papel comercial não autoriza a representação. `producer`, por exemplo,
não concede `manage`. Actor inexistente ou inacessível continua a
responder 404. Não há migração nova: a revisão permanece
`0002_identity_access`.

## Limitações deste incremento

- `0001_initial` permanece vazia. As tabelas de identidade nascem em `0002`.
Não houve migração nova: a conta já tinha `email`, `password_hash` e `status`.
O I2 também não cria revisão. A lista de papéis vazia é recusada pela API;
a base continua a permitir um actor sem linhas em `actor_roles`.
- A SRS menciona área de actuação. O campo persistido continua a ser
`general_location`. Não foi acrescentada outra coluna.
- `GET /roles` não pede token. A resposta é o catálogo de três códigos,
sem dados de actores nem de contas.
- O email tem de estar em minúsculas, conter `@` e não ter espaços. Não é um validador RFC.
- A palavra-passe de login tem entre 8 e 128 caracteres.
- `pytest` sem `RUN_DB_TESTS=1` não abre ligação ao PostgreSQL. Confirma o
contrato da API, a cadeia de migrações e a forma do modelo em Python.
- O Compose constrói a interface em modo de produção. Alterar a página
exige um novo `docker compose up --build`.
- `npm audit` reporta avisos no PostCSS que vem fechado dentro do Next.js
15.5.29. O cenário é um CSS de terceiros durante o build. O CSS deste
incremento é o nosso `globals.css`. A correcção publicada pede o Next.js 16,
que fica de fora para não mudar de geração sem necessidade.
- O FastAPI 0.162 traz `opentelemetry-api` como dependência transitiva.
Não há exportador nem telemetria configurada.

## Fora deste incremento

Registo público, recuperação de palavra-passe, refresh tokens, concessão
e revogação de acessos a outros representantes, alteração do catálogo
global de papéis, produtos, ofertas, contactos públicos, interfaces de
login, carregamento de ficheiros, filas e qualquer sincronização entre
clientes. O próximo passo só deve começar depois da validação do I2.
