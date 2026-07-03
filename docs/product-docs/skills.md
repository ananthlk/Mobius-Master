# Skills
> The library of capabilities Mobius Chat can invoke on your behalf — from corpus search and NPI lookup to provider-roster credentialing reports and web scraping.

## Purpose
The Skills system is the set of concrete capabilities that Mobius Chat can call to answer a question or complete a task. When you ask something in chat, a planner decides which skill(s) to run — search the curated policy corpus, look up a provider by NPI, generate a credentialing report, scrape a web page, draft an email — and folds the results back into its answer. Each skill is a named, self-describing unit: the planner sees a one-line description of what it does and picks the right one for your request.

Three modules make this work. **`mobius-skills`** holds the standalone skill *services* — the FastAPI apps that do the heavy lifting (healthcare lookups, org intelligence, provider-roster credentialing, document reading, instant-RAG, appeals, email, web search/scrape, task manager, vibe). **`mobius-skills-core`** is the shared *implementation library*: one canonical Python function per capability (google search, web scrape, healthcare query, corpus search, lazy/thread retrieval, document-upload info) so the same code powers both chat and external clients without drifting. **`mobius-skills-mcp`** is the *MCP transport*: it wraps those capabilities as MCP tools reachable by any MCP client (Claude Desktop, other Mobius modules, external agents). Chat itself imports the fast-path skills directly (in-process, no network hop) via its own registry, and can additionally auto-register any tool the MCP server exposes.

## Audience
- **End users** — people working in Mobius Chat who trigger skills through natural-language requests (e.g. "get the NPI for David Lawrence Center", "run a credentialing report for Aspire", "what does ICD-10 F32.1 mean?"). Users generally don't invoke skills by name; the planner selects them.
- **Developers** — engineers who build new skills. They add one implementation to `mobius-skills-core` (or a standalone service in `mobius-skills`), then choose a *surface*: direct-import into chat, expose as an MCP tool, or both.

## Capabilities

### Available skills (user-facing)
These are the capabilities the chat planner can pick. The authoritative set is the **13 registered `SkillSpec` builtins** (`mobius-chat/app/skills/registry.py` + `app/skills/builtin/*`). Two entries below (`search_uploaded_document`, `healthcare_npi_lookup`) are **router-owned synthetic entries**, not registered skills — they are marked inline and are not independently user-invokable. Names in `code` are the canonical skill IDs.

The 13 registered builtins are: `search_corpus`, `fetch_document`, `document_upload_skill`, `list_thread_document_uploads`, `healthcare_query`, `google_search`, `web_scrape`, `list_tasks`, `create_task`, `resolve_task`, `transform_previous_answer`, `cached_answer_lookup`, and `vibe`.

**Knowledge & documents**
- `search_corpus` — Search Mobius's curated authoritative knowledge base (provider manuals, payer/Medicaid policies) with hybrid BM25 + vector retrieval; the default for policy/billing questions.
- `fetch_document` — Resolve a corpus document by name/filename/policy ID and return a clickable download link when you want the file itself, not the answer in it.
- `document_upload_skill` — Explains how to attach a PDF/DOCX/CSV/XLSX to the current chat thread (UI steps + upload endpoint) so it becomes searchable.
- `list_thread_document_uploads` — List the documents already attached to the current thread (filename, org, rows, upload time).
- `search_uploaded_document` — Search inside the documents you uploaded on this thread. **(Router-owned, not a registered `SkillSpec`.** Confirmed: appended synthetically by `skills_catalog()` and dispatched in the react-loop router, not the registry. Appears in the tool-settings UI but is not an independently registered chat skill.)

**Healthcare & provider registry**
- `healthcare_query` — Look up ICD-10-CM code meanings, CPT/HCPCS wording, Medicare/Medicaid coverage summaries (NCD/LCD), and NPI-by-number facts.
- `healthcare_npi_lookup` — Look up a provider by NPI number from the NPPES registry. **(Router-owned, not a registered `SkillSpec`.** Confirmed: synthetic entry in `skills_catalog()`. NPI-by-name/number lookups are actually served by `healthcare_query` (builtin) and the MCP `org_npi_lookup` / `search_org_names` tools.)

