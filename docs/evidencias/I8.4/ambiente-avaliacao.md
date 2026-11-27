# Ambiente isolado de avaliação — I8.4

O ambiente de avaliação não usa a base de desenvolvimento.
Os dois Compose partilham o ficheiro `compose.yaml` e separam-se pelo
projecto, pelo volume, pela base, pelas portas e pelas credenciais.

| | Desenvolvimento | Avaliação |
| --- | --- | --- |
| Projecto Compose | `kaivita-produtor-academico` | `kaivita-avaliacao` |
| Ficheiros | `compose.yaml` | `compose.yaml` e `compose.avaliacao.yaml` |
| Volume | `kaivita-produtor-academico_pgdata` | `kaivita-avaliacao-pgdata` |
| Base | `kaivita` | `kaivita_avaliacao` |
| Utilizador PostgreSQL | `kaivita` | `kaivita_avaliacao` |
| Portas no anfitrião | 5435, 8010, 3010 | 5436, 8020, 3020 |
| Emissor JWT | `kaivita-produtor-academico` | `kaivita-avaliacao` |
| Ficheiro de ambiente | `.env` | `.env.avaliacao`, fora do Git |

O volume da avaliação tem nome explícito em `compose.avaliacao.yaml`.
Não é o volume `pgdata` prefixado pelo projecto de desenvolvimento.

As credenciais estão só em `.env.avaliacao`. O modelo versionado é
`.env.avaliacao.example`, sem segredos. O script
`scripts/avaliacao.ps1` recusa as portas 5432, 5435, 8000, 8010, 3000
e 3010, recusa a base `kaivita` e confirma o projecto resolvido antes
de actuar.

A migração corre no arranque do contentor da API, até
`0008_offer_status_events`.

Os testes automatizados não usam esta base. `pytest` e Playwright
continuam no ambiente de desenvolvimento, ou numa base descartável
criada por eles. `.env.avaliacao` não define `DATABASE_URL`.

O ambiente escuta em localhost. Não foi publicado na Internet.

Preservação dos dados do I9: o volume `kaivita-avaliacao-pgdata`
sobrevive a `parar` e a `docker compose stop`. Um backup
`pg_dump` em `avaliacao-backups/` fica fora do Git. As respostas,
os consentimentos e as notas da avaliação não entram nesta base:
o protótipo não é o arquivo da investigação.

Reposição inicial, antes de uma sessão de avaliação que precise de
partir do zero: `scripts/avaliacao.ps1 repor -Confirmar` remove só
`kaivita-avaliacao-pgdata`, volta a criar a base vazia, aplica as
migrações e pára aí. `preparar` volta a criar o conjunto sintético.
O volume de desenvolvimento foi confirmado presente depois dessa
remoção.

Contagens da base de desenvolvimento, lidas antes e depois, sem
escrita: `kaivita`, 55 contas, 173 actores, 92 produtos, 40 ofertas,
2 contactos, Alembic `0008_offer_status_events`. Os contentores
`kaivita-produtor-academico-db-1`, `api-1` e `web-1` ficaram saudáveis.
