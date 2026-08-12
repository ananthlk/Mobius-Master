# Shape:Structure — Sign-off Tracker

**Live status, updated in real time** — went stale once for Gate, TECH caught it; not repeating that here.
**Spec under review:** `shape-structure-schematic-spec.md`

| Collaborator | Status | Notes |
|---|---|---|
| UX | ✅ **Signed off** 2026-07-23 | Emit key `shape_structure` confirmed clean (no collision). Diagnostics-only surface, NOT `thinking_trace` — Structure has no narrative layer unlike Gate/Reformat. `resolve_resource_posture()` should return an explicit all-zero object (not `None`) for CLARIFY/CLARIFY_REPHRASE/DECLINE — cleaner for consuming code, no null-checking. Diagnostics should show the 4 fields as a "Retrieval budget"/"Resource constraints" section. |
| Chat | ✅ **Signed off** 2026-07-23 | No real user-facing "think mode" toggle exists today — nearly all Chat traffic hits `DEFAULT_CALLER_MODE` with no signal. Found a THIRD vocabulary (see below). Nothing Chat-specific needed in the contract; flagged SSE streaming timeout as a deployment constraint on high-`max_attempts` paths, not a contract item. |
| **Eval** | **✅ Signed off** 2026-07-23 | **Table-based v1 is correct.** Router already validated this pattern (forced-calibration → production data → learned weights). Hand-set cells anchored in existing code (`accuracy_need` 0.70–1.00, `_get_escalation_budget()` patterns, default `k=10`) are plausible starts. **Resourcing eval bank:** strategically-placed test queries per (posture, caller_mode) cell; measure oracle_recall + time-to-convergence + cost. Accept cells if: high-effort show ≥5% recall lift vs baseline, or no lift but ≤10% cost premium. **RELY_ON_EXTERNAL "breadth":** leave as design placeholder in Structure (interpretation lives downstream with Router/Fillers). **Blocker note:** caller_mode vocabulary mismatch (three incompatible vocabularies found) must be resolved by TECH/DB before locking `max_attempts` cells, since they depend on `_get_escalation_budget()` pattern. Not a Structure issue; flagged for pre-build fix ownership. |
| DB | ✅ **Signed off** 2026-07-23 | Zero-DB claim VERIFIED. Also independently confirmed the caller_mode vocabulary bug (see below) — real, critical, pre-existing, not Structure-specific. |
| TECH | ✅ **Signed off** 2026-07-23 (PASS) | Structurally sound: additive, read-only, clean seam (ReformatResult + caller_mode in → ResourcePosture out), zero DB calls, lookup table valid for v1, legacy `answer_shape` passthrough untouched. `breadth`/`confidence_bar`/`speed_budget` can be locked now. **`max_attempts` cells build with a safe conservative fallback** until DB's caller_mode vocabulary fix lands, then lock for real. |

**ALL 5 SIGNED OFF (UX, Chat, Eval, DB, TECH) — 2026-07-23. Cleared to build.**

## Build + integration status — 2026-07-23

- `structure.py` + `contracts.py` additions (`ResourcePosture`, `StructureResult`) built.
- `tests/test_shape_structure.py` — 19/19 passing, pure unit tests (zero DB calls, matches sign-off assumption).
- Sample outputs verified sensible across posture × caller_mode, including graceful fallback on the 3-way vocabulary bug case (no crash, explicit reason string).
- **Wired into `orchestrator.py` by Retriever** (Gate→Reformat→Structure, `caller_mode` threaded through the whole chain) — Retriever independently re-verified pure/sync + 19/19 before wiring, then live-tested 3 cases matching reported samples exactly. **Committed `1636c81`.**
- Emit key `shape_structure` added to `retriever-emit-telemetry-registry.md`.

**Now requesting final implementation sign-off** (build matches the design each collaborator already approved) from UX/Chat/Eval/DB/TECH before closing this module out.

---

## FINAL SIGN-OFF (2026-07-23 — EVAL)

**✅ SHAPE LAYER COORDINATION COMPLETE.**

- **Gate (Step 1a):** CLOSED 2026-07-22 (commit 2f57369). 26-case contour bank proven live.
- **Reformat (Step 1b):** Built + tested 2026-07-23, 12/13 PASS (1 bank correction). Theme clustering validated live: 80 codes → 3 themes (enrollment/income/age-range, 31/32/17 members, semantically distinct). Proposed w_p=0.4/w_l=0.6 used as-is, no re-tuning needed.
- **Structure (Step 1c):** Built + tested 2026-07-23, 19/19 PASS. Lookup table (posture × caller_mode) anchored in live constants. All 5 lenses signed (UX/Chat/Eval/DB/TECH 2026-07-23). Integrated into orchestrator.py (commit 1636c81).

**All three modules cleared for production pending two critical infrastructure blockers (below).**

---

## CRITICAL BLOCKERS — Decision Queue for Ananth

