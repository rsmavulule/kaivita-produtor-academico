Lacunas funcionais — I8.0

Este texto separa o que a SRS torna obrigatório do que os incrementos
anteriores deixaram como residual. A classificação global está na
matriz de rastreabilidade. Aqui ficam as quatro questões pedidas e a
reconciliação funcional.

1. RF-01 — área de actuação ou cobertura

Redacção, secção 5, página 3:
«Criar, consultar e actualizar perfil de actor com papel produtor;
pessoa singular ou organização, localização geral e área de actuação.»

A secção 3, página 2, acrescenta: «No protótipo, actor.general_location
e eventual coverage_area podem expressar esta informação sem exigir
CRUD de delegações.»

Estado actual. O actor tem kind, display_name, general_location e
status. A criação e a actualização privadas cobrem nome e localização.
O papel producer é independente da representação. Não existe coluna,
campo, projecção pública nem teste de área de actuação.

Diferença. A localização geral está feita e validada. A área de
actuação, que a SRS distingue da sede, não está. Q-01 esclarece que a
actuação nacional não é o endereço da sede nem o de cada delegação.
Guardar essa informação só em general_location apaga a distinção.

Necessidade. É obrigatória para fechar RF-01, prioridade Alta da SRS.
Não é obrigatório o CRUD de delegações: a própria SRS o exclui.

Solução mínima. Uma coluna de texto opcional, por exemplo
coverage_area, distinta de general_location. Edição no perfil privado.
Inclusão na projecção pública do produtor, na ficha da oferta. O mesmo
aviso de texto livre que já existe para a localização. Sem mapa, sem
geometria e sem filtro novo: RF-04 filtra a localização geral, não a
área de actuação.

Impacto. Migração Alembic. Actor e ActorUpdate. Projecção em
public_offers.py e public_catalog.py. Formulário do actor. Testes de
API e um percurso Playwright. O aviso de texto livre aplica-se ao campo.

2. RF-02 — fotografia do produto

Redacção, secção 5, página 3:
«Criar, editar, arquivar e consultar produtos associados a actor
produtor; nome, categoria, descrição e fotografia opcional.»

A entidade Product tem o atributo image_ref. A fotografia é opcional.
A funcionalidade de a registar e consultar não é opcional.

Estado actual. name, description, category, status e o arquivo estão
implementados e testados. image_ref é texto opcional, gravado e editado
na ficha privada. O comentário do modelo diz que não é um ficheiro.
A projecção pública PublicProduct leva nome, descrição e categoria.
Não leva image_ref. Não há declaração de direito de uso.

Diferença. A referência existe em privado. Não há consulta pública da
referência, nem apresentação de uma imagem, nem gate de direitos.
image_ref não equivale, por si, a gestão de fotografias. Também não é
necessário um repositório de ficheiros para cumprir o atributo que a
SRS chamou image_ref.

Necessidade. A parte de nome, categoria, descrição e arquivo está
fechada. A parte da fotografia fica por fechar em conjunto com RB-08.
Prioridade Alta de RF-02. A fotografia em si pode continuar ausente
num produto concreto.

Solução mínima. Manter image_ref como texto opcional. Acrescentar uma
declaração explícita do representante, por omissão falsa. A referência
só entra na projecção pública quando a declaração está feita. Na ficha
pública, mostrar a referência como texto. Não armazenar binários, não
processar imagens e não fazer hotlink automático: um endereço remoto
pode revelar a consulta a um terceiro. Um elemento de imagem pode ser
decisão posterior, não é o mínimo.

Impacto. Migração com a declaração, por omissão falsa, para não
publicar referências já gravadas. Product, catálogo privado, projecção
pública, formulário e testes. Sem serviço externo.

3. RB-08 — direitos de utilização

Redacção, secção 6, página 4:
«Fotografias só são publicadas com declaração de direito de uso;
fotografias da FACIM não são importadas automaticamente.»

A secção 10 exige declaração de titularidade ou licença e atenção a
pessoas identificáveis e a contactos impressos. As fotografias da
FACIM destinam-se a análise documental, não ao catálogo, sem
autorização adequada.

