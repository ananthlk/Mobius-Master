# The Mobius Model — RCM Gates & Tier Progression

> Mobius exists to unlock network-scale Revenue Cycle Management intelligence. This page shows the 8 RCM gates that define the progression from standalone provider tools (Tier A) to a shared, unified network intelligence platform (Tier C).

---

## The Vision: From Tier A to Tier C

**Tier A: Point Solutions** ($5M–$20M per org)
- Standalone tools. No EHR integration required.
- You own all your data. Nothing is shared.
- **Gates unlocked:** Claim Closure, Denial Management.

**Tier B: Network Intelligence** ($20M–$60M per network)
- Connect your claims to Mobius — they stay yours, never shared.
- **The network learns from all claims.** You benefit from aggregated intelligence: payer patterns, rate benchmarks, market trends.
- **Gates unlocked:** Eligibility Verification, Payor Policies & Benefits, Credentialing, Authorization.

**Tier C: Virtual Network** ($60M–$150M+)
- One unified network. Not 34 separate organizations.
- **Shared services, shared intelligence, shared leverage.**
- You operate as a single entity for payer negotiation, staff credentialing, appeals, and claims.
- **Gates unlocked:** All 8 gates, plus network effects that only work at scale.
- **The promise:** "What one center learns at 2 AM, 34 centers know by breakfast."

---

## The 8 RCM Gates

Each gate is a revenue-cycle capability that Mobius unlocks at network scale. Gates are cumulative: you don't skip Tier A to reach Tier B.

### **Gate 1: Claim Closure** (Tier A)
**What it enables:** Auto-post of claim payments, reconciliation, and closure.
**Why it matters:** Claims stuck in open state = cash stuck in limbo = 84+ day AR, revenue leakage.
**Mobius solves:** Shared claim-closure rules + automation. Moves AR from 84 days → ~45 days.
**Status:** Live (core feature).

### **Gate 2: Denial Management** (Tier A)
**What it enables:** Automated denial detection, categorization, and appeal routing.
**Why it matters:** 18% denial rate (vs. 5.7% benchmark) = $60M+ in leakage across the network.
**Mobius solves:** Shared denial playbooks, appeals agent, real-time denial trending.
**Status:** Live (Appeals Agent building Gate 6).

### **Gate 3: Eligibility Verification** (Tier B)
**What it enables:** Real-time 270/271 lookups. Know who is actually enrolled and billable **before** you bill.
**Why it matters:** Ghost billing (billing non-enrolled patients) = denials, compliance risk, revenue leakage.
**Mobius solves:** Live MCO eligibility checks, shared roster reconciliation.
**Status:** Live (core feature).

### **Gate 4: Payor Policies & Benefits** (Tier B) ⭐ **Building now**
**What it enables:** Fee schedules, prior-auth rules, timely-filing windows, covered services — answered in seconds with citations. **New:** Payor Fact Store for instant, certified answers on high-confidence predicates.
**Why it matters:** "Some questions should take 3 phone calls." Each call = 20 minutes of admin time. The network loses $60M–70M/year on admin overhead. Wrong answers cost more: wrong fee rate = revenue leakage; wrong prior-auth rule = denials.
**Mobius solves:** Two-tier answer stack. (1) **Fact Store (round 0):** certified predicates with provenance — instant, deterministic, pre-cited. Covers high-confidence facts (fee codes, mandatory waiting periods, covered benefits). (2) **Retrieval (round 1):** if facts don't answer, Chat + RAG escalate. This architecture prioritizes certainty over coverage — answer-or-abstain, never guess.
**Status:** Live (Chat + RAG). Payor Platform Agent + Payor Fact Store building network-scale policies engine. First consumer: Appeals (legal-deadline criticality).

**Roadmap in progress:**
- **Fact Store API (round 0 for ReAct):** Certified-facts endpoint with resolve + appeals-pack shapes, coverage map in manifest, telemetry parity. Status: spec phase. Blocker: appeals-pack co-design. Next: wire behind flag, measure on 22q eval.
- **Deep Research × Fact Store lane:** DR's critic-verified sourcing feeds the store across 6 use cases (batch sourcing, standing audit, appeals pack, reverify, divergence probe, new-payor sweep). Status: contract settled, UC-2 validated. Blocker: DR document_id propagation. Next: UC-1 batch when ready.
- **Start-a-run through RAG:** Payor panel's button fires full pipeline (scrape→classify→chunk→gate→embed→publish). Status: button live on Payor side. Blocker: sequencing after current crawls. Next: wire to RAG trigger endpoint.
- **Deferred structural:** health_plan sub-programs (MMA/LTC/CWSP/HealthyKids), documents sub-program column, shelved-restore of 404 version-chain docs. Blocker: DB §11.4 ruling (Ananth). Next: one-line flip when ruling lands.

### **Gate 5: Credentialing** (Tier B)
**What it enables:** Automated provider credentialing, roster reconciliation, enrollment tracking.
**Why it matters:** "Who do we have? Who can bill? Who has gaps?" — answered for all 34 orgs at once.
**Mobius solves:** Shared credentialing pipeline, shared NPPES lookups, shared taxonomy (credentials, specialties, licenses).
**Status:** Live (core feature).

