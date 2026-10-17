# Formato de importação de build

Este arquivo descreve o texto que o Montador de Itens lê em **Builds → Exportar / importar → Importar**. Serve para escrever uma build à mão ou pedir a uma IA que gere uma — cole o texto no campo de importação e a build aparece montada.

Os nomes válidos de item e de marcador estão em [marcadores.md](marcadores.md): 225 itens (português ou inglês), 13 marcadores padrão e as quatro habilidades. Nome que não bate com a lista é ignorado; o resto da build entra normalmente.

## Exemplo completo

```
BUILD: Jinx crítico
MODO: Summoner's Rift
CAMPEÃO: Jinx
MARCADORES: AD | Habilidade Q | Gume do Infinito
DESCRIÇÃO: Crítico puro para a rota inferior. / A Coletora primeiro contra times frágeis.
LAYOUT: Trilha por fases
MESTRE FORJADOR: Gume do Infinito

[PRIORIDADE] Núcleo | 3×1
# comprar sempre nessa ordem
= ~14min · 6.500g
- A Coletora
- Gume do Infinito * segurar até os 20 min
- Dança da Morte

[ESCOLHA 1] 4º item | 1×3
# o de cima é o padrão; os de baixo são trocas para o mesmo espaço
- Espada do Rei Destruído
- Mata-Cráquens
- Sedenta por Sangue

[OPCIONAL] Contra tanque | 2×1
- Arco do Axioma
- Cutelo Negro
```

## Linhas do cabeçalho

Vêm antes da primeira caixa, uma por linha, em qualquer ordem. Só `BUILD:` é obrigatória.

| Linha | O que faz | Valores |
|---|---|---|
| `BUILD:` | nome da build | texto livre |
| `MODO:` | modo de jogo, usado no aviso de item indisponível | `Summoner's Rift`, `ARAM`, `ARAM: Mayhem` |
| `CAMPEÃO:` | campeão em pt-BR, como no cliente | nome do Data Dragon, ex.: `Jinx`, `K'Sante`, `Lee Sin` |
| `MARCADORES:` | até 3, separados por ` \| ` | ver [marcadores.md](marcadores.md) |
| `DESCRIÇÃO:` | texto da build numa linha só | ` / ` (barra com espaço dos dois lados) separa parágrafos; ver a regra dos separadores |
| `LAYOUT:` | como a build é exibida | `Tabuleiro` (padrão), `Núcleo + bandeja`, `Trilha por fases`, `Árvore de decisão` |
| `MESTRE FORJADOR:` | liga o interruptor e escolhe o item forjado | nome de um item da build, ou `sim` |
| `RUNAS:` | trilha primária: a de assinatura primeiro, depois os três slots | `Precisão > Pressione o Ataque \| Triunfo \| Lenda: Espontaneidade \| Golpe de Misericórdia` |
| `RUNAS 2:` | trilha secundária: duas runas, de slots diferentes | `Dominação > Golpe Desleal \| Sexto Sentido` |
| `FRAGMENTOS:` | um de cada slot, na ordem | `Força Adaptativa \| Velocidade de Movimento \| Vida` |
| `HABILIDADES:` | a ordem de subida, 18 níveis separados por espaço | `Q W E Q Q R Q W Q W R W W E E R E E` |

As três linhas de runa são opcionais e independentes — dá para importar só os fragmentos, por exemplo. Vaga vazia se escreve `-`, como na linha de habilidades: `RUNAS: Precisão > Pressione o Ataque | - | Lenda: Espontaneidade | Golpe de Misericórdia` deixa o primeiro slot em branco. Na primária, cada runa é reconhecida pelo slot a que pertence — a ordem ajuda quem lê, mas não é ela que decide. Nos fragmentos a ordem decide, porque os grupos repetem runas (Força Adaptativa está no 1º e no 2º): escreva as três vagas, com `-` na que ficar vazia. Texto antigo, sem os `-`, ainda é lido — cada fragmento vai para o primeiro grupo que o aceita, em ordem. O nome antes do `>` é a trilha; depois dele, as runas separadas por ` | `. Nome de runa que não existir entra na mesma lista de "não encontrei" dos itens, e o resto da build importa normalmente. Os nomes válidos são os da aba **Runas**; a grafia segue o `data/Runas_League_of_Legends.md`.

Na linha de habilidades, `-` marca um nível em branco. As regras do jogo são aplicadas na importação: um ponto por nível, no máximo 5 em Q/W/E e 3 no R, e o supremo só nos níveis 6, 11 e 16 — o que não couber é descartado em silêncio, porque é regra do jogo e não erro de digitação.

