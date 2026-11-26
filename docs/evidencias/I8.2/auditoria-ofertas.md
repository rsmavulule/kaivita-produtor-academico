# Auditoria das ofertas — I8.2

Tabela `offer_status_events`, migração `0008_offer_status_events`.

Colunas:

- `id`
- `offer_id`, chave estrangeira para `offers.id`, `ON DELETE RESTRICT`
- `previous_status`
- `new_status`
- `performed_by_user_id`, chave estrangeira para `users.id`,
  `ON DELETE RESTRICT`
- `occurred_at`, com fuso horário

Restrições: os dois estados pertencem a `draft`, `published`,
`suspended` e `withdrawn`, e o par tem de ser uma transição que o
ciclo aceita: rascunho ou suspensa para publicada, publicada para
suspensa, ou qualquer um desses três para retirada. Há um índice por
`offer_id`.

O que fica registado, quando a transição é aceite:

- rascunho ou suspensa para publicada
- publicada para suspensa
- publicada, suspensa ou rascunho para retirada

O que não fica registado:

- criação do rascunho
- transição recusada
- pedido sem representação `manage`
- falha no meio da escrita, que desfaz também o estado
- segunda publicação concorrente que encontra a oferta já publicada

Os testes com PostgreSQL confirmaram a correspondência entre o estado
gravado e o par anterior/novo, a conta do operador, o instante, a
ausência de evento na transição inválida e no pedido de leitura, o
rollback conjunto e uma publicação concorrente com um único evento
compatível com o estado final.

A limpeza E2E apaga os eventos das ofertas dos actores exclusivos
dessa execução antes de apagar as ofertas. Se sobrar um evento de uma
conta do manifesto noutro actor, a limpeza pára, como já fazia com as
autorizações de contacto. Actores partilhados continuam de fora.

`PublicationAuthorization` mantém finalidade, versão do aviso, instante
e operador da concessão, instante e operador da revogação, revisão do
contacto e motivo. O modelo não foi alterado.
