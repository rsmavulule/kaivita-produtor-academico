# RNF-02 — I8.3

Texto da SRS, secção 7: «Mensagens de erro claras, campos obrigatórios
identificados, navegação acessível por teclado.»

Não é uma auditoria WCAG. Os testes de viewport que já existiam
mantêm-se.

## O que já havia

Teclado no login, na criação de actor e na pesquisa pública. Rótulos,
`role=alert` e mensagens de validação sem eco do valor rejeitado. O foco
visível é `outline: 2px solid` em `:focus-visible`.

## O que esta ronda acrescentou

Três testes, um por formulário. Percorrem Tab e Shift+Tab, confirmam o
rótulo pelo `id` do campo, exigem contorno visível no elemento focado,
activam o botão com Enter, lêem a `validationMessage` nativa do campo
vazio e verificam que Tab sai do botão.

- Contacto: canal e valor, selecção de email, confirmação da divulgação
  com Espaço, alerta «A confirmação explícita é obrigatória.» e
  «Divulgação autorizada».
- Oferta: produto, preço, moeda, quantidade, unidade, disponibilidade e
  condições de entrega. O envio abre a oferta em «Rascunho».
- Produto: nome, descrição, categoria, fotografia e declaração de
  direitos. No ecrã de edição, Enter com o nome em branco mostra
  «Nome inválido.» e o campo aponta para `edit-name-error`.

Execução isolada dos três: 3 aprovados em 1,0 min, a
2026-11-26T15:12:31Z. As duas suites completas, 68 testes cada,
incluíram estes três e passaram. Classificação proposta, só para o
texto da SRS: validado. Não cobre WCAG.
