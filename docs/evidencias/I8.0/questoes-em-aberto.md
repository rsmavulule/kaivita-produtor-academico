Questões em aberto — I8.0

Estado na SRS, secção 11, confirmado na leitura do docx. Não se
reclassifica uma questão esclarecida.

Q-01  Esclarecida. Actuação nacional por delegações. A sede e os
      endereços das delegações não se inferem. O protótipo deve poder
      distinguir localização geral e área de actuação. A área ainda
      não existe no modelo. A questão analítica está fechada; a
      consequência em RF-01 está aberta como lacuna de implementação,
      não como ambiguidade nova.

Q-02  Esclarecida. Não gera requisito de software.

Q-03  Resolvida analiticamente. Não gera requisito de crédito.

Q-04  Resolvida metodologicamente. Não gera requisito de software.

Q-05  Decisão de projecto. Preço, quantidade e disponibilidade são
      obrigatórios na publicação. Está implementada em RB-04 e RF-03.
      A SRS diz que se pode rever mediante excepções futuras. Não há
      excepção pedida. A questão não está reaberta.

Q-06  Parcialmente aberta, como na SRS. A política preliminar está
      implementada no que é operacional: privado por omissão, finalidade,
      aviso, data, revogação, evidência mínima sem o valor. Continuam
      por confirmar o prazo de retenção e o enquadramento legal. Não se
      fecha Q-06 com código. Não se escreve um prazo. Antes de dados
      reais, o calendário tem de existir. O protótipo de avaliação usa
      dados sintéticos e não depende desse prazo para funcionar.

Q-07  Informada; documentação pendente. A SRS regista a concordância do
      supervisor e pede o âmbito exacto em acta ou nota. Essa acta não
      está neste repositório. Não é lacuna de software. Bloqueia a
      afirmação de que o modelo foi validado institucionalmente, não a
      execução técnica do protótipo.

Pendências da secção 13 que não são Q numeradas

Validar com o supervisor o modelo actor/papéis. A implementação seguiu
a SRS v1.1. A validação externa não está evidenciada aqui.

Confirmar a estratégia de autorização para organizações. Hoje uma
organização é um actor com kind organization e os mesmos mecanismos de
representação. Não há diferença de regra. Se o supervisor exigir outra
estratégia, é mudança de âmbito, não dívida do que está especificado.

Autorização específica antes de publicar imagens ou contactos reais.
Não há dados reais identificados nesta leitura. As 6 contas fora do
padrão sintético não foram inspeccionadas. Não se assume que sejam
reais nem que sejam de teste.

Critério de passagem da secção 12: validar ambiguidades com utilizadores
quando viável. Não foi feito. É o I9, não uma questão de implementação
do I8.

Divergência à espera de decisão, sem identificador

A secção 4 diz que o visitante pesquisa perfis, produtos e ofertas. Os
requisitos numerados e o diagrama de UC-06 falam de ofertas, com o
perfil e o produto embutidos. Recomendação: não implementar catálogos
independentes sem confirmação. Se o orientador os considerar
obrigatórios, a prioridade passa a P1 e o roadmap do I8.1 alarga-se.

O diagrama de estados nota que a republicação carecia de aprovação
antes da implementação. A implementação e os testes já a incluem desde
o I4. A decisão está tomada na prática. Falta, se se quiser fechar a
nota do diagrama, uma linha de aceitação. Não se altera o diagrama
nesta ronda.

README versus interface de contactos. Correcção documental P3, quando
houver autorização para editar o README. Não é questão da SRS.
