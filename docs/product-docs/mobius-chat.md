# Mobius Chat
> A conversational assistant for the non-clinical work behind healthcare operations — ask a question, upload a file, run a credentialing workup, get sourced answers in seconds instead of three phone calls.

## Purpose
Mobius Chat is the flagship user-facing product of the Mobius platform: a chat interface where a healthcare operations user can ask policy, billing, and provider questions and get answers grounded in a curated corpus, uploaded documents, live web search, and the NPPES provider registry — with citations. It is more than a chatbot: it doubles as the entry point to structured operational workflows, most notably **provider credentialing** (a 6-step pipeline) and a **provider roster** that tracks who is billable, who has gaps, and what tasks are open.

A user cares because it collapses slow, multi-tool operational work — looking up a payer's timely-filing rule, checking whether an NPI is active and enrolled, reconciling a provider roster against Medicaid enrollment data — into a single conversational surface backed by verifiable sources. The landing page tagline states the value directly: "Some questions should take seconds, not three phone calls."

## Audience
- **End user (primary):** Healthcare operations / non-clinical staff — eligibility, claims, credentialing, scheduling roles. This is the dominant audience; the UI is built for them (chat, uploads, roster, pipeline).
- **Provider-operations user:** People running credentialing and maintaining a provider roster for an organization.
- **Admin / operator:** Access to query-dump dashboards, model-health/profile controls, and dev-token minting — all gated behind env flags (`MOBIUS_ADMIN_ENABLED`, `MOBIUS_DEV_TOKEN_ENABLED`).
- **Developer:** Interacts through the documented HTTP API (`POST /chat`, SSE streaming, per-turn mode/profile overrides) and the skill registry.

## Capabilities
**Core chat**
- Ask natural-language questions; answers stream back with inline citations and source cards (with "Open document" / "Download PDF" CTAs where available).
- Choose a **response mode** in the composer dropdown: **⚡ Fast** (2 rounds, brief answer), **◉ Normal** (registry-first, practical — the default), **✦ Thinking** (deep research, high confidence). These map to backend `chat_mode` values `quick` / `copilot` / `agentic` respectively (confirmed in `frontend/index.html` composer `<select id="composerMode">` and the `MODE_LABELS` map in `app.js`). A fourth `task` mode exists at the API level (raw text, skips the integrator) but is not a composer option.
- Pick an **LLM / model profile** from a sidebar dropdown (`<select id="modelProfileSelect">`); `auto` is always offered and the rest of the list is server-driven from `available_profiles`. The choice travels with each turn as `model_profile`.
- Multi-turn context: threads retain jurisdiction, URLs, and running state across follow-up turns.

**Documents & uploads**
- Attach a document from the composer via the **paperclip (📎)** button; accepted types are **PDF, DOCX, HTML, TXT** (`accept` on `#composerAttachmentInput`). The file is staged as a chip above the composer and uploaded on **Send** to `/chat/roster-upload?file_purpose=instant_rag`, then you can immediately ask questions against it in that thread ("instant RAG"). Large files (~500 KB+) trigger a confirmation dialog with an estimated processing time.
- The older ⋯ → "Upload file" flow with a purpose picker ("Roster for reconciliation" / "Other (RAG / reference) — soon") is **no longer in the shipped `/` bundle** — that menu item is hidden; the paperclip is now the single file-attach affordance. (The purpose picker still exists on the separate roster upload page and in the legacy `frontend/static/index.html`, which is not the page served at `/`.)
- Ask questions against uploaded documents (per-thread and cross-thread upload catalog).
- Restore / re-attach uploads from other threads via an upload-restore banner ("Attach to this chat").
- Document reader operations proxied to the doc-reader skill: **read/reassemble**, query-targeted **extract**, and **summarize** a published document.

