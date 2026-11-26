# Rastreabilidade — I8.1

Fontes: SRS v1.1, secções 3, 5, 6 e 10, e o diagnóstico I8.0
(`lacunas-funcionais.md`, `matriz-rastreabilidade-integral.md`).
A SRS e os diagramas UML não foram alterados.

## RF-01

Texto: criar, consultar e actualizar o perfil do actor com papel
produtor, incluindo pessoa ou organização, localização geral e área
de actuação. A secção 3 admite `coverage_area` eventual e dispensa o
CRUD de delegações.

Estado depois do I8.1: o atributo existe, é distinto de
`general_location`, entra na criação, consulta e alteração privadas,
aparece na ficha pública da oferta elegível e tem testes de API e o
percurso de interface. Não há mapa, coordenadas nem filtro novo.

Classificação proposta para revisão: validado no âmbito do protótipo.
O diagrama de classes continua sem o atributo. Actualizá-lo fica fora
deste incremento.

## RF-02

Texto: criar, editar, arquivar e consultar produtos do actor produtor,
com nome, categoria, descrição e fotografia opcional.

Estado depois do I8.1: a fotografia opcional continua em `image_ref`,
agora validada como referência HTTPS, editável na ficha privada e
consultável na oferta pública quando RB-08 o permite. A ausência da
fotografia não impede publicar a oferta. Não há armazenamento de
ficheiros.

Classificação proposta para revisão: validado no âmbito do protótipo,
em conjunto com RB-08.

## RB-08

Texto: fotografias só são publicadas com declaração de direito de uso.
As fotografias da FACIM não são importadas automaticamente.

Estado depois do I8.1: a publicação exige declaração persistente da
referência efectivamente indicada. Sem declaração, a oferta segue sem
fotografia. Não existe importação da FACIM. A declaração é a afirmação
do representante. A aplicação não verifica a titularidade, não
inspecciona pessoas identificáveis e não lê contactos impressos na
imagem. Esses limites estão na secção 10 e ficam explícitos em
`seguranca-privacidade.md`.

Classificação proposta para revisão: validado no âmbito do protótipo,
com os limites da secção 10 por cumprir de forma automática.

## Casos de uso

UC-02 passa a incluir a área de actuação no perfil. O acesso negado
já estava validado e mantém-se.
UC-04 passa a incluir a fotografia opcional e a declaração. O
isolamento do produto já estava validado e mantém-se.

## Fora deste fecho

RF-04 continua a pesquisar a localização geral. RNF-06 e RNF-07
permanecem como no I8.0. I8.2, I8.3, I8.4 e I9 não foram iniciados.
