# Segurança e privacidade — I8.2

## Minimização

A projecção pública, a finalidade única dos contactos, a ocultação e a
revogação não foram redesenhadas. O evento de oferta não acrescenta
preço, descrição, contacto nem identificador da conta à resposta HTTP.
A conta que declarou a fotografia continua fora da consulta pública.

O aviso dos formulários de actor, produto e oferta nomeia os campos
que podem aparecer numa oferta elegível, incluindo a área de actuação
e o endereço da fotografia. Diz que a aplicação não reconhece sozinha
dados pessoais no texto nem pessoas ou contactos dentro da imagem.
Não há filtro heurístico.

## Comprimentos

Na base de desenvolvimento, nesta ronda, os máximos observados foram:
nome do actor 32, localização 31, área de actuação sem valor,
nome do produto 20, descrição 36, categoria 10, referência de imagem
10, condições de entrega 31, unidade 2. Não se acrescentou um máximo
novo. Não se truncou nada. `image_ref` continua com o tecto de 2048
na escrita, herdado do I8.1.

## Fotografia

O I8.1 mantém-se: o servidor não pede o URL, o elemento usa
`referrerPolicy="no-referrer"`, a imagem pública exige declaração da
referência actual, e a conta declarante não sai na resposta pública.

Foi recusado o anfitrião local ou o IP que não é global, sem resolver
DNS. HTTPS não elimina o risco restante: um nome público pode apontar
para um servidor que regista o IP e o agente do visitante, e pode
resolver para um endereço privado. Não há proxy nem armazenamento
gerido pela aplicação.

## O que não fica provado

A amostra de logs está em `logs-verificacao.txt`. Não cobre todos os
processos que possam vir a escrever um log no futuro. Q-06 não fica
fechada. Não há conformidade legal integral.
