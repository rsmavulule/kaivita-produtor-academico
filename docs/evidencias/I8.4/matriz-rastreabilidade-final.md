# Matriz definitiva de rastreabilidade — I8.4

Fonte normativa: SRS v1.1, secções 5, 6 e 7. Os textos abaixo são os da SRS.
A SRS e os diagramas não foram alterados. Há 27 requisitos numerados:
10 RF, 10 RB e 7 RNF. Q-06 não entra neste denominador.

A classificação «validado» significa comportamento implementado e exercido
por testes automatizados no âmbito académico, no HEAD
`ba62f25`. Não é avaliação empírica com utilizadores. Essa avaliação é o I9.

| Classe | Total | Validado | Parcial |
| --- | ---: | ---: | ---: |
| RF | 10 | 10 | 0 |
| RB | 10 | 10 | 0 |
| RNF | 7 | 6 | 1 |
| Total | 27 | 26 | 1 |

O único parcial numerado é RNF-06. Não foi reclassificado neste incremento.

## RF-01

Descrição: Criar, consultar e actualizar perfil de actor com papel produtor; pessoa singular ou organização, localização geral e área de actuação.

Componente: actores e representação.

Código: `backend/app/actors.py`, `backend/app/actor_roles.py`, `backend/app/identity.py`, migração `0007_coverage_and_image_rights`.

Endpoints: `POST /actors`, `GET /actors`, `GET /actors/{actor_id}`, `PATCH /actors/{actor_id}`.

Interface: `/actores`, `/actores/[actorId]`. A área de actuação sai na ficha pública da oferta elegível.

Testes: `backend/tests/test_i81_coverage_image.py` (`test_coverage_area_is_independent_of_general_location`); `frontend/e2e/actors.spec.ts`; `frontend/e2e/i81-cobertura.spec.ts`. Evidência I8.1 e suites I8.3.

Classificação: validado.

Limitações: não há mapa nem coordenadas. O diagrama de classes continua sem `coverage_area`. Isso é divergência documental, não lacuna do requisito.

## RF-02

Descrição: Criar, editar, arquivar e consultar produtos associados a actor produtor; nome, categoria, descrição e fotografia opcional.

Componente: catálogo de produtos.

Código: `backend/app/catalog.py`, `backend/app/products.py`, migração `0003_products` e colunas de direitos em `0007_coverage_and_image_rights`.

Endpoints: `POST /actors/{actor_id}/products`, `GET` da colecção e da ficha, `PATCH .../products/{product_id}`, `POST .../archive`.

Interface: `/actores/[actorId]/produtos` e ficha do produto. A referência HTTPS, quando declarada, aparece na oferta pública.

Testes: `backend/tests/test_products.py`; `backend/tests/test_i81_coverage_image.py` (`test_photograph_stays_optional_until_a_matching_declaration`); `frontend/e2e/products.spec.ts`.

Classificação: validado.

Limitações: a fotografia é uma referência HTTPS, não um ficheiro guardado pela aplicação. Sem a referência, o produto e a oferta continuam válidos.

## RF-03

Descrição: Criar, editar, publicar, suspender e retirar ofertas; preço, moeda, quantidade, unidade e disponibilidade obrigatórios para publicação.

Componente: ofertas.

Código: `backend/app/offer_catalog.py`, `backend/app/offers.py`, migração `0004_offers`.

Endpoints: `POST /actors/{actor_id}/offers`, `GET`, `PATCH`, `POST .../publish`, `POST .../suspend`, `POST .../withdraw`.

Interface: `/actores/[actorId]/ofertas` e ficha da oferta. A republicação usa publicar a partir de `suspended`.

Testes: `backend/tests/test_offers.py` (`test_lifecycle_follows_the_approved_state_diagram`); `frontend/e2e/offers.spec.ts`.

Classificação: validado.

Limitações: não há `DELETE`. A retirada é terminal. A criação do rascunho não gera `OfferStatusEvent`; as transições efectivas geram.

