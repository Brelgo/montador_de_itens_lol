"""Captura das duas opções da "build sempre aberta" (F13, 18/10/2026).

Abre o app de verdade no Chrome do QA (mudo, sem tocar no servidor das builds),
injeta docs/amostras/fase13-build-aberta.js e fotografa:
  Opção A — a build fica na bigorna até você largá-la (o F5 volta com ela);
  Opção B — o site sempre abre com a bigorna vazia, e o primeiro item pergunta
            em qual build entra.
Nada disso é código do app. Saída: docs/screenshots/fase13-build-aberta-opcoes.png
Uso: python docs/amostras_build_aberta.py
"""
import base64
import io
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import qa_roteiro as q  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

RAIZ = os.path.dirname(AQUI)
JS = open(os.path.join(AQUI, "amostras", "fase13-build-aberta.js"), encoding="utf-8").read()


def foto(s, clip=None):
    pedido = {"format": "png"}
    if clip:
        pedido["clip"] = dict(clip, scale=1)
    return Image.open(io.BytesIO(base64.b64decode(s.envia("Page.captureScreenshot", pedido)["data"]))).convert("RGB")


srv = q.Servidor()
s = q.Sessao(srv.url)
fotos = {}
try:
    s.abrir()
    s.tela(1440, 900)
    s.entrar()
    s.js("localStorage.clear(); 'ok'")
    s.abrir()
    time.sleep(1.0)
    s.entrar()
    s.js(JS + "; 'ok'")
    s.js("switchTab('catalog'); window.scrollTo(0, 0); 'ok'")
    time.sleep(0.6)
    nome = "Jinx ADC — crítico"
    # Opção A: ao entrar, a build de ontem continua na bigorna, à vista
    s.js("amostraBigorna('aberta', %r); 'ok'" % nome)
    time.sleep(0.4)
    fotos["A1"] = foto(s)
    # ...rolando a loja, com uma caixa escolhida e alteração por salvar
    s.js("amostraBigorna('sujo', %r, 'Núcleo', 3); window.scrollTo(0, 760); 'ok'" % nome)
    time.sleep(0.6)
    fotos["A2"] = foto(s)
    # Opção B: ao entrar, nada na bigorna
    s.js("window.scrollTo(0, 0); amostraBigorna('vazia'); 'ok'")
    time.sleep(0.5)
    fotos["B1"] = foto(s)
    slug = s.js("CATALOG.items.find(i => i.namePt === 'Gume do Infinito').slug")
    s.js("""amostraEmQualBuild(%r, [
      { nome: %r, modo: 'Summoner\\'s Rift', qtd: 9 },
      { nome: 'Sona suporte', modo: 'Summoner\\'s Rift', qtd: 6 },
      { nome: 'Malphite topo', modo: 'ARAM', qtd: 7 }]); 'ok'""" % (slug, nome))
    time.sleep(0.5)
    fotos["B2"] = foto(s)
    s.js("document.getElementById('escolher-caixa').hidden = true; 'ok'")
    # os estados da plaqueta, recortados do topo
    for est in ("aberta", "editando", "sujo", "vendo", "vazia"):
        s.js("amostraBigorna(%r, %r); window.scrollTo(0, 0); 'ok'" % (est, nome if est != "vendo" else "Ahri meio (pública)"))
        time.sleep(0.3)
        r = s.js("(() => { const r = document.querySelector('.bigorna').getBoundingClientRect(); return { x: r.left - 10, y: r.top - 8, width: r.width + 20, height: r.height + 16 }; })()")
        fotos["p-" + est] = foto(s, r)
    for w, h in ((2560, 1440), (1920, 1080), (1440, 900), (1600, 900)):
        s.tela(w, h)
        time.sleep(0.4)
        s.js("document.querySelectorAll('.bigorna, .cff-amostra').forEach(e => e.remove()); 'ok'")
        alt = s.js("Math.round(document.querySelector('header.top').getBoundingClientRect().height)")
        s.js("amostraBigorna('sujo', %r); 'ok'" % nome)
        m = s.js("""(() => { const h = document.querySelector('header.top').getBoundingClientRect(); const p = document.querySelector('.bigorna').getBoundingClientRect();
          const busca = document.querySelector('#search-input'); const b = busca ? busca.getBoundingClientRect() : null;
          return [Math.round(h.height), Math.round(p.bottom), b ? Math.round(b.top) : null, Math.round(p.right), innerWidth]; })()""")
        print("%dx%d: cabeçalho %spx (sem a plaqueta: %spx); plaqueta termina em %s, a busca começa em %s; direita %s de %s" % (w, h, m[0], alt, m[1], m[2], m[3], m[4]))
    print("erros:", s.erros[:3])
    for k in ("A1", "A2", "B1", "B2"):
        fotos[k] = fotos[k].crop((0, 0, 1440, 560))
finally:
    s.fechar()
    try:
        srv.fechar()
    except Exception:
        pass

f_t = ImageFont.truetype("C:/Windows/Fonts/georgia.ttf", 21)
f_p = ImageFont.truetype("C:/Windows/Fonts/georgia.ttf", 15)
esc = 0.56
tam = (int(1440 * esc), int(560 * esc))
W = 40 + tam[0] * 2 + 30 + 40
H = 70 + 2 * (tam[1] + 70) + 260
img = Image.new("RGB", (W, H), (22, 17, 13))
d = ImageDraw.Draw(img)
d.text((40, 22), "A build sempre aberta — duas opções (a plaqueta e a faixa valem para as duas)", font=f_t, fill=(233, 179, 106))
linhas = [("Opção A — a build fica na bigorna até você largá-la; o F5 volta com ela", "A1", "ao entrar no site", "A2", "rolando a loja, com caixa e alteração por salvar"),
          ("Opção B — o site sempre abre com a bigorna vazia", "B1", "ao entrar no site", "B2", "o primeiro item clicado pergunta a build")]
y = 70
for titulo, k1, l1, k2, l2 in linhas:
    d.text((40, y), titulo, font=f_t, fill=(255, 210, 122))
    d.text((40, y + 30), l1, font=f_p, fill=(207, 194, 173))
    d.text((40 + tam[0] + 30, y + 30), l2, font=f_p, fill=(207, 194, 173))
    img.paste(fotos[k1].resize(tam, Image.LANCZOS), (40, y + 52))
    img.paste(fotos[k2].resize(tam, Image.LANCZOS), (40 + tam[0] + 30, y + 52))
    y += tam[1] + 70
d.text((40, y), "Os estados da plaqueta: na bigorna · editando · não salva · vendo uma pública · vazia", font=f_p, fill=(207, 194, 173))
x, yy = 40, y + 26
for est in ("aberta", "editando", "sujo", "vendo", "vazia"):
    im = fotos["p-" + est]
    if x + im.width > W - 20:
        x, yy = 40, yy + im.height + 12
    img.paste(im, (x, yy))
    x += im.width + 14
img = img.crop((0, 0, W, yy + fotos["p-aberta"].height + 24))
saida = os.path.join(RAIZ, "docs", "screenshots", "fase13-build-aberta-opcoes.png")
img.save(saida)
print("salvo", saida, img.size)
