Critérios do release candidate académico — proposta

O candidato é uma versão do protótipo para avaliação, não um produto
comercial e não a prova de que o escoamento melhorou.

Condições de entrada em I8.4

RF-01, RF-02 e RB-08 reclassificados para validado, ou uma decisão
escrita do orientador a aceitar o estado actual desses três. Sem essa
decisão, o candidato não fecha.

RNF-07 reclassificado para validado no âmbito académico: eventos de
autorização e eventos de transição de oferta, sem valores de contacto
nem textos livres.

O teste test_postgres_rejects_invalid_authorizations não depende de
uma data constante no futuro.

A suite backend com RUN_DB_TESTS=1 está verde no commit candidato.

A suite Playwright está verde em duas execuções seguidas, com Chromium
1255 encontrado pelo processo e com NO_PROXY a cobrir 127.0.0.1 quando
houver proxy. Sem aumento de timeout e sem retries para obter o verde.

Alembic tem uma só cabeça, aplicada na base de avaliação.

Condições do ambiente

Base de avaliação distinta da base de desenvolvimento. Volume próprio.
Reposição por migrações e pelo conjunto sintético, não por cópia da
base actual.

Dados sintéticos controlados. Nenhuma das 49 contas residuais é
copiada. Nenhuma das 6 contas fora do padrão é copiada. Não se usam
contactos reais.

Pelo menos um percurso demonstrável de ponta a ponta: representante
entra, a oferta publicada é encontrada sem sessão, a localização geral
aparece, a área de actuação aparece se I8.1 a tiver acrescentado, o
contacto autorizado só aparece depois da acção do visitante, o contacto
privado não aparece, suspender ou revogar tira o que a regra manda
tirar na consulta seguinte.

Códigos HTTP da ficha coerentes com a decisão do I8.3. Se o soft 404
for aceite como limitação, a aceitação fica escrita. Não se deixa
implícita.

O README não afirma que a interface de contactos está por fazer.

Condições que não são exigidas

TLS público. Revogação de JWT. Análise de imagens. Censura heurística.
Catálogos independentes, salvo decisão em contrário. Backoffice de
administrador. Encomendas, pagamentos, logística e os restantes itens
da secção 2 da SRS. Prazo legal de retenção. Conformidade jurídica
integral. Avaliação com utilizadores: isso é o I9.

Condições para iniciar o I9, depois do candidato

Versão identificada pelo commit, com as suites da entrada em I8.4
arquivadas.

Ambiente dedicado e reponível, para que um teste automático não apague
o que os participantes viram.

Percursos escritos, curtos, correspondentes a UC-01, UC-02, UC-04,
UC-05, UC-06, UC-07 e UC-08.

Instrumento de recolha separado da base da aplicação.

Consentimento de participação, distinto do aviso de divulgação de
contactos do protótipo.

Registo de dificuldades, de usabilidade e de utilidade percebida,
relacionado com os objectivos da investigação.

Não se afirma, antes nem depois do I9, que o protótipo melhorou o
escoamento, salvo se o desenho do I9 produzir essa evidência. O I8 não
produz.

Saída

O candidato é aceite para o I9 quando as condições de entrada e de
ambiente estão evidentes num directório de evidências do I8.4 e o
orientador aprova o início da avaliação. O I8.0 não faz essa aprovação.
