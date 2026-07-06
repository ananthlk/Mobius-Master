# Nightly Corpus + Lexicon Pipeline — Design Spec

Status: DRAFT for review · Owner: RAG/Lexicon · Date: 2026-07-01

## 1. Purpose

Close the daily loop so the corpus and lexicon that **chat retrieves against** are
fresh, complete, and correct every morning — automatically.

Two things drift during the day:

- **(a) Documents** are uploaded all day → new `documents` rows that need
  chunking → tagging → embedding → publishing.
- **(b) Lexicon maintenance** happens all day in QA → new/edited tags accumulate
  in the QA lexicon (today QA is at rev 1050/1939 while RAG is at 959/1824 and
  chat at 268/231).

The nightly pipeline publishes the new lexicon to RAG, re-tags/chunks the docs,
embeds + publishes them, cleans up stragglers, then pushes the lexicon to chat
and runs the eval — so retrieval quality is validated before the next day.

## 2. Data flow (3 databases)

```
QA lexicon (source of truth, edited all day)
   │  publish (TRUNCATE+reinsert entries, bump revision)
   ▼
RAG DB  ── policy_lexicon_entries, policy_lines, embeddable_units,
           chunk_embeddings, rag_published_embeddings, document_tags
   │  push (entries + document_tags + policy_line_tags)
   ▼
Chat DB ── the copy the JPD tagger / reranker actually reads
```

Retrieval uses `document_tags` + `policy_line_tags` (from chat) + the lexicon
entries (for query tagging). So docs must be **tagged at the current revision**
AND **published** before the chat push, or chat serves stale/partial results.

## 3. The sequence (ordered; each step gates on the previous)

All actions are existing endpoints (built 2026-07-01 unless noted). Every step is
**idempotent** — safe to re-run after a mid-pipeline failure.

### Step 1 — Publish lexicon QA → RAG (with automated tag gate)
- **Trigger:** `GET /policy/lexicon/sync-status`; run only if `qa.revision > rag.revision`.
- **Sanity gate (automated — see §4):** `POST /policy/lexicon/publish {dry_run:true}`,
  validate the delta; **abort + alert** if it fails.
- **Action:** `POST /policy/lexicon/publish` (lexicon-maintenance service).
- **Success:** `sync-status` shows `rag.revision == qa.revision`, `rag.entries == qa.entries`.
- **Idempotency:** publish is TRUNCATE+reinsert; re-running is a no-op if already equal.

### Step 2 — Retag existing docs for the new lexicon (in-place, fast)
- **Action:** `POST /admin/retag-in-place {only_stale:true}` (RAG). UPDATE-by-PK on
  existing `policy_lines`, Aho-Corasick matcher; no delete/rebuild.
- **Success:** `retag-in-place/status` `running=false`, `errors=0`; `integrity/report`
  `stale_tags == 0`.
- **Idempotency:** targets only docs where `document_tags.lexicon_revision != current`.
- **Note:** must run AFTER Step 1 so tags reflect the new lexicon.

### Step 3 — Chunk + tag new / unchunked docs (deterministic Path B)
- **Action A — docs WITH lines, no EU:** `POST /admin/build-eu-from-lines`
  (set-based copy of `policy_lines` → `embeddable_units`, ~ms/doc).
- **Action B — docs WITH pages, no lines:** `POST /admin/integrity/remediate`
  enqueues **generator='B'** chunk jobs (`extraction_enabled=false`) → build lines +
  tag (AC) + write EU. **No LLM.**
- **Success:** chunking_jobs (gen B) queue → 0; `integrity/report` `need_rechunk == 0`
  (excluding the permanent no-pages set — see §5).
- **Idempotency:** build-eu skips docs that already have EU; remediate skips docs with
  a live gen-B job.

### Step 4 — Embed → publish
- **Action:** embedding workers drain `embedding_jobs` (pending → embed → AUTO_PUBLISH_ON_EMBED
  copies to `rag_published_embeddings` + chat).
- **Gate:** poll `embedding_jobs` pending/processing → 0, OR a **time budget** (see §6).
- **Straggler catch:** `POST /admin/publish_unpublished` for any docs whose vectors exist
  but never published.
- **Success:** `integrity/report` `need_embed == 0`, `need_publish == 0`.
- **Idempotency:** re-embedding an already-published doc republishes the same vectors.

### Step 5 — Clean up stragglers + test docs
- **Report:** `GET /admin/integrity/report`. Expected residual = the permanent buckets (§5).
- **Remediate:** one more `POST /admin/integrity/remediate` pass for anything transient.
- **Smoke test:** run N canned corpus queries (a fixed test set) and assert each returns
  ≥1 result with a citation (proves the freshly-published docs are retrievable).
