# Consistência transaccional — I8.2

## O que passou a estar fechado na transição

`publish_offer`, `suspend_offer` e `withdraw_offer` bloqueiam a linha
da oferta e pedem ao SQLAlchemy que substitua o objecto já carregado.
Só depois leem o estado, a representação e o papel de produtor. O
estado novo e o evento entram no mesmo savepoint.

O teste de concorrência abre duas sessões. A primeira publica e segura
a transacção. A segunda fica à espera do bloqueio da linha `offers`.
Quando a primeira confirma, a segunda vê `published`, é recusada e não
deixa evento. O estado final e o único evento coincidem:
`draft` para `published`.

## O que se mantém

O commit continua síncrono, no momento em que a resposta HTTP vai
começar. Foi a decisão do I5 para o pedido seguinte não ver 404. Não
se tornou a stack assíncrona.

O isolamento continua `READ COMMITTED`. Não se passou a
`SERIALIZABLE`.

Depois do bloqueio da oferta, a linha de representação deste operador
também é bloqueada e relida. Uma revogação que actualize essa linha
espera pelo fim da transição, ou a transição espera e passa a ver o
acesso já revogado. Isto vale só para publicar, suspender e retirar.
As outras escritas continuam a ler a representação no início do pedido.
Não houve uma corrida reproduzida fora deste caminho. Não se alargou
o bloqueio a todas as escritas.

O mapa de identidade fica controlado na transição da oferta porque a
leitura de bloqueio pede `populate_existing`. Uma leitura futura de
outro recurso, se carregar o objecto sem bloqueio e só depois o
bloquear, volta a ter o problema. Os contactos continuam a fazer a
primeira leitura já com `FOR UPDATE`.

Arquivar o produto, perder o papel de produtor ou inactivar o actor
não criam evento de oferta: o estado da oferta não muda. A consulta
pública deixa de a mostrar pelas regras já existentes.