### 1. Reformat FAN_OUT embedding latency — CRITICAL
**Measured:** ~18.8s live (81-code embedding via gemini-001's forced 1-input-per-call sequential). Switched to `text-embedding-004` batchable → ~9.2s embed alone, still ~17-19s total with DB. NOT viable for live query path.

**Fix required:** Precompute lexicon-code embeddings once, cache them, refresh on Curation's publish cadence.

**Decision needed:**
- Where cache lives? (new column on `policy_lexicon_entries`? companion table?)
- Who owns refresh trigger? (Curation pipeline or Reformat init?)
- **Assign owner + timeline before Shape ships.**

---

### 2. Shape:Structure caller_mode vocabulary bug — CRITICAL (pre-existing)
**Problem:** Three incompatible vocabularies coexist:
1. `CALLER_MODE_PRESETS` keys: `"chat.copilot"`, `"chat.default"`, `"chat.thinking"`, etc.
2. `_get_escalation_budget()` checks: `mode in ("fast", "copilot")` — doesn't match (1)
3. `corpus_search.py:147` skill sends: `assembly_strategy` values — matches neither (1) nor (2)

Currently latent (Chat sends no mode, defaults everywhere), but Structure exposes it immediately if any non-default cell gets traffic.

**Fix required:** Normalize to single vocabulary (recommend CALLER_MODE_PRESETS as canonical).

**Decision needed:**
- Who owns normalization? (TECH or DB?)
- Which vocabulary canonical?
- **Assign owner + timeline before Shape ships.**

---

## RESOURCING EVAL BANK — Phase 1 Collaboration Ready

Structure's 19 test cases + Eval's measurement framework (recall lift / cost premium per cell). 

**Phase 1 (framework design):** Start now — Structure to provide 19-case breakdown by (posture, caller_mode); Eval to map to success criteria.

**Phase 2 (live measurement):** After embedding cache lands + dev environment clean. Measure oracle_recall + time-to-convergence + cost per cell; validate high-effort cells show ≥5% recall lift or ≤10% cost premium.

**No Ananth decision needed yet** — self-contained work, ready to proceed in parallel with blocker fixes.

| Collaborator | Implementation sign-off |
|---|---|
| Chat | ✅ 2026-07-23 — degradation on unrecognized caller_mode confirmed correct, no crash/mis-key |
| TECH | ✅ 2026-07-23 (PASS) — "Shape module (all 3 steps) is complete and locked." All criteria met, ready to ship. |
| DB | ✅ 2026-07-23 — zero-DB confirmed, all 7 spec-compliance points verified against actual code, 19/19 tests |
| UX | ✅ 2026-07-23 — spot-checked code directly (not rubber-stamped): all-zero pattern, thinking_trace untouched, emit-key deferral consistent with Gate/Reformat. "Shape-Structure is closed." |
| Eval | ✅ 2026-07-23 — full Shape-layer coordination sign-off (Gate/Reformat/Structure all cleared), posted directly to this file. See "FINAL SIGN-OFF (2026-07-23 — EVAL)" section below. |

**5/5 implementation sign-offs complete (Chat, TECH, DB, UX, Eval). Shape:Structure is closed.**

## Open blocker before table values are finalized (not before more design work)

**`caller_mode` vocabulary bug — now confirmed THREE-WAY incompatible, widened 2026-07-23:**

1. `CALLER_MODE_PRESETS` (`corpus_search_router.py:118`) keys: `"chat.copilot"`, `"chat.default"`, `"chat.thinking"`, `"auth_agent"`, `"research"`, `"batch"`.
2. `_get_escalation_budget()` (`corpus_search_agent.py:2324`) checks: `mode in ("fast", "copilot")` — doesn't match any key in (1). Confirmed by DB.
3. **NEW, found by Chat:** the one real code path that sends `caller_mode` today — `corpus_search.py:147`, the `corpus_search` skill — actually sends `assembly_strategy` values (`"score"` / `"canonical_first"` / `"balanced"`, a completely different axis) into the `caller_mode` field. Doesn't match (1) OR (2).

Net effect: when `caller_mode` is sent at all today, it's in a vocabulary that matches neither preset lookup nor the escalation-budget check — both silently fall through to defaults. Also confirms Chat's finding: **nearly all Chat traffic sends no `caller_mode` at all** and hits `DEFAULT_CALLER_MODE`, so this bug is largely latent today (default path bypasses all three), but would surface immediately if Structure's `ResourcePosture` starts keying real behavior off whichever vocabulary happens to arrive.

**Design implication (not a blocker, a priority note):** since ~100% of current Chat traffic resolves to the default cell, that cell must be safe/sensible on its own — the richer posture×mode table is currently a forward-looking hook (Chat confirmed a "deep search" UI toggle is plausible later, would send `caller_mode:"chat.thinking"` explicitly then), not something live traffic exercises yet.

**Still waiting on TECH/DB to assign a fix owner for the vocabulary mismatch** before locking `max_attempts` table cells that lean on `_get_escalation_budget()`'s pattern. Structure is not touching any of the three vocabularies itself.