- **Gate to Step 6:** published fraction ≥ threshold (e.g. `published/documents_total ≥ 0.97`
  after subtracting the permanent no-pages set) AND `stale_tags == 0`. Otherwise **stop**
  (do NOT push a broken corpus to chat).

### Step 6 — Publish lexicon + tags RAG → Chat
- **Action:** `POST /policy/lexicon/push-to-chat` (copies entries + `document_tags` +
  `policy_line_tags`).
- **Cache:** post-push, chat's JPD tagger cache (300s TTL) refreshes; optionally call
  `clear_jpd_cache` if wired.
- **Success:** `sync-status` `chat.revision == rag.revision`, entries match.
- **Note:** MUST be after Steps 2–4 so chat gets the fresh `document_tags`.

### Step 7 — Invoke eval
- **Action:** trigger the eval job (the corpus/retrieval eval).
- **Purpose:** the final regression gate — catches lexicon or retrieval regressions from
  the night's changes. Results reviewed each morning.

## 4. Automated tag sanity checks (Step 1 gate)

Publish QA→RAG **only if all pass**; else abort the publish and alert (leave RAG on the
prior good revision). Compare the dry-run summary against RAG's current state:

| Check | Rule | Rationale |
|-------|------|-----------|
| Revision advanced | `qa.revision > rag.revision` | nothing to do otherwise |
| Not a mass deletion | `qa.entries ≥ 0.8 × rag.entries` | a sudden drop = corrupt/partial QA edit |
| Not an implausible explosion | `qa.entries ≤ 2.0 × rag.entries` | runaway candidate approval |
| No empty specs | 0 active entries with no `strong_phrases`/`phrases`/`aliases` | empty tags pollute matching |
| Kind sanity | each of p/d/j entry counts within [0.5×, 2×] of prior | catches a whole-kind wipe |
| Duplicate codes | 0 `(kind, code)` collisions | uniqueness invariant |

Thresholds are config (env), tuned after a few real nights. A failed gate is a
**hard stop for Step 1** but the rest of the pipeline (retag/chunk/embed of already-
published lexicon) can still proceed on the prior revision — decision below.

## 5. Straggler / quarantine policy

Some docs can never be fixed by this pipeline; they must NOT block it or churn nightly:

- **`need_reingest` (no source pages)** — e.g. 223 today. Require a full PDF→text
  re-ingest (upstream). → Write to a `corpus_quarantine` list, skip in the nightly
  chunk step, surface in the morning report. Do not retry automatically.
- **content-less (pages exist, chunk produced 0 EU)** — e.g. ~289 today. Genuinely
  empty/whitespace docs. → Same quarantine; mark `reason='no_extractable_content'`.
- **Retry cap:** a doc that fails chunk/embed 3 nights in a row → quarantine, stop retrying.

The Step-5 gate computes the publish fraction **excluding** the quarantine set, so a
stable pool of un-fixable docs doesn't hold the pipeline red forever.

## 6. Capacity, timing, idempotency

- **DB is 2-vCPU (`db-custom-2-7680`).** Heavy embed/publish contends. Options (decide):
  (i) run gentle (low worker concurrency) during a low-traffic window;
  (ii) auto-upsize the Cloud SQL tier at the start of the window and revert before the
  eval — but resize **restarts the shared instance** (affects chat + any running eval),
  so it must be scheduled when nothing else needs the DB.
- **Embed volume can be large** (a 118k-line handbook = 118k vectors; a full re-embed
  night can be millions of EU). Step 4 uses a **time budget**: embed until the queue
  drains OR the budget expires; remaining EU carry to the next night (published docs
  are still correct; unpublished ones just wait). The morning report shows the backlog.
- **Worker scaling** is a pipeline concern, not app logic: the orchestrator (or a
  pre-step) sets chunk/embed `min/maxScale`, and resets to idle at the end.
- **Idempotency invariant:** re-running the whole pipeline from scratch after any failure
  must converge, not duplicate. All steps are keyed on current state (revision mismatch,
  missing EU, unpublished), never on "did we run tonight".

## 7. Failure handling & observability

- **Per-step:** log start/end + counts; on failure, **stop the pipeline** (never push a
  half-processed corpus to chat) and emit an alert. Exception: Step-1 gate failure may
  allow Steps 2–7 on the prior revision (decision below).
