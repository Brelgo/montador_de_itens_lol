# Roteiro de QA

Um comando que abre o app, percorre os caminhos de sempre com clique de verdade
e diz o que quebrou.

```bash
python docs/qa_roteiro.py
```

Outras formas:

| Comando | O que faz |
|---|---|
| `python docs/qa_roteiro.py` | esta pasta, servida numa porta livre |
| `python docs/qa_roteiro.py --site` | o que está no ar, no GitHub Pages |
| `python docs/qa_roteiro.py --offline` | pula o que precisa do servidor das builds |
| `python docs/qa_roteiro.py -k marcador` | só o grupo com essa palavra no nome |
| `python docs/qa_roteiro.py --captura x.png` | salva uma captura do catálogo no fim |

Precisa de Chrome instalado e de `pip install websocket-client`. Sai com código
diferente de zero quando alguma checagem falha.

## Por que ele existe

Em 20/09/2026 dois bugs foram parar no ar e quem achou foi o Leo: a aba Públicas
vazia (`permission denied for table builds`) e os marcadores que abriam o
diálogo e não gravavam nada. Nenhum dos dois era difícil de pegar — bastava
abrir o app e fazer o de sempre. Os dois entraram no roteiro como checagem
própria, e é assim que ele cresce: **todo bug que o Leo achar vira uma linha
aqui**, para não achar duas vezes.

Os cliques são de verdade (CDP, `Input.dispatchMouseEvent`), não evento
sintético — evento sintético já passou verde com o drag e o duplo clique
quebrados.

## O que ele confere

**Arquivos** (sem abrir navegador, só quando roda nesta pasta)

- `.nojekyll` existe e nenhum caminho absoluto (`/assets/...`) no HTML.
- Todo `assets/...` citado no index.html existe **com a mesma caixa de letra** —
  o Pages é case-sensitive e o Windows não é, então `Assets/X.PNG` passa aqui e
  quebra lá.
- Todo MP3 do mapa de som existe em `assets/audio`.
- Todo card de região que o `data/regioes.js` aponta existe na pasta.

