# Mobius Chat
> A conversational assistant for the non-clinical work behind healthcare operations — ask a question, upload a file, run a credentialing workup, get sourced answers in seconds instead of three phone calls.

## Purpose
Mobius Chat is the flagship user-facing product of the Mobius platform: a chat interface where a healthcare operations user can ask policy, billing, and provider questions and get answers grounded in a curated corpus, uploaded documents, live web search, and the NPPES provider registry — with citations. It is more than a chatbot: it doubles as the entry point to structured operational workflows, most notably **provider credentialing** (a pipeline) and a **provider roster** that tracks who is billable, who has gaps, and what tasks are open.

A user cares because it collapses slow, multi-tool operational work into a single conversational surface backed by verifiable sources. The landing tagline states the value: "Some questions should take seconds, not three phone calls."

## Audience
- **End user (primary):** Healthcare operations / non-clinical staff — eligibility, claims, credentialing, scheduling roles. The UI is built for them (chat, uploads, roster, pipeline).
- **Provider-operations user:** People running credentialing and maintaining a provider roster for an organization.
- **Admin / operator:** Access to query-dump dashboards, model-health/profile controls, LLM-performance ratings, and dev-token minting — gated behind env/profile flags.
- **Developer:** Interacts through the HTTP API (`POST /chat`, SSE streaming, per-turn mode/profile overrides) and the skill registry.

## Response modes & caching
Choose a **response mode** in the composer dropdown (`#composerMode`; persists to `localStorage._mobiusChatMode`). Thinking is a *mode*, selected from the same dropdown as Fast/Normal — not a separate toggle:

| Mode (label) | `chat_mode` | Behavior | Caching |
|---|---|---|---|
| **⚡ Fast** | `quick` | 2 rounds, brief answer | **Uses cached answers** when available (skips the integrator on a cache hit) |
| **◉ Normal** *(default)* | `copilot` | Registry-first, practical | Fetches fresh **unless** a cached answer clears the confidence threshold |
| **✦ Thinking** | `agentic` | Deep research, multiple ReAct rounds, full tool chain | **Always fresh — never cached** |

A fourth `task` mode exists at the API level (raw text, skips the integrator) but is **not** a composer option. Cache behavior is exposed to admins in the queries dump (`cache_mode`, `cache_top_similarity`).

## Composer & sending
- **Message input** (`#input`) — placeholder "Message Mobius Chat…". **Enter** sends, **Shift+Enter** newline.
- **Send** (`#send`) — paper-airplane icon; disabled when input is empty.
- **Mode selector** — see *Response modes & caching* above.
- **Model / LLM profile selector** (admin-gated, `#modelProfileWrap`) — dropdown: `auto`, `optimal`, `gemini`, `anthropic`, plus custom profiles. Auto-hides if the endpoint 404s. (2026-04-27: the old `default`/`bandit` names were renamed to `auto` in the UI; the backend still accepts the old names.) A ✓/! status indicator follows `POST /chat/admin/model-profile`.
- **Paperclip attach** (`#composerAttach`) — "Attach a document"; accepts **.pdf, .docx, .html, .htm, .txt**. Staged as an inline chip (📎 filename + ✕ remove) above the composer; uploaded on Send for instant Q&A in that thread ("instant RAG").
- **Composer ⋯ menu** (`#composerOptions`) — effectively empty: "Upload file" is **hidden** (removed in a 2026-04-18 UX audit); "Add link" is a **disabled** "coming soon" stub.

## Message-level actions
Per assistant message:
- **Thumbs up / down** — Up records the rating and refreshes the sidebar "Most helpful"; Down opens a comment area for an optional note. Disabled after the first vote. **This is how you give feedback on an answer — there is no separate feedback form**: rate the message directly, or type product feedback straight into the composer (e.g. "I have feedback: …") and Mobius logs and routes it.
- **Copy** — copies the message text; shows "Copied" briefly.
- **Email this conversation** (`#emailDialog`, two-step, **live**) — the **Email button** under each answer is how you email this conversation or a summary of it. Step 1: recipient + scope (whole thread / last exchange) + mode (LLM summary or full transcript) → preview. Step 2: re-draft or send (`POST /chat/thread/{id}/email`). Nothing sends without your confirmation.
- **Per-source feedback** — thumbs up/down on each `[N]` source card (`POST /chat/source-feedback/{cid}`).
- **Details / Citations tabs** *(2026-07-13; replaces the old "Show details" toggle)* — Details expands the answer's sections; Citations lists formatted, copyable reference strings.
- **Source citation click** — "Open document" (inline doc reader), "Open in RAG ↗" (external), or "Download PDF" when the RAG API is configured.
- **Admin-gated:** "Routing correct?" LLM-performance thumbs; "Adjudicator helpful?" thumbs in the QA scorecard.

