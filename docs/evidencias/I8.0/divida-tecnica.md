Dívida técnica — I8.0

Obrigatória para o I8, ainda não corrigida

Teste temporal. backend/tests/test_publication.py, função
test_postgres_rejects_invalid_authorizations.

O I7.3 substituiu revoked_at de 2026-11-25T12:00:00Z por
2099-01-01T00:00:00Z na linha histórica que o teste espera conseguir
inserir. O CHECK ck_publication_authorizations_revocation exige
revoked_at >= granted_at. granted_at é o instante da inserção. Em ou
depois de 2099-01-01T00:00:00Z, a inserção volta a falhar. Os outros
casos do mesmo teste que usam datas antigas continuam a ser rejeições
esperadas e não têm o mesmo problema.

Correcção, no I8.3, sem mudar a produção: depois de inserir a linha
vigente, ler o granted_at efectivo e inserir a linha histórica com
revoked_at posterior a esse instante, por exemplo o próprio granted_at
ou granted_at mais um intervalo. Em alternativa, um relógio injectado
no teste. Não usar outra data constante no futuro.

Prioridade P2. Não é defeito de produção. É dívida obrigatória porque
a suite deixa de ser reproduzível numa data conhecida.

Dívida de teste observada nesta ronda

Corrida de logout em contacts.spec.ts, linha 89. Reproduzida duas
vezes. O teste de auth.spec.ts que espera o URL de logout passou.
Prioridade P2. Incremento I8.3.

Instabilidade da consulta do visitante depois de suspender, republicar
ou revogar, no mesmo spec. O ponto de falha não se manteve na
repetição. Prioridade P2. A espera deve ser pelo estado confirmado no
browser do produtor, não por um timeout maior.

Arranque do Playwright dependente da ausência de proxy para
127.0.0.1. Prioridade P2 de ambiente. O procedimento está em
diagnostico-testes.md. Não se altera a configuração versionada nesta
ronda.

Chromium 1255 ausente da cache persistente do utilizador. Prioridade
P2 de ambiente. A instalação desta sessão ficou na cache temporária
indicada por PLAYWRIGHT_BROWSERS_PATH.

Dívida de produto já classificada na matriz

RF-01 sem área de actuação. P1. I8.1.
RF-02 e RB-08 sem declaração nem referência pública. P1. I8.1.
RNF-07 sem eventos de publicação de oferta. P1. I8.2.
RNF-06 parcial: texto livre, access log com query, retenção por
confirmar. P2 para o log. Q-06 para a retenção.
RNF-02 sem evidência de teclado em todos os formulários essenciais.
P2. I8.3.
Soft 404 nas páginas de oferta. P2. I8.3.
README desactualizado sobre a interface de contactos. P3.

Riscos potenciais que não são defeitos observados

Transições de oferta sem FOR UPDATE. P2.
Revogação de representação entre a leitura e o commit. P2.
Mapa de identidade se uma autorização for lida antes do bloqueio. P3,
vigilância, sem alteração agora.
Papel producer não imposto pela base. P3.

Limitações aceites

Commit síncrono. READ COMMITTED. Logout sem revogação do JWT.
HTTP local sem TLS. Sem registo público, sem recuperação de
palavra-passe, sem refresh token. Sem reactivação de produto arquivado
nem de oferta retirada. Sem eliminação física de contacto. Histórico
de autorização sem o valor antigo. Página já aberta até nova consulta.
