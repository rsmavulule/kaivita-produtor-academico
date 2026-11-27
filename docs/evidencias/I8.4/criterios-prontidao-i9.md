# Critérios de prontidão para o I9 — I8.4

O I9 não foi iniciado. Esta lista diz se o candidato pode ser sujeito
a essa avaliação. A decisão de a iniciar continua a ser do autor.

## Cumprido

- Rastreabilidade dos 27 requisitos consolidada. 26 validados e RNF-06 parcial, por decisão explícita e não por omissão.
- Q-06 registada fora do denominador e ainda parcialmente aberta.
- Ambiente `kaivita-avaliacao` separado do desenvolvimento por projecto, volume, base, portas e credenciais.
- Migração `0008_offer_status_events` aplicada na base de avaliação.
- Base de desenvolvimento preservada: as mesmas contagens antes e depois.
- Contas e dados sintéticos criados pelos mecanismos existentes. Palavras-passe fora do Git.
- Percurso principal demonstrado: sessão, actores, produtos, oferta publicada, pesquisa, fotografia declarada, divulgação, revogação, suspensão, retirada e término de sessão.
- Backup lido numa base lateral e reposto sobre a base de avaliação.
- Reposição do volume de avaliação verificada, sem remover o volume de desenvolvimento.
- Limitações escritas, incluindo o soft 404 aceite.
- Candidato identificado como `v1.0.0-rc.1`, sem tag e sem o declarar avaliado.
- Não há defeito bloqueador conhecido.

## Ainda não é o I9

- Não houve participantes.
- Não há instrumento de recolha, consentimento de participação nem registo de dificuldades. Isso pertence ao desenho do I9, não a este protótipo.
- RNF-06 e Q-06 não ficam resolvidos por a avaliação começar.
- A tag Git não existe. O autor cria-a depois de versionar o I8.4.

## Condição de uso

A avaliação decorre no ambiente local de avaliação, com dados sintéticos
ou com dados que os próprios participantes introduzam. Não se publica
o ambiente. Não se corre a suite automática contra essa base.
