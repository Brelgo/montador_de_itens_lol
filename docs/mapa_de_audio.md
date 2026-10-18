# Mapa de Áudio — Montador de Itens (Capítulo 2)

> Derivado dos nomes dos arquivos de `assets/audio/` (lista de 13/09/2026). Todo som passa pelo módulo `Som.play(evento, contexto)`; nenhum outro trecho do código chama `new Audio()`. Variantes `_01.._NN` do mesmo evento são sorteadas, sem repetir a última tocada. Nomes de arquivo são usados exatamente como estão (case-sensitive no GitHub Pages).

## Eixos do sistema

- **Núcleo** (`itemClass.core` do catalog.js): `danodeataque` = AD · `poderdehabilidade` = AP · `tank` = Vitalidade. O único item "AD e AP" (Filhote de Garrabrasa) sorteia entre AD e AP.
- **Tier** (`tier`): Lendário tem som próprio ao entrar no Build (`ui_build_mod_add_legendary_*`), tocado no lugar do `build_item_add` genérico; Consumível/Distribuído/Trinket usam o clique neutro.
- **Item específico** (`nameEn` normalizado: minúsculas, sem espaços, apóstrofos, vírgulas ou acentos): fala rara do lojista ao adicionar ao Build — toca junto com o som do tier, com prioridade sobre a fala genérica.
- **Efeito Especial** (`specialEffects`, normalizado da mesma forma): fala do lojista ao selecionar o filtro daquele efeito.

## Tabela evento → arquivos

