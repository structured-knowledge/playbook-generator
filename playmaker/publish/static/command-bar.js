// Unified command bar — browse + ask over the published snapshot
// (spec: web-publish / web-query). Merges the old search.js (client-side
// filtering) and ask.js (the /api/query call + answer rendering) into one
// controller, so typing filters the play list live while an explicit
// "Ask the playbook" action stays visible — never a hidden Enter-mode (D2).
// No backend change: the Ask path posts the same {question} to /api/query and
// consumes the same single JSON response.
(function () {
  const bar = document.getElementById("command-bar");
  if (!bar) return; // only the index hosts the command bar
  const input = document.getElementById("cmd-input");
  const askRow = document.getElementById("ask-row");
  const askTrigger = document.getElementById("ask-trigger");
  const askQuery = document.getElementById("ask-query");
  const examples = document.getElementById("examples");
  const browseView = document.getElementById("browse-view");
  const list = document.getElementById("play-list");
  const meta = document.getElementById("result-meta");
  const askView = document.getElementById("ask-view");
  const answer = document.getElementById("ask-answer");
  const backBtn = document.getElementById("back-to-plays");
  const facetToggle = document.getElementById("facet-toggle");
  const facetsEl = document.getElementById("facets");
  const totalCount = parseInt(bar.dataset.count || "0", 10);

  let plays = null;
  let keymap = null;
  const active = { kind: "", maturity: "", tool: "", contested: "" };

  async function load() {
    if (plays) return plays;
    try {
      const data = await (await fetch("data/plays.json")).json();
      plays = data.plays || [];
    } catch (e) {
      plays = [];
    }
    keymap = {};
    plays.forEach((p) => (keymap[p.key] = { url: p.url, title: p.title }));
    return plays;
  }

  const esc = (s) =>
    (s || "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ---- Browse: filter + sort (ported from search.js + cli.py:plays_cmd) -----

  const MATURITY = ["established", "emerging", "experimental"];
  const matRank = (p) => {
    const i = MATURITY.indexOf(p.maturity);
    return i < 0 ? MATURITY.length : i;
  };

  function score(p, q) {
    if ((p.title || "").toLowerCase().includes(q)) return 3;
    if ((p.why || "").toLowerCase().includes(q)) return 2;
    if ((p.brief || "").toLowerCase().includes(q)) return 2;
    if ((p.tool_categories || []).join(" ").toLowerCase().includes(q)) return 1;
    if ((p.body || "").toLowerCase().includes(q)) return 1;
    return 0;
  }

  function facetMatch(p) {
    if (active.kind && p.kind !== active.kind) return false;
    if (active.maturity && p.maturity !== active.maturity) return false;
    if (active.contested && !p.contested) return false;
    if (active.tool && !(p.tool_categories || []).includes(active.tool)) return false;
    return true;
  }

  function itemHTML(p) {
    return (
      `<li class="play-item">` +
      `<a class="play-title" href="${p.url}">${esc(p.title)}</a>` +
      (p.kind ? ` <span class="badge kind">${esc(p.kind)}</span>` : "") +
      (p.maturity ? ` <span class="badge maturity ${esc(p.maturity)}">${esc(p.maturity)}</span>` : "") +
      (p.contested ? ` <span class="badge contested">⚠ contested</span>` : "") +
      (p.why ? `<p class="why-line">${esc(p.why)}</p>` : "") +
      `</li>`
    );
  }

  function metaText(n, q) {
    if (q) return `matching plays <span class="muted">· ${n}</span>`;
    const labels = [];
    if (active.kind) labels.push(esc(active.kind));
    if (active.maturity) labels.push(esc(active.maturity));
    if (active.tool) labels.push(esc(active.tool));
    if (active.contested) labels.push("contested");
    if (labels.length) return `${labels.join(" · ")} <span class="muted">· ${n} plays</span>`;
    return `plays <span class="muted">· by maturity</span>`;
  }

  function renderList() {
    if (!plays) return; // keep the server-rendered list until data arrives
    const q = input.value.trim().toLowerCase();
    let rows = plays.filter(facetMatch);
    if (q) {
      rows = rows
        .map((p) => [score(p, q), p])
        .filter((x) => x[0] > 0)
        .sort((a, b) => b[0] - a[0] || a[1].title.localeCompare(b[1].title))
        .map((x) => x[1]);
    } else {
      rows = rows.sort((a, b) => matRank(a) - matRank(b) || a.title.localeCompare(b.title));
    }
    meta.innerHTML = metaText(rows.length, q);
    list.innerHTML = rows.length
      ? rows.map(itemHTML).join("")
      : `<li class="play-item empty">No plays match.</li>`;
  }

  function syncChips() {
    bar.querySelectorAll(".chip").forEach((chip) => {
      const f = chip.dataset.facet;
      const on = (active[f] || "") === (chip.dataset.value || "");
      chip.classList.toggle("is-active", f === "kind" ? on : on && !!chip.dataset.value);
    });
  }

  // ---- View state: browse vs. ask ------------------------------------------

  function renderBrowseState() {
    const q = input.value.trim();
    askRow.hidden = !q;
    if (q) askQuery.textContent = `"${q}"`;
    if (examples) examples.hidden = !!q;
    renderList();
  }

  function showBrowse() {
    bar.classList.remove("is-asking");
    askView.hidden = true;
    browseView.hidden = false;
    renderBrowseState();
  }

  // ---- Ask: minimal markdown + [[key]] links (ported from ask.js) ----------

  function inline(s) {
    s = (s || "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    s = s.replace(/\[\[([^\]\|]+)(?:\|([^\]]*))?\]\]/g, (m, k, lab) => {
      const e = keymap && keymap[k];
      const text = (lab && lab.trim()) || (e && e.title) || k.split("/").pop().replace(/-/g, " ");
      return e ? `<a href="${e.url}">${esc(text)}</a>` : esc(text);
    });
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m, t, u) => `<a href="${esc(u)}">${esc(t)}</a>`);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    return s;
  }

  function renderMarkdown(md) {
    let html = "", listTag = null;
    const closeList = () => { if (listTag) { html += `</${listTag}>`; listTag = null; } };
    for (const raw of (md || "").split("\n")) {
      const line = raw.replace(/\s+$/, "");
      let m;
      if (!line.trim()) { closeList(); continue; }
      if ((m = line.match(/^(#{1,6})\s+(.*)$/))) {
        closeList();
        html += `<h${Math.min(m[1].length + 1, 6)}>${inline(m[2])}</h${Math.min(m[1].length + 1, 6)}>`;
      } else if ((m = line.match(/^\s*\d+\.\s+(.*)$/))) {
        if (listTag !== "ol") { closeList(); html += "<ol>"; listTag = "ol"; }
        html += `<li>${inline(m[1])}</li>`;
      } else if ((m = line.match(/^\s*[-*]\s+(.*)$/))) {
        if (listTag !== "ul") { closeList(); html += "<ul>"; listTag = "ul"; }
        html += `<li>${inline(m[1])}</li>`;
      } else {
        closeList();
        html += `<p>${inline(line)}</p>`;
      }
    }
    closeList();
    return html;
  }

  function bestMatch(q) {
    const lq = q.trim().toLowerCase();
    if (!plays || !lq) return null;
    const hit = plays
      .map((p) => [score(p, lq), p])
      .filter((x) => x[0] > 0)
      .sort((a, b) => b[0] - a[0])[0];
    return hit ? hit[1] : null;
  }

  function noAnswerCTA(q) {
    const closest = bestMatch(q);
    const hint = closest
      ? `<p class="closest">Closest topic ▸ <a href="${closest.url}">${esc(closest.title)}</a></p>`
      : "";
    const cmd = "playmaker ingest <url>";
    return (
      hint +
      `<div class="ingest-cta"><span class="cta-lead">This needs a source:</span>` +
      `<div class="cmd-copy"><code>${esc(cmd)}</code>` +
      `<button type="button" class="copy-btn" data-copy="${esc(cmd)}">copy</button></div></div>`
    );
  }

  async function ask(q) {
    q = (q || "").trim();
    if (!q) return;
    input.value = q;
    await load();

    // Honest elapsed feedback — a single JSON response still, no streaming (D5).
    bar.classList.add("is-asking");
    browseView.hidden = true;
    askView.hidden = false;
    const t0 = Date.now();
    const phase = () => {
      const s = Math.round((Date.now() - t0) / 1000);
      answer.innerHTML = `<p class="asking"><span class="spin" aria-hidden="true">◌</span> Reading ${totalCount} plays… · ${s}s</p>`;
    };
    phase();
    const timer = setInterval(phase, 1000);

    try {
      const res = await fetch("api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      clearInterval(timer);
      if (!res.ok || data.error) {
        answer.innerHTML = `<p class="error">Query failed: ${esc(data.error || res.status)}</p>`;
        return;
      }
      const cited =
        data.cited && data.cited.length
          ? `<p class="cited">Cited: ${data.cited
              .map((k) => { const e = keymap[k]; return e ? `<a href="${e.url}">${esc(e.title)}</a>` : esc(k); })
              .join(" · ")}</p>`
          : noAnswerCTA(q);
      answer.innerHTML = `<div class="answer-body">${renderMarkdown(data.answer)}</div>${cited}`;
    } catch (err) {
      clearInterval(timer);
      answer.innerHTML =
        '<p class="error">Could not reach the query endpoint — it only runs when the site is deployed.</p>';
    }
  }

  // ---- Wiring --------------------------------------------------------------

  input.addEventListener("input", showBrowse);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); ask(input.value); }
  });
  askTrigger.addEventListener("click", () => ask(input.value));
  backBtn.addEventListener("click", showBrowse);

  bar.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const f = chip.dataset.facet, v = chip.dataset.value || "";
      active[f] = active[f] === v ? "" : v; // toggle; "all" (empty value) clears
      syncChips();
      showBrowse();
    });
  });

  if (examples) {
    examples.querySelectorAll(".example").forEach((b) => {
      b.addEventListener("click", () => ask(b.dataset.q));
    });
  }

  if (facetToggle) {
    facetToggle.addEventListener("click", () => {
      const open = facetsEl.classList.toggle("open");
      facetToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  answer.addEventListener("click", (e) => {
    const btn = e.target.closest(".copy-btn");
    if (!btn) return;
    navigator.clipboard && navigator.clipboard.writeText(btn.dataset.copy);
    btn.textContent = "copied";
    setTimeout(() => (btn.textContent = "copy"), 1500);
  });

  // Load data, then let JS take over the server-rendered list.
  load().then(renderBrowseState);
})();