## Sidebar
- **New chat** (`#btnNewChat`).
- **Recent searches** and **Most helpful searches** — your conversation history; see the dedicated section **Your past queries** below.
- **Vault block** *(2026-07-13)* — a violet card with tabs (Recent / Liked / Tasks / Uploads) and "Manage →", opening the full Vault panel (your private documents; see Operations Suite → Vault).
- **Operations Suite** — open-in-tab product tiles (Strategy, Public Library, Roster, Vault) + an Appeals Agent demo tile + "Learn more about chat skills". Detailed in the **Operations Suite** section below.
- **User / account area** — "Signed in as {name}"; click opens the auth modal.
- **Onboarding nudge** (`#onboardingNudge`) — "⚙ Set up your profile" when not yet onboarded; opens Preferences.
- **Collapse** — a chevron collapses the sidebar to an icon rail (Recent 🔍, Most Helpful ⭐, Skills ⊞ with badges).

## Your past queries — where did my conversation go?
**Your past queries and conversations live in the sidebar.** Looking for a previous question, thread, or answer?
- **Recent searches** — your last ~20 conversations (`GET /chat/history/recent`). **Click any entry to reopen that conversation** and continue where you left off; nothing is lost when you start a new chat.
- **Most helpful searches** — your best past answers: everything you rated 👍, one click away. It refreshes each time you thumbs-up an answer.
- Starting fresh? **+ New chat** opens a new thread; your old ones stay in Recent searches.

## Operations Suite (open-in-tab products)
**What is the Public Library?** The Public Library is Mobius's shared knowledge base — payer manuals, regulations, and public sources — and it's one of the Operations Suite tiles in the chat sidebar. The sidebar's Operations Suite holds **open-in-tab product tiles** — distinct from the auto-invoked chat skills. Clicking a tile opens that product in a new tab; a Mobius-owned tile forwards your access token in the URL fragment (`#t=…`) so it signs you in without a second login. Current tiles (2026-04-29 layout):
- **Strategy** — "Benchmarking + KPIs" — **live**. Opens the market-intelligence / benchmarking deck.
- **Public Library** — "Shared corpus — payer manuals, regs, public sources" — **live**. Opens the shared RAG corpus UI (the public, non-private knowledge base). Renamed from "Library" to make room for Vault.
- **Roster** — "Provider directory + credentialing" — **coming soon**. Credentialing was folded into Roster (same backing service; two tiles confused users), and the tile's click is currently disabled.
- **Vault** — "Your org, personal & patient documents (private namespaces)" — **partially live (2026-07-13)**. The private counterpart to the Public Library. Live now in chat: a violet **Vault sidebar block** with tabs (Recent / Liked / Tasks / Uploads) and a "Manage →" link that opens the **Vault panel** — a full-width slide-in with rail navigation and a file table (Status · Filename · Uploaded · Last used · TTL · Visibility · Actions; status chips Ready/Indexing/Failed/Expired). Still pending: **Promote to org corpus** (button present but disabled — "Available when org corpus is enabled").

Also here: an **Appeals Agent demo** tile (external prototype) and a "Learn more about chat skills" link that opens the Skills modal.

