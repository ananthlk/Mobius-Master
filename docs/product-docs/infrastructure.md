# Supporting Infrastructure
> One-line: the developer-facing modules that power Mobius behind the scenes

## Overview

Mobius is a multi-repo system: each product surface (chat, RAG, OS, credentialing, roster) lives in its own repo and can run standalone. That structure only works because a set of shared, developer-facing modules hold the seams together — a common design language, one place for shared credentials, a typed contract layer so modules don't invent their own payload shapes, a centralized database gateway, a single migration runner, a dbt-managed datalake, an extracted answer-cache service, and QA/eval harnesses that measure quality. None of these are things an end user touches directly; they exist so the product modules stay consistent, testable, and loosely coupled. This page gives a short profile of each.

## Modules

### mobius-design
- **Purpose:** Shared branding and style tokens for all Mobius UIs — the single source of truth for logo and theme.
- **Capabilities:**
  - Canonical logo assets (`assets/logo.svg`, `logo-dark.svg`) for light/dark backgrounds.
  - CSS custom-property token files: `tokens.css` (light) + `tokens-dark.css` (dark overrides via `.dark` / `[data-theme="dark"]`).
  - Programmatic logo spec (`logo-spec.ts` / `logo-spec.json`) — path + colors for JS/TS-drawn logos (e.g. browser extension).
  - `BRANDING.md` — the canonical **Mobius Brand & UI Guidelines v1** (effective 2026-07-03), governance owner Ananth. Every module MUST: import `tokens.css` (never fork/redefine a `--mobius-*` token), use `var(--mobius-font-sans|mono)` (no font literals) and `var(--mobius-text-*)` (no raw px), carry the Mobius mark in the main header, and resolve compat aliases (`--surface`/`--border`/`--text-primary`) to `var(--mobius-*)`.
  - **Semantic accents** (chosen by meaning, not style): `--mobius-accent` #3B82F6 = action/links/focus · `--mobius-indigo` #5B5EF4 = runs/pipeline · `--mobius-violet` #7C3AED = credentialing/policy · `--mobius-emerald` #10B981 = roster/ops. **Banned as accent:** #1A73E8 (Google blue), #58A6FF (GitHub blue).
  - **Enforcement:** a shared `mobius-design/tests/` audit (8 checks incl. no-font-literals + no-raw-px) — a red audit **blocks merge**. New colour/size/component goes through `BRANDING.md` via PR first, never inlined.
- **Consumed by:** Every Mobius frontend (chat UI, story-UI, OS, landing pages, document viewer) that imports tokens or references the logo. The v1 audit gates their merges.
- **Audience tag:** dev

### mobius-config
- **Purpose:** Canonical place to define and inject shared credentials and environment variables across modules when working locally across repos.
- **Capabilities:**
  - `.env.example` — canonical list of env vars used by all modules; copied to a gitignored `.env`.
  - `env_helper.load_env(module_root)` — resolves a var from the module's own env first, falling back to the shared global; auto-discovers a service-account JSON in `credentials/` when `GOOGLE_APPLICATION_CREDENTIALS` is unset/placeholder.
  - `inject_env.sh` — copies the shared `.env` into a target module's directory.
  - `run_with_shared_env.sh` — sources the shared `.env` and runs a command from a module's own root (no copy).
  - `env_doctor.py`, `env-matrix.md` — diagnostics and a per-module var-to-module matrix.
- **Consumed by:** mobius-chat, mobius-rag, mobius-os, mobius-dbt, mobius-user, mobius-migrations — any module needing shared credentials. Optional (each repo can still keep its own `.env`).
- **Audience tag:** dev

### mobius-dbt
- **Purpose:** dbt-managed BigQuery datalake. Phase 1 scope: consume RAG's published embeddings, replicate them into a BigQuery landing dataset, and expose a contracted mart that syncs to the chat server.
- **Capabilities:**
  - Ingestion script (`scripts/ingest_rag_to_landing.py`) copies RAG's `rag_published_embeddings` from Postgres into BigQuery `landing_rag`.
  - One contracted dbt mart (`published_rag_embeddings` in `marts/chat_rag/`) with dbt contract + tests (unique/not_null).
  - Sync step pushes mart → Chat Postgres (`published_rag_metadata`) + Vertex AI Vector Search.
  - FastAPI "Job UI" (`app/main.py`, port 6500) to trigger the pipeline, pick Origin/Destination (Dev/Prod/Staging), and watch run status; run metadata in a SQLite `data/jobs.db`.
  - Cloud Run deploy (`deploy_cloudrun_dev.sh`, Dockerfile).
