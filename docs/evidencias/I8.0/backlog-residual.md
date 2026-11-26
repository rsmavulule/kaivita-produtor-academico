Backlog residual — I8.0

Prioridade, severidade e obrigatoriedade estão separadas. P0 é
bloqueador de segurança, integridade ou funcionamento essencial
demonstrado. Não há item P0. Um requisito obrigatório parcial não
desce de prioridade por ser trabalhoso.

| ID | Item | Obrigatoriedade | Severidade se ficar por fazer | Prioridade | Depende de | Incremento |
| --- | --- | --- | --- | --- | --- | --- |
| L1 | Área de actuação do actor, distinta da localização geral | RF-01, prioridade Alta | O perfil não cumpre a SRS | P1 | Nenhuma | I8.1 |
| L2 | Referência de imagem na consulta pública só com declaração de uso | RF-02 e RB-08 | Fotografia especificada continua ausente da consulta | P1 | Nenhuma; faz-se com L1 no mesmo incremento | I8.1 |
| L3 | Eventos de publicar, suspender, republicar e retirar, sem dados sensíveis | RNF-07 | Auditoria de publicação incompleta | P1 | Nenhuma | I8.2 |
| L4 | Access log sem query string | Parte residual de RNF-06 e RNF-07 | Pesquisa pode ficar no log do contentor | P2 | Nenhuma | I8.2 |
| L5 | Teste temporal relativo ao granted_at real | Dívida obrigatória do I8, não é RF | A suite parte em 2099-01-01 | P2 | Nenhuma | I8.3 |
| L6 | Spec de contactos espera o URL de logout antes de voltar a entrar | Fragilidade observada | Falso negativo de regressão | P2 | Nenhuma | I8.3 |
| L7 | Spec do visitante espera o estado confirmado no browser do produtor | Fragilidade observada, não estável | Falso negativo | P2 | Nenhuma | I8.3 |
| L8 | Página de oferta inexistente, inelegível ou UUID inválido com HTTP 404 | Qualidade, sem RF de código HTTP | Soft 404 | P2 | Nenhuma | I8.3 |
| L9 | Testes de teclado em produto, oferta e contacto | RNF-02, evidência em falta | Requisito fica não validado | P2 | Nenhuma | I8.3 |
| L10 | Medição de tempo da pesquisa pública, com limiar aprovado antes | RNF sem número na SRS | Sem evidência de desempenho | P2 | Ambiente de avaliação ajuda, não bloqueia uma medição local | I8.3 |
| L11 | Bloqueio da linha na transição de oferta e nova leitura do estado | Risco potencial, não defeito observado | Corrida teórica | P2 | Nenhuma | I8.2, se couber sem atrasar L3 |
| L12 | Reverificar a representação depois do bloqueio da linha escrita | Risco potencial | Corrida teórica | P2 | Nenhuma | I8.2, junto de L11 |
| L13 | Base de avaliação, dados sintéticos, reposição e isolamento | Condição do I9, não é RF | Avaliação mistura resíduos | P2 | L1 a L10 desejáveis antes do congelamento | I8.4 |
| L14 | Correr de novo as suites no candidato e arquivar a evidência | Critério de RC | RC sem prova | P2 | L1, L2, L3, L5 | I8.4 |
| L15 | Procedimento de Chromium 1255 e NO_PROXY documentado no README ou num guião de execução | Ambiente | A suite nem arranca | P2 | Nenhuma | I8.3 ou I8.4 |
| L16 | Actualizar a frase do README que diz que a interface não mostra contactos | Documentação desactualizada | Leitor conclui o contrário do código | P3 | Nenhuma | I8.4 |
| L17 | Operação para activar ou desactivar o actor | Não está em RF numerado | O estado existe e só os testes o mudam | P3 | Decisão | Fora do I8, salvo decisão |
| L18 | Catálogos públicos independentes de actores e produtos | Não são RF numerado | Nenhum, se a decisão for não os fazer | P3 | Decisão do orientador | Não planear no I8 |
| L19 | CHECK de papel producer na base | A API já recusa | INSERT directo contorna | P3 | Nenhuma | Não planear, salvo decisão |
| L20 | TLS, revogação de JWT, análise de imagens, censura de texto livre, backoffice de administrador | Fora do texto obrigatório ou limite aceite | Não bloqueia a avaliação académica local | P3 | Decisões externas | Não fazer no I8 |

Dependências que importam

L2 não deve publicar image_ref já gravado sem declaração. A omissão por
defeito tem de ser falsa.

L13 não deve correr antes de L1 e L2 se os dados sintéticos forem a
imagem do candidato. Pode ser preparado em paralelo, mas o conjunto
final inclui os campos novos.

L14 é o último. Não substitui L1, L2 ou L3.

Não há P0. O funcionamento essencial de autenticação, isolamento,
oferta e descoberta está implementado e a API passou 266 testes.