**Built-in skills (auto-selected by the planner, invoked in natural language)**
- `search_corpus` — hybrid BM25+vector search over the curated policy/billing corpus.
- `search_uploaded_document` — search inside user-uploaded documents on the thread.
- `healthcare_query` / healthcare code lookup — payer/billing/clinical coding (CPT, HCPCS).
- `healthcare_npi_lookup` — provider lookup by NPI from the NPPES registry.
- `fetch_document` — retrieve a specific corpus document.
- `google_search` and `web_scrape` — live web search + URL scraping (web mode).
- `list_tasks` / `create_task` / `resolve_task` — task management from chat.
- `vibe`, `transform_previous_answer`, `cached_answer_lookup` — conversation helpers (rephrase/reformat prior answer, reuse cached answers).
- `document_upload_skill` / `list_thread_document_uploads` — upload handling.
- Skills are grouped by category (corpus, healthcare, npi, web, documents, tasks, utility) and each user can **enable/disable individual tools** via a per-user tool policy (`GET/PUT/DELETE /user/tools`, reset via `POST /user/tools/reset`).

**Credentialing pipeline (`/pipeline`)**
- Start a credentialing **run** for an organization; choose **🧭 Copilot** (step-by-step, default) or **⚡ Autopilot** (full pipeline) mode, then "Start Pipeline →".
- **8 steps** (from the `PLAN` array in `pipeline-core.js`): Identity → Locations → Roster validation (NPPES) → Payor enrollment (Medicaid PML) → Compliance (ghost billing) → Taxonomy optimization → Provider AI summaries → Org credential-health report.
- NPI/org discovery with selectable NPI cards; NPPES reconciliation table (filter Enrolled/Flagged/Not enrolled; search by name/NPI/Medicaid ID); per-provider actions (mark resolved, create task, export, dismiss).
- PML validation with payer readiness score (0–100) and per-provider detail (AHCA PML record vs confirmed location, edit codes, recommended actions, notes).
- Embedded **task queue** (needs-attention / open / added-by-you) with CSV export.
- Floating **"Ask Mobius" chat** scoped to the current org's run data.

**Provider roster (`/roster`)**
- Live provider roster for an organization: stats bar (Total, NPPES Active, PML Gaps, Open Tasks, Last Run), filter rail, search, provider cards, and per-provider detail drawer (NPPES/PML status, AI summary, open tasks).
- **Export CSV**, **Add Provider** (with live NPPES lookup), and **Run Credentialing →** (opens the pipeline).
- Natural-language command input / chips: `run`/`credentialing` → pipeline, `export`/`csv` → download, `add provider` → modal, `upload`/`roster` → upload page; anything else is treated as a search. (No `/slash` syntax.)

**Feedback & personalization**
- Per-response thumbs up/down, optional comment, per-source feedback, and adjudicator/QC scoring endpoints.
- Passage bookmarking inside the **document reader** panel (Bookmarks button + drawer; stored in localStorage).
- Config drawer (hamburger ☰) with Profile / Activities / AI Comfort / Display preference tabs.
- Sidebar: **Recent searches**, **Most helpful searches**, **Most helpful documents** (with citation counts), plus a **New chat** button.

**Email**
- A thread-email API exists (`POST /chat/thread/{id}/email`) that assembles the transcript server-side, supports an LLM summary mode, and is idempotent (proxies to the mobius-skills email service). **No UI trigger for this was found in the shipped `/` frontend bundle** — treat "email a thread" as an API/backend capability, not a user-facing button yet. See "Not yet available (planned)".

**Admin (env-gated)**
- Query-dump / usage dashboard (`GET /chat/admin/queries`), model-health and model-profile inspection/override, LLM router & quality report, dev-token minting.

