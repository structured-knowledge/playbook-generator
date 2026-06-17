// Edge middleware: a shared-password gate over the whole site AND /api/query
// (spec: web-gating-deploy). Pure Web-standard APIs — no npm dependency.
//
// Set in the Vercel project env:
//   GATE_PASSWORD  the shared password users type at /login
//   GATE_SECRET    a random string used to sign the session cookie
//
// Static assets (/static/*) are left open so the /login page can style itself;
// all content (pages, data/plays.json) and the API are gated.

export const config = { matcher: ["/((?!static/|favicon).*)"] };

const COOKIE = "pmgate";

async function token(secret) {
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode("authenticated"));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export default async function middleware(req) {
  const url = new URL(req.url);
  const password = process.env.GATE_PASSWORD || "";
  const secret = process.env.GATE_SECRET || "";
  const expected = await token(secret);

  // Login submission.
  if (url.pathname === "/login.html" && req.method === "POST") {
    const form = await req.formData();
    if (password && form.get("password") === password) {
      const res = new Response(null, { status: 303, headers: { Location: "/" } });
      res.headers.append(
        "Set-Cookie",
        `${COOKIE}=${expected}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=2592000`,
      );
      return res;
    }
    return new Response(null, { status: 303, headers: { Location: "/login.html?e=1" } });
  }

  // The login page itself is always reachable.
  if (url.pathname === "/login" || url.pathname === "/login.html") return;

  // Valid session?
  const m = (req.headers.get("cookie") || "").match(new RegExp(`${COOKIE}=([a-f0-9]+)`));
  if (m && m[1] === expected) return;

  // Blocked: API → 401 JSON; everything else → the login page.
  if (url.pathname.startsWith("/api/")) {
    return new Response(JSON.stringify({ error: "unauthorized" }), {
      status: 401, headers: { "Content-Type": "application/json" },
    });
  }
  return Response.redirect(new URL("/login.html", req.url), 307);
}