| Evento | Quando dispara | Arquivos | Nº |
|---|---|---|---|
| `build:close` | sair da tela Build | `build_close.mp3` | 1 |
| `build:item_add` | item não Lendário entra no Build, pela forja ou marcado pelo Catálogo (F10-T4, Leo, 16/09/2026: os dois caminhos tocam o mesmo; antes o Catálogo era sempre genérico) | `build_item_add_01.mp3`, `build_item_add_02.mp3`, `build_item_add_03.mp3`, `build_item_add_04.mp3` | 4 |
| `build:save` | Salvar na forja (botão ou Ctrl+S) e "Salvar e sair" da placa de alterações não salvas | os mesmos `build_open_*.mp3` (cooldown 300 ms) | — |
| `build:item_move` | molde arrastado de uma bancada para outra (sem fala do lojista) | os mesmos `build_item_add_01..04.mp3` | 4 |
| `build:open` | entrar na tela Build | `build_open_01.mp3`, `build_open_02.mp3`, `build_open_03.mp3`, `build_open_04.mp3`, `build_open_05.mp3`, `build_open_06.mp3` | 6 |
| `catalog:close` | sair do Catálogo | `close_catalog.mp3` | 1 |
| `catalog:open` | tela de entrada → Catálogo (destrava o áudio) | `open_catalog.mp3` | 1 |
| `lojista:build_add:item:bloodthirster` |  | `shopkeeper_build_add_bloodthirster_01.mp3` | 1 |
| `lojista:build_add:item:heartsteel` |  | `shopkeeper_build_add_heartsteel_01.mp3` | 1 |
| `lojista:build_add:item:infinityedge` |  | `shopkeeper_build_add_infinityedge_01.mp3` | 1 |
| `lojista:build_add:item:jakshotheprotean` |  | `shopkeeper_build_add_jakshotheprotean_01.mp3` | 1 |
| `lojista:build_add:item:rabadonsdeathcap` |  | `shopkeeper_build_add_rabadonsdeathcap_01.mp3` | 1 |
| `lojista:build_add:item:rylaiscrystalscepter` |  | `shopkeeper_build_add_rylaiscrystalscepter_01.mp3` | 1 |
| `lojista:efeito_select:danoaolongodotempo` | ao entrar na build um item com esse Efeito Especial (Leo, 13/09/2026; prioridade: fala rara do item > efeito > núcleo) e ao marcar o chip do efeito | `shopkeeper_build_efeitosespeciais_danoaolongodotempo_select_01.mp3`, `shopkeeper_build_efeitosespeciais_danoaolongodotempo_select_02.mp3` | 2 |
| `lojista:efeito_select:lentidao` | idem | `shopkeeper_build_efeitosespeciais_lentidao_select_01.mp3` | 1 |
| `lojista:tag_open:AD` | ao TROCAR para a aba de Classe AD no Catálogo, e ao entrar na build um item de núcleo AD que não tem fala rara própria (Leo, 13/09/2026); sujeito a chance/intervalo do lojista | `shopkeeper_tag_open_danodeataque_01.mp3`, `shopkeeper_tag_open_danodeataque_02.mp3`, `shopkeeper_tag_open_danodeataque_03.mp3`, `shopkeeper_tag_open_danodeataque_04.mp3`, `shopkeeper_tag_open_danodeataque_05.mp3` | 5 |
| `lojista:tag_open:AP` | ao TROCAR para a aba de Classe AP no Catálogo, e ao entrar na build um item de núcleo AP que não tem fala rara própria (Leo, 13/09/2026); sujeito a chance/intervalo do lojista | `shopkeeper_tag_open_poderdehabilidade_01.mp3`, `shopkeeper_tag_open_poderdehabilidade_02.mp3`, `shopkeeper_tag_open_poderdehabilidade_03.mp3`, `shopkeeper_tag_open_poderdehabilidade_04.mp3`, `shopkeeper_tag_open_poderdehabilidade_05.mp3` | 5 |
| `lojista:tag_open:Vitalidade` | ao TROCAR para a aba de Classe Vitalidade no Catálogo, e ao entrar na build um item de núcleo Vitalidade que não tem fala rara própria (Leo, 13/09/2026); sujeito a chance/intervalo do lojista | `shopkeeper_tag_open_tank_01.mp3`, `shopkeeper_tag_open_tank_02.mp3`, `shopkeeper_tag_open_tank_03.mp3`, `shopkeeper_tag_open_tank_04.mp3`, `shopkeeper_tag_open_tank_05.mp3` | 5 |
| `build:add_legendary:AD` | item Lendário entra no Build (substitui build:item_add) | `ui_build_mod_add_legendary_danodeataque.mp3` | 1 |
| `build:add_legendary:AP` | item Lendário entra no Build (substitui build:item_add) | `ui_build_mod_add_legendary_poderdehabilidade.mp3` | 1 |
| `build:add_legendary:Vitalidade` | item Lendário entra no Build (substitui build:item_add) | `ui_build_mod_add_legendary_tank.mp3` | 1 |
| `catalog:hover:AD` | mouse entra em qualquer card do Catálogo — toca na hora, sem cooldown (Leo, 13/09/2026), a 40% do volume geral (ganho 0,4; Leo, 17/10/2026: 60% mais baixo) | `ui_catalog_mod_hover_danodeataque_01.mp3`, `ui_catalog_mod_hover_danodeataque_02.mp3`, `ui_catalog_mod_hover_danodeataque_03.mp3`, `ui_catalog_mod_hover_danodeataque_04.mp3`, `ui_catalog_mod_hover_danodeataque_05.mp3`, `ui_catalog_mod_hover_danodeataque_06.mp3`, `ui_catalog_mod_hover_danodeataque_07.mp3`, `ui_catalog_mod_hover_danodeataque_08.mp3`, `ui_catalog_mod_hover_danodeataque_09.mp3`, `ui_catalog_mod_hover_danodeataque_10.mp3`, `ui_catalog_mod_hover_danodeataque_11.mp3` | 11 |
| `catalog:hover:AP` | idem | `ui_catalog_mod_hover_poderdehabilidade_01.mp3`, `ui_catalog_mod_hover_poderdehabilidade_02.mp3`, `ui_catalog_mod_hover_poderdehabilidade_03.mp3`, `ui_catalog_mod_hover_poderdehabilidade_04.mp3`, `ui_catalog_mod_hover_poderdehabilidade_05.mp3`, `ui_catalog_mod_hover_poderdehabilidade_06.mp3`, `ui_catalog_mod_hover_poderdehabilidade_07.mp3`, `ui_catalog_mod_hover_poderdehabilidade_08.mp3`, `ui_catalog_mod_hover_poderdehabilidade_09.mp3`, `ui_catalog_mod_hover_poderdehabilidade_10.mp3`, `ui_catalog_mod_hover_poderdehabilidade_11.mp3` | 11 |
| `catalog:hover:Vitalidade` | idem | `ui_catalog_mod_hover_tank_01.mp3`, `ui_catalog_mod_hover_tank_02.mp3`, `ui_catalog_mod_hover_tank_03.mp3`, `ui_catalog_mod_hover_tank_04.mp3`, `ui_catalog_mod_hover_tank_05.mp3`, `ui_catalog_mod_hover_tank_06.mp3`, `ui_catalog_mod_hover_tank_07.mp3`, `ui_catalog_mod_hover_tank_08.mp3`, `ui_catalog_mod_hover_tank_09.mp3`, `ui_catalog_mod_hover_tank_10.mp3` | 10 |
| `catalog:tag_select` / `catalog:pergaminho` | abrir o pergaminho do item (decisão do Leo, 13/09/2026) e clique em qualquer chip de filtro — ambos à metade do volume geral (ganho 0,5) | `ui_catalog_tag_select_01.mp3`, `ui_catalog_tag_select_02.mp3`, `ui_catalog_tag_select_03.mp3`, `ui_catalog_tag_select_04.mp3`, `ui_catalog_tag_select_05.mp3`, `ui_catalog_tag_select_06.mp3` | 6 |
| `catalog:click:neutro (tiers Consumível, Distribuído, Trinket)` | clique num card do Catálogo (marca para o Build) | `ui_shop_click_consumivel_distribuido_talisma.mp3` | 1 |
| `catalog:click:AD` | clique num card do Catálogo (marca para o Build) | `ui_shop_click_danodeataque.mp3` | 1 |
| `catalog:click:AP` | clique num card do Catálogo (marca para o Build) | `ui_shop_click_poderdehabilidade.mp3` | 1 |
| `catalog:click:Vitalidade` | clique num card do Catálogo (marca para o Build) | `ui_shop_click_tank.mp3` | 1 |