## Navigation & Access
- **Main chat:** `GET /` (served from `frontend/index.html`), title "Mobius Chat". Composer at bottom; sidebar on the left.
- **Pipeline (credentialing):** `GET /pipeline` (served by mobius-chat from `frontend/static/pipeline.html`) — also reachable from the sidebar Skills section and the "Open Pipeline" / "Run Credentialing →" buttons.
- **Roster:** the roster page is **served by the external provider-roster-credentialing service**, not by mobius-chat. The sidebar Roster button opens it in a **new tab** via `window.open(<MOBIUS_ROSTER_URL>/roster?org=…)` (base URL from `MOBIUS_ROSTER_URL` / `CHAT_SKILLS_PROVIDER_ROSTER_CREDENTIALING_URL`). Its data still comes from chat APIs (`/chat/roster-truth/*`, `/chat/roster-reconcile/*`).
- **Roster upload page:** `/roster-ui/upload.html` — also served by the external roster/credentialing service (URL surfaced via `GET /chat/skills/urls`); the roster page's "upload"/"roster" command navigates here.
- **Sidebar entry points:** New chat, Recent searches, Most helpful searches, Skills (Roster / Credentialing Pipeline), account/sign-in area, LLM selector.
- **Composer entry points:** message input ("Message Mobius Chat…"), response-mode dropdown, paperclip (📎) document attach, ⋯ options menu (currently only "Add link" — disabled/coming soon; the "Upload file" item is present in markup but hidden), send.
- **Keyboard:** Enter sends; Shift+Enter inserts a newline. (No slash-command palette found in the frontend bundle.)
- **Landing quick prompts:** "Sunshine timely filing", "NPI profile sample", "BH prior auth" one-click buttons, plus "Try:" example links on the update cards (e.g. provider enrollment, disputing a claim, behavioral-health prior auth).
- **Auth:** Google OAuth ("Continue with Google") plus email/password; SSO and Microsoft OAuth show "Coming soon". Auth mode is env-controlled (`CHAT_AUTH_MODE`: off / optional / required; hosted defaults to required, dev to off).

## Key User Workflows
1. **Ask a sourced policy/billing question**
   1. Open `/`, optionally pick a response mode (Fast/Normal/Thinking) and model profile.
   2. Type a question (e.g. "What is timely filing for participating providers with Sunshine Health?") and press Enter.
   3. Read the streamed answer with inline citations; open/download source documents.
   4. Optionally thumbs-up/down, comment, or bookmark passages; ask a follow-up in the same thread (context is retained).

2. **Look up a provider by NPI**
   1. Ask "Look up NPI 1669572290 and summarize practice location and taxonomy" (or use the "NPI profile" quick prompt).
   2. The `healthcare_npi_lookup` skill queries NPPES and returns practice location, taxonomy, and status inline.

3. **Reconcile / upload a provider roster**
   1. Roster reconciliation uploads (CSV/XLSX with `file_purpose=roster_reconciliation`) are handled by `POST /chat/roster-upload` and surfaced through the **external roster upload page** (`/roster-ui/upload.html`), reached from the Roster page's upload action — not from the main chat composer paperclip (that path is document Q&A / instant-RAG only).
   2. Review the roster upload receipt (storage → database → warehouse progress) and any reconciliation link.
   3. Open the Roster page (new tab) to view providers, gaps, and open tasks.

4. **Run a credentialing workup**
   1. Go to `/pipeline`, enter the organization, choose Copilot or Autopilot, click "Start Pipeline →".
   2. Step through Identity → Locations → Roster/NPPES → Payor/PML → Compliance → Taxonomy → Provider summaries → Org report; select/flag NPIs, resolve reconciliation rows, create tasks.
   3. Use the "Ask Mobius" floating chat for org-specific questions; export tasks/records as needed.
   4. Completed run updates the persistent Roster; monitor providers and open tasks there.

