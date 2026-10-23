# Esquema do habilidades.js

`habilidades.js` define `window.HABILIDADES`. É gerado pelo `gerar_habilidades.py` a partir de `habilidades_campeoes.md` e nunca é editado à mão.

```
meta        : { fonte, gerado, patch, campeoes, conferidos, pendentes[] }
  pendentes[] : { key, id, nome, motivo }   — exceção que a Riot tem e a fonte ainda não
regraGeral  : { niveis, maxPorHabilidade, niveisPorPonto, automatico, niveisDoSupremo }
campeoes    : { "<key>": ficha }
  ficha     : { key, id, nome, temSupremo, maxPorHabilidade, niveisPorPonto,
                automatico, niveisDoSupremo, formas[], requer, trava, habilidades, observacao }
  formas[]  : { nome, habilidades: { Q, W, E, R } }
```

- **`campeoes`** só traz quem foge da regra geral e já foi conferido. A chave é a `key` do Data Dragon (`"77"`), a mesma que a build guarda em `champion.key`. Campeão fora de `campeoes` usa `regraGeral`.
- **`maxPorHabilidade`**: quantos pontos cada botão aceita, por exemplo `{ Q: 6, W: 6, E: 6, R: 0 }` no Jayce.
- **`niveisPorPonto`**: para cada botão, o nível mínimo exigido pelo 1º, 2º, … ponto, por exemplo `[1, 3, 5, 7, 9]` no caso comum. O nível 1 quer dizer "sem trava". O nível é mínimo, não exato: o ponto pode entrar depois. Fora isso, só entra um ponto por nível.
  - Para saber se a grade aceita a letra L no nível n: conte os pontos que L tem nos níveis antes de n (k) e veja se `k < maxPorHabilidade[L]` e `niveisPorPonto[L][k] <= n`. Isso também cobre a regra do nível 8: o 5º ponto exige o nível 9.
  - Marcar um nível anterior muda a posição dos pontos seguintes da mesma letra. Por isso a sequência inteira precisa ser conferida de novo depois de cada marcação.
- **`automatico`**: ranks que vêm sem gastar ponto, com o nível em que chegam, por exemplo `{ R: [1] }` no Jayce e `{ R: [6, 11, 16] }` no Aphelios. Esses níveis não consomem o ponto do nível: o ponto continua livre para outro botão.
- **`niveisDoSupremo`**: os níveis em que o R ganha rank, por ponto ou sozinho. Fica vazio quando o campeão não tem supremo (`temSupremo: false`: Udyr; Jayce, cujo R é a Transformação).
- **`formas`**: quando os mesmos pontos valem para dois conjuntos de habilidades (Jayce). O ponto num botão sobe as duas formas juntas.
- **`requer`**: o 1º ponto do botão exige outra habilidade já aprendida, por exemplo `{ W: ["Q", "E"] }` no Zilean (uma das duas) e `{ Q: ["W"], E: ["W"] }` no Azir. Vazio (`{}`) quando não há.
- **`trava`**: texto, quando o campeão não pode gastar ponto em certa situação (Hwei com um tema aberto, Viego possuindo alguém). Não muda a grade; é para mostrar na tela.
- **`habilidades`**: os nomes pt-BR dos quatro botões, como o Data Dragon escreve (com as formas separadas por " / ").
- **`observacao`**: o texto que explica a exceção, para aparecer na grade.
- **`meta.pendentes`**: campeões cuja regra a Riot mostra que é diferente, mas que ainda não têm ficha. Enquanto estiverem ali, a grade aplica a regra geral a eles sabendo que pode errar. Vale avisar isso na tela.
