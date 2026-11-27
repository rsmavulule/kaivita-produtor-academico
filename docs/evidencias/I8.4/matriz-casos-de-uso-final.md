# Matriz final de casos de uso — I8.4

Os oito casos de uso não entram nos 27 requisitos. A fonte dos critérios
é a SRS v1.1, secção 8. O diagrama 01B não substitui essa tabela.
Os diagramas não foram alterados.

| UC | Critério da SRS | Requisitos | Classificação | Evidência | Limite que não falha o critério |
| --- | --- | --- | --- | --- | --- |
| UC-01 Autenticar utilizador | Credenciais válidas permitem sessão; inválidas são rejeitadas. | RF-08, RNF-03 | Validado | `backend/tests/test_auth.py`; `frontend/e2e/auth.spec.ts`; smoke I8.4 de login, 401 e término de sessão | Terminar a sessão apaga o cookie e não revoga o JWT. |
| UC-02 Gerir actor representado | Representante autorizado edita; outro utilizador recebe acesso negado. | RF-01, RF-08, RB-10 | Validado | `backend/tests/test_i81_coverage_image.py`; `frontend/e2e/actors.spec.ts`; smoke: consulta `read` recebe 404 na escrita | A área de actuação existe desde o I8.1. O diagrama de classes ainda não a mostra. |
| UC-03 Associar papéis comerciais | Actor pode possuir producer e buyer sem duplicação de identidade. | RF-09, RB-01 | Validado | `test_one_actor_can_hold_several_roles`; E2E de papéis | O comprador não tem fluxo comercial próprio. A SRS adia esse fluxo. |
| UC-04 Gerir produtos | Produto pertence a actor produtor; outro actor não consegue alterá-lo. | RF-02, RB-02, RB-03 | Validado | `backend/tests/test_products.py`; `test_i81_coverage_image.py`; `frontend/e2e/products.spec.ts` | A fotografia é referência HTTPS com declaração. A aplicação não verifica a titularidade nem o conteúdo da imagem. |
| UC-05 Publicar oferta | Sem preço, quantidade, unidade ou disponibilidade, a publicação é rejeitada; o rascunho é permitido. | RF-03, RB-04, RB-05 | Validado | `test_lifecycle_follows_the_approved_state_diagram`; E2E de publicação inválida e de rascunho; smoke de publicar, suspender e retirar | A retirada é terminal. |
| UC-06 Pesquisar e consultar | Visitante vê apenas conteúdos publicados e estados coerentes de disponibilidade. | RF-04, RF-07, RB-06 | Validado | `backend/tests/test_public_offers.py`; `frontend/e2e/public-offers.spec.ts`; smoke de pesquisa e de rascunho oculto | O diagrama intitula o caso como ofertas. Perfil e produto aparecem dentro da oferta. |
| UC-07 Gerir contacto público | Sem autorização, contacto oculto; após revogação, oculto imediatamente. | RF-10, RB-07, RF-05 | Validado | `test_committed_revoke_hides_the_contact_before_the_response_finishes`; `frontend/e2e/contacts.spec.ts` nas duas suites de 68; smoke de concessão e revogação | A página já aberta só muda na consulta seguinte. |
| UC-08 Informar entrega | Condições aparecem como texto, sem promessa de serviço logístico. | RF-06, RB-09 | Validado | Campo `delivery_terms` na ficha pública e no smoke | Não há cálculo de frete. |

Actores do diagrama 01B

Visitante público. Ligado à pesquisa e à consulta de contactos. Implementado.

Representante autorizado. Ligado à sessão, ao actor, aos produtos, às ofertas, aos contactos e às condições de entrega. Implementado.

Administrador. Está no diagrama, sem caso de uso numerado. A nota do próprio diagrama pede validação antes de congelar essa gestão. Não há backoffice. A criação de contas continua a ser `python -m app.create_user`, fora da interface. Não é requisito numerado pendente.

Extensões desenhadas e não numeradas

«Validar dados e propriedade da oferta» e «Aplicar filtros de pesquisa» são comportamentos internos de UC-05 e UC-06. Estão implementados.
