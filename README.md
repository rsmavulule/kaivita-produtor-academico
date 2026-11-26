# Kaivita Produtor Académico

Protótipo de Licenciatura em Desenvolvimento de Software. É um projecto
independente, construído de raiz para a monografia. O repositório contém a
fundação técnica (I0), o modelo de identidade (I1.1), a autenticação (I1.2),
a autorização de representação (I1.3), a gestão de actores e papéis
comerciais (I2), o catálogo de produtos (I3), a gestão de ofertas
comerciais (I4), a sessão da interface (I5), a descoberta pública de
ofertas na API (I6.1), a interface pública dessa descoberta (I6.2), a
gestão privada de contactos comerciais (I7.1) e a autorização de
divulgação desses contactos (I7.2).

Não há registo público, recuperação de palavra-passe, refresh tokens,
concessão de acessos a outros utilizadores, filas, Redis, inteligência
artificial nem sincronização offline. A descoberta pública de ofertas
existe na API e na interface, em `/`, `/ofertas` e
`/ofertas/[offerId]`. A consulta pública dos contactos autorizados
existe só na API, em `GET /public/offers/{offer_id}/contacts`. A
interface ainda não a apresenta. Os contactos nascem privados.

## Arquitectura

Três processos, um repositório:

| Serviço | Tecnologia | Função neste incremento |
| --- | --- | --- |
| `web` | Next.js e TypeScript | Entrada pública, descoberta de ofertas, login e sessão HttpOnly |
| `api` | FastAPI e Python | Saúde, autenticação, actores, papéis, produtos, ofertas privadas, contactos privados, autorizações de divulgação e descoberta pública |
| `db` | PostgreSQL 16 | Identidade, acesso, produtos, ofertas, contactos e autorizações, versão Alembic `0006_publication_authorizations` |

Os pedidos autenticados ficam no servidor Next.js. O browser não recebe o
JWT e não chama a API. A descoberta pública também é lida no servidor,
com `API_URL` e `cache: no-store`, sem cabeçalho de credenciais. A entrada
não liga a `/health` nem a `/docs`.

