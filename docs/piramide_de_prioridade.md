# Pirâmide de prioridade do Montador

**Aprovada pelo Leo em 17/10/2026.** O conceito abaixo é do Leo (15 e 16/10/2026); a fila do `CHECKPOINT.md` segue esta ordem.

## O conceito

É uma pirâmide de **ordem de importância**, emprestada do desenvolvimento de jogos. A base é o pilar mais crítico; o pico é o menos importante. Ela mostra como uma falha nas prioridades básicas estraga a experiência inteira: se a base falha, nada acima dela importa. O pico só recebe atenção quando toda a base está "sólida como um diamante" — ele é bônus para uma experiência já redondinha, nunca atalho por cima de uma base instável.

No jogo, os cinco andares são, da base para o pico: **Funcionalidade** (os sistemas fundamentais funcionam na prática: servidor estável, sem bug que impeça o progresso, carregamento certo, comando que responde) · **Mecânicas** (como o gameplay se sustenta no dia a dia: movimentação, combate, progressão, inventário) · **Conteúdo** (o que há de fato para fazer com as mecânicas: missões, monstros, eventos, mapa) · **Balanceamento e polimento** (justiça entre armas, classes e mecânicas, sem nada desproporcional quebrando a progressão ou a economia; acabamento gráfico, fluidez, arestas) · **Monetização** (lojas, cosméticos, pacotes — a camada mais supérflua).

## Os cinco andares no Montador

O que vale é o **sentido** de cada andar, não o nome.

| Andar | No Montador | Exemplos do que está pendente |
|---|---|---|
| **1. Funcionalidade** — a base, o mais crítico | O app funciona na prática: abre do disco e no site sem erro, salva e não perde build, importa e exporta o que exportou, o número mostrado é o do catálogo, publicar não falha nem mente | T37 e o alinhamento do formato (o texto volta igual), T38 (o texto perde as trilhas de runa), T43 (números do Catálogo que não batem), T42 (o "Puxar da build ativa"), T45 e nºs 50, 53 e 49 (publicar mostra o rascunho, o nome some, data errada, erro falso). Criar: o robô de atualização por patch, que mantém itens e runas no patch atual sem depender do Claude |
| **2. Mecânicas** | Como a montagem se sustenta no dia a dia: catálogo e filtros, forja (arrastar, caixas, interruptores), runas, ordem de habilidades, calculadora, biblioteca, publicar, compartilhar, favoritos | Consertar: T39, T40, T41, T44, nºs 51 e 52, o link curto e o fim do arquivo do Arsenal. Criar: duas abas com arrastar entre janelas, mapa de visão e rotas da selva, comparar builds, cadeado de grupo e aviso de efeito que não acumula, calculadora de armadura para tanques, calculadora de monstros épicos |
| **3. Conteúdo** | O que há para montar e consultar com as mecânicas: os 225 itens (Capítulo 1), as runas, os campeões (Capítulo 1.1, com as classes do Leo), o Bestiário (monstros por acampamento e por unidade, épicos, torres e tropas), as builds públicas, a informação no card (rota, feitiços, título do campeão) | Capítulo 1.1, Bestiário, campos novos do card |
| **4. Balanceamento e polimento** | Balanceamento: o que é público é justo entre si — a popularidade conta só visualização e cópia, mostra até 10 e não inventa popular. Polimento: tamanhos e legibilidade em 1440, 1080 e 900, acessibilidade, fluidez, arestas | Popularidade remodelada, card de habilidades maior, nºs 47 e 48 (foco e Tab), nº 39 (aviso de rascunho fora da forja) |
| **5. O pico — o supérfluo** (a "monetização" do Montador) | Cosmético e vitrine: o que enfeita ou mostra o app, sem mudar o que ele faz | Imagens geradas (capas, cenários, texturas por região), card no formato do post, miniatura no Discord, o tour guiado |

## Regras

1. **Classificar pela base:** pergunta-se de baixo para cima — "isso impede usar ou mostra dado errado?", "é como a montagem funciona?", "é coisa para consultar?", "é justiça ou acabamento?", "é enfeite ou vitrine?". A primeira resposta "sim" dá o andar.
2. **Um defeito pertence ao andar que ele quebra.** Um botão de enfeite que perde a build é Funcionalidade.
3. **Um andar só recebe trabalho quando os de baixo estão sólidos**, a não ser que o Leo puxe algo para cima.
4. **Dentro do andar, consertar vem antes de criar.**
5. **O que está aberto fecha antes de abrir outro.**