- **Consumed by:** mobius-chat (receives the synced mart + Vertex index); reads from mobius-rag (source of truth for published embeddings).
- **Audience tag:** dev

### mobius-qa and mobius-qa-modules
- **Purpose:** QA/eval tooling for Mobius — test bots, curated question banks, retrieval evaluations, and lexicon-maintenance UI. `mobius-qa` is the primary tree (holds all four sub-apps: `mobius-chat-qa`, `retrieval-eval`, `retrieval-eval-studio`, `lexicon-maintenance`); `mobius-qa-modules` is a re-packaging of a deployable subset — it re-nests `mobius-qa/lexicon-maintenance` (with a built frontend `dist/`) and `mobius-qa/retrieval-eval-studio`, plus a static `landing/retrieval-eval/` page. `mobius-qa` is canonical.
- **Capabilities:**
  - `mobius-chat-qa` — chat test bot: curated questions, LLM adjudication, thumbs-up/down scoring, reports (the suite driven by the top-level `meval` harness).
  - `retrieval-eval` — retrieval-only bake-off against dev Vertex Vector Search (e.g. hier-only vs atomic+hier strategies), outputs CSV/JSONL/summary + distribution plots.
  - `lexicon-maintenance` — FastAPI + frontend app (deployable to Cloud Run) for reviewing/curating lexicon tags and candidate phrases, with revision bumping.
  - `retrieval-eval-studio` — FastAPI backend + UI for retrieval eval (a full ~1,790-line `app/main.py`, not a skeleton; present in both `mobius-qa` and the `mobius-qa-modules` copy, which are near-identical).
- **Consumed by:** Developers/operators evaluating chat + RAG quality; feeds RAG lexicon/retag work. Not consumed at runtime by product modules.
- **Audience tag:** dev

### mobius-answer-cache
- **Purpose:** Standalone skill service that owns chat's answer cache (semantic reuse of past answers) — carved out of mobius-chat to decouple chat from the cache backend and give the cache rows a queryable history.
- **Capabilities:**
  - `cache_lookup` skill (read path) — semantic retrieval of past answers by question similarity with caller filters (max_age_days, payer/state/program, thumbs_down…).
  - `cache_write` skill (write path) — persists a turn's final answer + sources + metadata.
  - Admin endpoints — query cache rows as turn history (per-thread history, top repeated questions, hit rate per caller).
  - Pluggable backends (Chroma today → pgvector target) via a phased rollout; FastAPI service (`app/main.py`) + Cloud Run Dockerfile + pgvector migration.
- **Consumed by:** mobius-chat (via HTTP skill calls, mirroring the `corpus_search` skill pattern).
- **Audience tag:** dev
- **Status caveat:** Carve-out bundle — per its README, "not yet a deployed service" (confirmed: the bundle is meant to be handed to a new repo and brought up). Phased plan (Phase 0 Chroma HTTP-shim → Phase 1 pgvector backend, currently a stub → later retire Chroma) with several open questions unresolved. **Note the fleet standard (2026-07-13): pgvector is the mandated vector store — any bring-up of this bundle should go straight to the pgvector backend, not the Chroma shim.**

### mobius-contracts
- **Purpose:** Typed Pydantic contracts shared across modules — the seam that stops each module inventing its own envelope shape and versioning scheme.
- **Capabilities:**
  - Envelope models: `assistant.py` (UI blocks a chat turn renders), `tool_output.py` (internal summary + user-facing detail), `credentialing.py` (workflow options + assertions), `error.py`.
  - Enforced rules: single `version: Literal["v1"]` per envelope; no `dict[str, Any]` in public models; every envelope declares a `schema_name` discriminator for union routing/validation.
  - Installable package (`pyproject.toml`, `mobius_contracts.egg-info`); future homes for `events/` and typed HTTP `clients/`.
- **Consumed by:** mobius-chat, mobius-rag, credentialing, strategy, task-manager — any producer/consumer of cross-module payloads.
- **Audience tag:** dev

