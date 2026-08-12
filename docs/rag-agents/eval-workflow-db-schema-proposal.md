# Eval-Workflow DB Schema — Concrete Proposal for Database Ratification

> **Author:** Eval-Architect (schema/build lane). **Semantics owner:** Eval-RAG.
> **Status:** proposal for Database ratification (2026-08-05). Implements
> `eval-workflow-tooling-spec.md` §3a + §3c. Persistence layer = `eval/db.py`
> asyncpg pool (confirmed). **No migration runs until Database ratifies this +
> Ananth's direct go on the irreversible step.**

## Design principles (why this shape)
1. **Structural provenance, not policy.** The ruler-stamp gap and the empty
   pool-re-export this session were both MISSING-PERSISTENCE failures. This
   schema makes provenance a constraint, not a convention.
2. **Persist features once, fold any which way forever.** Per-query rows are a
   TABLE with pool features first-class → re-bucketing (incl. the post-ship
   top_score_percentile re-cut) is a QUERY, never a re-sweep.
3. **A published value physically cannot originate off-pipeline.** The
   published→computed→bank_run→valid_ruler FK chain makes a flash-graded or
   hand-edited value unrepresentable.

## Tables

### 1. `eval_valid_rulers` — the allowlist (Eval-RAG owns rows; adding a version = INSERT, not migration)
```sql
CREATE TABLE eval_valid_rulers (
  ruler_id            SERIAL PRIMARY KEY,
  ruler               TEXT NOT NULL,              -- e.g. 'factcheck/gemini-2.5-pro'
  fact_checker_version TEXT NOT NULL,             -- e.g. 'fact_check_v1.2026-07-31'
  added_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  added_by            TEXT NOT NULL,
  UNIQUE (ruler, fact_checker_version)
);
-- seed (§6a): ('factcheck/gemini-2.5-pro','fact_check_v1.2026-07-31')
```

### 2. `eval_population_rules` — versioned ruleset (Eval-RAG owns; bumped on rule change)
```sql
CREATE TABLE eval_population_rules (
  population_rules_version INT PRIMARY KEY,
  definition          JSONB NOT NULL,            -- ONLY machine-readable logic: {field, population, formula} per rule + meta_rule. NO "why" prose (that lives in spec §6b). Fully determines computation AND comparability.
  spec_ref            TEXT NOT NULL,             -- pin to the rationale: spec §6b at the git commit/tag current when this version was ratified (so immutable logic isn't orphaned from its explanation)
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- IMMUTABLE / append-only: never UPDATE a row. Version bumps ONLY on population/formula
-- change (not wording — wording edits touch the spec, not the DB). This extends the
-- provenance guarantee to the RULES: an auditor proves the logic a cell was computed
-- under never changed.
-- seed: version=1, spec_ref=<§6b @ ratification commit>, definition = the §6b logical rules:
--   recall_lift{full-pop,failures-0,mean(recall)} / accuracy_estimate{same-pop,
--   clamp01(mean(answer_recall,None→0)/mean(recall))} / authority{conditional-pop-nonnull,mean,+authority_n} /
--   k0{round(n-weighted-mean-capacity)} / latency_p50_ms{round(median(fillers_ms))} +
--   meta_rule{recall None=gap→EXCLUDE, 0.0=real-zero→INCLUDE}.
```

### 3. `eval_bank_runs` — one comprehensive sweep
```sql
CREATE TABLE eval_bank_runs (
  bank_run_id         UUID PRIMARY KEY,
  ruler_id            INT NOT NULL REFERENCES eval_valid_rulers(ruler_id),  -- ★ locked-ruler is an FK, not a string
  corpus_version      TEXT,
  query_set           TEXT NOT NULL,             -- which bank (e.g. 'cmhc_v1')
  status              TEXT NOT NULL,             -- 'running'|'done'|'failed'
  started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at         TIMESTAMPTZ
);
```
**★ The FK to eval_valid_rulers is the structural locked-ruler enforcement** — a run graded by anything not on the allowlist cannot be recorded with a valid ruler_id.

### 4. `eval_bank_run_rows` — per-query observations (PriorsLabRow SUPERSET; the fold consumes these)
```sql
CREATE TABLE eval_bank_run_rows (
  row_id              BIGSERIAL PRIMARY KEY,
  bank_run_id         UUID NOT NULL REFERENCES eval_bank_runs(bank_run_id),
  query_id            TEXT NOT NULL,
  caller_mode         TEXT NOT NULL,
  strategy            TEXT NOT NULL,
  -- grading outputs (recompute-a-cell needs ALL of these)
  recall              REAL,     -- chunk recall; NULL = grading gap (exclude), 0.0 = real zero (include)
  recall_answer       REAL,     -- NULL on zero-output
  authority           REAL,     -- NULL on zero-output (nothing to judge)
  n_contradicted      INT,
  n_hallucinated_claims INT,
  n_facts_total       INT,
  -- pool features (★ the missing cols this session — enable feature-parameter bucketing as a QUERY)
  top_score_percentile REAL,
  distinct_content_topk INT,
  pool_size           INT,
  capacity            INT,      -- real fill_depth capacity
  fillers_ms          REAL,     -- real per-strategy latency
  UNIQUE (bank_run_id, query_id, caller_mode, strategy)
);
```

