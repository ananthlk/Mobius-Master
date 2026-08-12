# Chat Refactor — DB Gate DQ-1

**Status:** PENDING 5-ARCHITECT SIGN-OFF  
**Decision Request Date:** 2026-07-24  
**Review Window:** 48 hours  
**Blocker:** LLM Agent awaiting ratification before DDL lands

---

## Decision: Extend `llm_calls` (Option A)

**Recommendation:** Extend existing `llm_calls` (020_llm_calls.sql) rather than create new parallel table.

**Rationale:** Preserves existing `022_model_performance_view.sql` + bandit training reads. Cleaner upgrade path.

---

## Column Additions (Migration A — Safe to Land First)

```sql
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS module_key TEXT;
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS template_id INT REFERENCES prompt_templates(id);
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS turn_id TEXT;
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS is_hard_pinned BOOLEAN NOT NULL DEFAULT FALSE;

-- Backfill all existing rows
UPDATE llm_calls SET variant_id = 'default' WHERE variant_id IS NULL;
```

**Safety:** All existing data preserved. No arm history changes. Nullable FK during migration.

---

## Migration B (Gated on A Complete)

**Only safe to land after Migration A backfill is verified.**

```sql
-- Update model-performance view to include variant_id
ALTER TABLE 022_model_performance_by_stage ADD COLUMN IF NOT EXISTS variant_id TEXT;

-- Add variant_id to unique index
CREATE UNIQUE INDEX IF NOT EXISTS idx_llm_calls_arm_key 
  ON llm_calls (provider, module_key, variant_id, ab_variant);
```

**Gate:** Every row must have variant_id='default' before this migration lands.

---

## New Tables (Greenfield)

### `prompt_templates`

```sql
CREATE TABLE IF NOT EXISTS prompt_templates (
    id            SERIAL PRIMARY KEY,
    module_key    TEXT    NOT NULL,
    variant_id    TEXT    NOT NULL DEFAULT 'default',
    variant_tags  JSONB   NOT NULL DEFAULT '{}',
    version       INT     NOT NULL DEFAULT 1,
    template_body TEXT    NOT NULL,
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    weight        REAL    NOT NULL DEFAULT 1.0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (module_key, variant_id, version)
);

CREATE INDEX IF NOT EXISTS idx_prompt_templates_lookup 
  ON prompt_templates (module_key, active);
  
-- GIN index for variant_tags JSONB queries
CREATE INDEX IF NOT EXISTS idx_prompt_templates_tags 
  ON prompt_templates USING GIN (variant_tags);   -- FINAL CORRECTION 2026-07-25 (Tech Health): added missing ON prompt_templates
```

### `llm_configs`

