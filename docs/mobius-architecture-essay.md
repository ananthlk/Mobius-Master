# How Mobius Works: The Architecture Story

## The Problem

A network of 34 independent healthcare organizations processes $1B+ in claims annually across behavioral health. Each center operates alone:

- **Policy questions take 3+ phone calls** — "What's the prior-auth rule for Medicaid in FL?" Someone digs through PDFs, finds a conflicting answer, calls to clarify.
- **Denials pile up** — 18% denial rate vs. 5.7% benchmark = $60M+ in annual leakage.
- **Staff burns out** — every center duplicates: credentialing, policy research, appeals, billing logic. 34 back offices doing the same work in isolation.
- **Nobody learns from anyone** — if one center discovers a payor pattern, the other 33 never find out.

**Mobius solves this by making the network itself intelligent.**

---

## The Five-Layer Stack

Mobius is built in five layers. Each layer solves one problem; together they form a network brain.

### **Layer 1: User Interface (Chat)**

*What the operator sees.*

A conversational interface. Ask it anything about payer policies, prior-auth rules, denial patterns, appeals. It answers with citations—"Here's the rule, here's the source, here's the page number."

No PDFs to hunt through. No ambiguity. One source of truth, shared across the network.

### **Layer 2: Router (Reasoning Engine)**

*What decides which tool to use.*

When you ask a question, the router doesn't just search. It **reasons about what strategy will work best**:

- **Strategy A (Facts)**: "This is a simple fee lookup" → Hit the certified fact store (instant, deterministic).
- **Strategy B (Retrieval)**: "This needs nuanced policy understanding" → Search the RAG corpus with citations.
- **Strategy C (Web)**: "This is new or obscure" → Search the web as a fallback.
- **Strategy D (Reasoning)**: "This needs multi-step logic" → Use ReAct (a reasoning engine) to plan and execute.

The router **learns what works** by observing which strategies produce good answers. Over time, it routes smarter.

### **Layer 3: Intelligence (RAG + Facts)**

*Where the knowledge lives.*

**Two tiers of knowledge:**

1. **Fact Store (certified, instant)**
   - Fee schedules, mandatory waiting periods, covered/non-covered services
   - Answer-or-abstain: either you know with certainty, or you say "I don't know"
   - No guessing, no hallucinations
   - First place the router checks

2. **RAG Corpus (rich, searchable)**
   - Full text of policies, provider manuals, regulatory guidance
   - Embedded in vectors so semantic search works ("What's the rule about telehealth for ADHD?" finds the right manual section)
   - Citations tied to every answer (page number, date, source)
   - Fallback when facts don't cover it

Together: **certified answers first, detailed research second.**

### **Layer 4: Sourcing & Curation**

*How the knowledge gets built and stays fresh.*

Three agents keep the corpus alive:

- **Sourcing Agent** — Scrapes payor websites, regulatory PDFs, provider manuals. Classifies documents by type (fee schedule, policy, manual). Chunks them appropriately.
- **Curation Agent** — Embeds chunks, tags them with structured metadata (payor, service line, document type, temporal validity). Culls outdated content.
- **Deep Research Agent** — For complex questions, digs into the corpus, finds gaps, feeds verified facts into the Fact Store.

Result: A corpus that's **complete, current, and interconnected.**

### **Layer 5: Evaluation & Feedback**

*How we know if it's working.*

Every answer is graded:

- **Accuracy**: Is the answer correct? (Did it cite the right policy?)
- **Coverage**: Did we have the knowledge to answer? (Or did we miss a source?)
- **Latency**: Is it fast enough for an operator?

Grades feed back into the Router (so it learns what strategy works best) and into Sourcing (so we know what to prioritize next).

---

## How a Question Flows Through the Stack

**Operator asks:** "Can FL Medicaid deny a claim for a telehealth ADHD intake if the patient declined video?"

1. **Chat** (Layer 1) receives the question
2. **Router** (Layer 2) decides: "This is specific policy + precedent. Try Facts first, then RAG."
3. **Facts** (Layer 3a) checks: "No certified fact for this exact scenario."
4. **RAG** (Layer 3b) searches: Finds 3 relevant Medicaid policy documents, one telehealth addendum, one ADHD-specific guidance.
5. **Retrieval** ranks them by relevance; **ReAct** (if needed) chains them together ("Policy X says video optional; Addendum Y says audio-only requires physician approval; Addendum Z says ADHD requires synchronous real-time contact").
6. **Chat** synthesizes: "Medicaid can deny if audio-only violates real-time requirement for ADHD. Here are the three policy sections. [Citations + page numbers]"
7. **Operator** gets an answer in 2 seconds, with full provenance.
8. **Eval** grades it: "Correct. Good citations. Fast. → Router learns: RAG + reasoning works for this class."

---

## Why This Architecture?

### **Scalability**
Every organization feeds the Fact Store and RAG corpus. 34 centers learning becomes one network learning.

### **Certainty**
Two-tier knowledge (facts + retrieval) means we answer with confidence when we can, and admit uncertainty when we can't.

### **Speed**
Facts are instant. RAG with pre-computed embeddings is <1s. Router chooses the fast path when it's safe.

### **Auditability**
Every answer is cited. Every decision is logged. Every payor policy is versioned and traceable.

### **Learning**
Router improves from feedback. Sourcing improves from gaps. Curation improves from freshness signals. The system gets smarter over time.

---

## The 8 RCM Gates: What Mobius Unlocks

Each gate is a capability. Each layer of the stack enables gates:

- **Tiers A–B (Gates 1–5):** Live today. Chat + RAG answering policy questions. Denials detected. Claims closed faster.
- **Tier B→C (Gates 6–7):** Building now. Appeals automated. Coding standardized across the network.
- **Tier C (Gate 8):** Roadmap. Collective rate negotiation. 34 centers operating as one.

---

## Next Steps

**For operators:** Use Chat to ask policy questions. You're talking to 34 centers' collective knowledge.

**For developers:** Understand the five-layer stack. Each layer has owners. Each layer has APIs.

**For architects:** The Router is the heart. Everything else feeds it (facts, corpus, feedback). If Router gets better at choosing strategies, everything gets better.

---

*Last Updated: 2026-09-07*
