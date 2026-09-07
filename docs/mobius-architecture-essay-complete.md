# How Mobius Works: The Complete Architecture

## The Problem We Solve

A network of 34 independent healthcare organizations processes $1B+ in claims annually. Each center operates alone, duplicating work:

- **Policy questions take 3+ phone calls** — "What's the prior-auth rule for Medicaid in FL?" Someone digs through PDFs, finds conflicting answers, calls to clarify. Meanwhile, 33 other centers are asking the same question.
- **Denials pile up** — 18% denial rate vs. 5.7% benchmark = $60M+ in annual leakage. Many denials are preventable if staff had access to the right policy at the right time.
- **Staff burns out** — 34 back offices duplicating: credentialing, policy research, appeals, billing logic. The network loses $66M/year to administrative overhead.
- **Nobody learns from anyone** — If one center discovers a payor pattern or a successful appeal strategy, the other 33 never hear about it.

**Mobius solves this by making the network itself intelligent.**

---

## The Architecture: 7 Layers + Deep Research

### **Layer 1: Surfaces**

*How operators enter the system.*

Mobius is accessible through multiple surfaces, all connected to the same backend:

- **Chat** — Conversational interface. Ask anything about policies, denials, appeals.
- **API** — Programmatic access for integrations.
- **Chrome Extension** — Inline help while operators work in their EHR or billing system.
- **Mobile/Dashboard** — Alerts, task tracking, status updates.

All surfaces talk to the same intelligence backend. No matter how you enter, you get the same knowledge, the same reasoning, the same answers with citations.

### **Layer 2: Router & Optimizer**

*What decides how to answer your question.*

The Router is the brain. When you ask a question, it doesn't just search. It **reasons about the best way to answer**:

#### **Modular Prompting**
The Router composes a prompt from reusable blocks:
- **System prompt** — "You are a payor policy expert. Answer with certainty or admit uncertainty."
- **Context block** — Relevant facts, prior decisions, payor-specific rules.
- **Example block** — Similar questions answered correctly.
- **Constraint block** — "Cite sources. Use only verified information. No speculation."

Different questions get different combinations of blocks. A complex appeals question might include reasoning examples. A simple fee lookup might skip examples entirely.

#### **Dynamic Mode Selection**
The Router picks the reasoning approach:
- **Direct answer** — For factual lookups. One shot, high confidence.
- **Few-shot reasoning** — For policy interpretation. Show 2-3 examples, then answer.
- **Chain-of-thought** — For multi-step logic. Break it down: policy + exception + timeline → ruling.
- **Debate mode** — For conflicting interpretations. "Here's the conservative reading... here's the aggressive reading... here's the likely middle ground."

#### **Strategy Selection**
Then it picks the retrieval strategy:
- **Strategy A (Facts)** — "This is a simple lookup." Hit the Fact Store. Instant, deterministic.
- **Strategy B (RAG)** — "This needs nuanced policy understanding." Search the corpus. Return with citations.
- **Strategy C (Web)** — "This is obscure or new." Search the web as a fallback.
- **Strategy D (Reasoning)** — "This needs multi-step logic." Use ReAct to plan and execute.

The Router **learns what works** by observing which strategies produce good answers. Over time, it routes smarter.

### **Layer 3: Platform Agents**

*Infrastructure that supports the system itself.*

These agents don't solve RCM problems—they solve **Mobius problems**:

- **Product Awareness Agent** — Keeps all documentation fresh, up-to-date, and discoverable. Owns the learning materials.
- **Feedback Agent** — Listens to operator feedback (CSAT, NPS, feature requests) and routes insights to product and engineering.
- **User Manager Agent** — Manages enrollment, profiles, permissions, access levels.
- **Org Agent** — Handles organization setup, datastore provisioning, onboarding workflows.
- **Eval Command Center** — Runs the QA system. Grades answers. Identifies gaps. Trains the Router.
- **Technical Review Agent** — Biweekly architecture reviews. Governs module health and system coherence.

### **Layer 4: Domain Agents**

*Specialists in specific revenue cycle problems.*

Each domain agent owns one piece of the RCM workflow:

- **Credentialing Agent** — Provider enrollment, license tracking, taxonomy management.
- **Strategy Agent** — Payor strategy, rate benchmarking, contract management.
- **Roster Agent** — Team management, staff credentials, coverage tracking.
- **Prior Auth Agent** — Prior authorization workflows, rules, timelines, appeals.
- **Engagement Agent** — Patient outreach, appointment management, follow-up tracking.
- **Appeals Agent** — Appeal workflows, letter generation, regulatory compliance.
- **Sourcing Agent** — Web scraping, document classification, corpus building.
- **Curation Agent** — Embedding, tagging, metadata enrichment, content freshness.

Each agent has access to:
- The Router (to answer questions)
- Skills (to take actions)
- Intelligence (to access knowledge)
- Other agents (to coordinate)

### **Layer 5: Skills**

*Discrete tools agents call.*

Skills are reusable capabilities:

- **Email Skill** — Send emails to payors, patients, staff.
- **Tasks Skill** — Create and track tasks for staff.
- **Download Skill** — Fetch and verify external documents (PDFs, fee schedules, policy files).
- **Feedback Skill** — Capture operator feedback.
- **Vault Skill** — Personal document library, saved queries, liked answers.
- (More as needed)

Skills are **modular and composable**. An agent calls one or many skills in sequence. A skill doesn't know what agent called it—it just does its job.

### **Layer 6: Intelligence**

*Where the knowledge lives.*

Two tiers of knowledge, accessed by the Router:

