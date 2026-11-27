# Reconciliação UML — I8.4

Fonte: diagramas em `docs/srs/diagramas`, lidos no I8.0, e a implementação
no HEAD `ba62f25`. Os diagramas não foram alterados neste incremento.
O diagrama de classes é modelo conceptual. As tabelas são o modelo físico.

## O que passou a existir depois do I8.0

| Elemento | No diagrama | Na implementação | Leitura |
| --- | --- | --- | --- |
| `coverage_area` | Ausente no diagrama de classes. A SRS pede área de actuação em RF-01. | Coluna `actors.coverage_area`, distinta de `general_location`, migração `0007_coverage_and_image_rights`. Entra na criação, na alteração e na ficha pública. | O código segue a SRS. O diagrama ficou atrás dos dois. Não é incumprimento da implementação. |
| Declaração de direitos da fotografia | O diagrama tem `imageRef`. Não tem declaração. | `image_ref`, `image_rights_ref`, `image_rights_declared_at`, `image_rights_declared_by` e `CHECK ck_products_image_rights`. A referência pública só sai se a declaração for da mesma referência. | Extensão física justificada por RB-08. O diagrama conceptual não a mostra. |
| `OfferStatusEvent` | Ausente. O diagrama de estados mostra as transições, não o rasto. | Tabela `offer_status_events`: oferta, estado anterior, estado novo, operador e instante. Sem preço, texto ou contacto. Migração `0008_offer_status_events`. | Registo físico de RNF-07. Não muda o ciclo da oferta. |
| Histórico de autorizações | `PublicationAuthorization` conceptual, e uma FK única em `PublicContact`. | Tabela `publication_authorizations` com contacto, revisão, canal, finalidade, aviso, operadores, instantes e motivo. Sem o valor do contacto. Índice único parcial da autorização vigente. | A FK única não guardaria revogação nem histórico. A divergência já estava justificada no I8.0 e mantém-se. |

## Integridade

Implementado na base e alinhado com o desenho:

- Par actor/papel único pela chave de `actor_roles`.
- Oferta do mesmo dono do produto, pela chave estrangeira composta.
- Preço, quantidade, moeda e campos de publicação, por `CHECK`.
- Quantidade zero com disponibilidade `available`, recusada por `CHECK`.
- Autorização revogada com motivo, e no máximo uma autorização vigente por contacto.
- Transições de oferta permitidas, por `CHECK` em `offer_status_events`.
- Apagar um registo ainda referenciado é recusado (`ON DELETE RESTRICT`).

Diferença justificada, já conhecida:

- O papel `producer` é exigido pela API. A base aceita uma linha directa sem esse papel. A fronteira do protótipo é a API.
- A API recusa um actor sem papéis. A tabela `actor_roles` não impede um actor sem linhas.
- Actor inexistente e actor sem representação respondem o mesmo 404. O diagrama de sequência ainda indica 403 no ramo inválido. Mudar a API para 403 revelaria a existência do recurso.

## Estados das ofertas

O diagrama 07 e o código têm os mesmos quatro estados: rascunho, publicada,
suspensa e retirada. Publicar, suspender, republicar com revalidação e
retirar estão implementados. Retirada não volta atrás. A disponibilidade
é atributo, não estado do ciclo.

A nota do diagrama que diz que a enumeração e a republicação careciam de
aprovação está desactualizada. A republicação é a publicação a partir de
`suspended`, testada desde o I4. Não se editou o diagrama.

## Actualizações recomendadas para a monografia

Não fazer estas alterações nos ficheiros UML deste repositório sem uma
decisão própria. São notas para o texto final:

1. Acrescentar `coverageArea` ao actor no diagrama de classes, distinto de `generalLocation`.
2. Acrescentar a declaração de direitos junto de `imageRef`, ou uma nota de que a publicação da referência depende dessa declaração.
3. Acrescentar `OfferStatusEvent` como rasto das transições, sem atributos comerciais.
4. Manter o histórico de autorizações no lugar da FK única, e dizê-lo na legenda.
5. Substituir o 403 do diagrama de sequência pelo 404 opaco, com a justificação de não revelar o recurso.
6. Retirar, na legenda do diagrama de estados, a nota de que a republicação ainda carece de aprovação.
7. Manter o administrador como figura não numerada, ou escrever que a criação de contas é um comando local e não um caso de uso do protótipo.

Não se recomenda desenhar catálogos públicos separados, backoffice, frete,
encomendas ou armazenamento de ficheiros só para coincidir com leituras
mais largas da SRS. Essas exclusões continuam de fora.
