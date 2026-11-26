# Segurança e privacidade — I8.1

## Área de actuação

É texto livre, com o mesmo aviso já usado na localização: pode tornar-se
público numa oferta elegível e não deve levar telefone, correio ou
outros dados pessoais. Não revela o identificador do actor. Actores
sem oferta elegível não ganham ficha pública.

A representação `read` consulta o campo. A representação `manage` é
necessária para o alterar. Outro actor recebe 404, como nos restantes
campos do perfil.

## Referência da fotografia

A validação rejeita, antes de gravar, protocolos que não sejam HTTPS,
URLs malformados, URLs com utilizador ou palavra-passe, e referências
que não possam ser usadas no `<img>`. O backend e o servidor Next.js
não pedem o URL. Não há proxy de imagens, para não abrir um caminho de
SSRF.

A consulta pública omite o URL quando a declaração não cobre essa
referência. Referências históricas que não são HTTPS ficam na ficha
privada e saem como null na oferta pública. O 422 não devolve o texto
rejeitado.

## O que o navegador revela

Com `referrerPolicy="no-referrer"`, o pedido da imagem não leva o
cabeçalho Referer. O anfitrião da imagem recebe na mesma o endereço IP
e o agente do navegador de quem abre a oferta. A disponibilidade e o
conteúdo da imagem dependem desse anfitrião. A aplicação não os
controla. O percurso de teste intercepta `https://example.com` e
confirma Referer vazio; a imagem mostrada na captura é sintética.

Se o carregamento falha, a fotografia sai da página e os outros dados
permanecem. Retirar ou trocar a referência impede que pedidos públicos
seguintes devolvam o URL anterior. Imagens já obtidas pelo navegador
podem continuar na cache local. A aplicação não promete apagá-las.

## Declaração

Regista quem afirmou, quando, e para que referência. A resposta privada
mostra só o boolean. A resposta pública não mostra a conta nem o
instante. A restrição de chave estrangeira impede apagar a conta
enquanto a declaração a citar. A restrição de verificação impede uma
declaração sem referência ou uma declaração de outra referência.

A afirmação não é uma verificação jurídica de direitos de autor, nem
uma análise da imagem. A caixa começa desmarcada e perde o efeito
quando a referência muda ou é retirada.

## O que não foi acrescentado

Não há catálogos públicos de actores ou produtos. A elegibilidade, o
isolamento, a paginação e `Cache-Control: no-store` mantêm-se. Não há
filtros novos. Não há mapas nem geolocalização. Não há importação de
fotografias da FACIM.