## RF-04

Descrição: Pesquisar ofertas públicas por texto e filtrar por categoria; localização geral quando disponível.

Componente: descoberta pública.

Código: `backend/app/public_offers.py`, `backend/app/public_catalog.py`.

Endpoints: `GET /public/offers` com `q`, `category` e `location`.

Interface: `/` e `/ofertas`.

Testes: `backend/tests/test_public_offers.py` (`test_search_combines_text_category_and_location`); `frontend/e2e/public-offers.spec.ts`.

Classificação: validado.

Limitações: a pesquisa não filtra por área de actuação. O requisito pede localização geral. O mapa de acentos não cobre caracteres fora do português previsto nem formas Unicode decompostas.

## RF-05

Descrição: Apresentar localização geral e apenas contactos comerciais autorizados pelo actor.

Componente: descoberta pública e autorizações.

Código: `backend/app/public_catalog.py`, `backend/app/public_offers.py`, `backend/app/publication.py`.

Endpoints: a localização vai em `GET /public/offers` e `GET /public/offers/{offer_id}`. Os contactos vão só em `GET /public/offers/{offer_id}/contacts`.

Interface: ficha `/ofertas/[offerId]` e acção «Ver contactos».

Testes: `backend/tests/test_publication.py` (`test_public_disclosure_follows_eligibility_and_authorization`); `frontend/e2e/contacts.spec.ts`. Suites I8.3: 68 testes, duas vezes.

Classificação: validado.

Limitações: a página já aberta conserva o último resultado até nova consulta. O enquadramento do titular permanece em Q-06 e não retira o cumprimento operacional deste requisito.

## RF-06

Descrição: Registar e apresentar condições informativas de entrega, sem cálculo ou contratação de frete.

Componente: ofertas e ficha pública.

Código: `delivery_terms` em `backend/app/offers.py` e `backend/app/offer_catalog.py`.

Endpoints: corpo da oferta privada e campo da oferta pública.

Interface: formulário da oferta e ficha pública.

Testes: `backend/tests/test_offers.py`, `backend/tests/test_public_offers.py`, `frontend/e2e/offers.spec.ts`, `frontend/e2e/public-offers.spec.ts`.

Classificação: validado.

Limitações: o texto não é garantia de transporte. RB-09 reforça o mesmo limite.

## RF-07

Descrição: Permitir consulta pública sem autenticação apenas de recursos publicados.

Componente: descoberta pública.

Código: predicado de elegibilidade em `backend/app/public_offers.py`. Oferta `published`, produto `active`, actor `active` e papel `producer`.

Endpoints: `GET /public/offers` e `GET /public/offers/{offer_id}`, sem sessão.

Interface: `/`, `/ofertas`, `/ofertas/[offerId]`.

Testes: `test_unpublished_states_are_hidden_on_list_and_detail`, `test_archiving_the_product_hides_the_offer_without_changing_it`, `test_inactive_actor_is_hidden_from_public_discovery` em `backend/tests/test_public_offers.py`.

Classificação: validado.

Limitações: uma oferta `published` com disponibilidade `unavailable` continua visível como indisponível. Não é anunciada como disponível. O soft 404 da página Next.js não é este requisito.

## RF-08

Descrição: Autenticar utilizadores e impedir alteração de dados de actores sem representação autorizada.

Componente: autenticação e autorização.

Código: `backend/app/auth.py`, `backend/app/authorization.py`, `frontend/lib/session.ts`, `frontend/app/login/actions.ts`.

Endpoints: `POST /auth/login`, `GET /auth/me`. As escritas privadas passam por `actor_for_manage`.

Interface: `/login`, `/inicio`, botão «Terminar sessão».

Testes: `backend/tests/test_auth.py`, `backend/tests/test_authorization.py`; `frontend/e2e/auth.spec.ts`.

Classificação: validado.