**Web**
- `google_search` — Search the web for current information; used as a last-resort external lookup after corpus and curated sources come up empty. Auto-scrapes the top result.
- `web_scrape` — Read a web page or crawl a site section from a seed URL (quick single page / medium tree crawl / detailed deep crawl with linked-document downloads).

**Tasks**
- `list_tasks` — List tasks from the unified task manager (open follow-ups, blockers, info cards), filterable by org, module, status, assignee, NPI, run, severity, etc.
- `create_task` — Create a new task / action item / follow-up for an org so the assistant can track it.
- `resolve_task` — Mark a task resolved. (Confirmed registered in `app/skills/builtin/tasks.py`, alongside `list_tasks` and `create_task`.)

**Conversation utilities**
- `transform_previous_answer` — Reshape the previous assistant answer into a new artifact (appeal letter, email, memo, shorter/plain-English version) with no new retrieval — the prior turn is the source.
- `cached_answer_lookup` — Semantic lookup against prior completed turns so a recent good answer can finalize the turn without fresh retrieval.
- `vibe` — Emit a short, dry, work-adjacent one-liner (toast, empathy, gratitude, data joke) when the message is casual and not a substantive question.

**Additional capabilities available over MCP (`mobius-skills-mcp`)** — reachable by external MCP clients, and auto-registerable into chat via the MCP adapter. Beyond the chat builtins above, the MCP server also exposes:
- `search_org_names` — Search NPPES + Florida PML for an organization/provider by name (copilot registry-only or agentic web-assisted), ranked by match confidence, returning NPI.
- `search_org_by_address` — Same registry search but by street address.
- `org_npi_lookup` — Enriched NPI lookup for an org (registry + optional web enrichment / name-variant expansion in agentic mode).
- `find_org_locations` — Discover all practice locations for a billing organization (credentialing Step 2) from NPPES + PML + DOGE billing→servicing links.
- `find_associated_providers_at_locations` — Build the operational provider roster per site for a billing org (credentialing Step 4).
- `provider_roster_credentialing_report` — Generate the Provider Roster / Credentialing (Medicaid readiness) report for an org: executive summary, invalid combos, ghost billing.
- `corpus_search` — Heavyweight filtered vector search of the approved corpus (citation-quality).
- `lazy_corpus_search` — Fast vector-only scan of the approved corpus (capture-first).
- `thread_corpus_search` — Vector-only search inside a single user-uploaded document.
- `profile_org` / `get_org_report` — Org Intelligence: profile an organization and render/fetch its report.
- `email_send` / `email_craft_send` / `email_prepare` / `email_status` / `email_suppress` — Email skill: draft, send, check status, and manage suppression. (Confirmed: all five are `@mcp.tool()` functions on the primary MCP server.)
- `appeals_lookup_rules` / `appeals_get_playbook` / `appeals_validate_claim` / `appeals_assemble_letter` (Appeals Agent) — denial-appeals rules, payor playbooks, claim validation, and full appeal-letter assembly. (Confirmed: a **separate** FastMCP server at `mobius-skills/appeals-agent/api/mcp_server.py` exposing four `@mcp.tool()`s — the draft previously omitted `appeals_assemble_letter`. These are **not** on the primary `mobius-skills-mcp` server and are **not wired into chat by default**: chat only picks them up if the operator lists the appeals server URL in the `EXTRA_MCP_URLS` env var, which the MCP adapter fans out to at registration time.)

**Standalone skill services in `mobius-skills` without a distinct chat registration** — `doc-reader`, `instant-rag`, `cmhc-cost-report`, `fl-medicaid-npi`, and `org-intelligence` run as their own FastAPI services (the full set under `mobius-skills/` also includes `email`, `google-search`, `web-scraper`, `provider-roster-credentialing`, `task-manager`, `healthcare`, `vibe`, `chat-document-upload`). Surfacing (verified against `mobius-skills-mcp/app/server.py`):
  - `org-intelligence` **is** surfaced to chat as the MCP tools `profile_org` / `get_org_report`.
  - `instant-rag` retrieval is reached indirectly: uploaded-document search runs against Chroma metadata flagged `instant_rag=true` (see `thread_corpus_search` and the `document_upload` MCP tool); there is no standalone `instant_rag` MCP tool.
  - `doc-reader`, `cmhc-cost-report`, and `fl-medicaid-npi` have **no** distinct MCP tool on the primary server and are **not** independently user-invokable chat skills; they are internal/back-end services consumed by other skills or run out-of-band. [UNVERIFIED: exact upstream caller of each was not traced end-to-end.]

