# Correcções — I8.3

Não houve alteração de código de produção. Não se subiu timeout, não se
acrescentou retry, não se usou espera fixa e não se retirou asserção.

## Testes

`frontend/e2e/contacts.spec.ts`

- Depois de «Terminar sessão», o teste espera `/login?motivo=terminada`
  e «Sessão terminada neste browser.» antes de voltar a entrar.
- Publicar, suspender e republicar usam um clique normal e esperam
  `main p.eyebrow` em «Publicada» ou «Suspensa».
- Guardar, revogar, substituir papéis e confirmar arquivo esperam a
  resposta POST e, em seguida, o estado visível: valor do contacto,
  «Sem autorização vigente», caixas de papel ou «Arquivado».
- Novo teste de teclado do contacto, da confirmação e da validação.

`frontend/e2e/offers.spec.ts`

- Novo teste de teclado da oferta e da validação.
- No produto de outro actor, o envio espera o POST e o fim do texto
  «A carregar as ofertas.» antes de afirmar «Produto não encontrado.»

`frontend/e2e/products.spec.ts`

- Novo teste de teclado do produto, da declaração de direitos e da
  mensagem «Nome inválido.» com `aria-describedby`.

`backend/tests/test_publication.py`

- A linha histórica revogada deixa de usar `2099-01-01`. Detalhe em
  `teste-temporal.md`.

## O que não se alterou

`playwright.config.ts` mantém um worker, zero retries, 90 s de teste e
20 s de expectativa. O logout, o middleware e as acções de oferta
ficaram iguais. O soft 404 da ficha pública (HTTP 200 com a mensagem de
oferta indisponível) não foi implementado: a SRS não fixa esse código
e esta autorização não o pedia.
