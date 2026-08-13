# Bug Log — Mobius Platform
## File-Backed Issue Tracker (Persists in Git)

**Purpose:** Track known bugs and quality issues that can be picked up during slower periods. This lives in git so issues never evaporate to message-channel drops.

**How to use:**
- Add new issues at the bottom with `## Bug [ID]` format
- Update status as work progresses (OPEN → IN PROGRESS → FIXED → VERIFIED)
- Link to commits/PRs in fixes
- Never delete; mark as FIXED + move to VERIFIED section when confidence is high

---

## 🔴 OPEN BUGS (Active, Unassigned)

### Bug #1: Irrelevant Jurisdiction Prompt When Context Exists
**Component:** Chat RAG reasoning  
**Severity:** MEDIUM (UX failure, but system recovers after retry)  
**Reporter:** Ananth (2026-08-12)  
**Repro:**

User asks: *"Can you review this page https://www.sunshinehealth.com/providers/Billing-manual.html and tell me the key billing rules for behavioral health providers?"*

Expected: Recognize Sunshine Health (payer) is already specified → search corpus for SH billing rules  
Actual: System asks "Which state or jurisdiction did you mean?" even though payer context is present  
Error in logs: `Cannot read properties of undefined (reading 'toLowerCase')`

**Impact:**
- User sees "Request failed" + irrelevant prompt
- Forces retry (user must re-submit same query)
- After retry, system works correctly (contradiction suggests state loss mid-turn)

**Root cause hypothesis:** 
- Router or Shape step loses payer context when escalating to external search (Filler-d)
- Likely in `AnswerShapeResult` → payer field not being threaded through to Router/Filler decision
- Or: PHI classifier / jurisdiction gate running on partial context

**Next steps:**
1. Reproduce in dev with payer-specific query
2. Check Shape output for payer field presence
3. Verify Router receives payer in `AnswerShapeResult`
4. Trace Filler-d context loss

**Owner:** (unassigned — Router or Chat agent)

---

### Bug #2: Web Scrape Tool Output Not Verified in RAG Answers
**Component:** Filler-d (Web Search) + Synthesis  
**Severity:** MEDIUM (accuracy risk — claims without source verification)  
**Reporter:** Ananth (2026-08-12), observed in Bug #1 investigation  
**Repro:**

User asks: *"Can you review this page [URL] and tell me the key billing rules?"*  
Force RAG through mode-d (web search).

Expected: Answer includes only claims that can be traced to provided RAG chunks  
Actual: Final answer includes detailed tables + claims with audit note: "The final answer is almost entirely based on information from a `web_scrape` tool output which was not provided for verification. The provided RAG chunks support almost none of the claims."

**Impact:**
- Answers appear authoritative but lack verifiable source
- "Clean claim requirements" table has no supporting doc link
- Violates core promise: "grounded, not general — comes with citations you can check"

**Root cause:**
- Synthesis step not enforcing source-citation linkage
- Web scrape results may not be saved to `documents` table before synthesis runs
- Or: Synthesis allowed to use tool output as implicit source without doc_id

**Related:**
- Phase 13.3c: `web-scraper → POST /sources/upsert` has zero callers (unbuilt)
- Filler-d workflow may bypass document ingestion entirely

**Next steps:**
1. Verify Filler-d web scrape saves to `documents` before answering
2. Check Synthesis contract: does it require `source_document_id` for every claim?
3. Audit a mode-d answer end-to-end (tool → doc → chunk → answer)
4. Consider gating mode-d until Phase 13.3c lands (or make docs explicit in output)

**Owner:** (unassigned — Retriever/Filler-d or Synthesis agent)

---

### Bug #3: Router Loses Carry-Forward Context on Escalation
**Component:** Router / Query state threading  
**Severity:** MEDIUM (causes unnecessary rework; affects latency + cost)  
**Reporter:** Ananth (2026-08-12), inferred from Bug #1  
**Repro:**

1. User provides payer + specific URL (rich context)
2. Router's first allocation (pool-based search) doesn't meet confidence bar
3. Router escalates to Filler-d (external search)
4. Filler-d doesn't know payer or original URL context
5. Filler-d prompts for disambiguation instead of reusing carry-forward

**Expected:** Context (payer, URL, original query) threads through entire chain  
**Actual:** State loss between Router decision and Filler execution

**Impact:**
- Forces user rework
- Wastes latency on re-clarification
- Confidence signal lost (Router's "need external evidence" doesn't transfer reasoning to external source)

**Root cause:**
- `AnswerShapeResult` or `RoutingLadder` may not include full carry-forward fields
- Or: Filler-d initialization doesn't unpack context from Shape/Router outputs

**Next steps:**
1. Map carry-forward fields: original_query, payer, url, user_context, confidence_bar
2. Verify Router writes these to `rag_query_decisions`
3. Verify Filler-d reads + uses them on execute
4. Add test: escalation query should not re-prompt for info already provided

**Owner:** (unassigned — Router or Filler-d agent)

---

## 🟡 IN PROGRESS BUGS

(None currently assigned)

---

## 🟢 FIXED BUGS (Verified Working)

### Bug: Pool Column Reference (`authority_level` → `document_authority_level`)
**Fixed:** 2026-07-24  
**Commit:** [retriever pool fixes](https://github.com/ananthlk/Mobius-Master/search?q=authority_level)  
**Verified:** 2026-08-11 (Retriever agent, live query traces)

### Bug: Tag-Coverage False Positive (4 → interpreted as 1.0)
**Fixed:** 2026-07-24  
**Details:** Raw tag count was being interpreted as [0,1] confidence score  
**Verified:** 2026-08-11 (live query calibration)

### Bug: Content Dedup Unreliable (content_sha mismatch)
**Fixed:** 2026-07-24  
**Details:** Switched from content_sha to normalized-text grouping  
**Verified:** 2026-08-11 (dedup accuracy spot-check)

---

## 📋 Bug Triage Template

When adding a new bug, use this format:

```markdown
### Bug #[N]: [One-line title]
**Component:** [which agent/service]
**Severity:** [CRITICAL/HIGH/MEDIUM/LOW]
**Reporter:** [who found it] ([date])
**Repro:** [steps to reproduce]
**Expected:** [what should happen]
**Actual:** [what happens instead]
**Impact:** [why it matters]
**Root cause hypothesis:** [best guess at why]
**Next steps:** [investigation checklist]
**Owner:** [who's taking it]
```

---

## 📊 Stats

| Status | Count |
|--------|-------|
| Open | 3 |
| In Progress | 0 |
| Fixed | 3 |
| **Total** | **6** |

---

**Last updated:** 2026-08-12 by PA Architect  
**Next review:** When new bugs reported or weekly triage pass