### mobius-db-agent
- **Purpose:** Centralized database-access gateway exposed as an MCP server — so modules stop opening their own connection pools and hardcoding DB URLs, and access is governed by per-service manifests.
- **Capabilities:**
  - MCP server (`python -m app`, FastMCP, streamable-http, default port 8008) fronting the chat/rag/user/qa databases.
  - Thin client (`db_client.py`) copied into each consumer: `db_query` (read), `db_execute` (write, no DDL), `db_get_schema` (discovery).
  - Manifest-based access control (`manifests/*.yml`) — per-service read/write table allowlists + row/timeout limits, keyed to `DB_AGENT_CALLER_ID`.
  - Automatic fallback to direct psycopg2 (`_fallback: true`) if the agent is unreachable, so consumers keep working.
  - Metrics + contract validation modules (`metrics.py`, `contracts.py`).
- **Consumed by:** mobius-os, mobius-chat, mobius-rag, credentialing, task-manager, doc-reader (each has a manifest in `manifests/`).
- **Audience tag:** dev

### mobius-migrations
- **Purpose:** Single entrypoint to run database migrations for all Mobius modules (chat, rag, os, user) in dev or prod.
- **Capabilities:**
  - CLI: `python run_migrations.py --env dev|prod [--module chat|rag|os|user]`.
  - Per-module runners: chat = ordered SQL files; rag = Python migrations; os + user = Alembic `upgrade head`.
  - Does not load env files itself (deliberate security choice — deploy pipelines set env explicitly); caller supplies the right DB URLs per env.
  - Optional `VERSION` file so pipelines can record which migration package was applied.
- **Consumed by:** Deploy pipelines / operators for mobius-chat, mobius-rag, mobius-os, mobius-user databases.
- **Audience tag:** dev

### meval
- **Purpose:** Top-level shell wrapper that runs the full Mobius chat eval suite from the repo root — the convenient front door to `mobius-qa/mobius-chat-qa`.
- **Capabilities:**
  - Runs the baseline sprint against `eval_suite.yaml` (34 tests) via `run_eval.py`, with shared `.venv` and mobius-chat on `PYTHONPATH`.
  - Flags: `--dry-run`, `--no-adjudicate`, `--tests T01,T16`, `--report`; env knobs like `MOBIUS_EVAL_MAX_WAIT_SEC`.
  - Sources chat + config `.env`; streams to a timestamped log and writes a baseline markdown report under `mobius-qa/mobius-chat-qa/reports/`.
  - Aware of credentialing tests (T23+) needing the provider-roster-credentialing service on 8011.
- **Consumed by:** Developers running chat quality regressions; wraps `mobius-qa`.
- **Audience tag:** dev

## Doc-readiness notes

- **Overall audience tag:** dev. None of these modules are end-user-facing; all documentation here targets Mobius engineers/operators.
- **Worth full user (developer) docs:**
  - **mobius-db-agent** — has a real integration contract (manifests, client API, fallback semantics) that every new module must follow; deserves a complete, maintained doc.
  - **mobius-contracts** — the cross-module payload standard; worth documenting so producers/consumers stay compliant.
  - **mobius-config** — practical onboarding pain-point (credentials/env); a solid setup guide pays off.
  - **mobius-dbt** and **mobius-migrations** — worth full docs as operational runbooks (pipeline + migration procedures).
- **Just a stub is fine:**
  - **mobius-design** — small, self-explanatory; the existing README + STYLE_GUIDELINES cover it.
  - **meval** — thin wrapper; a stub pointing to `mobius-qa/mobius-chat-qa` is enough.
  - **mobius-answer-cache** — stub only until it's actually deployed; flag as "planned/carve-out," not "live."
- **Gaps a human must fill:**
  - Whether **mobius-answer-cache** has since progressed past the carve-out bundle (any repo split / first deploy) — code confirms it is not yet deployed.
  - Whether **mobius-db-agent** is deployed as a shared service beyond local `mstart` (only a `DB_AGENT_MCP_URL=http://localhost:8008/mcp` local default is code-visible), and how the manifest allowlists are enforced/audited in prod.
  - Confirm the set of frontends actually importing **mobius-design** tokens (assumed, not code-verified here).
