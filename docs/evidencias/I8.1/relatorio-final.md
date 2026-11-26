# Relatório final — I8.1

## 1. Baseline

HEAD de `main`: `d8338ac`, «docs(i8.0): reconcile SRS requirements and
establish final implementation roadmap». O commit anterior é
`045a634`. O ramo estava alinhado com `origin` no início do incremento.

Antes deste trabalho: Alembic `0006_publication_authorizations`;
266 testes de backend; Playwright 64 testes, 61 aprovados e 3 falhados;
PostgreSQL 5435; API 8010; frontend 3010.

## 2. Solução

`actors.coverage_area` é texto opcional, distinto da localização geral.
Entra nos contratos privados e na ficha pública da oferta elegível.

A fotografia continua em `image_ref`, como URL HTTPS. Três colunas
guardam a declaração do representante para essa referência. A oferta
pública mostra a imagem só quando já é elegível, a referência é válida
e a declaração cobre essa referência. Sem isso, a oferta segue sem
fotografia.

## 3. Decisões

Estão em `decisoes-tecnicas.md`. A peça que ultrapassa o uso corrente
das tecnologias é a fotografia indisponível: o erro pode acontecer
antes de o `onError` do React ficar ligado, e `display: block` da
classe anula o efeito visual do atributo `hidden`. O componente
confirma `complete` e `naturalWidth` depois de montar e, em falha,
retira o elemento.

## 4. Ficheiros

Criados:

- `backend/alembic/versions/0007_coverage_and_image_rights.py`
- `backend/tests/test_i81_coverage_image.py`
- `frontend/components/public-photo.tsx`
- `frontend/e2e/i81-cobertura.spec.ts`
- `docs/evidencias/I8.1/` e as quatro capturas em `capturas/`

Alterados no backend: `identity.py`, `actor_roles.py`, `actors.py`,
`products.py`, `catalog.py`, `public_offers.py`, `public_catalog.py`,
e os testes de fundação, identidade, autorização, papéis, produtos e
ofertas públicas, apenas para o contrato e para o esquema migrado.

Alterados no frontend: vista, cliente e formulários de actores e
produtos; `errors.ts`; `offer-public.tsx`; `globals.css`;
`public-offer-view.ts`; `public-offers.ts`; `actors.spec.ts`,
`products.spec.ts` e `public-offers.spec.ts`, para os campos novos e
para referências HTTPS nos dados de teste.

Não foram alterados a SRS, os UML, as evidências anteriores,
`_srs_extract.txt` nem `docs/srs/`.

## 5. Migração

Ver `migracao.txt`. A base de desenvolvimento está em
`0007_coverage_and_image_rights`. Não foi feito downgrade nela. A
prova de upgrade, downgrade e novo upgrade correu numa base
descartável, dentro do pytest, e apagou essa base.

## 6. Contratos

Ver `contratos-api.md`.

## 7. Interface

O registo e a edição do actor têm «Área de actuação», depois da
localização, com a nota de que os campos são independentes. A ficha
mostra o valor ou «não indicada».

O produto tem «Fotografia (HTTPS)» e a caixa «Declaro que possuo os
direitos necessários ou autorização para utilizar esta fotografia.».
Começa desmarcada, desactiva-se sem URL e desmarca-se se o URL mudar.
A ficha diz se a declaração está registada para a fotografia actual.
O texto da caixa explica que a aplicação regista a afirmação e não
verifica direitos de autor, e que a oferta pode ser publicada sem
fotografia.

A oferta pública mostra a imagem e, à parte, a localização geral e a
área de actuação. As capturas usam dados sintéticos:

- `capturas/area-de-actuacao.png`
- `capturas/fotografia-e-declaracao.png`
- `capturas/declaracao-registada.png`
- `capturas/oferta-publica.png`

## 8. Segurança e privacidade

Ver `seguranca-privacidade.md`.

## 9. Testes

Pytest: 273 passed em 55,69 s, com `RUN_DB_TESTS=1`. Ver
`pytest-resultados.txt`.

Playwright oficial: 65 testes, 61 aprovados, 4 falhados, 8,9 min.
Três falhas são as de `contacts.spec.ts` do I8.0. A quarta,
`offers.spec.ts:292`, ficou na lista «A carregar as ofertas.» durante
a suite e passou em 42,5 s quando repetida isolada. Não é defeito
funcional do I8.1. O percurso `i81-cobertura.spec.ts` passou na
execução oficial. Ver `playwright-resultados.txt`.

Build e contentores: `build-compose.txt`.

## 10. Rastreabilidade

RF-01, RF-02 e RB-08 ficam proponíveis como validados no âmbito do
protótipo. Os limites estão em `rastreabilidade.md`.

## 11. Limitações

Não há upload, processamento de imagem, verificação jurídica de
direitos, análise de pessoas ou de texto dentro da fotografia, nem
importação da FACIM. O anfitrião da imagem vê o IP e o agente do
visitante. Uma imagem já carregada pode permanecer na cache do
navegador. A área de actuação não tem comprimento máximo, como os
outros textos do actor. O diagrama UML não foi actualizado. As três
falhas E2E de contactos e o teste temporal de publicação ficam para
o I8.3. I8.2, I8.4 e I9 não foram iniciados.

## 12. Git

HEAD continua `d8338ac`. Não houve commit nem push. O trabalho está
na árvore. `_srs_extract.txt` e `docs/srs/` permanecem por versionar
e fora do âmbito.