```text
browser ──► Next.js :3000
              │  cookie HttpOnly
              ▼
            FastAPI :8000 ──► PostgreSQL :5432
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
componentes e sem cliente HTTP de terceiros no frontend. O servidor Next.js
usa `fetch`. Cada dependência corresponde a uma peça pedida.

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
│   │       ├── 0002_identity_access.py
│   │       ├── 0003_products.py
│   │       ├── 0004_offers.py
│   │       ├── 0005_contacts.py
│   │       └── 0006_publication_authorizations.py
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
│   │   ├── products.py
│   │   ├── catalog.py
│   │   ├── offers.py
│   │   ├── offer_catalog.py
│   │   ├── contacts.py
│   │   ├── contact_catalog.py
│   │   ├── publication.py
│   │   ├── publication_catalog.py
│   │   ├── public_offers.py
│   │   ├── public_catalog.py
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
│       ├── test_identity.py
│       ├── test_products.py
│       ├── test_offers.py
│       ├── test_contacts.py
│       ├── test_publication.py
│       └── test_public_offers.py
└── frontend/
    ├── Dockerfile
    ├── .dockerignore
    ├── package.json
    ├── package-lock.json
    ├── tsconfig.json
    ├── next.config.ts
    ├── next-env.d.ts
    ├── middleware.ts
    ├── playwright.config.ts
    ├── lib/
    │   ├── api.ts
    │   ├── cookie-name.ts
    │   ├── cookie-policy.ts
    │   ├── current-session.ts
    │   ├── errors.ts
    │   ├── origin.ts
    │   └── session.ts
    ├── e2e/
    │   ├── auth.spec.ts
    │   ├── global-setup.ts
    │   └── support.ts
    └── app/
        ├── layout.tsx
        ├── page.tsx
        ├── globals.css
        ├── login/
        │   ├── page.tsx
        │   ├── login-form.tsx
        │   ├── actions.ts
        │   └── form-state.ts
        ├── sessao/
        │   └── invalida/
        │       └── route.ts
        └── (privada)/
            ├── layout.tsx
            ├── loading.tsx
            ├── error.tsx
            ├── reload-on-back.tsx
            └── inicio/
                └── page.tsx
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

Depois do I7.2, `\dt` mostra `alembic_version`, `users`, `actors`, `roles`,
`actor_roles`, `user_actor_access`, `products`, `offers`,
`public_contacts` e `publication_authorizations`. A revisão Alembic
corrente é `0006_publication_authorizations`.

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
A cabeça do Alembic esperada é `0006_publication_authorizations`.
`0005_contacts` continua a ser a revisão dos contactos, `0004_offers` a
das ofertas, `0003_products` a do catálogo, `0002_identity_access` a de
identidade e `0001_initial` a revisão vazia. Os testes de migração de
produtos, de ofertas, de contactos e de autorizações criam bases à
parte, no mesmo servidor, e apagam-nas no fim. A conta PostgreSQL do
Compose consegue criar essas bases.

## Testes de ponta a ponta

Pré-requisitos: Docker Desktop, Node.js, o ambiente `backend/.venv` e o
Chromium do Playwright. Na pasta `frontend`, uma vez:

```powershell
npm install
npx playwright install chromium
```

Com o Compose saudável nas portas publicadas (neste ambiente, 3010, 8010 e
5435), a regressão corre contra o contentor. Não gera nem substitui capturas
versionadas. Se existir um proxy HTTP, exclua o anfitrião local.

```powershell
$env:NO_PROXY = "127.0.0.1,localhost"
$env:no_proxy = "127.0.0.1,localhost"
$env:E2E_NO_SERVER = "1"
$env:E2E_BASE_URL = "http://127.0.0.1:3010"
npm run test:e2e
```

A conta sintética é criada no arranque e removida no fim, juntamente com os
actores que só ela representa. Duas execuções ao mesmo tempo são recusadas
por `frontend/e2e/.run.lock`. Não há retries. A API é recolocada em serviço
no fim, inclusive depois do teste que a pára.

Se uma execução for interrompida e o cadeado ou a API ficarem presos:

```powershell
Remove-Item frontend/e2e/.run.lock -ErrorAction SilentlyContinue
docker compose start api
curl.exe --noproxy "*" http://127.0.0.1:8010/health
docker compose restart web
curl.exe --noproxy "*" -o NUL http://127.0.0.1:3010/login
```

Para gravar as capturas do I5.5, e só essas, numa execução explícita:

```powershell
$env:E2E_EVIDENCE = "I5.5"
npx playwright test e2e/integracao.spec.ts
Remove-Item Env:E2E_EVIDENCE
```

O procedimento completo está em `docs/evidencias/I5.5/procedimento.txt`.

## Interface sem Docker

Na pasta `frontend`, depois de `npm install`:

```powershell
npm run dev
```

A página fica em http://localhost:3000. O servidor lê `API_URL`. Se a
variável não estiver no ambiente, o `next.config.ts` usa `API_URL` ou
`API_PORT` do `.env` da raiz. A API tem de estar publicada nesse endereço
para o login responder. As ligações de saúde e documentação usam
`NEXT_PUBLIC_API_URL`, gravado no arranque do `next dev`.

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
responder 404. O I2 não cria migração; nesse incremento a revisão permanece
`0002_identity_access`.

## Incremento I3 — catálogo de produtos

`0003_products` cria a tabela `products`, depois de `0002_identity_access`.
As migrações anteriores não são editadas. Essa revisão não cria tabelas de
ofertas, categorias ou ficheiros.

Os pedidos ficam por baixo do actor:

- `POST /actors/{actor_id}/products` cria o produto. Exige `manage` activo
  e o papel `producer` entre os papéis do actor. O corpo leva `name`,
  `description`, `category` e, se existir, `image_ref`. O dono é o actor
  do caminho. `owner_actor_id` no corpo responde 422.
- `GET /actors/{actor_id}/products` e `GET .../products/{product_id}` exigem
  `read` ou `manage` activo. A lista inclui produtos `active` e `archived`,
  só desse actor, por nome e id.
- `PATCH .../products/{product_id}` altera os campos descritivos e exige
  `manage` e o papel `producer`. Não muda o dono nem o estado.
- `POST .../products/{product_id}/archive` passa o estado a `archived`,
  conserva os outros campos e pode repetir-se. Não há `DELETE`.

Actor inacessível, representação revogada ou nível insuficiente respondem
404 com `Actor não encontrado.` Um produto que não pertence ao actor do
caminho responde 404 com `Produto não encontrado.`, sem dados desse produto.
O papel `producer` não substitui a representação. Pode estar junto de
`buyer` e `partner`. Sem ele, a escrita responde 422 e a consulta continua
possível. A base não aplica esta regra: só a API.

O estado `active` ou `archived` não vem na SRS nem no diagrama. É a decisão
deste incremento. A fotografia é opcional, como no RF-02: `image_ref` nulo
significa que não há referência. O texto não é um ficheiro guardado.

## Incremento I4 — ofertas comerciais

`0004_offers` cria a tabela `offers`, depois de `0003_products`. As migrações
anteriores não são editadas. A revisão também cria `uq_products_id_owner`,
para a oferta referenciar o par `(id, owner_actor_id)` do produto.

Os pedidos ficam por baixo do actor e exigem token:

- `POST /actors/{actor_id}/offers` cria um rascunho. Exige `manage` activo
  e o papel `producer`. O corpo leva `product_id`. Preço, moeda, quantidade,
  unidade, disponibilidade e condições de entrega podem ficar por preencher.
  O dono é o actor do caminho.
- `GET /actors/{actor_id}/offers` e `GET .../offers/{offer_id}` exigem
  `read` ou `manage` activo. A lista inclui todos os estados, só desse
  actor, por id.
- `PATCH .../offers/{offer_id}` altera os campos comerciais enviados e
  exige `manage` e o papel `producer`. Não muda o dono, o produto nem o
  estado. Uma oferta `published` tem de continuar válida. Uma oferta
  `withdrawn` não se altera.
- `POST .../publish` passa de `draft` ou `suspended` a `published` quando
  o produto está `active` e os cinco campos de publicação estão válidos.
  Muda só o estado.
- `POST .../suspend` passa de `published` a `suspended`.
- `POST .../withdraw` passa de `draft`, `published` ou `suspended` a
  `withdrawn`. A linha permanece. Não há `DELETE` nem `/archive`.

Preço e quantidade são `NUMERIC` e saem em JSON como texto decimal.
O OpenAPI descreve os dois campos como string, com os exemplos `150.00` e
`2.50`. Um número fraccionário no JSON é recusado; o cliente envia `"150.00"`.
Um inteiro é aceite. A moeda, quando vem, são três letras maiúsculas.
Quantidade zero com disponibilidade `available` é recusada. Não há tecto
de valor, catálogo de moedas nem vocabulário de unidades.

Actor inacessível responde 404 com `Actor não encontrado.` Oferta ou
produto de outro actor respondem 404, sem dados desse recurso. Sem o papel
`producer`, a escrita responde 422 e a consulta continua possível. A base
não exige o papel. Exige, sim, que `product_id` e `owner_actor_id`
pertençam ao mesmo produto.

Arquivar o produto não muda as ofertas já gravadas. Não nascem ofertas
novas para esse produto, nem se publica ou republica uma oferta dele.
Uma oferta que já estava `published` continua nesse estado na consulta
privada. A descoberta pública deixa de a mostrar. O estado `published`
não autoriza a divulgação de contactos.

## Limitações deste incremento

- `0001_initial` permanece vazia. As tabelas de identidade nascem em `0002`.
O I1.2 e o I2 não criaram revisão. O I3 acrescenta `0003_products` e o I4
acrescenta `0004_offers`. A lista de papéis vazia é recusada pela API; a
base continua a permitir um actor sem linhas em `actor_roles`. O papel
`producer` do produto e da oferta também é regra da API, não um CHECK da base.
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
- Não há limite de produtos ou de ofertas por actor, nem tamanho máximo dos
textos. A SRS e o diagrama não os fixam. A categoria e a unidade são texto
livre. Preço e quantidade não têm tecto nem escala fixa.
- Arquivar não congela a ficha do produto: um `PATCH` posterior pode corrigir
nome, descrição, categoria ou referência, e o estado continua `archived`.
Não há operação para reactivar o produto nem a oferta retirada.
- Não há bloqueio da linha do produto nem da oferta. Outra transacção pode
retirar o papel `producer` ou a representação depois da leitura e antes da
escrita. A igualdade entre o dono da oferta e o dono do produto fica na
chave estrangeira composta.
- Uma oferta publicada cujo produto foi arquivado depois mantém o estado.
A descoberta pública do I6.1 não a devolve.
- O preço fraccionário tem de ir em texto JSON. Um número com casa decimal
é recusado, para não passar por ponto flutuante.
- Não há registo de auditoria das mudanças de publicação.
- A interface autentica, mostra a conta e gere actores, papéis, produtos e ofertas.
Ainda não há páginas públicas de ofertas. Não há contactos, encomendas nem
pagamentos. O logout apaga o cookie e não revoga o JWT.

## Incremento I5.1 — sessão da interface

O browser fala com o Next.js. O servidor chama `POST /auth/login` e
`GET /auth/me` com `Authorization: Bearer`. O `access_token` fica num
cookie `HttpOnly`, `SameSite=Lax` e `Path=/`, com `Max-Age` igual a
`expires_in`. `Secure` liga-se quando o protocolo observado é HTTPS.
Um `x-forwarded-proto: http` não o desliga. No Compose HTTP fica
desactivado. Um proxy que termina TLS e envia `x-forwarded-proto: https`
faz o Next.js observar HTTPS.

`API_URL` é lida no servidor. No Compose o valor é `http://api:8000`.
No `npm run dev` aponta para a porta publicada no anfitrião. Não há CORS
nem proxy genérico. Não há registo na interface.

