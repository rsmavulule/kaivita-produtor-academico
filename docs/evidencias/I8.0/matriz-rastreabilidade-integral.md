Matriz integral de rastreabilidade — SRS v1.1 — I8.0

Metodologia. Uma secção por requisito numerado. Os casos de uso estão
em matriz-casos-de-uso.md e não entram no total de 27. Estado segundo
as categorias do I8.0. «Validado» exige comportamento implementado e
teste que o exerce, no âmbito académico. A execução Playwright desta
ronda não ficou toda verde; onde isso afecta a confiança, a secção
diz qual foi a evidência que ainda sustenta o estado.

Indicadores

| Categoria | Total | Validado | Implementado não validado | Parcial | Pendente | Não aplicável | Fora do âmbito |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| RF | 10 | 8 | 0 | 2 | 0 | 0 | 0 |
| RB | 10 | 9 | 0 | 1 | 0 | 0 | 0 |
| RNF | 7 | 4 | 1 | 2 | 0 | 0 | 0 |
| Total | 27 | 21 | 1 | 5 | 0 | 0 | 0 |

21 + 1 + 5 + 0 + 0 + 0 = 27.

Taxa de validação integral: 21/27. Denominador: os 27 requisitos
numerados. Não inclui casos de uso, entidades, questões nem exclusões.
Não atribui fracção aos parciais.

Taxa de implementação integral: (21+1)/27 = 22/27. Conta apenas
validado e implementado não validado. Os 5 parciais não entram.

Requisitos parcialmente implementados: 5 (RF-01, RF-02, RB-08, RNF-06, RNF-07).

Requisitos numerados com estado pendente: 0.

Exclusões da secção 2 não são linhas desta tabela.

## RF-01

Tipo: RF. Prioridade SRS: Alta. Estado: PARCIAL. Prioridade do trabalho: P1. Incremento: I8.1.

Descrição: Criar, consultar e actualizar perfil de actor com papel produtor; pessoa singular ou organização, localização geral e área de actuação.

Fonte: SRS secção 5, página 3.

Implementação: backend/app/actors.py (create_actor, read_actor, update_actor); backend/app/actor_roles.py (create_represented_actor); backend/app/identity.py classe Actor. ActorUpdate aceita display_name e general_location. Não há coverage_area.

Persistência: tabela actors, migração 0002_identity_access. CHECK de kind, display_name, general_location e status. Sem coluna de área de actuação.

Interface: frontend/app/(privada)/actores/create-form.tsx e actores/[actorId]/edit-forms.tsx. Aviso PUBLIC_FIELD_NOTICE.

Testes: tests/test_actor_roles.py (test_creates_a_person_actor, test_creates_an_organization_actor, test_manager_replaces_actor_roles); tests/test_authorization.py; frontend/e2e/actors.spec.ts. Nenhum teste de área de actuação.

Evidências: docs/evidencias/I2 e I5.2; esta matriz.

Lacuna: campo de área de actuação, distinto da localização geral, no perfil e na projecção pública.

## RF-02

Tipo: RF. Prioridade SRS: Alta. Estado: PARCIAL. Prioridade do trabalho: P1. Incremento: I8.1.

Descrição: Criar, editar, arquivar e consultar produtos associados a actor produtor; nome, categoria, descrição e fotografia opcional.

Fonte: SRS secção 5, página 3.

Implementação: backend/app/catalog.py e backend/app/products.py. image_ref é texto opcional. A projecção pública em public_catalog.py classe PublicProduct não inclui image_ref.

Persistência: tabela products, migração 0003_products. CHECK ck_products_image_ref. Sem ficheiro e sem declaração de direitos.

Interface: produtos/novo/create-form.tsx e produtos/[productId]/edit-forms.tsx, campo image_ref. ProductFields inclui o aviso de texto livre.

Testes: tests/test_products.py (test_manager_creates_a_product, test_manager_updates_a_product, test_manager_archives_a_product, test_archive_is_idempotent); frontend/e2e/products.spec.ts. Não há teste de fotografia publicada nem de declaração.