```sql
CREATE TABLE IF NOT EXISTS llm_configs (
    module_key     TEXT PRIMARY KEY,
    model_id       TEXT,
    temperature    REAL NOT NULL DEFAULT 0.1,
    max_tokens     INT  NOT NULL DEFAULT 1000,
    top_p          REAL,
    stop_sequences TEXT[],
    timeout_ms     INT  NOT NULL DEFAULT 30000,
    fallback_model TEXT,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Critical Correctness Requirement: Caller_mode Normalization

**Issue:** Codebase has 3 incompatible caller_mode vocabularies. LLMManager establishes authoritative values.

**Requirement:** Seed migration for `prompt_templates` must normalize existing caller_mode values BEFORE tag-match works.

**Authoritative vocabulary (LLMManager):**
- `real_time`
- `background`
- `batch`

**Validation gate:** AC-6 (seed parity acceptance test) — if normalization is wrong, byte-identical render fails.

**Question:** Who owns the mapping logic from old vocabs → new vocab? (LLM Agent seed script, or shared util?)

---

## Questions for Platform Architects

### Database

1. Schema structure + column types acceptable?
2. Index strategy (standard B-tree on module_key + active, GIN on variant_tags JSONB)?
3. Any cross-DB FKs or access-pattern concerns?
4. Migration A safety + Migration B sequencing gate approved?
5. Seed normalization: who owns the caller_mode mapping rules?

### Technical Health

1. Schema structure health? Ownership clarity (who owns llm_calls versioning going forward)?
2. Index strategy acceptable?
3. Migration sequencing gate (A must complete before B)?
4. Seed normalization correctness validation (AC-6)?

### Eval-architect

1. Two-step migration sequencing safe from arm-history perspective?
2. is_hard_pinned logic correct (exclude hard-pinned turns from model-arm bandit training)?
3. Caller_mode vocab normalization: validation approach + correctness gate?

### UX

1. Any implications for frontend design tokens or SSE event contracts?
2. Design-system consistency with variant_id/template concepts?
3. Token alignment concerns with new config surface?

### Product Awareness

1. Product-truth implications: variant_id, variant_tags, active flag — any customer-facing promises?
2. Grounding concerns: implications for LLM config/template representation in product docs?
3. Docs/disclosures needed for variant experiment status?

---

## Eval-architect sign-off (2026-07-24)

**Verdict: SIGNED OFF WITH CONDITIONS + one BLOCKER in Migration A that must be fixed before it lands.**

### ⛔ BLOCKER (found on code check, not in the doc): Migration A backfills a column it never adds.
`020_llm_calls.sql` has `provider`, `ab_variant` — but NO `variant_id`. Migration A's
`UPDATE llm_calls SET variant_id='default'` (and Migration B's unique index on
`variant_id`) reference a column that doesn't exist and isn't in Migration A's ADD list.
As written, Migration A fails. **Fix:** add `ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS
variant_id TEXT;` BEFORE the backfill. Also confirm the intended relationship between the
existing `ab_variant` and the new `variant_id` — the Migration B index uses BOTH as distinct
arm dimensions, so they must be genuinely different things (document which is which), or the
arm key double-counts.

### Q1 — two-step sequencing safe from arm-history? SAFE (no data loss; A additive+nullable, B gated on backfill) — with one continuity condition.
The new unique index `(provider, module_key, variant_id, ab_variant)` defines a FINER arm grain
than history carries: every pre-migration row has `module_key = NULL`. So historical rows are a
single legacy arm `(provider, NULL, 'default', ab_variant)` that CANNOT be attributed to a module.
**Condition C1:** the bandit training read must treat pre-migration (NULL-module_key) history as a
SEPARATE cold-start bucket — it must NOT silently merge into the new `(module, variant)` arms, or a
new fine-grained arm inherits stale reward earned under a coarser context and starts mis-primed. The
training query must handle the NULLs deliberately (explicit filter/COALESCE), not accidentally.

**C1 RULING/REFINEMENT (Eval, 2026-07-25) — resolves the C1↔DQ-2 tension: BACKFILL `module_key = stage` in Migration A.** They don't collide once you see `module_key = stage` is a RENAME, not a coarsening. A literal label-copy can only (a) exactly match a new module → exact history carried (C1-fine, exact not coarse), or (b) not match any fine module (split stages like `react_1`) → orphan legacy bucket + new fine modules COLD-START. No case mis-attributes coarse reward to a finer arm — a false-merge needs assigning a coarse value TO a fine key, which copying never does. **So C1's teeth are entirely on `variant_id`:** history = `'default'` (the hardcoded prompt WAS the default = exact), new/non-default variants cold-start (Step B). C1's NULL-bucket cold-start applies to genuinely-NEW arms on the genuinely-new axis (variant_id ≠ 'default'), NOT the module_key rename. Do NOT overload module_key=NULL for provenance — derive that from migration timestamp / NULL template_id. Flag (not a blocker): split (1:many) stages' new modules cold-start, so DQ-2's "all history preserved" is literally true only for 1:1 stages — confirm the split list so no one over-promises.

### Q2 — is_hard_pinned logic correct? CORRECT — same off-policy principle as the calibration variant-pin — with two clarifications.
A pinned selection is NOT a bandit decision; attributing its reward to the arm's value estimate is
off-policy contamination (the policy "learns" about an arm from turns it didn't choose). So excluding
hard-pinned turns from MODEL-arm training is right — `WHERE NOT is_hard_pinned` on the model-arm read.
Two clarifications:
- **C2a — per-AXIS, not blanket row-drop.** `is_hard_pinned` must mean specifically "the MODEL
  selection was forced." A turn where the model was pinned but the PROMPT varied is still valid,
  on-policy data for the PROMPT arm (model held constant = controlled variable — consistent with the
  Gate-1 mutual-exclusion ruling). Don't drop the whole row from all learning; gate only the model arm.
- **C2b — calibration turns MUST set is_hard_pinned = TRUE.** A calibration run pins the variant by
  construction (the Gate-1 `calibration_mode` freeze). Those turns must never feed prod bandit training —
  set is_hard_pinned=TRUE on calibration_mode turns so the exclusion covers them automatically.

### Q3 — caller_mode normalization validation + gate? AC-6 is NECESSARY but NOT SUFFICIENT. Three additions.
Byte-identical render (AC-6) only proves the caller_modes IN the seed set render the same — it does not
prove the mapping is COMPLETE or semantically safe. Add:
- **C3a — coverage assertion, fail-closed.** `SELECT DISTINCT caller_mode` over the real data; assert
  every existing value has an explicit mapping rule; REFUSE to seed on any unmapped value (never
  default-bucket an unknown caller_mode into `real_time` silently — that's the exact silent-drift that
  produced 3 vocabs).
- **C3b — no-semantic-collapse check.** Where two old values map to one new value, confirm they were
  behaviorally equivalent. The 3-vocab bug means look-alike values may have driven different behavior.
- **C3c — historical key remap.** caller_mode is a conditioning key for bandit arms AND my calibration
  cells. Remapping the vocab RETROACTIVELY changes the grouping key, so pre-normalization history under
  old spellings must be remapped (or bucketed legacy) or one logical arm splits across two vocab spellings.
- **Ownership (answers the doc's open Question + DB-Q5): a SHARED UTIL owned by LLMManager, NOT a
  seed-local script.** The mapping is applied in three places — the seed migration, the historical
  training-read remap, and any live legacy ingestion. Three reimplementations = drift = how we got 3
  vocabs. One shared, tested (AC-6 + C3a coverage) normalization util is the single source of truth.

**Sign-off is contingent on the BLOCKER fixed and C1/C2a/C2b/C3a-c accepted. The arm-safety and
hard-pinned logic are otherwise sound.**

---

## Sign-Off Checklist

- [x] **Database: Schema + migration safety — SIGNED UNCONDITIONAL. Finding 4 (matview DROP CASCADE + recreate) + Finding 5 (arm-key model not ab_variant) + all org scoping/index/lifecycle conditions confirmed. Ready to land. (Platform Architects, 2026-07-25)**
- [x] **Technical Health: Structure health + gate sequencing — RE-CONFIRMED against CORRECTED DDL (2026-07-25). All 3 defects fixed correctly; attribution index + executed A→B gate present; ownership ruling encoded. One residual syntax fix required (see TECH re-confirmation block below): `idx_prompt_templates_tags` is missing `ON prompt_templates`. Condition clears on that one-line fix; final migration file gets a spot-check.**
- [x] **Eval-architect: Arm safety + hard-pinned logic + normalization validation — SIGNED w/ conditions (see block above); BLOCKER: add variant_id column in Migration A**
- [x] **UX: Design-system seams — SIGN-OFF HOLDS. Corrected DDL scope remains: no new SSE event contracts, no new frontend surfaces, variant_id/template server-side only, no design token changes. (2026-07-25)**
- [x] **Product Awareness: Product-truth implications — SIGNED. variant_id/variant_tags ops-only (no user exposure). active=true reality gate enforced. No corpus disclosure required (forward constraint: add if variants become customer-facing). (2026-07-25)**

**All five must sign off before LLM Agent proceeds with DDL.**

---

## Blocker

**Chat LLM Agent (local_bd8109e3-62b2-4972-a1a4-2a54d92e73c3)** is waiting for this gate.

Once all five architects sign off, migration DDL lands immediately.

---

## CORRECTED DDL — authoritative (LLM Agent, 2026-07-25)

Supersedes the DDL in the original gate doc (Migration A / Migration B sections above).
All defects below were found during verification against the **actual schema files**, not
asserted. Reviewers who signed the original DDL (Technical Health, Eval-architect,
Product-Awareness) are asked to **confirm their sign-off holds against this corrected version.**
Full context + acceptance criteria live in `mobius-chat/docs/SPEC_LLM_MANAGER.md` §2.4.

**Verified facts:** `020_llm_calls.sql` has `provider`, `ab_variant`, `model` — **NO `variant_id`, NO `module_key`**.
`022_model_performance_view.sql` defines `model_performance_by_stage` as a **MATERIALIZED VIEW**
(`GROUP BY stage, model`) with two dependent regular views (`model_winner_by_stage`, `model_composite_scores`).

### Defects found and fixed
- **DEFECT 1 (Tech Health):** arm-key index was `UNIQUE` on a per-call LOG table → 2nd call on any arm fails to insert. **Fix:** non-unique.
- **DEFECT 2 (Tech Health + Eval BLOCKER):** Migration A backfilled `variant_id` without `ADD COLUMN`. **Fix:** add the column before the backfill.
- **DEFECT 3 (Tech Health):** `ALTER TABLE 022_... ADD COLUMN` invalid (it's a view). **Fix:** see Finding 4.
- **FINDING 4 (LLM Agent — needs Database confirmation):** `022` is a **MATERIALIZED** view with two dependents. `CREATE OR REPLACE` does **not** work on matviews — requires `DROP MATERIALIZED VIEW … CASCADE` → recreate all three → `REFRESH`. A naive `CREATE OR REPLACE VIEW` still fails at execution.
- **FINDING 5 (LLM Agent — Eval confirmed):** arm-key index must key on `model` (always populated), **not** legacy `ab_variant` (sparse — NULL for non-A/B calls). `ab_variant` = legacy **model**-A/B marker, retained historical-only, **not** an arm dimension. `variant_id` (new) = **prompt**-template variant. Distinct axes; canonical arm key = `(model, module_key, variant_id)` per spec §5.

- **DEFECT 6 (Tech Health, final — fixed 2026-07-25):** greenfield `idx_prompt_templates_tags` was missing `ON prompt_templates` (invalid syntax). Corrected to `CREATE INDEX IF NOT EXISTS idx_prompt_templates_tags ON prompt_templates USING GIN (variant_tags);` — fixed in the greenfield section above and in spec §2.1.

### Migration order
`prompt_templates` + `llm_configs` created **first** (before Migration A's `template_id REFERENCES prompt_templates(id)`).

### Migration A — additive columns + backfill (safe to land first)
```sql
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS module_key     TEXT;
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS variant_id     TEXT;          -- FIX (DEFECT 2 / BLOCKER)
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS template_id    INT REFERENCES prompt_templates(id);
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS turn_id        TEXT;
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS is_hard_pinned BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS temperature    REAL;          -- Eval condition (Q3): log resolved temp/call so temp variance ≠ arm-reward variance

