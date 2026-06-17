// Vault app — a 3-pane reader over the published snapshot: taxonomy (left),
// source viewer (center), and the assistant (right). All client-side over
// data/plays.json; the Ask path posts the same {question} to /api/query and
// consumes the same single JSON response (no backend change).
(function () {
  const app = document.getElementById("app");
  if (!app) return;
  const $ = (id) => document.getElementById(id);
  const totalCount = parseInt(app.dataset.count || "0", 10);

  let plays = null, byKey = {}, byUrl = {}, currentKey = null;

  // ---- data -----------------------------------------------------------------
  async function load() {
    if (plays) return plays;
    try {
      plays = (await (await fetch("data/plays.json")).json()).plays || [];
    } catch (e) { plays = []; }
    plays.forEach((p) => { byKey[p.key] = p; byUrl[p.url] = p; });
    return plays;
  }

  const esc = (s) =>
    (s || "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function status(msg) { $("statusbar").querySelector(".status-label").textContent = msg; }

  // ---- viewer ---------------------------------------------------------------
  function docHeader(p) {
    const badges =
      (p.kind ? `<span class="badge kind">${esc(p.kind)}</span>` : "") +
      (p.maturity ? `<span class="badge maturity ${esc(p.maturity)}">${esc(p.maturity)}</span>` : "") +
      (p.contested ? `<span class="badge contested">⚠ contested</span>` : "");
    const why = p.why ? `<blockquote class="why"><strong>Why</strong>${esc(p.why)}</blockquote>` : "";
    return `<header class="doc-head"><h1>${esc(p.title)}</h1>` +
           `<div class="badges">${badges}</div>${why}</header>`;
  }

  function openDoc(key, opts) {
    const p = byKey[key];
    if (!p) return;
    opts = opts || {};
    currentKey = key;
    const ribbon = opts.cite
      ? `<div class="cite-ribbon">✦ Cited by the assistant — jumped to this source</div>`
      : "";
    const body = $("viewer-body");
    body.className = "viewer-body" + (opts.cite ? " ai-cited" : "");
    body.innerHTML = ribbon + docHeader(p) + `<div class="doc-body">${p.body_html || ""}</div>`;
    body.hidden = false;
    $("viewer-empty").hidden = true;
    $("viewer-actions").hidden = false;
    $("open-source").hidden = false;
    $("viewer-search").disabled = false;
    $("viewer-search").value = "";
    $("viewer-status").textContent = "LOCKED SOURCE";
    // tab
    $("open-tab").hidden = false;
    $("tab-title").textContent = p.title;
    // active item in taxonomy
    document.querySelectorAll(".tax-item.active").forEach((a) => a.classList.remove("active"));
    const link = document.querySelector(`.tax-item[data-key="${cssEsc(key)}"]`);
    if (link) { link.classList.add("active"); revealGroup(link); }
    // deep link + scroll
    history.replaceState(null, "", "#" + key);
    $("viewer-scroll").scrollTop = 0;
    status(opts.cite ? `Opened ${p.title} — jumped to cited source` : `Opened ${p.title}`);
  }

  function cssEsc(s) { return (window.CSS && CSS.escape) ? CSS.escape(s) : s.replace(/"/g, '\\"'); }

  function revealGroup(link) {
    const grp = link.closest(".tax-group");
    if (grp && grp.classList.contains("collapsed")) toggleGroup(grp.querySelector(".tax-group-head"));
  }

  function closeDoc() {
    currentKey = null;
    $("viewer-body").hidden = true;
    $("viewer-empty").hidden = false;
    $("viewer-actions").hidden = true;
    $("open-tab").hidden = true;
    $("viewer-search").disabled = true;
    document.querySelectorAll(".tax-item.active").forEach((a) => a.classList.remove("active"));
    history.replaceState(null, "", location.pathname);
    status("Closed document.");
  }

  // ---- taxonomy: open, collapse groups, tag filter --------------------------
  document.getElementById("taxonomy").addEventListener("click", (e) => {
    const head = e.target.closest(".tax-group-head");
    if (head) { toggleGroup(head); return; }
    const item = e.target.closest(".tax-item");
    if (item) { e.preventDefault(); load().then(() => openDoc(item.dataset.key)); }
  });

  function toggleGroup(head) {
    const grp = head.closest(".tax-group");
    const collapsed = grp.classList.toggle("collapsed");
    head.setAttribute("aria-expanded", collapsed ? "false" : "true");
  }

  let activeTag = null;
  document.querySelectorAll(".tag:not(.clear-tag)").forEach((tag) => {
    tag.addEventListener("click", () => {
      const sig = tag.dataset.tagtype + ":" + tag.dataset.tagvalue;
      if (activeTag === sig) { applyTag(null); } else { applyTag(tag); }
    });
  });
  const clearTagBtn = $("clear-tag");
  if (clearTagBtn) clearTagBtn.addEventListener("click", () => applyTag(null));

  function applyTag(tag) {
    document.querySelectorAll(".tag.is-active").forEach((t) => t.classList.remove("is-active"));
    if (!tag) {
      activeTag = null;
      document.querySelectorAll(".tax-item").forEach((a) => (a.closest("li").hidden = false));
      document.querySelectorAll(".tax-group").forEach((g) => (g.hidden = false));
      if (clearTagBtn) clearTagBtn.hidden = true;
      status("Cleared tag filter.");
      return;
    }
    tag.classList.add("is-active");
    activeTag = tag.dataset.tagtype + ":" + tag.dataset.tagvalue;
    const type = tag.dataset.tagtype, val = tag.dataset.tagvalue;
    document.querySelectorAll(".tax-item").forEach((a) => {
      const match = type === "contested" ? a.dataset.contested === "1" : a.dataset.maturity === val;
      a.closest("li").hidden = !match;
    });
    document.querySelectorAll(".tax-group").forEach((g) => {
      g.hidden = !g.querySelector('li:not([hidden])');
    });
    if (clearTagBtn) clearTagBtn.hidden = false;
    status(`Filtered by #${val}.`);
  }

  // ---- viewer actions: copy link, quote to chat, open full page, search -----
  $("copy-link").addEventListener("click", () => {
    if (!currentKey) return;
    const url = location.origin + location.pathname + "#" + currentKey;
    navigator.clipboard && navigator.clipboard.writeText(url);
    status("Link copied to clipboard.");
  });
  $("open-source").addEventListener("click", () => {
    if (currentKey && byKey[currentKey]) window.open(byKey[currentKey].url, "_blank");
  });
  $("close-tab").addEventListener("click", closeDoc);

  $("viewer-search").addEventListener("input", (e) => findInDoc(e.target.value));
  function findInDoc(q) {
    const body = $("viewer-body");
    body.querySelectorAll("mark.find").forEach((m) => {
      m.replaceWith(document.createTextNode(m.textContent));
    });
    body.normalize();
    q = (q || "").trim();
    if (q.length < 2) return;
    const re = new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
    const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
    const hits = [];
    let n;
    while ((n = walker.nextNode())) { if (re.test(n.nodeValue)) hits.push(n); }
    let first = null;
    hits.forEach((node) => {
      const span = document.createElement("span");
      span.innerHTML = esc(node.nodeValue).replace(re, (m) => `<mark class="find">${esc(m)}</mark>`);
      const frag = document.createDocumentFragment();
      while (span.firstChild) frag.appendChild(span.firstChild);
      node.replaceWith(frag);
    });
    first = body.querySelector("mark.find");
    if (first) first.scrollIntoView({ block: "center" });
    status(`${body.querySelectorAll("mark.find").length} match(es) for “${q}”.`);
  }

  // ---- chat (Ask) -----------------------------------------------------------
  const inlineMd = (s) => {
    s = esc(s);
    s = s.replace(/\[\[([^\]\|]+)(?:\|([^\]]*))?\]\]/g, (m, k, lab) => {
      const e = byKey[k];
      const text = (lab && lab.trim()) || (e && e.title) || k.split("/").pop().replace(/-/g, " ");
      return e ? `<a class="cite" data-key="${esc(k)}">${esc(text)}</a>` : esc(text);
    });
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m, t, u) => `<a href="${esc(u)}" target="_blank">${esc(t)}</a>`);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    return s;
  };
  function renderMd(md) {
    let html = "", list = null;
    const close = () => { if (list) { html += `</${list}>`; list = null; } };
    for (const raw of (md || "").split("\n")) {
      const line = raw.replace(/\s+$/, ""); let m;
      if (!line.trim()) { close(); continue; }
      if ((m = line.match(/^(#{1,6})\s+(.*)$/))) { close(); const l = Math.min(m[1].length + 1, 6); html += `<h${l}>${inlineMd(m[2])}</h${l}>`; }
      else if ((m = line.match(/^\s*\d+\.\s+(.*)$/))) { if (list !== "ol") { close(); html += "<ol>"; list = "ol"; } html += `<li>${inlineMd(m[1])}</li>`; }
      else if ((m = line.match(/^\s*[-*]\s+(.*)$/))) { if (list !== "ul") { close(); html += "<ul>"; list = "ul"; } html += `<li>${inlineMd(m[1])}</li>`; }
      else { close(); html += `<p>${inlineMd(line)}</p>`; }
    }
    close();
    return html;
  }

  const chatLog = $("chat-log");
  function addMsg(cls, html) {
    const intro = $("chat-intro"); if (intro) intro.remove();
    const div = document.createElement("div");
    div.className = "msg " + cls;
    div.innerHTML = html;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
    return div;
  }

  async function ask(q) {
    q = (q || "").trim();
    if (!q) return;
    await load();
    addMsg("user", `<div class="bubble">${esc(q)}</div>`);
    const t0 = Date.now();
    const wait = addMsg("bot", `<div class="bubble"><span class="asking"><span class="spin">◌</span> Reading ${totalCount} docs… · 0s</span></div>`);
    const span = wait.querySelector(".asking");
    const timer = setInterval(() => {
      if (span) span.innerHTML = `<span class="spin">◌</span> Reading ${totalCount} docs… · ${Math.round((Date.now() - t0) / 1000)}s`;
    }, 1000);
    try {
      const res = await fetch("api/query", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      clearInterval(timer);
      if (!res.ok || data.error) {
        wait.innerHTML = `<div class="bubble error">Query failed: ${esc(data.error || res.status)}</div>`;
        return;
      }
      const cited = (data.cited && data.cited.length)
        ? `<div class="cited">Sources: ${data.cited.map((k) => {
            const e = byKey[k];
            return e ? `<a class="cite" data-key="${esc(k)}">${esc(e.title)}</a>` : esc(k);
          }).join(" · ")}</div>`
        : noAnswerCTA(q);
      wait.innerHTML = `<div class="bubble"><div class="answer">${renderMd(data.answer)}</div>${cited}</div>`;
      status("Answer ready.");
    } catch (err) {
      clearInterval(timer);
      wait.innerHTML = `<div class="bubble error">Could not reach the query endpoint — it only runs on the deployed site.</div>`;
    }
  }

  function noAnswerCTA(q) {
    const lq = q.toLowerCase();
    const hit = (plays || []).map((p) => {
      let s = 0;
      if ((p.title || "").toLowerCase().includes(lq)) s = 3;
      else if ((p.why || "").toLowerCase().includes(lq)) s = 2;
      else if ((p.body || "").toLowerCase().includes(lq)) s = 1;
      return [s, p];
    }).filter((x) => x[0] > 0).sort((a, b) => b[0] - a[0])[0];
    const closest = hit
      ? `<div class="closest">Closest topic ▸ <a class="cite" data-key="${esc(hit[1].key)}">${esc(hit[1].title)}</a></div>` : "";
    const cmd = "playmaker ingest &lt;url&gt;";
    return `${closest}<div class="ingest"><span>Not in the vault — add a source:</span>` +
      `<code>${cmd}</code><button class="copy-cmd" data-copy="playmaker ingest <url>">copy</button></div>`;
  }

  // chat delegated clicks: citations, examples, copy-cmd
  $("chat-log").addEventListener("click", (e) => {
    const cite = e.target.closest(".cite");
    if (cite) { load().then(() => openDoc(cite.dataset.key, { cite: true })); return; }
    const ex = e.target.closest(".chat-example");
    if (ex) { $("chat-input").value = ex.dataset.q; ask(ex.dataset.q); return; }
    const cc = e.target.closest(".copy-cmd");
    if (cc) { navigator.clipboard && navigator.clipboard.writeText(cc.dataset.copy); cc.textContent = "copied"; setTimeout(() => (cc.textContent = "copy"), 1500); }
  });

  const chatForm = $("chat-form"), chatInput = $("chat-input");
  chatForm.addEventListener("submit", (e) => { e.preventDefault(); const q = chatInput.value; chatInput.value = ""; autoGrow(chatInput); ask(q); });
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); chatForm.requestSubmit(); }
  });
  chatInput.addEventListener("input", () => autoGrow(chatInput));
  function autoGrow(t) { t.style.height = "auto"; t.style.height = Math.min(t.scrollHeight, 160) + "px"; }

  // ---- viewer body internal links open in-pane ------------------------------
  $("viewer-body").addEventListener("click", (e) => {
    const a = e.target.closest("a");
    if (!a) return;
    const href = a.getAttribute("href") || "";
    if (byUrl[href]) { e.preventDefault(); openDoc(byUrl[href].key); }
  });

  // ---- panes: collapse + mobile toggles -------------------------------------
  $("collapse-left").addEventListener("click", () => {
    const c = app.classList.toggle("left-collapsed");
    status(c ? "Taxonomy collapsed." : "Taxonomy expanded.");
  });
  $("toggle-left").addEventListener("click", () => $("pane-left").classList.toggle("open"));
  $("toggle-right").addEventListener("click", () => $("pane-right").classList.toggle("open"));

  // ---- init: deep link -------------------------------------------------------
  load().then(() => {
    const key = decodeURIComponent((location.hash || "").replace(/^#/, ""));
    if (key && byKey[key]) openDoc(key, { cite: false });
  });
})();
