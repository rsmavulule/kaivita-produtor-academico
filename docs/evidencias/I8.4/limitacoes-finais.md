# Limitações finais — I8.4

Não há defeito bloqueador para o I9. As limitações abaixo são aceitáveis
no protótipo académico, desde que a avaliação use dados sintéticos e o
texto da monografia não as apresente como conformidade completa.

## Parcial numerado

RNF-06 permanece parcial. A projecção pública é mínima, a autorização
tem finalidade e aviso, e a revogação oculta o contacto. Falta o
calendário de retenção pedido pela secção 10 antes de dados reais.
O texto livre e a fotografia podem conter dados pessoais, e a aplicação
não os detecta. Não se classificou RNF-06 como validado.

## Questão fora dos 27

Q-06 permanece parcialmente aberta, como na SRS: a política preliminar
existe e os prazos legais não estão confirmados. Não entra no
denominador. A nota `docs/evidencias/I8.2/retencao-q06.md` é proposta,
não decisão.

Q-07, a documentação da concordância do supervisor, também não é
requisito numerado e não foi tratada aqui.

## Texto livre e dados pessoais

Os formulários avisam que nome, localização, área de actuação, produto,
condições de entrega e endereço da fotografia podem ficar públicos.
Não há filtro heurístico. A avaliação I9 deve usar só os dados
sintéticos, ou dados que o participante introduza sabendo desse aviso.
Não reutilizar contactos ou fotografias reais sem a autorização
específica pedida pela SRS.

## Fotografias externas

A aplicação guarda um URL HTTPS e não o ficheiro. O browser pede a
imagem ao anfitrião, com `referrerPolicy=no-referrer`. Se o anfitrião
falhar, a ficha continua e a imagem é omitida. A declaração é do
representante. Não há análise de pessoas ou de texto dentro da imagem.
A referência de demonstração é um ficheiro do Wikimedia Commons cuja
licença não foi reconfirmada nesta preparação, porque o anfitrião não
respondeu.

## Soft 404

`GET /public/offers/{id}` de uma oferta inexistente ou inelegível
responde 404. A página `/ofertas/[offerId]` responde HTTP 200 com
«Oferta não encontrada.» Confirmado no smoke: API 404, interface 200,
texto presente. É qualidade da ficha, não requisito numerado. Não foi
corrigido. Não impede o percurso principal.

## Concorrência residual

Pedidos sequenciais respeitam a representação. Nas transições de oferta
há bloqueio da linha e releitura da representação, desde o I8.2.
Continua possível uma corrida entre a revogação de acesso e uma escrita
já iniciada noutro pedido, no sentido registado no I8.0. Não se observou
esse defeito no smoke. Não é bloqueador.

## Desempenho observado

A SRS não fixa segundos nem utilizadores simultâneos. A medição do I8.3,
um cliente e 21 ofertas, ficou com medianas à volta de 22 ms em
`GET /public/offers`, relógio que inclui o arranque do `curl`. Não é
teste de carga e não cria limiar. Não se mediu de novo.

## Fora de produção e fora de utilizadores

Não houve implantação pública nem validação em produção. Não houve
avaliação empírica. O I9 é que a faz. Este candidato não é a versão
final avaliada.

## Outros limites já aceites

Terminar a sessão não revoga o JWT. O Compose local não usa TLS.
Não há registo público, recuperação de palavra-passe, backoffice,
frete, encomendas nem pagamentos. O papel de produtor não é um `CHECK`
da base. Uma autorização cobre um contacto de cada vez.

Nada disto foi corrigido neste incremento. São limites do âmbito, não
falhas que impeçam a demonstração académica.
