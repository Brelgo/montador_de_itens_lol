# Proposta de Capítulo 1.1 — dado de campeão

O Capítulo 1 é exclusivamente de itens; isso você deixou claro em 18/09/2026. Tudo que a grade de habilidades precisa e não tem vem de outro lugar, e esse outro lugar não existe ainda.

Este arquivo é o pedido, não a solução. Enquanto ele não for atendido, o app **não inventa nada**: a grade aplica só as regras que valem para todo campeão.

## O que a grade já faz sem dado novo

São regras do jogo, iguais para os 170 e tantos campeões, e por isso podem morar no código:

- 18 níveis, um ponto por nível;
- no máximo 5 pontos em Q, W e E, e 3 no supremo;
- o supremo só sobe nos níveis 6, 11 e 16.

Os ícones e os nomes de Q/W/E/R vêm do Data Dragon, pela mesma porta que o diálogo de marcador já usa. Sem campeão escolhido, a grade mostra as letras.

## O que falta, e por quê

### 1. Campeões cuja regra de pontos é diferente

O caso que você citou: **o W do Azir** — as Areias Ascendentes não seguem a regra comum. Há outros:

- **Udyr** não tem supremo; os quatro botões sobem até 6 e os níveis 6/11/16 não são especiais para ele.
- **Jayce, Elise, Nidalee, Karma** e os outros de forma têm dois conjuntos de habilidades que compartilham os mesmos pontos.
- **Aphelios** não tem Q/W/E no sentido comum.
- **Kayn, Gnar, Kled** mudam de habilidade conforme o estado.

Para tratar qualquer um deles, o app precisa saber, por campeão: quantos pontos cada botão aceita, em que níveis, e se ele tem supremo.

### 2. Distribuição automática

Você pediu "distribuições automáticas (W no Azir, por exemplo)". Automatizar significa ter a regra escrita em algum lugar; hoje a única fonte seria eu digitando de memória, e isso é exatamente o que este projeto não faz.

## O que o Capítulo 1.1 precisaria ter

Um registro por campeão, com pelo menos:

| Campo | Para quê |
|---|---|
| `key` / `id` | casar com o Data Dragon, como a build já faz |
| `temSupremo` | Udyr e afins |
| `maxPorHabilidade` | `{ Q: 5, W: 5, E: 5, R: 3 }` no caso comum; diferente onde for diferente |
| `niveisDoSupremo` | `[6, 11, 16]` no caso comum |
| `formas` | quando o campeão tem dois conjuntos que dividem pontos |
| `ordemSugerida` | a subida recomendada, se você quiser o botão de preencher sozinho |
| `observacao` | o texto que explica a exceção, para aparecer na grade |
| `classes` | a classe do campeão pela sua curadoria — a etiqueta da Riot "distribui muito mal" (Leo, 15/10/2026); é ela que abre a calculadora de armadura embutida na forja para os tanques |

Os atributos base e por nível (vida, armadura, resistência mágica) **não** precisam estar aqui: vêm do `champion.json` do Data Dragon, que o app já baixa (decisão do Leo, 15/10/2026). O kit em números (o que cada ponto de habilidade dá) continua sendo deste capítulo.

A fonte desses campos é sua decisão — wiki oficial, curadoria própria, ou uma mistura, como foi com as runas. O que importa para mim é ser **um arquivo**, com um gerador que faça a checagem de integridade e relate o que falta, igual ao `catalog.js` e ao `runas.js`.

## Enquanto isso

A grade funciona para a esmagadora maioria dos campeões, que seguem a regra comum. Para os de exceção ela vai deixar marcar coisas que o jogo não deixaria — e é melhor assim do que eu chutar a exceção e errar.
