# Platform Auth Gating + Usage Visibility — Spec v1 (for sign-off)

**Author:** User Manager Agent (owns mobius-user / @mobius/auth / identity)
**Status:** UX APPROVED by Ananth (mockup, 2026-07-22) — circulating for sign-off. Build sequence: signed → build. NO code until impacted agents + platform architects ratify.
**Date:** 2026-07-22

> **Ratified UX (Ananth-approved visual):** the sign-in flow + Users&Usage console layout are
> locked to the mockup at https://claude.ai/code/artifact/8f10d500-4200-4b35-827f-b35a5f9515b8
> — §6 text conforms to it, not the reverse. Sign-offs are against that visual; the build
> reproduces it. Platform Architect (UX seat) owns visual/design-system conformance on top.

---

## 1. Why now

Mobius is going from one public entry point (chat) to several. As Ananth shares the
story broadly, **credentialing, appeals, and organization surfaces will be exposed to
external people** (partners, prospects). Chat stops being the only front door. Four
drivers, all in play:

- **(a) Compliance** — no unauthenticated request should reach PHI-adjacent data.
- **(b) Accountability** — every surface should know *who* you are (audit + attestation; the
  PHI override + Team&Access lifecycle structurally require a real acting user).
- **(c) Go-to-market** — no anonymous access; everyone signs in.
- **(d) Usage visibility** — "keep tabs on who is using us," across every surface, not just chat.

## 2. The reframe (what this spec is really about)

"Gate every agent" is the wrong unit — **browser-facing origins** get authenticated, not
agents. Backend services (RAG, payor, task-manager) are reached via chat's authenticated
proxy and stay gated service-to-service by internal key — they never face a browser.

Two coupled deliverables:

- **Single front door.** One identity across every surface (mobius-user issues, everything
  validates the same signed token, `@mobius/auth` is the drop-in). A user signs in once;
  every Mobius origin recognizes them. This is SSO across our own properties — most plumbing
  already exists (chat proved it). **Anti-goal: five separate logins = five disconnected
  identities = no coherent "who is this."**
- **Usage ledger.** A login gate answers "can you get in," NOT "who used what, how much."
  Each gated surface emits an **access beacon** `(user_id, surface, org_slug, ts)` to
  mobius-user after it validates the token. This attribution spine is what makes the
  dashboard real.

Headline: **make mobius-user the single front door AND the usage ledger.** Gates fall out of
the front-door work; the dashboard is a read over the ledger.

## 3. Surface taxonomy (who's impacted)

| Surface | Owner | Browser-facing? | Auth today | Action |
|---|---|---|---|---|
| Chat | Chat Agent | yes | GATED | reference impl; add beacon |
| Mobius Story deck | Strategy Agent | yes | open | gate + beacon (FIRST per Ananth) |
| Credentialing / Providr | Roster & Credentialing + ORG | yes | open | gate + beacon (external soon) |
| Appeals | Appeals Agent | yes | open | gate + beacon (external soon) |
| Organization / Team&Access | ORG Agent | yes | open | gate + beacon (external soon) |
| Vault page | Vault Agent | yes | token-reuse | confirm gate + beacon |
| Landing | Landing Agent | yes | public by design | stays public (pre-auth funnel) |
| RAG / payor / task-mgr | (services) | no | internal-key | unchanged |

## 4. Architecture (single front door)

- **Issuer:** mobius-user, one shared `JWT_SECRET`, HS256, `sub` = canonical user_id. Unchanged.
- **Relying party per surface:** adopt `@mobius/auth` (AuthModal + AuthService + PreferencesModal),
  proxy `/api/v1/auth/*` to mobius-user (the chat pattern), gate the app shell on a valid token.