**Fundação** — 225 itens; as runas contadas pela estrutura batem com o número
que o gerador anotou (foi um leitor calado que escondeu 4 runas em 18/09);
a placa de entrada diz "Este é um projeto feito por hobby sem fins lucrativos." e o contato do autor
(League of Legends Brelgo#RPG, Discord brelgo; F13-T54), com os dois canais numa linha, um clique selecionando
o ID inteiro e a placa cabendo na tela nas quatro resoluções; a placa diz "Bem Vindo(a)!", "Meus Contatos" e
"League of Legends · Atualização <fase.tarefa> · patch <patch>" (F13-T57), e o número da atualização
(`ATUALIZACAO` no index.html) não fica para trás do último commit "F13-T…" — com o index.html mexido, uma tarefa
está em andamento e ele tem de estar à frente; entrar na loja sem exceção.

**Catálogo** — 225 cards desenhados; a busca filtra; a aba de núcleo vira
oficina com o estandarte de 46 px; a aba Todos volta a ser uma grade só.
No modo Ícones, o mouse não aciona o golpe do AD nem apaga o ícone (F13-T29,
bug nº 46); nos Cards, o golpe continua.
O número que a tela mostra é o que o resto usa (F13-T43, nºs 24, 32 e 33): a
eficiência nunca arredonda para cima — a Joia da Ruína e o Cetro Vampírico
saem 99,9%, fora do filtro "100% a 119%" e no grupo que vai até 99; o seletor de atributo conta itens; o preço com Reembolso sai
com as casas do catálogo (2.543,75g, 3.083,03g) e a soma da caixa fecha.
Ordenar por atributo não mistura pontos com % (F13-T43b, nº 25): primeiro os
pontos, depois a %, e o card dos Sapatos Enfeitiçados mostra "+20 · +8%".

**Calculadora** (F13-T42, bugs nºs 23 e 31) — o "Puxar da build ativa" usa
os itens que a build compra: sem as caixas Opcionais e, na Escolha 1, só o
padrão, e o painel "Atributos da build" da forja conta a mesma build; itens
sem vida não apagam a vida digitada. Roda depois dos grupos da
forja, porque troca de aba e de caixas.

**Falta pouco para publicar** (F13-T45, nºs 45, 49, 50 e 53) — com rascunho na
forja, publicar pergunta antes de abrir a janela; o campo do nome fica na tela
(e com o foco) enquanto se digita; o mesmo marcador ou o mesmo nome não
carimbam a "Última atualização"; tirar do site duas vezes faz o segundo
esperar, sem erro falso.

**Forja** — a build nova nasce com as 8 caixas; item entra na caixa; o modo
leitura esconde os atributos.

**Marcadores** — escolher, o segundo espaço, trocar um já preenchido e tirar no
`×`. O `×` só existe no hover, então o roteiro passa o mouse antes; sem isso o
clique cai num retângulo de tamanho zero e acusa bug que não existe.

**Runas** — a página fecha em 9 de 9 e a faixa aparece na forja.

**Habilidades** — o nível 1 aceita clique (já ficou inalcançável uma vez), o
supremo é recusado no nível 5 e aceito no 6.

**Texto** — exportar e reimportar devolve a mesma build (itens, marcadores,
habilidades e runas). F13-T36 (bugs nºs 17 e 28): a descrição e a observação
de várias linhas voltam iguais, pela interface (Copiar esta build → Importar)
e pelo texto de várias builds, com o pior dado — barras coladas, barra solta,
barra dupla, link, e linhas que parecem cabeçalho do formato (#, -, =, [ ]);
texto escrito à mão: " / " separa a descrição, " ¶ " a observação, "/"
colado é barra; texto exportado antes: a barra na observação continua barra;
quebras que chegam por fora (U+2028, \r, observação só de espaço, nome com
quebra) não derrubam item, caixa nem descrição; F13-T37 (bug nº 19): o texto
de várias builds (Selecionar → Copiar como texto) volta como várias builds,
cada uma com runas, fragmentos, habilidades, Mestre Forjador e campeão, pelo
botão de verdade; o cabeçalho de cada build fica com ela (comentário no meio,
régua dentro da build, cabeçalho entre a régua e o BUILD:); a mensagem avisa a
build sem caixa e o campeão desconhecido sem apagar o resumo nem a mensagem
mais nova, e "sem internet" é uma frase só; importar 10 builds grava e
redesenha uma vez; fragmento e modo que chegam
de fora não desmontam a linha; texto antigo com uma quebra invisível no meio
da linha fica inteiro; um campo de uma linha com uma quebra dentro não abre
linha nova.

**Texto, a trilha sem runa** (F13-T38, bug nº 35) — a primária escolhida sem
runa não leva a secundária junto na ida e volta; só a trilha, ou a secundária
escolhida sem runa, também voltam.

**Texto, o que o formato promete** (F13-T36b, achados da revisão da T36) —
pelo botão Importar: tópico de IA (`* dica`, `• dica`) antes da primeira caixa
vai para o "não encontrei" sem deixar uma caixa "Importados" vazia; texto só de
tópicos não importa build vazia, avisa que não achou nada; caixa sem grade
nasce com 6 colunas, como `docs/formato_de_importacao.md` diz, e a
"Importados" também, inclusive depois do F5 — o caminho antigo continua (`| ½`
dá 6, `| 2×1` dá 2); o nome errado numa build que fica sem caixa aparece no
aviso (no lote e sozinha); um tópico de IA entre dois `BUILD:` não funde as
builds (a parte sem caixa fica de fora, avisada).

**Rascunho** (F13-T24, bug nº 37) — com o Editar ligado e um item não salvo,
reabrir a build que já está na forja (duplo clique na linha, o Editar do
detalhe) mantém o rascunho; o coração da lista grava na hora sem gravar o
rascunho; e o Descartar continua voltando à cópia salva. Olha o
`rascunho.sujo` e o localStorage, não só a forja: um conserto que gravasse o
rascunho calado também deixaria o item na tela.

**Troca de build** (F13-T25, bug nº 38) — com o rascunho sujo, abrir outra
build pela lista, "+ Nova build" e Importar perguntam Salvar/Descartar como a
forja pergunta, e "Salvar e sair" grava e segue; excluir outra build e digitar
o nome na janela "Falta pouco para publicar" gravam o que é deles sem gravar as
caixas do rascunho; um Ctrl+S com essa janela aberta não solta a cópia (o
que se digita depois ainda grava); e o Enter da lista abre o diálogo com o
foco nele. Cada checagem monta o próprio estado e só responde o diálogo se ele
apareceu, para falhar sozinha no código de antes.

**Salvar** (F13-T31, bug nº 14; o `setItem` da biblioteca recusado) — o Salvar
não diz "salvo" (o botão fica aceso, o aviso de saída armado, sem o som); a placa
explica, com o foco nela; o "Salvar e sair" não sai; o Ctrl+S numa build limpa
não a suja; a cópia na memória não fica com o que não gravou, e o Descartar
descarta de verdade; o coração recusado avisa; a publicação que passou sem
gravar aqui pede para anotar o ID; com a gravação de volta, o aviso some
sozinho e o Salvar salva.

**Duas abas** (F13-T35, bug nº 27; várias abas de verdade no mesmo Chrome, a
mesma trava do navegador) — a aba nova já nasce parada enquanto confere a
trava; a segunda fica sob o véu, com a página por baixo sem resposta, e não
grava por cima; "Usar esta aba" recarrega do disco e assume, e a outra para;
parada, a aba não obedece a atalhos (Esc, Ctrl+S); a troca é recusada com
rascunho, com gravação recusada, com publicação, exclusão ou importação
esperando a internet — e o véu diz qual; a marca de uma aba que já perdeu a
vez não recusa; F5 mantém a dona; a dona que vai a outra página e volta pelo
Voltar volta inteira; a outra fechou: a parada avisa e assume; um link #b=
numa aba parada avisa e arma o aviso de saída; a dona presa num diálogo não
grava por cima da que assumiu; o "Limpar build" numa aba que perdeu a vez não
mexe em nada; a aba nova que esperou a vez relê o disco; "Usar esta aba" numa
aba de link assume sem o aviso falso de saída; a dona que quebra sem avisar é
percebida pela parada; a página de captura da observação fica com o foco no
editor; F5 da dona com outra aba na fila continua dona; outra aba que toma a
trava enquanto esta confere não deixa duas donas; o "saiu" que a dona regrava
logo depois não faz a aba nova tomar a vez; a trava negada pelo navegador não
prende a aba.

**Publicação órfã** (F13-T34, bug nº 42; servidor simulado, espera encurtada) —
com a publicação no ar, a build não se exclui (lista, forja, lote); despublicar
durante o "Atualizar publicação" espera; publicar durante uma exclusão no ar
espera; se a build some mesmo assim, a publicação recém-criada sai do site.

**Atualização** (F13-T33, bugs nºs 13 e 41) — abrir outra build depois de
recarregar não muda a "Última atualização" (e a publicada continua "Publicada");
uma mudança de verdade ainda carimba; o Mestre Forjador não acende a nota da
publicação; um Salvar durante uma publicação lenta acende; a build migrada do
formato antigo tem data.

**Última build** (F13-T32, bug nº 15) — com uma pública aberta, a última build
própria não se exclui (o Excluir desligado) e o "Fechar visualização" ainda
fecha; a exclusão da última própria não deixa cópia fantasma (e, desde a
F13-T53, nem uma "Build sem nome" no lugar); com uma visualização aberta, a
ativa gravada é a sua; o Excluir da forja numa visualização fecha sem
perguntar; a biblioteca gravada vazia não traz de volta a build do formato
antigo nem cria uma.

**Publicar** (F13-T30, bugs nºs 11, 12 e 26; servidor simulado) — o hidden
esconde sempre (Descartar sem rascunho, ⟳ em Minhas); o "+ Nova categoria" não
anda quando o rascunho aparece; durante "Publicando…" não há Fechar e o Enter
não manda outro pedido; depois de um erro o Enter fecha a placa; servidor lento:
o Fechar aparece (os 30 s encurtados trocando o relógio da página), a trava
segura e a resposta atrasada vale; a placa atrasada fica por cima do
"Alterações não salvas" e o Esc fecha só ela; ao salvar, o Descartar some na hora.

**Acessibilidade** — os quatro interruptores ligam, o "menos movimento" zera as
transições de verdade, e tudo sobrevive ao recarregar.
O daltonismo por tipo (F13-T50) é medido como a pessoa vê: o roteiro escolhe
cada modo com clique, lê a cor da faixa de núcleo dos cards de verdade (AD, AP,
Vitalidade) e passa as três pela simulação de Machado, Oliveira e Fernandes
(2009), com a tabela publicada em cada severidade de 0,1 a 1,0 (o pior caso
não é sempre a plena); a menor distância ΔE2000 entre elas tem
de ficar alta. A Geral não desce de 33 em nenhum dos três tipos (as cores do
jogo caem a 6; a Okabe-Ito de antes caía a 12 na tritanopia); cada tipo passa
de 40 no seu e ganha da Geral por 4 ou mais — senão o modo não teria razão de
existir. A ordem das habilidades (Q, W, E, R) é medida do mesmo jeito. E ainda:
a bolinha do menu é a cor que vai à tela, a calculadora segue a cor do núcleo,
o Desligado volta às cores do jogo e o "ligado" guardado antes vira a Geral.
Depois da revisão (F13-T50b): o texto da calculadora fica legível no papel
(contraste ≥ 4,5:1), as leituras alternativas da build seguem o núcleo, a brasa
da forja não muda, o menu se usa pelo teclado (Esc devolve o foco, Tab para fora
fecha, a explicação do tipo é anunciada) e cada tipo sobrevive ao recarregar.

**Bigorna** (F13-T51, o nº 39; a build sempre aberta, opção B do Leo) — a plaqueta sob a aba Builds nomeia a
build em todas as telas (loja, lista, forja, Runas, Calculadora); fora da forja diz "editando" e "● não salva";
no pior estado (nome de 63 letras, editando, não salva, caixa escolhida) nada estoura e o cabeçalho não muda de
altura em nenhuma resolução; o Ctrl+S salva da loja; "parar de editar" pergunta com rascunho e devolve o foco;
o nome leva à forja; renomear pelo campo muda a plaqueta e a faixa na hora; a faixa fica presa no topo ao rolar;
a gravação recusada aparece na hora; e uma pública aberta para ver não fica com o Editar ligado (o nº 40).

**Fechar a build** (F13-T52; Leo, 19/10/2026: "deveria ter uma opção de fechar") — o × da plaqueta fecha a
build (a plaqueta some, a build continua na lista, o disco não guarda build aberta, a aba Builds fica na lista,
o foco vai para a aba Builds); com rascunho, o × (o da plaqueta e o da faixa) pergunta antes; nada da build
fechada sobra na memória; sem build, o clique num item só abre a ficha (nenhuma pergunta, nada gravado); fechar
uma pública volta para a build de antes (ou para a bigorna vazia); e sem build as Runas só leem, a calculadora
não puxa, a forja não abre e o "Marcar em" fica parado.

**Entrada sem build** (F13-T53; Leo, 19/10/2026: "ao recarregar mantenha a build que já estava aberta, e o
primeiro acesso fica completamente vazio por conta do tour") — o primeiro acesso começa sem build nenhuma (nada
no disco; a lista diz "Nenhuma build ainda"); o F5 volta a build que estava aberta, e com a bigorna vazia fica
vazio; excluir a build aberta deixa a bigorna vazia, sem outra no lugar; e o #build-observacao sem build não
liga o Editar.

**Builds publicadas** — a lista vem do servidor e não traz "permission denied"; nenhuma desatualizada aparece
(a nota no pé diz quantas ficaram de fora); e o roteiro não registra evento no servidor de verdade.

**A barreira dos eventos** (F13-T56) — toda sessão do roteiro (e toda aba que ele abre) carrega, antes do app,
um `fetch` que responde "ok" ao `registrar_evento` sem sair da página. Antes, cada rodada (perfil novo, memória
limpa) registrava no Supabase do Leo uma "impressão" por build da aba Públicas — e a impressão alimenta a
popularidade. O contador `window.__eventosBarrados` mostra o que foi segurado.

**Públicas desatualizadas** (F13-T56; Leo, 19/10/2026: "builds marcadas como desatualizada não devem aparecer
nas públicas") — com uma lista montada no roteiro (sem servidor): a aba mostra só o catálogo de agora, nem na
popularidade; a nota diz quantas ficaram de fora; pelo ID exato a desatualizada ainda se acha, com a etiqueta;
e as impressões da lista ficam na página.

**Resoluções** — 2560×1440, 1920×1080 e 1600×900, a ordem do Leo, mais
1280×800 como piso de notebook: sem rolagem horizontal e nada fora da tela.
**Celular não é alvo** (Leo, 21/09/2026: "não tenho a intenção de fazer para o
celular"): o app é ferramenta de mesa, e 375px não entra na conta — medido, a
página abre com viewport de 513px e os cards têm 281px fixos.

**Console** — nenhuma exceção e nenhum 404 durante o percurso inteiro.

## Achado na primeira volta — e consertado (21/09/2026)

Com as **38 builds publicadas na tela**, a página travava: o Chrome queimava um
núcleo inteiro e parava de responder por mais de um minuto. Acontecia nas duas
pontas — no navegador do roteiro e no navegador embutido, contra o site no ar.

Causa, medida por dentro: cada marcador de **habilidade** sem a lista do campeão
no cache pedia a lista ao Data Dragon e, na resposta, mandava redesenhar a lista
inteira. 38 linhas × até 3 marcadores = dezenas de pedidos, e cada redesenho
fazia os pedidos de novo. **`renderBuildIndex` rodava ~80 vezes em 4 segundos.**

Conserto: `pedirRedesenho()` junta os pedidos e redesenha **uma vez por quadro**.
De ~80 para **7**, a página continua respondendo e a arte da habilidade chega
igual. Duas checagens novas seguram isso: "sem tempestade de redesenho" e "a
arte da habilidade chega no marcador".

O grupo das públicas continua sendo o **último** do roteiro: é o estado mais
pesado do app, e depois dele qualquer medida sai contaminada.

## O que ele não faz

Não olha. Cor, alinhamento, peso da animação, se o card ficou bonito — isso
continua sendo captura de tela e o aprovado do Leo. O roteiro só garante que o
caminho ainda anda.
