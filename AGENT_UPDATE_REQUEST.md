# 📋 Agent Status Update Request

**To:** All Agent Owners (Appeals, Retriever, Eval, Chat, Payor Platform, UX, etc.)  
**From:** PA Architect  
**Date:** 2026-08-11  
**Deadline:** 2026-08-15 (by end of week)

---

## What's This About?

The **Specs Catalog** (https://mobius-specs-1032922478554.us-central1.run.app) is now the single source of truth for what's shipped, what's being built, and what's blocked.

**Right now, some of the data in the catalog is stale or incorrect.** We need YOU to update it with accurate, real-time status.

This takes **~30 minutes per agent** and ensures the whole team knows what's actually happening (not aspirations).

---

## What We Need From You

1. **Fill out the Agent Status Update Form** (see below or file: `AGENT_STATUS_UPDATE.md`)
2. **Be honest about:**
   - What's actually LIVE (deployed, users using it)
   - What's actively IN PROGRESS (current sprint, ETA)
   - What's BLOCKED (ready to ship but waiting on something)
   - What's PLANNED (designed, not started)
3. **List your sprints** (what you're shipping this sprint)
4. **List open bugs** (P0/P1/P2, with impact)
5. **Flag your blockers** (what you're waiting on from other agents)

---

## How to Submit

**Option 1: GitHub Issue**
```
Title: Agent Status Update: [Your Agent Name]
Description: [Copy/paste your completed form]
Assignee: PA Architect
```

**Option 2: Direct Message**
Send the completed form to PA Architect via this session.

---

## The Form

Copy this template and fill it out:

```
# Agent Status Update — [Your Agent Name]

## Your Agent Info
Agent Name: [Name]
Owner: [Your Name]
Date Submitted: 2026-08-XX

## Current Status (Today)

### Live Right Now
- [Component] — Gate [#]
- [Component] — Gate [#]

### In Progress
- [Component] — Started [DATE], Expected [DATE], [X%] complete
- [Component] — Started [DATE], Expected [DATE], [X%] complete

### Blocked
- [Component] — Blocked on: [What/Who] — Unblocks when: [DATE]

### Planned
- [Component] — Planned for [QUARTER]

## Current Sprints

### Sprint: [Name]
Duration: [START] → [END]
Goals:
1. [Goal 1]
2. [Goal 2]
3. [Goal 3]
On Track? [Yes/No/At Risk]

## Open Bugs

### P0 (Breaks Production)
- [BUG] — Impact: [What/Who] — Workaround: [Yes/No]

### P1 (Should Fix Soon)
- [BUG] — Planned fix: [DATE]

### P2 (Nice to Fix)
- [BUG] — On radar for [QUARTER]

## Dependencies

Waiting on:
- [Agent] for [What] by [DATE]

Others waiting on me for:
- [Agent] needs [What] by [DATE]

## Reality Check

Is the specs catalog accurate for your area? [Yes/Partially/No — explain]

## Sign-Off

This status reflects reality today ✓
Dates are realistic ✓
Bugs are actually open ✓
```

---

## Examples

### ✅ Good (Honest)

```
Live Right Now:
- Observer module built + live-validated
- Fillers a–e all built and ranked

Blocked:
- Observer wiring to production — Blocked on Eval's calibration plan
- Synthesis integration — Blocked on AsyncSession threading (still in progress)

In Progress (Current Sprint: RAG Hardening)
- Observer calibration — Started 2026-07-24, Expected 2026-08-30, 40% complete
- Synthesis AsyncSession — Started 2026-08-04, Expected 2026-08-25, 60% complete

Open Bugs:
P0: None (all in flight are in sprint)
P1: 
- Pool P0 fixes (authority_level, tag-coverage) need test coverage — Fix: 2026-08-18
- Router execution-order invariance needs contract test — Fix: 2026-08-20

P2:
- Trace explorer UX could use polish — Deprioritized for 2026-Q4
```

### ❌ Bad (Aspirational)

```
Live Right Now:
- Entire RAG pipeline fully optimized ← NOT REAL, some pieces still blocked

In Progress:
- Everything shipping this quarter ← Too vague, no ETA

Blocked:
- None ← Probably not true, what's waiting on others?

Open Bugs:
- No known issues ← Every system has bugs
```

---

## Why This Matters

1. **Team visibility** — Everyone knows what's blocked and why
2. **Realistic planning** — You stop asking "when is X done?" without real answers
3. **Blocker clearing** — When agent A sees they're blocking agent B, they prioritize
4. **Specs catalog accuracy** — The source of truth stays current, not aspirational

---

## Timeline

| Date | Action |
|------|--------|
| 2026-08-11 (today) | PA sends this request |
| 2026-08-15 (EOW) | **Deadline: All agents submit updates** |
| 2026-08-16 | PA updates specs catalog with your input |
| 2026-08-17 | Specs catalog goes live with real data |

---

## Questions?

- **How long does this take?** ~30 minutes (you already know your status, just fill out the form)
- **Do I need to be perfect?** No. Honest is better than perfect. If you don't know, say so.
- **What if I'm not sure about a date?** Give your best estimate and flag confidence level (high/medium/low)
- **What if things change mid-sprint?** Update again at the next review (quarterly or when things significantly shift)

---

## What Happens With Your Data

Your form gets:
1. ✓ Reviewed by PA Architect for consistency
2. ✓ Integrated into the specs catalog
3. ✓ Shared with the team via the live website
4. ✓ Used to clear blockers and unblock you

It's not a report to management — it's a tool for the team to coordinate better.

---

## Sample Update (Appeals Agent)

```
Agent Status Update — Appeals Agent

Live Right Now:
- Appeals lookup rules wired (4 tools live)
- Playbook drafting working

In Progress (W1 DB Build):
- Database schema — Started 2026-08-05, Expected 2026-08-18, 80% complete
- Golden-answer mode rules — Started 2026-08-10, Expected 2026-08-15, 60% complete

Blocked:
- Chat W7 surface integration — Blocked on Chat FE/UX availability — Unblocks: 2026-08-30

Sprints:
Sprint: M1 Appeals Decision Engine
Duration: 2026-08-01 → 2026-08-30
Goals:
1. Ship Decision Engine (Gates 1–3)
2. Wire Chat surface (Gate 4)
3. Finalize golden-answer contract

Current Status: On Track

Open Bugs:
P0: None
P1:
- Appeals letter assembly edge case (commas in names) — Fix: 2026-08-20

P2:
- Product-help docs tone — Deprioritized until M2

Dependencies:
Waiting on: Chat FE/UX for W7 surface wiring (by 2026-08-30)
Others waiting: Chat team needs appeals modes finalized (by 2026-08-15) ✓ on track
```

---

## Submit Your Update

**By EOW Friday (2026-08-15)**, send your completed form:

- GitHub Issue: `Agent Status Update: [Your Name]` 
- Or: Paste in a message to PA Architect

**Thanks!** This keeps the team coordinated and the specs catalog honest.

— PA Architect