Evidências: I3, I5.3.

Lacuna: a referência não é consultável na oferta pública e não há declaração de uso. Ver RB-08. Não se exige armazenamento de ficheiros.

## RF-03

Tipo: RF. Prioridade SRS: Alta. Estado: VALIDADO. Prioridade do trabalho: nenhuma. Incremento: nenhum.

Descrição: Criar, editar, publicar, suspender e retirar ofertas; preço, moeda, quantidade, unidade e disponibilidade obrigatórios para publicação.

Fonte: SRS secção 5, página 3.

Implementação: backend/app/offer_catalog.py; backend/app/offers.py funções publish_offer, suspend_offer, withdraw_offer. A republicação é publish a partir de suspended. A retirada é terminal.

Persistência: tabela offers, migração 0004_offers. CHECK ck_offers_published e ck_offers_quantity_availability.

Interface: ofertas/nova/create-form.tsx e ofertas/[offerId]/edit-forms.tsx. O botão diz «Republicar» quando o estado é suspended.

Testes: tests/test_offers.py test_lifecycle_follows_the_approved_state_diagram, test_repeated_transition_does_not_write, test_draft_can_be_withdrawn_without_publication_data; frontend/e2e/offers.spec.ts «suspender, republicar e retirar», aprovado nesta ronda.

Evidências: I4, I5.4.

Lacuna: nenhuma funcional no âmbito do requisito. A nota do diagrama sobre aprovar a republicação está ultrapassada pela implementação testada. Não é lacuna de código.

## RF-04

Tipo: RF. Prioridade SRS: Alta. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Pesquisar ofertas públicas por texto e filtrar por categoria; localização geral quando disponível.

Fonte: SRS secção 5, página 3.

Implementação: backend/app/public_offers.py funções normalize_search_text, _filtered, public_offer_page; backend/app/public_catalog.py read_public_query.

Persistência: sem tabela nova. Lê products.name, products.description, products.category e actors.general_location.

Interface: frontend/app/(descoberta)/page.tsx, ofertas/page.tsx, components/offer-search.tsx.

Testes: tests/test_public_offers.py test_search_combines_text_category_and_location, test_normalization_folds_portuguese_accents_and_escapes_wildcards, test_null_location_stays_visible_until_a_location_filter_is_used, test_ordering_pagination_and_bounds; frontend/e2e/public-offers.spec.ts, aprovados nesta ronda.

Evidências: I6.1, I6.2.

Lacuna: nenhuma no texto de RF-04. A pesquisa não inclui área de actuação, porque esse campo não existe e RF-04 fala de localização geral.

## RF-05

Tipo: RF. Prioridade SRS: Alta. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Apresentar localização geral e apenas contactos comerciais autorizados pelo actor.

Fonte: SRS secção 5, página 3. A secção 10 admite titular ou representante habilitado.

Implementação: producer.general_location na oferta pública. Contactos só em GET /public/offers/{id}/contacts, predicado em public_offers._contact_statement. A ficha não os inclui no primeiro carregamento.

Persistência: actors.general_location; public_contacts; publication_authorizations, migrações 0005 e 0006.

Interface: components/offer-public.tsx e components/public-contacts.tsx. O visitante carrega em «Ver contactos».

Testes: tests/test_public_offers.py test_published_available_offer_is_public_without_authentication; tests/test_publication.py test_public_disclosure_follows_eligibility_and_authorization, test_logs_and_openapi_do_not_expose_contact_values_or_internal_fields; frontend/e2e/contacts.spec.ts. O percurso de revogação do visitante passou na repetição isolada e falhou na passagem completa. Os testes de API passaram. O estado validado apoia-se na API e nos percursos E2E que passaram, não na passagem completa do Playwright.

Evidências: I6.1, I6.2, I7.2, I7.3.

Lacuna: nenhuma no comportamento especificado. O consentimento do titular permanece em Q-06 e RNF-06, não retira o cumprimento operacional de RF-05.

