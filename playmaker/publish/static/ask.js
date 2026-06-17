// "Ask the playbook" — posts to the /api/query serverless function and renders
// the grounded answer, turning [[key]] citations into links to play pages
// (spec: web-query). The endpoint only exists when deployed; failures degrade
// to a friendly note. A tiny markdown renderer keeps the answer readable with
// no external dependency.
(function () {
  const form = document.getElementById("ask-form");
  if (!form) return;
  const input = document.getElementById("ask-input");
  const out = document.getElementById("ask-answer");
  let keymap = null;

  async function keys() {
    if (keymap) return keymap;
    keymap = {};
    try {
      const plays = (await (await fetch("data/plays.json")).json()).plays || [];
      plays.forEach((p) => (keymap[p.key] = { url: p.url, title: p.title }));
    } catch (e) {}
    return keymap;
  }

  const esc = (s) =>
    (s || "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

  function inline(s, km) {
    s = esc(s);
    s = s.replace(/\[\[([^\]\|]+)(?:\|([^\]]*))?\]\]/g, (m, k, lab) => {
      const e = km[k];
      const text = (lab && lab.trim()) || (e && e.title) || k.split("/").pop().replace(/-/g, " ");
      return e ? `<a href="${e.url}">${esc(text)}</a>` : esc(text);
    });
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m, t, u) => `<a href="${esc(u)}">${esc(t)}</a>`);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    return s;
  }

  function render(md, km) {
    let html = "", listTag = null;
    const closeList = () => { if (listTag) { html += `</${listTag}>`; listTag = null; } };
    for (const raw of (md || "").split("\n")) {
      const line = raw.replace(/\s+$/, "");
      let m;
      if (!line.trim()) { closeList(); continue; }
      if ((m = line.match(/^(#{1,6})\s+(.*)$/))) {
        closeList();
        const lvl = Math.min(m[1].length + 1, 6);
        html += `<h${lvl}>${inline(m[2], km)}</h${lvl}>`;
      } else if ((m = line.match(/^\s*\d+\.\s+(.*)$/))) {
        if (listTag !== "ol") { closeList(); html += "<ol>"; listTag = "ol"; }
        html += `<li>${inline(m[1], km)}</li>`;
      } else if ((m = line.match(/^\s*[-*]\s+(.*)$/))) {
        if (listTag !== "ul") { closeList(); html += "<ul>"; listTag = "ul"; }
        html += `<li>${inline(m[1], km)}</li>`;
      } else {
        closeList();
        html += `<p>${inline(line, km)}</p>`;
      }
    }
    closeList();
    return html;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    out.hidden = false;
    out.innerHTML = '<p class="asking">Asking the playbook…</p>';
    try {
      const res = await fetch("api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        out.innerHTML = `<p class="error">Query failed: ${esc(data.error || res.status)}</p>`;
        return;
      }
      const km = await keys();
      const cited =
        data.cited && data.cited.length
          ? `<p class="cited">Cited: ${data.cited
              .map((k) => { const e = km[k]; return e ? `<a href="${e.url}">${esc(e.title)}</a>` : esc(k); })
              .join(" · ")}</p>`
          : "";
      out.innerHTML = `<div class="answer-body">${render(data.answer, km)}</div>${cited}`;
    } catch (err) {
      out.innerHTML =
        '<p class="error">Could not reach the query endpoint — it only runs when the site is deployed.</p>';
    }
  });
})();
