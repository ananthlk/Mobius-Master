# Doc Stale: Payor Readiness Registry — Freshness Promise vs Reality

**Filed by:** PA Architect (2026-08-12)  
**Area:** sourcing/corpus  
**Severity:** HIGH (product-truth claim doesn't match implementation)  
**Status:** open

---

## Issue

**File:** `docs/payor-readiness-registry-spec.md`  
**Claim:** "A daily worker already re-fetches `curation_status='canonical'` URLs and detects content change."

**Reality:** `app/curator/freshness_worker.py` does not exist. Phase 13.10 (upstream freshness detection) is unbuilt.

---

## Impact

This claim appears in an authoritative spec as if it's currently live, but the capability doesn't ship until Phase 13.10 lands. This is a product-truth violation: a reader of the spec would believe Mobius automatically detects policy changes daily, which is not true today.

---

## Fix

Update the payor readiness registry spec to accurately reflect current state:

**Option A (mark as future):**
> "A daily freshness worker will re-fetch `curation_status='canonical'` URLs and detect content change (Phase 13.10, not yet shipped)."

**Option B (remove until shipped):**
> Remove the clause entirely. Re-add when Phase 13.10 lands and `freshness_worker.py` is live.

---

## Related

- **Crawler sub-scope spec:** `docs/rag-agents/crawler-sub-scope.md` — Phase 13.10 listed as unbuilt
- **Crawler signoff:** Sourcing agent's verdict on Q2 (this doc_stale)
- **Maintaining agent:** Also claims "freshness" in charter (`docs/rag-agents/maintaining.md:6`, `:10`). Charter collision pending their counter-sign.

---

**Owned by:** Sourcing agent (will fix once Phase 13.10 architecture is decided)  
**Gated on:** Maintain/Sourcing charter resolution + Ananth approval of Crawler sub-scope
