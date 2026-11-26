# Relatório final — I8.3

Não houve commit nem push. O HEAD de `main` mantém-se em
`d3fb83d5bbcb8abff8155d027d036fd85ac231af`
(`feat(i8.2): implement offer lifecycle auditing and privacy safeguards`).

## 1. Baseline

Alembic `0008_offer_status_events`. Backend no I8.2: 280 testes
aprovados. Playwright no I8.2: 65 testes, 63 aprovados e 2 falhados
(`contacts.spec.ts` linhas 76 e 265). As linhas 198 e 292 passaram nessa
execução e não estavam declaradas estáveis. Classificação então: 25
validados, 1 implementado não validado (RNF-02), 1 parcial (RNF-06).

## 2. Causa de cada falha investigada

Logout, linha 76. Sincronização do teste. A produção já limpa o cookie
e redirecciona para `/login?motivo=terminada`. O teste abria `/login`
antes desse redirect, com a sessão ainda válida, e ficava em `/inicio`.

Elegibilidade, linha 265. Sincronização do teste. O visitante consultava
enquanto publicar, suspender ou republicar ainda não estava visível.
`p.eyebrow` sem `main` apanhava também o cabeçalho «Sessão».

Contacto do visitante, linha 198. A mesma sincronização, intermitente
antes e aprovada no I8.2. Não se demonstrou defeito estável da ocultação.

Oferta de outro actor, linha 292. Não é mensagem errada. Numa das três
repetições o segmento ficou em «A carregar as ofertas.» e `p.alert` não
apareceu. A acção de produção permanece no formulário com «Produto não
encontrado.» quando o produto não é do actor. O URL já era
`/ofertas/nova` antes de a acção acabar. O teste passou a esperar o POST
e o fim desse fallback, sem aumentar timeouts.

## 3. Correcções

Os três testes de contactos esperam o estado visível do produtor antes
do clique do visitante, e o logout espera o URL da sessão terminada.
O envio da oferta de outro actor espera o POST e o fim do fallback de
carregamento antes do alerta. Há um teste de teclado em contacto, oferta
e produto. O teste temporal usa o mesmo `CURRENT_TIMESTAMP` na concessão
e na revogação.

## 4. Produção e testes

Nenhum ficheiro de produção foi alterado. `playwright.config.ts` também
não. Timeouts e retries ficaram iguais. Não há esperas fixas.

## 5. Teste temporal

`2099-01-01` saiu. A linha histórica revogada grava os dois instantes
com o `CURRENT_TIMESTAMP` de uma só instrução e verifica
`revoked_at >= granted_at`. Os rejeites, incluindo 2020, mantêm-se.
Não depende do ano. A suite de 280 testes passou com esta versão.

## 6. RNF-02

Os três formulários em falta percorrem Tab, Shift+Tab, rótulo, foco
visível, Enter, validação nativa e, no contacto e no produto, a
confirmação por teclado. Isolados: 3 aprovados em 1,0 min. Incluídos
nas duas suites de 68. Classificação proposta: validado para o texto
da SRS. Não é WCAG.

## 7. Desempenho

A SRS não tem número. O limiar de 500 ms proposto no I8.0 não foi
aprovado e não foi usado. `GET /public/offers`, 21 ofertas, página de
20, vinte amostras depois de três aquecimentos: sem filtro, mediana
22,1 ms e máximo 25,3 ms; com filtro sem resultados, mediana 22,5 ms e
máximo 26 ms. Um cliente, relógio que inclui o arranque do `curl`.
Sem optimização. Detalhe em `desempenho.md`.

## 8. Estabilidade

Repetições do quarteto: a primeira foi contaminada (servidor 3100
terminado, ligação recusada); a segunda, 4 aprovados em 1,9 min; a
terceira, 3 aprovados e a linha 292 falhada no fallback de carregamento.
Todas ficam registadas. A aprovação da segunda não esconde a terceira.

## 9. Suites completas

Backend: 280 passed in 73,42 s e, a seguir, 280 passed in 71,49 s.
Build: duas invocações registadas saíram 0 (cerca de 36,7 s e 31,9 s,
Next.js 15.5.29). Uma suite completa sobreposta a uma build foi
interrompida por `routes-manifest.json` em falta e não conta. Imagens
não reconstruídas. Serviços saudáveis, Alembic em `0008`.

Playwright oficial, sem build em paralelo: 68 passed (7,4 min) e
68 passed (7,6 min), exit 0 nos dois. O critério de duas suites
consecutivas sem falhas fica cumprido.

## 10. Ficheiros

Criados em `docs/evidencias/I8.3/`: `relatorio-final.md`,
`diagnostico-e2e.md`, `correccoes-implementadas.md`, `teste-temporal.md`,
`validacao-rnf02.md`, `desempenho.md`, `procedimento-execucao-testes.md`,
`pytest-resultados.txt`, `playwright-resultados.txt`, `build-compose.txt`,
`rastreabilidade.md`.

Modificados: `backend/tests/test_publication.py`,
`frontend/e2e/contacts.spec.ts`, `frontend/e2e/offers.spec.ts`,
`frontend/e2e/products.spec.ts`.

## 11. Rastreabilidade

26 validados e 1 parcial. RNF-02 passa a validado no texto da SRS.
RNF-06 e Q-06 continuam parciais. RNF-07 mantém o fecho do I8.2.
O soft 404 da ficha não entra na contagem.

## 12. Limitações

A linha 292 mostrou, uma vez, o fallback «A carregar as ofertas.» em vez
do alerta. Não se demonstrou defeito da rejeição. A espera do POST não
aumenta o timeout. As duas suites completas passaram esse teste.

O soft 404 da ficha pública continua em HTTP 200. A retenção Q-06 e o
texto livre de RNF-06 continuam abertos. A medição de tempo não é
teste de carga e não cria limiar. A cache do Chromium e o proxy pessoal
não foram versionados.

## 13. Git

Branch `main`, HEAD `d3fb83d`. Sem commit e sem push. Por versionar:
os quatro ficheiros de teste e `docs/evidencias/I8.3/`. Continuam de
fora, como já estavam, `_srs_extract.txt` e `docs/srs/`.
