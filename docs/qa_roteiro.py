#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Roteiro de QA do Montador de Itens — os caminhos de sempre, percorridos a cada mudança.

    python docs/qa_roteiro.py            # o app desta pasta
    python docs/qa_roteiro.py --site     # o que está no ar, no GitHub Pages
    python docs/qa_roteiro.py -k marcador   # só as checagens com essa palavra

Por que ele existe: em 20/09/2026 dois bugs foram parar no ar e quem achou foi o
Leo — a aba Públicas vazia e os marcadores mudos. Nenhum dos dois era difícil de
pegar: bastava abrir o app e percorrer o de sempre. O roteiro faz isso com
clique de verdade (CDP), porque evento sintético já passou com bug no drag e no
duplo clique.

Ele não substitui o olho: mede o que dá para medir e cala sobre o resto.
Captura de tela e aprovado continuam por fora.

Precisa de: Chrome instalado e `pip install websocket-client`.
"""
import argparse
import atexit
import base64
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request

import websocket

# O console do Windows nasce em cp1252 e engasga no primeiro acento do relatório.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://brelgo.github.io/montador_de_itens_lol/"   # a conta do GitHub virou Brelgo em 30/09/2026 (o endereço antigo dá 404)
CHROMES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome",
]
# O Leo abre o app nestas três, nesta ordem de prioridade (20/09/2026). A quarta
# é um piso: notebook comum, conferido mas sem prioridade.
# Celular NÃO é alvo (Leo, 21/09/2026: "não tenho a intenção de fazer para o
# celular") — o app é ferramenta de mesa, e 375px nem entra na conta.
RESOLUCOES = [(2560, 1440), (1920, 1080), (1600, 900), (1280, 800)]

VERDE, VERMELHO, AMARELO, CINZA, FIM = "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[0m"


# ---------------------------------------------------------------- resultado
class Placar:
    def __init__(self):
        self.linhas = []

    def conta(self, grupo, nome, ok, detalhe="", pulou=False):
        self.linhas.append((grupo, nome, ok, detalhe, pulou))
        marca = (AMARELO + "–" + FIM) if pulou else ((VERDE + "ok" + FIM) if ok else (VERMELHO + "FALHOU" + FIM))
        print("  %-6s %-44s %s%s%s" % (marca, nome, CINZA, detalhe, FIM))

    @property
    def falhas(self):
        return [l for l in self.linhas if not l[2] and not l[4]]

    def resumo(self):
        passou = sum(1 for l in self.linhas if l[2] and not l[4])
        pulou = sum(1 for l in self.linhas if l[4])
        print("\n" + "=" * 78)
        if self.falhas:
            print("%sFALHOU: %d de %d%s" % (VERMELHO, len(self.falhas), len(self.linhas), FIM))
            for g, n, _, d, _ in self.falhas:
                print("  %s · %s — %s" % (g, n, d))
        else:
            print("%s%d checagens, nenhuma falha%s%s" % (VERDE, passou, (", %d pulada(s)" % pulou) if pulou else "", FIM))
        return 1 if self.falhas else 0


# ---------------------------------------------------------------- servidor
class Servidor:
    """Serve a pasta do projeto numa porta livre, só para o roteiro."""

    def __init__(self):
        import http.server
        s = socket.socket(); s.bind(("127.0.0.1", 0)); self.porta = s.getsockname()[1]; s.close()

        class Mudo(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=RAIZ, **k)

            def log_message(self, *a, **k):
                pass                      # o relatório é o que importa, não o log

            def handle_one_request(self):
                try:
                    super().handle_one_request()
                except ConnectionError:
                    self.close_connection = True   # o Chrome corta conexão à vontade

        handler = Mudo
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", self.porta), handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = "http://127.0.0.1:%d/" % self.porta

    def parar(self):
        self.httpd.shutdown()


# ---------------------------------------------------------------- navegador
class Sessao:
    def __init__(self, url):
        chrome = next((c for c in CHROMES if os.path.exists(c)), None)
        if not chrome:
            sys.exit("Não achei o Chrome. Ajuste CHROMES no topo do arquivo.")
        s = socket.socket(); s.bind(("127.0.0.1", 0)); porta = s.getsockname()[1]; s.close()
        self.porta = porta
        import tempfile
        # perfil próprio: dois Chromes no mesmo user-data-dir e o segundo não sobe
        perfil = tempfile.mkdtemp(prefix="qa-montador-")
        self.proc = subprocess.Popen(
            [chrome, "--headless=new", "--remote-debugging-port=%d" % porta, "--user-data-dir=" + perfil,
             "--window-size=1920,1080", "--no-first-run", "--hide-scrollbars", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        atexit.register(self.fechar)
        alvo = None
        for _ in range(80):
            try:
                alvo = [t for t in json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % porta))
                        if t["type"] == "page"][0]
                break
            except Exception:
                time.sleep(0.25)
        if not alvo:
            sys.exit("O Chrome não respondeu na porta de depuração.")
        self.ws = websocket.create_connection(alvo["webSocketDebuggerUrl"], suppress_origin=True)
        self.ws.settimeout(90)
        self._id = 0
        self.erros = []
        self.rede = []
        self.dialogos = []
        self.envia("Page.enable"); self.envia("Runtime.enable"); self.envia("Log.enable")
        self.url = url

    def fechar(self):
        try: self.proc.kill()
        except Exception: pass

    def nova_aba(self):
        """Uma segunda aba no MESMO Chrome — mesmo perfil, mesmo localStorage, e o
        evento "storage" chega de uma para a outra (F13-T35, duas abas abertas)."""
        req = urllib.request.Request("http://127.0.0.1:%d/json/new?about:blank" % self.porta, method="PUT")
        alvo = json.load(urllib.request.urlopen(req))
        outra = object.__new__(Sessao)
        outra.proc = None
        outra.porta = self.porta
        outra.ws = websocket.create_connection(alvo["webSocketDebuggerUrl"], suppress_origin=True)
        outra.ws.settimeout(90)
        outra._id = 0; outra.erros = []; outra.rede = []; outra.dialogos = []
        outra.envia("Page.enable"); outra.envia("Runtime.enable"); outra.envia("Log.enable")
        outra.url = self.url
        outra.alvo_id = alvo["id"]
        return outra

    def fechar_aba(self):
        """Fecha a aba de verdade (não só a conexão): aberta, ela continua ouvindo o
        localStorage e reage aos grupos seguintes do roteiro."""
        try: self.ws.close()
        except Exception: pass
        try: urllib.request.urlopen("http://127.0.0.1:%d/json/close/%s" % (self.porta, self.alvo_id)).read()
        except Exception: pass

    def envia(self, metodo, params=None):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": metodo, "params": params or {}}))
        while True:
            try:
                msg = json.loads(self.ws.recv())
            except websocket.WebSocketTimeoutException:
                # Acontece de verdade: com a lista pública cheia, o renderizador
                # some por mais de um minuto. Vira falha legível, não pilha.
                raise RuntimeError("o navegador parou de responder em %s" % metodo)
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})
            self._anota(msg)

    def _anota(self, msg):
        if msg.get("method") == "Page.javascriptDialogOpening":
            # Um diálogo nativo (confirm, alert, "sair sem salvar?") trava a
            # página inteira até alguém responder: o roteiro via só "o navegador
            # parou de responder". Agora ele anota qual foi e aceita.
            d = msg["params"]
            self.dialogos.append("%s: %s" % (d.get("type"), (d.get("message") or "")[:80]))
            self._id += 1
            self.ws.send(json.dumps({"id": self._id, "method": "Page.handleJavaScriptDialog",
                                     "params": {"accept": True}}))
            return
        if msg.get("method") == "Runtime.exceptionThrown":
            self.erros.append((msg["params"]["exceptionDetails"].get("text") or "")[:160])
        elif msg.get("method") == "Log.entryAdded":
            e = msg["params"]["entry"]
            if e.get("level") == "error":
                # 404 de arquivo é bug de publicação: o Pages é case-sensitive.
                alvo = e.get("url") or ""
                self.rede.append("%s %s" % (e.get("text", "")[:80], alvo))

    def js(self, expr):
        r = self.envia("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in r:
            # "Uncaught" sozinho não diz nada: a mensagem de verdade mora em exception.description
            d = r["exceptionDetails"]
            desc = ((d.get("exception") or {}).get("description") or d.get("text") or "erro no JS").split(chr(10))[0]
            raise RuntimeError(desc + " :: " + expr[:80])
        return r["result"].get("value")

    def abrir(self, caminho=""):
        self.envia("Page.navigate", {"url": self.url + caminho})
        fim = time.time() + 30
        while time.time() < fim:
            try:
                msg = json.loads(self.ws.recv())
            except websocket.WebSocketTimeoutException:
                raise RuntimeError("a página não carregou: %s" % (self.url + caminho)[:90])
            self._anota(msg)
            if msg.get("method") == "Page.loadEventFired":
                return
        raise RuntimeError("a página não terminou de carregar")

    def caixa(self, seletor):
        # Rolar só quando precisa: um scrollIntoView à toa fecha menu ancorado
        # (que escuta scroll de propósito) e o clique seguinte cai no vazio.
        return self.js("""(() => { const e = document.querySelector(%s); if (!e) return null;
          let r = e.getBoundingClientRect();
          if (r.top < 4 || r.bottom > innerHeight - 4 || r.left < 4 || r.right > innerWidth - 4) {
            e.scrollIntoView({block:'center'}); r = e.getBoundingClientRect();
          }
          if (r.width < 1 || r.height < 1) return 'invisivel';
          return [Math.round(r.left + r.width/2), Math.round(r.top + r.height/2)]; })()""" % json.dumps(seletor))

    def hover(self, seletor):
        p = self.caixa(seletor)
        if not isinstance(p, list):
            raise RuntimeError("não achei (ou tem tamanho zero): " + seletor)
        self.envia("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": p[0], "y": p[1]})
        time.sleep(0.25)
        return p

    def clicar(self, seletor, espera=0.4):
        """Clique de verdade. O mouseMoved antes não é enfeite: sem ele, controle
        que só existe no hover tem tamanho zero e o clique cai no vazio."""
        p = self.hover(seletor)
        for tipo in ("mousePressed", "mouseReleased"):
            self.envia("Input.dispatchMouseEvent",
                       {"type": tipo, "x": p[0], "y": p[1], "button": "left", "clickCount": 1})
        time.sleep(espera)

    def tela(self, largura, altura):
        self.envia("Emulation.setDeviceMetricsOverride",
                   {"width": largura, "height": altura, "deviceScaleFactor": 1, "mobile": False})
        time.sleep(0.6)

    def tela_normal(self):
        self.envia("Emulation.clearDeviceMetricsOverride")

    def captura(self, destino, altura=900):
        dados = self.envia("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                           "clip": {"x": 0, "y": 0, "width": 1920, "height": altura, "scale": 1}})["data"]
        with open(destino, "wb") as f:
            f.write(base64.b64decode(dados))

    # ------- atalhos do app
    def entrar(self):
        self.js("document.getElementById('entrar').click(); document.documentElement.style.scrollBehavior='auto'")
        time.sleep(1.8)

    def limpar_memoria(self):
        self.js("localStorage.clear()")
        self.abrir()
        time.sleep(0.8)

    def nova_build(self):
        self.js("switchTab('build'); showBuildScreen('lista')")
        time.sleep(0.5)
        self.js("document.getElementById('new-build').click()")
        time.sleep(1.2)
        self.js("showBuildScreen('forja')")
        time.sleep(0.8)


# ---------------------------------------------------------------- 1. arquivos
def checar_arquivos(p):
    """O que dá para conferir sem abrir o navegador. O Pages é case-sensitive e
    não perdoa nome com uma letra diferente."""
    print("\n%sARQUIVOS%s" % (AMARELO, FIM))
    idx = open(os.path.join(RAIZ, "index.html"), encoding="utf-8").read()

    p.conta("arquivos", ".nojekyll existe", os.path.exists(os.path.join(RAIZ, ".nojekyll")))

    absolutos = re.findall(r'(?:src|href)="(/[^/][^"]*)"', idx)
    p.conta("arquivos", "nenhum caminho absoluto", not absolutos, ", ".join(absolutos[:3]))

    # todo assets/... citado no HTML e no CSS existe, com a mesma caixa de letra
    # Trecho montado em JS (`${...}`) ou com curinga não é arquivo: fica de fora.
    citados = sorted({c for c in re.findall(r'["\'\(](assets/[^"\'\)\s]+)', idx)
                      if "${" not in c and "*" not in c})
    faltando = [c for c in citados if not _existe_exato(c)]
    p.conta("arquivos", "assets citados existem (caixa exata)", not faltando,
            "%d citados; faltam: %s" % (len(citados), ", ".join(faltando[:3]) or "nenhum"))

    # áudio: o mapa vive no index.html e os arquivos na pasta do Leo
    mapa = re.search(r"const SOM_ARQUIVOS = (\{.*?\n\});", idx, re.S)
    if mapa:
        arquivos = sorted({v for lista in json.loads(mapa.group(1)).values() for v in lista})
        sumidos = [a for a in arquivos if not _existe_exato("assets/audio/" + a)]
        p.conta("arquivos", "áudio do mapa existe em assets/audio", not sumidos,
                "%d arquivos; sumiram: %s" % (len(arquivos), ", ".join(sumidos[:3]) or "nenhum"))
    else:
        p.conta("arquivos", "áudio do mapa existe em assets/audio", False, "não achei SOM_ARQUIVOS no index.html")

    # cards de região: o data/regioes.js aponta, a pasta tem de ter
    reg = os.path.join(RAIZ, "data", "regioes.js")
    if os.path.exists(reg):
        corpo = open(reg, encoding="utf-8").read()
        bloco = corpo.split("medidas:", 1)[1].split("variantes:", 1)[0]
        cards = ["assets/regioes/cards/%s.jpg" % n for n in re.findall(r'"([^"]+)":\s*\[', bloco)]
        sumidos = [c for c in cards if not _existe_exato(c)]
        p.conta("arquivos", "cards de região existem", not sumidos,
                "%d cards; sumiram: %s" % (len(cards), ", ".join(sumidos[:2]) or "nenhum"))


def _existe_exato(rel):
    """os.path.exists mente no Windows: 'Assets/X.PNG' passa. Aqui cada pedaço do
    caminho é conferido contra o que a pasta realmente tem."""
    atual = RAIZ
    for pedaco in rel.split("?")[0].split("#")[0].split("/"):
        if not pedaco:
            continue
        try:
            nomes = os.listdir(atual)
        except (NotADirectoryError, FileNotFoundError):
            return False
        if pedaco not in nomes:
            return False
        atual = os.path.join(atual, pedaco)
    return True


# ---------------------------------------------------------------- 2. o app
def checar_fundacao(s, p):
    print("\n%sFUNDAÇÃO%s" % (AMARELO, FIM))
    s.limpar_memoria()
    n = s.js("CATALOG.items.length")
    p.conta("fundação", "225 itens no catálogo", n == 225, "vieram %s" % n)
    # Contadas pela estrutura e conferidas contra o número que o gerador anotou:
    # foi um leitor calado que deixou 4 runas de fora em 18/09/2026.
    r = s.js("""(() => { const n = RUNAS.trilhas.reduce((a, t) =>
        a + t.slots.reduce((b, sl) => b + sl.runas.length, 0), 0);
      return { contadas: n, meta: RUNAS.meta.runas,
               frag: RUNAS.fragmentos.reduce((a, g) => a + g.runas.length, 0),
               metaFrag: RUNAS.meta.fragmentos }; })()""")
    p.conta("fundação", "runas contadas batem com o gerador",
            r["contadas"] == r["meta"] and r["frag"] == r["metaFrag"],
            "%s runas (gerador diz %s), %s fragmentos (diz %s)"
            % (r["contadas"], r["meta"], r["frag"], r["metaFrag"]))
    patch = s.js("CATALOG.meta && CATALOG.meta.patch")
    p.conta("fundação", "o catálogo diz de que patch é", bool(patch), "patch %s" % patch)
    s.entrar()
    p.conta("fundação", "entrar na loja não gera erro", not s.erros, "; ".join(s.erros[:2]))


def checar_catalogo(s, p):
    print("\n%sCATÁLOGO%s" % (AMARELO, FIM))
    n = s.js("document.querySelectorAll('#grid .card').length")
    p.conta("catálogo", "225 cards desenhados", n == 225, "vieram %s" % n)

    s.js("""(() => { const c = document.getElementById('search-input'); c.value = 'doran';
            c.dispatchEvent(new Event('input', {bubbles: true})); })()""")
    time.sleep(0.6)
    achados = s.js("document.querySelectorAll('#grid .card').length")
    p.conta("catálogo", "a busca filtra", 0 < achados < 225, "'doran' → %s itens" % achados)
    s.js("""(() => { const c = document.getElementById('search-input'); c.value = '';
            c.dispatchEvent(new Event('input', {bubbles: true})); })()""")
    time.sleep(0.6)

    s.clicar(".class-tab[data-classe='AD']", 0.8)
    estado = s.js("""(() => { const o = document.getElementById('oficina');
      const e = document.querySelector('.estandarte');
      return { display: getComputedStyle(o).display, faixa: e ? Math.round(e.getBoundingClientRect().width) : 0,
               corpo: [...document.body.classList].filter(c => c.startsWith('nucleo')) }; })()""")
    # A regressão de 18–20/09: a .oficina deixou de ser grid e o estandarte
    # engoliu a largura toda em toda aba de núcleo.
    p.conta("catálogo", "aba de núcleo vira oficina com estandarte",
            estado["display"] == "grid" and estado["faixa"] == 46,
            "display %s, faixa %spx" % (estado["display"], estado["faixa"]))

    s.clicar(".class-tab[data-classe='']", 0.8)
    p.conta("catálogo", "aba Todos volta a ser uma coluna só de grade",
            s.js("getComputedStyle(document.getElementById('oficina')).display") == "block")

    # F13-T9: o Ápice não pode apagar número do item. A Tocha perdia os +80 de PdH
    # (o texto diz "+20% de PdH"), a Couraça Protoplasmática ia de 600 para 241
    # de Vida, e o Elixir da Força somava as duas alternativas de um "ou". E o
    # caminho antigo: o Lacre Sombrio continua indo de 15 para 55 no Ápice.
    # F13-T21: desde o Capítulo 1 de 23/09 o Ápice vem em números (apexNumeric):
    # o total no máximo substitui, o "a mais" soma. A Couraça chega a 841,18 de
    # Vida no nível 13 (a leitura humilde da T9 deixava os 600), a Tocha mantém
    # os +80 e ganha o multiplicador de +20%, e o Atma — o caso que provou que
    # o texto não bastava — chega a 50% de crítico, não 30%.
    ap = s.js("""(() => { const pega = (n) => CATALOG.items.find(i => i.namePt === n);
      const le = (n) => { const it = pega(n); state.applyApex = true;
        const r = effectiveAttributes(it, { itemId: it.slug }).map(a => a.raw); state.applyApex = false; return r; };
      return { tocha: le('Tocha de Chamas Negras'), couraca: le('Couraça Protoplasmática'),
               elixir: le('Elixir da Força'), lacre: le('Lacre Sombrio'), atma: le('Acerto de Contas de Atma') }; })()""")
    p.conta("catálogo", "Ápice não apaga número do item (Tocha +80 e +20%)",
            "+80 de Poder de Habilidade" in ap["tocha"] and "+20% de Poder de Habilidade" in ap["tocha"],
            "Tocha %s" % ap["tocha"][:3])
    p.conta("catálogo", "Ápice usa o total do catálogo (Couraça 841,18; Atma 50%)",
            "+841,18 de Vida" in ap["couraca"] and "+50% de Chance de Acerto Crítico" in ap["atma"],
            "Couraça %s | Atma %s" % (ap["couraca"][:1], [x for x in ap["atma"] if "Crítico" in x]))
    p.conta("catálogo", "Ápice não soma as duas pontas de um \"ou\"", ap["elixir"] == [], str(ap["elixir"]))
    p.conta("catálogo", "Ápice ainda sobe o que é máximo (Lacre 15 → 55)",
            "+55 de Poder de Habilidade" in ap["lacre"], str(ap["lacre"][:1]))

    # F13-T15 (Leo, 23/09: eficiência "com a passiva"): duas regras que valem
    # para o catálogo inteiro. O desconto do Reembolso nunca piora um item — a
    # base antiga derrubava o Limite da Razão de 119% para 91% —, e a caixa com
    # um item só mostra a mesma eficiência da ficha dele, com e sem Reembolso.
    ef = s.js("""(() => { const piora = [], dif = [];
      CATALOG.items.forEach(it => { const val = (on) => { state.applyCashback = on; return [itemEfficiency(it), goldEfficiency([{ itemId: it.slug }]).pct]; };
        const [off, cxOff] = val(false), [on, cxOn] = val(true);
        if (hasCashback(it) && off !== null && on !== null && on < off - 0.05) piora.push(it.namePt);
        if ((off !== null && cxOff !== null && Math.abs(off - cxOff) > 0.06) || (on !== null && cxOn !== null && Math.abs(on - cxOn) > 0.06)) dif.push(it.namePt); });
      state.applyCashback = false; return { piora, dif }; })()""")
    p.conta("catálogo", "o Reembolso nunca piora a eficiência de um item", not ef["piora"],
            ("pioram: " + ", ".join(ef["piora"][:4])) if ef["piora"] else "nenhum dos 225")
    p.conta("catálogo", "caixa de um item só = eficiência da ficha dele", not ef["dif"],
            ("diferem: " + ", ".join(ef["dif"][:4])) if ef["dif"] else "os 225, com e sem Reembolso")
    # F13-T20: o valor em ouro vem pronto do Capítulo 1 (goldValueBase). O
    # contorno da T15 (efficiencyBase × preço) errava por arredondamento em 16
    # itens — o Limite da Razão valia 3.331,72g em vez de 3.331,67g.
    vo = s.js("""(() => { const dif = [], com = [];
      CATALOG.items.forEach(it => { const b = it.costAnalysis && it.costAnalysis.goldValueBase;
        if (typeof b !== 'number') return; com.push(it);
        if (Math.abs(valorEmOuro(it) - b) > 0.001) dif.push(it.namePt + ' ' + valorEmOuro(it).toFixed(2) + '≠' + b); });
      return { n: com.length, dif }; })()""")
    p.conta("catálogo", "valor em ouro = o do catálogo, sem conta por fora", vo["n"] > 200 and not vo["dif"],
            ("diferem: " + "; ".join(vo["dif"][:3])) if vo["dif"] else "%d itens com Valor de Ouro (base)" % vo["n"])
    # F13-T22: o Ápice e o Mestre Forjador mudam o valor em ouro, com os números
    # do catálogo. O Atma no ápice vale 3.866,67g (133,33%); forjado, qualquer
    # Lendário elegível ganha os 1.000g do bônus. E a caixa com um item só
    # continua igual à ficha dele com o Ápice ligado.
    mx = s.js("""(() => { const atma = CATALOG.items.find(i => i.namePt === 'Acerto de Contas de Atma');
      state.applyApex = true; const efAtma = itemEfficiency(atma);
      const dif = [];
      CATALOG.items.forEach(it => { const f = itemEfficiency(it), c = goldEfficiency([{ itemId: it.slug }]).pct;
        if (f !== null && c !== null && Math.abs(f - c) > 0.06) dif.push(it.namePt); });
      state.applyApex = false;
      const alvo = CATALOG.items.find(i => mfEligible(i) && typeof i.costAnalysis.goldValueBase === 'number');
      const antes = build.masterwork; build.masterwork = true;
      const ouro = goldEfficiency([{ itemId: alvo.slug, mf: true }]).gold;
      build.masterwork = antes;
      return { efAtma, dif, alvo: alvo.namePt, ouro, base: alvo.costAnalysis.goldValueBase, bonus: alvo.masterwork.bonusGold }; })()""")
    p.conta("catálogo", "o Ápice muda a eficiência (Atma 133,33%)", abs((mx["efAtma"] or 0) - 133.33) < 0.01,
            "Atma no ápice: %s%%" % mx["efAtma"])
    p.conta("catálogo", "o Mestre Forjador soma o bônus ao item forjado",
            abs(mx["ouro"] - (mx["base"] + (mx["bonus"] or 0))) < 0.01 and (mx["bonus"] or 0) > 0,
            "%s: %sg + %sg = %sg" % (mx["alvo"], mx["base"], mx["bonus"], mx["ouro"]))
    p.conta("catálogo", "caixa de um item só = ficha, também no Ápice", not mx["dif"],
            ("diferem: " + ", ".join(mx["dif"][:4])) if mx["dif"] else "os 225")
    # F13-T29 (bug nº 46, achado pelo Leo): no modo Ícones o mouse fazia os
    # ícones do AD sumirem. A reação do núcleo não entra ali (F11-T5), mas o AD
    # anima o próprio card, e a variante 5 apagava a superfície por 235 ms. O
    # sorteio escolhe a 5 uma vez em cinco: a checagem olha se QUALQUER variante
    # foi acionada, e mede a opacidade da superfície logo depois do mouse entrar.
    def passar_mouse_nos_ad(modo, n=6):
        s.clicar('.view-btn[data-view="%s"]' % modo, 0.8)
        s.js("document.querySelector('#grid').scrollIntoView({block: 'start'}); window.scrollBy(0, -40); 'ok'")
        time.sleep(0.4)
        idx = s.js("""[...document.querySelectorAll('#grid .card')].map((c, i) => [c, i])
          .filter(([c]) => c.classList.contains('fx-ad') && c.getBoundingClientRect().top > 0
                           && c.getBoundingClientRect().bottom < innerHeight).slice(0, %d).map(([, i]) => i)""" % n)
        vistos = []
        for i in idx:
            c = s.js("(() => { const r = document.querySelectorAll('#grid .card')[%d].getBoundingClientRect(); return [r.left + r.width/2, r.top + r.height/2]; })()" % i)
            s.envia("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": c[0], "y": c[1]})
            time.sleep(0.06)
            vistos.append(s.js("""(() => { const c = document.querySelectorAll('#grid .card')[%d];
              return { variante: [1,2,3,4,5].filter(v => c.classList.contains('a' + v))[0] || 0,
                       op: Number(getComputedStyle(c.querySelector('.card-surface')).opacity) }; })()""" % i))
            s.envia("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 3, "y": 3})
            time.sleep(0.3)
        return vistos
    ic = passar_mouse_nos_ad("icons")
    p.conta("catálogo", "Ícones: o mouse não aciona o golpe do AD (nem apaga o ícone)",
            len(ic) >= 4 and all(v["variante"] == 0 and v["op"] > 0.99 for v in ic),
            "%d ícones AD; variantes %s; menor opacidade %.2f" % (len(ic), [v["variante"] for v in ic], min([v["op"] for v in ic] or [0])))
    cd = passar_mouse_nos_ad("cards", 4)
    p.conta("catálogo", "Cards: o golpe do AD continua (caminho antigo)", len(cd) >= 3 and all(v["variante"] > 0 for v in cd),
            "%d cards AD; variantes %s" % (len(cd), [v["variante"] for v in cd]))

    # F13-T43 (nºs 24, 32 e 33): o número que a tela mostra é o mesmo que o
    # filtro, o cabeçalho do grupo, o seletor e a soma usam. O pior dado: a Joia
    # da Ruína (99,995%) e o Cetro Vampírico (99,98%), que aparecem "100,0%";
    # Sapatos Enfeitiçados, com Penetração Mágica plana e em %; o Arco do Axioma
    # (2.543,75g com Reembolso) e a Força da Trindade (3.083,03g).
    n43 = s.js("""(() => {
      const it = n => CATALOG.items.find(i => i.namePt === n);
      const joia = it('Joia da Ruína'), cetro = it('Cetro Vampírico');
      const antes = { eff: new Set(state.efficiency), sort: state.sort, cash: state.applyCashback };
      state.efficiency = new Set(['100-119']);
      const noFiltro = [joia, cetro].map(x => itemMatchesFilters(x));
      const naTela = [joia, cetro].map(x => fmtEff(itemEfficiency(x)));
      state.efficiency = antes.eff;
      state.sort = 'eff-desc';
      const grupo = [joia, cetro].map(x => groupLabelFn(CATALOG.items)(x));
      state.sort = antes.sort;
      const opt = [...document.querySelectorAll('#sort-attr-select option')].find(o => o.value === 'Penetração Mágica');
      const comPen = CATALOG.items.filter(x => (x.attributes || []).some(a => a.stat === 'Penetração Mágica')).length;
      state.applyCashback = true;
      const arco = it('Arco do Axioma'), forca = it('Força da Trindade');
      const precos = [arco, forca].map(x => fmtG(effectivePrice(x)));
      const caixa = catTotal({ items: [{ itemId: arco.slug }, { itemId: forca.slug }], kind: 'comum' });
      const soma = [arco, forca].reduce((t, x) => t + effectivePrice(x), 0);
      state.applyCashback = antes.cash;
      return { noFiltro, naTela, grupo, curto: [fmtEff(106.1), fmtEff(100), fmtEff(1450 / 2500 * 100)], opt: opt ? opt.textContent : null, comPen, precos, caixa: fmtG(caixa), soma: fmtG(soma),
               netArco: arco.cashback.netGold, netForca: forca.cashback.netGold };
    })()""")
    # (Leo, 17/10/2026: a eficiência nunca arredonda para cima) 99,995% e 99,98%
    # saem 99,9%, ficam fora de "100% a 119%" e no grupo que vai até 99
    import re as _re
    faixas = [tuple(int(x) for x in _re.findall(r"\d+", g)[:2]) for g in n43["grupo"]]
    p.conta("catálogo", "eficiência que a tela mostra é a do filtro e a do grupo",
            n43["naTela"] == ["99,9%", "99,9%"] and n43["noFiltro"] == [False, False]
            and all(len(f) == 2 and f[0] <= 99 <= f[1] for f in faixas)
            and n43["curto"] == ["106,1%", "100,0%", "58,0%"],
            "na tela %s · no filtro 100–119%% %s · grupo %s · 106,1, 100 e 1450÷2500 (57,99999…): %s" % (n43["naTela"], n43["noFiltro"], n43["grupo"], n43["curto"]))
    p.conta("catálogo", "o seletor de atributo conta itens",
            n43["opt"] == "Penetração Mágica (%d itens)" % n43["comPen"], "%s · itens com o atributo: %d" % (n43["opt"], n43["comPen"]))
    p.conta("catálogo", "preço com Reembolso com as casas do catálogo",
            n43["precos"] == ["2.543,75g", "3.083,03g"] and n43["caixa"] == n43["soma"] == "5.626,78g",
            "preços %s (catálogo: %s e %s) · caixa %s · soma %s" % (n43["precos"], n43["netArco"], n43["netForca"], n43["caixa"], n43["soma"]))


def checar_calculadora(s, p):
    """F13-T42 (bugs nºs 23 e 31): o "Puxar da build ativa" usa os itens que a
    build de fato compra — sem as caixas Opcionais e, na Escolha 1, só o padrão —
    e não apaga a vida digitada quando os itens não dão vida."""
    print("\n%sCALCULADORA%s" % (AMARELO, FIM))
    s.nova_build()
    garantir_build_editavel(s)
    puxa = """(() => { document.getElementById('calc-from-build').click(); return { hp: calc.hp, armor: calc.armor, mr: calc.mr }; })()"""
    r = s.js("""(() => { const it = n => CATALOG.items.find(i => i.namePt === n);
      const ent = n => ({ itemId: it(n).slug, note: '' });
      const pr = it('Presságio de Randuin'), es = it('Armadura de Espinhos'), wa = it('Armadura de Warmog');
      const v = (x, st) => (x.attributes || []).filter(a => a.stat === st && a.unit === 'flat').reduce((t, a) => t + a.value, 0);
      build.cats = [
        { id: 'cat-c1', name: 'Escolha', desc: '', kind: 'escolha', span: 2, cols: 1, rows: 2, items: [ent('Presságio de Randuin'), ent('Armadura de Espinhos')] },
        { id: 'cat-c2', name: 'Se precisar', desc: '', kind: 'opcional', span: 2, cols: 6, rows: 1, items: [ent('Armadura de Warmog')] },
      ];
      gravarBuild(); renderBuildAll();
      return { esperado: { hp: v(pr, 'Vida'), armor: v(pr, 'Armadura') }, comTudo: { hp: v(pr, 'Vida') + v(es, 'Vida') + v(wa, 'Vida'), armor: v(pr, 'Armadura') + v(es, 'Armadura') + v(wa, 'Armadura') } }; })()""")
    s.js("switchTab('calc')")
    time.sleep(0.6)
    veio = s.js(puxa)
    p.conta("calculadora", "Puxar da build ativa: sem Opcionais e só o padrão da Escolha 1",
            veio["hp"] == r["esperado"]["hp"] and veio["armor"] == r["esperado"]["armor"] and r["esperado"] != r["comTudo"],
            "veio vida %s / armadura %s · o padrão dá %s / %s · somando tudo daria %s / %s" % (
                veio["hp"], veio["armor"], r["esperado"]["hp"], r["esperado"]["armor"], r["comTudo"]["hp"], r["comTudo"]["armor"]))
    # a revisão da T42: o painel "Atributos da build" da forja somava as
    # Opcionais, e a Calculadora deixou de somar — os dois contam a mesma build
    painel = s.js("""(() => { switchTab('build'); showBuildScreen('forja'); renderBuildTotals();
      const t = document.querySelector('#build-totals .bt-title'), l = document.querySelector('#build-totals .cs-list');
      return { titulo: t ? t.textContent : '', lista: l ? l.textContent : '' }; })()""")
    s.js("switchTab('calc')")
    time.sleep(0.4)
    p.conta("calculadora", "o painel Atributos da build conta a mesma build",
            "1 item" in painel["titulo"] and ("+%d" % r["esperado"]["hp"]) in painel["lista"]
            and ("+%d" % r["comTudo"]["hp"]) not in painel["lista"], "%s · %s" % (painel["titulo"], painel["lista"][:80]))
    s.js("""(() => { const it = CATALOG.items.find(i => i.namePt === 'Cota de Malha');
      build.cats = [{ id: 'cat-c1', name: 'Núcleo', desc: '', kind: 'comum', span: 2, cols: 6, rows: 1, items: [{ itemId: it.slug, note: '' }] }];
      gravarBuild(); calc.hp = 2000; renderCalc(); return 'ok'; })()""")
    veio = s.js(puxa)
    p.conta("calculadora", "Puxar da build ativa: itens sem vida não apagam a vida digitada",
            veio["hp"] == 2000 and veio["armor"] > 0, "vida %s (era 2000) · armadura %s" % (veio["hp"], veio["armor"]))
    s.js("switchTab('build')")
    s.nova_build()


def checar_forja(s, p):
    print("\n%sFORJA%s" % (AMARELO, FIM))
    s.nova_build()
    caixas = s.js("build.cats.length")
    p.conta("forja", "nova build nasce com as 8 caixas sugeridas", caixas == 8, "vieram %s" % caixas)

    s.js("build.cats[1].items.push({ itemId: CATALOG.items[0].slug, note: '' }); renderBuildAll()")
    time.sleep(0.5)
    p.conta("forja", "item entra na caixa", s.js("build.cats[1].items.length") == 1)

    # A build nasce em leitura: é o padrão do Leo, "o jogador vê os itens, não os
    # atributos". Os dois lados da regra são conferidos, leitura e edição.
    atributos = """(() => { const t = document.querySelector('.build-totals.show');
      return t ? getComputedStyle(t).display !== 'none' : false; })()"""
    p.conta("forja", "modo leitura esconde os atributos", not s.js(atributos),
            "editando = %s" % s.js("document.body.classList.contains('editando')"))
    s.clicar("#edit-switch", 0.8)
    p.conta("forja", "o Editar liga", s.js("document.body.classList.contains('editando')"))
    p.conta("forja", "e com ele os atributos voltam", s.js(atributos))

    # F13-T3: os dois verbos que estavam escondidos no balão. Como só existem no
    # hover, o mouse passa antes — senão o clique cai num retângulo invisível.
    s.hover(".item-tile")
    p.conta("forja", "os botões do molde aparecem no hover",
            s.js("""(() => { const f = document.querySelector('.item-tile .tile-acoes');
              return !!f && Number(getComputedStyle(f).opacity) > .9
                     && getComputedStyle(f).pointerEvents === 'auto'; })()"""))
    s.clicar(".item-tile .ta-nota", 0.6)
    p.conta("forja", "o ✎ abre a observação",
            s.js("document.getElementById('note-editor').classList.contains('show')"))
    s.js("closeNoteEditor(false)")
    time.sleep(0.4)
    antes = s.js("build.cats[1].items.length")
    s.hover(".item-tile")
    s.clicar(".item-tile .ta-x", 0.6)
    p.conta("forja", "o ✕ tira o item da caixa", s.js("build.cats[1].items.length") == antes - 1,
            "de %s para %s" % (antes, s.js("build.cats[1].items.length")))

    # F13-T7: dois ✕ em 150 ms tiravam o item errado (achado da caçada de bugs).
    # A saída espera a animação; a posição mudava no meio. Pedir A e B tem de
    # deixar o C.
    fim = s.js("""(async () => { const c = build.cats[1]; c.items = [];
      CATALOG.items.filter(i => i.tier === 'Lendário').slice(0, 3).forEach(it => c.items.push({ itemId: it.slug, note: '' }));
      renderBuildAll(); await new Promise(r => setTimeout(r, 400));
      const c3 = c.items[2].itemId;
      removeItemFromCategory(c.id, 0); await new Promise(r => setTimeout(r, 150));
      removeItemFromCategory(c.id, 1); await new Promise(r => setTimeout(r, 900));
      return { sobrou: c.items.map(i => i.itemId), esperado: [c3] }; })()""")
    p.conta("forja", "dois ✕ seguidos tiram os dois pedidos", fim["sobrou"] == fim["esperado"],
            "sobrou %s" % fim["sobrou"])

    # F13-T4: o tipo da caixa deixou de ser um botão que dá a volta olímpica.
    s.clicar(".build-cat:nth-of-type(2) .cat-kind", 0.6)
    menu = s.js("""(() => { const m = document.getElementById('kind-menu');
      if (!m || !m.classList.contains('show')) return null;
      const r = m.getBoundingClientRect();
      return { opcoes: [...m.querySelectorAll('button')].map(b => b.dataset.kind),
               marcado: (m.querySelector('[aria-checked="true"]') || {}).dataset,
               cabe: r.left >= 0 && r.top >= 0 && r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1 }; })()""")
    p.conta("forja", "o tipo da caixa abre um menu com os quatro",
            bool(menu) and menu["opcoes"] == ["comum", "prioridade", "opcional", "escolha"] and menu["cabe"],
            "%s" % (menu or "não abriu"))
    s.clicar('#kind-menu [data-kind="opcional"]', 0.7)
    p.conta("forja", "escolher no menu troca o tipo e fecha",
            s.js("build.cats[1].kind") == "opcional"
            and not s.js("document.getElementById('kind-menu').classList.contains('show')"),
            "ficou %s" % s.js("build.cats[1].kind"))
    s.js("build.cats[1].kind = 'comum'; renderBuild()")


def checar_marcadores(s, p):
    """O bug de 20/09: o diálogo abria, a escolha não gravava. Todo passo aqui é
    clique de verdade, e o × só existe no hover."""
    print("\n%sMARCADORES%s" % (AMARELO, FIM))
    s.js("switchTab('build'); showBuildScreen('forja')")
    time.sleep(0.6)
    s.clicar("#build-marks .mark-slot[data-i='0']")
    p.conta("marcadores", "o diálogo abre", not s.js("document.getElementById('marker-dialog').hidden"))
    s.clicar("#md-tags .md-cell")
    primeiro = s.js("JSON.stringify(build.markers)")
    p.conta("marcadores", "escolher grava na build", s.js("build.markers.length") == 1, primeiro)

    s.clicar("#build-marks .mark-slot[data-i='1']")
    s.clicar("#md-tags .md-cell:nth-child(3)")
    p.conta("marcadores", "o segundo espaço também", s.js("build.markers.length") == 2)

    s.clicar("#build-marks .mark-slot[data-i='0']")
    s.clicar("#md-tags .md-cell:nth-child(5)")
    p.conta("marcadores", "trocar um já preenchido",
            s.js("JSON.stringify(build.markers)") != primeiro and s.js("build.markers.length") == 2)

    s.hover("#build-marks .mark-slot[data-i='1']")
    s.clicar("#build-marks .mark-slot[data-i='1'] .mark-x")
    p.conta("marcadores", "o × tira", s.js("build.markers.length") == 1)


def garantir_build_editavel(s):
    """Runas, habilidades e texto são da build ativa, e a grade de habilidades só
    existe com o Editar ligado. Rodando um grupo sozinho (-k), nada disso existe
    ainda — então o roteiro monta o cenário antes de cobrar."""
    if not s.js("typeof build !== 'undefined' && !!build"):
        s.nova_build()
    else:
        s.js("switchTab('build'); showBuildScreen('forja')")
        time.sleep(0.5)
    if not s.js("document.body.classList.contains('editando')"):
        s.clicar("#edit-switch", 0.8)


def checar_runas(s, p):
    print("\n%sRUNAS%s" % (AMARELO, FIM))
    garantir_build_editavel(s)
    s.js("switchTab('runas')")
    time.sleep(0.8)
    s.js("""(() => { const b = document.querySelector('.runas-modo[data-modo=\"montar\"]');
            if (b) b.click(); })()""")
    time.sleep(0.8)
    # A página só oferece runas depois da trilha primária escolhida, e as da
    # secundária só depois da secundária. Então: trilha, escolhe o que aparecer,
    # secundária, escolhe o que aparecer de novo.
    s.clicar("#runas-trilhas [data-trilha]", 0.6)
    fim = time.time() + 40
    while time.time() < fim:
        # Uma escolha por fileira: toda opção carrega data-escolher, então clicar
        # sempre na primeira "não escolhida" só ficaria trocando a mesma vaga.
        acao = s.js("""(() => {
          for (const sec of document.querySelectorAll('#runas-corpo .runas-slot')) {
            if (sec.querySelector('[data-secundaria]')) {
              if (!sec.querySelector('[data-secundaria].ativa')) {
                sec.querySelector('[data-secundaria]').click();
                return 'secundaria';
              }
              continue;
            }
            if (sec.querySelector('.escolhida')) continue;
            const b = sec.querySelector('[data-escolher]:not(.bloqueada)');
            if (b) { b.click(); return 'runa'; }
          }
          return ''; })()""")
        if not acao:
            break
        time.sleep(0.25)
    cheias = s.js("""(() => { const p = paginaDaBuild();
      return (p.assinatura ? 1 : 0) + p.slots.filter(Boolean).length
           + p.secundarios.filter(Boolean).length + p.fragmentos.filter(Boolean).length; })()""")
    p.conta("runas", "a página fecha em 9 de 9", cheias == 9, "%s de 9" % cheias)
    # F13-T18: o app não aplica as trocas automáticas, só avisa — e a tela diz isso.
    # No Resumido, que é onde as linhas "Vira…" aparecem (em Ícones o card não
    # tem texto, e a legenda some junto de propósito).
    s.js("document.querySelector('.runas-vista[data-vista=resumido]').click(); 'ok'")
    time.sleep(0.4)
    rodape_montar = s.js("""(() => { const r = document.querySelector('#runas-corpo .runas-rodape');
      return !!r && getComputedStyle(r).display !== 'none' && r.textContent.includes('O app só avisa'); })()""")
    p.conta("runas", "a faixa aparece na forja",
            s.js("""(() => { switchTab('build'); showBuildScreen('forja');
              const f = document.querySelector('.build-runas');
              return !!f && !f.hidden && getComputedStyle(f).display !== 'none'; })()"""))
    # F13-T17: o bloco "Controle de grupo válido" do markdown sumia no leitor,
    # calado — a ficha do Golpe Desleal nunca mostrou a lista.
    s.js("switchTab('runas'); 'ok'")
    time.sleep(0.6)
    s.js("""(() => { const b = document.querySelector('.runas-modo[data-modo="ler"]'); if (b) b.click(); })()""")
    time.sleep(0.5)
    s.js("document.querySelector('.runas-vista[data-vista=completo]').click(); 'ok'")
    time.sleep(0.4)
    s.js("""(() => { const t = [...document.querySelectorAll('#runas-trilhas [data-trilha]')]
      .find(b => b.dataset.trilha === 'dominacao'); if (t) t.click(); })()""")
    time.sleep(0.6)
    cg = s.js("""(() => { const a = [...document.querySelectorAll('article.runa')].find(e => e.title === 'Golpe Desleal');
      const c = a && a.querySelector('.cg');
      return { visivel: !!c && getComputedStyle(c).display !== 'none', texto: c ? c.textContent : '' }; })()""")
    p.conta("runas", "a ficha mostra o controle de grupo válido",
            cg["visivel"] and "Inclui" in cg["texto"] and "Cripple" in cg["texto"],
            "Golpe Desleal, modo Completo" if cg["visivel"] else "o bloco não aparece")
    rodape_ler = s.js("""(() => { const r = document.querySelector('#runas-corpo .runas-rodape');
      return !!r && getComputedStyle(r).display !== 'none' && r.textContent.includes('O app só avisa'); })()""")
    p.conta("runas", "a tela diz que as trocas “Vira…” são só aviso", rodape_montar and rodape_ler,
            "no Ler e no Montar" if rodape_montar and rodape_ler
            else "falta no " + " e no ".join(n for n, ok in (("Montar", rodape_montar), ("Ler", rodape_ler)) if not ok))


def checar_fragmento(s, p):
    """F13-T23: o Atributo adicional guarda o fragmento escolhido (entry.frag)."""
    print("\n%sFRAGMENTO DO ATRIBUTO ADICIONAL%s" % (AMARELO, FIM))
    s.nova_build()
    if not s.js("document.body.classList.contains('editando')"):
        s.clicar("#edit-switch", 0.8)
    s.js("""(() => { const c = build.cats[3]; c.items = [{ itemId: 'stat-bonus', note: '' }, { itemId: 'stat-bonus', note: 'segundo' }];
      switchTab('build'); showBuildScreen('forja'); renderBuildAll(); return 'ok'; })()""")
    time.sleep(0.8)
    sel = s.js("'.build-cat[data-cat-id=\"' + build.cats[3].id + '\"] .item-tile'")
    s.clicar(sel + " .item-icon", 0.8)
    n = s.js("document.getElementById('escolher-fragmento').hidden ? 0 : document.querySelectorAll('#fr-lista [data-frag]').length")
    p.conta("fragmento", "clicar no ícone abre a escolha dos fragmentos", n > 30, "%s fragmentos na lista" % n)
    if n:
        s.clicar('#fr-lista [data-frag="Ouro · Vida"]', 0.8)
    s.js("(() => { build.cats[3].items[1].frag = 'Prata · Swiftness'; renderBuildAll(); return 'ok'; })()")
    t = s.js("""(() => { const cx = build.cats[3]; return { f: cx.items.map(e => e.frag || null),
      attrs: sumAttributes(cx.items).map(x => x.stat + '|' + x.unit + '|' + x.value), ouro: goldEfficiency(cx.items).gold }; })()""")
    p.conta("fragmento", "o fragmento entra nos atributos e no ouro",
            t["f"] == ["Ouro · Vida", "Prata · Swiftness"] and "Vida|flat|375" in t["attrs"] and "Velocidade de Ataque|percent|10" in t["attrs"]
            and abs(t["ouro"] - 1650) < 0.01, "%s · %sg" % (t["attrs"], t["ouro"]))
    # Os caminhos que listam os campos da entrada um a um: texto, lote, link e servidor.
    s.js("gravarBuild(); 'ok'")
    v = s.js("""(() => { const quer = JSON.stringify(['Ouro · Vida', 'Prata · Swiftness']);
      const deTexto = (txt) => JSON.stringify(textToBuild(txt).cats.flatMap(c => c.items).filter(e => e.itemId === 'stat-bonus').map(e => e.frag || null));
      const b = library.builds.find(x => x.id === build.id);
      const lk = linkParaBuild('#' + buildParaLink(b).split('#')[1]);
      const sv = caixasDoServidor(caixasParaServidor(build.cats), []);
      const so = (cats) => JSON.stringify(cats.flatMap(c => c.items).filter(e => e.itemId === 'stat-bonus').map(e => e.frag || null));
      return { texto: deTexto(buildToText()) === quer, lote: deTexto(loteParaTexto([build.id]).split(String.fromCharCode(10) + String.fromCharCode(10) + '=====')[0]) === quer,
               link: so(lk.cats) === quer, servidor: so(sv) === quer }; })()""")
    p.conta("fragmento", "o fragmento viaja no texto, no lote, no link e na publicação", all(v.values()),
            ", ".join(k for k, ok in v.items() if not ok) or "os quatro")


def checar_habilidades(s, p):
    print("\n%sHABILIDADES%s" % (AMARELO, FIM))
    garantir_build_editavel(s)
    # O nível 1 já ficou inalcançável uma vez, por causa do rótulo transbordando.
    s.clicar(".bh-cel[data-hab='Q'][data-nivel='1']")
    p.conta("habilidades", "nível 1 aceita clique", (s.js("build.habilidades[0]") or "") == "Q",
            "ficou %r" % s.js("build.habilidades[0]"))
    s.clicar(".bh-cel[data-hab='R'][data-nivel='5']")
    p.conta("habilidades", "supremo recusado no nível 5", (s.js("build.habilidades[4]") or "") != "R")
    s.clicar(".bh-cel[data-hab='R'][data-nivel='6']")
    p.conta("habilidades", "supremo aceito no nível 6", (s.js("build.habilidades[5]") or "") == "R")

    # F13-T8: duplicar perdia runas, habilidades e Mestre Forjador (caçada de bugs).
    antes = s.js("""(() => { build.masterwork = true; gravarBuild();
      return { hab: build.habilidades.map(x => x || '-').join(''), runas: JSON.stringify(build.runas), id: build.id }; })()""")
    s.js("duplicateBuild(build.id)")
    time.sleep(0.6)
    depois = s.js("({ hab: build.habilidades.map(x => x || '-').join(''), runas: JSON.stringify(build.runas), id: build.id, mf: !!build.masterwork })")
    p.conta("habilidades", "duplicar leva habilidades, runas e Mestre Forjador",
            depois["id"] != antes["id"] and depois["hab"] == antes["hab"] and depois["runas"] == antes["runas"] and depois["mf"],
            "habilidades %s" % depois["hab"])


def checar_texto(s, p):
    """Exportar e reimportar tem de devolver a mesma build — é como o Leo move
    build entre máquinas e como uma IA gera build para ele."""
    print("\n%sTEXTO%s" % (AMARELO, FIM))
    # sempre uma build nova, com as 8 caixas: herdar a do grupo anterior fazia o
    # teste depender da ordem (rodando só -k texto, não havia caixa nem item)
    s.nova_build()
    garantir_build_editavel(s)
    # F13-T12: a comparação antiga contava as CHAVES do objeto de runas — sempre
    # 6 — e não via runa sumindo. Agora compara o conteúdo, com a pior página:
    # Slot 1 da primária vazio e fragmento do Slot 1 vazio. Era exatamente aí
    # que a ida e volta perdia runas (a escrita espremia os vazios e a leitura
    # confiava na posição).
    s.js("""(() => { const t = RUNAS.trilhas[0], t2 = RUNAS.trilhas[1];
      const F = RUNAS.fragmentos;
      // itens: texto sem item é recusado pelo importador, e aí não há ida e volta
      if (!build.cats.some(c => c.items.length))
        build.cats[3].items = CATALOG.items.filter(i => i.tier === 'Lendário').slice(0, 3).map(it => ({ itemId: it.slug, note: '' }));
      build.runas = normRunas({ primaria: t.id, assinatura: t.slots[0].runas[0].id,
        slots: ['', t.slots[2].runas[0].id, t.slots[3].runas[0].id],
        secundaria: t2.id, secundarios: [t2.slots[1].runas[0].id, t2.slots[3].runas[0].id],
        fragmentos: ['', F[1].runas[0].id, F[2].runas[0].id] });
      gravarBuild(); return 'ok'; })()""")
    RETRATO = """(() => JSON.stringify({ itens: build.cats.flatMap(c => c.items.map(i => i.itemId)),
      marcadores: build.markers, habilidades: build.habilidades, runas: normRunas(build.runas) }))()"""
    antes = s.js(RETRATO)
    id_antes = s.js("build.id")
    texto = s.js("buildToText()")
    s.js("switchTab('build'); showBuildScreen('lista'); document.getElementById('toggle-io').classList.add('active')")
    time.sleep(0.4)
    s.js("document.getElementById('import-text').value = %s" % json.dumps(texto))
    s.js("document.getElementById('import-btn').click()")
    time.sleep(1.4)
    depois = s.js(RETRATO)
    importou = s.js("build.id") != id_antes
    if not importou:
        det = "a importação NÃO criou build nova: comparar seria comparar a build com ela mesma"
    elif antes == depois:
        det = "itens, marcadores, habilidades e runas iguais"
    else:
        a, d = json.loads(antes), json.loads(depois)
        det = "; ".join("%s: %s → %s" % (k, json.dumps(a[k], ensure_ascii=False)[:90], json.dumps(d[k], ensure_ascii=False)[:90])
                        for k in a if a[k] != d[k])
    p.conta("texto", "exportar e reimportar devolve a mesma build", importou and antes == depois, det)

    # F13-T38 (bug nº 35): a linha RUNAS só saía com runa na primária. Com a
    # trilha escolhida e sem runa, o texto ia só com RUNAS 2 e FRAGMENTOS, e na
    # volta a secundária sumia junto (o normRunas não guarda secundária sem
    # primária) — sem aviso. O pior dado: primária sem runa com a secundária
    # cheia; só a trilha; a secundária escolhida sem runa.
    r38 = s.js("""(() => { const t = RUNAS.trilhas[0], t2 = RUNAS.trilhas[1], F = RUNAS.fragmentos;
      const it = CATALOG.items.find(i => i.tier === 'Lendário').namePt;
      const volta = (pg) => { const linhas = linhasDeRunas(pg);
        const r = textToBuild(['BUILD: T38', ...linhas, '[COMUM] Núcleo', '- ' + it].join(String.fromCharCode(10)));
        return { ok: JSON.stringify(normRunas(pg)) === JSON.stringify(normRunas(r.runas)) && !r.unknown.length,
                 linhas: linhas.join(' ¦ '), unknown: r.unknown }; };
      return {
        semRuna: volta({ primaria: t.id, secundaria: t2.id, secundarios: [t2.slots[1].runas[0].id, t2.slots[3].runas[0].id],
                         fragmentos: [F[0].runas[0].id, F[1].runas[0].id, F[2].runas[0].id] }),
        soTrilha: volta({ primaria: t.id }),
        secSemRuna: volta({ primaria: t.id, assinatura: t.slots[0].runas[0].id, secundaria: t2.id }),
      }; })()""")
    p.conta("texto", "primária sem runa não leva a secundária junto", r38["semRuna"]["ok"], r38["semRuna"]["linhas"][:150])
    p.conta("texto", "trilha escolhida sem runa volta no texto",
            r38["soTrilha"]["ok"] and r38["secSemRuna"]["ok"],
            "só a trilha: %s · secundária sem runa: %s" % (r38["soTrilha"]["linhas"][:60], r38["secSemRuna"]["linhas"][:90]))
    # a revisão da T38: o link também perdia a trilha sem runa (só levava a
    # página com alguma runa escolhida) — o texto e o link levam a mesma página
    lk = s.js("""(() => { const t = RUNAS.trilhas[0], t2 = RUNAS.trilhas[1];
      const vai = (pg) => { const b = { ...build, id: 'lk38', isActive: false, runas: normRunas(pg) };
        const url = buildParaLink(b); const volta = linkParaBuild(url.slice(url.indexOf('#b=')));
        return JSON.stringify(normRunas(pg)) === JSON.stringify(normRunas(volta && volta.runas)); };
      return { soTrilha: vai({ primaria: t.id }), comSec: vai({ primaria: t.id, secundaria: t2.id }) }; })()""")
    p.conta("texto", "o link leva a trilha escolhida sem runa", lk["soTrilha"] and lk["comSec"], "%s" % lk)

    # F13-T36 (bugs nºs 17 e 28): a descrição e a observação têm várias linhas,
    # e o texto é uma linha por campo. A observação saía com a quebra crua (a
    # segunda linha sumia, ou virava descrição da caixa com "#", ou item com
    # "-"); a descrição voltava partida em qualquer "/" ("poke/sustain"). O pior
    # dado: barras coladas, barra solta, barra dupla, link, e linhas que parecem
    # cabeçalho do formato.
    DESC = "Build de poke/sustain para a rota do meio (3/0, AD/AP)" + chr(10) + "Contra tanque: AD / AP no fim // ou não" + chr(10) + "https://exemplo.com/a/b"
    NOTA = "segurar até os 20 min" + chr(10) + "#1 contra tanque" + chr(10) + "- não vender / nunca" + chr(10) + "= marco falso" + chr(10) + "[COMUM] caixa falsa"
    s.js("""(() => { const c = build.cats.find(x => x.items.length); build.desc = %s; c.items[0].note = %s; c.desc = 'desc da caixa';
      window.__qaCaixa = build.cats.indexOf(c); gravarBuild(); return 'ok'; })()""" % (json.dumps(DESC), json.dumps(NOTA)))
    texto36 = s.js("buildToText()")
    id36 = s.js("build.id")
    s.js("switchTab('build'); showBuildScreen('lista'); document.getElementById('toggle-io').classList.add('active')")
    time.sleep(0.4)
    s.js("document.getElementById('import-text').value = %s" % json.dumps(texto36))
    s.js("document.getElementById('import-btn').click()")
    time.sleep(1.4)
    r36 = s.js("""(() => { const c = build.cats[window.__qaCaixa] || {}; return { nova: build.id !== %s, desc: build.desc, nota: (c.items && c.items[0] || {}).note,
      caixa: c.desc, caixas: build.cats.length, msg: document.getElementById('io-msg').textContent }; })()""" % json.dumps(id36))
    p.conta("texto", "descrição e observação de várias linhas voltam iguais (Copiar esta build → Importar)",
            r36["nova"] and r36["desc"] == DESC and r36["nota"] == NOTA and r36["caixa"] == "desc da caixa" and "não encontr" not in r36["msg"].lower(),
            "nova %s · descrição %s · observação %s · caixa %s · aviso: %s" % (r36["nova"], "igual" if r36["desc"] == DESC else json.dumps(r36["desc"], ensure_ascii=False)[:90],
            "igual" if r36["nota"] == NOTA else json.dumps(r36["nota"], ensure_ascii=False)[:90], r36["caixa"], r36["msg"][:60] or "—"))
    # o texto de várias builds (Selecionar → Copiar como texto) é outro escritor
    lote36 = s.js("""(() => { const r = textToBuild(loteParaTexto([build.id])); const c = r.cats[window.__qaCaixa] || {};
      return { desc: r.desc, nota: (c.items && c.items[0] || {}).note, unknown: r.unknown }; })()""")
    p.conta("texto", "o texto de várias builds leva a descrição e a observação inteiras",
            lote36["desc"] == DESC and lote36["nota"] == NOTA and not lote36["unknown"],
            "descrição %s · observação %s · não encontrei %s" % ("igual" if lote36["desc"] == DESC else json.dumps(lote36["desc"], ensure_ascii=False)[:80],
            "igual" if lote36["nota"] == NOTA else json.dumps(lote36["nota"], ensure_ascii=False)[:80], lote36["unknown"]))
    # texto escrito à mão (ou por IA, pelo docs/formato_de_importacao.md): " / " separa, "/" colado é barra
    mao = s.js("""(() => { const r = textToBuild(%s); return { desc: r.desc, nota: (r.cats[0].items[0] || {}).note }; })()""" % json.dumps(chr(10).join([
        "BUILD: t", "DESCRIÇÃO: Crítico puro. / / A Coletora primeiro contra poke/sustain", "[COMUM] Core | 3x1", "- Abatedora * AD/AP ¶ segurar até 3/0"])))
    p.conta("texto", "texto escrito à mão: \" / \" separa a descrição e \" ¶ \" a observação; \"/\" colado é barra",
            mao["desc"] == "Crítico puro." + chr(10) + "A Coletora primeiro contra poke/sustain" and mao["nota"] == "AD/AP" + chr(10) + "segurar até 3/0",
            "descrição %s · observação %s" % (json.dumps(mao["desc"], ensure_ascii=False), json.dumps(mao["nota"], ensure_ascii=False)))
    # texto exportado antes da T36 (a observação saía crua): " / " e " // " na observação são barra, como eram
    velho36 = s.js("""(() => { const n = CATALOG.items.filter(i => i.tier === 'Lendário').slice(0, 3).map(i => i.namePt);
      const r = textToBuild(['BUILD: velho', '[COMUM] Core | 3x1', '- ' + n[0] + ' * AD / AP', '- ' + n[1] + ' * 3 / 0 no lane', '- ' + n[2] + ' * a // b'].join(String.fromCharCode(10)));
      return { notas: r.cats[0].items.map(i => i.note), unknown: r.unknown }; })()""")
    p.conta("texto", "texto exportado antes: a barra na observação continua barra",
            velho36["notas"] == ["AD / AP", "3 / 0 no lane", "a // b"] and not velho36["unknown"], "%s" % velho36)
    # quebras que chegam por fora (U+2028 colado, \r, observação só de espaço, nome da build com quebra) não derrubam item, caixa nem descrição
    fora = s.js("""(() => { const c = build.cats.find(x => x.items.length >= 2) || build.cats.find(x => x.items.length); const guarda = JSON.stringify({ n: build.name, d: build.desc, c });
      const L = String.fromCharCode(0x2028), P = String.fromCharCode(0x2029), R = String.fromCharCode(13), N = String.fromCharCode(10);
      build.name = 'Jinx' + N + '- ' + CATALOG.items[0].namePt; build.desc = 'x' + P + 'y' + R + 'z';
      c.items[0].note = ' ' + N + ' '; if (c.items[1]) c.items[1].note = 'a' + L + 'b'; c.name = 'Core' + L + 'falsa' + R + 'x';
      const i = build.cats.indexOf(c); const r = textToBuild(buildToText()); const rc = r.cats[i] || {};
      const res = { nome: r.name, desc: r.desc, caixas: r.cats.length, esperado: build.cats.length, itens: (rc.items || []).length, itensAntes: c.items.length,
        nota1: rc.items && rc.items[1] ? rc.items[1].note : null, tem2: !!c.items[1], caixa: rc.name, unknown: r.unknown };
      const g = JSON.parse(guarda); build.name = g.n; build.desc = g.d; Object.assign(c, g.c); return res; })()""")
    p.conta("texto", "quebras que chegam por fora não derrubam item, caixa nem descrição",
            fora["nome"].startswith("Jinx - ") and fora["desc"] == "x" + chr(10) + "y" + chr(10) + "z" and fora["caixas"] == fora["esperado"]
            and fora["itens"] == fora["itensAntes"] and (not fora["tem2"] or fora["nota1"] == "a" + chr(10) + "b") and fora["caixa"] == "Core falsa x" and not fora["unknown"],
            "%s" % fora)
    # fragmento e modo que chegam de fora (link #b= ou pública montados à mão) não
    # desmontam a linha: o fragmento sai do catálogo, e o modo só se for um modo de verdade
    ff = s.js("""(() => { const c = build.cats.find(x => x.items.length); const N = String.fromCharCode(10);
      const comFrag = CATALOG.items.find(i => temFragmentos(i)); const guarda = JSON.stringify(c.items);
      c.items[0].note = 'nota'; c.items[0].frag = 'x' + N + '- ' + CATALOG.items[1].namePt;
      c.items.push({ itemId: comFrag.slug, note: '', frag: 'Prata · X] * y [z' });
      const i = build.cats.indexOf(c); const r = textToBuild(buildToText()); const rc = r.cats[i] || { items: [] };
      const res = { itens: rc.items.length, esperado: c.items.length, nota0: (rc.items[0] || {}).note, notaFrag: (rc.items[rc.items.length - 1] || {}).note, unknown: r.unknown };
      c.items = JSON.parse(guarda);
      const salvo = library.builds.find(b => !b.temp && b.id !== build.id); const modo = salvo.mode;   // outra: a aberta é lida da memória viva
      salvo.mode = 'ARAM' + N + '[OPCIONAL] Injetada' + N + '- ' + CATALOG.items[1].namePt;
      const rl = textToBuild(loteParaTexto([salvo.id])); salvo.mode = modo;
      res.caixasLote = rl.cats.length; res.caixasEsperadas = salvo.cats.length; return res; })()""")
    p.conta("texto", "fragmento e modo que chegam de fora não desmontam a linha",
            ff["itens"] == ff["esperado"] and ff["nota0"] == "nota" and ff["notaFrag"] == "" and not ff["unknown"] and ff["caixasLote"] == ff["caixasEsperadas"],
            "%s" % ff)
    # texto antigo com U+2028 no meio de uma linha (colado na descrição da caixa ou no marco): a linha fica inteira
    u28 = s.js("""(() => { const L = String.fromCharCode(0x2028), N = String.fromCharCode(10);
      const r = textToBuild(['BUILD:' + L + 'Jinx', '[COMUM] Core | 3x1', '# contra AD' + L + 'AP no fim', '= ~14min' + L + '6.500g', '- ' + CATALOG.items[1].namePt].join(N));
      return { nome: r.name, desc: (r.cats[0] || {}).desc, marco: (r.cats[0] || {}).marco, itens: ((r.cats[0] || {}).items || []).length }; })()""")
    p.conta("texto", "texto antigo com uma quebra invisível no meio da linha fica inteiro",
            u28["nome"] == "Jinx" and u28["desc"] == "contra AD AP no fim" and u28["marco"] == "~14min 6.500g" and u28["itens"] == 1, "%s" % u28)
    # F13-T37 (bug nº 19): o texto de várias builds (Selecionar → Copiar como texto)
    # voltava como UMA build, com o nome da última, todas as caixas empilhadas, a
    # régua virando marco — e sem runas, fragmentos, habilidades nem Mestre
    # Forjador, que o lote nem escrevia. Três builds diferentes, pelo botão de verdade.
    RETRATO37 = """(b => JSON.stringify({ nome: b.name, modo: b.mode, desc: b.desc, layout: layoutValido(b.layout), mf: !!b.masterwork,
      camp: b.champion ? b.champion.key : null, marc: normMarkers(b.markers), runas: normRunas(b.runas), hab: normHabilidades(b.habilidades),
      caixas: (b.cats || []).map(c => ({ n: c.name, d: c.desc || '', m: c.marco || '', k: c.kind, w: catCols(c), h: catRows(c),
        i: c.items.map(e => [e.itemId, e.note || '', !!e.mf, e.frag || '']) })) }))"""
    texto37 = s.js("""(async () => { await Campeoes.carregar();
      const t = RUNAS.trilhas[0], t2 = RUNAS.trilhas[1], F = RUNAS.fragmentos;
      const lend = CATALOG.items.filter(i => i.tier === 'Lendário' && mfEligible(i)).slice(0, 2);
      const champs = [Campeoes.porNome('Jinx'), Campeoes.porNome('Ahri'), null];
      const ids = [];
      ['Lote A', 'Lote B', 'Lote C'].forEach((nome, k) => {
        createNewBuild(nome, [{ id: 'cat-qa37-' + k, name: 'Core ' + k, desc: 'caixa ' + k, marco: '~' + (k + 14) + 'min', kind: 'comum', span: 2, cols: 3, rows: 1,
          items: lend.map((it, j) => ({ itemId: it.slug, note: 'nota ' + k + j, ...(j === 0 && k !== 2 ? { mf: true } : {}) })) }],
          k === 1 ? 'ARAM' : "Summoner's Rift", champs[k], [{ t: 'hab', letter: 'Q' }]);
        build.desc = 'descrição ' + k; build.layout = k === 0 ? 'arvore' : 'tabuleiro'; build.masterwork = k !== 2;
        build.runas = normRunas({ primaria: t.id, assinatura: t.slots[0].runas[k % t.slots[0].runas.length].id,
          slots: [t.slots[1].runas[0].id, t.slots[2].runas[0].id, t.slots[3].runas[0].id],
          secundaria: t2.id, secundarios: [t2.slots[1].runas[0].id, t2.slots[2].runas[0].id], fragmentos: [F[0].runas[0].id, F[1].runas[0].id, F[2].runas[0].id] });
        build.habilidades = normHabilidades(['Q','W','E','Q','Q','R','Q','W','Q','W','R','W','W','E','E','R','E','E']);
        gravarBuild(); ids.push(build.id);
      });
      window.__qa37 = ids; return loteParaTexto(ids); })()""")
    antes37 = s.js("window.__qa37.map(id => (%s)(library.builds.find(b => b.id === id)))" % RETRATO37)
    s.js("switchTab('build'); showBuildScreen('lista'); document.getElementById('toggle-io').classList.add('active')")
    time.sleep(0.4)
    s.js("document.getElementById('import-text').value = %s" % json.dumps(texto37))
    s.js("document.getElementById('import-btn').click()")
    time.sleep(2.5)   # o campeão vem da lista do Data Dragon, depois
    r37 = s.js("""(() => { const novas = library.builds.filter(b => !window.__qa37.includes(b.id) && /^Lote [ABC]$/.test(b.name));
      return { depois: ['Lote A', 'Lote B', 'Lote C'].map(n => { const b = novas.find(x => x.name === n); return b ? (%s)(b) : null; }),
        quantas: novas.length, msg: document.getElementById('io-msg').textContent }; })()""" % RETRATO37)
    difs = [("ABC"[k], json.loads(a), json.loads(d) if d else None) for k, (a, d) in enumerate(zip(antes37, r37["depois"])) if a != d]
    det = "3 builds iguais às originais · %s" % r37["msg"][:70] if not difs and r37["quantas"] == 3 else "%d build(s) importada(s) · diferenças: %s · %s" % (
        r37["quantas"], "; ".join("%s: %s" % (n, "faltou" if d is None else ", ".join(k for k in a if a[k] != d[k])) for n, a, d in difs) or "nenhuma", r37["msg"][:90])
    p.conta("texto", "o texto de várias builds volta como várias builds, com runas, habilidades, Mestre Forjador e campeão",
            not difs and r37["quantas"] == 3 and "Importadas 3 builds" in r37["msg"], det)
    # o cabeçalho de cada build fica com ela: escrito antes do BUILD: da seguinte (texto à
    # mão ou de IA) não vai para a anterior; e um BUILD: repetido no cabeçalho só renomeia
    cab = s.js("""(() => { const N = String.fromCharCode(10), it = CATALOG.items.filter(i => i.tier === 'Lendário')[0].namePt;
      const dois = textoParaBlocos = dividirBuilds(['BUILD: Alfa', "MODO: Summoner's Rift", 'CAMPEÃO: Jinx', '[COMUM] Core | 2x1', '- ' + it, '',
        'MODO: ARAM', 'CAMPEÃO: Ahri', 'BUILD: Beta', '[COMUM] Core | 2x1', '- ' + it].join(N)).map(textToBuild);
      const um = dividirBuilds(['BUILD: rascunho', 'MODO: ARAM', 'CAMPEÃO: Jinx', 'DESCRIÇÃO: crítico puro', 'MESTRE FORJADOR: sim',
        'BUILD: Jinx crítico', '[COMUM] Core | 2x1', '- ' + it].join(N)).map(textToBuild);
      const R = '=========='; const it2 = CATALOG.items.filter(i => i.tier === 'Lendário')[1].namePt;
      const reguaTitulo = dividirBuilds(['BUILD: Alfa', "MODO: Summoner's Rift", R, '[COMUM] Core | 2x1', '- ' + it, '',
        'BUILD: Beta', 'MODO: ARAM', R, '[COMUM] Core | 2x1', '- ' + it2].join(N)).map(textToBuild);
      const reguaCaixas = dividirBuilds(['BUILD: Alfa', '[COMUM] Core | 2x1', '- ' + it, R, '[OPCIONAL] Situacional | 2x1', '- ' + it2, '',
        'BUILD: Beta', '[COMUM] Core | 2x1', '- ' + it].join(N)).map(textToBuild);
      const comentario = dividirBuilds(['BUILD: Alfa', "MODO: Summoner's Rift", '[COMUM] Core | 2x1', '- ' + it, '',
        'MODO: ARAM', 'Segunda opção:', 'BUILD: Beta', '[COMUM] Core | 2x1', '- ' + it2].join(N)).map(textToBuild);
      const reguaDepois = dividirBuilds(['BUILD: Alfa', '[COMUM] Core | 2x1', '- ' + it, R, 'MODO: ARAM', 'BUILD: Beta', '[COMUM] Core | 2x1', '- ' + it2].join(N)).map(textToBuild);
      const resumo = rs => rs.map(r => [r.name, r.mode, r.cats.length]);
      return { dois: dois.map(r => [r.name, r.mode, r.championName]), um: um.map(r => [r.name, r.mode, r.championName, r.desc, r.masterwork, r.cats.length]),
        reguaTitulo: resumo(reguaTitulo), reguaCaixas: resumo(reguaCaixas), comentario: resumo(comentario), reguaDepois: resumo(reguaDepois) }; })()""")
    p.conta("texto", "o cabeçalho de cada build fica com ela (antes do BUILD: da seguinte, com comentário no meio; BUILD: repetido só renomeia; régua dentro da build é só enfeite)",
            cab["dois"] == [["Alfa", "Summoner's Rift", "Jinx"], ["Beta", "ARAM", "Ahri"]]
            and cab["um"] == [["Jinx crítico", "ARAM", "Jinx", "crítico puro", True, 1]]
            and cab["reguaTitulo"] == [["Alfa", "Summoner's Rift", 1], ["Beta", "ARAM", 1]]
            and cab["reguaCaixas"] == [["Alfa", "", 2], ["Beta", "", 1]]
            and cab["comentario"] == [["Alfa", "Summoner's Rift", 1], ["Beta", "ARAM", 1]]
            and cab["reguaDepois"] == [["Alfa", "", 1], ["Beta", "ARAM", 1]], "%s" % cab)
    # a mensagem do lote: a build sem caixa é avisada pelo nome (com uma build ou várias),
    # e o aviso do campeão entra no resumo, com o nome da build, em vez de apagá-lo
    def importa(texto, espera=1.8):
        s.js("switchTab('build'); showBuildScreen('lista'); document.getElementById('toggle-io').classList.add('active')")
        time.sleep(0.3)
        s.js("document.getElementById('import-text').value = %s; document.getElementById('import-btn').click(); 'ok'" % json.dumps(texto))
        time.sleep(espera)
        return s.js("document.getElementById('io-msg').textContent")
    item1 = s.js("CATALOG.items.filter(i => i.tier === 'Lendário')[0].namePt")
    REGUA = chr(10) + chr(10) + "=" * 40 + chr(10) + chr(10)
    s.js("Campeoes.carregar().then(() => 'ok')")
    m1 = importa(REGUA.join(["BUILD: Vazia V" + chr(10) + "MODO: ARAM", "BUILD: Rica A" + chr(10) + "[COMUM] Core | 2x1" + chr(10) + "- " + item1]))
    m2 = importa(REGUA.join(["BUILD: Rica B" + chr(10) + "CAMPEÃO: Fulano Inexistente" + chr(10) + "[COMUM] Core | 2x1" + chr(10) + "- " + item1,
                             "BUILD: Rica C" + chr(10) + "[COMUM] Core | 2x1" + chr(10) + "- " + item1]))
    m4 = importa(REGUA.join(["BUILD: Vazia W" + chr(10) + "MODO: ARAM", "BUILD: Rica D" + chr(10) + "CAMPEÃO: Fulano Inexistente" + chr(10) + "[COMUM] Core | 2x1" + chr(10) + "- " + item1]))
    # o aviso que chega depois (a lista do Data Dragon atrasada) entra no fim da mensagem mais nova, sem apagá-la
    s.js("window.__carOrig37 = Campeoes.carregar; Campeoes.carregar = () => new Promise(r => setTimeout(r, 900)); 'ok'")
    importa(REGUA.join(["BUILD: Rica E" + chr(10) + "CAMPEÃO: Fulano Atrasado" + chr(10) + "[COMUM] Core | 2x1" + chr(10) + "- " + item1,
                        "BUILD: Rica F" + chr(10) + "[COMUM] Core | 2x1" + chr(10) + "- " + item1]), 0.1)
    s.js("showIoMsg('Mensagem mais nova.', false); 'ok'"); time.sleep(1.6)
    m5 = s.js("document.getElementById('io-msg').textContent")
    # sem internet: uma frase só para todas as builds (doze builds eram um paredão de 7.500 caracteres)
    s.js("Campeoes.carregar = () => Promise.reject(new Error('sem rede')); 'ok'")
    m6 = importa(REGUA.join("BUILD: Sem Rede %d" % k + chr(10) + "CAMPEÃO: Jinx" + chr(10) + "[COMUM] Core | 2x1" + chr(10) + "- " + item1 for k in range(12)), 1.2)
    s.js("Campeoes.carregar = window.__carOrig37; 'ok'")
    p.conta("texto", "a mensagem do lote avisa a build sem caixa e o campeão desconhecido, sem apagar o resumo",
            "Vazia W" in m4 and "Fulano Inexistente" in m4 and m5.startswith("Mensagem mais nova.") and "Fulano Atrasado" in m5
            and m6.count("Sem internet") == 1 and "e mais 4" in m6 and len(m6) < 600 and
            "Vazia V" in m1 and "Importado" in m1 and "modo ARAM" not in m1 and "Importadas 2 builds" in m2 and "Rica B" in m2 and "Fulano Inexistente" in m2,
            "uma build + uma sem caixa: %s · duas, uma com campeão desconhecido: %s · uma + sem caixa + campeão: %s · atrasado: %s · sem internet (%d caracteres): %s" % (
                m1[:90], m2[:120], m4[:140], m5[:100], len(m6), m6[:120]))
    # o lote grava a biblioteca uma vez, no fim (60 builds travavam a página 7,5 s: 4 gravações e 2 redesenhos por build)
    lote10 = REGUA.join("BUILD: Lote %d" % k + chr(10) + "[COMUM] Core | 2x1" + chr(10) + "- " + item1 for k in range(10))
    s.js("""(() => { window.__gravacoes = 0; window.__redesenhos = 0; window.__setOrig37 = Storage.prototype.setItem; window.__rbOrig37 = renderBuild;
      Storage.prototype.setItem = function (k, v) { if (k === 'lol-builds-v3') window.__gravacoes++; return window.__setOrig37.call(this, k, v); };
      renderBuild = (...a) => { window.__redesenhos++; return window.__rbOrig37(...a); }; return 'ok'; })()""")
    m3 = importa(lote10, 1.0)
    grav = s.js("(() => { Storage.prototype.setItem = window.__setOrig37; renderBuild = window.__rbOrig37; return [window.__gravacoes, window.__redesenhos]; })()")
    p.conta("texto", "importar 10 builds grava a biblioteca e redesenha a forja uma vez, no fim", grav[0] <= 2 and grav[1] <= 3 and "Importadas 10 builds" in m3,
            "%s gravação(ões), %s redesenho(s) da forja · %s" % (grav[0], grav[1], m3[:60]))
    # um campo de uma linha só (descrição e nome da caixa, marco) com uma quebra que chegou por fora não abre linha nova
    umal = s.js("""(() => { const c = build.cats.find(x => x.items.length); const antes = { desc: c.desc, name: c.name, marco: c.marco };
      c.desc = 'linha 1' + String.fromCharCode(10) + '- Gume do Infinito'; c.marco = 'marco' + String.fromCharCode(10) + '[COMUM] falsa'; c.name = 'Core' + String.fromCharCode(10) + '# nome falso';
      const r = textToBuild(buildToText()); const i = build.cats.indexOf(c); Object.assign(c, antes);
      const rc = r.cats[i] || {}; return { caixas: r.cats.length, esperado: build.cats.length, itens: (rc.items || []).length, itensAntes: c.items.length, desc: rc.desc, marco: rc.marco, nome: rc.name }; })()""")
    p.conta("texto", "campo de uma linha com uma quebra dentro não abre linha nova no texto",
            umal["caixas"] == umal["esperado"] and umal["itens"] == umal["itensAntes"] and umal["desc"] == "linha 1 - Gume do Infinito" and umal["marco"] == "marco [COMUM] falsa",
            "%s" % umal)

    # F13-T12: texto exportado ANTES do conserto espremia as vagas vazias, e o
    # formato promete que dá para importar só os fragmentos. Os dois voltavam
    # sem runa nenhuma — e "Vida" era acusada de "não encontrada".
    texto_velho = chr(10).join(["BUILD: t", "[COMUM] Core | 3x1", "- Abatedora",
        "RUNAS: Precisão > Pressione o Ataque | Lenda: Espontaneidade | Golpe de Misericórdia",
        "FRAGMENTOS: Força Adaptativa | Vida"])
    velho = s.js("""(() => { const r = textToBuild(%s);
      const p = normRunas(r.runas); return { slots: p.slots, frag: p.fragmentos, unknown: r.unknown }; })()""" % json.dumps(texto_velho))
    p.conta("texto", "texto antigo (vagas espremidas) e só fragmentos voltam inteiros",
            velho["slots"][1:] == ["lenda-espontaneidade", "golpe-de-misericordia"] and "vida" in velho["frag"] and not velho["unknown"],
            "slots %s, fragmentos %s, não encontrei %s" % (velho["slots"], velho["frag"], velho["unknown"]))

    # F13-T13: o LINK da build é o outro jeito de mandá-la para alguém, e ele
    # não levava runas, habilidades, layout nem Mestre Forjador — mas a placa
    # promete "quem abrir recebe esta build". Aqui o link é aberto numa página
    # nova, como quem recebe, e comparado campo a campo.
    CAMPOS = """(() => JSON.stringify({ itens: build.cats.flatMap(c => c.items.map(i => [i.itemId, i.note || '', !!i.mf])),
      runas: normRunas(build.runas), habilidades: normHabilidades(build.habilidades),
      layout: layoutValido(build.layout), mestre: !!build.masterwork, modo: build.mode || '', desc: build.desc || '',
      marcadores: build.markers }))()"""
    s.js("""(() => { const t = RUNAS.trilhas[2];
      build.runas = normRunas({ primaria: t.id, assinatura: t.slots[0].runas[1].id, slots: [t.slots[1].runas[0].id, '', t.slots[3].runas[1].id],
        fragmentos: [RUNAS.fragmentos[0].runas[1].id, '', RUNAS.fragmentos[2].runas[0].id] });
      build.habilidades = normHabilidades(['Q','E','W','Q','Q','R','Q','E','Q','E','R','E','E','W','W','R','W','W']);
      build.layout = Object.keys(LAYOUTS).find(k => k !== 'tabuleiro');
      build.masterwork = true; build.desc = 'descrição do link';
      const c = build.cats.find(c => c.items.length); if (c) { c.items[0].note = 'observação'; c.items[0].mf = true; }
      gravarBuild(); return 'ok'; })()""")
    enviado = s.js(CAMPOS)
    link = s.js("buildParaLink(library.builds.find(b => b.id === build.id))")
    # página NOVA: trocar só o "#" não recarrega o documento, e aí ninguém "recebe"
    s.abrir("?link=1#" + link.split("#", 1)[1])
    time.sleep(1.2)
    s.entrar()
    recebido = s.js(CAMPOS)
    veio_do_link = s.js("build.id.startsWith('l-')")
    if not veio_do_link:
        det = "a build ativa não é a recebida pelo link (id %s)" % s.js("build.id")
    elif enviado == recebido:
        det = "runas, habilidades, layout, Mestre Forjador, itens e observações; link de %d caracteres" % len(link)
    else:
        a, b = json.loads(enviado), json.loads(recebido)
        det = "; ".join("%s: %s → %s" % (k, json.dumps(a[k], ensure_ascii=False)[:60], json.dumps(b[k], ensure_ascii=False)[:60]) for k in a if a[k] != b[k])
    p.conta("texto", "o link leva a build inteira (quem abre recebe tudo)", veio_do_link and enviado == recebido, det)

    # F13-T8: importar tem de CRIAR uma build nova (senão a comparação acima
    # passa sem testar nada) e ela tem de nascer GRAVADA — com Mestre Forjador e
    # campeão, o importador deixava rascunho, e recarregar perdia os dois.
    s.js("""(async () => { await Campeoes.carregar(); build.champion = Campeoes.porNome('Jinx');
      build.masterwork = true; gravarBuild(); return 'ok'; })()""")
    id_origem = s.js("build.id")
    texto = s.js("buildToText()")
    s.js("document.getElementById('import-text').value = %s" % json.dumps(texto))
    s.js("document.getElementById('import-btn').click()")
    time.sleep(2.5)                       # o campeão chega pelo Data Dragon, depois
    r = s.js("""(() => { const salva = library.builds.find(b => b.id === build.id) || {};
      return { nova: build.id !== %s, sujo: rascunho.sujo,
               mfSalvo: !!salva.masterwork, campeaoSalvo: salva.champion ? salva.champion.name : null }; })()""" % json.dumps(id_origem))
    p.conta("texto", "importar cria uma build nova", r["nova"])
    p.conta("texto", "a build importada nasce gravada (Mestre Forjador e campeão)",
            r["nova"] and not r["sujo"] and r["mfSalvo"] and r["campeaoSalvo"] == "Jinx",
            "rascunho sujo=%s, MF gravado=%s, campeão gravado=%s" % (r["sujo"], r["mfSalvo"], r["campeaoSalvo"]))

    # Achado da revisão da F13-T36: "*" e "•" também abrem linha de item (tópico
    # comum em texto de IA), e a caixa "Importados" — a do item que vem antes da
    # primeira caixa — nascia ANTES de conferir o nome. Um tópico solto no topo
    # deixava uma caixa vazia na build; um texto só de tópicos importava uma
    # build vazia em vez de dizer que não achou nada. Pelo botão, como o Leo faz.
    def importar(texto):
        s.js("document.getElementById('import-text').value = %s" % json.dumps(texto))
        s.js("document.getElementById('import-btn').click()")
        time.sleep(1.2)
        return s.js("""({ id: build.id, caixas: build.cats.map(c => c.name + ':' + c.items.length),
          msg: document.getElementById('io-msg').textContent })""")
    s.js("switchTab('build'); showBuildScreen('lista'); document.getElementById('toggle-io').classList.add('active')")
    time.sleep(0.4)
    id_antes = s.js("build.id")
    misto = importar(chr(10).join(["BUILD: tópicos no topo", "* Dica: fechar o núcleo antes dos 20 min",
                                   "• Contra cura, antecipar o corte", "[COMUM] Núcleo | 3x1", "- Gume do Infinito"]))
    p.conta("texto", "tópico antes da primeira caixa não vira caixa vazia",
            misto["id"] != id_antes and misto["caixas"] == ["Núcleo:1"],
            "caixas %s · aviso: %s" % (misto["caixas"], misto["msg"][:80]))
    id_antes = misto["id"]
    so = importar(chr(10).join(["BUILD: só tópicos", "* Dica: fechar o núcleo antes dos 20 min", "• Contra cura, antecipar o corte"]))
    p.conta("texto", "texto só de tópicos não importa build vazia",
            so["id"] == id_antes and "Não encontrei" in so["msg"],
            "build nova %s · caixas %s · aviso: %s" % (so["id"] != id_antes, so["caixas"], so["msg"][:80]))

    # Caixa sem grade: 6 colunas, a largura ½ de sempre, também na "Importados"
    # (Leo, 17/10/2026, escolha B — o documento dizia 3 e o importador dava 6;
    # o documento passou a dizer 6). O caminho antigo continua: "| ½" dá 6, "| 2×1" dá 2.
    grade = importar(chr(10).join(["BUILD: grades", "- Sedenta por Sangue",
                                   "[COMUM] Sem grade", "- A Coletora",
                                   "[COMUM] Largura antiga | ½", "- Gume do Infinito",
                                   "[COMUM] Com grade | 2×1", "- Dança da Morte"]))
    cols = s.js("build.cats.map(c => c.name + ':' + catCols(c))")
    # e depois do F5: a "Importados" sem colunas gravadas virava 1 coluna na
    # carga (o normalizeCats dá min(itens, 6)) — na sessão ela parecia certa
    s.js("location.reload()")
    time.sleep(2.5)
    s.entrar()
    s.js("switchTab('build')")
    time.sleep(0.6)
    # a carga normaliza as caixas de toda a biblioteca; a build aberta depois do
    # F5 pode ser outra, então a importada é procurada pelo id
    depois = s.js("(() => { const b = library.builds.find(x => x.id === %s); return b ? b.cats.map(c => c.name + ':' + catCols(c)) : ['sumiu']; })()" % json.dumps(grade["id"]))
    esperado = ["Importados:6", "Sem grade:6", "Largura antiga:6", "Com grade:2"]
    p.conta("texto", "caixa sem grade nasce com 6 colunas (e a Importados)",
            grade["id"] != id_antes and cols == esperado and depois == esperado,
            "na sessão %s · depois do F5 %s" % (cols, depois))

    # Revisão da F13-T36b: (1) o nome que não existe numa build que fica sem caixa
    # sumia do aviso — a culpa ia para a caixa; (2) um tópico de IA entre dois
    # BUILD: dividia a build, e o modo e o campeão ficavam na parte descartada.
    s.js("switchTab('build'); showBuildScreen('lista'); document.getElementById('toggle-io').classList.add('active')")
    time.sleep(0.4)
    lote = importar(chr(10).join(["BUILD: A", "[COMUM] X", "- Gume do Infinito", "",
                                  "BUILD: B", "MODO: ARAM", "- Gume do Infinto", "- Sedenta por Sangu"]))
    s.js("showBuildScreen('lista')"); time.sleep(0.3)
    so_erro = importar(chr(10).join(["BUILD: Rascunho", "- Gume do Infinto", "- A Coletra", "- Gume do Infinto"]))
    p.conta("texto", "nome errado em build sem caixa aparece no aviso",
            "Gume do Infinto" in lote["msg"] and "Sedenta por Sangu" in lote["msg"]
            and so_erro["msg"].count("Gume do Infinto") == 1 and "A Coletra" in so_erro["msg"],
            "lote: %s · só nomes errados: %s" % (lote["msg"][:110], so_erro["msg"][:110]))
    # (3) a segunda volta tentou não contar o tópico como corpo e fundiu calado uma
    # build de nomes errados com a seguinte (a reconferência pegou): o tópico entre
    # dois BUILD: separa, e a parte sem caixa é avisada com o tópico.
    div = s.js("""(() => { const N = String.fromCharCode(10);
      const r = rs => rs.map(x => [x.name, x.mode, x.championName || '', x.cats.length, x.unknown.length]);
      const topico = dividirBuilds(['BUILD: Jinx', 'MODO: ARAM', 'CAMPEÃO: Jinx', '* Dica: fechar o núcleo antes dos 20 min',
        'BUILD: Jinx crítico', '[PRIORIDADE] Núcleo | 3x1', '- Gume do Infinito'].join(N)).map(textToBuild);
      const negrito = dividirBuilds(['BUILD: Jinx ARAM', 'MODO: ARAM', 'CAMPEÃO: Jinx', 'MARCADORES: AD | Dano',
        '* **Gume do Infinito** — o núcleo', '* **Dançarina Fantasma** — velocidade', '',
        'BUILD: Caitlyn SR', 'MARCADORES: Utilidade', '[PRIORIDADE] Núcleo', '- Gume do Infinito', '- Cutelo Negro'].join(N)).map(textToBuild);
      return { topico: r(topico), negrito: r(negrito), mkCait: (negrito[1] || {}).markers || null }; })()""")
    p.conta("texto", "tópico de IA entre dois BUILD: não funde as builds",
            div["topico"] == [["Jinx", "ARAM", "Jinx", 0, 1], ["Jinx crítico", "", "", 1, 0]]
            and len(div["negrito"]) == 2 and div["negrito"][0][:4] == ["Jinx ARAM", "ARAM", "Jinx", 0]
            and div["negrito"][1][:4] == ["Caitlyn SR", "", "", 1] and len(div["mkCait"] or []) == 1, "%s" % div)


def checar_salvar(s, p):
    """F13-T31 (bug nº 14): com o navegador recusando a gravação (espaço cheio,
    armazenamento bloqueado), o Salvar dizia "salvo", apagava o botão, tocava o
    som e desarmava o aviso de saída — e a build sumia ao recarregar. Aqui o
    setItem da biblioteca é que falha; o resto do localStorage segue normal."""
    print(chr(10) + "%sSALVAR%s" % (AMARELO, FIM))
    s.nova_build()
    if not s.js("build.editing"):
        s.clicar("#edit-switch", 0.8)
    x0 = s.js("Math.round(document.getElementById('add-cat').getBoundingClientRect().left + scrollX)")
    s.js("""(() => { window.__setOrig = Storage.prototype.setItem; window.__sons = []; window.__recusar = false;
      Storage.prototype.setItem = function (k, v) { if (window.__recusar && k === 'lol-builds-v3') throw new DOMException('cheio', 'QuotaExceededError'); return window.__setOrig.call(this, k, v); };
      window.__somOrig = Som.play; Som.play = function (ev, ...a) { window.__sons.push(ev); return window.__somOrig.call(this, ev, ...a); };
      return 'ok'; })()""")
    estado = """(() => { const ev = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(ev);
      const disco = JSON.parse(localStorage.getItem('lol-builds-v3') || '{"builds":[]}').builds.find(b => b.id === build.id) || {};
      const mem = library.builds.find(b => b.id === build.id) || {};
      const tem = (b) => (b.cats || []).some(c => c.items.some(e => e.itemId === 'long-sword'));
      return { sujo: rascunho.sujo, salvar: !document.getElementById('save-btn').disabled, status: document.getElementById('save-status').textContent,
        aviso: ev.defaultPrevented, som: window.__sons.includes('build:save'), tela: buildScreen, na_forja: tem(build), na_memoria: tem(mem), no_disco: tem(disco),
        placa: document.getElementById('pub-dialog').hidden ? '' : document.getElementById('pub-title').textContent,
        foco_na_placa: !!(document.activeElement && document.activeElement.closest('#pub-dialog')),
        x: Math.round(document.getElementById('add-cat').getBoundingClientRect().left + scrollX) }; })()"""
    fecha_placa = lambda: s.js("document.getElementById('pub-dialog').hidden ? 'ok' : (fecharPub(), 'ok')")
    # Ctrl+S numa build limpa, com a gravação recusada: avisa, mas não a deixa "com alterações"
    s.js("window.__recusar = true; 'ok'")
    for tipo in ("rawKeyDown", "keyUp"):
        s.envia("Input.dispatchKeyEvent", {"type": tipo, "key": "s", "code": "KeyS", "modifiers": 2, "windowsVirtualKeyCode": 83})
    time.sleep(0.4)
    limpa = s.js(estado); fecha_placa()
    p.conta("salvar", "Ctrl+S recusado numa build limpa não a deixa \"com alterações\"",
            not limpa["sujo"] and not limpa["salvar"] and limpa["placa"] == "Não deu para salvar" and limpa["status"] == "gravação recusada",
            "sujo %s, placa \"%s\", status \"%s\"" % (limpa["sujo"], limpa["placa"], limpa["status"]))
    # a gravação volta (uma gravação passa): o aviso some sozinho — antes ficava preso, com Salvar e Descartar apagados
    s.js("window.__recusar = false; gravarBiblioteca(); 'ok'"); time.sleep(0.2)
    volta = s.js(estado)
    s.js("window.__recusar = true; 'ok'")
    p.conta("salvar", "com a gravação de volta, o aviso some sozinho", volta["status"] == "" and not volta["aviso"],
            "status \"%s\", aviso de saída %s" % (volta["status"], "armado" if volta["aviso"] else "desarmado"))
    # o rascunho de verdade
    s.js("build.cats[3].items.push({ itemId: 'long-sword', note: '' }); saveBuild(); renderBuildAll(); window.__sons = []; 'ok'")
    s.clicar("#save-btn", 0.6)
    a = s.js(estado)
    p.conta("salvar", "gravação recusada: o Salvar não diz \"salvo\"",
            a["status"] == "não deu para salvar" and a["salvar"] and a["sujo"] and a["aviso"] and not a["som"] and not a["no_disco"],
            "status \"%s\", Salvar %s, aviso de saída %s, som %s" % (a["status"], "aceso" if a["salvar"] else "APAGADO", "armado" if a["aviso"] else "DESARMADO", "tocou" if a["som"] else "não tocou"))
    p.conta("salvar", "a placa explica, com o foco nela", a["placa"] == "Não deu para salvar" and a["foco_na_placa"],
            "placa \"%s\", foco %s" % (a["placa"], "nela" if a["foco_na_placa"] else "FORA"))
    fecha_placa()
    # e cabe no lugar guardado também na Georgia, a fonte de reserva sem a Alegreya da web
    g = s.js("""(() => { const st = document.getElementById('save-status'), cs = getComputedStyle(st), sp = document.createElement('span');
      sp.textContent = st.textContent; sp.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;font-family:Georgia;font-style:' + cs.fontStyle
        + ';font-weight:' + cs.fontWeight + ';font-size:' + cs.fontSize + ';letter-spacing:' + cs.letterSpacing;
      document.body.appendChild(sp); const w = sp.getBoundingClientRect().width; sp.remove(); return { w, min: parseFloat(cs.minWidth) }; })()""")
    p.conta("salvar", "o aviso não empurra o \"+ Nova categoria\"", a["x"] == x0 and g["min"] >= g["w"],
            "x %d → %d · na Georgia o aviso tem %.0f px, o lugar %.0f px" % (x0, a["x"], g["w"], g["min"]))
    p.conta("salvar", "a cópia na memória não fica com o que não gravou", not a["na_memoria"] and a["na_forja"],
            "item na forja %s, na biblioteca da memória %s" % (a["na_forja"], a["na_memoria"]))
    # "Salvar e sair" pelo diálogo: não sai, fica na build com o aviso
    s.clicar("#build-back", 0.6)
    s.clicar('#save-dialog [data-sd="salvar"]', 0.6)
    b = s.js(estado); fecha_placa()
    p.conta("salvar", "\"Salvar e sair\" recusado: fica na build, com o aviso",
            b["tela"] == "forja" and b["sujo"] and b["status"] == "não deu para salvar" and not b["som"],
            "tela %s, status \"%s\"" % (b["tela"], b["status"]))
    # Descartar depois da recusa descarta de verdade (antes recarregava o rascunho)
    s.clicar("#discard-btn", 0.5)
    s.clicar('#save-dialog [data-sd="descartar"]', 0.6)
    d = s.js(estado)
    p.conta("salvar", "Descartar depois da recusa descarta de verdade", not d["na_forja"] and not d["na_memoria"] and not d["sujo"],
            "item na forja %s, na memória %s" % (d["na_forja"], d["na_memoria"]))
    # o coração (gravação direta) com a recusa: avisa e arma o aviso de saída
    # (a placa das gravações diretas vem na primeira recusa de uma série: uma gravação que passa começa outra)
    s.js("window.__recusar = false; gravarBiblioteca(); window.__recusar = true; showBuildScreen('lista'); 'ok'"); time.sleep(0.5)
    s.clicar('.bi-fav[data-fav="%s"]' % s.js("build.id"), 0.5)
    h = s.js(estado); fecha_placa()
    p.conta("salvar", "coração recusado: a placa avisa e o aviso de saída arma", h["placa"] == "Não deu para gravar" and h["aviso"],
            "placa \"%s\", aviso de saída %s" % (h["placa"], "armado" if h["aviso"] else "DESARMADO"))
    # caminho antigo: com a gravação de volta, o Salvar salva e diz "salvo"
    s.js("window.__recusar = false; showBuildScreen('forja'); build.cats[3].items.push({ itemId: 'long-sword', note: '' }); saveBuild(); renderBuildAll(); window.__sons = []; 'ok'")
    time.sleep(0.4)
    s.clicar("#save-btn", 0.4)
    c = s.js(estado)
    # publicação que passou no site mas não ficou guardada aqui: a placa pede para anotar o ID (servidor SIMULADO)
    s.js("""(() => { window.__fetchOrig = window.fetch;
      window.fetch = function (u, ...a) { const t = String(u);
        if (t.includes('publicar_build')) return Promise.resolve(new Response(JSON.stringify({ id: 'qa0031', versao: 1 }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
        if (t.includes('/rpc/') || t.includes('/rest/')) return Promise.resolve(new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }));
        return window.__fetchOrig.call(this, u, ...a); };
      build.name = 'Salvar de teste'; build.desc = 'descrição'; build.markers = normMarkers(MARCADORES.slice(0, 3).map(m => ({ t: 'tag', id: m.id })));
      gravarBuild(); window.__recusar = true; showBuildScreen('lista'); biSelected = build.id; renderBuildIndex(); return 'ok'; })()""")
    time.sleep(0.5)
    s.clicar('#bi-detail [data-act="publish"]', 1.0)
    pub = s.js("({ titulo: document.getElementById('pub-title').textContent, texto: document.getElementById('pub-text').textContent })")
    fecha_placa()
    s.js("window.fetch = window.__fetchOrig; window.__recusar = false; showBuildScreen('forja'); 'ok'"); time.sleep(0.4)
    p.conta("salvar", "publicada, mas sem gravar aqui: a placa pede para anotar o ID (e avisa da recusa)",
            pub["titulo"] == "Build publicada com sucesso" and "anote" in pub["texto"] and "qa0031" in pub["texto"] and "recusando gravar" in pub["texto"],
            pub["texto"][:60] + " … " + ("com" if "recusando gravar" in pub["texto"] else "SEM") + " o aviso da recusa")
    s.js("Storage.prototype.setItem = window.__setOrig; Som.play = window.__somOrig; 'ok'")
    p.conta("salvar", "com a gravação de volta, o Salvar salva", c["status"] == "salvo" and not c["sujo"] and c["no_disco"] and c["som"] and not c["aviso"],
            "status \"%s\", no disco %s, aviso de saída %s" % (c["status"], c["no_disco"], "armado" if c["aviso"] else "desarmado"))


def checar_publicar(s, p):
    """F13-T30 (bugs nºs 11, 12 e 26): o atributo hidden perdia para qualquer
    display do CSS. O pior caso: o "Fechar" aparecia durante "Publicando…", e
    dava para publicar a mesma build duas vezes. O servidor é SIMULADO: nenhum
    publicar_build sai deste navegador."""
    print(chr(10) + "%sPUBLICAR%s" % (AMARELO, FIM))
    visiveis = """[...document.querySelectorAll('[hidden]')].filter(e => { const b = e.getBoundingClientRect();
        return getComputedStyle(e).display !== 'none' && b.width > 0 && b.height > 0; })
      .map(e => e.id ? '#' + e.id : e.className)"""
    s.nova_build()
    if not s.js("build.editing"):
        s.clicar("#edit-switch", 0.8)
    fe = s.js(visiveis)
    # o Descartar some sem tirar o lugar: com hidden, o "+ Nova categoria" andava
    # 90 px e, no primeiro clique, o Descartar reaparecia embaixo do cursor
    n0 = s.js("build.cats.length")
    c = s.caixa("#add-cat")
    x0 = s.js("Math.round(document.getElementById('add-cat').getBoundingClientRect().left + scrollX)")
    xs = []
    for _ in range(2):
        for tipo in ("mousePressed", "mouseReleased"):
            s.envia("Input.dispatchMouseEvent", {"type": tipo, "x": c[0], "y": c[1], "button": "left", "clickCount": 1})
        time.sleep(0.5)
        xs.append(s.js("Math.round(document.getElementById('add-cat').getBoundingClientRect().left + scrollX)"))
    ac = s.js("({ n: build.cats.length, dlg: !document.getElementById('save-dialog').hidden })")
    if ac["dlg"]:
        s.clicar('#save-dialog [data-sd="voltar"]', 0.3)   # Continuar editando
    # uma resposta atrasada que chega com o "Alterações não salvas" aberto: a
    # placa abria POR BAIXO dele (mesmo z-index) e o Enter fechava o que não se via
    s.clicar("#build-back", 0.6)
    s.js("mostrarPub('Build publicada com sucesso', 'resposta atrasada de teste', 'sucesso'); 'ok'"); time.sleep(0.3)
    cima = s.js("""(() => { const pn = document.querySelector('#pub-dialog .md-panel').getBoundingClientRect();
      const e = document.elementFromPoint(pn.left + pn.width / 2, pn.top + pn.height / 2);
      return { pub: !!(e && e.closest('#pub-dialog')), salvar: !document.getElementById('save-dialog').hidden }; })()""")
    for tipo in ("rawKeyDown", "keyUp"):
        s.envia("Input.dispatchKeyEvent", {"type": tipo, "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27, "nativeVirtualKeyCode": 27})
    time.sleep(0.3)
    esc = s.js("({ placa: document.getElementById('pub-dialog').hidden, salvar: !document.getElementById('save-dialog').hidden })")
    if not esc["placa"]:
        s.js("fecharPub(); 'ok'")
    if esc["salvar"]:
        s.clicar('#save-dialog [data-sd="voltar"]', 0.3)
    p.conta("publicar", "a placa atrasada fica por cima do \"Alterações não salvas\", e o Esc fecha só ela",
            cima["pub"] and cima["salvar"] and esc["placa"] and esc["salvar"],
            "no meio do painel: %s; Esc: placa %s, diálogo de baixo %s" % ("a placa" if cima["pub"] else "OUTRO diálogo",
            "fechou" if esc["placa"] else "ficou", "ficou" if esc["salvar"] else "FECHOU junto"))
    c2 = s.caixa("#save-btn")
    for tipo in ("mousePressed", "mouseReleased"):
        s.envia("Input.dispatchMouseEvent", {"type": tipo, "x": c2[0], "y": c2[1], "button": "left", "clickCount": 1})
    time.sleep(0.03)
    vis = s.js("getComputedStyle(document.getElementById('discard-btn')).visibility")
    time.sleep(0.5)
    # a reserva do "alterações não salvas" cobre também a fonte de reserva (Georgia), sem a Alegreya da web
    res = s.js("""(() => { const st = document.getElementById('save-status'), sp = document.createElement('span');
      sp.textContent = 'alterações não salvas'; sp.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;font-style:italic;font-size:' + getComputedStyle(st).fontSize + ';font-family:Georgia';
      document.body.appendChild(sp); const w = sp.getBoundingClientRect().width; sp.remove();
      return { min: parseFloat(getComputedStyle(st).minWidth), georgia: w }; })()""")
    p.conta("publicar", "ao salvar, o Descartar some na hora; a reserva cabe sem a fonte da web",
            vis == "hidden" and res["min"] >= res["georgia"],
            "30 ms depois: %s · reserva %.0f px, Georgia %.0f px" % (vis, res["min"], res["georgia"]))
    s.js("showBuildScreen('lista'); 'ok'"); time.sleep(0.5)
    mi = s.js(visiveis)
    p.conta("publicar", "o hidden esconde (Descartar sem rascunho, ⟳ em Minhas)", not fe and not mi,
            "forja: %s · Minhas: %s" % (fe or "nada", mi or "nada"))
    p.conta("publicar", "o \"+ Nova categoria\" não anda quando o Descartar aparece", ac["n"] > n0 and not ac["dlg"] and all(x == x0 for x in xs),
            "x %d → %s; %d → %d caixas; diálogo de descartar %s" % (x0, xs, n0, ac["n"], "ABRIU" if ac["dlg"] else "não abriu"))
    # publicar_build: preso até o roteiro soltar, ou erro 500 com __falhar; conta quantos saíram
    s.js("""(() => { window.__fetchOrig = window.fetch; window.__pubs = []; window.__soltar = null; window.__falhar = false;
      window.__resposta = { id: 'qa0030', versao: 1 };
      window.fetch = function (u, opts, ...a) { const t = String(u);
        if (t.includes('publicar_build')) { window.__pubs.push(Date.now());
          if (window.__falhar) return Promise.resolve(new Response(JSON.stringify({ message: 'falha simulada' }), { status: 500, headers: { 'Content-Type': 'application/json' } }));
          return new Promise((res) => {
            window.__soltar = () => res(new Response(JSON.stringify(window.__resposta), { status: 200, headers: { 'Content-Type': 'application/json' } })); }); }
        if (t.includes('/rpc/') || t.includes('/rest/')) return Promise.resolve(new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }));
        return window.__fetchOrig.call(this, u, opts, ...a); };
      build.name = 'Publicar de teste'; build.desc = 'descrição de teste';
      build.markers = normMarkers(MARCADORES.slice(0, 3).map(m => ({ t: 'tag', id: m.id })));
      build.cats[3].items = [{ itemId: 'long-sword', note: '' }]; gravarBuild();
      biSelected = build.id; renderBuildIndex(); return 'ok'; })()""")
    time.sleep(0.5)
    enter = lambda: [s.envia("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "text": chr(13), "unmodifiedText": chr(13), "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13}),
                     s.envia("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})]
    # (sem o "text" o Chrome não gera o keypress e o botão não é acionado)
    s.clicar('#bi-detail [data-act="publish"]', 0.8)
    durante = s.js("""({ aguardando: document.getElementById('pub-dialog').classList.contains('aguardando'),
      fechar: getComputedStyle(document.getElementById('pub-foot')).display })""")
    enter(); time.sleep(0.6)
    n = s.js("window.__pubs.length")
    p.conta("publicar", "durante \"Publicando…\" não há Fechar", durante["aguardando"] and durante["fechar"] == "none",
            "rodapé: %s" % durante["fechar"])
    p.conta("publicar", "Enter durante a espera não manda outro pedido", n == 1, "%d pedido(s) de publicar_build" % n)
    s.js("window.__soltar && window.__soltar(); 'ok'"); time.sleep(0.8)
    ok = s.js("({ sucesso: document.getElementById('pub-dialog').classList.contains('sucesso'), pub: build.pubId })")
    s.clicar("#pub-close", 0.4)
    # erro: o Enter fecha a placa — com o foco no Publicar, atrás dela, publicava de novo
    s.js("window.__falhar = true; 'ok'")
    s.clicar('#bi-detail [data-act="publish"]', 0.8)
    antes_enter = s.js("({ n: window.__pubs.length, erro: document.getElementById('pub-dialog').classList.contains('erro') })")
    enter(); time.sleep(0.6)
    depois_enter = s.js("({ n: window.__pubs.length, fechada: document.getElementById('pub-dialog').hidden })")
    if not depois_enter["fechada"]:
        s.clicar("#pub-close", 0.3)
    p.conta("publicar", "depois de um erro, o Enter fecha a placa (não publica de novo)",
            antes_enter["erro"] and depois_enter["n"] == antes_enter["n"] and depois_enter["fechada"],
            "pedidos %d → %d; placa %s" % (antes_enter["n"], depois_enter["n"], "fechada" if depois_enter["fechada"] else "aberta"))
    # servidor lento: a espera de 30 s encurtada só aqui, trocando o relógio da página
    s.js("""(() => { window.__falhar = false; window.__resposta = { id: 'qa0030', versao: 2 }; window.__stOrig = window.setTimeout;
      window.setTimeout = (f, ms, ...a) => window.__stOrig(f, ms === 30000 ? 400 : ms, ...a); return 'ok'; })()""")
    s.clicar('#bi-detail [data-act="publish"]', 1.4)
    lento = s.js("""({ fechar: getComputedStyle(document.getElementById('pub-foot')).display,
      texto: document.getElementById('pub-text').textContent, n: window.__pubs.length })""")
    s.clicar("#pub-close", 0.4)
    s.clicar('#bi-detail [data-act="publish"]', 0.6)      # de novo, com a placa fechada e o pedido no ar
    denovo = s.js("({ n: window.__pubs.length, titulo: document.getElementById('pub-title').textContent })")
    s.clicar("#pub-close", 0.3)
    s.js("window.__soltar && window.__soltar(); 'ok'"); time.sleep(0.8)
    tarde = s.js("({ sucesso: document.getElementById('pub-dialog').classList.contains('sucesso') && !document.getElementById('pub-dialog').hidden, versao: build.pubVersao })")
    if tarde["sucesso"]:
        s.clicar("#pub-close", 0.3)
    s.js("window.setTimeout = window.__stOrig; window.fetch = window.__fetchOrig; 'ok'")
    p.conta("publicar", "servidor lento: o Fechar aparece, a trava segura e a resposta atrasada vale",
            ok["sucesso"] and ok["pub"] == "qa0030" and lento["fechar"] != "none" and "demorando" in lento["texto"]
            and denovo["n"] == lento["n"] and "Ainda publicando" in denovo["titulo"] and tarde["sucesso"] and tarde["versao"] == 2,
            "Fechar %s; de novo: %s; resposta atrasada: versão %s" % (lento["fechar"], denovo["titulo"], tarde["versao"]))


def checar_atualizacao(s, p):
    """F13-T33 (bugs nºs 13 e 41): depois de recarregar a página, só abrir outra
    build carimbava "agora" na "Última atualização" das duas, e a publicada
    passava a dizer "Há alterações depois da última publicação". A publicação
    aqui é montada por JS (os campos dela), sem servidor."""
    print(chr(10) + "%sATUALIZAÇÃO%s" % (AMARELO, FIM))
    s.limpar_memoria(); s.entrar()
    ids = s.js("""(() => { switchTab('build'); showBuildScreen('lista');
      createNewBuild('Publicada A'); build.cats[3].items = [{ itemId: 'long-sword', note: '' }]; build.desc = 'descrição';
      build.markers = normMarkers(MARCADORES.slice(0, 3).map(m => ({ t: 'tag', id: m.id }))); gravarBuild();
      const a = build.id;
      gravarMetadados(library.builds.find(b => b.id === a), { pubId: 'qa0033', pubVersao: 1, pubEm: Date.now() + 5, pubPatch: CATALOG.meta.patch });
      createNewBuild('B'); return { a, b: build.id }; })()""")
    time.sleep(0.3)
    s.abrir(); time.sleep(0.8); s.entrar()
    disco = lambda: s.js("""(() => { const d = JSON.parse(localStorage.getItem('lol-builds-v3')).builds; const f = (id) => (d.find(x => x.id === id) || {}).updatedAt;
      return { a: f(%s), b: f(%s) }; })()""" % (json.dumps(ids["a"]), json.dumps(ids["b"])))
    antes = disco()
    s.js("switchTab('build'); showBuildScreen('lista'); 'ok'"); time.sleep(3.0)
    alvo = ids["b"] if s.js("build.id") == ids["a"] else ids["a"]
    c = s.caixa('.bi-row[data-id="%s"]' % alvo)
    for n in (1, 2):
        for tipo in ("mousePressed", "mouseReleased"):
            s.envia("Input.dispatchMouseEvent", {"type": tipo, "x": c[0], "y": c[1], "button": "left", "clickCount": n})
    time.sleep(1.0)
    depois = disco()
    s.js("showBuildScreen('lista'); biSelected = %s; renderBuildIndex(); 'ok'" % json.dumps(ids["a"])); time.sleep(0.5)
    nota = s.js("(document.querySelector('#bi-detail .bd-pub-note') || {}).textContent || ''")
    p.conta("atualização", "abrir outra build não muda a \"Última atualização\"", antes == depois and "Publicada na versão 1" in nota,
            "A %s → %s, B %s → %s; nota: %s" % (antes["a"], depois["a"], antes["b"], depois["b"], nota[:45]))
    # caminho antigo: uma mudança de verdade ainda carimba a data e acende a nota
    s.js("""(() => { activateBuild(%s, true); build.cats[3].items.push({ itemId: 'long-sword', note: 'nova' }); gravarBuild();
      showBuildScreen('lista'); biSelected = build.id; renderBuildIndex(); return 'ok'; })()""" % json.dumps(ids["a"]))
    time.sleep(0.5)
    mudou = disco()
    nota2 = s.js("(document.querySelector('#bi-detail .bd-pub-note') || {}).textContent || ''")
    p.conta("atualização", "uma mudança de verdade ainda carimba a data", mudou["a"] > depois["a"] and "Há alterações" in nota2,
            "A %s → %s; nota: %s" % (depois["a"], mudou["a"], nota2[:50]))
    # a nota compara o que foi publicado (servidor SIMULADO): o Mestre Forjador, que não vai ao site, não a acende;
    # um Salvar durante uma publicação lenta, sim (a assinatura é do que foi ENVIADO)
    s.js("""(() => { window.__fetchOrig = window.fetch; window.__soltar = null; window.__lento = false;
      window.fetch = function (u, ...a) { const t = String(u);
        if (t.includes('publicar_build')) { const resp = () => new Response(JSON.stringify({ id: 'qa0033', versao: 2 }), { status: 200, headers: { 'Content-Type': 'application/json' } });
          return window.__lento ? new Promise(res => { window.__soltar = () => res(resp()); }) : Promise.resolve(resp()); }
        if (t.includes('/rpc/') || t.includes('/rest/')) return Promise.resolve(new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }));
        return window.__fetchOrig.call(this, u, ...a); };
      if (build.editing) document.getElementById('edit-switch').click();
      showBuildScreen('lista'); biSelected = build.id; renderBuildIndex(); return 'ok'; })()""")
    time.sleep(0.5)
    nota_do = lambda: s.js("(() => { showBuildScreen('lista'); biSelected = %s; renderBuildIndex(); return (document.querySelector('#bi-detail .bd-pub-note') || {}).textContent || ''; })()" % json.dumps(ids["a"]))
    s.clicar('#bi-detail [data-act="publish"]', 0.8); s.js("fecharPub(); 'ok'")
    publicada = nota_do()
    s.js("showBuildScreen('forja'); 'ok'"); time.sleep(0.5)
    s.clicar("#mf-switch", 0.5)
    mf = s.js("build.masterwork")
    depois_mf = nota_do()
    p.conta("atualização", "o Mestre Forjador não acende a nota da publicação", "Publicada na versão 2" in publicada and mf and "Publicada na versão 2" in depois_mf,
            "logo depois: %s · Mestre Forjador %s: %s" % (publicada[:26], "ligado" if mf else "?", depois_mf[:40]))
    s.js("""(() => { window.__lento = true; window.__stOrig = window.setTimeout;
      window.setTimeout = (f, ms, ...a) => window.__stOrig(f, ms === 30000 ? 300 : ms, ...a); return 'ok'; })()""")
    s.clicar('#bi-detail [data-act="publish"]', 1.0); s.js("fecharPub(); 'ok'")
    s.js("""(() => { build.cats[3].items.push({ itemId: 'long-sword', note: 'durante a espera' }); gravarBuild(); window.__soltar && window.__soltar(); return 'ok'; })()""")
    time.sleep(0.8); s.js("fecharPub(); window.setTimeout = window.__stOrig; window.fetch = window.__fetchOrig; 'ok'")
    lenta = nota_do()
    p.conta("atualização", "um Salvar durante a publicação lenta acende a nota", "Há alterações" in lenta, lenta[:60])
    # a build migrada do formato antigo nasce com data
    s.js("localStorage.clear(); localStorage.setItem('lol-build-v2', JSON.stringify({ name: 'Antiga', cats: [{ name: 'Caixa antiga', items: [] }] })); 'ok'")
    s.abrir(); time.sleep(0.8)
    mig = s.js("({ n: library.builds.length, u: (library.builds[0] || {}).updatedAt || 0 })")
    s.js("localStorage.removeItem('lol-build-v2'); 'ok'"); s.entrar()
    p.conta("atualização", "a build migrada do formato antigo tem data", mig["n"] == 1 and mig["u"] > 0, "updatedAt %s" % mig["u"])


def checar_ultima(s, p):
    """F13-T32 (bug nº 15): com uma pública aberta, a visualização contava como
    build. Excluir a última build própria gravava a biblioteca vazia (a
    visualização não vai ao disco) e, na recarga, voltava a build única do HTML
    anterior (lol-build-v2). A pública aqui é montada por JS, sem servidor."""
    print(chr(10) + "%sÚLTIMA BUILD%s" % (AMARELO, FIM))
    s.limpar_memoria(); s.entrar()
    s.js("""(() => { localStorage.setItem('lol-build-v2', JSON.stringify({ name: 'Build velha do HTML anterior', cats: [{ name: 'Caixa antiga', items: [] }] }));
      switchTab('build'); showBuildScreen('lista');
      abrirPublicaTemporaria(publicaResumo({ id: 'qa0015', nome: 'Pública de teste', caixas: [], marcadores: [] }));
      showBuildScreen('lista'); biSelected = library.builds.find(b => !b.temp).id; renderBuildIndex(); return 'ok'; })()""")
    time.sleep(0.6)
    r = s.js("""(() => { const b = document.querySelector('#bi-detail [data-act="del"]');
      return { proprias: library.builds.filter(x => !x.temp).length, temp: library.builds.filter(x => x.temp).length, desligado: !b || b.disabled }; })()""")
    s.clicar('#bi-detail [data-act="del"]', 0.8)
    depois = s.js("""(() => { const d = JSON.parse(localStorage.getItem('lol-builds-v3') || '{"builds":[]}'); return { disco: d.builds.length, proprias: library.builds.filter(x => !x.temp).length }; })()""")
    p.conta("última build", "com uma pública aberta, a última build própria não se exclui",
            r["temp"] == 1 and r["proprias"] == 1 and r["desligado"] and depois["proprias"] == 1,
            "1 própria + %d visualização; Excluir %s; próprias depois: %d" % (r["temp"], "desligado" if r["desligado"] else "LIGADO", depois["proprias"]))
    # caminho antigo: com uma build própria só, "Fechar visualização" continua fechando a pública
    s.js("biSelected = library.builds.find(b => b.temp) ? library.builds.find(b => b.temp).id : null; renderBuildIndex(); 'ok'"); time.sleep(0.4)
    s.clicar('#bi-detail [data-act="del"]', 0.6)
    fechou = s.js("library.builds.filter(b => b.temp).length === 0 && library.builds.filter(b => !b.temp).length === 1")
    p.conta("última build", "com uma build só, \"Fechar visualização\" ainda fecha a pública", fechou, "")
    # a corrida (excluir uma enquanto outra espera o servidor) chega ao ramo "sem build própria":
    # a build excluída não pode voltar como cópia sem id — voltava na recarga, com o pubId já apagado
    g = s.js("""(() => { createNewBuild('P2'); const p2 = build.id; const p1 = library.builds.find(b => !b.temp && b.id !== p2).id;
      library.builds.find(b => b.id === p1).name = 'P1'; library.builds.find(b => b.id === p1).pubId = 'qa9P1'; gravarBiblioteca();
      abrirPublicaTemporaria(publicaResumo({ id: 'qa0016', nome: 'Outra pública', caixas: [], marcadores: [] }));
      deleteBuild(p1); deleteBuild(p2);
      const disco = JSON.parse(localStorage.getItem('lol-builds-v3')).builds;
      return { nulos: library.builds.filter(b => !b.id).length, disco: disco.map(b => b.name), pub: disco.some(b => b.pubId === 'qa9P1') }; })()""")
    p.conta("última build", "excluir a última própria não deixa cópia fantasma", g["nulos"] == 0 and g["disco"] == ["Build sem nome"] and not g["pub"],
            "sem id na memória: %d; no disco: %s" % (g["nulos"], g["disco"]))
    # com uma visualização ativa, o disco guarda a última build própria como a ativa
    a_ = s.js("""(() => { const propria = build.id; abrirPublicaTemporaria(publicaResumo({ id: 'qa0017', nome: 'Mais uma', caixas: [], marcadores: [] }));
      gravarBiblioteca(); return { propria, disco: JSON.parse(localStorage.getItem('lol-builds-v3')).activeId }; })()""")
    p.conta("última build", "com uma visualização aberta, a ativa gravada é a sua", a_["disco"] == a_["propria"],
            "activeId no disco: %s" % a_["disco"])
    # o Excluir da forja numa visualização fecha, sem a pergunta de excluir
    s.js("switchTab('build'); showBuildScreen('forja'); 'ok'"); time.sleep(0.5)
    nd = len(s.dialogos)
    alvo = s.js("build.temp ? build.id : null")
    s.clicar("#del-build", 0.6)
    fx = s.js("({ ficou: library.builds.some(b => b.id === %s), ativa_temp: !!build.temp })" % json.dumps(alvo))
    p.conta("última build", "o Excluir da forja numa visualização fecha, sem perguntar", alvo and not fx["ficou"] and not fx["ativa_temp"] and len(s.dialogos) == nd,
            "%s %s; perguntas: %d" % (alvo, "ficou" if fx["ficou"] else "fechou", len(s.dialogos) - nd))
    # a recarga com a biblioteca gravada vazia não ressuscita o formato antigo
    s.js("localStorage.setItem('lol-builds-v3', JSON.stringify({ builds: [], activeId: null })); 'ok'")
    s.abrir(); time.sleep(0.8)
    velha = s.js("library.builds.map(b => b.name)")
    p.conta("última build", "biblioteca vazia na recarga não traz a build do formato antigo", "Build velha do HTML anterior" not in velha and len(velha) == 1,
            "builds: %s" % velha)
    s.js("localStorage.removeItem('lol-build-v2'); 'ok'")
    s.entrar()


def checar_abas(s, p):
    """F13-T35 (bug nº 27): com duas abas abertas, cada uma gravava a biblioteca
    que tinha desde que abriu — a segunda a gravar apagava a build criada na
    primeira. Decisão do Leo: uma aba por vez. A que abre depois fica parada sob
    um véu; "Usar esta aba" recarrega do disco e assume, e é recusado enquanto a
    dona tem alteração não gravada ou espera resposta da internet. Várias abas
    de verdade no mesmo Chrome — mesmo localStorage, mesma trava (Web Locks);
    cliques e teclas de verdade."""
    print(chr(10) + "%sDUAS ABAS%s" % (AMARELO, FIM))
    s.limpar_memoria(); s.entrar()
    s.js("switchTab('build'); showBuildScreen('lista'); 'ok'"); time.sleep(0.6)
    no_disco = lambda: s.js("(JSON.parse(localStorage.getItem('lol-builds-v3') || 'null') || { builds: [] }).builds.map(x => x.name)")
    marca = lambda q: q.js("JSON.parse(localStorage.getItem('montador.dona') || 'null')")
    veu = lambda q: q.js("""(() => { const v = document.getElementById('aba-dona'); if (!v || v.hidden) return null;
      const e = document.elementFromPoint(innerWidth / 2, 30);
      return { titulo: document.getElementById('aba-dona-titulo').textContent, texto: document.getElementById('aba-dona-texto').textContent,
        emCima: !!(e && e.closest('#aba-dona')), parado: [...document.body.children].filter(x => x !== v).every(x => x.inert),
        leitor: v.getAttribute('aria-describedby') === 'aba-dona-texto' && document.getElementById('aba-dona-texto').getAttribute('aria-live') === 'polite' }; })()""")
    texto_veu = lambda q: q.js("(document.getElementById('aba-dona-texto') || {}).textContent || ''")

    def espera(q, expr, limite=8.0):
        fim = time.time() + limite
        while time.time() < fim:
            try:
                if q.js(expr):
                    return True
            except (RuntimeError, KeyError):   # no meio de uma recarga a resposta pode vir sem "result"
                pass
            time.sleep(0.25)
        return False

    decidiu = lambda q: espera(q, "typeof decidido !== 'undefined' && decidido === true")

    def recarregou(q, clique=None, expr=None):
        """Clica de verdade (ou roda o JS) e espera a página nova decidir quem é a dona."""
        q.js("window.__velha = 1; 'ok'")
        if clique:
            q.clicar(clique, 0.3)
        else:
            q.js(expr)
        return espera(q, "typeof window.__velha === 'undefined' && document.readyState === 'complete'", 15) and decidiu(q)

    def tentar_usar(q):
        """A aba parada clica "Usar esta aba": recusado, ela nem recarrega."""
        q.js("window.__fica = 1; 'ok'")
        q.clicar("#aba-dona-usar", 0.8)
        return q.js("({ fica: window.__fica === 1, dona: souDona, texto: document.getElementById('aba-dona-texto').textContent })")

    b = s.nova_aba(); c = d = e = f = g = h = v = w = None
    try:
        # enquanto a trava não responde, a aba nova já nasce parada: um clique em
        # "Entrar na loja" não abre nada (antes, por 2 s, a loja abria e o que se
        # fazia parecia gravado e depois sumia)
        b.abrir()
        b.clicar("#entrar", 0.2)
        cf = b.js("({ conferindo: !!document.querySelector('#aba-dona.conferindo'), entrou: document.getElementById('entrada').classList.contains('saindo') || document.getElementById('entrada').classList.contains('fechada'), decidido: typeof decidido === 'undefined' ? null : decidido })")
        p.conta("duas abas", "enquanto confere a trava, a aba nova já nasce parada", cf["conferindo"] and not cf["entrou"] and not cf["decidido"],
                "enquanto confere: %s" % cf)
        decidiu(b)
        vb = veu(b)
        p.conta("duas abas", "a segunda aba abre parada, sob o véu, com a página por baixo sem resposta",
                bool(vb) and vb["emCima"] and vb["parado"] and vb["leitor"] and vb["titulo"] == "Aberto em outra aba" and "já está aberto em outra aba" in vb["texto"], "véu: %s" % vb)
        # a aba 1 cria uma build DEPOIS que a 2 abriu; a 2 grava o que tem na memória
        s.clicar("#bi-new", 1.0); s.js("build.name = 'Da aba 1'; gravarBuild(); showBuildScreen('lista'); 'ok'"); time.sleep(0.4)
        gravou = b.js("gravarBiblioteca()")
        disco = no_disco()
        p.conta("duas abas", "a aba parada não grava por cima da build criada na outra", "Da aba 1" in disco and gravou is False,
                "gravarBiblioteca na aba 2: %s · no disco: %s" % (gravou, disco))
        if not vb:
            return
        # a aba 1 na forja com uma caixa escolhida (o Esc solta a caixa — atalho da página inteira)
        s.js("(() => { showBuildScreen('forja'); build.selectedCatId = build.cats[0] && build.cats[0].id; renderBuild(); return 'ok'; })()")
        # a aba 2 assume: recarrega do disco, com a build da aba 1
        ok = recarregou(b, "#aba-dona-usar")
        if ok:
            b.entrar()
        espera(s, "!souDona", 3)
        va, vb2 = veu(s), veu(b)
        tem = b.js("library.builds.map(x => x.name)") if ok else []
        p.conta("duas abas", "\"Usar esta aba\" recarrega do disco e assume; a outra fica parada",
                ok and not vb2 and "Da aba 1" in tem and bool(va) and va["parado"] and "passou a usar" in va["texto"],
                "recarregou %s · aba 2: %s · véu na aba 2 %s · véu na aba 1: %s" % (ok, tem, vb2, va))
        caixa = s.js("build.selectedCatId")
        for tipo in ("rawKeyDown", "keyUp"):
            s.envia("Input.dispatchKeyEvent", {"type": tipo, "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27, "nativeVirtualKeyCode": 27})
        time.sleep(0.3)
        depois = s.js("build.selectedCatId")
        # o Ctrl+S não abre o "Salvar como" do navegador (o evento sai anulado)
        salvar = s.js("!document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true, cancelable: true }))")
        p.conta("duas abas", "parada, a aba não obedece aos atalhos (o Esc não mexe na forja; o Ctrl+S não abre o \"Salvar como\")",
                bool(caixa) and depois == caixa and salvar is True,
                "caixa escolhida antes %s · depois do Esc %s · Ctrl+S anulado %s" % (caixa, depois, salvar))
        # a aba 2 cria outra; a aba 1 (que perdeu a vez) tenta gravar
        b.js("switchTab('build'); showBuildScreen('lista'); 'ok'"); time.sleep(0.6)
        b.clicar("#bi-new", 1.0); b.js("build.name = 'Da aba 2'; gravarBuild(); showBuildScreen('lista'); 'ok'"); time.sleep(0.4)
        gravou = s.js("gravarBiblioteca()")
        disco = no_disco()
        p.conta("duas abas", "a aba que perdeu a vez não grava por cima", "Da aba 1" in disco and "Da aba 2" in disco and gravou is False,
                "gravarBiblioteca na aba 1: %s · no disco: %s" % (gravou, disco))
        # a marca escrita por uma aba que já perdeu a vez (um confirm atrasado) não recusa a troca
        velha = s.js("""(async () => { const antes = localStorage.getItem('montador.dona');
          localStorage.setItem('montador.dona', JSON.stringify({ cliente: 'aba-que-perdeu', sujo: 1, ocupada: 0 }));
          const r = await donaOcupada(); localStorage.setItem('montador.dona', antes); return r; })()""")
        p.conta("duas abas", "a marca de uma aba que já perdeu a vez não recusa a troca", velha is False, "donaOcupada com a marca velha: %s" % velha)
        # com rascunho na dona, a troca é recusada (a aba parada nem recarrega)
        b.js("(() => { showBuildScreen('forja'); if (!build.editing) document.getElementById('edit-switch').click(); build.cats[0].items.push({ itemId: 'long-sword', note: '' }); saveBuild(); return 'ok'; })()")
        time.sleep(0.4)
        r = tentar_usar(s)
        p.conta("duas abas", "com alteração não salva na outra, \"Usar esta aba\" é recusado", r["fica"] and not r["dona"] and "alterações não salvas" in r["texto"],
                "ficou %s · virou dona %s · texto: %s" % (r["fica"], r["dona"], r["texto"]))
        b.js("descartarAlteracoes(); if (build.editing) document.getElementById('edit-switch').click(); 'ok'"); time.sleep(0.4)
        # com a gravação recusada na dona (T31), também: o que só está na memória dela não pode se perder
        b.js("""(() => { window.__setOrig = Storage.prototype.setItem;
          Storage.prototype.setItem = function (k, v) { if (k === 'lol-builds-v3') throw new DOMException('cheio', 'QuotaExceededError'); return window.__setOrig.call(this, k, v); };
          gravarBiblioteca(); fecharPub(); return 'ok'; })()""")
        recusada = (marca(b) or {}).get("sujo")
        r = tentar_usar(s)
        b.js("Storage.prototype.setItem = window.__setOrig; gravarBiblioteca(); 'ok'"); time.sleep(0.3)
        p.conta("duas abas", "com a gravação recusada na outra, \"Usar esta aba\" é recusado (e diz o que fazer lá)",
                recusada == 2 and r["fica"] and not r["dona"] and "gravação recusada" in r["texto"] and "Exportar/importar" in r["texto"],
                "marca na hora %s · ficou %s · virou dona %s · texto: %s" % (recusada, r["fica"], r["dona"], r["texto"]))
        # com uma publicação no ar na outra, também; a marca acompanha na hora (não na próxima volta)
        marcou = b.js("noServidor.set('qa-t35', 'publicando'); JSON.parse(localStorage.getItem('montador.dona')).ocupada === 1")
        r = tentar_usar(s)
        solto = b.js("noServidor.delete('qa-t35'); JSON.parse(localStorage.getItem('montador.dona')).ocupada === 0")
        p.conta("duas abas", "com publicação no ar na outra, \"Usar esta aba\" é recusado", marcou and solto and r["fica"] and not r["dona"] and "resposta da internet" in r["texto"],
                "marca na hora %s · solta na hora %s · ficou %s · virou dona %s · texto: %s" % (marcou, solto, r["fica"], r["dona"], r["texto"]))
        # excluir do site uma publicação que não está na biblioteca também é esperar a internet
        ex = b.js("""(async () => { window.__rpcOrig = Servidor.rpc; window.__confOrig = window.confirm; window.confirm = () => true;
          Servidor.rpc = (nome, a) => nome === 'apagar_build' ? new Promise(r => { window.__soltaRpc = r; }) : window.__rpcOrig(nome, a);
          excluirPublicacao('qa35xx'); await new Promise(r => setTimeout(r, 300));
          const esperando = JSON.parse(localStorage.getItem('montador.dona')).ocupada;
          window.__soltaRpc(true); await new Promise(r => setTimeout(r, 300));
          const depois = JSON.parse(localStorage.getItem('montador.dona')).ocupada;
          Servidor.rpc = window.__rpcOrig; window.confirm = window.__confOrig; fecharPub(); return { esperando, depois }; })()""")
        p.conta("duas abas", "excluir do site uma publicação fora da biblioteca conta como esperar a internet", ex["esperando"] == 1 and ex["depois"] == 0,
                "marca esperando %s · depois %s" % (ex["esperando"], ex["depois"]))
        # importação com campeão, esperando a lista da internet: também
        b.js("""(() => { window.__carregarOrig = Campeoes.carregar; Campeoes.carregar = () => new Promise(r => { window.__soltaCampeao = r; });
          switchTab('build'); showBuildScreen('forja');
          if (!document.getElementById('io-panel').classList.contains('show')) document.getElementById('toggle-io').click();
          const c = build.cats[0]; c.items.push({ itemId: 'long-sword', note: '' }); const t = buildToText(); c.items.pop();
          document.getElementById('import-text').value = t + String.fromCharCode(10) + 'Campeão: Ahri'; return 'ok'; })()""")
        time.sleep(0.4)
        b.clicar("#import-btn", 0.6)
        esperando = (marca(b) or {}).get("ocupada")
        r = tentar_usar(s)
        b.js("window.__soltaCampeao && window.__soltaCampeao(); Campeoes.carregar = window.__carregarOrig; 'ok'"); time.sleep(0.4)
        solto = (marca(b) or {}).get("ocupada")
        p.conta("duas abas", "com a importação esperando o campeão na outra, \"Usar esta aba\" é recusado",
                esperando == 1 and solto == 0 and r["fica"] and not r["dona"] and "resposta da internet" in r["texto"],
                "marca esperando %s · depois %s · ficou %s · texto: %s" % (esperando, solto, r["fica"], r["texto"]))
        # a dona recarrega (F5): continua dona
        b.abrir(); decidiu(b)
        f5 = b.js("({ dona: souDona, veu: !!document.getElementById('aba-dona') })")
        p.conta("duas abas", "a dona recarrega (F5) e continua dona", f5["dona"] and not f5["veu"] and s.js("!souDona"), "aba 2 depois do F5: %s" % f5)
        # a dona vai a outra página e volta (Voltar): volta inteira, do cache do navegador —
        # a parada não a tira de lá (a consulta da trava a despejava) — e retoma a marca
        b.envia("Page.bringToFront"); b.js("window.__fica = 1; 'ok'")
        b.envia("Page.navigate", {"url": b.url + "docs/qa.md"}); time.sleep(4.5)
        fora = texto_veu(s)
        hist = b.envia("Page.getNavigationHistory")
        b.envia("Page.navigateToHistoryEntry", {"entryId": hist["entries"][hist["currentIndex"] - 1]["id"]}); time.sleep(2)
        vt = b.js("({ fica: window.__fica === 1, dona: souDona })")
        espera(s, "(document.getElementById('aba-dona-texto') || {}).textContent.includes('já está aberto')", 4)
        volta = texto_veu(s)
        p.conta("duas abas", "a dona vai a outra página e volta inteira (Voltar); a parada acompanha",
                "saiu do Montador" in fora and vt["fica"] and vt["dona"] and "já está aberto" in volta,
                "véu com a dona fora: %s · a dona voltou: %s · véu depois: %s" % (fora[:45], vt, volta[:45]))
        # a dona fecha: a parada avisa (pela marca) e assume com um clique; a entrada da loja volta a ter o foco
        b.fechar_aba()
        espera(s, "(document.getElementById('aba-dona-texto') || {}).textContent.includes('saiu do Montador')", 5)
        vs = veu(s) or {}
        ok = "saiu do Montador" in vs.get("texto", "") and recarregou(s, "#aba-dona-usar")
        fim = s.js("({ dona: souDona, veu: !!document.getElementById('aba-dona'), foco: document.activeElement && document.activeElement.id, nomes: library.builds.map(x => x.name) })") if ok else {}
        if ok:
            s.entrar()
        p.conta("duas abas", "a outra fechou: a parada avisa e assume, com as duas builds",
                ok and vs.get("titulo") == "A outra aba saiu" and fim["dona"] and not fim["veu"] and fim["foco"] == "entrar" and "Da aba 1" in fim["nomes"] and "Da aba 2" in fim["nomes"],
                "véu: %s · depois: %s" % (vs, fim))
        # um link de build (#b=) aberto enquanto a loja está em outra aba: o véu avisa
        # que a build só é guardada usando esta aba, e fechar pergunta antes
        s.js("switchTab('build'); showBuildScreen('lista'); 'ok'"); time.sleep(0.4)
        hash_ = s.js("(() => { const x = library.builds.find(y => y.name === 'Da aba 2'); const l = buildParaLink({ ...x, id: 'qa-link-35', name: 'Do link' }); return l.slice(l.indexOf('#')); })()")
        e = s.nova_aba(); e.abrir(hash_); decidiu(e)
        lk = e.js("({ texto: (document.getElementById('aba-dona-texto') || {}).textContent || '', sair: !window.dispatchEvent(new Event('beforeunload', { cancelable: true })) })")
        p.conta("duas abas", "um link de build aberto numa aba parada: o véu avisa, e fechar pergunta",
                "ainda não foi guardada" in lk["texto"] and lk["sair"] is True, "véu: %s · aviso de saída %s" % (lk["texto"], lk["sair"]))
        e.fechar_aba(); e = None
        # a dona presa num confirm() (o Excluir) enquanto outra aba assume e cria uma build:
        # o OK de lá não pode gravar a biblioteca velha por cima. O confirm é trocado por
        # uma espera que trava a aba do mesmo jeito (o roteiro aceita os de verdade na hora).
        c = s.nova_aba(); c.abrir(); decidiu(c)
        s.js("""(() => { showBuildScreen('forja');
          window.confirm = () => { const fim = Date.now() + 9000; while (Date.now() < fim) {} return true; };
          setTimeout(() => document.getElementById('del-build').click(), 50); return 'ok'; })()""")
        time.sleep(0.5)
        assumiu = recarregou(c, expr="usarEstaAba(); 'ok'")
        if assumiu:
            c.entrar()
            c.js("switchTab('build'); showBuildScreen('lista'); 'ok'"); time.sleep(0.5)
            c.clicar("#bi-new", 1.0); c.js("build.name = 'Da aba 3'; gravarBuild(); 'ok'")
        s.js("'acordou'"); time.sleep(0.6)          # espera o "confirm" da aba 1 terminar
        disco = no_disco()
        r = s.js("({ dona: souDona, texto: (document.getElementById('aba-dona-texto') || {}).textContent || '' })")
        p.conta("duas abas", "a dona presa num diálogo não grava por cima da aba que assumiu",
                assumiu and "Da aba 3" in disco and not r["dona"] and "passou a usar" in r["texto"],
                "a outra assumiu %s · no disco: %s · aba presa: %s" % (assumiu, disco, r))
        # o "Limpar build" depois do confirm, numa aba que perdeu a vez e ainda não
        # sabe (o aviso da trava atrasado): pergunta ao navegador antes de mexer
        antes = marca(s)
        lb = s.js("""(async () => { const n = build.cats.length; souDona = true; window.confirm = () => true;
          document.getElementById('clear-build').click(); await new Promise(r => setTimeout(r, 400));
          return { antes: n, depois: build.cats.length, dona: souDona }; })()""")
        depois = marca(s)
        p.conta("duas abas", "o \"Limpar build\" numa aba que perdeu a vez sem saber não mexe em nada",
                lb["antes"] > 0 and lb["depois"] == lb["antes"] and not lb["dona"] and depois == antes,
                "caixas %s → %s · dona %s · marca antes %s · depois %s" % (lb["antes"], lb["depois"], lb["dona"], antes, depois))
        # uma aba nova espera a vez (a trava tem uma pequena espera, para o F5) enquanto
        # a dona grava e sai: a nova tem de reler o disco, não assumir com a memória velha
        d = s.nova_aba(); d.abrir()
        c.js("build.name = 'Antes de sair'; gravarBuild(); 'ok'")
        c.envia("Page.navigate", {"url": "about:blank"})
        decidiu(d); time.sleep(0.5)
        decidiu(d)
        d.js("gravarBiblioteca(); 'ok'")
        rd = d.js("({ dona: souDona, nomes: library.builds.map(x => x.name) })")
        disco = no_disco()
        p.conta("duas abas", "a biblioteca que mudou enquanto a aba nova esperava a vez é relida",
                rd["dona"] and "Antes de sair" in rd["nomes"] and "Antes de sair" in disco,
                "aba nova: %s · no disco: %s" % (rd, disco))
        # "Usar esta aba" numa aba de link: assume sem o aviso falso de saída ("Recarregar
        # site?") — o #b= fica na URL e a build do link entra na carga nova
        hash2 = d.js("(() => { const x = library.builds.find(y => !y.temp); const l = buildParaLink({ ...x, id: 'qa-link-35b', name: 'Do link 2' }); return l.slice(l.indexOf('#')); })()")
        f = s.nova_aba(); f.abrir(hash2); decidiu(f)
        f.dialogos.clear()
        assumiu = recarregou(f, "#aba-dona-usar")
        rf = f.js("({ dona: souDona, link: library.builds.some(x => x.name === 'Do link 2') })") if assumiu else {}
        avisos = [x for x in f.dialogos if x.startswith("beforeunload")]
        p.conta("duas abas", "\"Usar esta aba\" numa aba de link assume sem o aviso falso de saída, com a build do link",
                assumiu and rf["dona"] and rf["link"] and not avisos, "assumiu %s · %s · avisos: %s" % (assumiu, rf, avisos or "nenhum"))
        # a dona que quebra sem avisar (sem pagehide, a marca não diz "saiu"): a parada percebe pela trava
        f.ws.send(json.dumps({"id": 99999, "method": "Page.crash"}))
        espera(s, "(document.getElementById('aba-dona-texto') || {}).textContent.includes('não responde mais')", 6)
        tq = texto_veu(s)
        p.conta("duas abas", "a dona que quebra sem avisar: a parada percebe", "não responde mais" in tq, "véu: %s" % tq[:90])
        # a página de captura da observação (#build-observacao): o foco volta ao editor depois do "conferindo"
        s.js("""(() => { const d = JSON.parse(localStorage.getItem('lol-builds-v3')); const b = d.builds.find(x => x.id === d.activeId) || d.builds[0];
          d.activeId = b.id; if (!b.cats.length) b.cats.push({ id: 'cat-qa', name: 'QA', desc: '', kind: 'comum', span: 2, items: [] });
          if (!b.cats[0].items.length) b.cats[0].items.push({ itemId: 'long-sword', note: '' });
          localStorage.setItem('lol-builds-v3', JSON.stringify(d)); return 'ok'; })()""")
        g = s.nova_aba(); g.abrir("#build-observacao"); decidiu(g); time.sleep(0.4)
        fo = g.js("({ dona: souDona, foco: document.activeElement && document.activeElement.id, editor: document.getElementById('note-editor').classList.contains('show') })")
        p.conta("duas abas", "a página de captura da observação fica com o foco no editor", fo["dona"] and fo["editor"] and fo["foco"] == "note-text", "%s" % fo)
        # F5 da dona com outra aba ainda conferindo (na fila da trava): a dona continua dona
        h = s.nova_aba(); h.abrir()
        g.abrir(); decidiu(g); decidiu(h); time.sleep(1.5)
        f5 = {"dona": g.js("souDona"), "outra": h.js("({ dona: souDona, veu: !!document.getElementById('aba-dona') })")}
        p.conta("duas abas", "F5 da dona com outra aba na fila da trava: a dona continua dona",
                f5["dona"] and not f5["outra"]["dona"] and f5["outra"]["veu"], "%s" % f5)
        # outra aba toma a trava bem na hora em que esta confere se ela é sua (entre a
        # concessão e a consulta): esta não assume — senão ficavam duas donas.
        # A conferência desta aba é atrasada de propósito, para a corrida ser certa.
        g.fechar_aba(); g = None; time.sleep(0.5)
        s.js("localStorage.setItem('montador.dona', JSON.stringify({ cliente: 'qa', sujo: 0, ocupada: 0 })); 'ok'")
        v = s.nova_aba()
        v.envia("Page.addScriptToEvaluateOnNewDocument", {"source": "(() => { if (!navigator.locks) return; const req = navigator.locks.request.bind(navigator.locks); navigator.locks.request = (nome, ...r) => String(nome).startsWith('montador.eu.') ? new Promise(ok => setTimeout(ok, 1500)).then(() => req(nome, ...r)) : req(nome, ...r); })()"})
        v.abrir()
        h.js("navigator.locks.request('montador.dona', { steal: true }, () => new Promise(() => {})); 'ok'")
        time.sleep(3.5)
        rv = v.js("({ dona: souDona, veu: !!document.getElementById('aba-dona') })")
        p.conta("duas abas", "outra aba toma a trava enquanto esta confere: esta não assume", not rv["dona"] and rv["veu"], "aba: %s" % rv)
        v.fechar_aba(); v = None
        # a aba nova que desiste da espera (2 s) justo quando a marca diz "saiu" — a
        # dona recarregando, que regrava a marca logo depois — não toma a vez: confere
        # de novo em 1 s. A trava continua com a aba de antes; o roteiro faz o papel da
        # dona que volta, regravando a marca a tempo.
        s.js("localStorage.setItem('montador.dona', JSON.stringify({ cliente: 'qa', sujo: 0, ocupada: 0, fora: 1 })); 'ok'")
        w = s.nova_aba(); w.abrir(); time.sleep(2.3)
        s.js("localStorage.setItem('montador.dona', JSON.stringify({ cliente: 'qa', sujo: 0, ocupada: 0 })); 'ok'")
        time.sleep(2.0)
        rw = w.js("({ dona: souDona, veu: !!document.getElementById('aba-dona') })")
        p.conta("duas abas", "o \"saiu\" que a dona regrava logo depois (F5) não faz a aba nova tomar a vez", not rw["dona"] and rw["veu"], "aba: %s" % rw)
        w.fechar_aba(); w = None
        # a trava negada pelo navegador (dados do site bloqueados): a aba sozinha
        # funciona, como antes — não fica presa no véu
        e = s.nova_aba()
        e.envia("Page.addScriptToEvaluateOnNewDocument", {"source": "(() => { const nega = () => Promise.reject(new DOMException('The request was denied.', 'SecurityError')); if (navigator.locks) { navigator.locks.request = nega; navigator.locks.query = nega; } })()"})
        e.abrir(); decidiu(e)
        ng = e.js("({ dona: souDona, veu: !!document.getElementById('aba-dona') })")
        p.conta("duas abas", "com a trava negada pelo navegador, a aba não fica presa no véu", ng["dona"] and not ng["veu"], "aba: %s" % ng)
    finally:
        for q in (b, c, d, e, f, g, h, v, w):
            if q:
                q.fechar_aba()


def checar_orfa(s, p):
    """F13-T34 (bug nº 42): excluir a build enquanto ela é publicada deixava a
    publicação no site sem lugar nenhum que guardasse o ID. Servidor SIMULADO:
    publicar_build fica preso até o roteiro soltar; apagar_build só é contado."""
    print(chr(10) + "%sPUBLICAÇÃO ÓRFÃ%s" % (AMARELO, FIM))
    s.nova_build()
    s.js("""(() => { window.__fetchOrig = window.fetch; window.__soltar = null; window.__apagados = []; window.__proxId = 'qa0042';
      window.__pubs = 0; window.__apagarPreso = false; window.__soltarApagar = null;
      window.fetch = function (u, opts, ...a) { const t = String(u);
        if (t.includes('publicar_build')) { window.__pubs++; return new Promise(res => { window.__soltar = () => res(new Response(JSON.stringify({ id: window.__proxId, versao: 1 }), { status: 200, headers: { 'Content-Type': 'application/json' } })); }); }
        if (t.includes('apagar_build')) { window.__apagados.push(JSON.parse(opts.body).p_id); const ok = () => new Response('true', { status: 200, headers: { 'Content-Type': 'application/json' } });
          return window.__apagarPreso ? new Promise(res => { window.__soltarApagar = () => res(ok()); }) : Promise.resolve(ok()); }
        if (t.includes('/rpc/') || t.includes('/rest/')) return Promise.resolve(new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }));
        return window.__fetchOrig.call(this, u, opts, ...a); };
      window.__stOrig = window.setTimeout; window.setTimeout = (f, ms, ...a) => window.__stOrig(f, ms === 30000 ? 300 : ms, ...a);
      if (build.editing) document.getElementById('edit-switch').click();
      build.name = 'Órfã de teste'; build.desc = 'descrição'; build.markers = normMarkers(MARCADORES.slice(0, 3).map(m => ({ t: 'tag', id: m.id })));
      build.cats[3].items = [{ itemId: 'long-sword', note: '' }]; gravarBuild();
      showBuildScreen('lista'); biSelected = build.id; renderBuildIndex(); return 'ok'; })()""")
    time.sleep(0.5)
    bid = s.js("build.id")
    s.clicar('#bi-detail [data-act="publish"]', 0.9)
    s.clicar("#pub-close", 0.3)                                    # o Fechar aparece depois da espera (encurtada)
    nd = len(s.dialogos)
    s.clicar('#bi-detail [data-act="del"]', 0.5)
    lista = s.js("({ placa: document.getElementById('pub-dialog').hidden ? '' : document.getElementById('pub-title').textContent })")
    s.js("fecharPub(); showBuildScreen('forja'); 'ok'"); time.sleep(0.5)
    s.clicar("#del-build", 0.5)
    forja = s.js("({ placa: document.getElementById('pub-dialog').hidden ? '' : document.getElementById('pub-title').textContent })")
    s.js("fecharPub(); showBuildScreen('lista'); 'ok'"); time.sleep(0.5)
    s.clicar("#bi-lote", 0.4)
    if isinstance(s.caixa('.bi-row[data-id="%s"]' % bid), list):
        s.clicar('.bi-row[data-id="%s"]' % bid, 0.3); s.clicar("#bl-excluir", 0.5)
        lote = s.js("(document.getElementById('bl-msg') || {}).textContent || ''")
    else:
        lote = "(a build já tinha sido excluída)"
    s.clicar("#bl-sair", 0.3)
    ficou = s.js("library.builds.some(b => b.id === %s)" % json.dumps(bid))
    s.js("window.__soltar && window.__soltar(); 'ok'"); time.sleep(0.8)
    pub = s.js("(library.builds.find(b => b.id === %s) || {}).pubId || null" % json.dumps(bid))
    s.js("fecharPub(); 'ok'")
    p.conta("publicação órfã", "com a publicação no ar, a build não se exclui (lista, forja, lote)",
            ficou and pub == "qa0042" and lista["placa"] == "Ainda publicando" and forja["placa"] == "Ainda publicando" and "Espere terminar" in lote and len(s.dialogos) == nd,
            "lista: %s · forja: %s · lote: %s · perguntas: %d · ID gravado: %s" % (lista["placa"] or "—", forja["placa"] or "—", lote[:30] or "—", len(s.dialogos) - nd, pub))
    # despublicar durante o "Atualizar publicação": a mesma trava
    s.clicar('#bi-detail [data-act="publish"]', 0.9); s.clicar("#pub-close", 0.3)
    nd = len(s.dialogos); ap = len(s.js("window.__apagados"))
    s.clicar('#bi-detail [data-act="unpub"]', 0.5)
    unpub = s.js("({ placa: document.getElementById('pub-dialog').hidden ? '' : document.getElementById('pub-title').textContent, apagados: window.__apagados.length })")
    s.js("fecharPub(); window.__soltar && window.__soltar(); 'ok'"); time.sleep(0.8); s.js("fecharPub(); 'ok'")
    p.conta("publicação órfã", "despublicar durante o \"Atualizar publicação\" espera", unpub["placa"] == "Ainda publicando" and unpub["apagados"] == ap and len(s.dialogos) == nd,
            "placa: %s · apagar_build: %d · perguntas: %d" % (unpub["placa"] or "—", unpub["apagados"] - ap, len(s.dialogos) - nd))
    # a defesa: se a build some mesmo assim, a publicação que acabou de nascer sai do site
    s.js("window.__proxId = 'qa0042b'; 'ok'")
    s.clicar('#bi-detail [data-act="publish"]', 0.9)
    s.js("(() => { deleteBuild(%s); window.__soltar && window.__soltar(); return 'ok'; })()" % json.dumps(bid)); time.sleep(0.9)
    fim = s.js("({ placa: document.getElementById('pub-dialog').hidden ? '' : document.getElementById('pub-title').textContent, apagados: window.__apagados })")
    # publicar durante uma exclusão no ar: a trava vale nos dois sentidos
    s.js("""(() => { fecharPub(); createNewBuild('Excluindo'); build.desc = 'descrição'; build.markers = normMarkers(MARCADORES.slice(0, 3).map(m => ({ t: 'tag', id: m.id })));
      build.cats[3].items = [{ itemId: 'long-sword', note: '' }]; gravarBuild();
      gravarMetadados(library.builds.find(b => b.id === build.id), { pubId: 'qa0043', pubVersao: 1, pubEm: Date.now(), pubPatch: CATALOG.meta.patch });
      window.__apagarPreso = true; showBuildScreen('lista'); biSelected = build.id; renderBuildIndex(); return 'ok'; })()""")
    time.sleep(0.5)
    s.clicar('#bi-detail [data-act="del"]', 0.9); s.clicar("#pub-close", 0.3)      # o "Tirando do site" ganha o Fechar
    pubs = s.js("window.__pubs")
    s.clicar('#bi-detail [data-act="publish"]', 0.5)
    exc = s.js("({ placa: document.getElementById('pub-dialog').hidden ? '' : document.getElementById('pub-title').textContent, pubs: window.__pubs })")
    s.js("fecharPub(); window.__soltarApagar && window.__soltarApagar(); 'ok'"); time.sleep(0.6)
    p.conta("publicação órfã", "publicar durante uma exclusão no ar espera", exc["placa"] == "Ainda tirando do site" and exc["pubs"] == pubs,
            "placa: %s · publicar_build: %d" % (exc["placa"] or "—", exc["pubs"] - pubs))
    s.js("fecharPub(); window.setTimeout = window.__stOrig; window.fetch = window.__fetchOrig; 'ok'")
    p.conta("publicação órfã", "se a build some mesmo assim, a publicação sai do site", fim["placa"] == "Publicação desfeita" and "qa0042b" in fim["apagados"],
            "placa: %s · apagar_build: %s" % (fim["placa"] or "—", fim["apagados"]))


def checar_exclusao(s, p):
    """F13-T14: excluir uma build publicada prometia "ela também sai do site" e,
    se o servidor falhasse, apagava daqui calada — a publicação ficava no ar e o
    ID dela sumia. O servidor é SIMULADO: o pedido apagar_build nunca sai deste
    navegador, e o confirm é respondido pelo roteiro."""
    print(chr(10) + "%sEXCLUSÃO%s" % (AMARELO, FIM))
    s.js("""(() => { window.__fetchOrig = window.fetch; window.__confirmOrig = window.confirm;
      window.fetch = function (u, ...a) {
        if (String(u).includes('apagar_build')) return Promise.reject(new TypeError('Failed to fetch'));
        return window.__fetchOrig.call(this, u, ...a); };
      window.__confirms = []; window.__respostas = [true, false];   // sim ao Excluir; não a "apagar só daqui"
      window.confirm = (m) => { window.__confirms.push(m); return window.__respostas.length ? window.__respostas.shift() : false; };
      return 'ok'; })()""")
    s.nova_build()
    bid = s.js("""(() => { build.name = 'Publicada de teste'; build.pubId = 'qa0000';
      build.cats[3].items = CATALOG.items.slice(0, 2).map(i => ({ itemId: i.slug, note: '' })); gravarBuild(); return build.id; })()""")
    s.nova_build()
    s.js("switchTab('build'); showBuildScreen('lista'); biSelected = %s; renderBuildIndex(); 'ok'" % json.dumps(bid))
    time.sleep(0.5)
    s.js("""(() => { const b = [...document.querySelectorAll('[data-act="del"]')][0]; if (b) b.click(); return !!b; })()""")
    time.sleep(1.0)
    r = s.js("""(() => ({ ficou: library.builds.some(b => b.id === %s),
      pub: (library.builds.find(b => b.id === %s) || {}).pubId || null, perguntas: window.__confirms }))()""" % (json.dumps(bid), json.dumps(bid)))
    p.conta("exclusão", "servidor fora do ar: a publicada não some calada",
            len(r["perguntas"]) == 2 and "continua no site" in r["perguntas"][1],
            (r["perguntas"][1][:70] if len(r["perguntas"]) > 1 else "só %d pergunta(s)" % len(r["perguntas"])))
    p.conta("exclusão", "dizendo não, a build fica, com o ID guardado", r["ficou"] and r["pub"] == "qa0000")
    s.js("window.fetch = window.__fetchOrig; window.confirm = window.__confirmOrig; 'ok'")


def checar_rascunho(s, p):
    """F13-T24 (bug nº 37): abrir de novo a build que já está na forja recarregava
    a cópia salva por cima do rascunho, calado. Chega-se à lista com o rascunho
    sujo pela aba Builds (a troca de aba não pergunta, de propósito: F10-T2); aqui
    esse caminho é montado por JS e o gesto testado é o de verdade — duplo clique
    na linha, o botão Editar do detalhe, o coração. Não basta ver o item na forja:
    se o rascunho fosse gravado calado ele também estaria lá, então a checagem
    olha o `rascunho.sujo` e o localStorage."""
    print("\n%sRASCUNHO%s" % (AMARELO, FIM))
    s.nova_build()
    id_b = s.js("build.id")
    s.nova_build()
    id_a = s.js("build.id")
    if not s.js("build.editing"):
        s.clicar("#edit-switch", 0.8)
    s.js("""(() => { build.cats[3].items.push({ itemId: 'long-sword', note: 'rascunho' }); saveBuild(); renderBuildAll();
      showBuildScreen('lista'); return 'ok'; })()""")
    time.sleep(0.6)
    estado = lambda: s.js("""(() => { const disco = JSON.parse(localStorage.getItem('lol-builds-v3') || '{"builds":[]}').builds;
      const d = (id) => disco.find(b => b.id === id) || {};
      return { na_forja: build.cats.some(c => c.items.some(e => e.note === 'rascunho')), sujo: rascunho.sujo,
        no_disco: (d(%s).cats || []).some(c => c.items.some(e => e.note === 'rascunho')),
        forja: !document.getElementById('build-editor').hidden, ativa: build.id,
        fav_a: !!d(%s).fav, fav_b: !!d(%s).fav, dialogo: !document.getElementById('save-dialog').hidden }; })()"""
                          % (json.dumps(id_a), json.dumps(id_a), json.dumps(id_b)))
    intacto = lambda e: e["na_forja"] and e["sujo"] and not e["no_disco"] and e["ativa"] == id_a
    antes = estado()
    linha = '.bi-row[data-id="%s"]' % id_a
    c = s.caixa(linha)
    for n in (1, 2):
        for tipo in ("mousePressed", "mouseReleased"):
            s.envia("Input.dispatchMouseEvent", {"type": tipo, "x": c[0], "y": c[1], "button": "left", "clickCount": n})
    time.sleep(1.0)
    e = estado()
    p.conta("rascunho", "duplo clique na build aberta não apaga o rascunho", intacto(antes) and intacto(e) and e["forja"],
            "na forja %s, sujo %s, no disco %s" % (e["na_forja"], e["sujo"], e["no_disco"]))
    s.js("showBuildScreen('lista'); 'ok'"); time.sleep(0.5)
    s.clicar(linha, 0.5)
    s.clicar('#bi-detail [data-act="edit"]', 1.0)
    e = estado()
    p.conta("rascunho", "o Editar do detalhe também não", intacto(e) and e["forja"],
            "na forja %s, sujo %s, no disco %s" % (e["na_forja"], e["sujo"], e["no_disco"]))
    # o coração é gesto da lista: grava na hora, com o Editar ligado, sem o rascunho
    s.js("showBuildScreen('lista'); 'ok'"); time.sleep(0.5)
    s.clicar('.bi-fav[data-fav="%s"]' % id_b, 0.5)
    s.clicar('.bi-fav[data-fav="%s"]' % id_a, 0.5)
    e = estado()
    p.conta("rascunho", "o coração grava na hora, sem gravar o rascunho", e["fav_a"] and e["fav_b"] and intacto(e),
            "fav A %s, fav B %s, sujo %s, rascunho no disco %s" % (e["fav_a"], e["fav_b"], e["sujo"], e["no_disco"]))
    # caminho antigo: o Descartar continua voltando à cópia salva, e o favorito fica
    s.clicar(linha, 0.3)
    s.clicar('#bi-detail [data-act="edit"]', 1.0)
    s.clicar("#discard-btn", 0.5)
    s.clicar('#save-dialog [data-sd="descartar"]', 1.0)
    e = estado()
    p.conta("rascunho", "Descartar ainda volta ao salvo (e o favorito fica)",
            not e["na_forja"] and not e["sujo"] and e["fav_a"] and s.js("build.fav") is True,
            "na forja %s, sujo %s, fav %s" % (e["na_forja"], e["sujo"], e["fav_a"]))


def checar_troca(s, p):
    """F13-T25 (bug nº 38): na forja, trocar de build, criar e duplicar perguntam
    pelo rascunho; na lista e no Importar, os mesmos gestos gravavam o rascunho
    calados. E o que só mexe em OUTRA build (excluir, a janela "Falta pouco para
    publicar") gravava junto o rascunho da aberta. Cada checagem monta o próprio
    estado (a build A aberta, suja, na lista) por JS; o gesto testado é o de
    verdade. O diálogo só é respondido se apareceu: no código de antes ele não
    aparece, e cada checagem tem de falhar por si, não o grupo parar na primeira."""
    print("\n%sTROCA DE BUILD%s" % (AMARELO, FIM))
    ids = []
    for _ in range(3):
        s.nova_build()
        ids.append(s.js("build.id"))
    id_c, id_b, id_a = ids
    if not s.js("build.editing"):
        s.clicar("#edit-switch", 0.8)

    def preparar():
        s.js("""(() => { rascunho.sujo = false; activateBuild(%s, true); renderBuildAll();
          build.cats[3].items.push({ itemId: 'long-sword', note: 'rascunho' }); saveBuild(); renderBuildAll();
          showBuildScreen('lista'); return 'ok'; })()""" % json.dumps(id_a))
        time.sleep(0.5)

    def estado():
        return s.js("""(() => { const disco = JSON.parse(localStorage.getItem('lol-builds-v3') || '{"builds":[]}').builds;
          const d = (id) => disco.find(b => b.id === id) || {};
          return { ativa: build.id === %s ? 'A' : build.id === %s ? 'B' : build.name, sujo: rascunho.sujo,
            dialogo: !document.getElementById('save-dialog').hidden,
            a_disco: (d(%s).cats || []).some(c => c.items.some(e => e.note === 'rascunho')),
            nome_a: d(%s).name || '', existe_c: library.builds.some(b => b.id === %s), n: library.builds.length }; })()"""
                    % (json.dumps(id_a), json.dumps(id_b), json.dumps(id_a), json.dumps(id_a), json.dumps(id_c)))

    def responder(sd):
        if s.js("!document.getElementById('save-dialog').hidden"):
            s.clicar('#save-dialog [data-sd="%s"]' % sd, 1.0)

    def duplo(sel):
        c = s.caixa(sel)
        for n in (1, 2):
            for tipo in ("mousePressed", "mouseReleased"):
                s.envia("Input.dispatchMouseEvent", {"type": tipo, "x": c[0], "y": c[1], "button": "left", "clickCount": n})
        time.sleep(1.0)

    def limpar_a():   # tira da cópia salva de A o rascunho que um "Salvar" de propósito gravou
        s.js("(() => { const a = library.builds.find(b => b.id === %s); a.cats.forEach(c => c.items = c.items.filter(x => x.note !== 'rascunho')); gravarBiblioteca(); return 'ok'; })()" % json.dumps(id_a))

    preparar()
    duplo('.bi-row[data-id="%s"]' % id_b)
    e = estado()
    responder("voltar")
    e2 = estado()
    p.conta("troca", "abrir outra build pela lista pergunta",
            e["dialogo"] and e["ativa"] == "A" and not e["a_disco"] and e2["ativa"] == "A" and e2["sujo"],
            "diálogo %s, ativa %s, rascunho no disco %s" % (e["dialogo"], e["ativa"], e["a_disco"]))
    # pelo teclado: Enter na linha abre o diálogo com o foco nele, e o Enter
    # seguinte responde "Continuar editando" em vez de acionar a lista por trás
    preparar()
    s.clicar('.bi-row[data-id="%s"]' % id_b, 0.4)
    for tipo in ("keyDown", "keyUp"):
        s.envia("Input.dispatchKeyEvent", {"type": tipo, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": chr(13)})
    time.sleep(0.6)
    foco = s.js("document.activeElement.dataset.sd || document.activeElement.className")
    for tipo in ("keyDown", "keyUp"):
        s.envia("Input.dispatchKeyEvent", {"type": tipo, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": chr(13)})
    time.sleep(0.6)
    e = estado()
    p.conta("troca", "o diálogo recebe o foco (Enter responde nele)", foco == "voltar" and not e["dialogo"] and e["ativa"] == "A" and e["sujo"],
            "foco em %r, diálogo aberto %s, ativa %s" % (foco, e["dialogo"], e["ativa"]))
    responder("voltar")
    preparar()
    duplo('.bi-row[data-id="%s"]' % id_b)
    viu = s.js("!document.getElementById('save-dialog').hidden")
    responder("salvar")
    e = estado()
    p.conta("troca", "\"Salvar e sair\" grava e abre a outra", viu and e["ativa"] == "B" and e["a_disco"] and not e["sujo"],
            "diálogo %s, ativa %s, rascunho de A no disco %s" % (viu, e["ativa"], e["a_disco"]))
    limpar_a()
    preparar()
    n0 = s.js("library.builds.length")
    s.clicar("#bi-new", 0.6)
    e = estado()
    responder("voltar")
    p.conta("troca", "\"+ Nova build\" da lista pergunta", e["dialogo"] and e["n"] == n0 and not e["a_disco"],
            "diálogo %s, builds %d → %d, rascunho no disco %s" % (e["dialogo"], n0, e["n"], e["a_disco"]))
    preparar()
    s.clicar('.bi-row[data-id="%s"]' % id_c, 0.5)
    s.clicar('#bi-detail [data-act="del"]', 1.2)
    e = estado()
    p.conta("troca", "excluir outra build não grava o rascunho", not e["existe_c"] and e["sujo"] and not e["a_disco"],
            "excluída %s, sujo %s, rascunho de A no disco %s" % (not e["existe_c"], e["sujo"], e["a_disco"]))
    preparar()
    s.clicar('.bi-row[data-id="%s"]' % id_a, 0.5)
    s.clicar('#bi-detail [data-act="publish"]', 0.8)
    aberta = s.js("!document.getElementById('pub-falta').hidden")
    s.clicar("#pf-nome", 0.2)
    s.envia("Input.insertText", {"text": "Nome da troca"})
    time.sleep(0.6)
    e = estado()
    s.clicar("#pf-close", 0.4)
    p.conta("troca", "\"Falta pouco para publicar\" grava o nome, não as caixas",
            aberta and e["nome_a"] == "Nome da troca" and e["sujo"] and not e["a_disco"],
            "janela %s, nome no disco %r, sujo %s, rascunho no disco %s" % (aberta, e["nome_a"], e["sujo"], e["a_disco"]))
    # Achado pela revisão da T25: um Ctrl+S com a janela aberta troca o objeto da
    # build na biblioteca, e o que se digitava depois ia para uma cópia solta.
    preparar()
    s.clicar('.bi-row[data-id="%s"]' % id_a, 0.5)
    s.clicar('#bi-detail [data-act="publish"]', 0.8)
    s.clicar("#pf-desc", 0.2)   # a janela só mostra o que falta: o nome já foi
    for tipo in ("rawKeyDown", "keyUp"):
        s.envia("Input.dispatchKeyEvent", {"type": tipo, "key": "s", "code": "KeyS", "windowsVirtualKeyCode": 83, "modifiers": 2})
    time.sleep(0.6)
    salvou = s.js("!rascunho.sujo")
    s.clicar("#pf-desc", 0.2)
    s.envia("Input.insertText", {"text": "Descrição depois do Ctrl+S"})
    time.sleep(0.6)
    desc = s.js("(JSON.parse(localStorage.getItem('lol-builds-v3')).builds.find(b => b.id === %s) || {}).desc || ''" % json.dumps(id_a))
    s.clicar("#pf-close", 0.4)
    p.conta("troca", "Ctrl+S com a janela aberta: o que vem depois grava", salvou and desc == "Descrição depois do Ctrl+S",
            "Ctrl+S salvou %s, descrição no disco %r" % (salvou, desc))
    limpar_a()
    preparar()
    s.js("showBuildScreen('forja'); 'ok'"); time.sleep(0.6)
    if not s.js("document.getElementById('io-panel').classList.contains('show')"):
        s.clicar("#toggle-io", 0.5)
    s.js("document.getElementById('import-text').value = 'BUILD: Importada na troca\\n[COMUM] Core\\n- Gume do Infinito'; 'ok'")
    s.clicar("#import-btn", 0.8)
    e = estado()
    responder("descartar")
    e2 = estado()
    p.conta("troca", "Importar pergunta (e Descartar não grava)",
            e["dialogo"] and e["ativa"] == "A" and e2["ativa"] == "Importada na troca" and not e2["a_disco"],
            "diálogo %s, depois: %s, rascunho de A no disco %s" % (e["dialogo"], e2["ativa"], e2["a_disco"]))


def checar_acessibilidade(s, p):
    print("\n%sACESSIBILIDADE%s" % (AMARELO, FIM))
    s.js("switchTab('catalog')")
    time.sleep(0.5)
    s.clicar("#acess-btn")
    for chave in ("movimento", "brilho", "leitura", "daltonismo"):
        s.clicar("#ac-" + chave, 0.25)
    ligadas = s.js("[...document.body.classList].filter(c => c.startsWith('ac-')).length")
    p.conta("acessibilidade", "os quatro interruptores ligam", ligadas == 4, "%s de 4" % ligadas)
    p.conta("acessibilidade", "menos movimento zera as transições",
            s.js("""(() => { const c = document.querySelector('.card-surface');
              return !c || /^0s/.test(getComputedStyle(c).transitionDuration); })()"""))
    # F13-T10: cada interruptor cumpre o que o próprio rótulo promete.
    s.nova_build()
    s.js("build.cats[1].items = CATALOG.items.slice(0, 2).map(it => ({ itemId: it.slug, note: '' })); renderBuildAll(); 'ok'")
    time.sleep(0.4)
    tam = s.js("""(() => { const t = document.querySelector('.item-tile .tile-name');
      return t ? parseFloat(getComputedStyle(t).fontSize) : 0; })()""")
    p.conta("acessibilidade", "leitura calma aumenta o nome no molde da forja", tam >= 12, "%spx" % tam)
    s.js("""(() => { window.__choveu = false; const o = new MutationObserver(() => {
        if (document.querySelector('.chovendo')) window.__choveu = true; });
      o.observe(document.body, { subtree: true, attributes: true, attributeFilter: ['class'] });
      switchTab('catalog'); switchTab('build'); showBuildScreen('lista'); return 'ok'; })()""")
    time.sleep(1.2)
    p.conta("acessibilidade", "menos movimento para a chuva de entrada", not s.js("window.__choveu"))
    s.js("switchTab('build'); showBuildScreen('forja'); 'ok'")
    time.sleep(0.5)
    brilho = s.js(r"""(() => {
      const quente = (x) => { const m = x.match(/rgba?\((\d+), (\d+), (\d+)/); if (!m) return false;
        const [r, g, b] = m.slice(1).map(Number); return r > 200 && g > 60 && g < 200 && b < 90; };
      let n = 0;
      document.querySelectorAll('body *').forEach(e => { const r = e.getBoundingClientRect(); if (r.width < 1) return;
        const bs = getComputedStyle(e).boxShadow; if (!bs || bs === 'none') return;
        if (bs.split(/,(?![^(]*\))/).some(x => !/inset/.test(x) && quente(x) && !/0px 0px 0px/.test(x.replace(/rgba?\([^)]*\)/, '')))) n++; });
      return { halos: n, brasa: /255, 110, 30/.test(getComputedStyle(document.body).backgroundImage) }; })()""")
    p.conta("acessibilidade", "menos brilho apaga a brasa e os halos da forja",
            brilho["halos"] == 0 and not brilho["brasa"], "%s halo(s), brasa=%s" % (brilho["halos"], brilho["brasa"]))
    s.abrir()
    time.sleep(1.0)
    s.entrar()
    p.conta("acessibilidade", "os ajustes sobrevivem ao recarregar",
            s.js("[...document.body.classList].filter(c => c.startsWith('ac-')).length") == 4)
    s.js("localStorage.removeItem('acessibilidade')")


def checar_publicas(s, p, online):
    print("\n%sBUILDS PUBLICADAS%s" % (AMARELO, FIM))
    if not online:
        p.conta("públicas", "a lista vem do servidor", True, "pulada (--offline)", pulou=True)
        return
    s.js("switchTab('build'); showBuildScreen('lista')")
    time.sleep(0.6)
    # F13-T2: contar os redesenhos. Eram ~80 em 4 segundos, com a página morta —
    # cada marcador de habilidade pedia a lista inteira de volta.
    s.js("""(() => { window.__redesenhos = 0; const f = window.renderBuildIndex;
      window.renderBuildIndex = function (...a) { window.__redesenhos++; return f.apply(this, a); };
      return 'ok'; })()""")
    s.js("""document.querySelector('.bi-tab[data-view=\"publicas\"]').click()""")
    # A lista vem do Supabase e traz o retrato de cada campeão do Data Dragon:
    # depende de rede, então espera até aparecer em vez de cronometrar no chute.
    estado = {"linhas": 0, "texto": ""}
    fim = time.time() + 30
    while time.time() < fim:
        try:
            estado = s.js("""(() => { const l = document.getElementById('bi-rows');
              return { linhas: l.querySelectorAll('.bi-row').length,
                       texto: l.innerText.replace(/\\s+/g, ' ').slice(0, 90) }; })()""")
        except RuntimeError as e:
            estado = {"linhas": 0, "texto": str(e)[:90]}
        if estado["linhas"]:
            break
        time.sleep(2)
    # Foi exatamente isto que ficou quebrado em 20/09: a view caiu inteira porque
    # faltava o grant das colunas novas, e a lista veio vazia com um aviso.
    p.conta("públicas", "a lista vem do servidor", estado["linhas"] > 0,
            "%d builds — %s" % (estado["linhas"], estado["texto"]))
    p.conta("públicas", "nenhum 'permission denied'", "permission denied" not in estado["texto"].lower())

    time.sleep(3)
    try:
        n = s.js("window.__redesenhos")
        vivo = s.js("document.querySelectorAll('#bi-rows .bi-row').length") > 0
    except RuntimeError as e:
        n, vivo = -1, False
    # O número varia com a rede: é um redesenho por quadro em que chega a lista
    # de habilidades de algum campeão, então 6 com cache quente e 15 com cache
    # frio, nas mesmas 42 builds. O que se pega aqui é a disparada — eram ~80 e
    # subindo até a página morrer —, não um valor exato.
    p.conta("públicas", "sem tempestade de redesenho", 0 <= n <= 30 and vivo,
            "%s redesenhos; página %s" % (n if n >= 0 else "?", "viva" if vivo else "MUDA"))
    # a arte das habilidades ainda tem de chegar: a letra vira ícone sozinha
    try:
        arte = s.js("""(() => ({ letras: document.querySelectorAll('#bi-rows .mk-letra').length,
          icones: document.querySelectorAll('#bi-rows .mk-hab:not(.mk-letra)').length }))()""")
        p.conta("públicas", "a arte da habilidade chega no marcador",
                arte["letras"] == 0, "%s letras, %s ícones" % (arte["letras"], arte["icones"]))
    except RuntimeError as e:
        p.conta("públicas", "a arte da habilidade chega no marcador", False, str(e)[:80])

    # F13-T6: os dois laços de pedidos ao Supabase achados pela caçada de bugs
    # (117 e 126 pedidos em 5 s). Conta os pedidos que o app faz sozinho,
    # parado, depois de uma ação só.
    s.js("""(() => { window.__pedidos = 0; if (!window.__fetchEspiado) { const f = window.fetch;
      window.fetch = function (u, ...a) { if (String(u).includes('supabase')) window.__pedidos++;
        return f.call(this, u, ...a); }; window.__fetchEspiado = true; } return 'ok'; })()""")
    s.js("""(() => { const c = document.getElementById('bi-search'); c.value = 'cabeca';
      c.dispatchEvent(new Event('input', { bubbles: true })); return 'ok'; })()""")
    time.sleep(4)
    n = s.js("window.__pedidos")
    p.conta("públicas", "busca por ID que não existe não vira laço", n <= 1, "%s pedido(s) em 4 s" % n)
    s.js("""(() => { const c = document.getElementById('bi-search'); c.value = '';
      c.dispatchEvent(new Event('input', { bubbles: true })); return 'ok'; })()""")

    s.js("localStorage.setItem('publicacao.favoritos', JSON.stringify(['ffffff'])); window.__pedidos = 0; 'ok'")
    s.js("""document.querySelector('.bi-tab[data-view="minhas"]').click(); 'ok'""")
    time.sleep(4)
    n = s.js("window.__pedidos")
    p.conta("públicas", "favorita apagada do site não vira laço", n <= 1,
            "%s pedido(s) em 4 s; favoritos agora: %s" % (n, s.js("favoritosIds()")))


def checar_resolucoes(s, p):
    print("\n%sRESOLUCOES (1440, depois 1080, depois 900)%s" % (AMARELO, FIM))
    s.js("switchTab('catalog')")
    time.sleep(0.5)
    fora_js = """(() => {
      const mau = [];
      document.querySelectorAll('.card, .build-cat, .runa, .trilha-btn, .bh-grade, .oficina, .top-inner')
        .forEach(el => { const r = el.getBoundingClientRect();
          if (r.width > 0 && (r.right > innerWidth + 1 || r.left < -1))
            mau.push(el.className.split(' ')[0]); });
      return { rolagem: document.documentElement.scrollWidth > innerWidth + 1,
               fora: [...new Set(mau)].slice(0, 4) }; })()"""
    # Até 22/09 só o catálogo era medido, e a forja em 1280 rolava de lado sem
    # ninguém ver. Agora as três telas, em cada resolução — e com a PIOR build
    # que o catálogo permite, escolhida pelos dados: o item com o atributo mais
    # longo (o Biscoito, 255 caracteres, estourava a faixa da build em 1280) e o
    # de nome mais longo, mais alguns para encher as fileiras. Medir com uma
    # build comportada é o jeito de não achar nada. E no pior ESTADO também: a
    # faixa de atributos só aparece com o Editar ligado (F12), e a primeira
    # versão desta checagem media em modo leitura — passou com o bug lá dentro.
    s.nova_build()
    if not s.js("document.body.classList.contains('editando')"):
        s.clicar("#edit-switch", 0.8)
    pior = s.js("""(() => {
      const maiorAttr = (it) => Math.max(0, ...(it.attributes || []).map(a => (a.stat || '').length));
      const porAttr = CATALOG.items.slice().sort((a, b) => maiorAttr(b) - maiorAttr(a))[0];
      const porNome = CATALOG.items.slice().sort((a, b) => b.namePt.length - a.namePt.length)[0];
      const lend = CATALOG.items.filter(i => i.tier === 'Lendário').slice(0, 5);
      const c = build.cats[3];
      c.items = [porAttr, porNome, ...lend].map(it => ({ itemId: it.slug, note: 'observação de teste' }));
      renderBuildAll();
      return porAttr === porNome ? porAttr.namePt : porAttr.namePt + ' / ' + porNome.namePt; })()""")
    # Runas no pior modo também: o Completo (etiquetas, notas, controle de grupo
    # abertos), em cada trilha. Até a F13-T17 elas eram medidas em Ícones, e a
    # etiqueta que estourava o card com a Leitura calma ficava escondida.
    trilhas = s.js("RUNAS.trilhas.map(t => t.id)")
    # E com a Leitura calma ligada, que é o texto maior que o app tem: medir com
    # ela depender de um grupo anterior tê-la deixado ligada é medir por sorte.
    tinha_leitura = s.js("document.body.classList.contains('ac-leitura')")
    s.js("document.body.classList.add('ac-leitura'); 'ok'")
    for largura, altura in RESOLUCOES:
        s.tela(largura, altura)
        ruins = []
        for tela, cmd in (("catálogo", "switchTab('catalog')"), ("forja", "switchTab('build'); showBuildScreen('forja')"),
                          ("runas", "switchTab('runas')")):
            s.js(cmd + "; 'ok'")
            time.sleep(0.4)
            passos = [None]
            if tela == "runas":
                s.js("""(() => { const b = document.querySelector('.runas-modo[data-modo="ler"]'); if (b) b.click();
                  document.querySelector('.runas-vista[data-vista=completo]').click(); })()""")
                passos = trilhas
            for t in passos:
                if t:
                    s.js("""(() => { const b = [...document.querySelectorAll('#runas-trilhas [data-trilha]')]
                      .find(x => x.dataset.trilha === %s); if (b) b.click(); })()""" % json.dumps(t))
                    time.sleep(0.3)
                r = s.js(fora_js)
                if r["rolagem"] or r["fora"]:
                    ruins.append("%s%s (%s)" % (tela, " / " + t if t else "", ", ".join(r["fora"]) or "rolagem"))
                    break
        p.conta("resoluções", "%dx%d sem nada fora da tela" % (largura, altura), not ruins,
                ("catálogo, forja e runas (Completo, cinco trilhas), com Leitura calma e " + pior) if not ruins else "; ".join(ruins))
    if not tinha_leitura:
        s.js("document.body.classList.remove('ac-leitura'); 'ok'")
    s.js("switchTab('catalog'); 'ok'")
    s.tela_normal()


def checar_console(s, p):
    print("\n%sCONSOLE%s" % (AMARELO, FIM))
    p.conta("console", "nenhuma exceção durante o roteiro", not s.erros, "; ".join(s.erros[:3]))
    if s.dialogos:
        print("  %sdiálogos nativos que apareceram e foram aceitos: %s%s" % (CINZA, "; ".join(s.dialogos[:4]), FIM))
    # 404 de arquivo é o bug clássico do Pages: nome com outra caixa de letra.
    # o favicon.ico não existe de propósito: o 404 dele não é arquivo perdido
    quatro04 = [r for r in s.rede if "404" in r and "favicon" not in r]
    p.conta("console", "nenhum arquivo faltando (404)", not quatro04, "; ".join(quatro04[:3]))


# ---------------------------------------------------------------- principal
GRUPOS = [
    ("catálogo", checar_catalogo),
    ("forja", checar_forja),
    ("marcadores", checar_marcadores),
    ("runas", checar_runas),
    ("habilidades", checar_habilidades),
    ("texto", checar_texto),
    ("fragmento", checar_fragmento),
    ("salvar", checar_salvar),
    ("publicar", checar_publicar),
    ("exclusão", checar_exclusao),
    ("publicação órfã", checar_orfa),
    ("duas abas", checar_abas),
    ("última build", checar_ultima),
    ("atualização", checar_atualizacao),
    ("rascunho", checar_rascunho),
    ("troca", checar_troca),
    ("acessibilidade", checar_acessibilidade),
    ("resoluções", checar_resolucoes),
    ("calculadora", checar_calculadora),
    # Por último de propósito: com as 38 builds publicadas na tela, o navegador
    # fica pesado, e daí em diante qualquer medida sai contaminada.
    ("públicas", checar_publicas),
]


def main():
    ap = argparse.ArgumentParser(description="Roteiro de QA do Montador de Itens")
    ap.add_argument("--site", action="store_true", help="roda contra o GitHub Pages em vez desta pasta")
    ap.add_argument("--offline", action="store_true", help="pula o que precisa do servidor das builds")
    ap.add_argument("-k", metavar="PALAVRA", help="só os grupos cujo nome contém a palavra")
    ap.add_argument("--captura", metavar="ARQUIVO", help="salva uma captura do catálogo no fim")
    args = ap.parse_args()

    p = Placar()
    servidor = None
    if args.site:
        url = SITE
        print("Alvo: %s%s%s" % (CINZA, url, FIM))
    else:
        servidor = Servidor()
        url = servidor.url
        print("Alvo: %sesta pasta, servida em %s%s" % (CINZA, url, FIM))
        checar_arquivos(p)

    s = Sessao(url)
    try:
        s.abrir()
        checar_fundacao(s, p)
        for nome, fn in GRUPOS:
            if args.k and args.k.lower() not in nome.lower():
                continue
            # Grupo que estoura vira falha dele, não fim do roteiro: eu quero o
            # relatório inteiro, não o primeiro tropeço.
            try:
                if nome == "públicas":
                    fn(s, p, not args.offline)
                else:
                    fn(s, p)
            except Exception as e:
                p.conta(nome, "o grupo rodou até o fim", False,
                        "%s: %s" % (type(e).__name__, str(e)[:110]))
        checar_console(s, p)
        if args.captura:
            # A captura é cortesia: se o navegador já estiver ruim, não é ela que
            # vai decidir se o roteiro passou.
            try:
                s.js("switchTab('catalog')")
                time.sleep(0.8)
                s.captura(args.captura)
                print("\ncaptura em %s" % args.captura)
            except Exception as e:
                print("\nsem captura: %s" % str(e)[:80])
    finally:
        s.fechar()
        if servidor:
            servidor.parar()
    sys.exit(p.resumo())


if __name__ == "__main__":
    main()