## RF-06

Tipo: RF. Prioridade SRS: Média. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Registar e apresentar condições informativas de entrega, sem cálculo ou contratação de frete.

Fonte: SRS secção 5, página 4.

Implementação: offers.delivery_terms em offers.py e offer_catalog.py. Sai na oferta pública. Não há cálculo.

Persistência: coluna delivery_terms, CHECK de texto vazio, migração 0004.

Interface: formulário da oferta e ficha pública. Texto «Condições de entrega não indicadas» quando falta.

Testes: tests/test_offers.py e tests/test_public_offers.py; e2e/offers.spec.ts e e2e/public-offers.spec.ts «o visitante acompanha a publicação, a alteração e a retirada», aprovado nesta ronda.

Evidências: I4, I6.2.

Lacuna: nenhuma. RB-09 reforça que o texto não é garantia de transporte.

## RF-07

Tipo: RF. Prioridade SRS: Alta. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Permitir consulta pública sem autenticação apenas de recursos publicados.

Fonte: SRS secção 5, página 3.

Implementação: rotas públicas sem dependência de get_current_user. Predicado _eligible: oferta published, produto active, actor active, papel producer. Suspensa, retirada e rascunho não aparecem. Indisponível publicada aparece como indisponível, não como disponível.

Persistência: estados em offers, products e actors. Sem coluna de elegibilidade.

Interface: /, /ofertas, /ofertas/[offerId]. Sem sessão obrigatória.

Testes: test_published_available_offer_is_public_without_authentication, test_unpublished_states_are_hidden_on_list_and_detail, test_archiving_the_product_hides_the_offer_without_changing_it, test_inactive_actor_is_hidden_from_public_discovery, test_losing_and_restoring_the_producer_role, test_revoked_representation_does_not_hide_the_public_offer. E2E de descoberta aprovado nesta ronda. O E2E de elegibilidade no spec de contactos foi instável; a API cobriu o predicado.

Evidências: I6.1, I6.2.

Lacuna: nenhuma para o requisito numerado. Catálogo independente de actores e produtos: ver lacunas-funcionais.md. Não é pendência deste RF.

## RF-08

Tipo: RF. Prioridade SRS: Alta. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Autenticar utilizadores e impedir alteração de dados de actores sem representação autorizada.

Fonte: SRS secção 5, página 3. Secção 4: a API verifica o acesso ao actor, não só o identificador do cliente.

Implementação: backend/app/auth.py login e me; backend/app/authorization.py actor_for_read e actor_for_manage; cookie em frontend/lib/session.ts.

Persistência: users, user_actor_access, migração 0002.

Interface: /login, middleware, área /actores.

Testes: tests/test_auth.py, tests/test_authorization.py (test_revoked_access_blocks_read_and_update, test_user_without_access_cannot_reach_the_actor, test_unauthorized_actor_returns_the_same_404); e2e/auth.spec.ts, aprovado nesta ronda, incluindo terminar sessão.

Evidências: I1.2, I1.3, I5.1.

Lacuna: nenhuma no requisito. O JWT continua válido até expirar depois do logout. Isso está em RNF-03 como limitação aceite, não como falha de RF-08: a alteração seguinte sem cookie ou com conta desactivada é recusada.

## RF-09

Tipo: RF. Prioridade SRS: Alta. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Permitir associação de um actor a múltiplos papéis comerciais sem duplicar identidade.

Fonte: SRS secção 5, página 3.

Implementação: backend/app/actor_roles.py replace_actor_roles; backend/app/roles.py. Catálogo producer, buyer, partner.

Persistência: actor_roles com chave primária (actor_id, role_id). Seed idempotente em identity.seed_commercial_roles. Migração 0002.

Interface: ficha do actor, substituição de papéis.

Testes: test_one_actor_can_hold_several_roles, test_producer_role_does_not_grant_manage, test_replacing_roles_with_the_same_set_is_idempotent; e2e/actors.spec.ts.

