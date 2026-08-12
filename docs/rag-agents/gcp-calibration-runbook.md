# GCP Calibration Runbook — turnkey run spec (Eval, 2026-07-24)

> **PREREQUISITE (critical path, verified 2026-07-24):** a fresh `git clone`
> gets whatever is PUSHED to origin — currently HEAD `0779feb` (a DB migration),
> which has NONE of the retriever refactor, the grading harness, or the
> forced-chunks artifact (all uncommitted/untracked across sessions). So the
> Cloud Shell path below CANNOT run until {retriever refactor + `scripts/prefix_grade.py`
> + `scripts/prefix_grade_3mode.py` + `eval/artifacts/forced_filler_bank_run.json`}
> are committed AND pushed to a branch Cloud Shell clones (NOT main/HEAD). This
> is a multi-session commit-coordination step and is the real gate — bigger than
> the deploy (which builds from the local dir and tolerates uncommitted code; a
> clone does not). Until that push lands, "turnkey" means the commands are
> ready, not that a clone works.

Why GCP (four converged reasons): (1) judge lock — only the LLM Manager proxy
resolves `rag_eval_adjudicate` to the locked gemini-2.5-pro; local bypasses it;
(2) mode-(b) synthesis 429s locally; (3) DB contention on the local proxy;
(4) REAL per-stage latency — unmeasurable locally, and it's what the router's
gates + the ops/representativeness side need. Provisioning/quota is an
Ananth/infra step; this makes the stand-up a checklist.

## 1. Environment variables

| Var | Value | Why |
|---|---|---|
| `CHAT_INTERNAL_LLM_URL` | the LLM Manager proxy endpoint | routes the judge → model_registry → **locked gemini-2.5-pro**. Its absence is what triggers the dev-fallback bypass. |
| `MOBIUS_SKILL_LLM_INTERNAL_KEY` | secret `mobius-skill-llm-internal-key` | proxy auth header `X-Mobius-Skill-LLM-Key`. Judge 400s without it. |
| `CHAT_RAG_DATABASE_URL` | Cloud SQL mobius_rag (in-cluster) | retrieval harness DB; NOT a local cloud-sql-proxy (reason 3). Preferred name; `RAG_DATABASE_URL`/`DATABASE_URL` also accepted. |
| `VERTEX_PROJECT_ID` | mobius-os-dev (or target) | embeddings + Vertex region base. |
| `VERTEX_LOCATION` | us-central1 | region for the pro roster. |
| `ENV` | `prod` | so the dev-fallback path is never even eligible. |
| `DB_IDLE_IN_TXN_TIMEOUT_MS` | `120000` | the leaked-txn guardrail (per RAG connection-leak note). |

Both proxy vars MUST be set — the harness is now **fail-closed** on their
absence (see §3).

## 2. Entry point + invocation

Two harnesses run on GCP; they are separate concerns:

**A. Retrieval harness** — produces the ranked chunks per (query, strategy)
AND the per-stage latency (§5). Needs the DB. This is the forced-matrix run
(every strategy × every query, full top-X). Output feeds the grader.

**B. Grading harness** — `scripts/prefix_grade.py`, grades top-K prefixes
through the locked judge. Needs the proxy.

Committed + pushed on branch **retriever-answer-engine** (commit 4d6eb75).
Cloud Shell block (Ananth runs it — his identity reaches the private proxy +
Secret Manager). Clone the BRANCH (main is still 0779feb), and the repo is
pyproject-based (`pip install -e .`, there is no requirements.txt):

```bash
git clone -b retriever-answer-engine https://github.com/ananthlk/Mobius-RAG.git mobius-rag && cd mobius-rag
python3 -m venv .venv && .venv/bin/pip install -e .
export CHAT_INTERNAL_LLM_URL="https://mobius-chat-ortabkknqa-uc.a.run.app/internal/skill-llm"
export MOBIUS_SKILL_LLM_INTERNAL_KEY="$(gcloud secrets versions access latest --secret=mobius-skill-llm-internal-key --project=mobius-os-dev)"
export CHAT_RAG_DATABASE_URL="postgresql+asyncpg://postgres:x@/mobius_rag?host=/cloudsql/mobius-os-dev:us-central1:mobius-platform-dev-db"
export VERTEX_PROJECT_ID="mobius-os-dev" VERTEX_LOCATION="us-central1" ENV=prod
.venv/bin/python scripts/prefix_grade_3mode.py --legs a,b,c,d,s --ks 1,3,5,10   # 3-mode
# or scripts/prefix_grade.py for mode (a) only. → eval/artifacts/recall_curves_3mode.json (+ __judge_lock__)
```

