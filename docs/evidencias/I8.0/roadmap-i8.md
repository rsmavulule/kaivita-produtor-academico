Roadmap do I8 — proposta para aprovação

O I8.0 fecha o diagnóstico. Não inicia estes incrementos. A divisão
mantém os quatro blocos pedidos porque cada um tem um critério de
saída diferente: função, protecção, prova de qualidade, e candidato
congelado. Juntá-los num único incremento misturaria migração de
dados, auditoria e correcção de testes na mesma revisão.

## I8.1 — Completude funcional

Objectivo. Fechar RF-01, RF-02 e RB-08 no mínimo académico.

Requisitos. RF-01, RF-02, RB-08. UC-02 e UC-04 passam a poder ser
reclassificados.

Lacunas. L1 e L2.

Alterações previstas. Coluna opcional de área de actuação. Declaração
de uso, por omissão falsa. image_ref continua texto. A projecção
pública do produtor ganha a área. A do produto ganha a referência só
quando a declaração é verdadeira, mostrada como texto. Formulários e
aviso de texto livre. Migração. Testes de API e um percurso de browser.
Sem ficheiros, sem serviço de imagens, sem catálogos independentes.

Dependências. Nenhuma. Não depende de I8.2.

Riscos. Publicar referências antigas por engano. A omissão falsa
evita-o. Confundir área de actuação com localização geral. Os campos
ficam separados e os testes também.

Testes. Criar e limpar a área. Oferta pública mostra a área e não a
confunde com a sede. Referência sem declaração não sai na API pública.
Referência com declaração sai. Produto sem referência continua válido.

Critério de aceitação. RF-01, RF-02 e RB-08 reclassificáveis para
validado com testes novos aprovados, mais a suite anterior verde.

Evidências. Migração, testes, captura da ficha pública com e sem
referência.

Esforço. Médio.

## I8.2 — Segurança, privacidade e auditoria

Objectivo. Fechar a parte em falta de RNF-07 e reduzir a exposição da
query no log.

Requisitos. RNF-07. Parte residual técnica de RNF-06. Q-06 não se fecha.

Lacunas. L3, L4. L11 e L12 se couberem sem alargar o incremento.

Alterações previstas. Tabela append-only de transições de oferta:
actor, oferta, estado anterior, estado novo, operador, instante. Sem
preço, textos livres nem contactos. Registo na mesma transacção da
transição. Configuração do Uvicorn, ou um filtro, que não grave a
query string. Nota curta, no guião de avaliação, de que os dados são
sintéticos e de que não há prazo legal afirmado. Opcional: FOR UPDATE
na oferta e segunda verificação da representação.

Dependências. Nenhuma em relação a I8.1. Pode seguir-se ou precedê-lo.
Recomenda-se depois de I8.1 para a revisão não misturar os dois temas,
não por dependência técnica.

Riscos. O log de eventos passar a copiar descrição ou contacto. O
critério de aceitação recusa isso. Mudar o access log e perder a
capacidade de diagnosticar erros: o caminho sem query chega.

Testes. Publicar, suspender, republicar e retirar geram linhas na
ordem, na mesma transacção. Falha da transição não deixa evento.
O teste de logs não encontra o valor de um parâmetro de pesquisa.
Concorrência das transições, se L11 entrar.

Critério de aceitação. RNF-07 reclassificável para validado no âmbito
académico. RNF-06 continua parcial no que depende de Q-06 e do texto
livre, e deixa de ter a query como lacuna técnica.

Evidências. Migração, testes, excerto de log sem query e sem segredos.

Esforço. Médio. Baixo se L11 e L12 ficarem de fora.

## I8.3 — Qualidade e desempenho

Objectivo. Corrigir a dívida de testes e recolher as medições que a
SRS não quantificou, com limiares aprovados antes de medir.

Requisitos. RNF-02 na parte de evidência. RNF-01 só se a medição de
overflow for acrescentada. Nenhum RF novo.

Lacunas. L5, L6, L7, L8, L9, L10, L15.

Alterações previstas. Teste temporal relativo ao granted_at. Espera do
URL de logout. Espera do estado no browser do produtor antes da
consulta do visitante. HTTP 404 na página de oferta inválida ou
inelegível. Testes de teclado. Protocolo de tempo da pesquisa, executado
uma vez, com o limiar escrito antes. Guião de instalação do Chromium
1255 e de NO_PROXY. Sem aumentar timeouts para esconder falhas. Sem
teste de carga extenso.

Dependências. Nenhuma de esquema. Convém depois de I8.1 e I8.2 para a
medição e o 404 incidirem sobre o candidato, mas o teste temporal pode
ser feito em qualquer momento.

Riscos. O limiar de 500 ms proposto ser irrealista. Por isso é aprovado
antes, e uma falha regista-se em vez de se mover a meta. O 404 da página
pode partir um teste que espera 200. Os testes ajustam-se ao
comportamento novo, não o contrário.

Testes. Os próprios itens são testes, mais a suite completa.

Critério de aceitação. O teste de autorização não contém data constante
futura. A suite Playwright completa fica verde duas vezes seguidas no
mesmo ambiente. A medição de tempo fica arquivada, mesmo que não cumpra
o limiar: nesse caso o limiar ou o código voltam a decisão, não se
apaga o número.

Evidências. pytest, Playwright, tabela de tempos, nota do código HTTP
da ficha.

Esforço. Baixo a médio.

## I8.4 — Release candidate académico

Objectivo. Congelar uma versão avaliável, separada da base de
desenvolvimento.

Requisitos. Nenhum funcional novo. Condições de criterios-release-candidate.md.

Lacunas. L13, L14, L16.

Alterações previstas. Base e Compose de avaliação, ou perfil equivalente,
sem reutilizar o volume actual. Migrações. Conjunto sintético pequeno.
Duas contas de demonstração. Guião de reposição. README alinhado com a
interface de contactos. Execução final das suites. Não entra I9.

Dependências. I8.1, I8.2 e I8.3. Sem eles, o candidato herda as lacunas
P1 e a fragilidade de testes.

Riscos. Copiar resíduos da base de desenvolvimento. O procedimento de
reposição parte de uma base vazia. Credenciais de demonstração no Git.
Ficam fora do versionamento, como o .env actual.

Testes. Suite completa na base de desenvolvimento ou descartável.
Percurso manual curto na base de avaliação: entrar, ver a oferta
sintética, consultar o contacto autorizado, confirmar que o contacto
privado não aparece.

Critério de aceitação. O de criterios-release-candidate.md.

Evidências. Contagens da base de avaliação, saída das suites, guião de
reposição, versão e Alembic head.

Esforço. Médio.

Ordem recomendada

I8.1, depois I8.2, depois I8.3, depois I8.4. I8.2 pode trocar com I8.1
se a revisão preferir auditoria primeiro. Não se recomenda começar por
I8.4 nem por I8.3 sozinho como se isso fechasse a SRS: o teste temporal
é obrigatório, mas não é a lacuna funcional.
