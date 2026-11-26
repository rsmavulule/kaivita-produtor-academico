Qualidade e desempenho — I8.0

A SRS não define segundos, pedidos por segundo, número de utilizadores
simultâneos nem percentagem de disponibilidade. Não se inventam
resultados de medição. Não se fez teste de carga.

O que a SRS pede e o que foi observado

RNF-01. Larguras 360 e 1280 nos fluxos essenciais. Os specs de
autenticação, actores, produtos, ofertas, descoberta pública e
contactos mudam a viewport e, em vários casos, gravam captura. O teste
de autenticação verifica que a entrada e o login cabem. Não há auditoria
de overflow em todos os ecrãs nesta ronda. Classificação: validado para
o critério escrito, com a reserva de que esta ronda não reabriu as
capturas históricas.

RNF-02. Mensagens claras, obrigatórios identificados, teclado. Há
testes de teclado no login, na criação de actor e na pesquisa pública.
Mensagens de 422 são testadas sem eco do valor. Os formulários usam
controlos nativos. Não há percurso de teclado automatizado para
produtos, ofertas e contactos, nem auditoria WCAG. Classificação:
implementado não validado. Métrica proposta abaixo.

Paginação. A API limita limit a 1–50 e offset a 0–1000. A ordenação é
nome normalizado do produto e identificador. O total usa o mesmo
predicado. Testes: test_ordering_pagination_and_bounds e o spec de
paginação. A interface avisa quando o tecto é atingido. Não se mediu
tempo com o volume máximo.

Códigos HTTP

| Situação | API | Página Next em 3010 |
| --- | --- | --- |
| UUID inválido na ficha | 422 | 200, texto «Endereço inválido» |
| Oferta inexistente ou inelegível | 404 | 200, texto «Oferta não encontrada» |
| Pesquisa inválida, por exemplo limit=0 | 422 | 200, alerta de parâmetros inválidos |
| Falha da API | 5xx ou ligação recusada | 200 com alerta e «Tentar novamente»; o spec de falha simulada passou |
| Sem cookie em /inicio | — | 307 para /login |
| Cookie inválido na área privada | 401 em /auth/me | a sessão é terminada; specs de auth passaram |
| Contacto público de oferta inelegível | 404 | o route handler da interface também responde 404 |

Cache-Control: no-store na entrada, na pesquisa e na ficha, observado
nos GET desta ronda. As páginas privadas estão configuradas com
private, no-store. As leituras usam cache: no-store. As ligações
públicas são âncoras, sem prefetch de next/link. Uma página já aberta
não recebe sozinha a revogação; a consulta seguinte vê o estado novo.
Isto está documentado desde o I6.2 e o I7.3 e corresponde ao modelo
de pedido.

O soft 404 da ficha tem impacto de qualidade: um cliente que olhe só
para o código HTTP trata a oferta inexistente como página válida. Não
há requisito da SRS que fixe o código da página. Proposta P2, no I8.3:
a ficha de UUID inválido, oferta inexistente e oferta inelegível deve
usar o estado 404 da página, mantendo a mensagem actual. A pesquisa
inválida pode continuar 200, porque a página de pesquisa existe e o
alerta explica o endereço. A falha temporária da API não deve passar
a 404. Não se altera o contrato da API, que já distingue 404, 422 e 5xx.

Desempenho, volume, concorrência, disponibilidade

Não há medição de tempo de resposta nesta ronda. O pytest demorou
48,40 s para 266 testes. O Playwright completo demorou 9,5 min para
64 testes, acima dos cerca de 3,5 min do I7.3. Essa diferença não é
uma métrica de desempenho do protótipo: inclui o servidor de
desenvolvimento, o proxy contornado e timeouts de testes falhados.

Concorrência de autorização está testada com duas transacções. Não há
teste de carga.

Recuperação. /health devolve 503 se a base não responder. O contentor
tem healthcheck. Não se ensaiou queda do processo nem restauro de
cópia. Não há cópia de segurança configurada no Compose. Limitação
aceitável no protótipo local. Para a avaliação, a reposição é por
migração e dados sintéticos, não por recuperação de desastre.

Manutenibilidade e testabilidade. Monorepo, migrações encadeadas, testes
com e sem base. A fragilidade temporal e a corrida de logout estão em
diagnostico-testes.md.

Acessibilidade e usabilidade. RNF-02 não pede WCAG. Há rótulos, alertas
com role=alert e alguns percursos de teclado. A usabilidade percebida
é matéria do I9, não desta ronda.

Compatibilidade. O protótipo foi exercitado com Chromium 1255 via
Playwright. Não se ensaiaram outros browsers nesta ronda.

Propostas de medição, sujeitas a aprovação

Não são resultados. São o protocolo mínimo, para o I8.3, sem campanha
de carga.

RNF-01. Métrica: ausência de scroll horizontal a 360 e a 1280 nos
fluxos de login, actor, produto, oferta, pesquisa, ficha e contactos.
Cenário: os percursos já existentes. Ambiente: o Playwright actual.
Instrumento: expect de scrollWidth, como já acontece num spec.
Critério: scrollWidth não excede a largura da viewport. Evidência:
saída do Playwright.

RNF-02. Métrica: percurso de teclado até à acção principal, sem rato,
nos formulários de produto, oferta e contacto. Critério: o foco
atinge cada campo e o botão, e o envio ocorre com Enter ou com o
botão focado. Evidência: um teste por formulário.

Tempo de resposta, limiar proposto porque a SRS não tem número.
Cenário: GET /public/offers com a base de avaliação, página de 20,
sem filtro, e com um filtro de texto. Ambiente: Compose local, uma
instância, sem outros clientes. Instrumento: tempo do cliente HTTP
até ao fim do corpo, 20 repetições, depois de 3 de aquecimento.
Critério proposto, a aprovar: mediana inferior a 500 ms e máximo
inferior a 2 s neste ambiente. Se a medição falhar o limiar, o facto
regista-se; não se ajusta o limiar depois de ver o número. Evidência:
tabela com as 20 amostras, sem dados pessoais.

Concorrência já coberta. Não se propõe teste de carga com centenas
de clientes. O critério académico é o comportamento correcto de duas
transacções, já existente, mais a ausência de deadlock nesses testes.

Disponibilidade. Critério do protótipo: /health 200 com base no ar e
503 com base indisponível. Já implementado. Não se promete percentagem
mensal.
