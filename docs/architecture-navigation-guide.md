# Architecture Navigation Guide
## How to explore Mobius' 7-layer stack + Deep Research

---

## **Start Here: Three Documents, One Architecture**

### 1. **mobius-architecture-essay-complete.md** — The Story
- **For:** Anyone learning what Mobius is
- **Contains:** Business problem, conceptual overview, why 7 layers work, real question flow
- **Time:** 10 minutes to read
- **Best when:** Onboarding new team members, explaining to stakeholders

### 2. **mobius-architecture-diagram-complete.html** — The Visuals
- **For:** Understanding component relationships
- **Contains:** Expandable layer views, question flow visualization, RCM gates
- **Time:** 5 minutes to explore
- **Best when:** You need a quick reference or a visual to share

### 3. **mobius-architecture-drilldown-reference.md** — The Details
- **For:** Engineers, architects, operators building/running Mobius
- **Contains:** Component ownership, database schemas, API contracts, UI links, roadmap
- **Time:** Look up what you need
- **Best when:** "Where do I find X?", "What does this component own?", "What's the schema?"

---

## **Navigation Paths**

### **I'm new to Mobius**
1. Read the essay (10 min) → understand the problem + architecture
2. Look at the diagram (5 min) → see how layers connect
3. Come back to drilldown reference when you need details

### **I'm implementing a feature in Layer X**
1. Find your layer in the drilldown reference
2. Click into your component
3. See: status, owner, UI links, schema, known issues, roadmap

### **I need to integrate with Component X**
1. Search the drilldown reference for "Component X"
2. Find the API section
3. Links point to spec docs + code repos

### **I want to understand why we chose this architecture**
1. Read section "Why This Architecture?" in the essay
2. See how it solves: scalability, certainty, speed, auditability, learning, modularity

### **I'm debugging a bug in Layer X**
1. Find your component in the drilldown reference
2. See: Known Issues section
3. Check BUG_LOG.md in docs/ for open bugs

---

## **Quick Reference: 7 Layers + Deep Research**

### **Layer 1: Surfaces**
- Chat, API, Chrome Extension, Mobile/Dashboard
- **Navigate via:** drilldown → "LAYER 1: SURFACES"
- **Key link:** mobius-chat UI at `https://mobius-chat-ortabkknqa-uc.a.run.app/`

### **Layer 2: Router & Optimizer**
- Reasoning engine that picks the best strategy (Facts/RAG/Web/Reasoning)
- **Navigate via:** drilldown → "LAYER 2: ROUTER & OPTIMIZER"
- **Key links:** prompt-composer.py, router-reasoning-strategy.md

### **Layer 3: Platform Agents**
- Infrastructure agents (Product Awareness, Eval, User Manager, Org, Feedback, Tech Review)
- **Navigate via:** drilldown → "LAYER 3: PLATFORM AGENTS"
- **Key insight:** These agents support Mobius itself, not RCM workflows

### **Layer 4: Domain Agents**
- RCM specialists (Credentialing, Strategy, Appeals, Sourcing, Curation, etc.)
- **Navigate via:** drilldown → "LAYER 4: DOMAIN AGENTS"
- **Key insight:** These solve the actual RCM problems

### **Layer 5: Skills**
- Discrete tools agents call (Email, Tasks, Download, Feedback, Vault, Deep Research)
- **Navigate via:** drilldown → "LAYER 5: SKILLS"
- **Key insight:** Reusable, composable, modular

### **Layer 6: Intelligence**
- Fact Store (certified instant) + RAG Corpus (rich searchable)
- **Navigate via:** drilldown → "LAYER 6: INTELLIGENCE"
- **Key insight:** Two tiers = certainty without guessing

### **Layer 7: Evaluation & Feedback**
- Grades answers, identifies gaps, trains the Router
- **Navigate via:** drilldown → "LAYER 7: EVALUATION & FEEDBACK"
- **Key insight:** The system learns from every answer

### **Deep Research (Parallel)**
- Runs continuously, finds gaps, verifies, feeds back to Intelligence
- **Navigate via:** drilldown → "DEEP RESEARCH (PARALLEL SYSTEM)"
- **Key insight:** The learning engine that makes Mobius smarter over time

---

## **Schema Navigation**

Each component in the drilldown reference includes **Schema details** showing:
- **Table name** (PG for PostgreSQL, BQ for BigQuery, pgvector for vectors)
- **Column definitions** with types and relationships
- **Purpose** of each field

Example: To understand how facts are stored, go to **Layer 6** → **Fact Store** → **Schema** section.

---

## **Ownership Map**

To find who owns a component:
1. Go to drilldown reference
2. Find your component
3. See **Owner** field (and **Links to → Code** for repo)
4. Cross-reference **Technical tab** of the platform (shows all 23 modules + owners)

---

## **Roadmap by Layer**

Each layer in the drilldown has a **Roadmap** section showing next 3 milestones. Read through to understand what's coming next:
- Layer 1 (Surfaces): Chrome extension, mobile refinements
- Layer 2 (Router): Fine-tuned per-domain bandits
- Layer 3 (Platform): Auto-generated API docs
- Layer 4 (Domain): varies by agent (Appeals M6 judge, Sourcing distributed scraper, etc.)
- Layer 5 (Skills): expanded as new capabilities emerge
- Layer 6 (Intelligence): Deep Research UC-1 batch sourcing
- Layer 7 (Eval): Real-time online grading
- Deep Research: Continuous improvement

---

## **How to Stay Current**

- **Weekly:** Check platform Status tab → Live System Status (last 7 days)
- **Biweekly:** Technical Review Agent posts updates → see Coordination tab
- **When blocked:** Check Status tab → Known Blockers section
- **When building:** Reference drilldown for current schema + owner
- **When shipping:** Update your component's section in drilldown reference

---

## **Files at a Glance**

| File | Purpose | Update Frequency |
|------|---------|------------------|
| mobius-architecture-essay-complete.md | Conceptual overview | Rarely (architecture stable) |
| mobius-architecture-diagram-complete.html | Visual reference | Rarely |
| mobius-architecture-drilldown-reference.md | Technical details | Monthly (as systems evolve) |
| platform.html (Learn tab) | Integrated navigation | Weekly (FAQs + docs updated) |
| BUG_LOG.md | Known issues | Daily (as bugs surface) |
| RAG_FACTSTORE_COORDINATION.md | Cross-agent agreements | Weekly (as decisions made) |

---

## **Platform Integration**

All of this is accessible in one place:
1. Open mobius-chat → Platform view
2. Click **Learn** tab
3. See: Architecture Overview (links to essay/diagram/drilldown), all 7 layers, Deep Research, FAQs, key docs

---

*Last Updated: 2026-09-07*