Estado actual. Não há importação da FACIM. Não há fotografia na
resposta pública. A invariante «não publicar sem declaração» cumpre-se
hoje pela omissão total, não por uma declaração. Não há registo de
que o representante declarou o direito.

Diferença. A proibição de importação automática está satisfeita por
ausência de carga. A declaração, que é a condição para publicar, não
existe. Não se classifica RB-08 como validado só porque nada é mostrado.

Necessidade. Obrigatória no momento em que qualquer referência de
imagem passa a ser pública. Enquanto a referência ficar só no privado,
a publicação sem declaração não ocorre, mas o requisito continua
parcial.

Solução mínima. A mesma declaração do ponto 2. Texto curto: o
representante declara ter direito a usar a referência; a confirmação
não prova a licença nem inspecciona pessoas ou contactos na imagem.
Não se propõe análise automática de imagens. A inspecção de pessoas
identificáveis fica como limite aceite do protótipo, alinhada com a
secção 10 e sem censura heurística.

Impacto. O mesmo do ponto 2. Sem pipeline de visão computacional.

4. Consulta pública independente de actores e produtos

Textos relevantes:

  Secção 4, página 3: o visitante pesquisa e consulta perfis, produtos
  e ofertas publicados, e consulta contactos autorizados.
  RF-04: pesquisar ofertas públicas por texto, categoria e localização.
  RF-07: consulta pública sem autenticação apenas de recursos publicados.
  UC-06: o visitante vê apenas conteúdos publicados e estados coerentes.
  Diagrama 01B: UC-06 intitula-se «Pesquisar e consultar ofertas».

Estado actual. Há lista e ficha públicas de ofertas elegíveis. Cada
oferta inclui o nome, a descrição e a categoria do produto, e o nome,
o tipo e a localização do produtor. Não há GET /public/actors nem
GET /public/products. Não há páginas /actores públicos nem /produtos
públicos.

Diferença. A frase da secção 4 é mais larga do que RF-04, do que o
critério de UC-06 e do que o título do diagrama. A consulta de perfil
e de produto existe hoje só dentro da oferta elegível.

Necessidade. Não é um requisito numerado autónomo. Não se abre um
catálogo independente para «cumprir» uma frase de interveniente que
os requisitos e o caso de uso não repetem com critérios próprios.
Tratar essa frase como P1 inventaria âmbito. Fica divergência
documental, prioridade P3, à espera de confirmação do orientador.
Se for confirmada como obrigatória, deixa de ser P3.

O que está obrigatório e já fechado na reconciliação

Identidade. Autenticação, actores pessoa e organização, papéis
producer, buyer e partner, representação read/manage, isolamento e
separação entre papel comercial e autorização de acesso. RF-08, RF-09,
RB-01 e RB-10.

Perfil, excepto a área de actuação. Nome, tipo, localização geral.
Estado active/inactive existe e a consulta pública exige active, mas
não há operação para o representante mudar o estado. Isso não está em
RF-01. Fica limitação P3, não lacuna de RF.

Produtos, excepto fotografia e direitos. Registo, alteração, categoria
livre, descrição, arquivo, dono e isolamento.

Ofertas. Preço e moeda, quantidade e unidade, disponibilidade, condições
de entrega, rascunho, publicação, suspensão, republicação, retirada,
produto do mesmo actor. A republicação está no diagrama de estados e
no código, apesar da nota do diagrama que pedia aprovação prévia. Essa
aprovação foi exercida na implementação do I4 e está testada.

Descoberta. Pesquisa textual no nome e na descrição, filtro de
categoria, filtro de localização geral, ficha, elegibilidade, paginação
com tecto, contactos só depois de «Ver contactos».

Autorizações. Privacidade por omissão, finalidade commercial_discovery,
confirmação explícita, revisão do contacto, histórico, revogação,
revogação por alteração efectiva, desactivação com revogação, e a
mesma transacção para o contacto e a autorização. O representante
habilitado está previsto na secção 10. A confirmação não é prova do
consentimento do titular: isso permanece em Q-06 e em RNF-06.

README. As linhas iniciais ainda dizem que a interface não apresenta
os contactos autorizados. O código do I7.3 apresenta-os em «Ver
contactos». É divergência documental, P3, não lacuna funcional.