Limitações: terminar a sessão apaga o cookie e não revoga o JWT até este expirar. Sem o cookie, a interface não volta a usar o token. Isto está aceite em RNF-03.

## RF-09

Descrição: Permitir associação de um actor a múltiplos papéis comerciais sem duplicar identidade.

Componente: papéis comerciais.

Código: `backend/app/actor_roles.py`, `backend/app/roles.py`, tabela `actor_roles`.

Endpoints: `GET /roles`, `GET /actors/{actor_id}/roles`, `PUT /actors/{actor_id}/roles`.

Interface: ficha do actor.

Testes: `test_one_actor_can_hold_several_roles` e `test_replacing_roles_with_the_same_set_is_idempotent` em `backend/tests/test_actor_roles.py`; `frontend/e2e/actors.spec.ts`.

Classificação: validado.

Limitações: o catálogo continua fechado em `producer`, `buyer` e `partner`. Não há fluxos especializados de comprador ou parceiro. A SRS adia esses fluxos.

## RF-10

Descrição: Permitir registar, consultar e revogar autorização para publicação de contactos; ocultar contacto após revogação.

Componente: autorizações de divulgação.

Código: `backend/app/publication.py`, `backend/app/publication_catalog.py`, migração `0006_publication_authorizations`.

Endpoints: `GET` e `POST /actors/{actor_id}/contacts/{contact_id}/authorizations`; `POST .../authorizations/{authorization_id}/revoke`.

Interface: `/actores/[actorId]/contactos/[contactId]`.

Testes: `test_history_revoke_and_a_later_grant` e `test_committed_revoke_hides_the_contact_before_the_response_finishes` em `backend/tests/test_publication.py`; `frontend/e2e/contacts.spec.ts`.

Classificação: validado.

Limitações: uma autorização cobre um contacto de cada vez. O histórico não guarda o valor do contacto. Q-06 continua aberta quanto ao prazo legal.

## RB-01

Descrição: ActorRole é único por par actor/papel; papéis comerciais não substituem permissões.

Componente: papéis e representação.

Código: chave primária de `actor_roles` em `backend/app/identity.py`; `backend/app/authorization.py`.

Endpoints: `PUT /actors/{actor_id}/roles`. A decisão `manage` não é o papel comercial.

Interface: a gestão depende do nível de representação.

Testes: `test_duplicate_roles_are_rejected`, `test_producer_role_does_not_grant_manage`.

Classificação: validado.

Limitações: nenhuma no texto da regra.

## RB-02

Descrição: Produto e oferta têm actor proprietário; só actor com papel produtor pode publicar oferta.

Componente: produtos e ofertas.

Código: `owner_actor_id` atribuído no servidor; `require_producer_role` em `backend/app/products.py` e `backend/app/offers.py`.

Endpoints: criação, alteração, publicação, suspensão e retirada.

Interface: escrita só com representação `manage` e papel `producer`.

Testes: `test_actor_without_producer_role_cannot_write_offers`; `test_database_accepts_a_direct_row_without_the_producer_role` documenta que a base, sozinha, não verifica o papel.

Classificação: validado na fronteira da API.

Limitações: um `INSERT` directo na base pode contornar o papel. A fronteira do protótipo é a API. Não é defeito bloqueador.

## RB-03

Descrição: Oferta referencia produto do mesmo actor; operações cruzadas entre actores são rejeitadas.

Componente: ofertas.

Código: `backend/app/offers.py`; chave estrangeira composta `fk_offers_product_owner` na migração `0004_offers`.

Endpoints: `POST /actors/{actor_id}/offers` e leituras filtradas pelo actor da rota.

Interface: o selector lista produtos desse actor.

Testes: `test_product_of_another_actor_is_rejected`, `test_database_enforces_the_same_owner`, `test_offer_of_another_actor_is_not_disclosed`.

Classificação: validado.

Limitações: nenhuma no texto da regra.

## RB-04