### 5. `eval_computed_cells` — a folded cell
```sql
CREATE TABLE eval_computed_cells (
  cell_id             BIGSERIAL PRIMARY KEY,
  bank_run_id         UUID NOT NULL REFERENCES eval_bank_runs(bank_run_id),
  depth_bucket        INT NOT NULL,
  strategy            TEXT NOT NULL,
  caller_mode         TEXT,     -- NULL when pooled across modes
  -- value fields (appliable set; cost_per_attempt intentionally absent — never derived)
  recall_lift         REAL, accuracy_estimate REAL, authority REAL,
  authority_measured_at_bucket INT,  -- authority hybrid provenance (may differ from depth_bucket)
  n INT NOT NULL, authority_n INT, k0 INT, latency_p50_ms INT,
  reconciliation_ok   BOOLEAN NOT NULL,
  population_rules_version INT NOT NULL REFERENCES eval_population_rules(population_rules_version),
  cell_sha256         TEXT NOT NULL,   -- canonical hash of the 4dp appliable fields (see §Canonical sha)
  warnings            JSONB,
  computed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (bank_run_id, depth_bucket, strategy, caller_mode)
);
```

### 6. `eval_published_priors` — audit trail of what landed in priors_bootstrap.yaml
```sql
CREATE TABLE eval_published_priors (
  publish_id          BIGSERIAL PRIMARY KEY,
  depth_bucket        INT NOT NULL,
  strategy            TEXT NOT NULL,
  cell_id             BIGINT NOT NULL REFERENCES eval_computed_cells(cell_id),  -- ★ FK chain: published → computed → bank_run → valid_ruler
  cell_sha256         TEXT NOT NULL,           -- copied for tamper-evidence
  -- denormalized provenance (audit reads join-free; survives bank_run archival)
  ruler               TEXT NOT NULL,
  fact_checker_version TEXT NOT NULL,
  population_rules_version INT NOT NULL,
  n                   INT NOT NULL,
  published_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_by        TEXT NOT NULL
);
```
**★ The FK chain published_priors → computed_cells → bank_runs → valid_rulers is the whole integrity spine.** A published value with no locked-ruler ancestor is unrepresentable. The denormalized ruler/rules/n let an audit answer "what produced this live value" without walking the chain, while the FK guarantees the chain exists.

## Canonical `cell_sha256` (the meet-point: Eval-RAG defines field-set+precision, I spec bytes)
- **Field set (Eval-RAG):** the appliable fields = {recall_lift, accuracy_estimate, authority, n, k0, latency_p50_ms} (= `PriorsCell.to_priors_dict()` keys; cost omitted).
- **Precision (Eval-RAG):** floats rounded to 4 decimals (the stored precision) BEFORE hashing.
- **Byte serialization (mine):** `json.dumps(fields, sort_keys=True, separators=(',',':'))` with floats formatted as fixed 4-decimal strings (`f"{v:.4f}"`, not raw repr) and explicit `null` for None; UTF-8; SHA-256 hex. Deterministic across processes/years → §102 recompute-and-compare works.

## Authority hybrid (per the converged decision)
- `authority` on `eval_computed_cells` is the per-STRATEGY base + `authority_measured_at_bucket`/`authority_n` provenance.
- Optional per-(depth,strategy) OVERRIDE rows carry their OWN measured_at_bucket/authority_n (provenance travels with the resolved value).
- **Gate resolution invariant (enforced in the apply/read layer): override-if-present-else-base, NEVER NULL** — prevents the default-1.0 citable-gate bug from recurring at unmeasured depths.

## Open questions for Database
1. **Schema/namespace** — new `eval` schema, or `public`? eval/db.py's pool targets which DB (the RAG DB)? Confirm the home.
2. **Migration approach** — is there an eval migration runner, or raw DDL via `eval.db.execute`? How do we version these table creations?
3. **`eval_bank_run_rows` at scale** — I chose a rows TABLE over a blob-ref (so re-bucketing is a query). At 264 rows/run × many runs this is small; confirm indexing (bank_run_id, and (query_id,strategy) for the fold) and any partitioning threshold.
4. **`eval_published_priors` retention/versioning** — append-only audit (never UPDATE/DELETE)? Retention policy?
5. **Cross-DB** — priors_bootstrap.yaml is a file; these tables are the compute/audit side. Confirm no live-serving read path depends on these tables yet (Phase 1 = file stays authoritative, DB is compute+audit).

_Ratify the six tables + the FK-chain constraint + the canonical-sha contract, and I build the compute/apply endpoints on top. Irreversible migration execution holds for Ananth's direct go._
