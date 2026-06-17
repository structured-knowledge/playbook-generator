// Client-side play search — no backend (spec: web-publish / client-side search).
// Lazy-loads data/plays.json on first keystroke, filters, and overlays results.
(function () {
  const input = document.getElementById("search");
  const results = document.getElementById("search-results");
  if (!input || !results) return;
  const defaultView = document.getElementById("default-view");
  let plays = null;

  async function load() {
    if (plays) return plays;
    const res = await fetch("data/plays.json");
    plays = (await res.json()).plays || [];
    return plays;
  }

  function score(p, q) {
    if ((p.title || "").toLowerCase().includes(q)) return 3;
    if ((p.why || "").toLowerCase().includes(q)) return 2;
    if ((p.brief || "").toLowerCase().includes(q)) return 2;
    if ((p.tool_categories || []).join(" ").toLowerCase().includes(q)) return 1;
    if ((p.body || "").toLowerCase().includes(q)) return 1;
    return 0;
  }

  function esc(s) {
    return (s || "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  async function run(raw) {
    const q = raw.trim().toLowerCase();
    if (!q) {
      results.hidden = true;
      results.innerHTML = "";
      if (defaultView) defaultView.hidden = false;
      return;
    }
    const hits = (await load())
      .map((p) => [score(p, q), p])
      .filter((x) => x[0] > 0)
      .sort((a, b) => b[0] - a[0] || a[1].title.localeCompare(b[1].title))
      .slice(0, 25);
    results.innerHTML = hits.length
      ? hits.map(([, p]) =>
          `<li><a href="${p.url}">${esc(p.title)}</a>` +
          (p.kind ? ` <span class="badge kind">${esc(p.kind)}</span>` : "") +
          (p.why ? `<p class="why-line">${esc(p.why)}</p>` : "") +
          `</li>`).join("")
      : '<li class="empty">No plays match.</li>';
    if (defaultView) defaultView.hidden = true;
    results.hidden = false;
  }

  input.addEventListener("input", (e) => run(e.target.value));
})();
