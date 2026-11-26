# Retenção e Q-06 — I8.2

A SRS, secção 10, pede um calendário documentado antes de testes com
dados reais, depois de verificadas as obrigações legais e os requisitos
da USTM. Até lá: minimização, acesso restrito e revisão. Não se afirma
um prazo legal. A secção 11 deixa Q-06 parcialmente aberta.

Esta nota é uma proposta. Não aprova prazos. Não apaga dados. Não liga
eliminação automática. Q-06 continua parcialmente aberta.

## Distinção

Dados operacionais. Contas, actores, produtos, ofertas e contactos
usados pelo protótipo. Conservam-se enquanto o trabalho académico os
utilizar. A eliminação depende de decisão aprovada.

Histórico de autorizações. `publication_authorizations` guarda a
evidência mínima da concessão e da revogação, sem o valor do contacto.
Não deve ser apagado só porque o contacto deixou de ser público. O
prazo, se algum for exigido, tem de ser decidido fora deste código.

Eventos de auditoria. `offer_status_events` guarda a transição, não o
conteúdo comercial. Seguem a mesma lógica: existem para se poder ver
quem mudou o estado e quando. Não há tarefa que os apague por idade.

Logs técnicos. Os contentores escrevem para o log do Docker. Não são
um arquivo de retenção. A configuração desta ronda reduz o que lá
entra. Não se fixa quantos dias o Docker os conserva: isso depende do
anfitrião e não foi medido.

Dados sintéticos. O desenvolvimento e o Playwright usam contas
geradas. A limpeza no fim da execução remove as contas do manifesto
dessa execução, e os recursos dos actores que só essas contas
representam. Não mexe em actores partilhados nem em linhas fora do
manifesto. Não é uma política de retenção; é higiene da execução.

Dados de avaliação académica. Se a defesa vier a usar uma base própria,
ela deve ser criada por migração e por um conjunto controlado. Dados
reais de produtores, contactos ou fotografias não entram sem a
autorização específica pedida pela SRS e sem o calendário que Q-06
ainda não tem.

## Decisões que não são deste incremento

Quanto tempo conservar cada classe depois da defesa. Se a base de
avaliação é apagada no fim. Se os eventos têm de sobreviver à oferta.
Quem, na USTM ou fora dela, aprova o calendário. Nenhuma destas
respostas foi inventada aqui.