### **Gate 6: Authorization / Appeals** (Tier B→C) ⭐ **Building now**
**What it enables:** PA tracking, appeal workflows, appeal letter generation, regulatory compliance.
**Why it matters:** Appeals tie up staff time. Delayed appeals = revenue delayed or lost. Manual appeal letters = errors.
**Mobius solves:** Appeals Agent + Chat automation. Shared playbooks across all network orgs.
**Status:** Spec signed, Appeals Agent building.

### **Gate 7: Coding & Claims** (Tier B→C)
**What it enables:** Shared billing rules, coding guidance, claim-submission automation.
**Why it matters:** Inconsistent coding = denials. Different orgs submitting the same service with different codes.
**Mobius solves:** Shared coding standards, Chat answers "what code for this service?", automation flags likely denials pre-submit.
**Status:** Live (Chat answers coding questions).

### **Gate 8: Network Effects** (Tier C)
**What it enables:** Collective rate negotiation, market-scale leverage, unified operations.
**Why it matters:** A single center negotiating with a payer has no leverage. 34 centers operating as one network do.
**Mobius solves:** Unified data → collective intelligence → collective power.
**Status:** Roadmap (Tier C vision).

---

## Where Mobius Is Right Now

| Gate | Tier | Status | What You Get |
|---|---|---|---|
| **1. Claim Closure** | A | ✅ Live | Auto-post, AR reduction, cash faster |
| **2. Denial Management** | A | ✅ Live | Denial detection, appeal routing, trending |
| **3. Eligibility Verification** | B | ✅ Live | Real-time 270/271, roster reconciliation |
| **4. Payor Policies & Benefits** | B | ✅ Live | Chat answers policy questions with citations |
| **5. Credentialing** | B | ✅ Live | Shared credentialing, NPPES lookups, taxonomy |
| **6. Authorization / Appeals** | B→C | 🔨 Building | Appeals agent (spec signed, agent active) |
| **7. Coding & Claims** | B→C | ✅ Partial | Chat answers coding; full automation roadmap |
| **8. Network Effects** | C | 🗺️ Roadmap | Collective negotiation, unified ops (Tier C vision) |

**You are here:** Tier B signal phase (Gates 1–5 live, Gate 6 building, Gate 7 partial).

---

## Why This Matters: The RCM Economics

The FL Medicaid behavioral-health analysis (2019–2024) quantified why Mobius exists:

- **$144M–$217M** in annual value the network is leaving on the table:
  - Patient leakage: $60–125M (patients slipping away before intake = no revenue)
  - Admin overspend: ~$66M (34 separate back offices duplicating work)
  - Clinician churn: $10–18M (depleted centers can't afford to pay, staff leaves)
  - Rate gap: $7.8M (centers get paid less than peers for the same service, never know it)

**Mobius captures this value gate-by-gate:**

| Phase | Gates | Capture | Notes |
|---|---|---|---|
| **Year 1** | 1–3 (governance + credentialing) | ~$22M | Claim closure + denial mgmt + eligibility |
| **Year 2** | 4–5 (intelligence + operations) | ~$41M cumulative | Payor policies + credentialing at scale |
| **Year 3+** | 6–8 (full network intelligence) | $69M+ run-rate | Appeals + coding + network effects |

---

## How to Read This Document

- **Users / operators:** Start with "Where Mobius is right now" (table above). That's where your organization fits.
- **Product / investors:** Read "The Vision" and "Why This Matters." That's the value unlock path.
- **Technical / partners:** Read each gate. Each gate shows the business outcome Mobius is building toward.

---

## Related Pages

- **[About Mobius — Why We Exist](mobius-thesis.md)** — the founding vision and the Möbius strip metaphor
- **[Mobius Chat](mobius-chat.md)** — the conversational interface for gates 4–7 (policy, coding, appeals)
- **[RAG Backend](rag-backend.md)** — how grounding and citations work across all gates
- **[Payor Policies & Benefits](payor-readiness.md)** — Gate 4 deep dive (live feature)
- **[Appeals & Authorization](appeals-agent-spec.md)** — Gate 6 deep dive (building now)

**Payor Fact Store (Gate 4 infrastructure, building now):**
- **[Payor Fact Store Architecture](payor-fact-store-architecture.md)** — two-tier answer stack, integrity model, versioning
- **[Fact Store API for ReAct](payor-fact-store-api.md)** — resolve + appeals-pack shapes, coverage map, abstain contract
- **[Deep Research × Fact Store](deep-research-fact-store-lane.md)** — six sourcing use cases, critic-verified ingestion
- **[Start-a-run through RAG](start-a-run-through-rag.md)** — pipeline trigger, button to scrape-classify-gate-publish
- **[Deferred Structural Items](payor-fact-store-deferred.md)** — health_plan modeling, sub-program column, version restore

---

*Last updated: 2026-07-26*  
*Next alignment review: Q4 2026*  
*Questions? Ask Mobius Chat or reach out to Product.*
