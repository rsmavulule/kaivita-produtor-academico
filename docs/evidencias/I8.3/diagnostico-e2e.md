# Diagnóstico E2E — I8.3

Fontes: evidência I8.0, I8.1 e I8.2, e as execuções desta ronda.
Não se atribui causa sem o estado observado. A produção não foi alterada.

## Logout antes de novo login (`contacts.spec.ts`, desactivação)

No I8.2 o teste esgotou a espera de `#email` depois de «Terminar sessão».
O logout de produção já apaga o cookie e redirecciona para
`/login?motivo=terminada`. O middleware não tira de `/login` quem ainda
tem sessão. O teste chamava `login()`, que faz `goto("/login")`, antes
de esse redirect terminar. Com o cookie ainda válido, a página ficava
em `/inicio`.

Causa: sincronização do teste. O spec de autenticação já esperava o
URL e o estado «Sessão terminada neste browser.» Este teste não esperava.

## Visitante e ciclo da oferta (`contacts.spec.ts`, elegibilidade)

No I8.2, depois de «Republicar», o email não aparecia ao visitante: a
oferta ainda estava suspensa quando o outro browser carregava em
«Ver contactos». O botão de transição fica «A publicar…» enquanto a
acção não termina. Há dois `p.eyebrow` (cabeçalho «Sessão» e o estado).

Causa: sincronização do teste. A acção de produção já muda o estado e
redirecciona. Faltava esperar o estado visível no browser do produtor.

## Visitante e revogação (`contacts.spec.ts`, contacto depois da acção)

Intermitente no I8.0 e no I8.1. Passou no I8.2. O visitante consultava
antes de o valor gravado, ou de «Sem autorização vigente», estar visível
no browser do produtor.

Causa: a mesma sincronização, não um defeito estável da ocultação.

## Oferta de outro actor (`offers.spec.ts:292`)

`createOfferAction` permanece no formulário e mostra «Produto não
encontrado.» quando o produto não pertence ao actor. Não há redirect
para a lista. O URL `/ofertas/nova` já é verdadeiro antes de a acção
acabar, por isso a expectativa do alerta disparava com o fallback ainda
montado.

No I8.1 a lista ficou em «A carregar as ofertas.» Uma repetição isolada
passou. No I8.2 a suite completa passou. Nesta ronda, nas três repetições
do quarteto: a segunda passou; a terceira ficou sem `p.alert` durante
20 s, depois de o URL `/ofertas/nova` já ter sido aceite, com o segmento
das ofertas ainda no fallback «A carregar as ofertas.» A primeira
repetição não conta: o servidor em 3100 foi terminado a meio.

Causa não demonstrada como defeito funcional. O sintoma observado é o
fallback de carregamento, não uma mensagem errada. Depois dessa
repetição, o teste espera o POST de criação com estado inferior a 500
e o desaparecimento de «A carregar as ofertas.» antes de afirmar
`p.alert`. A asserção da mensagem mantém-se. Não se aumentou o timeout
de 20 s nem o de 90 s. As duas suites completas passaram com essa espera.

## Execução contaminada

Uma suite completa arrancou enquanto `next build` escrevia o mesmo
`.next`. O servidor perdeu `routes-manifest.json` e respondeu
`MODULE_NOT_FOUND`. Foram 11 aprovações e 3 falhas antes de se
interromper. Não é resultado funcional.

Outra repetição do quarteto perdeu a ligação a `127.0.0.1:3100` porque
o `next dev` foi terminado durante o teste. Também não conta como falha
da aplicação.