Rotas: `/`, `/login`, `/inicio`. Sem cookie, `/inicio` volta a `/login`.
Cookie inválido ou expirado também volta a `/login`, depois de a API
responder 401. Uma falha de ligação ou um 5xx não apagam o cookie.

Os testes de ponta a ponta estão em `frontend/e2e` e usam Playwright.
A conta é criada na base de desenvolvimento e a palavra-passe não entra
no Git.

## Incremento I5.2 — actores e papéis

`GET /actors` e `GET /actors/{actor_id}` incluem `representation`, com o
valor `read` ou `manage` da associação activa do utilizador autenticado.
`POST`, `PATCH` e os endpoints de papéis não devolvem nem aceitam esse campo.

A interface lista os actores em `/actores` e abre a ficha em
`/actores/[actorId]`. A edição do nome, da localização e dos papéis só
aparece quando a representação é `manage`. A autorização continua na API.

## Incremento I5.3 — produtos

A ficha do actor liga a `/actores/[actorId]/produtos`. O registo, a edição
e o arquivo só aparecem com representação `manage` e papel `producer`.
A consulta fica disponível com `read` ou `manage`, mesmo sem esse papel.
O dono e o estado inicial vêm da API. Não há carregamento de imagens.

## Incremento I5.4 — ofertas