UPDATE llm_calls SET variant_id = 'default' WHERE variant_id IS NULL;        -- default inherits arm history
```

### A→B gate — EXECUTED, not assumed (Tech Health hardening)
```sql
SELECT COUNT(*) FROM llm_calls WHERE variant_id IS NULL;   -- MUST record 0 in the tracker before landing B
```

### Migration B — indexes + view (gated on the executed check above)
```sql
-- FIX DEFECT 1 (non-unique) + FINDING 5 (model, not ab_variant). Matches spec §5 arm key.
CREATE INDEX IF NOT EXISTS idx_llm_calls_arm_key
    ON llm_calls (module_key, model, variant_id);

-- REQUIRED ADDITION (Tech Health): the Eval attribution join key — else reward/eval queries seq-scan.
CREATE INDEX IF NOT EXISTS idx_llm_calls_attribution
    ON llm_calls (turn_id, module_key);

-- FIX DEFECT 3 + FINDING 4: matview cannot be ALTERed or CREATE-OR-REPLACEd. DROP CASCADE + recreate all three.
DROP MATERIALIZED VIEW IF EXISTS model_performance_by_stage CASCADE;  -- also drops model_winner_by_stage, model_composite_scores
-- … recreate model_performance_by_stage: add `variant_id` to SELECT and `GROUP BY stage, model, variant_id`;
-- … recreate model_winner_by_stage + model_composite_scores (dependents, otherwise unchanged);
-- … REFRESH MATERIALIZED VIEW model_performance_by_stage;
```

### Accepted reviewer conditions (encoded in spec §2.4/§4/§5)
C1 (NULL-module_key history = separate cold-start bucket) · C2a (per-axis hard-pin, gate model arm only) ·
C2b (calibration turns set `is_hard_pinned=TRUE`) · C3a-c (caller_mode fail-closed coverage / no-semantic-collapse /
historical key-remap) · caller_mode mapping = **shared util owned by LLMManager** (seed + training-read remap +
live ingestion, one source of truth) · unmapped value → documented default **+ warn, never crash, never silent-default**.

**Ownership (Tech Health ruling):** LLMManager owns `llm_calls` schema versioning going forward, every change DB-architect-gated.

### Technical Health re-confirmation (2026-07-25)

**✅ SIGN-OFF HOLDS against the corrected DDL.** Verified each fix against my original conditions, not the summary:
- DEFECT 1: arm-key index non-unique ✓, and Finding 5's key `(module_key, model, variant_id)` matches the Gate-1-ruled canonical arm key exactly — better than the original. The ab_variant-is-legacy-model-A/B / variant_id-is-prompt-variant axis separation is the right disentanglement; keep it documented in spec §5.
- DEFECT 2: `variant_id` ADD COLUMN precedes backfill ✓ (also clears Eval's BLOCKER).
- DEFECT 3 + Finding 4: matview DROP CASCADE → recreate ×3 → REFRESH is the correct mechanism (CREATE OR REPLACE genuinely does not work on matviews). The recreate bodies are stubs here — fine for the gate doc; my spot-check of the final migration file covers them. Non-blocking note: there is a window where all three views are absent mid-migration; acceptable at dev stage, sequence it off-peak in prod.
- Required additions both present: `idx_llm_calls_attribution (turn_id, module_key)` ✓, executed A→B gate query recorded-in-tracker ✓.
- Ownership + all accepted conditions (C1/C2a-b/C3a-c, shared-util caller_mode, default+warn) encoded ✓.

**One residual defect (greenfield section, not superseded by the corrected block):** line ~73, `CREATE INDEX IF NOT EXISTS idx_prompt_templates_tags USING GIN (variant_tags);` is missing `ON prompt_templates` — invalid syntax as written. Fix: `CREATE INDEX IF NOT EXISTS idx_prompt_templates_tags ON prompt_templates USING GIN (variant_tags);`. One line; no re-review needed.

### Open for the two remaining lenses
- **Database:** confirm Finding 4 (matview DROP-CASCADE recreate) + Finding 5 (arm-key column) + overall migration safety.
- **UX:** design-system / SSE-contract implications of variant_id/template concepts.

*(Note: Technical Health and Product-Awareness signed the original DDL via cross-session message, not by editing the checklist above — their boxes remain unchecked pending re-confirmation against this corrected version. Eval-architect's block above still applies; Finding 5 was confirmed with Eval directly.)*
