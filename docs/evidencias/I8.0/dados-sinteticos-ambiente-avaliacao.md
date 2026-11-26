Dados sintéticos e ambiente de avaliação — I8.0

Não se eliminou qualquer linha. Não se criou base nova.

Leitura depois do pytest e, de novo, depois do Playwright. As contagens
coincidiram.

  users                         55
  padrão sintético i5* ou i73   49
  outras contas                  6
  actors                       173
  products                      92
  offers                        40
  public_contacts                0
  publication_authorizations     0

O padrão, ligado por user_actor_access, alcança 165 actores, 38 ofertas
e 185 representações. É o mesmo conjunto residual descrito no I7.3.
Há 8 actores e 2 ofertas que não entram nessa ligação. O prefixo de
email não prova que todos os recursos associados pertençam a execuções
de teste, nem que os 6 contas restantes sejam de teste. Os emails não
são listados.

As 12 contas de uma execução Playwright, quando a limpeza conclui,
não permanecem. Nesta ronda as contagens finais igualaram as iniciais,
incluindo zero contactos e zero autorizações. A limpeza não fez
TRUNCATE. O comportamento está em frontend/e2e/cleanup.ts e foi
descrito no I7.3. Esta ronda não o alterou.

A base em 5435 é a base de desenvolvimento. Mistura resíduos de
execuções antigas com o que a aplicação acumula. Não serve, tal como
está, de ambiente estável para avaliadores: o catálogo público pode
mostrar ofertas de testes anteriores, e uma limpeza por prefixo seria
insegura.

Proposta, para o I8.4, sem a implementar agora

Base dedicada, outro nome e outra porta, criada vazia. O volume do
Compose de desenvolvimento não é reutilizado.

Inicialização só por alembic upgrade head, até
0006_publication_authorizations ou a cabeça que existir no fim do I8.

Dados sintéticos controlados, num script ou numa migração de dados
explicitamente marcada como avaliação, não como esquema. Conteúdo
mínimo: duas contas de demonstração, dois actores produtores, papéis,
um produto, uma oferta publicada elegível, um contacto privado e um
contacto com autorização. Textos sem telefones nem emails reais. Os
emails de demonstração ficam num domínio reservado, documentado, e
não se confundem com o padrão i5/i73 da suite automática.

A suite Playwright e o pytest continuam na base de desenvolvimento,
ou numa base descartável, nunca na base de avaliação. Assim a limpeza
dos testes não apaga as respostas da avaliação.

Reposição: apagar e recriar essa base, voltar a aplicar migrações e o
conjunto sintético. Não se restaura a partir da base de desenvolvimento.
Não se copiam as 49 contas residuais.

Isolamento: outra DATABASE_URL, outro volume, portas próprias. A API
e a interface de avaliação são outro projecto Compose, ou o mesmo
ficheiro com um perfil que não publica 5435, 8010 e 3010. A escolha
do mecanismo fica para o I8.4; o critério é não partilhar o volume
pgdata actual.

Preservação do I9: as respostas, notas e consentimentos de participação
não entram nesta base. Ficam fora do repositório de código se contiverem
dados pessoais, e num registo separado se forem sintéticos ou
codificados. O protótipo não é o instrumento de arquivo da investigação.

Contas de demonstração: credenciais só no ambiente local de avaliação,
no mesmo regime do .env actual, fora do Git. Não se documentam senhas
nas evidências.

Esta proposta não é um requisito da SRS. É condição prática para o I9,
descrita em criterios-release-candidate.md e no relatório.
