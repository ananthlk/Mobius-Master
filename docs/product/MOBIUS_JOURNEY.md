# Mobius — our journey

This narrative is **evidence-based** where possible: milestones come from internal planning documents. Dates in status files may reflect a **snapshot** (e.g. “as of Feb 24, 2025” in [docs/V1_WEEK1_STATUS.md](../V1_WEEK1_STATUS.md)); treat them as historical context, not live project management.

For architecture diagrams, see [docs/ARCHITECTURE_SCHEMATIC.md](../ARCHITECTURE_SCHEMATIC.md).

---

## Why Mobius Chat exists

The product direction (from planning docs) emphasizes **non-failing chat**, **grounded answers** from published payer and regulatory materials, and **skills** (search, scrape, lookups) so staff spend less time on phone trees and PDF hunts. The **V1** plan locks scope: parser robustness, RAG corpus and lexicon work, skills, persistence, and a path to production migration — see [docs/V1_DAY_BY_DAY_PLAN.md](../V1_DAY_BY_DAY_PLAN.md).

---

## Timeline sketch (V1 day-by-day plan)

The following is a **compressed** outline of the locked 25-day plan (~5 weeks). See the linked doc for gates and module names.

| Phase | Days (approx.) | Theme |
|-------|----------------|--------|
| **Week 1** | 1–5 | Foundation: planner/parser, blueprint routing, pipeline orchestration, responder hardening, regression discipline |
| **Week 2** | 6–10 | RAG corpus: lexicon audit, six doc types, plan ingest, AHCA, scale toward ten plans |
| **Week 3** | 11–15 | Quality: retagging, retrieval eval, recall tuning, answer accuracy, graceful degradation when RAG is down |
| **Week 4** | 16–20 | Skills (Google, scraper, +1), persistence and streaming, full regression, **documentation and runbook** |
| **Week 5** | 21–25 | Code lock, staging migration and lexicon sync, staging deploy, production migration, production validation |

Lexicon work is called out repeatedly (Days 6, 8, 11, 22) — ongoing as documents change.

---

## Week 1 status snapshot (historical)

[V1_WEEK1_STATUS.md](../V1_WEEK1_STATUS.md) recorded early progress against an earlier week-1 framing: parser and routing work **done** in code for several items, while **test gates** (e.g. dedicated routing tests, comprehensive pipeline crash tests) were **not yet met** at the time of writing. Use that file for **what was tracked**, not for current CI status — run the test suite today for ground truth.

---

## Where we are heading (without scope creep)

The locked V1 plan explicitly avoids new features late in the cycle; ideas belong in a **post-V1 backlog** (see `.cursor/rules/v1-plan-lock.mdc`). Product documentation in `docs/product/` describes the system; it does not change that commitment.

---

## Moments (team)

**Purpose**: preserve human stories — demos that went sideways, bugs with personality, phrases that stuck — without exposing PHI or confidential client names.

### How to contribute

1. Add a **short bullet** (2–4 sentences) below.
2. **No patient identifiers**; redact customer names unless you have clearance.
3. Sign with **first name or initials** and **quarter/year** if you want credit.

### Entries (fill in)

- _(TBD — your story here. Example prompt: “What broke in a funny way during staging?” “What demo phrase became a meme?”)_

---

## See also

- [docs/product/CAPABILITIES.md](CAPABILITIES.md)
- [docs/product/USER_GUIDE_CHAT.md](USER_GUIDE_CHAT.md)
- [docs/product/ADMIN_GUIDE.md](ADMIN_GUIDE.md)
