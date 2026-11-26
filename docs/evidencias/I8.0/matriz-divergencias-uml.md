Matriz de divergências UML — I8.0

Fonte dos rótulos: os ficheiros .drawio em docs/srs/diagramas.
Foram lidos 01A-contexto-negocio, 01B-casos-de-uso-sistema, 02-classes,
04-componentes, 05-actividades, 06-sequencia e 07-estados-oferta.
Os SVG em diagramas/svg são exportações. A pesquisa de texto nos SVG
não devolveu os rótulos; a comparação usa o drawio, que é a fonte
editável. Os diagramas não foram alterados.

Distinção. O diagrama de classes é modelo conceptual. As tabelas e as
classes Python são o modelo lógico e a implementação. Não se exige uma
classe Python por classe do diagrama nem uma tabela por classe
conceptual. Exige-se que os atributos normativos existam e que as
divergências sejam justificadas ou registadas como incumprimento.

| Diagrama | Elemento | Implementação | Tipo | Impacto | Recomendação |
| --- | --- | --- | --- | --- | --- |
| 01A Contexto | Processos de divulgar, descobrir, consultar condições, estabelecer contacto e gerir informação. A nota exclui contacto, negociação, pagamento e logística como execução automática. | Descoberta, condições e divulgação de contacto existem. Estabelecer o contacto comercial ocorre fora da plataforma. O componente público diz isso. | Diferença justificada | Nenhum incumprimento. | Manter. |
| 01B Casos de uso | Administrador dentro da fronteira, sem UC numerado. A nota pede validação. | Não há interface de administrador. create_user.py cria contas. | Diferença em aberto, não é incumprimento de UC | Baixo, até haver decisão. | Não construir backoffice no I8. |
| 01B | UC-06 intitulado «Pesquisar e consultar ofertas». | A pesquisa é de ofertas. Perfil e produto aparecem na oferta. | Alinhado com RF-04. A secção 4 da SRS é mais larga do que o diagrama. | Ver lacunas funcionais. | Não acrescentar catálogos só para coincidir com a secção 4, sem decisão. |
| 02 Classes | Actor: id, kind, displayName, generalLocation, status. Operação genérica method. | Os cinco atributos existem. Não há coverage_area no diagrama nem no código. A SRS, em RF-01 e no parágrafo da secção 3, fala de área de actuação. | O diagrama coincide com o código e ambos ficam aquém de RF-01. | Incumprimento de RF-01, não divergência diagrama-código. | Implementar o campo. Actualizar o diagrama só num incremento autorizado a editar UML. Não se adapta o diagrama para apagar a lacuna. |
| 02 Classes | Product: id, ownerActorId, name, description, category, imageRef, status. Operações updateDetails e archive. | Iguais. image_ref não é publicado. | Atributo presente. A publicação condicional é RB-08, não um atributo em falta. | Parcial em RF-02 e RB-08. | Declaração e projecção condicional. O diagrama pode ganhar a declaração mais tarde; não é obrigatório para o mínimo. |
| 02 Classes | Offer: id, productId, ownerActorId, price, currency, quantity, unit, availability, deliveryTerms, status. Operações validateForPublication, publish, suspend, withdraw. | Iguais, mais republicação por publish a partir de suspended. | A republicação está no diagrama de estados e não nesta lista de operações. | Nenhum, se os dois diagramas se lerem juntos. | Sem mudança de código. |
| 02 Classes | User.login | A coluna é email, usada como login. | Nome diferente, mesmo papel. Justificado desde o I1. | Nenhum. | Manter email. |
| 02 Classes | PublicContact.authorizationRecord: UUID | Não há FK para uma autorização. O histórico é a tabela publication_authorizations. Há ainda status, revision, created_at e updated_at. | Evolução justificada no I7: uma FK única não guarda histórico nem revogação. | Nenhum incumprimento de RF-10. | Não voltar a uma FK única. |
| 02 Classes | PublicationAuthorization: id, actorId, scope, grantedAt, revokedAt, noticeVersion. | Há ainda contact_id, contact_revision, channel, purpose, operadores e revocation_reason. scope está repartido em purpose e channel. | Implementação mais específica do que o diagrama. Justificada. | Nenhum. | O diagrama conceptual fica como estava. A matriz lógica é a do I7.2. |
| 02 Classes | OrganizationUnit | Não está no diagrama de classes. A SRS põe o CRUD fora do âmbito. | Coerente com a exclusão. | Nenhum. | Não implementar. |
| 04 Componentes | Aplicação Web, API REST, Persistência, Migrações. A nota exclui o Compose como componente de negócio. | Next.js, FastAPI, PostgreSQL, Alembic. Compose é execução local. | Alinhado. | Nenhum componente de negócio em falta. | Manter. |
| 05 Actividades | Seleccionar actor, verificar autorização, seleccionar produto, preencher, validar, persistir publicada ou manter estado anterior. | publish_offer segue essa sequência. Erro não muda o estado. O teste de transição repetida e o de publicação falhada cobrem a rejeição. | Alinhado. | Nenhum. | Manter. |
| 06 Sequência | Publicar oferta: Web, API, PostgreSQL. Nota: comportamento proposto, não endpoints já implementados. Ramo inválido 403 ou 422. | O endpoint existe: POST /actors/{id}/offers/{id}/publish. Actor inexistente ou sem acesso: 404, igual para os dois casos. Dados inválidos: 422. Não se usa 403. | O 404 opaco é decisão de segurança posterior ao diagrama. O diagrama está desactualizado na nota e no 403. | Não é incumprimento. Mudar para 403 revelaria existência. | Não alterar a API para coincidir com o 403. Actualizar o diagrama só se for autorizado. |
| 07 Estados | Rascunho, Publicada, Suspensa, Retirada. Publicar, suspender, republicar com revalidação, retirar. Retirada terminal. Nota: a enumeração e a republicação careciam de aprovação. | Os quatro estados e as transições existem. Retirada não volta atrás. Republicar revalida. test_lifecycle_follows_the_approved_state_diagram. | A nota de «carece de aprovação» contradiz a implementação já testada desde o I4. Os estados coincidem. | A divergência é a nota, não o ciclo. | Registar a republicação como decisão tomada. Não mudar o ciclo. Não editar o diagrama nesta ronda. |

Cardinalidades. ActorRole e UserActorAccess usam a chave primária como UNIQUE da SRS. A oferta aponta para um produto do mesmo actor, imposto pela FK composta. Não se encontrou cardinalidade implementada ao contrário do diagrama.

Estados. Não há estado de oferta no código fora dos quatro do diagrama. A disponibilidade é atributo, como a nota do diagrama pede, e não é um estado do ciclo.

Operações em falta no código face ao diagrama: nenhuma operação nomeada de negócio. As operações genéricas «method» do Actor não são especificadas.

Componentes não implementados: nenhum dos quatro desenhados. Não há componente de mensagens, cache ou armazenamento de imagens no diagrama, e também não há na implementação. Isso é coerente.