Descrição: Publicação de oferta exige preço >= 0, quantidade >= 0, moeda, unidade e estado de disponibilidade explícitos. Zero é valor conhecido, não quantidade desconhecida.

Componente: ofertas.

Código: validação em `backend/app/offers.py`; `CHECK` `ck_offers_price`, `ck_offers_quantity`, `ck_offers_currency` e `ck_offers_published`.

Endpoints: `POST .../publish` e `PATCH` de oferta que já esteja publicada.

Interface: o formulário mostra a recusa da API.

Testes: `test_published_offer_must_remain_valid`, `test_invalid_offer_input_is_rejected`; percurso E2E de publicação inválida.

Classificação: validado.

Limitações: não há catálogo fechado de moedas nem de unidades. A SRS não o exige. Preço e quantidade viajam como texto decimal.

## RB-05

Descrição: Oferta com quantidade zero não pode aparecer como disponível; rascunhos podem ser incompletos.

Componente: ofertas.

Código: `backend/app/offers.py`; `CHECK` `ck_offers_quantity_availability`.

Endpoints: criação de rascunho e publicação.

Interface: rascunho incompleto na ficha privada; publicação recusada quando a combinação é inválida.

Testes: `test_manager_creates_an_incomplete_draft`, `test_draft_can_be_withdrawn_without_publication_data`.

Classificação: validado.

Limitações: nenhuma no texto da regra.

## RB-06

Descrição: Apenas ofertas publicadas e actores/produtos elegíveis aparecem em consulta pública; oferta suspensa/indisponível não pode ser anunciada como disponível.

Componente: descoberta pública.

Código: predicado em `backend/app/public_offers.py`.

Endpoints: `GET /public/offers` e `GET /public/offers/{offer_id}`.

Interface: `available` lê-se Disponível e `unavailable` lê-se Indisponível. Suspensa, retirada e rascunho não entram.

Testes: `test_unavailable_published_offers_stay_visible`, `test_unpublished_states_are_hidden_on_list_and_detail`.

Classificação: validado.

Limitações: a ficha pública inexistente ou inelegível responde 404 na API e HTTP 200 na página Next.js, com o texto «Oferta não encontrada.» É o soft 404, fora dos requisitos numerados.

## RB-07

Descrição: Contacto privado não é publicado; revogação de autorização impede exibição pública posterior.

Componente: contactos e autorizações.

Código: visibilidade `private` na criação, em `backend/app/contacts.py`; predicado público em `backend/app/public_offers.py`.

Endpoints: colecção privada de contactos e `GET /public/offers/{offer_id}/contacts`.

Interface: «Ver contactos» e revogação na ficha do contacto.

Testes: `test_login_email_is_not_copied_and_public_offers_omit_contacts`, `test_committed_revoke_hides_the_contact_before_the_response_finishes`.

Classificação: validado.

Limitações: a revogação retira a exposição nesta plataforma no pedido seguinte. Não apaga cópias feitas fora dela. A secção 10 não promete esse apagamento.

## RB-08

Descrição: Fotografias só são publicadas com declaração de direito de uso; fotografias da FACIM não são importadas automaticamente.

Componente: produtos e projecção pública.

Código: `public_image_ref` e `ck_products_image_rights` em `backend/app/products.py`; migração `0007_coverage_and_image_rights`.

Endpoints: criação e alteração do produto com `image_ref` e `image_use_confirmed`. A oferta pública só recebe a referência quando a declaração coincide com ela.

Interface: caixa «Declaro que possuo os direitos necessários ou autorização para utilizar esta fotografia.»

Testes: `test_photograph_stays_optional_until_a_matching_declaration`, `test_public_photograph_follows_offer_eligibility`, `test_migration_preserves_rows_and_does_not_publish_old_photos`.

Classificação: validado no âmbito do protótipo.

Limitações: a declaração é a afirmação do representante. A aplicação não verifica a titularidade, não inspecciona pessoas identificáveis e não lê contactos impressos na imagem. Esses pontos da secção 10 não estão automatizados. Não existe importação da FACIM.