Evidências: I2, I5.2.

Lacuna: nenhuma.

## RF-10

Tipo: RF. Prioridade SRS: Alta. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Permitir registar, consultar e revogar autorização para publicação de contactos; ocultar contacto após revogação.

Fonte: SRS secção 5, página 3. Secção 10: granularidade por canal e finalidade, data e versão do aviso, evidência mínima conservada.

Implementação: backend/app/publication.py grant_authorization, revoke_authorization, revoke_current_authorization; backend/app/publication_catalog.py. A alteração efectiva e a desactivação revogam.

Persistência: publication_authorizations, migração 0006. Índice único parcial de autorização vigente. CHECK de revogação. Sem coluna value.

Interface: contactos/[contactId]/page.tsx e forms.tsx. Histórico, confirmação desmarcada, revogação.

Testes: test_grant_stores_one_current_authorization_without_the_contact_value, test_history_revoke_and_a_later_grant, test_effective_change_revokes_and_invalid_change_does_not, test_deactivation_revokes_once_and_leaves_the_contact_private, test_committed_revoke_hides_the_contact_before_the_response_finishes. E2E: autorização, repetição sem nova linha e histórico passaram na execução completa. O percurso do visitante depois da revogação falhou nessa execução e passou na repetição isolada.

Evidências: I7.1, I7.2, I7.3.

Lacuna: nenhuma no requisito operacional. Q-06 continua aberta quanto ao enquadramento legal.

## RB-01

Tipo: RB. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: ActorRole é único por par actor/papel; papéis comerciais não substituem permissões.

Fonte: secção 6, página 4.

Implementação: chave primária de ActorRole; authorization.py não consulta o papel para decidir manage, excepto a regra própria de producer em produtos e ofertas.

Persistência: actor_roles. Migração 0002.

Interface: a gestão depende de access_level, não do papel.

Testes: test_duplicate_roles_are_rejected, test_producer_role_does_not_grant_manage.

Evidências: I1.3, I2.

Lacuna: nenhuma.

## RB-02

Tipo: RB. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Produto e oferta têm actor proprietário; só actor com papel produtor pode publicar oferta.

Fonte: secção 6, página 4.

Implementação: owner_actor_id atribuído no servidor. require_producer_role em products.py e offers.py. A publicação recusa actor sem producer.

Persistência: FK para actors. A base não verifica o papel. Um INSERT directo pode contornar a API. A fronteira do sistema é a API.

Interface: botões de escrita só com manage e producer.

Testes: test_actor_without_producer_role_cannot_write_offers, test_database_accepts_a_direct_row_without_the_producer_role (documenta o limite da base), test_producer_role_does_not_grant_access_to_another_actor.

Evidências: I3, I4.

Lacuna: o CHECK em falta na base é P3, não falha do requisito na API.

## RB-03

Tipo: RB. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Oferta referencia produto do mesmo actor; operações cruzadas entre actores são rejeitadas.

Fonte: secção 6, página 4.

Implementação: offers.create_offer recusa produto de outro actor. offer_for_actor filtra pelo actor da rota.

Persistência: fk_offers_product_owner sobre (product_id, owner_actor_id). Migração 0004.

Interface: o selector de produto lista os do actor.

Testes: test_product_of_another_actor_is_rejected, test_database_enforces_the_same_owner, test_offer_of_another_actor_is_not_disclosed.

Evidências: I4.

Lacuna: nenhuma.

## RB-04

Tipo: RB. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Publicação exige preço >= 0, quantidade >= 0, moeda, unidade e disponibilidade explícitos. Zero é valor conhecido.

Fonte: secção 6, página 4.

Implementação: offers._publishable. Decimais em texto, não ponto flutuante.

Persistência: ck_offers_price, ck_offers_quantity, ck_offers_currency, ck_offers_published.

Interface: a API recusa e a mensagem fica no formulário.

Testes: test_published_offer_must_remain_valid, test_invalid_offer_input_is_rejected; e2e «publicar, corrigir e recusar uma oferta inválida».

