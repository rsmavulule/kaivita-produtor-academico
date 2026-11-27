# Guia operacional da avaliação — I8.4

Guia curto para arrancar o protótipo no ambiente de avaliação.
Não é um manual de Docker. Os comandos são PowerShell, na raiz do
repositório, com o Docker Desktop a correr.

Todos os comandos `scripts/avaliacao.ps1` actuam só no projecto
`kaivita-avaliacao`. Não param, não migram e não apagam a base de
desenvolvimento. Não usar `docker compose down -v` sem o script:
sem `-p kaivita-avaliacao` e sem `compose.avaliacao.yaml`, o Compose
predefinido é o de desenvolvimento.

## Pré-requisitos

Docker Desktop, PowerShell, Python 3 no anfitrião e `curl.exe`.
O script de sessão do browser usa o Playwright já instalado em
`frontend/node_modules`. Não é preciso para subir a aplicação.

## Configuração

```powershell
Copy-Item .env.avaliacao.example .env.avaliacao
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Colocar no `.env.avaliacao`, e só aí, a palavra-passe do PostgreSQL,
o `JWT_SECRET` e as três palavras-passe das contas. Não as versionar.
Os nomes das variáveis estão no exemplo. A base tem de continuar
`kaivita_avaliacao`, o utilizador `kaivita_avaliacao` e o emissor
`kaivita-avaliacao`. As portas previstas são 5436, 8020 e 3020.

## Arranque

```powershell
powershell -NoProfile -File scripts\avaliacao.ps1 subir
```

Constrói as imagens se for preciso, cria o volume
`kaivita-avaliacao-pgdata` e espera a API saudável. A primeira vez
demora o tempo do build. As seguintes reutilizam as imagens.

## Migrações

Não há comando separado. O contentor da API executa
`alembic upgrade head` antes de aceitar pedidos. A revisão esperada
é `0008_offer_status_events`. `subir` imprime-a. Para a reler:

```powershell
powershell -NoProfile -File scripts\avaliacao.ps1 contagens
```

## Contas e dados

```powershell
powershell -NoProfile -File scripts\avaliacao.ps1 preparar
```

Cria as três contas com `python -m app.create_user` dentro do
contentor da API. A palavra-passe entra por stdin e não é impressa.
O resto do conjunto sintético entra pela API. Pode repetir-se:
o que já existe não é duplicado.

Para criar uma conta à mão, no mesmo projecto:

```powershell
docker compose -p kaivita-avaliacao -f compose.yaml -f compose.avaliacao.yaml --env-file .env.avaliacao exec -T api python -m app.create_user --email pessoa@avaliacao.example
```

A palavra-passe é pedida no terminal, ou lida de uma linha de stdin.
Não vai nos argumentos.

## Endereços

- Interface: http://127.0.0.1:3020
- Entrada de sessão: http://127.0.0.1:3020/login
- Ofertas públicas: http://127.0.0.1:3020/ofertas
- Saúde da API: http://127.0.0.1:8020/health
- Documentação da API: http://127.0.0.1:8020/docs

O desenvolvimento, se estiver no ar, continua em 3010, 8010 e 5435.

## Saúde e logs

`subir` só termina quando `/health` responde com a base `up`.
Para ver o fim dos logs da API de avaliação:

```powershell
docker compose -p kaivita-avaliacao -f compose.yaml -f compose.avaliacao.yaml --env-file .env.avaliacao logs --tail 80 api
```

O mesmo com `web` ou `db`. Estes logs não são o arquivo de retenção.

## Verificação, backup e reinício

```powershell
powershell -NoProfile -File scripts\avaliacao.ps1 verificar
powershell -NoProfile -File scripts\avaliacao.ps1 backup
powershell -NoProfile -File scripts\avaliacao.ps1 persistencia
node scripts\avaliacao-sessao.cjs
```

`verificar` acrescenta uma oferta que fica retirada e um contacto
que fica revogado. Não substitui o conjunto de demonstração.
Não lançar aqui `pytest` nem Playwright: essas suites não são deste
volume.

`backup` grava um `pg_dump` em `avaliacao-backups/`. A pasta está
no `.gitignore`.

Para recuperar sem tocar na base em uso:

```powershell
powershell -NoProfile -File scripts\avaliacao.ps1 recuperar -Ficheiro avaliacao-backups\NOME.dump
```

Cria `kaivita_avaliacao_restauro`, compara e apaga essa base lateral.
Para substituir a base de avaliação pelo dump:

```powershell
powershell -NoProfile -File scripts\avaliacao.ps1 recuperar -Sobrepor -Confirmar -Ficheiro avaliacao-backups\NOME.dump
```

`-Confirmar` é obrigatório. O comando recusa um ficheiro fora de
`avaliacao-backups`.

## Paragem

```powershell
powershell -NoProfile -File scripts\avaliacao.ps1 parar
```

Para os três contentores e mantém o volume. Para voltar:

```powershell
powershell -NoProfile -File scripts\avaliacao.ps1 subir
```

## Reposição inicial

Antes de uma sessão que deva começar no conjunto sintético, sem
dados deixados por um ensaio anterior:

```powershell
powershell -NoProfile -File scripts\avaliacao.ps1 repor -Confirmar
powershell -NoProfile -File scripts\avaliacao.ps1 preparar
```

`repor -Confirmar` apaga só `kaivita-avaliacao-pgdata`, confirma que
`kaivita-produtor-academico_pgdata` continua presente, sobe de novo
e exige a base vazia em `0008_offer_status_events`. Sem `-Confirmar`
não corre.

## Problemas frequentes

O script recusa a porta ou a base. O `.env.avaliacao` ainda aponta
para o desenvolvimento, ou o `JWT_SECRET` está vazio. Corrigir esse
ficheiro. Não copiar o `.env` de desenvolvimento para cima dele.

A interface abre e o login não chega à API. A imagem `web` foi
construída com outra `API_PORT`. Correr `subir` outra vez: esse
comando reconstrói.

`/health` não fica `up`. Ver `logs` de `db` e de `api`. A causa
habitual é o contentor da base ainda a iniciar, ou um `JWT_SECRET`
em falta que impede a API de arrancar.

Duas avaliações não devem partilhar este volume ao mesmo tempo.
Não há segundo ambiente dentro deste script.

A fotografia de demonstração pode não aparecer. A oferta continua.
O componente omite a imagem se o anfitrião não responder.
