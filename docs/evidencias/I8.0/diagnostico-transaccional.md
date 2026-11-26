Diagnóstico transaccional — I8.0

Fontes de código: backend/app/db.py, contacts.py, publication.py,
offers.py, products.py, actor_roles.py, accounts.py.
Fontes históricas, não alteradas: evidências de I4, I5.5, I7.1 e I7.2.
Nesta ronda não se escreveu um teste novo nem se reproduziu uma corrida
nova. O que não foi executado não é classificado como defeito observado.

Commit e sessão

CommitBeforeResponse, em backend/app/db.py, confirma a sessão síncrona
quando o ASGI está prestes a enviar http.response.start. O gerador
get_session confirma outra vez se a transacção ainda estiver aberta, e
faz rollback se o pedido falhar. Os testes de test_commit_order.py e
test_commit_visibility.py, e os de contactos e autorizações, passaram
nesta ronda: 266 no total.

Limitação aceite. O commit é síncrono dentro do ciclo ASGI. Foi a
decisão do I5 para o pedido seguinte não ver 404. Não se propõe tornar
a stack assíncrona. Não é um defeito observado.

Isolamento. A sessão usa o isolamento por omissão do PostgreSQL, READ
COMMITTED. Uma consulta iniciada depois do commit vê a revogação. Uma
instrução que já tenha o seu snapshot pode ver o estado anterior. O
I7.2 registou que não foi deixado um cursor aberto a atravessar o
commit de outra sessão. Esta ronda também não o fez. Continua risco
potencial, não defeito reproduzido. Não se propõe SERIALIZABLE.

Savepoints e unicidade

Criações e alterações que podem violar unicidade fazem flush dentro de
begin_nested. A concessão de autorização e a passagem do contacto a
public partilham um savepoint. A alteração efectiva revoga e muda o
contacto no mesmo savepoint. A desactivação revoga e marca inactive
antes de um flush único. Os testes de duplicado e de rollback passaram.

Bloqueios

Ordem actual, descrita no I7.2 e visível no código: a linha do contacto
com FOR UPDATE e, em seguida, a autorização vigente. Concessão,
revogação, alteração e desactivação seguem essa ordem. Os testes de
test_publication_concurrency.py passaram. Não se observou deadlock
nesta ronda; a evidência de ausência de deadlock é a do I7.2, não uma
medição nova.

Ofertas e produtos não usam FOR UPDATE. Duas transições concorrentes
podem ler o mesmo estado e ambas passarem a verificação em Python. O
I4 já o registou. Não há, nas suites, um teste que tenha gravado dois
estados finais contraditórios. É risco potencial. Correcção proporcional,
se for aceite no I8.2 ou no I8.3: bloquear a linha da oferta no início
da transição e reavaliar o estado depois do bloqueio. Não é motivo para
redesenhar a sessão.

Representação. O acesso é lido antes do bloqueio do recurso. Uma
revogação de representação confirmada nesse intervalo não é reavaliada.
Está documentada desde o I4 e repetida no I7.1 e no I7.2. Não foi
reproduzida como escrita aceite depois de revogação nesta ronda. Risco
potencial, não defeito observado. Correcção proporcional: repetir a
verificação de representação dentro da mesma transacção, depois do
bloqueio da linha que vai ser escrita. Prioridade P2. Não é P0: não há
exploração demonstrada e a janela é a de dois pedidos sobrepostos.

Mapa de identidade

Se a mesma sessão ler a autorização sem FOR UPDATE e só depois a
bloquear, o objecto antigo pode ser reutilizado e uma revogação já
confirmada por outra transacção pode ser reescrita. O I7.2 provocou
isto com um helper de teste e removeu esse helper. Os pedidos actuais
não fazem essa leitura prévia. O código de produção não foi alterado
desde então. Risco potencial condicionado a uma leitura futura. Não é
defeito actual. Não se mexe no código só por esta hipótese. Qualquer
leitura nova da autorização tem de ser a leitura de bloqueio.

Visibilidade

Autorização, revisão e visibilidade pública são uma instrução SQL no
caso dos contactos de uma oferta. A elegibilidade da oferta e a
autorização vigente são avaliadas juntas. Não há segunda leitura que
publique um contacto de uma oferta já inelegível dentro dessa instrução.
Entre dois pedidos, READ COMMITTED aplica-se como acima.

Oferta, produto e actor. A chave estrangeira composta impede que o
dono da oferta e o dono do produto divirjam. A elegibilidade pública
exige oferta published, produto active, actor active e papel producer.
Arquivar o produto não muda o estado da oferta; tira-a da consulta.
Perder o papel producer também. Estes comportamentos têm testes de API
aprovados nesta ronda.

O papel producer é exigido pela API e não por um CHECK na base. Um
INSERT directo pode criar uma oferta sem esse papel. A API recusa.
Limitação aceite desde o I4. Prioridade P3. Não se acrescenta um
trigger só por simetria, salvo decisão explícita.

Classificação usada

Defeito reproduzido nesta ronda: nenhum transaccional.
Risco potencial: revogação de representação entre a leitura e o commit;
transições de oferta sem bloqueio de linha; cursor já aberto em READ
COMMITTED; mapa de identidade se uma leitura sem bloqueio for
introduzida.
Limitação aceite: commit síncrono; READ COMMITTED; papel producer só
na API; histórico de autorização sem o valor do contacto.
