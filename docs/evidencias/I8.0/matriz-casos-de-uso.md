Matriz de casos de uso — SRS v1.1 — I8.0

Os casos de uso não entram no total de 27 requisitos. Verificam os
requisitos indicados. A fonte normativa dos critérios é a secção 8,
páginas 5–6. Os títulos do diagrama 01B são comparados, não substituem
a tabela.

| UC | Critério da SRS | Requisitos | Estado | Evidência principal | Lacuna |
| --- | --- | --- | --- | --- | --- |
| UC-01 Autenticar utilizador | Credenciais válidas permitem sessão; inválidas são rejeitadas. | RF-08, RNF-03 | Validado | tests/test_auth.py; e2e/auth.spec.ts, incluindo credenciais inválidas e terminar sessão, aprovados nesta ronda | Logout não revoga o JWT. Limitação aceite, não falha do critério. |
| UC-02 Gerir actor representado | Representante autorizado edita; outro utilizador recebe acesso negado. | RF-01, RF-08, RB-10 | Parcial | tests/test_authorization.py; e2e/actors.spec.ts | Falta a área de actuação de RF-01. O acesso negado está validado. |
| UC-03 Associar papéis comerciais | Actor pode possuir producer e buyer sem duplicação de identidade. | RF-09, RB-01 | Validado | test_one_actor_can_hold_several_roles; e2e de substituição de papéis | Nenhuma. |
| UC-04 Gerir produtos | Produto pertence a actor produtor; outro actor não consegue alterá-lo. | RF-02, RB-02, RB-03 | Parcial | tests/test_products.py test_product_of_another_actor_is_not_disclosed; e2e/products.spec.ts | O isolamento está validado. A fotografia opcional e a declaração não estão. |
| UC-05 Publicar oferta | Sem preço, quantidade, unidade ou disponibilidade, a publicação é rejeitada; o rascunho é permitido. | RF-03, RB-04, RB-05 | Validado | test_lifecycle_follows_the_approved_state_diagram; e2e de publicação inválida e de rascunho | Nenhuma no critério. |
| UC-06 Pesquisar e consultar | Visitante vê apenas conteúdos publicados e estados coerentes de disponibilidade. | RF-04, RF-07, RB-06 | Validado | tests/test_public_offers.py; e2e/public-offers.spec.ts, aprovado nesta ronda | O diagrama intitula o caso «ofertas». A secção 4 fala também de perfis e produtos. A consulta desses dados existe dentro da oferta. Catálogo independente não é critério deste UC. |
| UC-07 Gerir contacto público | Sem autorização, contacto oculto; após revogação, oculto imediatamente. | RF-10, RB-07, RF-05 | Validado na API | test_committed_revoke_hides_the_contact_before_the_response_finishes; e2e de histórico passou; e2e do visitante falhou na passagem completa e passou na repetição | Página já aberta até nova consulta. Instabilidade do E2E do visitante, P2. O critério de ocultação no pedido seguinte está coberto pela API. |
| UC-08 Informar entrega | Condições aparecem como texto, sem promessa de serviço logístico. | RF-06, RB-09 | Validado | campo delivery_terms na ficha pública; e2e do visitante que acompanha a oferta | Nenhuma. |

Actores do diagrama 01B

Visitante público. Ligado a UC-06 e à consulta de contactos. Implementado.

Representante autorizado. Ligado a UC-01 a UC-05, UC-07 e UC-08. Implementado.

Administrador. Presente no diagrama. A nota do próprio diagrama diz que a gestão de papéis pelo administrador depende das permissões previstas e deve ser validada antes de congelar o desenho. Não há UC numerado de administração. A secção 4 descreve a capacidade e a secção 13 ainda pede confirmação da estratégia. Não se classifica como requisito pendente. A criação de contas é o comando backend/app/create_user.py, fora da interface.

Extensões desenhadas e não numeradas

«Validar dados e propriedade da oferta» e «Aplicar filtros de pesquisa» são comportamentos internos de UC-05 e UC-06. Estão implementados. Não são casos de uso adicionais.
