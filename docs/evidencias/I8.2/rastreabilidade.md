# Rastreabilidade — I8.2

Fontes: SRS v1.1, secções 7, 10 e 11, e o diagnóstico I8.0.
A SRS e os diagramas não foram alterados.

## RNF-07

Texto: registar eventos relevantes de autorização e alterações de
publicação sem expor dados sensíveis em logs.

Estado depois do I8.2. As autorizações de contacto continuam em
`publication_authorizations`, com finalidade, aviso, instantes,
operadores, revisão e motivo, sem o valor. As transições efectivas da
oferta passam a `offer_status_events`, sem conteúdo comercial. Os
destinos de log inspeccionados nesta ronda não mostraram o marcador
sintético da pesquisa nem do caminho inválido. O log de erro da base
deixou de incluir a linha rejeitada.

Classificação proposta: validado no âmbito do protótipo académico.
Limite: a frase «sem expor dados sensíveis» fica demonstrada nos
destinos inspeccionados, não em todos os logs imagináveis. A consola
de quem executa SQL continua a receber o detalhe do erro. Não há painel
de auditoria; a SRS não o exige.

## RNF-06

Texto: minimização de dados pessoais, consentimento por finalidade e
possibilidade de ocultar contactos públicos.

Estado depois do I8.2. A projecção, a finalidade, a ocultação e a
revogação mantêm-se. O aviso de texto livre foi completado. A query
saiu do access log da API. Não há calendário de retenção aprovado.
Não há detecção automática de dados pessoais em texto livre ou em
fotografias.

Classificação: parcial. A lacuna técnica da query no access log fica
fechada. Continuam abertos o texto livre, no sentido em que a aplicação
não o censura, e Q-06.

## Q-06

Continua parcialmente aberta, como na SRS. A proposta está em
`retencao-q06.md`. Não se considera resolvida por existir essa nota.

## Fora deste fecho

I8.3, I8.4 e I9 não foram iniciados. As quatro falhas E2E conhecidas
não foram corrigidas. Na execução oficial, as linhas 76 e 265 de
`contacts.spec.ts` falharam com o sintoma já conhecido; as linhas 198
e 292 passaram. Não ficam declaradas como estáveis. O teste com a data `2099-01-01` não foi alterado.
