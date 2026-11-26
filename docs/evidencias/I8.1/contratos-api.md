# Contratos API — I8.1

Os corpos continuam com campos extra proibidos. As regras de
representação `read` e `manage`, o isolamento entre actores e os
códigos 404 existentes mantêm-se.

## Actor privado

Entram em criação, consulta, resposta de criação e alteração:

  coverage_area: string ou null

Omissão na criação grava null. Omissão na alteração não mexe no valor.
null na alteração limpa o campo. Texto vazio ou só espaços: 422,
«Área de actuação inválida.».

A localização geral continua no seu campo. Escrever uma não altera a
outra.

## Produto privado

Entram na resposta:

  image_ref: string ou null
  image_use_confirmed: boolean

Criação:

  image_ref, opcional, null por omissão
  image_use_confirmed, boolean, false por omissão

Alteração: os dois campos só são aplicados se vierem no corpo.
Confirmar sem fotografia: 422, «A declaração de direitos exige uma
fotografia.». Referência que não seja HTTPS válido: 422,
«Referência de imagem inválida.». O valor submetido não é repetido.

`image_use_confirmed` é verdadeiro só quando a referência gravada
coincide com a referência declarada e existem instante e conta.
A resposta não inclui `image_rights_declared_by` nem
`image_rights_declared_at`.

Arquivar não altera a referência nem a declaração.

## Oferta pública

`product` passa a incluir `image_ref`. É o URL HTTPS quando a
declaração dessa referência é válida. É null quando não há fotografia,
quando a declaração falta ou quando a referência não é HTTPS.
A chave existe nos dois casos. O URL não autorizado não aparece.

`producer` passa a incluir `coverage_area`, string ou null.
Não se acrescentam identificadores internos do actor, da conta ou da
declaração.

A consulta pública não selecciona `image_rights_declared_by`.
O predicado de elegibilidade, a paginação, o isolamento e
`Cache-Control: no-store` mantêm-se. Oferta em rascunho, suspensa,
retirada, ou produto arquivado, continua 404. Oferta publicada
indisponível continua visível, com a fotografia sujeita às mesmas
condições.

O filtro `location` compara só `general_location`. Não há filtro de
área de actuação.

## Interface

O cliente público rejeita a oferta inteira se `image_ref` não for null
e não passar na mesma verificação HTTPS, feita em memória. Não pede o
endereço.
