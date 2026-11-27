# Notas da versão candidata v1.0.0-rc.1

Identificação proposta: `v1.0.0-rc.1`.
Commit de base: `ba62f255cef623cc7df4e25bf2b1e2cc82e2fd28` em `main`.
Não foi criada tag Git. A tag fica para o autor, depois de aprovar e
versionar o I8.4.

Esta identificação é o candidato à avaliação académica. Não é a versão
final avaliada. Essa conclusão só pode existir depois do I9.

## Funcionalidades incluídas

Conta criada localmente, sessão no servidor Next.js, actores com papéis
comerciais e representação, produtos com fotografia opcional e declaração
de direitos, ofertas em rascunho, publicada, suspensa e retirada,
pesquisa pública, contactos privados e divulgação revogável, área de
actuação, histórico de autorizações e eventos das transições de oferta.

Não inclui registo público, recuperação de palavra-passe, backoffice,
encomendas, pagamentos, frete nem armazenamento de imagens.

## Arquitectura e tecnologias

Três processos no Compose: Next.js 15.5.29, FastAPI, PostgreSQL 16.
SQLAlchemy 2 síncrono. Alembic até `0008_offer_status_events`.
Palavras-passe em Argon2id. Sessão em cookie `HttpOnly`. O browser não
recebe o JWT.

## Requisitos

27 requisitos numerados da SRS v1.1: 26 validados e 1 parcial.
O parcial é RNF-06. Q-06 permanece parcialmente aberta e fora dessa
contagem. A matriz está em `matriz-rastreabilidade-final.md`.

## Testes

Herdados do I8.3, no mesmo commit de produção: 280 testes de backend
em duas execuções e 68 testes Playwright em duas execuções consecutivas.
Build Next.js aprovado no I8.3. Total então registado: 348 testes
automatizados. O I8.4 não os repetiu. Não alterou código de produção,
testes nem a configuração que esse resultado mediu.

O smoke deste candidato está em `smoke-test-resultados.txt`.

## Migração

Cabeça única: `0008_offer_status_events`. O contentor da API aplica
`alembic upgrade head` no arranque. A base de avaliação foi confirmada
nessa revisão, inclusive depois de recriar o volume.

## Limitações

RNF-06, Q-06, texto livre, fotografias externas, soft 404, concorrência
residual, desempenho só observado em laboratório, sem produção e sem
avaliação com utilizadores. Detalhe em `limitacoes-finais.md`.

## Execução

`docs/evidencias/I8.4/guia-operacional.md`.
Ambiente local, portas 5436, 8020 e 3020, volume próprio.
Não publicar na Internet sem autorização expressa.

## Condições para a avaliação académica

Usar o ambiente de avaliação, não a base de desenvolvimento.
Usar as contas sintéticas e deixar os participantes criar dados novos.
Não introduzir contactos ou fotografias reais sem autorização específica.
Não tratar as respostas do I9 como se já estivessem recolhidas.
Não afirmar que o protótipo melhorou o escoamento.
Conservar o volume ou um backup se os dados introduzidos durante o I9
tiverem de ser revistos. O instrumento de recolha da investigação fica
fora desta base.