A ficha do actor liga a `/actores/[actorId]/ofertas`. Um produto activo
pode abrir `/ofertas/nova?produto=` com esse produto já escolhido.
O rascunho pode ficar incompleto. Preço e quantidade viajam como texto
decimal. Publicar, suspender e retirar usam os endpoints do I4.
Uma oferta retirada fica só em consulta. Um produto arquivado não cria
oferta nova nem se publica, e a oferta já gravada mantém o estado.

## Incremento I5.5 — integração

O percurso privado, da autenticação à oferta retirada, e a separação entre
gestor, leitura e ausência de representação ficam num teste de ponta a ponta.
A regressão não reescreve as capturas dos incrementos anteriores. Duas suites
Playwright não partilham o mesmo ambiente.

## Incremento I6.1 — descoberta pública na API

`GET /public/offers` e `GET /public/offers/{offer_id}` não pedem token.
Um cabeçalho `Authorization` não muda a resposta. As rotas privadas
permanecem como no I4.

Entram na consulta as ofertas `published` cujo produto está `active`,
cujo actor está `active` e que ainda têm o papel `producer`. A
disponibilidade `unavailable`, incluindo quantidade zero, continua
visível com esse valor. Rascunho, suspensa, retirada, produto arquivado,
actor inactivo e actor sem o papel ficam de fora da lista e do GET
directo, com o mesmo 404: `Oferta não encontrada.` A representação
`UserActorAccess` não entra no predicado. Não há coluna nova nem migração.

A resposta pública leva o identificador da oferta, preço, moeda,
quantidade, unidade, disponibilidade, condições de entrega, e o nome,
a descrição e a categoria do produto, mais o nome, o tipo e a localização
geral do produtor. Preço e quantidade saem como texto decimal, com os
exemplos `150.00` e `2.50`. Não vão identificadores de produto ou de
produtor, estado, `image_ref`, email, representação nem contactos
estruturados. O texto livre pode conter dados que alguém tenha escrito;
a API não os censura.

