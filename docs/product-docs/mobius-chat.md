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
- **Email this thread** (`#emailDialog`, two-step, **live**) — Step 1: recipient + scope (whole thread / last exchange) + mode (LLM summary or full transcript) → preview. Step 2: re-draft or send (`POST /chat/thread/{id}/email`).
- **Per-source feedback** — thumbs up/down on each `[N]` source card (`POST /chat/source-feedback/{cid}`).
- **Show details** — expands hidden requirements/definitions in BLENDED answer cards.
- **Source citation click** — "Open document" (inline doc reader), "Open in RAG ↗" (external), or "Download PDF" when the RAG API is configured.
- **Admin-gated:** "Routing correct?" LLM-performance thumbs; "Adjudicator helpful?" thumbs in the QA scorecard.

## Sidebar
- **New chat** (`#btnNewChat`).
- **Recent searches** — last ~20 threads (`GET /chat/history/recent`), collapsible; clicking reopens the thread.
- **Most helpful searches** — populated from thumbs-up feedback; refreshes after each "up".
- **Operations Suite** — open-in-tab product tiles (Strategy, Public Library, Roster, Vault) + an Appeals Agent demo tile + "Learn more about chat skills". Detailed in the **Operations Suite** section below.
- **User / account area** — "Signed in as {name}"; click opens the auth modal.
- **Onboarding nudge** (`#onboardingNudge`) — "⚙ Set up your profile" when not yet onboarded; opens Preferences.
- **Collapse** — a chevron collapses the sidebar to an icon rail (Recent 🔍, Most Helpful ⭐, Skills ⊞ with badges).

## Operations Suite (open-in-tab products)
**What is the Public Library?** The Public Library is Mobius's shared knowledge base — payer manuals, regulations, and public sources — and it's one of the Operations Suite tiles in the chat sidebar. The sidebar's Operations Suite holds **open-in-tab product tiles** — distinct from the auto-invoked chat skills. Clicking a tile opens that product in a new tab; a Mobius-owned tile forwards your access token in the URL fragment (`#t=…`) so it signs you in without a second login. Current tiles (2026-04-29 layout):
- **Strategy** — "Benchmarking + KPIs" — **live**. Opens the market-intelligence / benchmarking deck.
- **Public Library** — "Shared corpus — payer manuals, regs, public sources" — **live**. Opens the shared RAG corpus UI (the public, non-private knowledge base). Renamed from "Library" to make room for Vault.
- **Roster** — "Provider directory + credentialing" — **coming soon**. Credentialing was folded into Roster (same backing service; two tiles confused users), and the tile's click is currently disabled.
- **Vault** — "Your org, personal & patient documents (private namespaces)" — **coming soon**. The private counterpart to the Public Library: per-org / per-user / per-patient isolated document namespaces behind a separate agent + isolation boundary (next sprint).

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

## Sign in & preferences
- **Auth gate** (`#authGate`) — blocks the UI until signed in.
- **Auth modal** — email/password login + signup, and **Google sign-in** (live after `/api/v1/public-config` provides the client id).
- **Preferences modal** — first/preferred name, tone, experience level, activity selection; saving refreshes the profile and hides the onboarding nudge.
- Auth mode is env-controlled (`CHAT_AUTH_MODE`: off / optional / required; hosted defaults to required, dev to off).

## Banners, status & answer components
- **Alpha banner** (`#alphaBanner`) + **Alpha notes modal** — release date, features, known limitations; dismiss persists.
- **Chat status banner** — transient ("Document ready", etc.), auto-hides ~20s.
- **Upload restore banner** — "Recent uploads from your other chats"; per-row "Attach" links an existing upload to this thread (no re-upload).
- **Roster upload receipt** — TurboTax-style progress (storage → database → warehouse) with a conditional NPI-reconciliation link.
- **Answer components** — a live **Thinking block** (phase dots, auto-collapse); an **Answer card** with a type badge (FACTUAL / CANONICAL / BLENDED) and a confidence badge (Approved Authoritative / Caution / Informational Only / No Sources), follow-up + suggested-action chips; **Clarification chips** (selections merge into the next send); a collapsible **Sources** citer; admin-only **LLM-performance**, **Adjudicator scorecard**, and **Retrieval-trace** panels; a **Credentialing Copilot** panel; a **Task-list** envelope (severity chips, resolve, Export CSV); and the **product-feedback capture card** + **feedback nudge chips** (the editable "share feedback" card and the low-weight prompts — live as of 2026-07-03).

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
- **Operations Suite: Vault + Roster tiles** — render but are **coming soon**: **Vault** = private per-org/user/patient document namespaces (next sprint, separate agent + isolation boundary); **Roster** tile's click is disabled. (The **Strategy** and **Public Library** tiles are live.)

## Doc-readiness notes
- **Primary audience tag:** user (with distinct provider-ops, admin, and developer surfaces).
- **Source:** rebuilt 2026-07-03 from the Chat Agent's code-verified UI inventory (`frontend/src/app.ts` ~10.3k lines + `index.html`), superseding the 07-01 code-skim. Every element above was confirmed against render code with file:line refs in the source session.
- **Corrections vs. the prior snapshot:** email-a-thread is **live** (two-step `#emailDialog`), not "no UI"; Microsoft/SSO are **absent**, not "coming soon"; caching now varies by mode (Thinking never caches).
- **Admin-gated** elements (model profile, LLM-performance, router report, queries dump, adjudicator/retrieval panels) appear only when the user's profile grants them.
- **Gaps a human must fill / for the loop:** deep pipeline & roster internals are owned by the credentialing/roster service (document via that agent); confirm which admin panels are user-reachable in production. Residual button-level gaps will surface via the `docs_gap` feedback loop.
