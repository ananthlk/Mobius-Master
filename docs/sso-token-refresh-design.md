# Shared SSO token refresh — RAG, Lexicon, and every embedded tool

Status: DESIGN for review · Date: 2026-07-02 · Owner: platform/auth

## 1. Problem (root cause)

Platform tools (mobius-rag, mobius-lexicon-maintenance, …) are launched from the
Mobius platform (chat/OS) as **iframe-embedded SPAs**. Auth today:

1. The launcher appends the caller's platform JWT to the tool URL as `#t=<jwt>`.
2. The tool captures it once (`platformToken.ts:capturePlatformToken`), stores it in
   `sessionStorage`, strips the hash, and attaches it as `Authorization: Bearer` to
   every API call (`installAuthFetch` shim).
3. The tool backend gates `/admin/*` on that JWT (or an `X-Admin-Key`).

**The gap:** the JWT is **short-lived (~1h) and never refreshed.** It's captured *once*
at launch. When it expires:

- every `/admin/*` call → **401**
- the SPA reads back empty → **history blanks, live status vanishes, actions fail**

The data is never lost (verified: DB rows intact, endpoints return correctly *with a
valid token*). It is purely a **missing token-refresh** in the shared SSO plumbing.

**Why it surfaces in RAG/Lexicon and "nowhere else":** RAG's nightly pipeline runs
~1.5h — far longer than the token TTL — so the token reliably dies mid-use. Quick tools
finish inside the TTL. Other dev services often run *open* (`ENV=dev`, no `ADMIN_API_KEY`
→ middleware bypasses auth), so they never exercise the token path at all. RAG's dev
deploy enforces it (`ADMIN_API_KEY` set; `ENV=staging`), which is why it hits the wall.

Note: `ENV=staging` on the dev service is a contributor (it makes the service "hosted"
and gated my dev-mint), but the enforcement itself comes from `ADMIN_API_KEY` being set —
auth is required regardless of `ENV` once the key is present.

## 2. Principle

Do **not** remove auth (Phase 1 deliberately put these tools behind the platform login).
**Add refresh, once, in the shared client layer** every tool already uses, backed by a
token source that works in both dev and prod.

## 3. Design

### 3.1 Client (shared `platformToken.ts` — used by RAG + Lexicon)

A single `getFreshToken()` the fetch shim calls on **401** (reactive) and on a **timer
before expiry** (proactive, decode `exp`, refresh at ~T-5min):

```
getFreshToken():
  1. prod path → request a token from the parent via postMessage (§3.2), 3s timeout
  2. dev path  → GET {VITE_DEV_MINT_URL} (/dev/mint-token proxy, §3.3)
  first to resolve wins; store in sessionStorage; return it
```

`installAuthFetch` (already re-mints on `/admin/*` 401) calls `getFreshToken()` instead
of the dev-only mint, so the *same* recovery works in both envs. No per-call-site changes.

### 3.2 Prod token source — parent `postMessage` (recommended)

Because tools are **cross-origin iframes**, `postMessage` to the parent is the cleanest
refresh (no CORS, no cross-origin cookies). The parent (platform) holds the live session
and can mint a fresh short-lived JWT on demand.

**Contract (both sides validate `event.origin` against an allowlist):**

| Direction | message | when |
|---|---|---|
| tool → parent | `{ type: 'mobius:auth:request', tool: 'rag' }` | on 401 / proactive refresh |
| parent → tool | `{ type: 'mobius:auth:token', token: '<jwt>' }` | reply to a request |
| parent → tool | `{ type: 'mobius:auth:token', token, push: true }` | parent-initiated pre-expiry push |

- Parent mints from the **logged-in platform session** (server-side), scoped to the tool.
- Short TTL (e.g. 15–60m); the push keeps long sessions alive without user action.
- Origin allowlist on **both** ends (parent checks the tool origin; tool checks the
  parent origin) — never accept a token from an unknown origin.

**Alternative (if not iframed):** a session-cookie-authenticated `POST {platform}/auth/token`
with `credentials: 'include'` + CORS allowing the tool origin. Works, but needs
`SameSite=None; Secure` cookies and per-origin CORS — more moving parts than postMessage.

### 3.3 Dev token source — mint proxy (already built)

`GET /dev/mint-token` on each tool, gated by an explicit `ALLOW_DEV_MINT=1` env (NOT on
`ENV`, since our dev service is `ENV=staging`). It server-side calls chat's open
`mint-dev-token` (same-origin from the browser → no CORS). Off (404) unless the flag is
set; prod never sets it.

## 4. Where the shared code lives

`platformToken.ts` is currently **duplicated** in each tool's frontend. To truly "solve
once": promote it to a shared package (e.g. `@mobius/platform-auth`) imported by
mobius-rag and mobius-lexicon-maintenance frontends. Interim: keep the two copies
byte-identical and update together.

## 5. Work items

- [ ] **Client (shared):** add `getFreshToken()` (postMessage + dev-mint race), proactive
      pre-expiry refresh timer, wire `installAuthFetch` 401-retry to it.
- [ ] **Platform (chat/OS):** parent-side postMessage handler that mints a fresh JWT from
      the session + proactive push; origin allowlist.
- [ ] **Dev (done for RAG):** `ALLOW_DEV_MINT` gate + `/dev/mint-token` proxy + shim
      re-mint. Replicate in Lexicon.
- [ ] **Packaging:** extract `platformToken.ts` into a shared module used by both tools.
- [ ] **Security review:** origin allowlists, token TTL, no token in logs/URL post-capture.

## 6. Immediate vs. permanent

- **Immediate (dev, this session):** `ALLOW_DEV_MINT` + `/dev/mint-token` + shim re-mint
  → RAG dev stops blanking on token expiry.
- **Permanent (cross-tool):** §3.1 + §3.2 implemented once → RAG, Lexicon, and any future
  embedded tool inherit refresh with zero per-tool auth code.
