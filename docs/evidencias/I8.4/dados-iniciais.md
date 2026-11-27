# Dados iniciais da avaliação — I8.4

O conjunto é sintético. Não reproduz participantes da FACIM nem do
inquérito inicial. Não é um resultado da investigação. Os nomes e os
contactos estão no domínio reservado `avaliacao.example` ou usam o
indicativo fictício `+999`.

As palavras-passe não estão neste ficheiro. Ficam em `.env.avaliacao`,
nas variáveis `AVALIACAO_PASSWORD_PRODUTOR`,
`AVALIACAO_PASSWORD_COMPRADOR` e `AVALIACAO_PASSWORD_CONSULTA`.
O comando `preparar` lê-as e não as imprime.

O participante não fica limitado a estes registos. Com a conta de
produtor pode criar actores, produtos, ofertas e contactos. A conta
de comprador entra e gere o seu próprio actor, sem papel de produtor.
A conta de consulta vê o actor produtor e não o altera.

## Contas

Criadas por `python -m app.create_user` no contentor da API de avaliação.

| Conta | Email | Papel no cenário |
| --- | --- | --- |
| Produtor | `produtor@avaliacao.example` | Representação `manage` do actor produtor |
| Comprador | `comprador@avaliacao.example` | Representação `manage` do actor comprador |
| Consulta | `consulta@avaliacao.example` | Representação `read` do actor produtor |

A representação `read` não tem endpoint de concessão. `preparar`
insere a linha em `user_actor_access` depois de as duas contas e o
actor existirem. É o mesmo mecanismo usado pelos testes para uma
representação que a API não concede a terceiros.

## Actores

Organização «Cooperativa Sintética da Avaliação», localização
«Localidade fictícia de demonstração», área de actuação
«Área sintética de demonstração», papel `producer`.

Pessoa «Comprador Sintético da Avaliação», localização
«Outra localidade fictícia», papel `buyer`. Não publica ofertas.

## Produtos e ofertas

«Tomate de demonstração», categoria hortícola, com referência HTTPS
e declaração de uso. Oferta publicada: 120.00 MZN, 10 kg, disponível,
condições «Recolha na localidade fictícia. Não inclui transporte.»

«Feijão de demonstração», categoria leguminosa, sem fotografia.
Oferta em rascunho, incompleta, fora da pesquisa pública.

A referência da fotografia é
`https://upload.wikimedia.org/wikipedia/commons/8/89/Tomato_je.jpg`,
ficheiro `Tomato_je.jpg` no Wikimedia Commons. Não é fotografia de
produtor nem material da FACIM. Durante a preparação, o anfitrião
não respondeu a uma consulta da licença, por isso a licença não fica
aqui afirmada. Confirmar a linha do ficheiro no Commons antes de
reproduzir a imagem na monografia. A aplicação não descarrega o
ficheiro. Se o anfitrião falhar, a ficha pública permanece e o
componente omite a imagem.

## Contactos

Telefone `+99955501001`, privado, sem autorização.

Email `contacto.sintetico@avaliacao.example`, com autorização vigente
de finalidade `commercial_discovery` e aviso `v1`.

Não há contactos reais. Não há importação da FACIM.

## O que o smoke acrescenta, e o que a reposição tira

`verificar` cria um produto e uma oferta que percorre publicar,
suspender e retirar, e um contacto que é autorizado e depois revogado.
Essas linhas ficam, porque o protótipo não apaga histórico.
`repor -Confirmar` seguido de `preparar` volta ao conjunto desta nota,
com identificadores novos. Foi o estado deixado no fim do I8.4.

O ficheiro `scripts/avaliacao-dados.json` é a mesma descrição, em
forma que o script lê. Não contém palavras-passe.
