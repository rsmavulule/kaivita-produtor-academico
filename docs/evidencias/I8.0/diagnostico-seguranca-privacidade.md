Diagnóstico de segurança e privacidade — I8.0

Redacção original confirmada na SRS, secção 7, página 5, e secção 11,
página 7.

RNF-06. «Minimização de dados pessoais, consentimento por finalidade e
possibilidade de ocultar contactos públicos.»

RNF-07. «Registar eventos relevantes de autorização e alterações de
publicação sem expor dados sensíveis em logs.»

Q-06. «Política preliminar definida; prazos de retenção e enquadramento
legal por confirmar.» Estado na SRS: parcialmente aberta.

Não se afirma conformidade legal. A confirmação do representante não
comprova o consentimento do titular. O histórico de autorizações de
contacto não é uma auditoria transversal de todas as escritas.

Garantias implementadas

Minimização da projecção pública. A oferta pública leva identificador
da oferta, preço, moeda, quantidade, unidade, disponibilidade, condições
de entrega, nome, descrição e categoria do produto, nome, tipo e
localização do produtor. Não leva email da conta, identificadores de
utilizador, estado interno, image_ref nem contactos.
Ficheiros: backend/app/public_offers.py, backend/app/public_catalog.py.

Contactos privados por omissão. A divulgação exige autorização vigente,
revisão e canal coincidentes, finalidade commercial_discovery, contacto
activo e visibilidade public. A oferta inelegível responde 404. A oferta
elegível sem contactos responde lista vazia.
Ficheiro: backend/app/public_offers.py, função _contact_statement.

Finalidade única e aviso v1. A concessão exige confirmação explícita e
a versão de aviso suportada. O texto do aviso diz que a confirmação
operacional não prova o consentimento do titular.
Ficheiros: backend/app/publication.py, frontend/lib/contact-view.ts.

Revogação. Manual, por alteração efectiva do canal ou do valor, e por
desactivação. A linha histórica permanece, sem cópia do valor.
Testes: test_history_revoke_and_a_later_grant,
test_effective_change_revokes_and_invalid_change_does_not,
test_deactivation_revokes_once_and_leaves_the_contact_private,
test_committed_revoke_hides_the_contact_before_the_response_finishes.

Palavra-passe. Argon2id. O JWT leva sub, iat, exp e iss. Não leva email
nem permissões. JWT_SECRET é obrigatório e não tem omissão no código.
Cookie de sessão HttpOnly, SameSite=Lax, Secure quando o protocolo
observado é HTTPS. O browser não recebe o JWT. Same-origin recusa
origem ausente, outro host e sec-fetch-site diferente de same-origin.
Ficheiros: backend/app/passwords.py, backend/app/tokens.py,
backend/app/config.py, frontend/lib/cookie-policy.ts,
frontend/lib/origin.ts, frontend/middleware.ts.

Erros. O 422 de validação não devolve o valor rejeitado.
backend/app/main.py, hide_rejected_input. Os testes de contactos e de
pesquisa cobrem a ausência do valor na mensagem.

Isolamento. Representação verificada no servidor. Actor inacessível e
actor inexistente respondem o mesmo 404. Papel comercial não concede
manage. Testes em test_authorization.py, test_actor_roles.py e nos
catálogos.

Garantias parciais

RNF-06. A ocultação e a finalidade única estão feitas. A minimização
não alcança o texto livre. Não há calendário de retenção. O aviso é
operacional.

RNF-07. Há histórico de autorização de contacto: operador, instante,
finalidade, versão do aviso, revisão, canal e motivo de revogação, sem
o valor. Não há eventos de publicar, suspender, republicar ou retirar
oferta. Essas transições só se vêem no estado actual da linha offers.
Não há quem nem quando.

Logs. A aplicação regista o tipo da excepção na falha de base e na
rejeição do token, não a URL nem a palavra-passe. O comando do contentor
é uvicorn sem configuração que desligue o access log. O access log do
Uvicorn inclui o caminho e a query. Uma pesquisa pode portanto ficar
no log do contentor. Não se observou, nesta ronda, um valor de contacto
nesse log, porque não se provocou essa escrita. O risco está na
configuração, não numa captura desta sessão.

Limitações da arquitectura

Logout apaga o cookie e não revoga o JWT. Um token copiado vale até
expirar. Não há refresh token. A SRS não pede lista de revogação.
Fica limitação aceite de RNF-03, já coberta pelos testes de expiração
e de conta desactivada. A conta desactivada é recusada no pedido
seguinte, mesmo com token ainda não expirado.

O Compose local é HTTP. Secure fica desligado nesse protocolo. Não há
terminação TLS no compose.yaml. Adequado ao protótipo local. Não é
uma configuração para exposição pública.

A base de desenvolvimento usa a palavra-passe por omissão do Compose
quando o ambiente local a repete. O .env não está no Git. O
.env.example não contém segredo. Não se transcreve nenhum segredo
nesta evidência. JWT_SECRET continua obrigatório para a API arrancar.

Riscos residuais

Texto livre público: nome do actor, localização, área de actuação se
for acrescentada, nome do produto, descrição, categoria e condições de
entrega. O aviso actual, PUBLIC_FIELD_NOTICE, pede para não introduzir
telefone, email ou outros dados pessoais. Está nos campos de actor,
produto e oferta, incluindo a edição, porque ProductFields e
OfferFields o incluem. Não há filtro heurístico. Não se propõe censura
automática. A medida proporcional é manter o aviso, não prometer que
o sistema detecta contactos escritos à mão, e não tratar esse texto
como contacto estruturado. Os contactos estruturados continuam no
modelo PublicContact e só saem com autorização.

Pesquisa. O parâmetro q pode conter dados pessoais escritos pelo
visitante. A API rejeita parâmetros inesperados e não ecoa o valor no
422. O access log pode guardá-lo. Medida proporcional para o I8.2:
não registar a query string no access log do contentor, ou usar um
formato que omita a query. Não é preciso um filtro de conteúdo.

Retenção. Q-06 continua aberta. Não se fixa um prazo legal. Para o
protótipo, o mínimo documental é: dados de desenvolvimento e de
avaliação são sintéticos; não se carregam contactos reais; a base de
avaliação, quando existir, é reposta a partir de migrações e de um
conjunto controlado; não se afirma prazo de conservação legal.

Auditoria. O histórico de publication_authorizations é a evidência
mínima da autorização, como pede a secção 10. Não reconstrói o valor
antigo. Isso é minimização, não perda da linha de autorização. Não
substitui auditoria das transições de oferta nem das alterações de
perfil, produto ou representação.

Questões não resolvidas por código

Enquadramento legal da publicação de contactos e de imagens.
Prazo de retenção. Acta de Q-07. Autorização específica antes de
qualquer dado real. Estratégia de autorização para organizações, ainda
pendente na secção 13. O administrador académico da secção 4 não tem
interface; a criação de contas é o comando create_user. Não é um RF
numerado. Não se constrói um backoffice neste protótipo sem decisão
nova.

Classificação

RNF-06 permanece parcial. A parte técnica de projecção, finalidade e
ocultação está testada. O resto é texto livre, logs e retenção.
RNF-07 permanece parcial. Falta o registo das alterações de publicação.
Prioridade dessa parte: P1, incremento I8.2. A omissão da query no
access log é P2, no mesmo incremento, porque reduz exposição sem
mudar o contrato.