#### **Fact Store (Certified, Instant)**
- Fee schedules, mandatory waiting periods, covered/non-covered services
- Timely-filing windows, appeal deadlines, documentation requirements
- **Contract:** Answer-or-abstain. Either you know with certainty, or you say "I don't know."
- No guessing. No hallucinations. Pre-cited, immutable.

#### **RAG Corpus (Rich, Searchable)**
- Full text of payor policies, provider manuals, regulatory guidance
- Embedded in vectors so semantic search works ("What's the rule about telehealth for ADHD?" finds the right manual section)
- Citations tied to every answer (page number, date, source, confidence)
- Fallback when facts don't cover it

Together: **certified answers first, detailed research second.**

### **Layer 7: Evaluation & Feedback**

*How the system knows if it's working.*

Every answer is graded:

- **Accuracy** — Is the answer correct? Did it cite the right policy?
- **Coverage** — Did we have the knowledge to answer? Or did we miss a source?
- **Latency** — Is it fast enough for an operator?
- **Clarity** — Is the answer understandable?

Grades feed back into:
- **Router** — "Strategy B (RAG) worked for this type of question. Increase its weight."
- **Sourcing** — "We couldn't answer this. Add these gaps to the research queue."
- **Product** — "Operators are struggling with this. Consider adding a surface for it."

---

## **Parallel System: Deep Research**

Deep Research runs **alongside the main stack**. It's the **learning engine** that makes Mobius smarter over time.

### **How It Works**

When Eval (Layer 7) notices a gap—"We answered this, but our corpus is incomplete" or "We don't have a certified fact for this scenario"—it signals Deep Research.

Deep Research then:

1. **Digs deeper** — Uses the full corpus + web + reasoning to research the gap thoroughly
2. **Verifies** — Runs the finding through a critic (human expert or LLM) to verify correctness
3. **Feeds back** — The verified finding goes into the Fact Store (if it's a certified fact) or into the RAG corpus (if it's documentation)

### **Why It's Parallel (Not a Layer)**

- It operates **across all domains** (Credentialing, Prior Auth, Strategy, Appeals, etc.)
- It's **asynchronous** — happens in background, doesn't block user queries
- It's **continuous** — always finding gaps, always improving
- It **feeds the main stack** — every finding makes the Router smarter, the Fact Store more complete, the corpus richer

### **The Learning Loop**

```
Operator asks question
    ↓
Router answers (using Facts + RAG + Reasoning)
    ↓
Eval grades the answer (accuracy, coverage, latency)
    ↓
Gap detected? → Deep Research investigates
    ↓
Finding verified? → Feeds into Fact Store or RAG Corpus
    ↓
Next operator asks similar question
    ↓
Router has better knowledge → Better answer
```

---

## How a Real Question Flows Through the System

**Operator asks:** "Can FL Medicaid deny a claim for a telehealth ADHD intake if the patient declined video?"

1. **Surface (Layer 1)** — Chat receives the question
2. **Router (Layer 2)** — Decides: "This is specific policy + precedent. Try Facts first, then RAG with reasoning."
3. **Facts (Layer 6a)** — Checks: "No certified fact for this exact scenario."
4. **RAG (Layer 6b)** — Searches: Finds 3 Medicaid policies, 1 telehealth addendum, 1 ADHD-specific guidance
5. **Reasoning (ReAct via Router)** — Chains them: "Policy X says audio-only requires physician approval. Addendum Y says ADHD requires real-time synchronous contact. Result: Medicaid can deny if audio-only violates sync requirement."
6. **Chat (Layer 1)** — Synthesizes: "Medicaid can deny. Here are the three policy sections. [Citations + page numbers]"
7. **Operator** — Gets answer in 2 seconds, with full provenance
8. **Eval (Layer 7)** — Grades: "✓ Correct. ✓ Good citations. ✓ Fast. → Router learns: RAG + reasoning works for this class."
9. **Deep Research** (Parallel) — Notices: "We found this by chaining 3 documents. This pattern should be a certified fact. Researching more telehealth + ADHD combinations to build a fact entry."

---

## Why This Architecture?

### **Scalability**
Every organization feeds the Fact Store and RAG corpus. 34 centers learning becomes one network learning.

### **Certainty**
Two-tier knowledge means we answer with confidence when we can, and admit uncertainty when we can't.

### **Speed**
Facts are instant. RAG is <1s. Router chooses the fast path when it's safe.

### **Auditability**
Every answer is cited. Every decision is logged. Every payor policy is versioned.

### **Learning**
Router improves from feedback. Sourcing improves from gaps. Deep Research improves from both. The system gets smarter every day.

### **Modularity**
Surfaces, agents, skills are all independent. Add a new surface, agent, or skill without touching the others. Swap strategies. Experiment safely.

---

## The 8 RCM Gates: What Mobius Unlocks

Each layer enables gates:

- **Tiers A–B (Gates 1–5):** Live today. Chat + RAG answering policy questions. Denials detected. Claims closed faster.
- **Tier B→C (Gates 6–7):** Building now. Appeals automated. Coding standardized.
- **Tier C (Gate 8):** Roadmap. Collective rate negotiation. 34 centers operating as one.

---

## Next Steps

**For operators:** Use Chat to ask policy questions. You're talking to 34 centers' collective knowledge.

**For developers:** Understand the 7-layer stack + Deep Research. Each layer has owners and APIs.

**For architects:** The Router is the heart. Everything else feeds it (facts, corpus, feedback, research). If Router gets better at choosing strategies, everything gets better.

---

*Last Updated: 2026-09-07*
