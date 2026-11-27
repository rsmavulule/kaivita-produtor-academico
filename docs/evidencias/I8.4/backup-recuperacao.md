# Backup e recuperação — I8.4

Instrumento: `pg_dump` em formato custom, sem donos nem privilégios,
executado no contentor `kaivita-avaliacao-db-1`. O ficheiro fica em
`avaliacao-backups/`, fora do Git. Não se copiou a base de
desenvolvimento.

## Prova de leitura do dump

Dump `kaivita-avaliacao-20261126-181951.dump`, 50943 bytes, tirado
depois de `preparar` e antes de `verificar`.

`recuperar` sem `-Sobrepor` restaurou-o em `kaivita_avaliacao_restauro`,
no mesmo servidor de avaliação, e apagou essa base no fim.

Contagens do restauro lateral:

```text
users=3 actors=2 products=2 offers=2 contacts=2 authorizations=1 events=1 alembic=0008_offer_status_events
```

A base em uso, já com o smoke, ficou por alterar nessa prova:

```text
users=3 actors=2 products=3 offers=3 contacts=3 authorizations=2 events=4 alembic=0008_offer_status_events
```

## Prova de substituição

`recuperar -Sobrepor -Confirmar` com o mesmo dump parou a API e a
interface, terminou as ligações, recriou `kaivita_avaliacao`,
restaurou e voltou a subir os serviços. A saúde respondeu e a revisão
ficou `0008_offer_status_events`. As contagens voltaram às do dump
limpo, incluindo 2 produtos, 2 ofertas, 2 contactos, 1 autorização
e 1 evento.

`persistencia` reiniciou os três contentores. A oferta pública de
demonstração continuou consultável. As contagens mantiveram-se.

## Reposição do volume

`repor -Confirmar` removeu o volume `kaivita-avaliacao-pgdata` e
confirmou que `kaivita-produtor-academico_pgdata` continuava presente.
A base nova subiu vazia, com zero contas, já em
`0008_offer_status_events`. `preparar` recriou o conjunto sintético:

```text
users=3 actors=2 products=2 offers=2 contacts=2 authorizations=1 events=1 alembic=0008_offer_status_events
```

Os identificadores são novos. O dump da prova anterior não corresponde
a estes identificadores. Foi retirado da pasta para não ser restaurado
por engano. O dump que corresponde ao ambiente deixado no ar é
`kaivita-avaliacao-20261126-182423.dump`, 50944 bytes.

A base de desenvolvimento, relida no fim, continuou
`kaivita|55|173|92|40|2|0008_offer_status_events`.
