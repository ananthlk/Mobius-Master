# Eval Workflow Tooling — Scoping Spec

> **Owner:** Eval-RAG + Eval-architect. **Status:** scoping (2026-08-05).
> **Directive:** Ananth — give the trace/priors tooling a real UX + persistence
> lift; Eval owns the eval-workflow layer, replacing the ad-hoc scripts
> (`derive_priors.py`, `run_matrix.py`, `calibrate.py`, `analyze_matrix.py`).
> This spec is what UX (Platform Architects) and Database design against.

## 1. The ownership seam

- **Retriever owns trace-GENERATION** — the pipeline run itself
  (orchestrator / pool / fillers / telemetry, the `/admin/trace-explorer/run*`
  endpoints). Output: **bank-run rows** (`sweep_per_query_rows.json`-shaped:
  one `(query, caller_mode, strategy)` observation with recall / recall_answer /
  authority / pool_size / capacity / fillers_ms / top_score_percentile / …).
- **Eval owns the EVAL-WORKFLOW layer on top** — question bank, comprehensive
  sweeps, priors compute/publish/retrieve, DB persistence, the UX.
- **The handoff is the rows.** Retriever produces them; Eval folds them into
  priors. This is how we already operate — Retriever ran the matrix, Eval owned
  grading/priors/population semantics.

**Eval-internal lanes:**
- **Eval-RAG (semantics):** grading, the population-consistency rules, priors
  field definitions, calibration methodology, what a sweep measures, sign-off on
  what gets published.
- **Eval-architect (schema/build):** DB tables, the compute/apply endpoints, the
  persistence pipeline, migration of the ad-hoc scripts.

## 2. Foundation that already exists (build on it, do not rebuild)

`app/services/retriever/priors_lab.py` (migrates to `eval/` ownership) —
audited firsthand 2026-08-05, correctly encodes the ratified rules:
- `compute_cell` — `recall_lift` and `accuracy_estimate` over the FULL attempt
  population (failures as 0, same population, since both are multiplied into the
  chain at `allocation.py:397`); `authority` conditional/gate-field with its own
  `authority_n`; `k0` = n-weighted mean of real observed capacity; latency =
  median real `fillers_ms`. Built-in reconciliation flag
  (`recall_lift × accuracy_estimate ≈ mean answer_recall`).
- `derive_bucket_cutoffs` — quantile cutoffs from the REAL distribution, not the
  hardcoded `50/200/500/5000` (which leave 4 of 5 buckets empty on CMHC).
- `apply_cell_to_yaml_text` — comment-preserving, refuses to clobber curated
  inline comments, **round-trip-verifies** (parses + reads back each field,
  refuses to save on mismatch). `cell_sha256` — provenance hash over exactly the
  appliable fields.

