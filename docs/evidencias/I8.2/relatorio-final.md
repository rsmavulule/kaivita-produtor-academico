# Relatório final — I8.2

Não houve commit nem push. O HEAD de `main` mantém-se em
`1a119b51b7c2f8c2c64454fddec9a39d3840b05a`
(`feat(i8.1): complete actor coverage and product photo rights`).

## 1. Baseline

Alembic versionado no I8.1: `0007_coverage_and_image_rights`.
Backend nessa base: 273 testes aprovados.
Playwright: 65 testes, 61 aprovados e 4 falhados.
RF-01, RF-02 e RB-08 já estavam no I8.1.

## 2. Auditoria

`OfferStatusEvent` regista a transição efectiva da oferta: publicação,
suspensão, republicação e retirada. A republicação é `suspended` para
`published`. A criação do rascunho não gera evento. Ofertas já
existentes não receberam eventos inventados.

Não há endpoint, painel, alteração nem eliminação pública. O histórico
de contactos continua em `publication_authorizations`, sem duplicação.

## 3. Persistência

Tabela `offer_status_events`, migração `0008_offer_status_events`.

Colunas: `id`, `offer_id`, `previous_status`, `new_status`,
`performed_by_user_id`, `occurred_at`. Chaves estrangeiras com
`ON DELETE RESTRICT`. O par de estados tem de ser uma transição que o
ciclo aceita. Índice por `offer_id`. Sem preço, quantidade, texto ou
contacto.

## 4. Consistência

A mudança de estado e o evento entram no mesmo savepoint. Transição
inválida, pedido sem gestão e falha de escrita não deixam evento.
Repetir uma transição recusada não cria segundo evento.

A oferta é bloqueada com `FOR UPDATE` e relida com `populate_existing`.
A representação deste operador também é bloqueada e relida, só neste
caminho. Não há bloqueio global nem mudança do commit síncrono.

## 5. Migração

`0008` segue `0007`. Não altera ofertas existentes e não insere
eventos. O teste numa base descartável fez upgrade, downgrade e novo
upgrade: a oferta `published` manteve-se e o número de eventos ficou
em zero. A base de desenvolvimento não teve downgrade e está em
`0008_offer_status_events`. A limpeza E2E apaga os eventos dos actores
exclusivos antes das ofertas e recusa apagar uma conta do manifesto
que ainda tenha evento noutro actor.

## 6. Segurança e privacidade

O aviso dos campos públicos passa a nomear a área de actuação, as
condições de entrega e o endereço da fotografia, e a dizer que a
aplicação não identifica sozinha dados pessoais no texto nem pessoas
ou contactos na imagem. Não há censura heurística.

Não foi acrescentado um comprimento máximo novo. Os máximos observados
na base de desenvolvimento eram curtos, o maior com 36 caracteres na
descrição. Nada foi truncado. `image_ref` mantém o tecto de 2048 na
escrita.

A fotografia do I8.1 mantém-se: sem pedido do servidor ao URL, sem
proxy, `no-referrer`, exposição pública só com declaração da referência
actual, e a conta declarante fora da resposta pública. Um anfitrião
local ou um IP que não é global passa a ser recusado, sem resolução
DNS. HTTPS não elimina o resto: um nome pode apontar para um servidor
que regista o visitante, ou resolver para um endereço privado.

## 7. Logs

Sonda com o marcador `i82probe4e2b`, descrita em `logs-verificacao.txt`.
Destinos vistos: contentores api, web e db, e a saída do `next dev` da
execução Playwright que chegou ao fim.

Na API, a query saiu, o segmento livre do caminho ficou `{omitido}`,
e o login 422 não mostrou corpo, email, palavra-passe nem Bearer. No
web, a query não foi escrita. Na base, o erro conservou o nome da
restrição e o marcador não entrou no log do contentor; o cliente psql
continuou a mostrar o DETAIL. A amostra não prova ausência universal.

## 8. Q-06