## Normalização de chaves (itens e efeitos)

```js
const chave = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
// 'Jak\'Sho, The Protean' → 'jakshotheprotean' · 'Dano ao Longo do Tempo' → 'danoaolongodotempo'
```

## Regras de reprodução

- Nada toca antes do clique em "Entrar na loja" (política de autoplay dos navegadores).
- Volume geral e mudo persistem em `localStorage` (`som.volume`, `som.mudo`). Volume geral padrão: **50%**, e o controle segue a curva dos tocadores de áudio — o volume tocado é o do controle ao quadrado (a metade dá ¼). Cada arquivo tem o seu redutor, medido por `docs/medir_sons.py` e gravado em `data/ganho_sons.js`: nenhum som passa de -30 dBFS RMS com o controle no máximo (as falas do lojista vinham perto de -13, os cliques da loja perto de -46). Rodar o script de novo sempre que um arquivo entrar ou mudar. O volume gravado antes da F13-T48 passa para 50% uma vez (`som.padrao` = 3) (Leo, 17 e 18/10/2026).
- Falas do lojista (regras do Leo, 13/09/2026): nunca cortam a fala em curso; uma nova só pode começar depois que a atual terminar, mais 0,5 s de folga; o lojista fala "de vez em quando" — falas de aba e de efeito têm 40% de chance por acionamento e intervalo mínimo de 15 s entre falas; falas raras por item sempre tocam quando o item entra, respeitando a fila e a folga. Constantes em `Som.LOJISTA` (FOLGA_MS, INTERVALO_MIN_MS, CHANCE). Sons de interface podem se sobrepor.
- **Regra do Leo (13/09/2026): sempre que um evento tiver mais de um arquivo, a ativação é aleatória** — um deles é sorteado a cada disparo, sem repetir o anterior.
- Hover toca em todo card que o mouse tocar, sem cooldown; clique e chip têm cooldown curto (80 ms) só para não disparar duas vezes no mesmo clique.
- Todos os arquivos são pré-carregados no clique de "Entrar na loja" para tocarem sem atraso.

## Texturas (assets/textures)

- `shopitem_papertexture01_psd.png`
- `shopitem_papertexture02_psd.png`
- `shopitem_papertexture03_psd.png`

## Canais e mudo (Fase 9, T6 — 15/09/2026)
- O painel do alto-falante tem **Som geral** (tudo mudo) e três canais independentes, guardados em `localStorage som.canais`: **Interface** (`ui_catalog_*`, `ui_shop_*`, `ui_catalog_tag_select`, `open_catalog`, `close_catalog`), **Forja** (`build_*`, `ui_build_mod_add_legendary_*`) e **Lojista** (`shopkeeper_*`). Um canal mudo não toca nada dele; o volume é geral.

