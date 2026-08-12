# 🔴 BLOCKER — Chat DQ-1 Migration A (Eval-architect Sign-Off)

**Severity:** CRITICAL — Migration A fails on execution  
**Flagged by:** Eval-architect  
**Date:** 2026-07-24  
**Action required:** Fix before LLM Agent proceeds with DDL

---

## The Blocker

**Migration A backfills a column it never adds.**

### Problem

`020_llm_calls.sql` currently has:
- `provider` ✅
- `ab_variant` ✅
- `variant_id` ❌ **MISSING**

Migration A script (as written) includes:
```sql
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS module_key TEXT;
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS template_id INT REFERENCES prompt_templates(id);
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS turn_id TEXT;
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS is_hard_pinned BOOLEAN NOT NULL DEFAULT FALSE;

-- Backfill all existing rows
UPDATE llm_calls SET variant_id='default' WHERE variant_id IS NULL;  ← ERROR: column doesn't exist
```

**The backfill tries to set `variant_id='default'`, but:**
1. The column doesn't exist in the current schema
2. Migration A never adds it
3. **Migration A fails on execution**

---

## Required Fix

**Add this before the backfill in Migration A:**

```sql
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS variant_id TEXT NOT NULL DEFAULT 'default';
```

**Complete Migration A (corrected):**

```sql
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS module_key TEXT;
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS template_id INT REFERENCES prompt_templates(id);
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS turn_id TEXT;
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS is_hard_pinned BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS variant_id TEXT NOT NULL DEFAULT 'default';  ← ADD THIS

-- Now backfill all existing rows
UPDATE llm_calls SET variant_id = 'default' WHERE variant_id IS NULL;
```

---

## Related Question for Database Architect

**Clarify the relationship between `ab_variant` (existing) and `variant_id` (new):**

Migration B creates a unique index:
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_llm_calls_arm_key 
  ON llm_calls (provider, module_key, variant_id, ab_variant);
```

This uses BOTH `variant_id` and `ab_variant` as distinct arm dimensions. Confirm:
- Are these genuinely different things? (E.g., `ab_variant` = A/B test arm, `variant_id` = prompt template variant?)
- Or is the index double-counting the same concept?

If they're the same thing, the index should use only one. If they're different, document which is which.

---

## Eval-architect Conditions (Once Blocker Fixed)

**Sign-off includes three conditions that must be built into the code:**

### C1: Cold-start bucket for pre-migration history
Bandit training read must treat pre-migration (NULL-module_key) rows as SEPARATE cold-start bucket.

```sql
-- WRONG: silently merges legacy history into new arms
SELECT module_key, variant_id, ab_variant, AVG(reward) 
FROM llm_calls 
WHERE NOT is_hard_pinned 
GROUP BY module_key, variant_id, ab_variant;

-- CORRECT: handles NULLs deliberately
SELECT COALESCE(module_key, 'legacy_pre_migration') AS module_key, variant_id, ab_variant, AVG(reward) 
FROM llm_calls 
WHERE NOT is_hard_pinned 
GROUP BY COALESCE(module_key, 'legacy_pre_migration'), variant_id, ab_variant;
```

Historical (NULL-module_key) rows cannot be attributed to a module. If a new fine-grained arm inherits stale reward from the legacy bucket, it starts mis-primed.

### C2a: is_hard_pinned is per-axis, not row-drop
`is_hard_pinned` means "the MODEL selection was forced" — not "drop this row from all learning."

A turn where MODEL was pinned but PROMPT varied is still valid, on-policy data for PROMPT training (model held constant = controlled variable).

**Apply the gate per-axis:**
```sql
-- Model arm training (exclude hard-pinned turns)
SELECT ... FROM llm_calls WHERE NOT is_hard_pinned ...;

-- Prompt arm training (include hard-pinned turns if prompt wasn't pinned)
SELECT ... FROM llm_calls WHERE ... (other conditions, no is_hard_pinned filter);
```

### C2b: Calibration turns MUST set is_hard_pinned = TRUE
Calibration runs pin the variant by construction. Those turns must NEVER feed prod bandit training.

**Required:** Any turn generated during `calibration_mode=true` must have `is_hard_pinned = TRUE` set before insert.

---

## Next Steps

1. **LLM Agent:** Fix Migration A DDL (add `variant_id` column + update backfill)
2. **Database Architect:** Clarify `ab_variant` vs `variant_id` relationship
3. **Code review:** Ensure C1, C2a, C2b are built into bandit training queries
4. **Re-route to Eval-architect:** Confirm fixes resolve the blocker

Once fixed, Eval-architect's sign-off is finalized + you proceed to Migration B (gated on A completion).

---

**Status:** Blocker must be resolved before LLM Agent's Migration A DDL lands.
