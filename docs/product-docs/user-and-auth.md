# User & Auth
> Sign in to Mobius, manage your account and preferences, and let every Mobius app know who you are.

## Purpose

User & Auth is Mobius's shared identity layer. It lets people create an account, sign in (with email/password or Google), and stay signed in across Mobius surfaces — the chat app, the browser extension, and other modules. One account works everywhere: sign in once and every Mobius app recognizes you, greets you by name, and applies your preferences.

It also stores who you are and how you like to work: your display and preferred name, timezone, the activities you focus on (e.g. verifying eligibility, submitting claims), and how much autonomy you want the AI to have on routine versus sensitive tasks. Those preferences are turned into a personalization profile that Mobius apps read to tailor their behavior to you. Two components deliver this: `mobius-user` (the backend service and database that owns accounts, sessions, and preferences) and `@mobius/auth` (the shared front-end login/preferences UI reused by every surface).

## Audience

- **End users** — people signing in to Mobius (chat app or browser extension) to do their work. They create accounts, log in, complete a short onboarding, and adjust their profile and preferences.
- **Org admins / operators** — a small allowlisted group who can view the roster of registered users and inspect an individual user's profile, onboarding status, linked sign-in providers, and active sessions. Admin is granted by email allowlist (the `MOBIUS_USER_ADMIN_EMAILS` env var), not a self-service role. There is no in-app UI to manage the allowlist — it is set via deploy config and requires a redeploy to change.

## Capabilities

- **Sign up with email and password** — create an account with email, password (minimum 8 characters), and optional display name / first name. A welcome email is sent on signup (best-effort; never blocks account creation).
- **Sign in with email and password.**
- **Sign in with Google** ("Sign in with Google") — one-click Google login; a first-time Google sign-in auto-creates the account, and a Google login that matches an existing email links Google to that account. (Available on the deployed FastAPI service / chat; the older Flask backend does not implement Google sign-in — see the Flask parity note below.)
- **Demo logins** — typing a shortcut like `admin`, `scheduler`, `eligibility`, `claims`, `clinical`, or `sarah` in the email field expands to a `@demo.clinic` demo account (for demos/testing).
- **Stay signed in** — sessions persist via access + refresh tokens; the front end silently refreshes your session in the background (~5 minutes before expiry) so you are not logged out mid-work.
- **Sign out** — ends your session on that device (requires a confirmation click in the account view).
- **Account view** — see who you're signed in as (greeting name), open preferences, and sign out.
- **Profile & preferences** you can edit:
  - Preferred name (how Mobius greets you)
  - Timezone (US: Eastern / Central / Mountain / Pacific)
  - Activities you focus on (multi-select from a server-provided list, e.g. verify eligibility, submit claims, rework denials, prior authorization, patient outreach, document notes, coordinate referrals; one can be marked primary)
  - Communication tone (Professional / Friendly / Concise)
  - AI experience level (beginner / regular / expert)
  - Autonomy for routine tasks (do it automatically / show me first / just guide me)
  - Autonomy for sensitive tasks (do it automatically / always show me before acting / never act without my approval)
  - Personalized greeting on/off
- **Personalization profile** — your preferences are compiled into a structured profile (including a ready-to-use `rendered_prompt`) that Mobius apps read to tailor responses to you.
- **Admin roster view** — allowlisted admins can list and search registered users and open a per-user detail panel.
- **Multi-tenant accounts** — every user belongs to a tenant (organization). A default tenant is used when none is specified. Email uniqueness is scoped per tenant and enforced in application code (there is no database uniqueness constraint yet).