Evidências: I4, I5.4.

Lacuna: nenhuma. Não há catálogo fechado de moedas nem de unidades. A SRS não o exige.

## RB-05

Tipo: RB. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Quantidade zero não pode aparecer como disponível; rascunhos podem ser incompletos.

Fonte: secção 6, página 4.

Implementação: _reject_zero_available. O rascunho aceita campos nulos. A oferta publicada não.

Persistência: ck_offers_quantity_availability.

Interface: mensagem da API no formulário.

Testes: test_manager_creates_an_incomplete_draft, test_draft_can_be_withdrawn_without_publication_data; e2e da lista vazia e do rascunho.

Evidências: I4.

Lacuna: nenhuma.

## RB-06

Tipo: RB. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Apenas ofertas publicadas e actores/produtos elegíveis aparecem em consulta pública; oferta suspensa ou indisponível não pode ser anunciada como disponível.

Fonte: secção 6, página 4.

Implementação: _eligible. Disponibilidade unavailable continua visível com esse estado. Suspensa não entra na lista nem na ficha.

Persistência: estados existentes. Sem coluna extra.

Interface: AVAILABILITY_LABELS. Ficha inelegível: mensagem de não encontrada, hoje com HTTP 200 na página e 404 na API.

Testes: test_unavailable_published_offers_stay_visible, test_unpublished_states_are_hidden_on_list_and_detail. E2E de descoberta aprovado. E2E de contactos sobre elegibilidade instável nesta ronda; não retira os testes de API.

Evidências: I6.1, I6.2.

Lacuna: nenhuma de comportamento. O soft 404 é qualidade, P2, não falha desta regra.

## RB-07

Tipo: RB. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Contacto privado não é publicado; revogação de autorização impede exibição pública posterior.

Fonte: secção 6, página 5. Secção 10: efeito imediato sobre a exposição nesta plataforma, sem apagar a evidência mínima.

Implementação: visibilidade private na criação. O predicado público exige autorização vigente coerente. A página já aberta conserva o último resultado até nova consulta. Cópias de terceiros não são apagadas. A secção 10 não promete apagá-las.

Persistência: public_contacts.visibility e publication_authorizations.revoked_at.

Interface: «Ver contactos» e «Ocultar contactos».

Testes: test_login_email_is_not_copied_and_public_offers_omit_contacts, test_committed_revoke_hides_the_contact_before_the_response_finishes, test_public_disclosure_follows_eligibility_and_authorization.

Evidências: I7.1, I7.2, I7.3.

Lacuna: nenhuma no requisito. A página aberta é limitação de HTTP já aceite.

## RB-08

Tipo: RB. Estado: PARCIAL. Prioridade do trabalho: P1. Incremento: I8.1.

Descrição: Fotografias só são publicadas com declaração de direito de uso; fotografias da FACIM não são importadas automaticamente.

Fonte: secção 6, página 4. Secção 10, página 7.

Implementação: não há importação. Não há imagem na resposta pública. Não há declaração.

Persistência: só image_ref opcional. Sem registo de declaração.

Interface: campo de texto da referência, sem caixa de declaração.

Testes: a ausência de importação não tem teste próprio, porque não há carga. Não há teste de recusa de publicação sem declaração, porque a publicação da referência não existe.

Evidências: I3. Ausência de funcionalidade registada, não evidência de cumprimento.

Lacuna: declaração explícita e inclusão condicional da referência na projecção pública. Sem armazenamento externo e sem análise automática de pessoas na imagem. Esse último ponto da secção 10 fica limite aceite, não automatismo.

## RB-09

Tipo: RB. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Condições de entrega são informação comercial, não prestação ou garantia de transporte.

Fonte: secção 6, página 4.

Implementação: campo de texto. Sem entidade de transporte, sem preço de frete, sem estado de expedição.

Persistência: delivery_terms.

Interface: texto na ficha. O aviso de publicação não promete logística.