**Ghost / router-owned skills** — `skills_catalog()` defines a `_ROUTER_OWNED` list of four names but appends each only if it is *not* already registered. `search_corpus` **is** a real builtin, so it is skipped; the three actually appended as synthetic (router-owned, non-`SkillSpec`) entries are `search_uploaded_document`, `healthcare_npi_lookup`, and `refuse` (a hard-stop PHI/clinical guardrail). These appear in the tool-settings UI so they can be blocked, but they dispatch in the react-loop router, not the registry — they are not independently user-invokable skills. See Doc-readiness notes.

### Framework capabilities
- **Declarative registration.** Each skill is a `SkillSpec` (name, description, handler, `inputs_schema`, category, planner visibility, mode support) registered at import time in `mobius-chat/app/skills/registry.py`. The `name` is a single source of truth: it's what the planner emits, what `dispatch()` looks up, and what the planner manifest prints — no drift.
- **Uniform envelope.** Every skill handler returns a typed `SkillEnvelope` (text, `SourceRef` citations, retrieval signal, usage, extras). In-process vs. remote is invisible to the dispatcher.
- **Computed planner manifest.** `manifest_text()` renders the registered skills into the prose the planner LLM reads, so a newly registered skill is automatically visible to the planner (no hand-maintained list).
- **Two surfaces, one implementation.** `mobius-skills-core` holds one function per capability; chat direct-imports the hot-path ones and `mobius-skills-mcp` wraps the same functions as MCP tools. Fix a bug once, both surfaces get it.
- **MCP auto-registration.** `register_mcp_skills()` (`mcp_adapter.py`) turns a remote MCP server's `list_tools` response into `SkillSpec`s, so any MCP tool becomes a dispatchable chat skill. Builtins win on name collisions; registration is best-effort (never crashes chat startup).
- **Per-user tool policy.** Skills carry a `category` (corpus, healthcare, npi, web, analytics, documents, tasks, utility, general) so the tool-settings UI can enable/disable whole themes.

## Navigation & Access
Users trigger skills with **natural language in chat** — you describe what you want and the planner selects the skill(s); there is no requirement to name a skill. Explicit steering is possible (e.g. asking to "search the web" biases toward `google_search`), and the tool-settings UI lets users enable/disable skill categories. Programmatic/`answer_tool` callers can force a specific skill via `tool_hint_override`. External MCP clients (e.g. Claude Desktop, Cursor) reach the same capabilities by pointing at the `mobius-skills-mcp` server (default `http://localhost:8006/mcp`).

## Key User Workflows
- **To look up a provider / get an NPI:** ask "what's the NPI for David Lawrence Center?" → the planner runs `org_npi_lookup` / `search_org_names` (NPPES + Florida PML), returns confidence-ranked matches with NPIs; provide an address to disambiguate via `search_org_by_address`.
- **To get a credentialing / Medicaid-readiness report:** ask "run a credentialing report for Aspire" → `provider_roster_credentialing_report` returns an executive summary (locations, NPIs, invalid combos, ghost billing) after resolving locations (Step 2) and the per-site provider roster (Step 4).
- **To answer a policy or billing question from authoritative sources:** ask a payer/Medicaid question → `search_corpus` (hybrid BM25 + vector) returns cited passages; if the corpus is thin, chat falls back to curated URLs then `google_search` + `web_scrape`. To pull the underlying file, `fetch_document` returns a download link.

