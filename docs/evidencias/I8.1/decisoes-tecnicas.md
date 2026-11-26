# Decisões técnicas — I8.1

## Área de actuação

A SRS, na secção 3, trata `coverage_area` como eventual, ao lado de
`general_location`. RF-01 exige o atributo no perfil. A coluna é texto
anulável. Vazio ou só espaços é rejeitado com «Área de actuação
inválida.». O valor aceite não é cortado nas pontas, como a localização
geral. Não há comprimento máximo novo: os outros textos do actor também
não o têm.

A migração não preenche a coluna a partir da localização. Limpar a área
na edição grava NULL e deixa `general_location` intacto.

## Fotografia

Continua a ser `products.image_ref`. Não há upload, ficheiro, CDN nem
pedido HTTP do backend ou do Next.js para o endereço.

Na escrita, a referência tem de ser um URL HTTPS absoluto, com anfitrião,
sem credenciais, sem barra invertida e sem espaços ou caracteres de
controlo. O tecto é 2048 caracteres, porque uma referência não é um
texto livre como o nome. Protocolos como `javascript:` e `http:`, e
textos que não são URL, são rejeitados. A mensagem é «Referência de
imagem inválida.» e o valor rejeitado não volta no corpo.

Valores antigos que não são HTTPS permanecem na base e na consulta
privada. Não entram na resposta pública. Confirmá-los sem os substituir
é recusado.

## Declaração

Três colunas no produto, ligadas pela restrição
`ck_products_image_rights`: referência declarada, instante e conta.
As três andam juntas e a referência declarada tem de ser a fotografia
gravada. Não se reutiliza `PublicationAuthorization`: esse mecanismo
regista versões e revogações de contactos. RB-08 pede uma afirmação
mínima ligada à fotografia indicada.

A API privada expõe só `image_use_confirmed`. O identificador da conta
e o instante ficam na base. Repetir a confirmação da mesma referência
conserva o instante original. Mudar ou retirar a referência apaga as
três colunas. Uma referência nova no mesmo pedido só fica declarada se
a confirmação vier nesse pedido.

A caixa começa desmarcada. Fica desactivada enquanto o campo está
vazio e desmarca-se quando o texto deixa de ser a referência já
confirmada.

## Apresentação pública

`public_image_ref` devolve o URL só quando a oferta já passou o
predicado público existente, a referência é HTTPS válida e a declaração
aponta para essa referência. Caso contrário o campo público `image_ref`
é null. A oferta continua consultável. A pesquisa continua a filtrar
`general_location`, nome e descrição. Um parâmetro `coverage_area` é
rejeitado. Não há catálogo separado de actores ou produtos.

O navegador pede a imagem com `<img referrerPolicy="no-referrer">`.
`next/image` faria o servidor pedir o URL. Não há proxy.

A regra `.product-photo { display: block }` ganha à folha de estilos
do atributo `hidden`, por isso uma imagem em falha é retirada da
árvore em vez de receber esse atributo. O erro pode ocorrer antes da
hidratação, quando `onError` ainda não está ligado. Depois de montar,
se `complete` é verdadeiro e `naturalWidth` é 0, o componente sai.
O resto da ficha permanece. Uma imagem já carregada pelo navegador
não é apagada da cache dele.

## Ordem das colunas

As colunas novas ficam no fim dos modelos. O PostgreSQL acrescenta
colunas no fim e os testes de esquema comparam essa ordem com o modelo.
O comentário de `image_ref` mantém o texto da migração 0003, porque o
mesmo teste compara comentários.
