Relatório final — I8.0

Diagnóstico de conformidade do protótipo com a SRS v1.1. Não houve
alteração de código, testes, migrações, configuração versionada, SRS,
diagramas nem evidências anteriores. Não houve commit nem push. Não se
consultou repositório comercial.

1. Baseline confirmado

Branch main, HEAD 045a63470eeaa382811c0ca6b7c33ff1e028b1a1, alinhada com
origin/main. Alembic 0006_publication_authorizations. PostgreSQL a
aceitar ligações, porta publicada 5435. API saudável em 8010. Interface
em 3010, HTTP 200. Não foi preciso reconstruir imagens: o backend de
produção não muda neste commit e três ficheiros da interface de
contactos coincidem com o contentor. Detalhe em diagnostico-baseline.txt.

2. Fontes inspeccionadas

SRS v1.1 no docx original, páginas 1 a 8 pelas marcas do documento.
Diagramas drawio 01A, 01B, 02, 04, 05, 06 e 07. README. Código de
backend/app, migrações 0001 a 0006, testes backend, testes Playwright,
compose.yaml, autenticação, cookies, origem e Dockerfiles. Evidências
I4, I5.5, I6.1, I6.2, I7.1, I7.2 e I7.3, sem as alterar.
_srs_extract.txt não foi a fonte.

3. Inventário normativo

27 requisitos numerados: 10 RF, 10 RB, 7 RNF. À parte: 8 casos de uso,
10 entidades conceptuais, 7 questões, 10 exclusões operacionais da
secção 2. OrganizationUnit tem CRUD fora do âmbito. Os fluxos
especializados de comprador e parceiro estão adiados. Nada disto entra
no denominador dos 27. Texto em inventario-normativo.txt.

4. Estado consolidado

| Categoria | Total | Validado | Implementado não validado | Parcial | Pendente | Não aplicável | Fora do âmbito |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| RF | 10 | 8 | 0 | 2 | 0 | 0 | 0 |
| RB | 10 | 9 | 0 | 1 | 0 | 0 | 0 |
| RNF | 7 | 4 | 1 | 2 | 0 | 0 | 0 |
| Total | 27 | 21 | 1 | 5 | 0 | 0 | 0 |

A soma das classificações é 27.

Validação integral: 21/27. O denominador é só o conjunto numerado.
Os 5 parciais não recebem meio cumprimento.

Implementação integral: 22/27, isto é, validado mais implementado não
validado. Não é percentagem de conclusão do software nem de linhas
cobertas.

Parciais: RF-01, RF-02, RB-08, RNF-06, RNF-07.

Pendentes numerados: zero.

Implementado não validado: RNF-02.

Não se usou «fora do âmbito» para nenhum requisito numerado. As
exclusões da secção 2 continuam excluídas e não foram implementadas.

5. Lacunas funcionais

Obrigatórias e ainda abertas: área de actuação; referência de imagem
consultável em público só depois de declaração de direito de uso.
Não são obrigatórios, no texto numerado: catálogos independentes de
actores e produtos, ficheiros de imagem, CRUD de delegações, mudança
de estado do actor pela interface. A republicação de ofertas já está
feita e testada. A descoberta pública, os contactos autorizados e o
ciclo da oferta estão feitos. O README ainda diz que a interface não
mostra os contactos; o código mostra-os. Detalhe em lacunas-funcionais.md.

6. Divergências UML

O diagrama de classes coincide com o código nos atributos de Actor,
incluindo a ausência de coverage_area. Quem fica aquém da SRS é o par
diagrama e código, face a RF-01. PublicContact.authorizationRecord foi
substituído por histórico, decisão justificada. O 403 do diagrama de
sequência foi substituído por 404 opaco, decisão de segurança que não
se deve reverter. A nota do diagrama de estados que pedia aprovação da
republicação está desactualizada: a transição existe e está testada.
Nenhum componente desenhado está por implementar. Detalhe em
matriz-divergencias-uml.md.

7. Segurança e privacidade

RNF-06 parcial. Projecção mínima, finalidade única, ocultação e aviso
operacional estão testados. Texto livre não é filtrado. Não há prazo
de retenção. A confirmação do representante não prova o consentimento
do titular.

RNF-07 parcial. O histórico de autorização de contacto existe e não
guarda o valor. As transições de oferta não geram evento.

Q-06 permanece parcialmente aberta, como na SRS. Não há conformidade
legal a declarar.

8. Auditoria e retenção

A evidência mínima da autorização é a linha em
publication_authorizations. Não reconstrói o contacto antigo. Não
audita publicação de ofertas, perfil nem representação. Retenção: não
se afirma prazo. Até decisão legal, a avaliação deve usar dados
sintéticos, acesso restrito e reposição, como a secção 10 permite sem
fixar o calendário.

9. Consistência transaccional

Nenhum defeito transaccional novo foi reproduzido. CommitBeforeResponse
e os testes de visibilidade passaram dentro dos 266. Riscos potenciais,
não observados como falhas: revogação de representação entre a leitura
e o commit; transições de oferta sem bloqueio de linha; mapa de
identidade se no futuro houver leitura antes do FOR UPDATE. Limitações
aceites: commit síncrono e READ COMMITTED. Detalhe em
diagnostico-transaccional.md.

10. Qualidade e desempenho

