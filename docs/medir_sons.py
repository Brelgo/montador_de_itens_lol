"""Mede a altura de cada som de assets/audio e grava data/ganho_sons.js.

F13-T48 (Leo, 18/10/2026: "precisa reduzir mais os sons, estou tendo que deixar o
volume no mínimo"). Os arquivos vêm gravados em alturas muito diferentes — as
falas do lojista com RMS perto de -13 dBFS, os cliques da loja perto de -46 —,
então nenhum volume geral serve para todos. Este script decodifica cada mp3 no
Chrome do roteiro de QA (mudo: o OfflineAudioContext não toca nada), mede o RMS e
o pico, e grava o ganho de cada arquivo para que nenhum passe de ALVO_DB. Quem já
está abaixo do alvo fica com ganho 1 (o volume de um <audio> não passa de 1).

Rodar de novo sempre que entrar ou mudar um arquivo em assets/audio:
    python docs/medir_sons.py
"""
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
import qa_roteiro as q  # noqa: E402

ALVO_DB = -30.0   # RMS máximo de um som com o volume geral no máximo

JS = """(async () => {
  const arquivos = [...new Set(Object.values(Som.ARQUIVOS).flat())];
  const ctx = new OfflineAudioContext(1, 44100, 44100);
  const out = [];
  for (const f of arquivos) {
    try {
      const a = await ctx.decodeAudioData(await (await fetch('assets/audio/' + f)).arrayBuffer());
      let pico = 0, soma = 0, n = 0;
      for (let c = 0; c < a.numberOfChannels; c++) { const d = a.getChannelData(c);
        for (let i = 0; i < d.length; i++) { const v = Math.abs(d[i]); if (v > pico) pico = v; soma += d[i] * d[i]; n++; } }
      out.push({ f, rms: Math.sqrt(soma / n), pico });
    } catch (e) { out.push({ f, erro: String(e) }); }
  }
  return out; })()"""


def main():
    srv = q.Servidor()
    s = q.Sessao(srv.url)
    try:
        s.abrir()
        s.entrar()
        medidas = s.js(JS)
    finally:
        s.fechar()
        try:
            srv.fechar()
        except Exception:
            pass
    erros = [m for m in medidas if "erro" in m]
    if erros:
        sys.exit("Não deu para decodificar: %s" % ", ".join(m["f"] for m in erros))
    ganhos = {}
    for m in sorted(medidas, key=lambda m: m["f"]):
        db = 20 * math.log10(m["rms"]) if m["rms"] > 0 else -99.0
        ganhos[m["f"]] = round(min(1.0, 10 ** ((ALVO_DB - db) / 20)), 4)
    linhas = ["// Gerado por docs/medir_sons.py (F13-T48) — não editar à mão.",
              "// Ganho de cada arquivo para que nenhum som passe de %.0f dBFS RMS com o volume" % ALVO_DB,
              "// geral no máximo; quem já está abaixo fica com 1.",
              "window.GANHO_SONS = " + json.dumps(ganhos, ensure_ascii=False, indent=1) + ";", ""]
    with open(os.path.join(RAIZ, "data", "ganho_sons.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(linhas))
    baixados = [k for k, v in ganhos.items() if v < 1]
    print("%d arquivos medidos; %d baixados para %.0f dBFS; o mais baixado: %s (x%.3f)" % (
        len(ganhos), len(baixados), ALVO_DB, min(ganhos, key=ganhos.get), min(ganhos.values())))


if __name__ == "__main__":
    main()