**Why this matters:** compute → apply → readback-verify closes the
manual-transcription gap. (The `n=66` contamination error on 2026-08-05 happened
in a hand-edit; this pipeline makes that class of error structurally impossible —
a value that doesn't reconcile never lands.)

Three additive extensions (from the audit):
1. Defensive `recall or 0.0`; document `recall=None` (grading gap → exclude) vs
   `recall=0.0` (real zero retrieval → include).
2. Explicit warning when the efficiency>1 clamp bites (c's reverse-RAG case).
3. `derive_bucket_cutoffs` takes a **feature parameter** (pool_size OR
   top_score_percentile) — the post-ship recut must cut on the feature that
   actually varies (top_score_percentile), not pool_size (degenerate here).

## 3. The three-layer build

### 3a. DB persistence (via `eval/db.py` asyncpg pool)

Replaces the GCS-blob-metadata hack (metadata-only listing, no query/filter/
audit). Three persisted entities:

- **`eval_bank_runs`** — one comprehensive sweep: which queries × strategies ×
  modes were graded, the **locked-ruler version** (`factcheck/gemini-2.5-pro`,
  fact_checker_version), corpus version, timestamp, status. The per-query rows
  hang off this (either a rows table or a blob ref keyed by run_id).
- **`eval_computed_cells`** — a folded cell: `(bank_run_id, bucket, strategy,
  caller_mode?)` → value fields + `n` + `authority_n` + `reconciliation_ok` +
  `population_rules_version` + `cell_sha256`.
- **`eval_published_priors`** — the audit trail of what actually landed in
  `priors_bootstrap.yaml`: `(depth_bucket, strategy, cell_sha256, bank_run_id,
  published_at, published_by)`. This is what makes "the value in the file traces
  to the rows that produced it" queryable.

### 3b. Question Bank management

The eval bank becomes a managed entity (today: 22 CMHC queries in a yaml).
Subsumes the logged **bank-expansion** item (22 → 150, tiered / tagged).
- Add / edit / tier (primary/secondary/tertiary must-facts) / tag (persona,
  payer, topic) queries.
- **Comprehensive sweep**: launch all strategy × mode × query for the bank
  (Retriever's run endpoints do the work; this layer orchestrates + tracks
  coverage). Distinct from today's one-job-at-a-time posture.
- **Column-presence assertion at ingest (integrity rule).** Each declared row
  column must be verified PRESENT AND NON-NULL in a real persisted row before the
  sweep counts as complete — not "the code computes it." This catches the
  recurring "computed-but-invisible" failure class at ingest (three instances so
  far: the ruler-stamp gap, the empty pool re-export, and the
  `per_slot_pool_metadata`-in-`feature_vector`-not-`feature_context` bug — all
  data that existed somewhere but was null where consumed) instead of silently
  producing null columns three layers downstream. "Verified in a real trace,"
  not "deployed," is the bar.
- Coverage view: which cells have adequate `n`, which are thin (the current
  66-row overfit ceiling on finer buckets lifts only as the bank grows).

### 3c. Compute / publish / retrieve — the provenance-sha spine

The workflow, and the answer to Ananth's "I know what's here IS in the priors":
1. **Compute** — fold a bank run into cells (`priors_lab.compute_priors_table`),
   read-only; every cell carries its `sha256` + `reconciliation_ok` + `n`.
2. **Review** — the sha-verified diff against current priors, with warnings
   (thin n, reconciliation failures, authority_n mismatch) surfaced. Eval-RAG
   sign-off gate here — nothing publishes without it.
3. **Publish** — `apply_cell_to_yaml_text` patches the cell, round-trip-verified;
   record in `eval_published_priors` with the sha.
4. **Retrieve/audit** — any priors value → its `cell_sha256` → the `bank_run_id`
   + ruler version + population + n that produced it. Recompute-and-compare-sha
   proves the file still matches its source.

**Invariant:** a published priors value's `cell_sha256` equals the sha of a
stored computed cell from a locked-ruler bank run. If they ever diverge, the
value was hand-edited off-pipeline — the audit catches it.

## 4. Sequencing & non-goals

- **Post-ship** per Ananth's ordering — the greedy ship gate is already closed on
  the current pooled `depth_3` cell; this tooling is the durable replacement, not
  a ship blocker.
- **Not in scope here:** trace generation (Retriever), the live Cloud-Run write
  path (deferred until `priors_bootstrap.yaml` moves to persistent storage — the
  container FS is ephemeral; Phase 1 stays local-file + human-approved).
- **Depends on:** the accuracy_n post-ship item folds in naturally — `n` (and
  `authority_n`) are already first-class in `PriorsCell`, so persisting them here
  is the same schema that later lets `accuracy_estimate` carry its own LB into
  the ranking.

## 5. Open questions for UX + Database

- **UX (Platform Architects):** the Question Bank surface — bank CRUD + sweep
  launch + coverage/thin-cell view + the compute→review→publish flow with the
  sha diff. Reuse the existing `trace_explorer.html` Priors Lab panel as the
  seed. What's the review/sign-off interaction (this is a gated publish)?
- **Database:** confirm `eval/db.py`'s pool is the right home; ratify the three
  tables' schema (esp. rows-table vs blob-ref for per-query rows at bank scale —
  Eval-architect's call: rows table with pool features first-class);
  the `published_priors` audit table's retention/versioning.
- **Authority grain (Eval-RAG lean: per-strategy, not per-(depth,strategy)).**
  `authority` is a source property (~constant across depth), so storing it once
  per strategy with an explicit "measured-at-bucket / n" provenance field is
  cleaner than duplicating it across depth cells (which today creates
  inconsistency: measured at bucket-3, seed-approximated elsewhere). Decide the
  grain in the schema. If kept per-(depth,strategy), unmeasured depths carry
  NULL/seed honestly rather than a propagated value that looks measured.
- **Eval-architect ↔ Eval-RAG:** I (Eval-RAG) sign off on the semantics
  (population rules, what publishes); Eval-architect builds the schema + endpoints
  + migration. Confirm the lane split before we bring UX/DB in.

## 6. Semantic contract inputs (Eval-RAG owns; the schema enforces these)

Eval-architect's schema constraints (§3a) need concrete semantic content to
enforce. These two are Eval-RAG's to define and version; the schema references
them.

### 6a. Valid-ruler allowlist (feeds the structural locked-ruler constraint)

`eval_published_priors` may only reference a `computed_cell` whose bank run's
`(ruler, fact_checker_version)` is in this allowlist. It is an **allowlist, not a
single pin** — valid versions accumulate; pinning one blocks the next legit bump.

| ruler | fact_checker_version | status |
|---|---|---|
| `factcheck/gemini-2.5-pro` | `fact_check_v1.2026-07-31` | valid (current) |

Rules: (1) only `factcheck/gemini-2.5-pro` is ever a valid ruler — flash /
dev-fallback never publish. (2) New versions are added here by Eval-RAG when a
grader change is validated. (3) Cross-version numbers are NOT comparable
(a version bump can shift scores); the allowlist gates *publish-eligibility*, not
*comparability* — comparison across versions is flagged at read time, not here.

### 6b. `population_rules_version = 1` (the ratified ruleset, denormalized onto each audit row)

The population-consistency rules a cell was computed under. Version bumps when any
rule changes; each published cell records the version that produced it.

**v1 (ratified 2026-08-05, encoded in `priors_lab.compute_cell`).** Structured
for 1:1 JSONB mapping — each rule as `{field, population, formula, why}`:

```
rule_1:
  field:      recall_lift
  population: FULL attempt population (all n rows; zero-output rows included, recall=0.0)
  formula:    mean(recall) over all n
  why:        multiplied into the chain (allocation.py:397 composes it with
              accuracy_estimate), so it must NOT condition away a strategy's own
              zero-output failures — those are real zero-recall attempts.

rule_2:
  field:      accuracy_estimate
  population: SAME full attempt population as recall_lift (zero-output answer_recall as 0)
  formula:    clamp[0,1]( mean(answer_recall, None->0) / mean(recall) )
  why:        multiplied BY recall_lift, so populations must match for the product to
              reconstruct mean answer_recall. Conditioning on "answered" overstates.
  invariant:  recall_lift * accuracy_estimate ≈ mean(answer_recall over full pop)
              (reconciliation_ok; goes FALSE when the efficiency>1 clamp bites — the
              reverse-RAG/c case — which correctly flags rather than hides it)

rule_3:
  field:      authority
  population: CONDITIONAL — only rows that produced content to judge
              (zero-output rows, authority=None, EXCLUDED)
  formula:    mean(authority) over non-null rows; authority_n = count, recorded
              separately when != cell n
  why:        standalone GATE field (strategy_authority_eligible), never multiplied,
              so population-consistency is not required; "when the strategy retrieves,
              is its content citable" is the correct conditional question.

rule_4:
  field:      k0
  population: rows with known capacity
  formula:    round( n-weighted mean of real observed per-row capacity )
  why:        capacity genuinely varies by caller_mode (copilot=7 vs default/thinking=10);
              a guessed constant mischaracterizes mode-pooled cells. k0 enters the
              capacity transform P(satisfied|k), so it must be the real observed capacity.

rule_5:
  field:      latency_p50_ms
  population: rows with known fillers_ms
  formula:    round( median(fillers_ms) )
  why:        must be per-strategy MARGINAL latency (fillers_ms), never whole-pipeline
              wall_ms — the allocator sums per-strategy budgets, so it needs each
              strategy's own marginal cost. (The d-latency saga: 13000=whole-pipeline
              WRONG, 9732=marginal p50 RIGHT.)

meta_rule (loader contract, applies to rule_1):
  recall = None  -> grading GAP  -> EXCLUDE from the mean
  recall = 0.0   -> real zero retrieval -> INCLUDE as 0
  A zero-output row (chunks_out=0) has recall=0.0, NOT None. The loader must preserve
  this — conflating them corrupts recall_lift's population.
```

This is the ruleset the ship-gate priors were folded under; it is the definition
the provenance chain proves compliance with. `population_rules_version` bumps when
any rule's population/formula changes (not on wording); each published cell records
the version that produced it.

## 7. The review-step sign-off gate (Eval-RAG owns; the human semantic gate before publish)

Between **compute** and **publish** sits a required Eval-RAG sign-off. The
structural constraints (§3a) guarantee a cell is well-FORMED (ruler locked, sha
matches, provenance complete); the sign-off gate is where the judgment the
constraints *can't* encode happens — is this value **trustworthy and sensible**,
not just valid. What the review surface presents, and what I inspect:

**Auto-verified pre-conditions (constraints already enforce; shown for confirmation):**
- `reconciliation_ok = true` — `recall_lift × accuracy_estimate ≈ mean answer_recall`.
  A `false` here is a HARD STOP: investigate (clamp-bite on efficiency>1, or a
  population error) before anything publishes. Never sign off on a non-reconciling
  cell without understanding why.
- Bank run's `(ruler, fact_checker_version) ∈ eval_valid_rulers` — confirm it's the
  intended locked-pro ruler, not a stale/wrong run.
- Provenance complete: `bank_run_id`, `ruler_version`, `population_rules_version`,
  `n`, `cell_sha256` all present.

**Semantic judgment (the actual gate — my call, per cell):**
- **Sha-diff review.** The exact value deltas vs current priors, with magnitude
  and direction. A small refinement is routine; a large swing warrants scrutiny
  (what changed in the data?). Confirm the sha I approve == the sha that publishes
  — no drift between review and write.
- **Sample adequacy (thin-n).** `n` per cell, flagged against a threshold
  (~20–30 for a stable Wilson LB — below that, leadership/rankings are within
  sampling noise, per the overfit finding). A thin cell can still publish, but the
  sign-off records that it's a low-confidence value, not a trusted one.
- **Population warnings acknowledged.** The `compute_cell` warnings — zero-output
  row count, `authority_n` vs `n` mismatch, efficiency-clamp — are context, not
  blockers, but each must be seen and understood (e.g. c's zero-output rows are
  real quality signal, not noise to wave through).
- **Comparability flag.** If this cell replaces one from a DIFFERENT
  `fact_checker_version`, the diff notes the new value is NOT directly comparable
  to the old (a version bump can shift scores). The magnitude of the delta must be
  read in that light, not as a real data movement.

**Sign-off = all pre-conditions green + each semantic item reviewed and accepted.**
Only then does `apply_cell_to_yaml_text` run (itself round-trip-verified) and the
publish record land in `eval_published_priors`. The gate is deliberately a human
step: it's where "well-formed" becomes "I stand behind this number."