## Config drawer (hamburger ☰)
- **Config version** — short SHA from `/chat/config`.
- **Preferences tabs** — Profile / Activities / AI Comfort / Display.
- **Show LLM performance** toggle (admin) — reveals model/latency/cost/routing panels; persists to localStorage.
- **Model Router & Quality Report** (admin) — modal of Thompson-sampling rules, composite-scoring spec, and per-stage breakdown (`GET /chat/llm-router-report`).
- **Recent Queries dump** (admin) — filterable (time window, user, errors-only, has-feedback, limit), auto-refreshing, paginated, JSON export; summary of p50/p95 latency, cost/tokens, errors, feedback.
- **Config Preferences panel** — an accordion of live config: **LLM (global)** (provider/model/temperature), **Decomposition** (parser & planner prompts), **Answering** (first-gen & RAG templates), **Integration** (integrator & consolidator). Save / load-from-server.
- **Config History** — past SHA versions with expandable snapshots.
- **Test with Current Config** — run a test prompt, name it, save as a **Named run** (Named runs list is view-only).

## Document reader panel
Opened via "Open document" on a source card (`#doc-reader-panel`, restored 2026-04-25):
- Header: title, payer, authority level, section count; "Open in RAG ↗".
- **Bookmarks** button + drawer (localStorage, max 50).
- **Table of contents** — hierarchical section links; clicking scrolls and marks the active section.
- **Expandable sections** — heading + markdown body + citation badges.
- **Text-selection toolbar** (on highlight): **Copy** | **Bookmark** (saves snippet + doc + page + date) | **Cite** (formats "text" — docname).

## Skills modal
"Mobius Operations Suite" (`#skillsModal`), from the sidebar "Learn more" or the rail skills icon: **Overview** tab (renders `/chat/skills-manifest`) + **Customize** tab (filter/order). Falls back to a curated chip list if the manifest is unavailable.

## Sign in & sign out — how do I log in or out?
**To sign in: click the user area at the bottom of the sidebar** ("Signed in as…" / "Sign in") — it opens the auth modal. Sign in with **email/password** or one click with **Google**; first-time users get a signup path and a welcome panel.

**To sign out: click the same user area → "Sign out"** (a confirmation click ends your session on this device). To switch accounts instead, choose **"Not you? Sign in differently"** — it signs you out and reopens the login modal in one step.
- **Auth gate** (`#authGate`) — blocks the UI until signed in (hosted default; dev may run with auth off).
- Auth mode is env-controlled (`CHAT_AUTH_MODE`: off / optional / required).
- Password reset doesn't exist yet (see the auth doc's "Not yet available") — if you're locked out, use Google sign-in or contact your admin.

## Preferences — how do I change the style of my answers?
**To change how Mobius talks to you: open the user menu (sidebar user area) → "My Preferences."** The preferences modal is where you update the style under which you get messages:
- **Communication tone** — Professional / Friendly / Concise: the style of every answer.
- **AI experience level** (beginner / regular / expert) and **autonomy** for routine vs sensitive tasks (do it automatically / show me first / just guide me).
- **Preferred name** (how Mobius greets you), **timezone**, and the **activities you focus on** (multi-select; one can be primary).
Saving refreshes your profile immediately — the next answer uses the new style — and hides the onboarding nudge. The same modal opens from the "⚙ Set up your profile" nudge for new users.

## Banners, status & answer components
- **Alpha banner** (`#alphaBanner`) + **Alpha notes modal** — release date, features, known limitations; dismiss persists.
- **Chat status banner** — transient ("Document ready", etc.), auto-hides ~20s.
- **Upload restore banner** — "Recent uploads from your other chats"; per-row "Attach" links an existing upload to this thread (no re-upload).
- **Roster upload receipt** — TurboTax-style progress (storage → database → warehouse) with a conditional NPI-reconciliation link.
- **Answer components** — a live **Thinking block** (phase dots, auto-collapse); an **Answer card** with a type badge (FACTUAL / CANONICAL / BLENDED / **RECITAL**) and a confidence badge (Approved Authoritative / Caution / Informational Only / No Sources), follow-up + suggested-action chips; **Clarification chips** (selections merge into the next send); a collapsible **Sources** citer; admin-only **LLM-performance**, **Adjudicator scorecard**, and **Retrieval-trace** panels; a **Credentialing Copilot** panel; a **Task-list** envelope (severity chips, resolve, Export CSV); and the **product-feedback capture card** + **feedback nudge chips** (live 2026-07-03).
- **RECITAL card mode** *(2026-07-13, revs 00413/414)* — for verbatim canonical texts (e.g. the founding "Why Mobius" essay): violet left border, an attribution line ("From the Mobius founding essay"), the full text as flowing serif prose (no bullet compression), a "Read the full essay" button, and a "Verbatim — Mobius founding document" badge.
- **Answer-card tab bar** *(2026-07-13, revs 00413/414)* — **Details / Citations** tabs replace the old "Show details" toggle; Citations shows formatted, copyable reference strings.
- **Envelope section formats** *(2026-07-13)* — answer sections can render as **table / steps / stats / conditions / bars / bullets** (per-section `format` field), not just bullet lists.

