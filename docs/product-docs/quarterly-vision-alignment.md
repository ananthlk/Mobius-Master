# Quarterly Vision Alignment — Gate Status & Roadmap Review

> **Purpose:** Track which RCM gates are live/building/roadmap, and align all agents on the path to the next tier unlock. This is a standing quarterly review that gates every sign-off on advancement.

---

## How This Works

Every quarter (Jan/Apr/Jul/Oct), each agent who owns a gate reports:
1. **Current status** (live / building / spec-signed / roadmap)
2. **Blocker list** (what's blocking the next step)
3. **Dependencies** (which other gates must land first)
4. **Product-truth alignment** (do the docs match the code?)

The Product-Awareness Architect synthesizes these into a fleet-wide picture and feeds it back to sign-offs, schematic updates, and roadmap adjustments.

---

## Current State (Q3 2026)

| Gate | Owner | Status | Progress | Blockers | Dependencies |
|------|-------|--------|----------|----------|--------------|
| **1. Claim closure** | Finance Agent | ✅ Live | Deployed in all orgs | none | none |
| **2. Denial management** | Appeals Agent | ✅ Live | Core rule playbooks + trending | none | Gate 1 |
| **3. Eligibility verification** | Credentialing Agent | ✅ Live | 270/271 lookups + roster reconciliation | none | Gate 1 |
| **4. Payor policies & benefits** | Payor Platform Agent | ✅ Live | Chat answers + corpus @9k docs | corpus quality (9.6% junk chunks in-progress Curation fix) | Gate 3 |
| **5. Credentialing** | Credentialing Agent | ✅ Live | Automated pipeline + shared NPPES | enrollment UI pending | Gate 3 |
| **6. Authorization / Appeals** | Appeals Agent | 🔨 Building | Spec signed (2026-07-26); agent active | – | Gates 1–5 |
| **7. Coding & claims** | Router Agent | ✅ Partial | Chat answers coding questions | full automation design pending | Gates 1–3 |
| **8. Network effects** | Org Agent | 🗺️ Roadmap | Post-Tier-B vision; collective leverage | unified ops architecture design | Gates 1–7 |

---

## Tier Unlock Timeline

**Tier A → Tier B (Q4 2026):** Gates 1–5 live, revenue unlock ~$22M.  
**Tier B → Tier C (Q2 2027):** Gates 6–7 live, revenue unlock cumulative ~$41M.  
**Tier C full (Q4 2027+):** Gate 8 live, network effects unlock $69M+ run-rate.

---

## Product-Awareness Reality Gates (Quarterly Checklist)

Before claiming a gate is "live," sign-off requires:

1. **Code exists** — The module code is deployed (not stubbed, not planned).
2. **Docs reflect reality** — User docs say what actually works, not aspirations.
3. **Status field is correct** — The gate's status in the docs matches the deployed state.
4. **Owner is accountable** — The agent can name blockers to the next step.
5. **Dependencies are clear** — If this gate blocks the next, that's explicit.

**Artifact validation:** Sign-offs are spot-checked against real code + test execution, not summaries.

---

## Gate Owner Checklist (Template for Each Review)

When you report on your gate(s), answer these:

- **What's deployed right now?** (User-facing feature statement)
- **What's the status?** (✅ Live / 🔨 Building / 🗺️ Roadmap)
- **What's blocking the next milestone?** (Explicit list, not vague)
- **Which gates must land before mine?** (Dependencies)
- **Which gates depend on mine?** (Reverse dependencies — who's waiting for you)
- **Do the docs match the code?** (Reality-gating check)

---

## Standing Questions (Asked Every Quarter)

1. **Are docs honest?** Do the product docs say "live" when the feature is actually live, or are they aspirational?
2. **Has status drifted?** Has code shipped but the docs still say "planned"? (Or vice versa?)
3. **What's the next blocker?** If you're "building," what's the hard stop to "live"?
4. **Do you own the blocker?** If your blocker is someone else's gate, that's a visible dependency.
5. **Is the value unlocked?** If a gate is "live," is the $M/year value actually flowing, or are there adoption gaps?

---

## Cross-Gate Dependencies (Network Map)

```
Gate 1 (Claim closure)
  ↓
Gate 2 (Denial management) ← also enables Appeals Agent
  ↓
Gates 3 & 5 (Eligibility + Credentialing) ← foundation for all Tier B gates
  ↓
Gate 4 (Payor policies) ← corpus + RAG + Chat
Gate 6 (Appeals) ← appeals playbooks + denial trends
Gate 7 (Coding) ← billing rules + Chat
  ↓
Gate 8 (Network effects) ← requires unified data from all prior gates
```

---

## Review Schedule

- **Quarterly:** First week of Jan/Apr/Jul/Oct. All gate owners report + PA synthesizes.
- **Monthly (standby):** Broadcast updates on major blockers mid-quarter (async Slack thread).
- **As-needed:** When a gate owner discovers a blocker that shifts the timeline, flag immediately.

---

## How to Update This Document

1. After each quarterly review, PA updates the "Current State" table.
2. If a gate changes status (e.g., "🔨 Building" → "✅ Live"), update the table AND commit with the changed date.
3. If new dependencies surface, update the "Cross-Gate Dependencies" diagram.
4. If the Tier unlock timeline shifts, flag it with a note: `(revised 2026-10-15: reason)`.

---

## Related Pages

- **[The Mobius Model](mobius-model.md)** — RCM gate framework + economics
- **[Mobius Thesis](mobius-thesis.md)** — Why this matters
- **[Retriever Fleet Schematic](../rag-agents/retriever-fleet-schematic.md)** — RAG module status (gate 4 substrate)
- **[Schematic](../../../product-awareness/product_awareness/static/schematic.html)** — Visual map (has Business Model lens showing gates)

---

*Last reviewed: 2026-07-30*  
*Next review: 2026-10-01*  
*Owner: Product-Awareness Architect*