Testes: os de RF-06. Não existe endpoint de frete para testar a ausência; a inspecção do modelo e das rotas em main.py não mostra esse domínio.

Evidências: I4, I6.2.

Lacuna: nenhuma.

## RB-10

Tipo: RB. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Representante só altera recursos de actor para o qual mantém autorização válida.

Fonte: secção 6, página 5.

Implementação: actor_for_manage em cada escrita. Leitura com actor_for_read. Revogação de acesso bloqueia o pedido seguinte.

Persistência: user_actor_access.status. Não há reavaliação dentro da mesma transacção depois do bloqueio do recurso.

Interface: perda de acesso esconde a gestão. Specs de produtos, ofertas, actores e contactos.

Testes: test_revoked_access_blocks_read_and_update, test_revocation_after_the_token_applies_on_the_next_request, test_readers_and_strangers_cannot_cross_authorizations. E2E de isolamento de contactos aprovado nesta ronda.

Evidências: I1.3, I5.5, I7.2.

Lacuna: nenhuma no pedido sequencial. A corrida entre revogação e escrita já aberta é risco potencial, P2, não defeito observado. Ver diagnostico-transaccional.md.

## RNF-01

Tipo: RNF. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Interface responsiva e navegável em 360 px e 1280 px; testar fluxos essenciais.

Fonte: secção 7, página 5.

Implementação: CSS da interface. Sem biblioteca de componentes.

Persistência: não aplicável.

Interface: login, actores, produtos, ofertas, descoberta e contactos.

Testes: setViewportSize nesses specs. O teste de auth afirma que a entrada e o login cabem. Os de contactos a 360 e 1280 correram na parte aprovada da suite, antes das falhas posteriores do mesmo ficheiro.

Evidências: I5.1 a I5.5, I6.2, I7.3. Esta ronda não regravou as capturas históricas.

Lacuna: nenhuma no critério escrito. Não houve medição formal de overflow em todos os ecrãs nesta ronda. Isso não reduz o estado, porque os testes de viewport existem e a maioria correu. Uma auditoria visual nova pode reforçar, não é pendência normativa.

## RNF-02

Tipo: RNF. Estado: IMPLEMENTADO NÃO VALIDADO. Prioridade do trabalho: P2. Incremento: I8.3.

Descrição: Mensagens de erro claras, campos obrigatórios identificados, navegação acessível por teclado.

Fonte: secção 7, página 5.

Implementação: role=alert, rótulos associados, controlos nativos, mensagens estáveis em frontend/lib/errors.ts. O 422 não ecoa o valor.

Persistência: não aplicável.

Interface: formulários privados e pesquisa pública.

Testes: teclado em auth.spec.ts, actors.spec.ts (criação) e public-offers.spec.ts. Mensagens em vários specs. Não há percurso de teclado de produto, oferta nem contacto.

Evidências: I5.1 a I5.4, I6.2. Insuficiente para os três formulários em falta.

Lacuna: três testes de teclado, um por formulário. Sem auditoria WCAG, que a SRS não pede.

## RNF-03

Tipo: RNF. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Hash seguro de palavras-passe, sessões protegidas, autorização verificada no servidor.

Fonte: secção 7, página 5.

Implementação: Argon2id em passwords.py. JWT HS256 em tokens.py. Cookie HttpOnly e SameSite=Lax. Secure conforme o protocolo observado. Autorização em cada pedido. Same-origin em origin.ts.

Persistência: users.password_hash. O token não é guardado na base.

Interface: login e middleware.

Testes: tests/test_auth.py, tests/test_foundation.py test_jwt_secret_is_required_and_has_no_default; e2e/auth.spec.ts, incluindo cookie Secure, origem e token expirado, aprovados nesta ronda.

Evidências: I1.2, I5.1.

Lacuna: nenhuma no texto. Limitação aceite: logout não revoga o JWT; não há TLS no Compose local.

## RNF-04

Tipo: RNF. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Integridade referencial e isolamento de dados por actor; validação de entradas no servidor.

Fonte: secção 7, página 5.