## RB-09

Descrição: Condições de entrega são informação comercial, não prestação ou garantia de transporte.

Componente: ofertas.

Código: campo de texto `delivery_terms`. Não há entidade de transporte.

Endpoints: os da oferta. Não há endpoint de frete.

Interface: texto na ficha, sem promessa logística.

Testes: os de RF-06. A inspecção de `backend/app/main.py` não mostra domínio de expedição.

Classificação: validado.

Limitações: nenhuma no texto da regra.

## RB-10

Descrição: Representante só altera recursos de actor para o qual mantém autorização válida.

Componente: autorização por pedido.

Código: `actor_for_manage` e `actor_for_read` em `backend/app/authorization.py`.

Endpoints: todas as rotas privadas sob `/actors/{actor_id}`.

Interface: perda de acesso esconde a gestão no pedido seguinte.

Testes: `test_revoked_access_blocks_read_and_update`, `test_revocation_after_the_token_applies_on_the_next_request`.

Classificação: validado para pedidos sequenciais.

Limitações: a corrida entre uma revogação e uma escrita já aberta noutro pedido foi registada como risco residual no I8.0. Nas transições de oferta, o I8.2 bloqueia a linha da oferta e relê a representação. Não ficou um defeito observado. Não é bloqueador do I9.

## RNF-01

Descrição: Interface responsiva e navegável em largura móvel de 360 px e desktop de 1280 px; testar fluxos essenciais.

Componente: interface Next.js.

Código: CSS em `frontend/app/globals.css` e páginas da descoberta e da área privada.

Endpoints: não aplicável.

Interface: login, actores, produtos, ofertas, descoberta e contactos.

Testes: `setViewportSize` nos specs E2E desses fluxos. Suites I8.3 aprovadas.

Classificação: validado para o critério escrito de 360 px e 1280 px.

Limitações: não é auditoria visual nova neste incremento. A SRS não fixa limiar numérico de tempo.

## RNF-02

Descrição: Mensagens de erro claras, campos obrigatórios identificados, navegação acessível por teclado.

Componente: formulários da interface.

Código: rótulos e `role=alert` nos formulários; mensagens em `frontend/lib/errors.ts`. O 422 da API não devolve o valor rejeitado.

Endpoints: não aplicável além das respostas de validação.

Interface: login, actor, produto, oferta, contacto e pesquisa pública.

Testes: teclado em `frontend/e2e/auth.spec.ts`, `actors.spec.ts`, `public-offers.spec.ts`, `products.spec.ts`, `offers.spec.ts` e `contacts.spec.ts`. Evidência `docs/evidencias/I8.3/validacao-rnf02.md`.

Classificação: validado para o texto da SRS.

Limitações: não é conformidade WCAG. A SRS não a pede.

## RNF-03

Descrição: Hash seguro de palavras-passe, sessões protegidas, autorização verificada no servidor.

Componente: contas, sessão e autorização.

Código: Argon2id em `backend/app/passwords.py`; JWT HS256 em `backend/app/tokens.py`; cookie `HttpOnly` e `SameSite=Lax` em `frontend/lib/session.ts`.

Endpoints: `POST /auth/login`, `GET /auth/me`, e a autorização em cada rota privada.

Interface: `/login` e middleware.

Testes: `backend/tests/test_auth.py`, `test_jwt_secret_is_required_and_has_no_default`; `frontend/e2e/auth.spec.ts`.

Classificação: validado.

Limitações: terminar a sessão não revoga o JWT. O Compose local não termina TLS. São limites aceites do protótipo, não falhas do texto verificado.

## RNF-04

Descrição: Integridade referencial e isolamento de dados por actor; validação de entradas no servidor.

Componente: persistência e validação.

Código: chaves estrangeiras `ON DELETE RESTRICT` nas migrações `0002` a `0008`; modelos Pydantic com `extra=forbid`.