**The DB URL is import-guard-only — NO reachable DB / no Cloud SQL proxy needed
for grading (Eval verified in config.py 2026-07-24):** config validates the URL
STRING (raises if unset) but never connects; `create_async_engine` at import is
lazy (connects on first session use, which the grader never does — it grades
pre-retrieved chunks); `assert_hosted_config()` under ENV=prod checks only that
VERTEX_PROJECT_ID / proxy URL / key are PRESENT, no DB connect. So ENV=prod is
safe and the cloudsql-socket URL never has to resolve. (This holds for GRADING
only; the retrieval harness + /api/retriever/answer DO query the DB — those run
on the deployed service, which has real cloudsql connectivity.)

Phasing (honest status): mode (a) grader exists now. Mode (c) = the
fact_checker reference-free wrapper (small, next). Mode (b) = the synthesis
step (needs the authority fix + prod-synth parity), added after. Bank: 22
labeled today; the target 100 (legacy-corpus_search-sourced, tiered-weighted,
primary-gated) is the long pole — the full 100q × 3-mode batch waits on it.

**Sharding:** if the pro quota bump (§4) lands, one job runs the full matrix.
If quota stays tight, shard by MODE (run a, then c, then b) and within a mode
by depth_bucket — each shard is an independent `prefix_grade` invocation over a
bank subset, results merge (the artifact is append-only per query).

## 3. Fail-closed guard — DONE (load-bearing)

`prefix_grade.py` now REFUSES to run if `CHAT_INTERNAL_LLM_URL` /
`MOBIUS_SKILL_LLM_INTERNAL_KEY` are unset (→ it would dev-fall-back to an
unlocked model), and ABORTS the batch if the actual judge model resolves to
anything but `gemini-2.5-pro` (belt-and-suspenders, checked after the first
grade). We can never again produce authoritative numbers on the wrong ruler.
Escape hatch: `--allow-fallback` exists ONLY for the known-unlocked local
methodology run; it must never be used for authoritative GCP numbers, and every
artifact carries a `__judge_lock__` stamp recording the models actually seen.

## 4. Vertex gemini-2.5-pro quota estimate

Full 3-mode pass over the 100q bank, forced matrix (5 legs × 4 K-checkpoints):
- mode (a): ~2,000 judge calls · mode (c): ~2,000 · mode (b): ~2,000 synth +
  ~2,000 judge ≈ **~8,000 pro-stage calls** (before c/d variance repeats).
- pro ≈ 8s/call (model_registry ema_latency). Sequential ≈ 18h; at ~10
  concurrent ≈ ~2h, which is **~75 RPM sustained**.
- Already 429-ing at low concurrency → current quota is under that.

**Ask (concrete, not a guess):** bump gemini-2.5-pro in `VERTEX_LOCATION` to
**≥ 120 RPM and ≥ 1M TPM** (headroom for ~10-way concurrency + retry backoff;
chunk-carrying prompts run ~4-8k tokens). At 120 RPM the full pass finishes
comfortably in ~1-2h without 429 noise corrupting rows.

## 5. Latency capture

Per-stage latency (gate / pool / router / fillers / synthesis) comes from the
RETRIEVAL harness (§2A), which records `*_ms` per stage per query — NOT from
the grader (`prefix_grade` scores pre-retrieved chunks, so it has no pipeline
timing). Therefore: to get REAL latency, the retrieval harness must run ON GCP
against the in-cluster DB (local numbers are meaningless — reason 4). Confirmed
the retrieval harness emits per-strategy `router_ms` / `fillers_ms` / `pool_ms`
already; on GCP these become the authoritative latency the router's gates need.

## Handoff

Once provisioned with §1's env + §4's quota, run §2A (retrieval, gets
chunks+latency) then §2B (grading, gets scores) — the fail-closed guard (§3)
guarantees the ruler is the locked pro or the run refuses. Authoritative numbers
replace the current dev-fallback-graded offline set.
