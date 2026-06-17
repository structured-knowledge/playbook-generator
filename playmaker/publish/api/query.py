"""Serverless query function: answer a question from the published snapshot.

Self-contained (stdlib + certifi only) — the DEPLOYED function does not import
playmaker. It reads ``plays.json`` from the bundle, sends the playbook to the
gateway, and returns a grounded, play-citing answer (spec: web-query).

Retrieval is the whole playbook for a small corpus (design.md D-B/D-C); swap
``select_plays`` for brief-routing / embeddings past ~100 plays — nothing else
in this file changes.

Env: GATEWAY_BASE, GATEWAY_KEY, GATEWAY_MODEL.
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import re
import ssl
import urllib.error
import urllib.request
from pathlib import Path

MAX_BODY_CHARS = 1200          # per-play context budget (design.md D-C)
MAX_TOKENS = 8192              # safe ceiling; headroom if a reasoning model is set
_KEY_RE = re.compile(r"\[\[([^\]\|]+)(?:\|[^\]]*)?\]\]")

PROMPT = """You answer strictly from the playbook below. Rules:

1. Use ONLY the plays provided — no outside knowledge.
2. Give a concise, actionable answer.
3. Cite each play you draw on inline as its key in double brackets, exactly as \
shown, e.g. [[concepts/example]].
4. Cite a play ONLY if it DIRECTLY addresses the question. Do not stretch a \
loosely-related play to fit; a play on a different topic is not an answer.
5. If no play directly addresses the question, do NOT improvise or cite a \
tangential play. Say plainly that the playbook does not cover it and cite \
nothing. You may name the closest related topic in one sentence, without \
presenting it as the answer.

QUESTION: {question}

PLAYS:
{plays}
"""


def _ssl_ctx() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def load_plays(path: str | None = None) -> list[dict]:
    """Find and load ``plays.json`` from the bundle (or an explicit/env path)."""
    here = Path(__file__).resolve()
    candidates = [
        Path(path) if path else None,
        Path(os.environ["PLAYS_JSON"]) if os.environ.get("PLAYS_JSON") else None,
        here.parent.parent / "data" / "plays.json",   # <root>/data next to api/
        Path.cwd() / "data" / "plays.json",
    ]
    for c in candidates:
        if c and c.is_file():
            return json.loads(c.read_text(encoding="utf-8")).get("plays", [])
    raise FileNotFoundError("plays.json not found in the bundle")


def select_plays(question: str, plays: list[dict]) -> list[dict]:
    """The retrieval seam. v1: whole playbook (validated for small corpora).
    Replace with brief-routing / embeddings when the corpus outgrows context."""
    return plays


def build_prompt(question: str, plays: list[dict]) -> str:
    ctx = "\n\n".join(
        f"### [[{p['key']}]] — {p.get('title', '')}\n"
        f"{(p.get('body') or '').strip()[:MAX_BODY_CHARS]}"
        for p in plays
    )
    return PROMPT.format(question=question, plays=ctx)


def call_gateway(prompt: str) -> str:
    base = os.environ["GATEWAY_BASE"].rstrip("/")
    key = os.environ["GATEWAY_KEY"]
    model = os.environ.get("GATEWAY_MODEL", "gemini-3.1-flash-lite")
    raw_model = model.split("/", 1)[1] if "/" in model else model
    payload = json.dumps(
        {
            "model": raw_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": MAX_TOKENS,
        }
    ).encode()
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "curl/8.4.0",   # gateway WAF workaround (spike D-A)
        },
    )
    with urllib.request.urlopen(req, timeout=120, context=_ssl_ctx()) as resp:
        body = json.loads(resp.read())
    return (body["choices"][0]["message"]["content"] or "").strip()


def answer(question: str, plays: list[dict]) -> dict:
    """Answer ``question`` from ``plays``; return the text + the keys it cited."""
    selected = select_plays(question, plays)
    text = call_gateway(build_prompt(question, selected))
    valid = {p["key"] for p in plays}
    cited = [k for k in dict.fromkeys(_KEY_RE.findall(text)) if k in valid]
    return {"answer": text, "cited": cited, "play_count": len(selected)}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - Vercel's expected method name
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")
            question = (data.get("question") or "").strip()
            if not question:
                return self._send(400, {"error": "missing 'question'"})
            self._send(200, answer(question, load_plays()))
        except urllib.error.HTTPError as e:
            self._send(502, {"error": f"gateway HTTP {e.code}",
                             "body": e.read().decode("utf-8", "replace")[:500]})
        except Exception as e:  # noqa: BLE001 - report any failure as JSON
            self._send(500, {"error": repr(e)})

    def _send(self, code: int, obj: dict):
        out = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)
