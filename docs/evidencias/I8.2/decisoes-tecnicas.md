# Decisões técnicas — I8.2

## Evento de oferta

`OfferStatusEvent` regista só a transição efectiva: oferta, estado
anterior, estado novo, conta e instante. Não há cópia de preço,
quantidade, textos ou contactos. A criação do rascunho não gera evento,
porque ainda não houve transição. Ofertas já existentes não recebem
eventos inventados.

A republicação é a publicação a partir de `suspended`. O estado
anterior distingue-a da primeira publicação. A retirada a partir de
rascunho, publicada ou suspensa também fica registada, porque o estado
mudou.

Não há endpoint de consulta, alteração ou eliminação. A demonstração é
a tabela e os testes. `PublicationAuthorization` continua a ser o
histórico dos contactos e não foi duplicado.

## Mesma transacção e bloqueio

A mudança de estado e o evento são gravados no mesmo savepoint. Se a
escrita do estado falha, o evento não fica. Se a transição não é
válida, a função sai antes de escrever qualquer dos dois.

A oferta é lida com `FOR UPDATE` e `populate_existing`. A segunda opção
existe porque o SQLAlchemy pode já ter o objecto em memória: sem ela,
o bloqueio esperaria pela outra transacção e o programa continuaria a
ver o estado antigo. A representação `manage` e o papel de produtor são
relidos depois do bloqueio. Não há bloqueio global.

Repetir uma transição que o contrato recusa não cria segundo evento.
Não há operação idempotente que grave o mesmo estado duas vezes.

## Logs

O access log da API deixa de usar o caminho completo do Uvicorn. A
query é retirada. Um segmento que não seja um nome fixo da API nem um
UUID passa a `{omitido}`. O método, o caminho redigido e o estado HTTP
permanecem.

O contentor da base usa `log_error_verbosity=terse` e
`log_min_error_statement=panic`. O erro continua a dizer qual a
restrição. A linha rejeitada e o texto da instrução não entram nesse
log. Quem executa o SQL na consola continua a ver o detalhe no cliente:
isso não é o log do serviço.

O Next.js não escreve o pedido de entrada nem o URL completo dos
fetches. A pesquisa pode ir na query, e esse texto não deve ficar no
log do contentor.

## Texto público e fotografia

Não foi acrescentado um comprimento máximo novo aos textos do actor,
do produto ou da entrega. Os valores observados na base de
desenvolvimento são curtos, o maior com 36 caracteres na descrição.
Um tecto sem número na SRS não identifica um email escrito no meio de
uma frase e poderia recusar texto legítimo. Os controlos que já existem
mantêm-se: texto vazio rejeitado, `image_ref` limitado a 2048 na
escrita, e o aviso nos formulários.

O aviso passa a nomear a área de actuação, as condições de entrega e o
endereço da fotografia, e a dizer que a aplicação não detecta sozinha
dados pessoais nem o conteúdo da imagem.

Um URL de fotografia em IP não global, `localhost` ou `.local` é
recusado. O nome DNS não é resolvido, para o servidor não contactar o
endereço.
