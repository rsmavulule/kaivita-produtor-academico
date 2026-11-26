# Procedimento de execução — Windows

Não versionar a cache do browser, credenciais nem a configuração pessoal
de proxy. A limpeza E2E continua a apagar só as contas do manifesto da
execução. Não apaga por prefixo de email. Não apaga dados preexistentes.

## Ambiente observado nesta ronda

- Node v22.18.0, npm 11.6.3
- Next.js 15.5.29, Playwright 1.65.1
- Chromium da revisão 1255 (Chrome for Testing e Chrome Headless Shell
  159.0.8154.6), instalado pelo Playwright, fora do repositório
- PostgreSQL do Compose na porta 5435, API 8010, frontend 3010
- Alembic `0008_offer_status_events`
- Playwright sobe `npx next dev` em `127.0.0.1:3100`, sem reutilizar
  servidor, um worker, zero retries

## Preparar

1. Na raiz: `docker compose up -d` e confirmar db, api e web saudáveis.
2. Confirmar `alembic current` em `0008_offer_status_events`. Não fazer
   downgrade da base de desenvolvimento.
3. Se o Chromium 1255 faltar, em `frontend`: `npx playwright install chromium`.
4. Definir `NO_PROXY` e `no_proxy` como `127.0.0.1,localhost,::1`.
   Retirar `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` e as variantes em
   minúsculas do processo que vai correr os testes. Não gravar isso
   no repositório.
5. Retirar `E2E_EVIDENCE`. Não apontar a evidência histórica.
6. Confirmar que a porta 3100 está livre e que `frontend/e2e/.run.lock`
   não aponta para um processo vivo. O cadeado de um processo já morto
   é substituído. Não apagar o cadeado de uma execução viva.
7. Não correr `npm run build` ao mesmo tempo que o Playwright. Os dois
   escrevem `frontend/.next`.

## Backend

Em `backend`, com a venv do projecto:

```
$env:RUN_DB_TESTS='1'
.\.venv\Scripts\python.exe -m pytest -q --tb=line
```

## Frontend

O build de produção é `npm run build` em `frontend`, sozinho.

A suite é `npx playwright test` em `frontend`, com o proxy e
`E2E_EVIDENCE` como acima. Esperar o processo terminar antes de outra
suite ou de outro build. O manifesto e a limpeza correm no setup e no
teardown.