Continua parcialmente aberta. `retencao-q06.md` distingue dados
operacionais, histórico de autorizações, eventos de auditoria, logs
técnicos, dados sintéticos e dados de avaliação. Não há prazo legal
inventado, nem eliminação automática, nem apagamento de dados
existentes. A nota não fecha a questão nem afirma conformidade legal.

## 9. Riscos corrigidos

Evento incompatível com duas publicações concorrentes: a segunda espera
o bloqueio, vê o estado já publicado e não grava evento.
Leitura obsoleta do Identity Map nesse bloqueio: `populate_existing`.
Representação revogada no meio de publicar, suspender ou retirar: a
linha de acesso é relida depois do bloqueio.
Query e caminho livre no access log da API.
Linha rejeitada no log de erro do PostgreSQL do Compose.
URL de fotografia em anfitrião local ou IP não global.

## 10. Riscos residuais

Commit síncrono antes da resposta HTTP, por decisão do I5.
Isolamento `READ COMMITTED`.
Outras escritas continuam a ler a representação no início do pedido.
Identity Map se uma leitura futura bloquear um objecto já carregado
sem `populate_existing`.
DNS de um nome público pode resolver para uma rede privada.
O browser pede a fotografia directamente ao servidor externo.
Texto livre e conteúdo da imagem não são classificados pela aplicação.
Q-06 sem calendário aprovado.
Consola de quem executa SQL continua a receber o DETAIL.
Quatro falhas E2E conhecidas por estabilizar no I8.3. Nesta execução
só duas se reproduziram.

## 11. Testes

Backend, `RUN_DB_TESTS=1`: 280 passed em 61.08s, exit code 0.
Uma execução anterior no mesmo dia também passou os 280 em 56.83s.

Frontend: `npm run build`, Next.js 15.5.29, exit code 0.

Playwright, execução completa: 63 passed, 2 failed, 9.3m, exit code 1.
Falharam `contacts.spec.ts:76` e `contacts.spec.ts:265`.
Passaram `contacts.spec.ts:198` e `offers.spec.ts:292`.
Não ficam declaradas como estáveis. Duas tentativas anteriores ficaram
sem o servidor em 3100 e não são o resultado.

## 12. Rastreabilidade

RNF-07: validado no âmbito do protótipo académico. Autorizações de
contacto e transições de oferta ficam registadas sem conteúdo
comercial, e os destinos de log inspeccionados não mostraram o
marcador. O limite é a amostra, não todos os processos futuros.

RNF-06: parcial. A query saiu do access log e o aviso foi completado.
Continuam abertos o texto livre, a fotografia pedida pelo browser e
Q-06. Não se classifica como integralmente validado.

Q-06: parcialmente aberta.

## 13. Ficheiros

Criados:

- `backend/alembic/versions/0008_offer_status_events.py`
- `backend/app/access_log.py`
- `backend/app/serve.py`
- `backend/tests/test_i82_offer_events.py`
- `docs/evidencias/I8.2/` com os doze documentos deste fecho

Modificados:

- `backend/Dockerfile`
- `backend/app/offer_catalog.py`
- `backend/app/offers.py`
- `backend/app/products.py`
- `backend/tests/test_contacts.py`
- `backend/tests/test_foundation.py`
- `backend/tests/test_identity.py`
- `backend/tests/test_publication.py`
- `backend/tests/test_publication_concurrency.py`
- `compose.yaml`
- `frontend/app/(privada)/actores/[actorId]/produtos/novo/create-form.tsx`
- `frontend/e2e/cleanup.ts`
- `frontend/lib/public-offer-view.ts`
- `frontend/lib/public-offers.ts`
- `frontend/next.config.ts`

## 14. Git

Branch `main`, HEAD `1a119b5`, igual ao remoto no início do incremento.
Alterações por gravar, nada em staging. `_srs_extract.txt` e `docs/srs/`
continuam por seguir e não foram preparados. Sem commit e sem push.
I8.3, I8.4 e I9 não foram iniciados. A SRS e os diagramas não foram
alterados.
