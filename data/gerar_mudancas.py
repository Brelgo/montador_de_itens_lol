#!/usr/bin/env python3
"""
gerar_mudancas.py — Capítulo 2, F13-T61
O que mudou no catálogo de um patch para o outro, item a item, lido do histórico
do data/catalog.js no git (e do catalog.js da pasta, se ele ainda não foi para o
commit). Grava data/mudancas.js (window.MUDANCAS), que o index.html usa para
decidir quais builds ficam desatualizadas.

Regra do Leo (21/10/2026): desatualizada é a build que tem, numa caixa que não é
Opcional, um item que mudou num patch depois do dela — ou um item que saiu do
catálogo. Uma build sem item mudado continua valendo no patch novo.

Uso:  python gerar_mudancas.py [saída]     (rodar depois do gerar_catalog_json.py)
      Sem argumento grava data/mudancas.js; com um caminho, grava lá — o roteiro
      de QA usa isso para conferir que o mudancas.js está em dia com o catálogo.

Só os campos de jogo contam: preço, custo de combinação, receita, atributos,
habilidades, modos, Reembolso e Passiva do Ornn (masterwork). Ícone, fontes,
notas e a análise de custo não desatualizam ninguém. Risco aceito com o Leo: uma
correção de texto do Capítulo 1 numa habilidade desatualiza a build sem precisar.

A saída não tem data nem hash: rodar duas vezes dá o mesmo arquivo.
"""
import json, os, re, subprocess, sys
from collections import OrderedDict

sys.stdout.reconfigure(encoding="utf-8")
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
CAMINHO = "data/catalog.js"
SAIDA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "mudancas.js")


def git(*args):
    return subprocess.run(["git", "-C", RAIZ] + list(args), capture_output=True, check=True).stdout


def ler(texto):
    texto = texto.decode("utf-8") if isinstance(texto, bytes) else texto
    return json.loads(texto[texto.index("{"): texto.rindex("}") + 1])


def versoes():
    """[(origem, catálogo)] em ordem de tempo: os commits do catalog.js e, se a
    pasta tem um catalog.js que não é o do último commit, ele por último."""
    out = []
    for h in git("log", "--reverse", "--format=%h", "--", CAMINHO).decode().split():
        out.append((h, ler(git("show", "%s:%s" % (h, CAMINHO)))))
    atual = ler(open(os.path.join(RAIZ, CAMINHO), encoding="utf-8").read())
    if not out or atual != out[-1][1]:
        out.append(("pasta", atual))
    return out


def por_patch(vs):
    """A última versão de cada patch: correção dentro do mesmo patch não conta —
    a build gravada naquele patch já nasceu com ela."""
    grupos = []
    for origem, cat in vs:
        p = cat["meta"]["patch"]
        if grupos and grupos[-1][0] == p:
            grupos[-1] = (p, origem, cat)
        else:
            grupos.append((p, origem, cat))
    return grupos


CAMPOS = OrderedDict([
    ("preço", lambda i: i.get("priceGold")),
    ("custo de combinação", lambda i: i.get("combineCost")),
    ("receita", lambda i: [(c.get("namePt"), c.get("qty")) for c in i.get("components") or []]),
    ("atributos", lambda i: [(a.get("stat"), a.get("value"), a.get("unit"), a.get("raw")) for a in i.get("attributes") or []]),
    ("habilidades", lambda i: [(h.get("name"), h.get("type"), h.get("description"), h.get("mechanics")) for h in i.get("abilities") or []]),
    ("modos", lambda i: sorted(i.get("gameModes") or [])),
    ("Reembolso", lambda i: [(i.get("cashback") or {}).get(k) for k in ("percent", "refundGold", "netGold")]),
    ("Passiva do Ornn", lambda i: [(i.get("masterwork") or {}).get("eligible"),
                                   [(m.get("stat"), m.get("base"), m.get("bonus"), m.get("total")) for m in (i.get("masterwork") or {}).get("stats") or []]]),
])


# Texto de habilidade que cita a fonte ("vazia no Data Dragon pt_BR 16.20.1") troca
# o número a cada patch sem o item mudar — achado no 16.21.1 (Atlas Mundial e
# Convergência de Zeke). O número de patch (16.21.1) vira um marcador antes de
# comparar; preço com ponto de milhar (1.100) não tem o terceiro grupo.
PATCH_NO_TEXTO = re.compile(r"\b\d{2}\.\d{1,2}\.\d{1,2}\b")


def assinatura(valor):
    return PATCH_NO_TEXTO.sub("<patch>", json.dumps(valor, ensure_ascii=False))


def compara(antes, depois):
    a = {i["slug"]: i for i in antes["items"]}
    d = {i["slug"]: i for i in depois["items"]}
    itens = OrderedDict()
    for slug in sorted(a):
        if slug not in d:
            continue
        mudou = [nome for nome, f in CAMPOS.items() if assinatura(f(a[slug])) != assinatura(f(d[slug]))]
        if mudou:
            itens[slug] = mudou
    removidos = sorted(s for s in a if s not in d)
    return itens, removidos


def main():
    grupos = por_patch(versoes())
    registro = []
    for (p0, o0, c0), (p1, o1, c1) in zip(grupos, grupos[1:]):
        itens, removidos = compara(c0, c1)
        registro.append(OrderedDict([("patch", p1), ("desde", p0), ("itens", itens), ("removidos", removidos)]))
        nomes = {i["slug"]: i["namePt"] for i in c1["items"]}
        print("%s → %s (%s → %s): %d itens mudaram, %d saíram" % (p0, p1, o0, o1, len(itens), len(removidos)))
        for slug, campos in itens.items():
            print("    %-34s %s" % (nomes.get(slug, slug), ", ".join(campos)))
        for slug in removidos:
            print("    saiu: %s" % slug)
    corpo = json.dumps({"versoes": registro}, ensure_ascii=False)
    open(SAIDA, "w", encoding="utf-8").write(
        "// GERADO por gerar_mudancas.py a partir do histórico do catalog.js no git — NÃO EDITAR À MÃO\n"
        "window.MUDANCAS = " + corpo + ";\n")
    print("→ %s (%d versões; patch atual %s)" % (os.path.relpath(SAIDA, RAIZ), len(registro), grupos[-1][0]))


if __name__ == "__main__":
    main()