Não há números de desempenho, porque não se mediu e a SRS não traz
limiares. Há protocolo proposto, com mediana de 500 ms na pesquisa
local como limiar a aprovar antes de medir. A página de oferta
inexistente ou UUID inválido responde 200 enquanto a API responde 404
ou 422. Cache-Control no-store foi observado. /inicio sem cookie
responde 307. Detalhe em diagnostico-qualidade-desempenho.md.

11. Cobertura e fragilidade dos testes

266 testes backend aprovados em 48,40 s. 64 testes Playwright
definidos. Execução completa: 61 aprovados, 3 falhados, 9,5 min. O
verde de 64 do I7.3 não foi reproduzido. Duas tentativas anteriores nem
arrancaram: o proxy local fazia o Playwright ver 503 no servidor que
noutro cliente respondia 200. Não se aumentou o timeout. A falha de
logout no spec de contactos reproduziu-se. As outras duas mudaram de
asserção ou passaram na repetição. O teste temporal com 2099-01-01
continua obrigatório de corrigir e ainda não o foi. Chromium 1255 não
estava na cache persistente do utilizador. Detalhe em
diagnostico-testes.md e playwright-resultados.txt.

12. Dívidas técnicas

Obrigatória e não feita: o instante de revogação do teste de
autorizações. Observadas: corrida de logout e instabilidade da consulta
do visitante. De produto: L1, L2 e L3 no backlog. Detalhe em
divida-tecnica.md.

13. Questões em aberto

Q-01 a Q-05 estão tratadas na SRS. Q-06 continua parcialmente aberta.
Q-07 continua com a acta por registar. A frase da secção 4 sobre
pesquisar perfis e produtos à parte das ofertas espera decisão e não
foi promovida a requisito. Detalhe em questoes-em-aberto.md.

14. Verificações executadas

Git status e git log no início. Compose, saúde, Alembic, PostgreSQL,
hashes da imagem web, contagens de leitura. Pytest 266. Build do
frontend com sucesso. Playwright depois do build, não em simultâneo.
Contagens iguais no fim: 55 contas, 49 do padrão sintético, 6 outras,
173 actores, 92 produtos, 40 ofertas, 0 contactos, 0 autorizações.
Git no fim: ver o ponto 20.

15. Backlog

Sem P0. P1: área de actuação, fotografia com declaração, eventos de
publicação. P2: teste temporal, corridas de browser, soft 404, teclado,
medição, bloqueios opcionais, base de avaliação, access log. P3: README,
estado do actor, catálogos independentes, CHECK do papel producer, TLS
e backoffice. Tabela em backlog-residual.md.

16. Roadmap

I8.1 completude funcional, esforço médio. I8.2 auditoria e logs, esforço
médio. I8.3 qualidade, testes e uma medição, esforço baixo a médio.
I8.4 candidato e base de avaliação, esforço médio, depois dos três.
Detalhe em roadmap-i8.md.

17. Release candidate

Não se declara candidato. Faltam as três lacunas P1, o teste temporal,
uma suite Playwright verde reproduzida e a base de avaliação separada.
Critérios em criterios-release-candidate.md.

18. Condições para o I9

Versão congelada, ambiente reponível, dados sintéticos, percursos dos
casos de uso, instrumento de recolha fora da base da aplicação,
consentimento de participação distinto do aviso de divulgação, registo
de dificuldades e de utilidade percebida. Não se executa o I9 agora.
Não se afirma que o protótipo melhorou o escoamento.

19. Evidências produzidas

docs/evidencias/I8.0/ e apenas essa pasta:

  diagnostico-baseline.txt
  inventario-normativo.txt
  matriz-rastreabilidade-integral.md
  matriz-casos-de-uso.md
  matriz-divergencias-uml.md
  lacunas-funcionais.md
  diagnostico-seguranca-privacidade.md
  diagnostico-transaccional.md
  diagnostico-qualidade-desempenho.md
  diagnostico-testes.md
  divida-tecnica.md
  dados-sinteticos-ambiente-avaliacao.md
  questoes-em-aberto.md
  backlog-residual.md
  roadmap-i8.md
  pytest-resultados.txt
  playwright-resultados.txt
  build-compose.txt
  criterios-release-candidate.md
  relatorio-final.md

20. Estado final do Git

HEAD mantém-se 045a634. Não houve commit nem push. Não houve staging.
Continuam por versionar, como no início, _srs_extract.txt e docs/srs/.
As evidências do I8.0 são ficheiros novos, ainda não versionados, à
espera de revisão. As evidências históricas não foram editadas. A
execução Playwright não usou E2E_EVIDENCE, por isso as capturas foram
para frontend/test-results, ignorado pelo Git.

Recomendação

O próximo incremento a implementar é o I8.1. É o único que fecha
requisitos funcionais de prioridade Alta ainda parciais, RF-01 e RF-02,
e a regra RB-08, com uma migração pequena e sem infra-estrutura de
imagens. O I8.2 é o seguinte, porque RNF-07 continua parcial num ponto
obrigatório: não há eventos das transições de oferta. O teste temporal
é obrigatório no I8, mas não deve ser o incremento seguinte: não corrige
um incumprimento actual da SRS e a data 2099 ainda não faz falhar a
suite. Não se inicia o I9.
