# Skills
> The tools the chat agent can call — corpus search, document handling, healthcare lookups, the FL-Medicaid market-data analytics suite, and utility skills — plus the framework that registers them.

## Purpose
"Skills" are the tools Mobius Chat's ReAct planner can invoke to answer a question. They come from two sources: **chat builtins** (registered in-process) and **MCP tools** (auto-discovered at boot from a remote MCP server). The planner reads a single **tool manifest** each turn and picks the tool whose capabilities fit the question.

A user never names a skill — they ask a question and the planner routes it. This doc is the catalog of what the agent *can actually do today*, which is not the same as "what code exists": a tool is only usable if it's in the live manifest (see reachability below).

## Audience
- **End users** — indirectly; skills are what make chat able to answer market-data, policy, NPI, and document questions.
- **Developers** — who build skills (builtins or MCP tools) and wire the MCP server.

## Reachability (read this first)
What the agent can call = **chat builtins** + **the tools the *wired* MCP server exposes**. The wired server is set by `CHAT_SKILLS_MCP_URL` and its tools register at boot. Consequences:
- The live dev manifest has **45 tools** (re-verified 2026-07-05): ~18 builtins (incl. the new `payor_lookup` / `payor_readiness` pair) + the ~27-tool FL-Medicaid analytics/org suite from the wired MCP.
- **Email, appeals, and other `mobius-skills-mcp` tools are NOT in the wired MCP in dev** — so the agent *cannot* call them. If a user types "email this to X," the agent correctly says it has no email capability. (Email is still usable via the Email button — see *Email* below — because that's a direct proxy, not an agent tool.)
- "Code exists" ≠ "reachable." This doc marks each tool's tier.

## Catalog — chat builtins (in-process, always reachable)
| tool | what it does |
|---|---|
| `search_corpus` | Hybrid BM25 + pgvector corpus search — the single entry point for curated-corpus retrieval (the agent auto-selects the internal strategy; callers omit `mode`). |
| `fetch_document` | Resolve a corpus document by name / filename / policy ID and return a download link (the file, not the answer). |
| `healthcare_query` | Healthcare code lookup — ICD-10-CM code meanings, etc. |
| `healthcare_npi_lookup` | NPPES registry lookup for a given 10-digit NPI. |
| `document_upload_skill` | How to attach a file to the thread for downstream Q&A. |
| `list_thread_document_uploads` | List documents already attached to the thread. |
| `search_uploaded_document` | Instant-RAG — search *inside* a user-uploaded document on the thread. |
| `google_search` | Web search — last-resort external lookup. |
| `web_scrape` | Read the web from a seed URL (quick / medium / detailed). |
| `ingest_url` | Fetch a single URL and add it to the indexed corpus now. |
| `lookup_authoritative_sources` | Search Mobius's curated registry of authoritative URLs for a payer/state/topic. |
| `transform_previous_answer` | Reshape the previous answer into a new artifact — no retrieval. |
| `vibe` | A short, work-adjacent line (toast / empathy / dry observation). |
| `product_feedback` | Capture open product feedback + CSAT/CES/NPS surveys. |
| `product_help_search` | Answer "how do I use Mobius?" from the product docs (this doc's own skill). |
| `payor_lookup` | Authoritative operational fact for a payor from the **payor registry** — the source of truth for contact/access facts the corpus can't reliably ground: provider-services phone, appeals/claims fax, EDI payer ID, portal/login/eligibility/prior-auth URLs, mailing addresses, timely filing. Preferred over `search_corpus` for these; `field` accepts natural aliases (phone, appeals fax, edi, portal…). *(new 2026-07-04)* |
| `payor_readiness` | Payor readiness scorecard — how much of a payor's required docs are ingested, known coverage, grounded-doc counts, and gaps. *(new 2026-07-04)* |
| `refuse` | Hard stop — no content returned (router-owned). |

## Catalog — FL Medicaid BH market-data analytics suite (MCP, wired in dev)
These query BigQuery directly and return verified numbers — used (not `search_corpus`) for any quantitative FL-Medicaid behavioral-health market question. This suite is the **largest capability in the manifest** and was previously undocumented.

**Market totals & trends**
- `get_market_size` — total market: benes, claims, paid, KPI averages.
- `get_market_timeseries` / `get_market_share_timeseries` — year-by-year market totals / an org's share (2019–2024).
- `get_market_decomposition` — how revenue/volume splits across service lines.
- `get_market_retention` — beneficiary retention (panel hold year-over-year).
- `get_msa_map` — all MSA (zip3) market areas with org counts and market tier.

**Orgs & profiles**
- `search_orgs` — find an org by name → slug, bene counts, metadata.
- `get_org_universe` — canonical list of FL Medicaid BH orgs with metadata.
- `get_org_profile` — full financial + clinical profile for a named org.
- `get_org_service_line_profile` — per-service-line revenue/volume/KPIs for an org.
- `get_org_type_stats` — aggregate KPIs for an org *type* in a year.
- `get_org_leakage` — patient-leakage analysis for a CMHC.
- `lookup_npi` — resolve an NPI or org → full identity (name, entity type, taxonomy, address; org_slug/org_name accepted). *(re-verified in live manifest 2026-07-17)*

**Benchmarks & positioning**
- `get_top_orgs` — rank orgs by a volume metric.
- `get_org_benchmark` — an org's percentile positioning vs a peer group on all KPIs.
- `get_benchmark_dimensions` — P25/P50/P75 peer distributions for all KPIs across a dimension.
- `get_churn_benchmark` — clinician retention/churn benchmarks.

**Rates**
- `get_published_rates` — the official FL AHCA Medicaid fee schedule (ceiling rate) per HCPCS.
- `get_rate_benchmarks` — actual-paid HCPCS rate benchmarks (P25/P50/P75/P90) by provider type.
- `get_rate_trends` — monthly P50 rate trend for HCPCS by peer group.
- `get_org_rate_gap` — an org's realized rates vs market benchmarks.

**Service lines & opportunity**
- `get_service_mix` — an entity's service-line revenue mix.
- `get_service_line_opportunity` — revenue-opportunity sizing (current vs potential).
- `get_service_line_code_map` — HCPCS → service-line / AHCA category mapping.

**Entrants & meta**
- `get_entrant_analysis` — new-entrant displacement (who captured CMHC share).
- `get_fact_pack` — the full fact-pack behind the market-narrative story deck.
- `get_valid_filters` — valid filter values for the dataset in a given year.

## Credentialing, roster & appeals — is my provider enrolled and payable?
**Ask credentialing questions directly in chat — chat is now the primary access point** (the roster UI still exists; a chip links you there). Wired 2026-07 via the roster-credentialing MCP:

- `check_provider_credentialing(org_slug, npi optional)` — THE credentialing entry point.
  - **With an NPI** (single provider): NPPES validation status, FL Medicaid PML enrollment + next revalidation date, compliance flags with severity, license/Medicaid ID/taxonomy, recent change events, and a readiness verdict (clean / review_needed / action_required / incomplete). The answer includes a structured **credentialing card** (provider, org, status, flags, action link) rendered alongside the text.
  - **Without an NPI** (org panel): count breakdown by verdict, validation coverage per source (NPPES/PML/compliance, when last run), and a "providers needing attention" list with per-provider issues and deep links. Try: "credentialing report for [org]", "how is [org]'s panel doing", "NPPES errors for [org]".
  - Credentialing-keyword questions also get an **"Open Credentialing Report" action chip** linking to the full roster UI (links are chips now, not inline URLs).
- `healthcare_npi_lookup(question)` — NPPES registry lookup when you give a 10-digit NPI number.
- **Appeals** — `appeals_lookup_rules(carc, …)`, `appeals_get_playbook(payor, carc_group)`, `appeals_validate_claim(carc, …)`, `appeals_assemble_letter(carc, …)`: denial-code rules, payor playbooks, claim validation, and appeal-letter assembly; appeal-related questions also surface an Appeals link chip.
- Retired (ask via the tools above instead): `run_credentialing_report`, `run_roster_reconciliation_report`, `validate_credentialing_step`, `ask_credentialing_npi`, `find_org_locations`, `find_associated_providers_at_locations` were disconnected and no longer exist. (`lookup_npi` was listed here 07-14 but is BACK in the live manifest as of 07-17 — analytics flavor, see the suite below.)

## Task management
Chat can create and track operational tasks (credentialing follow-ups, roster gaps, etc.) via three skills added 2026-07-02 (chat commit `624f74f`), backed by the **mobius-task-manager** Cloud Run service (shared `mobius_chat` DB):
- `list_tasks` — "show open tasks", "what's pending for Acme". Filters: org, module, status, assignee, npi, run_id, severity, type, workflow.
- `create_task` — "log a follow-up for provider X". Requires org + text; optional severity/module/provider/npi/assignee.
- `resolve_task` — **to mark a task complete / done / resolved**: say "mark task `abcd1234` resolved" (full or 8-char UUID; optional note), or click **Resolve** directly on the task card in a task list.

They render an inline `task_list` UI block. **Reachability caveat:** these three were *not* present in the live deployed manifest at last pull (2026-07-03) — so they may be pending deploy or pending the manifest hand-list; verify before telling users chat can manage tasks.

**Task shape (corrections to earlier docs):** `severity` is **5 lowercase values** — `critical | warning | info | low | none` (not the 4-value "Critical/Warning/Info/Low"); `status` is **6** — `open | in_progress | resolved | dismissed | running | failed`.

**Where tasks surface:** the chat `task_list` block; the `/chat/tasks/*` REST proxy + CSV export (the task-manager `/tasks` endpoint accepts `?source_module=X` as an alias for `?module=X`, matching the DB column); the pipeline task queue and roster open-tasks; credentialing report step-cards; satellite-service lifecycle events; and chat-turn → task promotion (`MOBIUS_TASK_MANAGER_PROMOTION`, flipped on 2026-07-02). Not yet: `get_task`/`patch_task`/`dismiss_task` chat skills (v2); appeals-agent case tasks (partial).

## Framework (how skills register)
- **Builtins** — a `SkillSpec` registered at import via `register()` in `app/skills/registry.py`, imported by an **explicit** `_load_builtins()` list. To be visible to the planner it must *also* be named in the **hand-list** `curated_blocks` in `tool_manifest.py` (registered + `visible_to_planner=True` is not enough — the manifest is an explicit list).
- **MCP tools** — auto-discovered at boot from `CHAT_SKILLS_MCP_URL` and appended to the manifest under "Auto-discovered tools (from MCP)."
- **LLM stages** — a skill whose handler calls the LLM must add its stage to `_SKILL_LLM_ALLOWED_STAGES` in `main.py` (pure-retrieval skills like `search_corpus` / `product_help_search` don't).
- **Router-owned synthetic entries** — `skills_catalog()` appends a few non-`SkillSpec` names (`search_uploaded_document`, `healthcare_npi_lookup`, `refuse`) that route to real handlers; they aren't independently user-invokable skills.

## Email — how to email a conversation (LIVE)
**To email this conversation: click the "Email" button under any assistant message.** It opens a two-step dialog — choose the recipient, the scope (whole thread or last exchange), and summary-or-full-transcript → **preview the draft** → send (or re-draft). Nothing sends without your confirmation. You can email a conversation summary or the complete transcript this way today; it's live on every answer.

Behind the button: the **email service** (`mobius-email`, Cloud Run) — a send chokepoint with validation, a suppression list, rate limits, idempotency, an audit log, and a Gmail provider (SES stubbed). The button goes through the direct proxy `POST /chat/thread/{id}/email` (not an agent tool), so it works regardless of MCP wiring.

**One nuance (dev-facing):** *agentic* email — the AI itself sending email on your behalf via the `email_*` MCP tools — is **not wired in dev** (that MCP server isn't the wired one). So typing "email X to Y" and expecting the agent to send it autonomously won't work; **the Email button is the way to email a conversation**.

**Operational gotcha:** the Gmail OAuth token uses a testing-mode consent screen and **expires ~7 days**; rotate via `scripts/oauth_bootstrap.py` → `gcloud secrets versions add mobius-email-gmail-token` → bounce the revision.

## PHI detection & the HIPAA gate (LIVE)
**Does Mobius detect PHI / patient information / protected health information?** Yes — a dedicated PHI classifier (`mobius-skills/phi-classifier`) is **deployed and live** (Cloud Run dev). It checks text for the 18 HIPAA Safe-Harbor identifiers (names, dates of birth, SSN, MRN, member/beneficiary IDs, dates of service, addresses, phone/email) plus contextual quasi-identifiers (e.g. "34-yo veteran from Tampa"). Detection is layered — **regex + Presidio NER + an LLM context pass** — and the LLM pass runs on a HIPAA-locked bandit stage (Google Cloud Vertex, within Mobius's BAA boundary), so no PHI leaves the network. Stored evidence is always **masked**; raw text is never logged (categories + counts only). Recall-over-precision: when uncertain it flags.

**It now gates, not just recommends.** In the platform's current **HIPAA-NOT-allowed** default, a PHI hit is a hard stop at the point of ingestion — the classifier is called *before* anything is embedded or stored, and if PHI is found the content is not stored, not indexed, and not retrievable. This gate is live on three surfaces: **chat message pre-send** (a message with patient identifiers is blocked that turn, with an attest-to-override path for false positives), **document / instant-RAG upload** (ingestion terminated, extracted text purged), and **roster CSV/Excel upload** (fail-closed across all upload handlers). The full user-facing story — what a block looks like, false-positive override tiering, and HIPAA-allowed mode — lives in the **Data privacy, PHI & HIPAA** doc.

Contract: `POST /classify {text, document_id?}` → `{phi_flag, recommended_ceiling, confidence, identifiers_found[], phi_evidence[] (masked), classifier_version, layers_run}`. Owner: PHI Classifier agent; source of truth `mobius-skills/phi-classifier/README.md` (`/classify` section) + `docs/hipaa-phi-policy.md`.

## Not yet available / not reachable in dev
- **Agentic email / extra `mobius-skills-mcp` tools** — code exists but not in the wired MCP (dev), so the agent can't call them. Reachable only when that MCP server is deployed and wired (or via `EXTRA_MCP_URLS`). *(The `appeals_*` tools that were listed here are now in the live manifest — see the Appeals entry above.)*
- **Skill-invocation analytics** — there is still **no `skill_invocations` table**; skill usage isn't recorded per-call, so skills are invisible to analytics. (Confirmed gap.)

## Doc-readiness notes
- **Primary audience tag:** mixed (users benefit; devs build).
- **Source:** rebuilt 2026-07-03 from the **live deployed tool manifest** (`/chat/skills-manifest`) + the Email agent's inventory, superseding the 07-01 "13 builtins / 21 MCP" snapshot — which missed the entire market-data analytics suite and mis-stated reachability. Re-verified 2026-07-05 (45 tools; payor pair added; task skills still not in the manifest).
- **Reachability is env-specific:** `CHAT_SKILLS_MCP_URL` differs by environment/worktree; this catalog reflects dev. Re-pull the live manifest when documenting another env.
- **For the loop:** the Appeals agent's inventory (appeals_* tools, rules schema) is pending; per-tool parameter detail for the analytics suite lives in the manifest's auto-discovered section. Residual gaps → `docs_gap`.