## Credentialing pipeline (`/pipeline`)
- Start a credentialing **run** for an organization; choose **🧭 Copilot** (step-by-step, default) or **⚡ Autopilot** (full pipeline), then "Start Pipeline →".
- Steps (from `pipeline-core.js`): Identity → Locations → Roster validation (NPPES) → Payor enrollment (Medicaid PML) → Compliance (ghost billing) → Taxonomy optimization → Provider AI summaries → Org credential-health report.
- NPPES reconciliation table (filter Enrolled/Flagged/Not enrolled; per-provider actions), PML validation with a payer-readiness score, an embedded task queue with CSV export, and a floating "Ask Mobius" chat scoped to the run.

## Provider roster
The roster page is **served by the external provider-roster-credentialing service**, not by mobius-chat — the sidebar Roster tile opens it in a new tab (`MOBIUS_ROSTER_URL`). Its data comes from chat APIs. It offers a stats bar, filter rail, provider cards + detail drawer, **Export CSV**, **Add Provider** (live NPPES lookup), and **Run Credentialing →**.

## Integrations
Mobius Chat orchestrates and proxies to other modules (URLs via env):
- **mobius-rag / retriever** — corpus retrieval + published metadata (`CHAT_RAG_DATABASE_URL`, `MOBIUS_RAG_URL`).
- **mobius-user / mobius-os** — OAuth + JWT via `/api/v1/auth/*` and `/api/v1/public-config`.
- **mobius-skills** — doc-reader, email, google-search, healthcare, instant-rag, task-manager, vibe, MCP, and **product-help** (`CHAT_SKILLS_*_URL`).
- **provider-roster-credentialing** — roster page + reconciliation data.
- **LLM backend** — Vertex AI (LLM + embeddings) with an in-process model router / bandit for per-stage selection.
- **MCP** — remote MCP tools auto-register as chat skills.

## Not yet available (planned)
Present in the surface but **not** wired for end users:
- **"Queue for batch processing"** on large uploads — a **disabled** "coming soon" stub (the large-file dialog's "Upload now" is live).
- **⋯ → "Add link"** — disabled "coming soon".
- **⋯ → "Upload file"** — hidden in the live bundle (the paperclip is the shipped composer upload path).
- **Microsoft OAuth / Enterprise SSO** — **not implemented**: no Microsoft/SSO code is present in the frontend at all (earlier docs called these "coming soon" — they are not even rendered).
- **Operations Suite: Roster tile** — renders but click is disabled (**coming soon**). (Strategy, Public Library are live; **Vault is now partially live** — see the Operations Suite section — with only org-corpus Promote still pending.)
- **Vault → Promote to org corpus** — button renders in the Vault panel but is **disabled**: "Available when org corpus is enabled."

## Doc-readiness notes
- **Primary audience tag:** user (with distinct provider-ops, admin, and developer surfaces).
- **Source:** rebuilt 2026-07-03 from the Chat Agent's code-verified UI inventory (`frontend/src/app.ts` ~10.3k lines + `index.html`), superseding the 07-01 code-skim. Every element above was confirmed against render code with file:line refs in the source session.
- **Corrections vs. the prior snapshot:** email-a-thread is **live** (two-step `#emailDialog`), not "no UI"; Microsoft/SSO are **absent**, not "coming soon"; caching now varies by mode (Thinking never caches).
- **Admin-gated** elements (model profile, LLM-performance, router report, queries dump, adjudicator/retrieval panels) appear only when the user's profile grants them.
- **Gaps a human must fill / for the loop:** deep pipeline & roster internals are owned by the credentialing/roster service (document via that agent); confirm which admin panels are user-reachable in production. Residual button-level gaps will surface via the `docs_gap` feedback loop.
