# Relatório final — I8.4

Não houve commit, push nem tag. O HEAD de `main` é
`ba62f255cef623cc7df4e25bf2b1e2cc82e2fd28`
(`test(i8.3): stabilize end-to-end tests and complete technical validation`),
igual a `origin/main`.

O I8.4 não alterou código de produção, testes, a SRS nem os diagramas.
Não consultou o projecto comercial.

## 1. Baseline

Alembic `0008_offer_status_events`.
Backend no I8.3: 280 testes aprovados em duas execuções (73,42 s e 71,49 s).
Playwright no I8.3: 68 testes aprovados em duas execuções consecutivas (7,4 min e 7,6 min).
Total então registado: 348 testes automatizados.
Build Next.js 15.5.29 aprovado no I8.3.
27 requisitos numerados. À entrada: 26 validados e 1 parcial.
RNF-06 parcial. Q-06 parcialmente aberta, fora do denominador.

Essas suites não foram repetidas. Não houve alteração com impacto no
comportamento que elas mediram.

## 2. Classificação definitiva

26 validados e 1 parcial, em 27.

| Grupo | Validado | Parcial |
| --- | ---: | ---: |
| RF-01 a RF-10 | 10 | 0 |
| RB-01 a RB-10 | 10 | 0 |
| RNF-01 a RNF-05 e RNF-07 | 6 | 0 |
| RNF-06 | 0 | 1 |

RNF-06 não foi promovido. Falta o calendário de retenção da secção 10
e a aplicação não detecta dados pessoais em texto livre nem em fotografias.
Q-06 continua parcialmente aberta e não entra na fracção.

Os oito casos de uso da secção 8 ficam validados nos seus critérios.
UC-02 e UC-04 deixam de estar parciais: a área de actuação e a
declaração da fotografia entraram no I8.1 e as suites do I8.3 passaram.
O detalhe está em `matriz-rastreabilidade-final.md` e
`matriz-casos-de-uso-final.md`.

## 3. Divergências UML

Os diagramas não foram editados. O código segue a SRS onde o diagrama
de classes ainda não a acompanha.

- `coverage_area` existe na base e na API. O diagrama de classes não a tem.
- A declaração de direitos existe em colunas e num `CHECK`. O diagrama só mostra `imageRef`.
- `OfferStatusEvent` é o rasto físico das transições. O diagrama de estados mostra o ciclo, não o rasto.
- O histórico de autorizações substitui, de forma justificada, a FK única do diagrama.
- O 404 opaco substitui o 403 desenhado na sequência.
- A nota do diagrama de estados que ainda pede aprovação da republicação está desactualizada. A republicação está implementada e testada.

A lista para a monografia está em `reconciliacao-uml.md`.

## 4. Arquitectura do ambiente de avaliação

O mesmo `compose.yaml`, com `compose.avaliacao.yaml` a fixar o projecto
`kaivita-avaliacao` e o volume `kaivita-avaliacao-pgdata`.
Base `kaivita_avaliacao`, portas 5436, 8020 e 3020, emissor JWT
`kaivita-avaliacao`. Três contentores: PostgreSQL 16, FastAPI e Next.js.
A API aplica Alembic até `0008` no arranque.

## 5. Isolamento e preservação

A base de desenvolvimento continuou `kaivita`, 55 contas, 173 actores,
92 produtos, 40 ofertas, 2 contactos e Alembic `0008`, antes e depois.
Os três contentores de desenvolvimento ficaram saudáveis.
Não se apagou dados por prefixo de email. As três contas mal gravadas
no primeiro ensaio, só na base de avaliação vazia, foram removidas por
email exacto e recriadas. Não havia actores ligados a elas.

O volume de avaliação foi removido na reposição e o de desenvolvimento
foi confirmado presente a seguir. As credenciais ficam em
`.env.avaliacao`, fora do Git. O ambiente não foi publicado.

## 6. Instalação

`scripts/avaliacao.ps1 subir` constrói, sobe e espera `/health`.
`preparar` cria contas e dados. `parar` mantém o volume.
`repor -Confirmar` apaga só o volume de avaliação e deixa a base vazia
já migrada. O procedimento está em `guia-operacional.md`.

## 7. Dados iniciais

