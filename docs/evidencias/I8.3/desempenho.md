# Desempenho — I8.3

A SRS não define segundos, pedidos por segundo, utilizadores simultâneos
nem disponibilidade em percentagem. O limiar de 500 ms de mediana e 2 s
de máximo, proposto no I8.0, não foi aprovado. Não serve de critério de
aceitação. A duração das suites não é tempo de resposta da aplicação.

## Medição

Ambiente: Compose local, API em `http://127.0.0.1:8010`, PostgreSQL
publicado em 5435, Alembic `0008_offer_status_events`. Um cliente.
Catálogo público no momento: 21 ofertas. Página pedida: `limit=20`.

Operação: `GET /public/offers`. Instrumento: relógio à volta de
`curl.exe` até o corpo terminar, portanto inclui o arranque do processo.
Três aquecimentos e vinte amostras. HTTP 200. Corpo com `items`, `limit`,
`offset` e `total`. Sem nomes de ofertas nesta nota.

Sem filtro (`limit=20`, uma página de 20 num total de 21):

- Aquecimento, ms: 68,1; 23,8; 21,5
- Amostras, ms: 25,3; 21,7; 22,8; 20,1; 21,9; 20,7; 22,8; 19,7; 24,3;
  20,9; 22,4; 20,8; 22,2; 24; 22,3; 22,4; 21,4; 21,1; 23,5; 20,8
- Mínimo 19,7; máximo 25,3; mediana 22,1; média 22,1

Com filtro `q=i83medida` (total 0):

- Aquecimento, ms: 45,2; 23,7; 22
- Amostras, ms: 22,6; 23,6; 22; 22,9; 25,2; 21,6; 22,4; 22,4; 23,3;
  23,9; 23,2; 21,8; 21,8; 26; 22,8; 21,3; 24,1; 22,4; 21,5; 20,1
- Mínimo 20,1; máximo 26; mediana 22,5; média 22,7

## Leitura

Não há limiar normativo para aceitar ou recusar. Os tempos observados
neste volume e neste cliente único ficam registados. Não se optimizou
nada: não havia necessidade demonstrada face a um critério da SRS.

Limites: uma máquina, um cliente, 21 ofertas, sem concorrência. O
relógio inclui o arranque do `curl`. Não é teste de carga. Não mede a
página Next, só a API pública.