## Invites, set-password & joining your org — how do I get my team in? (LIVE 2026-07-15)
**The onboarding chain is live end-to-end, both directions:**
- **Google sign-in does not activate invited accounts** *(policy, 2026-07-17)* — if you were invited, signing in with Google keeps your account in "invited" status; only completing the set-password link activates it. (Prevents invite-bypass; ruled by Ananth, live on mobius-user rev 00025.)
- **Invited path** — an org admin (via the org-setup flow) invites you: you get an email with a secure link → the **set-password page** (`/auth/set-password`; the same page also serves password reset — it reads the link's purpose and titles itself accordingly) → set your password → you're an active member with your org and roles already attached. Verified with a real send 2026-07-15.
- **Self-serve path** — register yourself (email+password or Google), then **claim your organization in Preferences**: the claim is validated against the org master and goes to **pending** until an authorized approver confirms it (approve endpoints are writer-gated). While pending, you can use Mobius as an individual; org-scoped features light up on approval.
- **Password reset** — same primitives as invites: a reset email links to the set-password page.
- Emails ride the **mobius-email send chokepoint** (validation, suppression list, audit log). Ops note: the email service's cold start once ate the first send after idle; hardened with a 30s timeout + one idempotent retry.

## Not yet available (planned)

These are visible in the UI or present in the schema but are **not functional today**. Do not describe them to users as working features.

- **Microsoft sign-in and Enterprise SSO** — the login modal renders **Microsoft** and **Enterprise SSO** buttons, but clicking either shows a "Coming soon" toast. There is no backend for any OAuth/SSO provider other than Google.
- **Roles / granular permissions** — a `role` table exists in the schema, but it is never populated or read. Access control is effectively **binary**: a regular user vs. an email-allowlisted admin. A code comment notes a planned migration to an `is_admin` column once roles are wired in; treat roles as future, not shipped.
- **Admin "add employees" UI** — the invite BACKEND is live (see the Invites section above), but there is no in-product admin screen to send invites or edit a team roster yet; invites go through the org-setup flow.
- **Tenant self-management** — no CRUD for tenants and no way for a user to create, switch, or leave a tenant from the UI. (Org membership itself is now self-claimable with approval — see the Invites section — but tenant management remains unbuilt.)
- **Email verification** — email/password signups are not required to verify their email. (Google's own `email_verified` claim is checked for Google sign-in only.)
- **Account deletion (GDPR delete)** — no self-service or admin endpoint to delete a user or their data.

## Navigation & Access

Auth is embedded in the host app (chat, extension) rather than living at fixed page URLs — the UI is a set of modals and a user menu that the host opens.

- **Login / signup** — opens as a modal (`AuthModal`) when a signed-out user clicks the sidebar/user button. Modes: `login`, `signup`, `account`, and a post-signup `welcome` panel.
- **User menu** — clicking your avatar/name opens a dropdown with: **My Preferences**, **Not you? Sign in differently**, and **Sign out**.
- **Preferences** — opens as a modal (`PreferencesModal`) from the account view, the user menu ("My Preferences"), or the "Set up preferences" button on the welcome panel. Tabs: Profile, Activities, AI Comfort, Display.
- **Admin roster** — surfaced by the host app (e.g. a "Registered users" item in the chat hamburger menu), shown only to allowlisted admins.
- **Standalone admin dashboard** — `mobius-user` also serves a plain admin page at `https://<mobius-user-host>/admin` (separate origin), used mainly for dev/ops debugging and disaster recovery.

Under the hood, all calls go to `/api/v1/auth/*` (login, register, google, refresh, logout, me, check-email, onboarding, preferences, activities) and admin calls to `/api/v1/admin/users`. Host apps typically proxy these through their own origin so the browser only talks to one domain. Note: the exact menu labels and placement (hamburger vs. sidebar) vary per host app; the labels here (`My Preferences`, `Not you? Sign in differently`, `Sign out`) are the `@mobius/auth` defaults and the chat/extension wiring is the reference.

## Key User Workflows

1. **To create an account (email/password):**
   Click the sidebar/user button → the login modal opens → switch to **Create account** → enter email, password (8+ chars), optionally display and first name → submit. You're signed in immediately and land on a welcome panel. Choose **Set up preferences** to onboard now, or **Skip for now** to jump straight in. A welcome email is sent in the background.

2. **To sign in with Google:**
   Open the login modal → click **Google** → pick your account in the Google popup. First-time Google users get a new account and the welcome panel; returning users are signed straight in. If your Google email matches an existing account, Google is linked to it.

3. **To set up or change your preferences:**
   Open the user menu → **My Preferences** (or "Set up preferences" on the welcome panel) → across the Profile / Activities / AI Comfort / Display tabs, set your preferred name, timezone, the activities you focus on, communication tone, and how much autonomy the AI gets on routine vs. sensitive tasks → **Save**. Mobius apps pick up the change the next time they read your profile.

4. **To sign out (or switch accounts):**
   Open the user menu → **Sign out** (confirm) to end the session on this device, or **Not you? Sign in differently** to log out and reopen the login modal.

5. **(Admins) To view registered users:**
   From an admin-only menu item (or the standalone `/admin` page), open the users list → search by email or name → click a user to see their profile, onboarding status, linked sign-in providers, active session count, and preferences. Admin access requires your email to be on the allowlist; non-admins never see the menu item.

## Integrations

Other Mobius modules (chat, RAG, extension, OS, story-ui) consume auth rather than reimplementing it:

- **Shared front-end package** (`@mobius/auth`) — every surface embeds the same login modal, preferences modal, and user menu, so the sign-in and preferences experience is identical across chat and the extension. Token storage is pluggable: web apps use `localStorage`, the Chrome extension uses a chrome-storage adapter.
- **Session tokens** — after login the front end holds a bearer access token and refresh token; it attaches `Authorization: Bearer <token>` to API calls. Modules can either call `GET /api/v1/auth/me` to get the full profile, or (if they share the `JWT_SECRET`) validate the JWT locally to identify the user without a round trip.
- **Proxy pattern** — host backends forward `/api/v1/auth/*` (and `/api/v1/admin/*`) to `mobius-user`, so the browser only sees the host's origin and the host can layer on logging, rate limits, and audit trails.
- **Personalization profile** — consumers read `user.profile.rendered_prompt` from `/me` and splice it into their LLM system prompt, or read structured fields (e.g. `autonomy.sensitive_tasks`) to gate behavior — for example, showing a "Confirm action" step when a user asked to confirm sensitive tasks first.
- **User identity everywhere** — only `mobius-user` reads/writes the user database; other modules reference a user solely by `user_id` (UUID). There are no cross-database foreign keys.
- **Admin gating** — admin endpoints require both a valid token and an email on the `MOBIUS_USER_ADMIN_EMAILS` allowlist (403 otherwise).

## Doc-readiness notes

- **Primary audience tag:** mixed. The end-user flows (sign up, sign in, preferences, sign out) are user-facing; the admin roster and integration/proxy material lean developer/operator.
- **What's solid:**
  - Sign-in methods (email/password, Google, demo shortcuts), session/refresh behavior, and logout — grounded in `AuthService.ts`, `AuthModal.ts`, and the backend routes.
  - The full preferences field list — grounded in `PreferencesModal.ts`, `preference.py`, and the onboarding/preferences routes.
  - Endpoints, token contract, and the personalization profile — authoritatively documented in `Mobius-user/SPEC.md`, `CONSUMER_RECIPE_PROFILE.md`, and `CONSUMER_RECIPE_ADMIN.md`.
  - Admin capabilities and the email-allowlist gating — grounded in `admin.py` and `CONSUMER_RECIPE_ADMIN.md`.
- **Not yet available:** stubbed/planned items live in the **"Not yet available (planned)"** section above (Microsoft/Enterprise SSO, granular roles, admin add-employees UI, tenant self-management, email verification, account deletion). Invites / set-password / password reset / org self-claim-with-approval moved to LIVE 2026-07-15 (owner-verified, real send confirmed) — see the Invites section.
- **What's ambiguous / thin (for the docs author):**
  - **Flask vs FastAPI parity — user-relevant.** There are two backend implementations. The FastAPI implementation (used by chat, and the one deployed to Cloud Run) has Google sign-in, the welcome email, the personalization `profile` envelope in `/me`, and auto-complete-onboarding-on-preferences-save. The **Flask** blueprint is a thinner, older variant that lacks **all four**: no `/google` route (no Google sign-in), no welcome email, no `profile` key in its `/me` response, and it does not mark onboarding complete when preferences are saved. Describe the FastAPI/chat behavior as the norm and flag Flask hosts as reduced.
  - **Menu labels / navigation:** the defaults (`My Preferences`, `Not you? Sign in differently`, `Sign out`) come from `@mobius/auth`, but exact labels and placement (hamburger vs. sidebar) depend on the host app; verify against the specific surface being documented.
  - **Per-tenant email uniqueness** is enforced only in application code (checked at register time); there is **no** database unique constraint, so it is race-prone. Do not describe it as a hard guarantee.
  - **Multi-tenant plumbing:** `tenant_id` is a request body field today (SPEC has an open question on whether it becomes a URL path prefix or a header). This is an implementation detail, not a user-facing feature.
- **Gaps a human must fill:**
  - Confirm the production `mobius-user` service URL and admin allowlist contents (dev values only are documented).
  - Confirm whether the "Not yet available" items are on the near-term roadmap before publishing timelines.