Três contas sintéticas em `@avaliacao.example`: produtor com `manage`,
comprador com actor `buyer`, consulta com `read` sobre o produtor.
Dois produtos, uma oferta publicada e um rascunho, um contacto privado
e um contacto com autorização. A fotografia é uma referência HTTPS do
Wikimedia Commons, não uma imagem da FACIM. A licença desse ficheiro
não foi reconfirmada porque o anfitrião não respondeu. A ficha não
depende dela. Detalhe em `dados-iniciais.md`.

## 8. Smoke

No ambiente isolado: serviços no ar, base certa, Alembic `0008`,
API `database=up`, interface 200 em `/login`, `/` e `/ofertas`,
login válido, credencial inválida 401, actores, produtos, oferta
pública com fotografia declarada e condições de entrega, pesquisa,
rascunho oculto, divulgação e revogação, escrita da consulta recusada
com 404, comprador isolado, publicar/suspender/retirar com 3 eventos,
término de sessão no browser e recusa do acesso seguinte.
Os logs recentes da API não continham os contactos sintéticos.
O registo está em `smoke-test-resultados.txt`.

## 9. Backup e recuperação

O dump limpo, de 50943 bytes, foi lido numa base lateral com as mesmas
contagens e depois reposto sobre a base de avaliação. O reinício dos
três serviços conservou a oferta pública. A reposição do volume deixou
zero contas em `0008` e `preparar` reconstruiu o conjunto. O dump que
corresponde ao ambiente agora no ar é
`avaliacao-backups/kaivita-avaliacao-20261126-182423.dump`, 50944 bytes,
fora do Git. Detalhe em `backup-recuperacao.md`.

## 10. Regressão

Não aplicável. Não houve alteração de produção, de testes nem de
configuração que mude o comportamento validado no I8.3.
`compose.avaliacao.yaml` só nomeia outro projecto e outro volume.

## 11. Limitações

RNF-06 parcial. Q-06 parcialmente aberta. Texto livre e fotografias
sem detecção de dados pessoais. Fotografia externa opcional. Soft 404
da ficha pública em HTTP 200, com a API em 404. Concorrência residual
não observada como defeito. Desempenho só no registo do I8.3.
Sem validação em produção e sem avaliação empírica. Nenhum destes
pontos foi tratado como bloqueador. Não se corrigiu o soft 404.

## 12. Release candidate

Proposto `v1.0.0-rc.1`, sobre o commit `ba62f25`. Sem tag.
Não é a versão final avaliada. Notas em `release-notes.md`.

## 13. Ficheiros

Criados:

- `compose.avaliacao.yaml`
- `.env.avaliacao.example`
- `scripts/avaliacao.ps1`
- `scripts/avaliacao-sessao.cjs`
- `scripts/avaliacao-dados.json`
- `docs/evidencias/I8.4/relatorio-final.md`
- `docs/evidencias/I8.4/matriz-rastreabilidade-final.md`
- `docs/evidencias/I8.4/matriz-casos-de-uso-final.md`
- `docs/evidencias/I8.4/reconciliacao-uml.md`
- `docs/evidencias/I8.4/ambiente-avaliacao.md`
- `docs/evidencias/I8.4/guia-operacional.md`
- `docs/evidencias/I8.4/dados-iniciais.md`
- `docs/evidencias/I8.4/smoke-test-resultados.txt`
- `docs/evidencias/I8.4/backup-recuperacao.md`
- `docs/evidencias/I8.4/limitacoes-finais.md`
- `docs/evidencias/I8.4/release-notes.md`
- `docs/evidencias/I8.4/criterios-prontidao-i9.md`

Modificado: `.gitignore`, para ignorar `.env.avaliacao` e
`avaliacao-backups/`.

Fora do Git, de propósito: `.env.avaliacao`,
`avaliacao-backups/estado.json` e o dump. Também continuam de fora,
como já estavam, `_srs_extract.txt` e `docs/srs/`.

## 14. Git

Branch `main`, alinhada com `origin/main`, HEAD `ba62f25`.
Sem commit, sem push e sem tag.

## 15. Parecer

O candidato está pronto para o I9, no âmbito académico, com as
limitações escritas. O percurso principal funciona num ambiente que
não é a base de desenvolvimento, os dados de demonstração são
sintéticos e reponíveis, e não apareceu defeito que impeça a avaliação.
RNF-06 e Q-06 têm de ser ditos aos participantes e na monografia:
a avaliação não os fecha e não autoriza dados reais. A tag e o início
do I9 ficam para o autor.