- **Status surface:** a single `nightly/status` (or the per-step `/status` endpoints)
  showing which step, counts, and the morning summary (published fraction, quarantine
  size, embed backlog, eval result).
- **Re-runnable:** operator can re-invoke the pipeline any time; idempotency makes it safe.

## 8. Decisions (resolved 2026-07-01) + still-open

**Resolved:**
1. **Orchestrator form** — **script now** (`mobius-rag/scripts/run_nightly_pipeline.sh`),
   wrap corpus steps in a **UI button** next, **Cloud Scheduler** once the rhythm is proven.
2. **DB during the window** — **auto-upsize (2→8 vCPU) → revert**, on-demand in a known-safe
   window (resize restarts the shared instance; must not overlap the eval).
3. **Evals bracket the run** — **run BOTH each night**: a fresh **baseline** BEFORE the corpus
   writes and a **final** AFTER they settle, then diff (per the eval runbook,
   `eval/calibration/NIGHTLY_EVAL_RUNBOOK.md`). This supersedes the earlier "rolling = reuse
   prior night's final" idea, which only holds if RAG's corpus is provably static intra-day
   (chat/instant uploads not auto-publishing into RAG between runs) — unverified, so we don't
   assume it. Rolling is a future optimization to revisit once intra-day behavior is confirmed.
   The eval hits **RAG** (`corpus_search_agent`) so it measures *corpus* lift, independent of
   the chat push. **Serialization is mandatory:** no retag/`document_tags` writes and no
   embed/publish while a calibration is in flight → the script idles workers + waits for
   queues to drain (FREEZE) before the final run. Judge model stays locked (`gemini-2.5-pro`)
   across the bracket.
4. **Eval is measure-after (not a pre-push gate) for now** — push to chat, then run the
   updated eval and emit the lift report. Safety comes later via **staging→prod promotion**
   (validate the whole night in staging before it touches prod chat).
5. **Human-review loop** — chunking surfaces tag candidates → human approves during the day →
   they publish *next* night. New tags carry a deliberate **24h latency**; the lexicon-
   maintenance queue IS this step. Operational bottleneck = candidate volume vs review rate,
   not compute.
6. **Deploy freeze during the run** — the run sits *after* the day's last deploy; no deploys
   mid-run (they restart workers and disrupt the pipeline).

**Still open:**
- **Content-less docs (~289)** — the live gate blocker: they hold the publish fraction at
  ~0.964 (< 0.97) so the chat push is skipped every night. Decide: investigate (scanned/OCR?),
  purge like the no-page set, or **quarantine from the gate** (spec §5) so a stable pool of
  un-fixable docs doesn't hold the pipeline red forever. This is the top open item.
- **Multi-source ingestion** — confirm chat + instant-RAG docs land in `RAG.documents` (so
  "chunk docs" picks them up) vs a separate store needing a collection step.
- **Content-less docs (~289)** — investigate (scanned/OCR?), purge like the no-page set, or
  quarantine from the gate.
- **No-payer metadata orphans** — backfill fixes known-payer docs; no-payer uploads still
  need a payer (upload-time default or human review).
- **Test-doc set** — which canned queries define the Step-5 smoke test + pass bar.

## 9. Reused building blocks (already implemented)

| Step | Endpoint | Status |
|------|----------|--------|
| 1 | `POST /policy/lexicon/publish` (+ `{dry_run}`), `GET /policy/lexicon/sync-status` | built |
| 2 | `POST /admin/retag-in-place`, `/status` | built (AC matcher) |
| 3 | `POST /admin/build-eu-from-lines`, `POST /admin/integrity/remediate` | built |
| 4 | embedding workers + `AUTO_PUBLISH_ON_EMBED`, `POST /admin/publish_unpublished` | exists/built |
| 5 | `GET /admin/integrity/report`, `POST /admin/integrity/remediate` | built |
| 6 | `POST /policy/lexicon/push-to-chat` | exists |
| A/B | `POST /api/eval/calibrate/trigger` → `GET /api/eval/active` → `/runs/{id}/progress` → `/runs/{id}/calibration_summary` | exists (eval module) |

The orchestration layer (gates + scheduling + tag sanity gate + quarantine + smoke test +
the **eval bracket**: baseline/final trigger→poll→summary, freeze gates, lift diff) is the
**only net-new code**; the corpus/lexicon operations and the eval module are all in place.
Later hardening: wrap the eval in a **Cloud Run Job** (guaranteed lifecycle vs the
fire-and-forget HTTP task; runbook §fallback), the **UI button**, and **Cloud Scheduler**.