- **Token sharing across origins — RESOLVED (Ananth, 2026-07-22).** Surfaces are SEPARATE Cloud
  Run origins (mobius-story-ui-…, mobius-chat-…, mobius-provider-roster-…, each its own host under
  `a.run.app`). `a.run.app` is on the Public Suffix List → cross-service cookies are BLOCKED;
  localStorage is per-origin. So no free shared session. **Decision: Path 1 + chat hand-off.**
  **DECISION UPDATED 2026-07-22 → HUB-BASED SIGN-IN (chat is the hub).** Rationale: Google is the
  primary login path, and Google requires each JS origin be registered in the OAuth client
  (Console-only, error-prone, fails as `origin_mismatch` in front of customers). Registering N
  surface origins is a treadmill. Instead: **Google sign-in happens on exactly ONE origin — chat,
  which is already OAuth-registered.** Every other surface redirects to chat to authenticate, then
  gets its session via a hand-off code. Register ZERO new OAuth origins, ever.

  **The flow (every surface, identical):**
  1. Land on surface. `#h=<code>` in the URL? → redeem (`POST /api/v1/auth/handoff/redeem`) →
     session → strip fragment → done. (This is also the chat→surface click path.)
  2. No code, no stored token → redirect to chat's sign-in with a return pointer:
     `https://mobius-chat-…/signin?return=<surface-url>`.
  3. Chat: already signed in → mint hand-off, redirect back to `return` with `#h=<code>`.
     Not signed in → show Google sign-in (works on chat's origin) → then mint + redirect back.
  4. Back on the surface with `#h=` → redeem → session. User is in, on the page they started on.

  **Endpoints (mine, LIVE):** `POST /api/v1/auth/handoff/mint` (bearer → 60s single-use code) +
  `POST /api/v1/auth/handoff/redeem` (code → session). Reuse auth_token purpose='handoff'.
  **Chat owns (the hub):** a `/signin?return=` page that ensures a session (Google/email) then
  mints + redirects. **Open-redirect guard:** chat validates `return` against an allow-list of
  known Mobius surface origins — never bounces to an arbitrary URL.
  **Each surface owns:** redeem-on-load, and "no session → redirect to chat/signin?return=self".
  No local Google button, no @mobius/auth modal per surface — LESS work than Path 1.
  **Deferred:** custom domains (`*.mobius.com` cookie SSO) when GTM moves off run.app.
- **Acting-user propagation (Tier-2, urgent on public exposure):** the human's identity must
  reach the *skills*, not just the page. Providr still hardcodes `uploaded_by='admin'`; external
  users on PHI-adjacent credentialing/appeals without a real acting user is a compliance blocker,
  not backlog. Skills receive the platform JWT `sub` (chat's whoami pattern).

## 5. Usage ledger (data model — DB architect gate)

New table `user_access_event` in mobius_user DB (append-only):

```
access_event_id  uuid pk
user_id          uuid fk app_user (nullable — anonymous pre-auth landing hits)
surface          text        -- 'chat' | 'story' | 'credentialing' | 'appeals' | 'org' | 'vault'
org_slug         text null   -- active org context if known
action           text null   -- optional coarse action ('view' | 'run_check' | ...), NEVER raw content
occurred_at      timestamptz default now()
```
Indexes: `(user_id, occurred_at)`, `(surface, occurred_at)`, `(org_slug, occurred_at)`.
PHI-in-logs standard applies: **categories/counts only, never raw query/message/document text.**
Retention + BQ replica for marts = DB architect's call (§8).

Ingest: `POST /api/v1/users/access-beacon` (bearer or internal-key), fire-and-forget from each
surface post-auth. Fail-open (a dropped beacon never blocks the user).

## 6. UX design + workflow

### 6.1 Per-surface sign-in (the recipe, identical everywhere) — HUB-BASED
1. On load: `#h=<code>` in URL? → `POST /api/v1/auth/handoff/redeem` → store token, strip fragment.
   Else valid stored token? → use it. Else → redirect to `https://mobius-chat-…/signin?return=<self>`.
2. (Sign-in itself happens at chat — Google/email — then chat hands back. Surface shows no login UI.)
3. Signed in → "Signed in as {name}" (reads greeting_name); sign-out clears local token + redirects to chat.
4. Every `/api/*` call carries the token (apiFetch wrapper — bare fetch = silent anonymous).
5. Post-auth, fire the access beacon once per session-load.
6. Invited-user path (set-password page, 4 certified states) unchanged — activation still one-per-account.
NB: Google's no-auto-activate policy is enforced at chat (the one sign-in point), not re-implemented per surface.

### 6.2 Users & Usage Console (the dashboard Ananth wants)
Admin-gated (allowlist today; capability later). Extends the existing `/admin` console. Screens:

- **Users list** — searchable; columns: name, email, org(s), status (active/invited/disabled),
  last-seen, granted capabilities. Filters: org, status, surface-used.
- **User detail** — profile, org memberships (active + pending), roles, capabilities, preference
  snapshot, recent access events (which surfaces, when), lifecycle history (from audit trail).
- **Usage panel** — signups trend, logins over time, per-surface usage bars, per-org rollup
  (members, active-last-7d). Lights up progressively as surfaces start beaconing; shows
  logins/signups from day one.
- **Org rollup** — per org: member count, invited/active split, last activity.

Workflow: Ananth (and org admins later) open the console → see who's using what → drill into a
user or org → act (grant/revoke capability, deactivate) via the existing lifecycle endpoints.

Design system: mobius-design tokens, `var(--mobius-*)`, kind=violet; **Platform Architects (UX
seat) owns the visual/experience sign-off** — this spec defers presentation to them.

## 7. Build sequence (POST sign-off only)

- **T0** settle token-sharing across origins (§8 Q2) — blocks everything public.
- **T1** usage ledger: migration 011 + beacon endpoint + dashboard skeleton (logins/signups).
- **T2** per-surface gating, in **exposure order** (Story first, then credentialing/appeals/org),
  each owner executes the §6.1 recipe against their surface + adds the beacon.
- **T3** acting-user propagation into skills (Tier-2) — with PHI agent for the classifier-gated paths.
- **T4** dashboard usage panel fills in as beacons land; org-admin access + capability-gated admin.

## 8. Open questions

1. **First surface + timeline** — RESOLVED: **Story, public in ~1 week** (Ananth 2026-07-22). Sets
   the whole clock: my hand-off endpoints + migration 011 + beacon + Story gating must be ready
   this week. Gating proceeds in exposure order after Story.
2. **Origin topology** — RESOLVED (§4): separate origins → Path 1 + chat hand-off.
3. **Admin console access model** — RESOLVED: **v1 = internal Mobius employees via email allowlist**
   (reuse the existing `MOBIUS_USER_ADMIN_EMAILS` gate the /admin console already uses — zero new
   build). Console shows the GLOBAL internal view (all users/orgs/usage), NOT org-scoped. The
   `platform_admin` capability + per-org admin views come LATER, when organizations + agents onboard
   as their own admins (Ananth: "over time we'll work admin auth as we bring on org entry + agents").
   Resolves old Q3 + Q4.
4. **DB architect:** `user_access_event` retention + BQ replica for marts — own it or defer? (still open)
5. **Anonymous landing** — beacon pre-auth landing hits (user_id null) for funnel, or only post-auth?
   (privacy call — defaulting to post-auth only unless told otherwise.)

## 9. Sign-off matrix

| Signer | Signs off on |
|---|---|
| **Platform Architect — UX seat** | dashboard UX + per-surface sign-in experience, design-system conformance |
| **Platform Architect — DB seat** | `user_access_event` schema, retention, BQ replica, migration 011 |
| **Chat Agent** | reference-impl alignment; beacon add; **mint hand-off code + append `#h=` to cross-surface links** |
| **Strategy Agent** (Mobius Story) | gating + beacon on the deck (FIRST surface) |
| **Roster & Credentialing Agent** | credentialing surface gating + acting-user propagation |
| **Appeals Agent** | appeals surface gating |
| **ORG Agent** | org/Team&Access gating; Providr `uploaded_by` → real acting user |
| **Vault Agent** | vault page gate + beacon |
| **PHI Classifier Agent** | acting-user propagation on PHI-adjacent paths |

Build starts only when the UX + DB architect seats ratify §5/§6 and each impacted surface owner
acks their row.
