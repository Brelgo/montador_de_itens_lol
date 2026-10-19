// Amostra F13 — "a build sempre aberta" (Leo, 18/10/2026: "sempre quando eu estou
// no site, tecnicamente eu sempre estou em uma build ativa… precisa ter alguma
// forma de demonstrar que tem uma build ativa ou se é para sair da edição").
// Só para a captura: injetada no app de verdade pelo docs/amostras_build_aberta.py,
// desenha a plaqueta "Na bigorna" no topo, a faixa da loja que acompanha a
// rolagem e o "Em qual build?". Não é código do app e não grava nada.
(function () {
  const css = `
  /* pendurada por duas correntes sob a aba Builds: a identidade fica no próprio
     controle, e o cabeçalho não muda de altura (sob a aba sobram 47 px na loja) */
  header.top nav.tabs { position: relative; }
  .bigorna { display: inline-flex; align-items: center; gap: 10px; position: absolute; top: calc(100% + 7px); z-index: 40;
    padding: 4px 8px 4px 0; border-radius: 3px; max-width: 560px; white-space: nowrap;
    background: linear-gradient(180deg, #2a2420, #1a1512); border: 1px solid #443a32;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.05), inset 0 0 22px rgba(0,0,0,.45), 0 3px 8px rgba(0,0,0,.5); }
  .bigorna::before, .bigorna::after { content: ""; position: absolute; top: 5px; width: 5px; height: 5px; border-radius: 50%;
    background: radial-gradient(circle at 35% 35%, #e6c27a, #7a5a26); box-shadow: 0 1px 1px rgba(0,0,0,.6); }
  .bigorna::after { right: 5px; } .bigorna::before { right: 5px; top: auto; bottom: 5px; }
  .bg-corrente { position: absolute; top: -8px; width: 3px; height: 8px; border-radius: 2px;
    background: repeating-linear-gradient(180deg, #8a7a66 0 2px, #3a2f28 2px 3px); }
  .bg-brasa { align-self: stretch; width: 5px; border-radius: 3px 0 0 3px; background: #ff7a1e;
    box-shadow: 0 0 8px 2px rgba(255,120,30,.5); }
  .bigorna[data-estado="vazia"] .bg-brasa { background: #3a2f28; box-shadow: none; }
  .bigorna[data-estado="sujo"] .bg-brasa { animation: cff-pulsa 1.8s ease-in-out infinite; }
  .bg-rot { font-family: var(--loja-gravado); font-size: 10.5px; letter-spacing: .16em; text-transform: uppercase; color: #ffd27a; white-space: nowrap; }
  .bigorna[data-estado="vazia"] .bg-rot { color: #8f8074; }
  .bg-nome { background: none; border: 0; padding: 0; cursor: pointer; font-family: 'IM Fell English', Georgia, serif;
    font-size: 15px; color: #fff4e0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 220px; flex-shrink: 0; }
  .bg-estado { font-family: var(--loja-texto); font-style: italic; font-size: 12.5px; color: #c9973f; white-space: nowrap; }
  .bg-estado .sujo { color: #ffb257; }
  .bg-btn { background: transparent; border: 1px solid #3a3029; border-radius: 3px; color: #b8a890; cursor: pointer;
    font-family: var(--loja-texto); font-size: 12px; padding: 2px 8px; white-space: nowrap; }
  .bg-x { font-size: 15px; line-height: 1; padding: 1px 7px 3px; margin-right: 8px; }
  .bg-abrir { margin-right: 8px; color: #ffd27a; border-color: #5a4630; }
  /* a faixa da loja: a de "Forjando em", agora presa no topo enquanto há build */
  .cff-amostra { position: sticky; top: 0; z-index: 30; margin: -6px 0 12px; }
  .cff-amostra .cff-texto b { margin-right: 2px; }
  .cff-amostra .cff-caixa { color: #d8cbb6; font-family: var(--loja-texto); font-size: 13.5px; }
  .cff-amostra .cff-caixa b { color: #ffd27a; font-weight: 500; }
  .cff-amostra .sujo { color: #ffb257; font-style: italic; font-size: 13px; white-space: nowrap; }
  /* rótulo da build no pergaminho */
  .ec-ultima { font-family: var(--loja-gravado); font-size: 9.5px; letter-spacing: .14em; text-transform: uppercase;
    color: #8d2c22; border: 1px solid rgba(141,44,34,.45); border-radius: 2px; padding: 1px 5px; margin-left: 6px; }
  `;
  const st = document.createElement("style");
  st.id = "amostra-bigorna-css";
  st.textContent = css;
  document.head.appendChild(st);

  const esc = (t) => String(t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // estado: "aberta" | "editando" | "sujo" | "vazia" | "vendo"
  window.amostraBigorna = function (estado, nome, caixa, qtd) {
    document.querySelectorAll(".bigorna, .cff-amostra").forEach(e => e.remove());
    const nav = document.querySelector("header.top nav.tabs");
    const p = document.createElement("div");
    p.className = "bigorna";
    p.dataset.estado = estado;
    if (estado === "vazia") {
      p.innerHTML = `<span class="bg-brasa"></span><span class="bg-rot">Bigorna vazia</span>
        <button type="button" class="bg-btn bg-abrir" title="Abrir uma das suas builds">abrir uma build</button>`;
    } else {
      const rot = estado === "vendo" ? "Vendo" : "Na bigorna";
      const ext = { aberta: "", editando: "· editando", sujo: '· editando · <span class="sujo">● não salva</span>', vendo: "· só visualização" }[estado];
      const parar = (estado === "editando" || estado === "sujo") ? `<button type="button" class="bg-btn" title="Desliga o Editar; a build continua na bigorna">parar de editar</button>` : "";
      p.innerHTML = `<span class="bg-brasa"></span><span class="bg-rot">${rot}</span>
        <button type="button" class="bg-nome" title="Ir para a forja">${esc(nome)}</button>
        ${ext ? `<span class="bg-estado">${ext}</span>` : ""}${parar}
        <button type="button" class="bg-btn bg-x" title="Largar a build — ela continua salva na lista" aria-label="Largar a build">×</button>`;
    }
    const aba = nav.querySelector('.tab-btn[data-tab="build"]');
    p.style.left = (aba.offsetLeft + 6) + "px";
    p.insertAdjacentHTML("afterbegin", '<i class="bg-corrente" style="left:14px"></i><i class="bg-corrente" style="left:calc(100% - 18px)"></i>');
    nav.appendChild(p);
    // a faixa da loja
    const faixa = document.getElementById("catalog-forja-faixa");
    if (faixa) faixa.hidden = true;
    if (estado !== "vazia" && faixa) {
      const f = document.createElement("div");
      f.className = "catalog-forja-faixa cff-amostra";
      const cx = caixa ? `<span class="cff-caixa">· caixa <b>${esc(caixa)}</b>${qtd != null ? ` · ${qtd} ${qtd === 1 ? "item" : "itens"}` : ""}</span>`
                       : `<span class="cff-caixa">· o clique pergunta a caixa</span>`;
      f.innerHTML = `<span class="cff-brasa" aria-hidden="true"></span>
        <span class="cff-texto">${estado === "vendo" ? "Vendo" : "Na bigorna"} <b>${esc(nome)}</b></span>${cx}
        <span class="cff-dica"></span>${estado === "sujo" ? '<span class="sujo">● não salva</span>' : ""}
        ${caixa ? '<button type="button" class="cff-soltar">soltar a caixa</button>' : ""}
        <button type="button" class="cff-soltar" title="Largar a build">largar ×</button>`;
      faixa.insertAdjacentElement("afterend", f);
    }
  };

  // o pergaminho "Em qual build?" (opção B), sobre o #escolher-caixa de verdade
  window.amostraEmQualBuild = function (slug, builds) {
    const item = CATALOG.items.find(i => i.slug === slug);
    const dlg = document.getElementById("escolher-caixa");
    dlg.querySelector(".md-title").textContent = "Em qual build?";
    document.getElementById("ec-sub").innerHTML = `<img src="${item.iconUrl}" alt=""> Colocar <b>${esc(item.namePt)}</b> em…`;
    document.getElementById("ec-lista").innerHTML = builds.map((b, i) => `<button type="button" class="ec-caixa">
        <span>${esc(b.nome)}${i === 0 ? '<span class="ec-ultima">a última aberta</span>' : ""}</span>
        <span class="ec-tipo">${esc(b.modo)}</span><span class="ec-qtd">${b.qtd} itens</span></button>`).join("")
      + `<button type="button" class="ec-caixa ec-nova">Nova build e colocar aqui</button>`;
    dlg.querySelector(".ec-dica").textContent = "A build escolhida fica na bigorna até você largá-la no × do topo.";
    dlg.hidden = false;
  };
})();
