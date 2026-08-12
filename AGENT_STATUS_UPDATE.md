# Agent Status Update Form
**For: Each Agent Owner (Appeals, Retriever, Eval, Chat, Payor Platform, UX, etc.)**

Fill this out and send to PA Architect. This updates the specs catalog with **real** status.

---

## Instructions

1. **Read this entire form first**
2. **Fill out each section honestly** — no aspirational status, just what's real today
3. **Send the completed form** to PA Architect (claude-code session or GitHub issue)
4. **PA updates the specs catalog** based on your input

---

## Your Agent Info

**Agent Name:** ________________  
**Owner:** ________________  
**Date Submitted:** ________________  

---

## Current Status (Today, Not Next Week)

### What's LIVE Right Now (Production, Users Using It)

List what's actually deployed and being used:
```
- [Example] Chat policy questions answered (Gate 4)
- [Example] Answer Cache service running on Cloud Run

Your turn:
- 
- 
- 
```

**Live Gate(s):** (Which gates from the RCM model are actually live?)  
________________

---

### What's In Progress (Being Built, ETA Known)

What are you actively building? When do you expect it to ship?

```
- [Component Name] — Started [DATE], Expected [DATE], % Complete [X%]
- [Component Name] — Started [DATE], Expected [DATE], % Complete [X%]

Your turn:
- 
- 
- 
```

---

### What's Blocked (Built but Can't Ship)

What's ready to ship but blocked on something upstream?

```
- [Component] — Blocked on: [What/Who] — Unblocks when: [DATE/EVENT]

Your turn:
- 
- 
- 
```

---

### What's Planned (Designed, Not Started)

What's on the roadmap but not being actively built?

```
- [Component] — Planned for [QUARTER]
- [Component] — Planned for [QUARTER]

Your turn:
- 
- 
- 
```

---

## Current Sprints

**Sprint Name:** (e.g., "M1 Appeals Decision Engine")  
**Duration:** [START DATE] → [END DATE]  
**Goals:** (What are you trying to ship this sprint?)

1. ________________
2. ________________
3. ________________

**On Track?** ☐ Yes ☐ No ☐ At Risk  
**If No/At Risk, Why?** ________________

---

**Sprint Name:** (if you have multiple)  
**Duration:** [START DATE] → [END DATE]  
**Goals:**

1. ________________
2. ________________

---

## Open Bugs/Issues

### P0 (Breaks Production, Urgent)

```
- [BUG TITLE] — Impact: [who/what affected] — Workaround: [yes/no]
- [BUG TITLE] — Impact: [who/what affected] — Workaround: [yes/no]

Your turn:
- 
- 
```

### P1 (Should Fix Soon, Impacts UX or Performance)

```
- [BUG TITLE] — Planned fix: [DATE]
- [BUG TITLE] — Planned fix: [DATE]

Your turn:
- 
- 
```

### P2 (Nice to Fix, Doesn't Block Work)

```
- [BUG TITLE] — On radar for [QUARTER]
- [BUG TITLE] — Deprioritized because [reason]

Your turn:
- 
- 
```

---

## Dependencies & Blockers

**What are you waiting for from other agents?**

```
- Waiting on: [Agent/Component] — For: [What] — Needed by: [DATE]
- Waiting on: [Agent/Component] — For: [What] — Needed by: [DATE]

Your turn:
- 
- 
```

**What are other agents waiting on from you?**

```
- [Agent] waiting on: [What] — Your ETA: [DATE]
- [Agent] waiting on: [What] — Your ETA: [DATE]

Your turn:
- 
- 
```

---

## Acceptance Criteria Status

For your key components, how close are you to "done"?

**[Component Name]**  
Acceptance Criteria:
- ☐ [Criterion 1]
- ☐ [Criterion 2]
- ☐ [Criterion 3]
- ☐ [Criterion 4]

**Percent Complete:** ____%  
**What's Left:** ________________

---

**[Component Name]**  
Acceptance Criteria:
- ☐ [Criterion 1]
- ☐ [Criterion 2]
- ☐ [Criterion 3]

**Percent Complete:** ____%  
**What's Left:** ________________

---

## Reality Check

**Is the specs catalog (https://mobius-specs-...) accurate for your area?**

☐ Yes, it's current  
☐ No, it's stale (what's wrong?: ________________)  
☐ Partially (some parts are right, some wrong)

---

## Anything Else?

Any context, decisions, or risks the team should know about?

________________

________________

---

## Sign-Off

By filling this out, you confirm:
- ✓ This status reflects reality today, not aspirations
- ✓ Dates are realistic estimates (not best-case)
- ✓ Blockers are real, not theoretical
- ✓ Bugs are actually open/unfixed

**Submitted by:** ________________  
**Date:** ________________  
**Confidence in this estimate:** ☐ High ☐ Medium ☐ Low (if low, why?: ________________)

---

**Send this to:** PA Architect (or create a GitHub issue in `Mobius-Master` with the title "Agent Status Update: [Your Agent Name]")

**Timeline:** Submit updates **before** quarterly reviews (Oct 1-7 for Q4)
