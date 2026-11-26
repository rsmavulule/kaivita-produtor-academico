Diagnóstico de testes — I8.0

Contagens

Backend: 266 testes, todos aprovados com RUN_DB_TESTS=1, em 48,40 s.
Playwright: 64 testes definidos. Na passagem completa desta ronda,
61 aprovados e 3 falhados. O I7.3 tinha 64 aprovados. Esta ronda não
reproduz esse verde.

Distribuição Playwright, pela contagem dos ficheiros:

  auth.spec.ts            16
  actors.spec.ts           8
  products.spec.ts         7
  offers.spec.ts           9
  integracao.spec.ts       2
  public-offers.spec.ts   10
  contacts.spec.ts        12
  Total                   64

Tipos, sem percentagem de cobertura de linhas

Testes de configuração e de contrato, sem base ou com duplo:
test_foundation.py em parte, test_commit_order.py, testes de OpenAPI
e de mapeamento que não escrevem na base de desenvolvimento.

Testes de integração com TestClient e PostgreSQL, quando
RUN_DB_TESTS=1: autenticação, autorização, papéis, produtos, ofertas,
contactos, publicação e descoberta pública. São a maioria dos 266.

Testes com PostgreSQL real e migração em base descartável: as funções
cujo nome indica throwaway database ou migrated_database, em produtos,
ofertas, contactos e publicação.

Testes de concorrência: test_publication_concurrency.py e os testes
de criação concorrente de contactos. Duas sessões, bloqueio e espera.
Não são teste de carga.

Testes de segurança: rejeição de token, isolamento, ausência do valor
secreto na resposta e nos logs de aplicação, cookie, same-origin,
parâmetros inesperados. Estão espalhados pelos ficheiros, não numa
suite com esse nome.

Testes E2E com API real: a maior parte do Playwright, contra a API em
8010 e um next dev em 3100.

Testes com resposta simulada: falha de ligação no login, falha da API
na pesquisa pública e falha simulada da consulta de contactos. Não
substituem o percurso com API real, que também existe.

Testes de regressão: a suite inteira é a regressão. Não há uma selecção
separada.

Fragilidades

Dependência temporal. test_postgres_rejects_invalid_authorizations
insere uma autorização histórica com revoked_at em
2099-01-01T00:00:00Z. O CHECK exige revoked_at >= granted_at. granted_at
é CURRENT_TIMESTAMP. A data 2099 adia a falha; não a elimina. É
correcção obrigatória do I8, ainda não feita. A solução é calcular o
instante de revogação a partir do granted_at da linha, ou controlar o
relógio do teste. Não se substitui 2099 por outra constante futura.

Dependência de dados preexistentes. Os testes de API criam os seus
dados e fazem rollback, ou usam base descartável. A contagem da base
de desenvolvimento não mudou com o pytest. O Playwright depende do
manifesto da execução e do padrão de email. A limpeza não usa o
prefixo como prova de propriedade de actores partilhados: se uma
autorização operada pela conta existir noutro actor, a limpeza aborta.
Nesta ronda a contagem final coincidiu com a inicial.

Ordem. Playwright usa workers: 1 e fullyParallel: false. Há estado
partilhado na conta de demonstração criada no setup. Uma falha a meio
pode deixar a sessão do browser num estado que o teste seguinte não
espera. O teste de desactivação falhou à espera do formulário de login
porque a sessão ainda estava activa.

Chromium. @playwright/test 1.65.1 declara a revisão 1255 em
frontend/node_modules/playwright-core/browsers.json. O directório
habitual do utilizador tinha as revisões 1223 e 1234 e não tinha 1255.
Nesta sessão, PLAYWRIGHT_BROWSERS_PATH apontava para uma cache
temporária, também sem 1255, até à instalação feita para poder correr
a suite. A ausência é recorrente quando a versão do Playwright sobe
e o browser não é reinstalado no sítio onde o processo o procura.

Proxy. Com HTTP_PROXY definido e sem NO_PROXY para 127.0.0.1, o
verificador de arranque do Playwright recebia 503 e a suite nem
começava, embora o servidor respondesse 200 a outro cliente. Não se
aumentou o timeout.

Corrida de logout no spec de contactos. O teste clica em «Terminar
sessão» e chama de seguida goto(/login). A página de login
redirecciona para /inicio se o cookie ainda for válido. O teste de
autenticação espera o URL de sessão terminada e passou. A correcção
proporcional, no I8.3, é o spec de contactos esperar o mesmo URL antes
de voltar a entrar. Não é aumento de timeout.

Corrida da consulta pública. O visitante pede os contactos sem esperar
a confirmação visual da suspensão ou da revogação no outro browser. O
ponto de falha mudou entre a passagem completa e a repetição. Não se
esconde com retries. A correcção proporcional é esperar o estado no
browser do produtor antes da consulta do visitante.

Cenários sem cobertura suficiente

Área de actuação: não existe.
Declaração de direito de uso e referência pública de imagem: não existem.
Eventos de transição de oferta: não existem.
Teclado em produtos, ofertas e contactos: sem teste dedicado.
Tempo de resposta: sem medição.
Catálogos públicos independentes: não são obrigatórios; também não há
teste, porque não há função.
Queda de processo e restauro: não há teste.

Duplicação. Vários testes de isolamento repetem o 404 opaco em cada
recurso. A repetição é justificada: cada router pode esquecer a
verificação. Não se propõe apagar essa redundância.

Reprodução do ambiente

1. Na pasta frontend, com a versão fixa em package-lock.json:
   npx playwright install chromium
2. Confirmar que o directório usado por PLAYWRIGHT_BROWSERS_PATH,
   ou %LOCALAPPDATA%\ms-playwright se a variável não estiver definida,
   contém chromium-1255.
3. Confirmar a revisão em
   node_modules/playwright-core/browsers.json.
4. Para a suite local, definir NO_PROXY=127.0.0.1,localhost,::1
   quando existir HTTP_PROXY. Não alterar playwright.config.ts só
   para isto, salvo decisão posterior de tornar o arranque independente
   do proxy. Nesta ronda a variável foi do processo, não do repositório.
5. Subir Compose nas portas 5435, 8010 e 3010. A suite de browser usa
   a API em 8010 e o seu próprio next dev em 3100.
6. Correr npm run test:e2e sem E2E_EVIDENCE, para não reescrever
   capturas históricas. Com E2E_EVIDENCE igual a um incremento antigo,
   evidenceShot grava em docs/evidencias desse incremento.

Não se confunde 266 mais 64 com percentagem de código coberto.
