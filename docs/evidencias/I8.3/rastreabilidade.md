# Rastreabilidade — I8.3

Fontes: SRS v1.1, secção 7, a matriz do I8.0 e o fecho do I8.2.
A SRS e os diagramas não foram alterados. Há 27 requisitos numerados.

## O que muda nesta ronda

RNF-02. Texto: mensagens de erro claras, campos obrigatórios
identificados, navegação acessível por teclado.

No I8.0 estava implementado e não validado, por faltarem os percursos
de produto, oferta e contacto. Esses três percursos passaram isolados
e nas duas suites completas. Os testes de viewport anteriores mantêm-se.

Classificação proposta: validado para o texto da SRS. Não é conformidade
WCAG. A SRS não a pede.

## O que fica como no I8.2

RNF-06: parcial. Texto livre e Q-06 continuam abertos. A query já tinha
saído do access log.

RNF-07: validado no âmbito do protótipo académico, com o limite já
registado no I8.2.

RNF-01: validado para o critério escrito de 360 px e 1280 px. Esta ronda
não mediu tempo de interface nem reclassificou o requisito. A SRS não
tem limiar numérico de desempenho.

Os restantes requisitos numerados não foram reabertos. A contagem passa
de 25 validados, 1 implementado não validado e 1 parcial, para
26 validados e 1 parcial (RNF-06).

## Fora da SRS

O soft 404 da ficha pública continua em HTTP 200 com a mensagem de
oferta indisponível. É qualidade, não requisito numerado. Não foi
implementado.

A medição de `GET /public/offers` está em `desempenho.md`. Não cria
critério novo e não valida um número que a SRS não escreveu.
