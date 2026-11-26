# Teste temporal — I8.3

`test_postgres_rejects_invalid_authorizations`, em
`backend/tests/test_publication.py`.

A restrição `ck_publication_authorizations_revocation` exige
`revoked_at >= granted_at` na mesma linha. `granted_at` por omissão é
`CURRENT_TIMESTAMP`. Copiar o `granted_at` de uma linha anterior para o
`revoked_at` de uma linha nova pode falhar, porque a concessão da linha
nova é posterior. A data fixa `2099-01-01` só contornava isso enquanto
o ano do relógio fosse anterior.

A linha histórica passa a inserir `granted_at` e `revoked_at` com o
mesmo `CURRENT_TIMESTAMP` de uma instrução. O PostgreSQL usa um instante
por instrução, por isso os dois valores coincidem. A asserção verifica
que a linha gravada tem `revoked_at >= granted_at`. Os casos de rejeição,
incluindo o de 2020, mantêm-se.

Não depende do ano, não dorme e não altera produção. Não resta
`2099-01-01` no backend. O teste isolado passou em 0,45 s. A suite
completa, 280 testes, passou com esta versão.