A pesquisa aceita `q`, `category` e `location`, até 100 caracteres.
`q` procura no nome ou na descrição. Os filtros diferentes combinam-se
por conjunção. Maiúsculas e os acentos portugueses do mapa são ignorados.
Espaços nas pontas saem e espaços internos seguidos viram um só. `%`, `_`
e `\` são literais. `limit` vai de 1 a 50, com omissão 20. `offset` vai
de 0 a 1000, com omissão 0. A ordenação é o nome normalizado do produto
e depois o identificador da oferta. `total` usa o mesmo predicado e os
mesmos filtros, na mesma instrução SQL, inclusive quando a página vem
vazia. Parâmetro desconhecido, repetido, tipo inválido ou UUID mal
formado responde 422 sem o valor recebido.

As respostas de `/public/`, incluindo erros, levam `Cache-Control: no-store`.
O mapa não cobre caracteres fora dele, como `ñ`, nem formas Unicode
decompostas. O SQL normaliza espaços POSIX; um espaço Unicode gravado na
coluna pode não coincidir com o termo. Não há índice novo nem meta de
desempenho medida.

## Incremento I6.2 — descoberta pública na interface

A entrada `/` apresenta a identidade, uma pesquisa e até seis ofertas
devolvidas por `GET /public/offers?limit=6`, na ordem da API. A listagem
está em `/ofertas` e a ficha em `/ofertas/[offerId]`. Os filtros `q`,
`category` e `location` ficam no URL. A página pede sempre `limit=20`.
O `offset` vai de 0 a 1000. Um parâmetro desconhecido, repetido ou fora
da gama não é enviado à API: a página pede para corrigir ou limpar, sem
repetir o valor. A ficha reconstrói o regresso só com esses filtros. Um
destino livre não é aceite.

Preço e quantidade aparecem como texto decimal. `available` lê-se
Disponível e `unavailable` lê-se Indisponível, mesmo com quantidade zero.
A interface não volta a filtrar a elegibilidade. Os formulários privados
de nome, localização, produto, condições de entrega e publicação avisam
que o texto pode ficar público. Não há caixa de consentimento nem
contacto do produtor.

As páginas públicas usam `fetch` com `cache: no-store` e
`dynamic = force-dynamic`. O Router Cache dinâmico fica com `staleTimes`
0. As ligações são âncoras, sem prefetch. Uma página já aberta não muda
sozinha: a actualização aparece na consulta seguinte. Não há meta de
desempenho medida.

## Incremento I7.1 — contactos comerciais privados

O representante com acesso `manage` cria, corrige e desactiva contactos do
actor em `/actors/{actor_id}/contacts`. O acesso `read` só consulta. O
contacto nasce `private` e `active`, com revisão 1. Os canais são `phone`,
`email` e `whatsapp`. O telefone e o WhatsApp guardam-se com `+` e 8 a 15
algarismos, sem inferir o indicativo do país. O email conserva a parte
local e põe o domínio em minúsculas. Não é o email de login.

A alteração efectiva do canal ou do valor incrementa a revisão. Uma
alteração que, depois da normalização, não muda o par não incrementa.
Desactivar conserva a linha, não incrementa a revisão e pode repetir-se.
Não há eliminação nem reactivação. O papel `producer` não é exigido.

A resposta privada traz `Cache-Control: private, no-store`. As rotas
públicas de listagem e ficha de ofertas não devolvem contactos. A
autorização de divulgação está no I7.2. O diagrama UML admite uma
autorização a cobrir vários contactos; o protótipo restringe essa
autorização a um contacto de cada vez. Os diagramas não foram alterados.

## Incremento I7.2 — autorização de divulgação

O representante `manage` concede e revoga a divulgação de um contacto
em `/actors/{actor_id}/contacts/{contact_id}/authorizations`. O acesso
`read` consulta o histórico. Cada concessão nova cria uma linha em
`publication_authorizations`. A linha vigente é a que tem `revoked_at`
nulo. A tabela não guarda o valor do contacto.

A concessão confirma a revisão actual, a finalidade
`commercial_discovery`, o aviso `v1` e `confirmed: true`. Repetir a
mesma concessão devolve a linha original. Uma revisão desactualizada,
um contacto inactivo ou uma autorização vigente incoerente respondem
409. Alterar o canal ou o valor, ou desactivar o contacto, revoga a
autorização vigente na mesma transacção. A publicação de uma oferta
não concede esta autorização.

`GET /public/offers/{offer_id}/contacts` não exige sessão. Usa o mesmo
predicado de elegibilidade do I6.1, na mesma instrução SQL. A resposta
traz só `channel` e `value`, ou uma lista vazia. Oferta inexistente ou
inelegível responde o 404 já usado na ficha. O cabeçalho é `no-store`.
A interface pede os contactos só na acção «Ver contactos», por um caminho
próprio que não reenvia a sessão.

## Fora deste incremento

Registo público, recuperação de palavra-passe, refresh tokens, concessão
e revogação de acessos a outros representantes, alteração do catálogo
global de papéis, catálogos
públicos independentes de produtos e actores, carregamento de ficheiros,
área de actuação, encomendas, pagamentos, reservas, filas e qualquer
sincronização entre clientes.
