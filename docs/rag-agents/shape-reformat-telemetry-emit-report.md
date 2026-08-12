# Shape-Reformat — Telemetry + Emit Report, one live case per archetype

**Generated:** 2026-07-23, from a real run of `run_gate()` → `run_reformat()` → `narrate()`/`narrate_full()` against the live dev DB. Not simulated — every field below is actual output. DB sign-off still pending (FAN_OUT latency blocker); everything else is real and current.

---

## 1. PRECISE

**Live query:** *"How do I confirm eligibility for Medicaid"*

**Dev telemetry** (Diagnostics / `shape_reformat` emit key)
```
gate_contour:      exact
reformat_posture:  precise
reformat_ms:       0
rewritten_queries: ["how do i confirm eligibility for medicaid"]
reason:            "EXACT contour — pass through unchanged, minimal work"
```

**User emit** (`narrate(gate, result)`, chat-bubble — REVISED 2026-07-23 per Ananth: v1 was too thin, didn't state what was found)
> I see you're asking about **eligibility**, for **medicaid** — this can be answered directly, so I'm searching for it now.

**Diagnostics trace** (`narrate_full(gate, result)`)
> You asked: "How do I confirm eligibility for Medicaid"
> Gate found about **eligibility**, for **medicaid**.
> The gate found this precise enough to search for directly, without any rewriting.
> Search query: "how do i confirm eligibility for medicaid"
> (EXACT contour — pass through unchanged, minimal work)

---

## 2. FAN_OUT

**Live query:** *"Eligibility for Medicaid"* (80 real sibling codes from the live lexicon)

**Dev telemetry**
```
gate_contour:        underspecified / explore_siblings
reformat_posture:    fan_out
reformat_ms:         17541   ← KNOWN BLOCKER, see tracker
rewritten_queries:   4 (3 themes + 1 catch-all)
fanout_themes:
  - label: "Policies and status related to newly enrolled individuals who are non-participants"
    n_members=31  prevalence_docs=3307  lexicon_proximity=0.857  score=0.914
  - label: "Policies and criteria related to gross income for eligibility"
    n_members=32  prevalence_docs=1487  lexicon_proximity=0.887  score=0.712
  - label: "Policies and services related to individuals aged 10-18 years"
    n_members=17  prevalence_docs=154   lexicon_proximity=0.747  score=0.467
  - label: "other considerations"  is_catchall=true  (no members, not corpus-derived)
reason: "explore_siblings — 80 candidate siblings clustered into 3 theme(s) + 1 catch-all"
```

**User emit** (`narrate(gate, result)` — REVISED 2026-07-23: angles now listed explicitly, not folded into one run-on sentence)
> I see you're asking about **eligibility**, for **medicaid** — this could mean a few different things. Here's what I'm exploring:
> - policies and status related to newly enrolled individuals who are non-participants
> - policies and criteria related to gross income for eligibility
> - policies and services related to individuals aged 10-18 years
> - anything else that might apply, beyond those

*(Still flagged to UX: theme labels are mechanically softened lexicon descriptions, not genuinely polished copy — that part is pending their narrative round, structure/richness is fixed.)*

**Diagnostics trace** (`narrate_full(gate, result)`)
> You asked: "Eligibility for Medicaid"
> Gate found about **eligibility**, for **medicaid**.
> The gate found this maps to a broad topic with a large set of more specific facets, and nothing narrowed which one you meant.
> Angle: "Policies and status related to newly enrolled individuals who are non-participants" — 31 related facet(s), 3307 document(s), relevance score 0.91.
> Angle: "Policies and criteria related to gross income for eligibility" — 32 related facet(s), 1487 document(s), relevance score 0.71.
> Angle: "Policies and services related to individuals aged 10-18 years" — 17 related facet(s), 154 document(s), relevance score 0.47.
> One additional angle isn't drawn from our documents at all — it's an open check for anything the other angles might have missed.
> Reformat took 17541ms to cluster and rank these.
> (explore_siblings — 80 candidate siblings clustered into 3 theme(s) + 1 catch-all)

---

## 3. CLARIFY

**Live query:** *"What documentation is required to enroll a new pediatric patient"*

**Dev telemetry**
```
gate_contour:       underspecified / missing_domain
reformat_posture:   clarify
reformat_ms:        0
clarify_questions:  ["Could you clarify what topic this relates to?"]
reason:             "UNDERSPECIFIED/missing_domain — no enumerable siblings, suggesting clarification instead of a blind ask"
```

**User emit**
> I want to make sure I get this right — Could you clarify what topic this relates to?

**Diagnostics trace**
> You asked: "What documentation is required to enroll a new pediatric patient"
> The gate found this topic too broad to explore on its own, with nothing to enumerate.
> Candidate clarifying question: "Could you clarify what topic this relates to?"
> (UNDERSPECIFIED/missing_domain — no enumerable siblings, suggesting clarification instead of a blind ask)

*Note: this case's `_suggest_clarify_questions` fell back to the generic prompt (no J-code co-occurrence data to build a targeted question) — the co-occurrence path is real code, just didn't fire for this particular query.*

*Also: this query has no found-path to state (D matched nothing at all — that's exactly why it's `missing_domain`), which caught a real grammar bug live — the naive "I see {found}" composition produced "I see I want to make sure I get this right..." (double subject) when `found` was empty. Fixed in `_compose()`; this case's emit output above is the corrected version.*

---

## 4. RELY_ON_EXTERNAL

**Live query:** *"What is the prior authorization process in Clarendon, AR"*

**Dev telemetry**
```
gate_contour:       vicinity
reformat_posture:   rely_on_external
reformat_ms:        0
external_reason:    vicinity
reason:             "vicinity — internal coverage insufficient, defer to Router c/d"
```

**User emit** (REVISED — now states what was found)
> I see you're asking about **prior authorization**, for **clarendon ar** — I have related material, but nothing that covers this exact combination, so I'll look a bit further to piece together a complete answer.

**Diagnostics trace**
> You asked: "What is the prior authorization process in Clarendon, AR"
> Gate found about **prior authorization**, for **clarendon ar**.
> Reason: vicinity.
> Deferring to the router's external strategies rather than forcing an internal answer.
> (vicinity — internal coverage insufficient, defer to Router c/d)

---

## 5. DECLINE

**Live query:** *"What's the weather forecast for tomorrow?"*

**Dev telemetry**
```
gate_contour:       out_of_scope
reformat_posture:   decline
reformat_ms:        0
decline_reason:     out_of_scope
reason:             "OUT_OF_SCOPE — hard boundary, no fallback attempted"
```

**User emit**
> This doesn't look like something in scope for what I can help with here.

**Diagnostics trace**
> You asked: "What's the weather forecast for tomorrow?"
> Reason: out_of_scope.
> No fallback attempted — this is a hard boundary, not a coverage gap.
> (OUT_OF_SCOPE — hard boundary, no fallback attempted)

---

## 6. CLARIFY_REPHRASE (tentative — not confirmed by Ananth)

**Live query:** *"asdkfjqwoeiru"*

**Dev telemetry**
```
gate_contour:       unclear
reformat_posture:   clarify_rephrase
reformat_ms:        0
clarify_questions:  ["I didn't quite understand that — could you rephrase your question?"]
reason:             "UNCLEAR — tentative CLARIFY_REPHRASE default, NOT yet confirmed by Ananth"
```

**User emit**
> I wasn't able to make sense of that — could you rephrase it?

**Diagnostics trace**
> You asked: "asdkfjqwoeiru"
> The gate couldn't parse this into anything actionable.
> (UNCLEAR — tentative CLARIFY_REPHRASE default, NOT yet confirmed by Ananth)

---

## Summary

| Archetype | Live query | reformat_ms | Status |
|---|---|---|---|
| PRECISE | "How do I confirm eligibility for Medicaid" | 0 | clean |
| FAN_OUT | "Eligibility for Medicaid" | 17541 | **latency blocker, DB pending** |
| CLARIFY | "What documentation is required to enroll a new pediatric patient" | 0 | clean |
| RELY_ON_EXTERNAL | "What is the prior authorization process in Clarendon, AR" | 0 | clean |
| DECLINE | "What's the weather forecast for tomorrow?" | 0 | clean |
| CLARIFY_REPHRASE | "asdkfjqwoeiru" | 0 | clean, posture itself unconfirmed by Ananth |

5 of 6 archetypes are latency-clean (DB-only, sub-2ms in practice, rounds to 0ms). FAN_OUT is the only one with a real, unresolved performance blocker. Source: `mobius-rag/app/services/retriever/shape/{reformat.py,reformat_narrate.py}`, companion to `shape-reformat-simulation-tracker.md`.