Endpoints: a validação está nas rotas de escrita.

Interface: mensagens de rejeição.

Testes: `test_database_restricts_delete_while_a_link_exists`, `test_database_enforces_the_same_owner`, testes de isolamento de contactos e de gestores.

Classificação: validado.

Limitações: o papel `producer` não é um `CHECK` da base. O isolamento exigido pelo requisito está na API e nas chaves que separam actores.

## RNF-05

Descrição: Testes automatizados de autenticação, papéis, representação, CRUD, publicação, pesquisa e revogação; guardar evidências de execução.

Componente: suites e evidências.

Código: `backend/tests`, `frontend/e2e`, `docs/evidencias`.

Endpoints: não aplicável.

Interface: não aplicável.

Testes: no I8.3, 280 testes de backend em duas execuções e 68 testes Playwright em duas execuções consecutivas. Evidências em `docs/evidencias/I8.3/pytest-resultados.txt` e `playwright-resultados.txt`. Este incremento não os repetiu, porque não alterou produção, testes nem configuração com efeito no comportamento já medido.

Classificação: validado.

Limitações: a taxa de cobertura não é critério da SRS. As categorias pedidas existem e as evidências estão conservadas.

## RNF-06

Descrição: Minimização de dados pessoais, consentimento por finalidade e possibilidade de ocultar contactos públicos.

Componente: projecção pública, autorizações e avisos.

Código: projecção sem identificadores internos em `backend/app/public_catalog.py`; finalidade `commercial_discovery` e aviso `v1` em `backend/app/publication.py`; avisos de texto livre em `frontend/lib/public-offer-view.ts`.

Endpoints: `GET /public/offers/{offer_id}/contacts` devolve só canal e valor dos contactos com autorização vigente. A revogação oculta o contacto no pedido seguinte.

Interface: avisos nos formulários e confirmação da concessão.

Testes: `test_public_disclosure_follows_eligibility_and_authorization`, `test_logs_and_openapi_do_not_expose_contact_values_or_internal_fields`. O I8.2 retirou a query do access log inspeccionado.

Classificação: parcial. Não foi promovido a validado.

Limitações que mantêm o parcial:

- A SRS, secção 10, pede um calendário de retenção antes de testes com dados reais. Esse calendário não existe. Q-06 permanece parcialmente aberta e fora deste denominador.
- O texto livre e a fotografia podem conter dados pessoais. A aplicação avisa e não os detecta.
- A secção 10 pede verificação de pessoas identificáveis e de contactos impressos na imagem. Isso não está automatizado.

O que já está satisfeito, e não chega para fechar o requisito: projecção mínima, finalidade única, aviso versionado, ocultação por revogação e redução do que entra nos logs inspeccionados.

## RNF-07

Descrição: Registar eventos relevantes de autorização e alterações de publicação sem expor dados sensíveis em logs.

Componente: histórico de autorizações e eventos de oferta.

Código: `publication_authorizations` em `backend/app/publication.py`; `OfferStatusEvent` em `backend/app/offers.py`; migração `0008_offer_status_events`. O access log da API omite a query e segmentos livres.

Endpoints: o histórico de autorizações consulta-se na rota privada do contacto. Não há endpoint de consulta dos eventos de oferta. A demonstração é a tabela.

Interface: histórico na ficha do contacto. Sem painel de auditoria. A SRS não o exige.

Testes: `backend/tests/test_i82_offer_events.py` (`test_status_events_follow_the_effective_transitions`, `test_access_path_drops_the_query_and_free_text`); testes de histórico em `backend/tests/test_publication.py`.

Classificação: validado no âmbito do protótipo académico.

Limitações: a frase «sem expor dados sensíveis» fica demonstrada nos destinos inspeccionados no I8.2, não em todos os logs imagináveis. Quem executa SQL na consola continua a ver o detalhe do erro no cliente. O evento de oferta não copia preço, descrição nem contactos.
