/* global process */
/**
 * Sign-in gate (Vercel Routing Middleware): runs in front of every request, pages and data files alike.
 *
 * Anyone with an @egain.com email address and the shared password gets in. The password lives only in the
 * SITE_PASSWORD environment variable in Vercel, never in the code. A signed session cookie keeps people signed in
 * for 7 days; changing the password signs everyone out. If SITE_PASSWORD is missing, nothing is served (fails closed).
 *
 * Note: the email address is not verified; it identifies the visitor, the password is the real lock.
 * A production version would use eGain's SSO instead.
 */

export const config = { matcher: "/:path*" };

const COOKIE = "vi_session";
const MAX_AGE = 60 * 60 * 24 * 7; // 7 days
const EMAIL_RE = /^[^\s@]+@egain\.com$/i;
const enc = new TextEncoder();

const b64url = (bytes) =>
  btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

async function hmac(secret, msg) {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return b64url(await crypto.subtle.sign("HMAC", key, enc.encode(msg)));
}

const sha256 = async (s) => b64url(await crypto.subtle.digest("SHA-256", enc.encode(s)));

function sameString(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function passwordOk(given, secret) {
  return sameString(await sha256(given), await sha256(secret)); // equal-length compare, no timing hint
}

async function makeToken(email, secret) {
  const payload = `${b64url(enc.encode(email))}.${Math.floor(Date.now() / 1000) + MAX_AGE}`;
  return `${payload}.${await hmac(secret, payload)}`;
}

async function sessionOk(request, secret) {
  const cookie = request.headers.get("cookie") || "";
  const m = cookie.match(new RegExp(`(?:^|;\\s*)${COOKIE}=([^;]+)`));
  if (!m) return false;
  const [email, exp, sig] = m[1].split(".");
  if (!email || !exp || !sig || Number(exp) < Date.now() / 1000) return false;
  return sameString(sig, await hmac(secret, `${email}.${exp}`));
}

/** Only same-site paths, so the login form can't be used to bounce people to another website. */
function safeNext(v) {
  return typeof v === "string" && v.startsWith("/") && !v.startsWith("//") && !v.startsWith("/\\") ? v : "/";
}

const NO_STORE = { "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow" };

function redirect(location, extra = {}) {
  return new Response(null, { status: 303, headers: { Location: location, ...NO_STORE, ...extra } });
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

function loginPage({ error = "", email = "", next = "/" } = {}, status = 200) {
  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Sign in · Visitor Insights</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='16' fill='%23b91d8f'/><path d='M8 21l5-6 4 4 7-9' stroke='white' stroke-width='3' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  :root { color-scheme: light; --bg:#f9f9f9; --surface:#fff; --border:#e6e6e6; --text:#000; --text-2:#4a4a4a; --text-3:#858585;
          --brand:#b91d8f; --accent:#1a73c8; --accent-soft:#eaf3fc; --on-accent:#fff; --hot:#b3261e; --hot-bg:#fdecea; }
  @media (prefers-color-scheme: dark) { :root { color-scheme: dark; --bg:#121212; --surface:#1b1b1b; --border:#333; --text:#f4f4f4;
          --text-2:#c4c4c4; --text-3:#8f8f8f; --brand:#e070c1; --accent:#5aa9e6; --accent-soft:#14273a; --on-accent:#0b1a2a; --hot:#f08a80; --hot-bg:#3a1f1c; } }
  * { box-sizing: border-box; }
  body { margin:0; min-height:100vh; display:grid; place-items:center; padding:24px 16px; background:var(--bg); color:var(--text);
         font: 15px/1.5 "Open Sans", "Helvetica Neue", Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; }
  .card { width:100%; max-width:400px; background:var(--surface); border:1px solid var(--border); border-top:4px solid var(--brand);
          border-radius:12px; padding:32px 28px; }
  .brand { display:flex; align-items:center; gap:10px; font-family:"Helvetica Neue", Helvetica, Arial, sans-serif; font-weight:700; font-size:17px; }
  .mark { width:28px; height:28px; border-radius:50%; background:var(--brand); display:grid; place-items:center; }
  h1 { font-family:"Helvetica Neue", Helvetica, Arial, sans-serif; font-weight:500; font-size:24px; margin:24px 0 4px; }
  p.sub { margin:0 0 22px; color:var(--text-2); }
  label { display:block; font-weight:600; font-size:13px; margin:14px 0 6px; }
  input { width:100%; height:42px; padding:0 14px; border:1px solid var(--border); border-radius:999px; background:var(--surface);
          color:var(--text); font:inherit; outline:none; }
  input:focus { border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft); }
  button { width:100%; height:44px; margin-top:22px; border:0; border-radius:999px; background:var(--accent); color:var(--on-accent);
           font:inherit; font-weight:700; cursor:pointer; }
  button:hover { filter:brightness(.93); }
  .error { margin:0 0 6px; padding:10px 12px; border-radius:8px; background:var(--hot-bg); color:var(--hot); font-size:14px; }
  .foot { margin:20px 0 0; font-size:12px; color:var(--text-3); }
</style>
</head>
<body>
<main class="card">
  <div class="brand"><span class="mark"><svg width="16" height="16" viewBox="0 0 32 32" aria-hidden="true"><path d="M6 22l6-7 5 5 9-11" stroke="white" stroke-width="3.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg></span>Visitor Insights</div>
  <h1>Sign in</h1>
  <p class="sub">For eGain staff. Use your eGain email address and the access password you were given.</p>
  ${error ? `<p class="error" role="alert">${esc(error)}</p>` : ""}
  <form method="post" action="/login">
    <input type="hidden" name="next" value="${esc(next)}">
    <label for="email">eGain email</label>
    <input id="email" name="email" type="email" autocomplete="email" placeholder="name@egain.com" value="${esc(email)}" required ${email ? "" : "autofocus"}>
    <label for="password">Password</label>
    <input id="password" name="password" type="password" autocomplete="current-password" required ${email ? "autofocus" : ""}>
    <button type="submit">Sign in</button>
  </form>
  <p class="foot">Prototype built for eGain sales. Company-level visitor data; access is restricted.</p>
</main>
</body>
</html>`;
  return new Response(html, { status, headers: { "Content-Type": "text/html; charset=utf-8", ...NO_STORE } });
}

export default async function middleware(request) {
  const url = new URL(request.url);
  const secret = process.env.SITE_PASSWORD;
  if (!secret) {
    return new Response("Sign-in is not configured yet.", { status: 503, headers: { "Content-Type": "text/plain", ...NO_STORE } });
  }

  if (url.pathname === "/logout") {
    return redirect("/login", { "Set-Cookie": `${COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0` });
  }

  if (url.pathname === "/login") {
    if (request.method === "POST") {
      const form = await request.formData();
      const email = String(form.get("email") || "").trim().toLowerCase();
      const next = safeNext(form.get("next"));
      if (!EMAIL_RE.test(email)) return loginPage({ error: "Use your @egain.com email address.", email, next }, 401);
      if (!(await passwordOk(String(form.get("password") || ""), secret))) {
        return loginPage({ error: "That password isn't right.", email, next }, 401);
      }
      const token = await makeToken(email, secret);
      return redirect(next, { "Set-Cookie": `${COOKIE}=${token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${MAX_AGE}` });
    }
    if (await sessionOk(request, secret)) return redirect("/");
    return loginPage({ next: safeNext(url.searchParams.get("next")) });
  }

  if (await sessionOk(request, secret)) return; // signed in: serve the site as normal

  // not signed in: data and code files get a plain 401, pages go to the sign-in form
  if (url.pathname.startsWith("/data/") || url.pathname.startsWith("/assets/")) {
    return new Response("Sign-in required.", { status: 401, headers: { "Content-Type": "text/plain", ...NO_STORE } });
  }
  return redirect(`/login?next=${encodeURIComponent(url.pathname + url.search)}`);
}
