# Product Roadmap — Open Questions Awaiting Owner Assignment

**Purpose:** Track new product specs filed with open architecture / ownership questions that need a decision before design can proceed.

**Status:** Living document — updated as specs arrive and decisions are made.

---

## Prior Auth Form Surfacing
**Spec:** `mobius-chat/docs/SPEC_PRIOR_AUTH_FORM_SURFACE.md`  
**Status:** Roadmap (not current sprint)  
**Filed by:** Chat Architecture (2026-08-18)  
**One-line:** When users ask about prior auth, surface the correct payor form + fax number + prep checklist. No pre-fill, no PHI.

### Three Open Questions Requiring Owner Decision

**Q1 — Form catalogue ownership:**
> Who owns the form catalogue maintenance — Sourcing Agent (who ingests payor docs) or Payor Policy Agent (who owns the fact store)? Catalogue sits at the seam.

**Options:**
- A: Sourcing Agent — they crawl forms, we catalog them as part of corpus ingest
- B: Payor Policy Agent — owns the payor fact store, extends it with form metadata
- C: Shared — Sourcing feeds form URLs, Payor Policy maintains catalogue state

**Decision needed by:** Before Phase 1 (form catalogue table build)

---

**Q2 — Where does the catalogue table live?**
> Schema location: extend payor fact store, new `prior_auth_forms` table in mobius_rag DB, or flat YAML per payor?

**Options:**
- A: Extend payor fact store — normalized with other payor attributes
- B: New `prior_auth_forms` table in mobius_rag — keeps it queryable, Maintaining Agent can sweep for freshness
- C: Flat config file per payor — simple, but not queryable; harder to maintain at scale

**Spec recommendation:** Option B (new table, queryable, enables Maintaining Agent freshness sweep)

**Decision needed by:** Before Phase 1 (schema DDL)

---

**Q3 — Should expedited auth paths surface as a distinct card variant?**
> Sunshine's expedited path is a phone call, not a form. Should Mobius surface that as an alternative when form is complex?

**Options:**
- A: Yes — low effort, high value (e.g., "Expedited path: call 1-844-477-8313")
- B: No — keep it simple, surface form only; users can read the notes field
- C: Maybe later — roadmap as future enhancement

**Decision impact:** A adds one field to `form_record` (`expedited_contact` | null); C/B requires no schema change.

**Decision needed by:** Before Phase 1 (form_record schema finalized)

---

## Summary of Roadmap Items Awaiting Owner Assignment

| Spec | Primary Question | Status | Blocker? |
|------|------------------|--------|----------|
| Prior Auth Form Surfacing | Ownership (Q1) + catalogue location (Q2) + expedited path (Q3) | Awaiting decision | Yes — blocks Phase 1 |

---

**Escalation process:** When a spec arrives with open questions, file it here. Product Lead (Ananth) routes Q1 to owner, decides Q2–Q3 via sync with stakeholders. Once all Qs are answered, move spec to the active product roadmap and update master timeline.

**Last updated:** 2026-08-18  
**Next review:** When new specs filed or decisions made