A página de runas e a ordem de habilidades ficam na build e saem no `Copiar esta build`, mas **não entram no JSON do cliente do LoL** — o conjunto de itens do cliente importa itens, não runas.

## Caixas

Uma caixa começa com `[TIPO] Nome | colunas×linhas`. A grade é opcional; sem ela a caixa nasce com 3 colunas.

| Tipo | Efeito |
|---|---|
| `[COMUM]` | caixa normal, conta nos totais |
| `[PRIORIDADE]` | conta nos totais e vira "- PRIORIDADE" no arsenal do cliente |
| `[OPCIONAL]` | fica fora dos totais e do resumo das listas |
| `[ESCOLHA 1]` | pilha de alternativas para o mesmo espaço: só o primeiro item conta |

Dentro da caixa:

| Linha | O que faz |
|---|---|
| `# texto` | descrição da caixa |
| `= texto` | marco ou teto, ex.: `= ~14min · 6.500g` |
| `- Item` | um item; `- Item * observação` grava a nota que aparece ao passar o mouse. A observação pode ter várias linhas, separadas por ` ¶ ` (sinal de parágrafo com espaço dos dois lados): `- Gume do Infinito * segurar até os 20 min ¶ vender por último`. Na observação a `/` é sempre barra |
| `- Atributo adicional [Ouro · Vida]` | o fragmento escolhido do Atributo adicional (ARAM: Desordem): `[Nível · Fragmento]`, com o nível (Prata, Ouro ou Prismático) e o nome do fragmento como aparece em "Qual fragmento?" na forja (o composto pelo nome dele: `[Prata · Swiftness]`). Vem antes da observação: `- Atributo adicional [Ouro · Vida] * pegar cedo`. Fragmento que não existe vai para o aviso de "não encontrei", e o item entra sem ele. |

## Regras

- Acentos e maiúsculas não importam nos nomes de item, marcador, modo e layout.
- Item desconhecido é listado no aviso de importação e não entra; a build importa mesmo assim.
- Linha que não é nenhuma das acima é ignorada silenciosamente, então comentários soltos não quebram nada.
- **Os separadores de linha:** na `DESCRIÇÃO:` da build, ` / ` (barra com espaço dos dois lados) separa os parágrafos; na observação do item (`- Item * ...`), ` ¶ `. Colados, são texto (`AD/AP`, `3/0`, `poke/sustain`, links). Para o separador solto de verdade no meio da linha, escreva-o dobrado (` // ` na descrição, ` ¶¶ ` na observação) — é assim que o Montador exporta, e volta igual. Linha em branco e recuo não vão para o texto. As linhas `# ` (descrição da caixa) e `= ` (marco) são de uma linha só: nelas a barra é sempre texto.
- A ordem dos itens dentro da caixa é a ordem de compra que aparece na forja e no arsenal do cliente.
- A build importada entra como rascunho: precisa de **Salvar** para ficar na biblioteca.
- **Runas ficam de fora**: o formato só trata itens do catálogo do Capítulo 1.

## Várias builds num texto só

Em **Builds → Selecionar → Copiar como texto**, o Montador põe várias builds num texto só, uma depois da outra, separadas por uma régua de `=`. A importação lê do mesmo jeito: cada `BUILD:` começa uma build nova, e a régua (uma linha só de `=`, de três para cima) separa uma da outra — dentro de uma build (abaixo do título ou entre caixas), ela é só enfeite. O cabeçalho de cada build (`MODO:`, `CAMPEÃO:`, `RUNAS:`...) vem antes da primeira caixa dela — antes ou depois do `BUILD:`; um `BUILD:` repetido antes de qualquer caixa só renomeia. **Importar como nova build** cria todas de uma vez e diz quantas entraram. Uma build sem nenhuma caixa fica de fora, e a mensagem diz qual.

## Prompt pronto para uma IA

```
Monte uma build de League of Legends para <campeão> no formato abaixo e responda
só com o bloco de texto, sem comentários.

BUILD: <nome>
MODO: Summoner's Rift
CAMPEÃO: <campeão>
MARCADORES: <até 3 da lista permitida>
DESCRIÇÃO: <uma linha; use " / " para separar parágrafos>

[PRIORIDADE] Núcleo | 3×1
# <quando comprar>
- <item>
- <item>
- <item>

[ESCOLHA 1] 4º item | 1×3
- <item padrão>
- <alternativa>
- <alternativa>

[OPCIONAL] Situacional | 2×1
- <item>
- <item>

Regras: use apenas nomes de itens e marcadores das listas que eu colar a seguir;
não invente item, atributo, preço nem efeito.
```

Cole junto o conteúdo de [marcadores.md](marcadores.md) para a IA ter as listas válidas.