## Integrations
- **Chat → skills:** the chat planner dispatches by name through the registry (`dispatch(SkillCall)` → handler → `SkillEnvelope`). Builtin handlers run in-process; MCP-backed handlers forward via `call_mcp_tool`.
- **MCP transport:** `mobius-skills-mcp` (FastMCP, port 8006) exposes **21** tools; a separate FastMCP server under `mobius-skills/appeals-agent` exposes **4** appeals tools (opt-in via `EXTRA_MCP_URLS`). These call the standalone skill services in `mobius-skills` (provider-roster-credentialing, healthcare, org-intelligence, email, etc.) and the shared `mobius-skills-core` functions over HTTP/in-process.
- **Skills → RAG / retriever:** corpus skills (`corpus_search`, `lazy_corpus_search`, `thread_corpus_search`) embed the query and run filtered vector search over the published corpus (Chroma) with Postgres metadata hydration; the chat `search_corpus` builtin runs the fuller hybrid pipeline. Web skills call the `google-search` (8004) and `web-scraper` (8002) services.

## Doc-readiness notes
- **Primary audience tag:** mixed (end users trigger skills; developers build them).
- **Solid:** the chat-side registry (`mobius-chat/app/skills/registry.py` + `builtin/*`) is authoritative and gives exact skill names + descriptions. The MCP tool list (`mobius-skills-mcp/app/server.py`) and the core library layout (`mobius-skills-core/README.md`) are clear. Registered chat builtins counted: **13** `SkillSpec`s (`search_corpus`, `fetch_document`, `document_upload_skill`, `list_thread_document_uploads`, `healthcare_query`, `google_search`, `web_scrape`, `list_tasks`, `create_task`, `resolve_task`, `transform_previous_answer`, `cached_answer_lookup`, `vibe` — verified by 13 `register(...)` calls across `builtin/*.py`). MCP tools on the primary server (`mobius-skills-mcp/app/server.py`): **21** (verified by 21 `@mcp.tool()` decorators).
- **Ambiguous / gaps:**
  - **Ghost / router-owned skills (confirmed in code):** `skills_catalog()`'s `_ROUTER_OWNED` list names `search_corpus`, `search_uploaded_document`, `healthcare_npi_lookup`, and `refuse`, but each is appended only if not already registered. `search_corpus` **is** a real builtin and is skipped, so exactly **three** synthetic entries are actually added: `search_uploaded_document`, `healthcare_npi_lookup`, and `refuse`. They dispatch in the react-loop router, so they show in the UI/manifest but are not in the registry and are not independently user-invokable. `lookup_authoritative_sources` and `ingest_url` are **confirmed not registered** anywhere — they appear only as prose references inside the `google_search` / `transform_previous_answer` skill descriptions, not as `SkillSpec`s or `@mcp.tool()`s.
  - **Analytics/market-data skills** (`get_top_orgs`, `get_org_profile`, `get_rate_benchmarks`, financial benchmarking) are **not implemented as skills**. Confirmed: these names appear only as *illustrative examples in code comments/docstrings* — the category-inference comment in `mcp_adapter.py` (line ~126) and the `analytics` category description in `registry.py` (line ~232). They are not registered `SkillSpec`s, and there are no matching `@mcp.tool()`s on the primary MCP server. Treat them as **planned / not yet available** — the `analytics` tool category exists so that if such MCP tools are later added they auto-group in the UI.
  - **Standalone services** (`doc-reader`, `instant-rag`, `cmhc-cost-report`, `fl-medicaid-npi`, `org-intelligence`, `appeals-agent`) exist under `mobius-skills` but most lack READMEs. Surfacing was traced far enough to say: `org-intelligence` → MCP `profile_org`/`get_org_report`; `appeals-agent` → separate MCP server, opt-in via `EXTRA_MCP_URLS`; `doc-reader`/`cmhc-cost-report`/`fl-medicaid-npi` → no distinct MCP tool, internal only. [UNVERIFIED: the exact internal caller of the non-surfaced services.]
  - **Analytics blind spot (confirmed):** there is **no** `skill_invocations` table in `mobius-chat` — a repo-wide grep for `skill_invocation` in `mobius-chat/` returns nothing (models or migrations). Per-skill usage is therefore not persisted to a dedicated table, confirming the memory note that skill invocations are largely invisible to analytics.