## Integrations
Mobius Chat orchestrates and proxies to several other Mobius modules (URLs configured via env):
- **mobius-rag / retriever** — curated corpus retrieval; published RAG metadata in Postgres + Vertex AI Vector Search (`CHAT_RAG_DATABASE_URL`, `MOBIUS_RAG_URL`, `MOBIUS_RAG_APP_PUBLIC_URL`).
- **mobius-user / mobius-os (auth)** — OAuth and JWT auth proxied via `/api/v1/auth/*` and `/api/v1/public-config` (`MOBIUS_USER_URL`, `MOBIUS_OS_AUTH_URL`).
- **mobius-skills** — remote skills the chat calls or proxies to: doc-reader (`CHAT_SKILLS_DOC_READER_URL`), email (`CHAT_SKILLS_EMAIL_URL`), Google search (`CHAT_SKILLS_GOOGLE_SEARCH_URL`), healthcare (`CHAT_SKILLS_HEALTHCARE_URL`), instant-rag (`CHAT_SKILLS_INSTANT_RAG_URL`), task-manager (`CHAT_SKILLS_TASK_MANAGER_URL`), vibe (`CHAT_SKILLS_VIBE_URL`), MCP server (`CHAT_SKILLS_MCP_URL`).
- **Provider roster / credentialing service** — `CHAT_SKILLS_PROVIDER_ROSTER_CREDENTIALING_URL` (co-owns the credentialing dataset; serves the roster upload UI).
- **mobius-document-viewer** — `MOBIUS_DOCUMENT_VIEWER_URL` for opening source documents.
- **LLM backend** — Vertex AI (LLM + embeddings) with an in-process model router / bandit for per-stage model selection.
- **MCP** — remote MCP tools auto-register as chat skills via `register_mcp_skills()` (`MOBIUS_MCP_AUTOREG` flag).
- **Queue** — pluggable request/response queue (in-memory for dev, Redis for API+worker split).

## Doc-readiness notes
- **Primary audience tag:** mixed (user-first, with distinct provider-ops, admin, and developer surfaces).
- **What's solid:**
  - Route inventory (chat `/`, pipeline `/pipeline`, uploads, tasks, credentialing, doc-reader, email, admin, user-tools) is grounded in `app/api/*` and `app/main.py`. Note: mobius-chat serves only `/` and `/pipeline`; the roster page is served by the external provider-roster-credentialing service.
  - The built-in skill catalog, categories, and per-user tool policy are grounded in `app/skills/registry.py` and `app/skills/builtin/*`.
  - Pipeline behavior is grounded in `frontend/static/pipeline*.js`; roster page behavior in `frontend/static/roster-unified.js` (the roster page HTML itself is served externally).
  - Response modes and per-turn overrides are grounded in `app/api/chat.py`.
- **Verified in this pass (`frontend/index.html`, `app.js`, `pipeline-core.js`, `app/api/*`, `app/main.py`):** composer mode labels → `chat_mode` mapping; model-profile picker; paperclip/instant-RAG composer upload; pipeline is 8 steps with Copilot/Autopilot modes; config-drawer tabs (Profile/Activities/AI Comfort/Display); Google OAuth + email/password login with Microsoft/SSO "coming soon"; admin gating flags; doc-reader bookmarks.
- **What's ambiguous / needs a human:**
  - `/` serves `frontend/index.html`; `frontend/static/index.html` is a stale/legacy bundle — do not cite it as the live UI.
  - No thread rename/delete UI was found in the frontend (may be server-side or unimplemented).
  - Confirm which admin dashboards are user-reachable in production vs env-gated (`MOBIUS_ADMIN_ENABLED` / `MOBIUS_DEV_TOKEN_ENABLED`).
  - `healthcare_query` and `healthcare_npi_lookup` share one backend (the latter is a router alias mapping to the former); treat them as one healthcare capability rather than two independent skills.

## Not yet available (planned)
These appear in the product surface but are not wired for end users in the shipped `/` bundle as of this snapshot:
- **Email a thread** — API (`POST /chat/thread/{id}/email`) exists, but there is **no UI trigger** in the frontend.
- **⋯ → "Add link"** — present but **disabled ("coming soon")**; clicking shows a "Coming soon" toast.
- **⋯ → "Upload file" purpose picker** ("Roster for reconciliation" / "Other (RAG / reference) — soon") — the menu item is **hidden** in the live bundle; the composer paperclip (document Q&A) is the only shipped composer upload path.
- **"Queue for batch processing"** on large uploads — surfaced but **disabled ("coming soon")**.
- **Microsoft OAuth** and **Enterprise SSO** sign-in buttons — render on the auth form but are **"coming soon"** (toast only).