Implementação: validação Pydantic e funções de domínio. FKs ON DELETE RESTRICT. Isolamento por actor da rota e por representação.

Persistência: migrações 0002 a 0006. Chaves compostas de produto, oferta, contacto e autorização.

Interface: não aplicável além das mensagens de rejeição.

Testes: test_database_restricts_delete_while_a_link_exists, test_database_enforces_the_same_owner, test_a_user_who_represents_both_actors_cannot_cross_contacts, test_managers_are_isolated_between_actors.

Evidências: I1 a I7.2. Pytest desta ronda, 266 aprovados.

Lacuna: papel producer não está num CHECK. P3. Não invalida o isolamento nem a integridade referencial que o requisito nomeia.

## RNF-05

Tipo: RNF. Estado: VALIDADO. Prioridade: nenhuma.

Descrição: Testes automatizados de autenticação, papéis, representação, CRUD, publicação, pesquisa e revogação; guardar evidências de execução.

Fonte: secção 7, página 5.

Implementação: backend/tests e frontend/e2e. Evidências em docs/evidencias, incluindo esta pasta.

Persistência: não aplicável.

Interface: não aplicável.

Testes: os 266 de API passaram. Os 64 de browser existem. Nesta ronda, 61 passaram na execução completa. A evidência da falha está em playwright-resultados.txt. O requisito pede os testes e a conservação da evidência, não uma taxa de cobertura. As categorias pedidas existem: autenticação, papéis, representação, CRUD, publicação, pesquisa e revogação.

Evidências: I0 a I7.3 e I8.0.

Lacuna: a reprodução do verde de browser desta ronda falhou em 3 testes. Isso é dívida de fragilidade, P2, não ausência dos testes. Não se classifica o requisito como parcial por uma execução instável de testes que existem.

## RNF-06

Tipo: RNF. Estado: PARCIAL. Prioridade do trabalho: P2 para o access log; a retenção permanece Q-06. Incremento: I8.2.

Descrição: Minimização de dados pessoais, consentimento por finalidade e possibilidade de ocultar contactos públicos.

Fonte: secção 7, página 5. Secção 10, páginas 6–7.

Implementação: projecção pública mínima; finalidade única; aviso v1; revogação e desactivação; avisos de texto livre. Sem calendário de retenção. Sem prova de consentimento do titular.

Persistência: autorização sem o valor do contacto.

Interface: avisos nos formulários e na concessão.

Testes: test_public_disclosure_follows_eligibility_and_authorization, test_logs_and_openapi_do_not_expose_contact_values_or_internal_fields. Os logs de aplicação não levam o valor. O access log do Uvicorn não foi reconfigurado.

Evidências: I7.2, I7.3, diagnostico-seguranca-privacidade.md.

Lacuna: omitir a query no access log. Documentar, sem inventar prazo, que a avaliação usa dados sintéticos. Não censurar texto livre por heurística.

## RNF-07

Tipo: RNF. Estado: PARCIAL. Prioridade do trabalho: P1. Incremento: I8.2.

Descrição: Registar eventos relevantes de autorização e alterações de publicação sem expor dados sensíveis em logs.

Fonte: secção 7, página 5.

Implementação: publication_authorizations regista concessão e revogação, operadores, instantes, motivo, sem o valor. As transições de oferta alteram offers.status e não escrevem evento.

Persistência: migração 0006. Sem tabela de eventos de oferta.

Interface: histórico na ficha do contacto. Sem histórico de publicação da oferta.

Testes: test_history_revoke_and_a_later_grant e test_authorization_schema_matches_the_model. Não há teste de evento de publish, suspend ou withdraw.

Evidências: I7.2 historico-auditoria.txt. A lacuna mantém-se.

Lacuna: registo append-only da transição de oferta, com actor, oferta, estado anterior, estado novo, operador e instante. Sem copiar preço, descrição nem contactos. Prioridade P1 porque o requisito numerado pede as alterações de publicação e elas não estão registadas.
