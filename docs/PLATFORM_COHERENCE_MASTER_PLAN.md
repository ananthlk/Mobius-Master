# Platform Coherence Master Plan
## Unifying User / Technical / Specs Tabs + Sprint Roadmap + Onboarding

**Started:** 2026-08-12  
**Target Completion:** End of September 2026 (100% by then)  
**Priority:** Lower (quality-of-life for onboarding + team scaling)  
**Owner:** PA Architect (Ananth) + Platform Architects group

---

## 🎯 The Direction

**Five perspectives, one truth:**
- **User Tab:** "What can you do?" — Surface capabilities, features, entry points
- **Technical Tab:** "Where does it run?" — Services, owners, infrastructure, APIs
- **Specs Tab:** "Is it done?" — Acceptance criteria, gates, sign-off status
- **Eval/Test Tab:** "Is it validated?" — Test coverage, eval metrics, confidence scores (Eval Agent owns)
- **Git Tab:** "What changed?" — Commit history, deployment status, version tracking (Technical team owns)
- **All five show the same 23 core modules**, just with different detail columns

**Plus:**
- **Sprint Board:** Current sprint (now) + archive of past sprints (history)
- **Onboarding Section:** For new team members — taxonomy, module map, first-day workflow (PA Architect owns as standing responsibility)

---

## 📊 Current State (Baseline)

| Aspect | Status | Notes |
|--------|--------|-------|
| **User Tab** | ✅ LIVE | 9 tabs (Overview, Governance, Surfaces, RAG Pipeline, Agents, Design, Onboarding), agent table, status badges |
| **Technical Tab** | ⏸️ BLOCKED | No single comprehensive view; agents scattered across CLAUDE.md memories |
| **Specs Tab** | ✅ LIVE | Specs Catalog live at https://mobius-specs-1032922478554.us-central1.run.app; specs linked from git; markdown→HTML rendering |
| **Eval/Test Tab** | ❌ MISSING | No module-keyed eval metrics view; Eval owns but needs UI + data plumbing |
| **Git Tab** | ❌ MISSING | No central deployment/commit status view; Technical team owns but needs aggregation |
| **Sprint Roadmap** | ❌ MISSING | No persistent sprint board; quarterly review SOP exists but no UI/structure |
| **Onboarding Section** | 🔨 PARTIAL | Fragments in product-docs; PA Architect now owns as standing responsibility |
| **Module Alignment** | 🔨 PARTIAL | User view covers ~60% of modules; Tech/Specs/Eval/Git views incomplete |

**Completion: ~25%** (was 35%, but expanded scope with 2 new tabs)

---

## 📐 Unified Module Framework

**The 23 Core Modules** (same across all 3 tabs):

### **User-Facing Surfaces (5)**
1. **Payor Dashboard** — Health plan enrollment, appeals, compliance dashboards
2. **Chat Interface** — Conversational query experience + vault upload
3. **My Vault** — Document storage + retrieval + instant RAG
4. **Mobile App** — On-the-go version (future)
5. **API Surface** — Third-party integrations

### **Intelligence Agents (10)**
6. **Retriever Agent** — RAG pipeline (Shape→Pool→Fillers→Router→Observer)
7. **Router Agent** — Strategy allocator + reasoning
8. **Eval Agent** — Calibration + priors + bandit reward
9. **Curation Agent** — Chunk→embed→tag→publish
10. **Appeals Agent** — Case routing + playbook generation
11. **Payor Policy Agent** — Reimbursement rules + coverage lookups
12. **PHI Classifier Agent** — HIPAA gate + sensitive detection
13. **Feedback Agent** — CSAT/NPS + product feedback
14. **Historical Extraction Agent** — Chat history analysis
15. **Org Agent** — Setup + datastore orchestrator

### **Skills & Interactions (4)**
16. **Skills Registry** — Capability discovery + versioning
17. **Interact Module** — Mobius-interact v1 + integrations (FROZEN)
18. **Download Skill** — Guarded document proxy
19. **Chat Telemetry** — Query logging + trace collection

### **Operations & Infrastructure (4)**
20. **Platform Database** — Schema + sync contracts + data models
21. **Authentication** — SSO + session management
22. **Task Manager** — Credential import + bulk operations
23. **Observability & Governance** — Monitoring + specs catalog + policies

---

## 🔄 Tab Design Framework

### **User Tab** — "What can users do?"
**Columns per module:**
- Module name
- Status badge (✅ LIVE | 🔨 IN PROGRESS | ⏸️ BLOCKED | 🗺️ PLANNED)
- User-facing capability (1-2 sentences)
- Entry point (button/link/UI location)
- Key features (bullet list)

**Example — Payor Dashboard:**
```
Module: Payor Dashboard
Status: ✅ LIVE
Capability: View active health plans, manage enrollment, track appeals status
Entry Point: /payors → Plan selector → Dashboard
Key Features:
  • Plan summary (active members, utilization rate)
  • Appeals tracker (open, resolved, trend)
  • Compliance checklist
```

---

### **Technical Tab** — "Where does it run?"
**Columns per module:**
- Module name
- Status badge (same)
- Owner (agent or team)
- Service/Repo (if applicable)
- Dependencies (other modules it needs)
- Data model (schema anchor, table/collection name)
- API/Interface (entry point for external callers)

**Example — Payor Dashboard:**
```
Module: Payor Dashboard
Status: ✅ LIVE
Owner: Platform UX Architect
Service: mobius-payor / product-awareness (FE)
Dependencies: Platform Database, Authentication, Payor Policy Agent
Data Model: health_plans, payor_profiles (pgvector)
API: GET /payors/{org_id}/health_plans → [plan_id, plan_name, status]
```

---

### **Specs Tab** — "Is it done?"
**Columns per module:**
- Module name
- Status badge (same)
- Spec link (→ GitHub markdown)
- Owner (agent or team)
- Gate status (RCM 8-gate progression: 1=design, 2=build, ..., 8=archive)
- Acceptance criteria (checklist)
- Sign-off status (who, when)
- Next review date

**Example — Payor Dashboard:**
```
Module: Payor Dashboard
Status: ✅ LIVE
Spec: docs/product-docs/payor-platform-spec.md
Owner: Platform UX Architect
Gate Status: Gate 7/8 (live, monitoring)
Acceptance Criteria:
  ✅ Show active plans
  ✅ Display appeals tracker
  ✅ HIPAA compliance verified
  🔨 A/B test compliance checklist UX (in progress)
Sign-off: PA Architect (2026-07-15) + UX Architect (2026-07-18)
Next Review: 2026-10-01 (Q4 standing review)
```

---

### **Eval/Test Tab** — "Is it validated?" (OWNED BY EVAL AGENT)
**Columns per module:**
- Module name
- Status badge (same)
- Test coverage (% unit tests, % integration tests)
- Eval metrics (primary: accuracy/F1/recall; secondary: latency/cost)
- Confidence level (green/yellow/red based on bandit data)
- Last eval run (date, version)
- Outstanding issues (count: P0/P1/P2)
- Eval owner (Eval Agent or delegated)

**Example — Payor Dashboard:**
```
Module: Payor Dashboard
Status: ✅ LIVE
Test Coverage: 87% unit | 64% integration (target: 90% unit, 75% integration)
Eval Metrics:
  • Accuracy: 0.94 (target: 0.92)
  • Latency p95: 280ms (target: 300ms)
  • Cost per query: $0.032 (target: $0.05)
Confidence: 🟢 HIGH (5000+ samples, CI > 0.95)
Last Eval: 2026-08-10 (v2.3.1)
Outstanding Issues: P0: 0 | P1: 2 ("appeals tracker date format") | P2: 3
Eval Owner: Eval Agent (primary), UX Architect (secondary)
```

---

### **Git Tab** — "What changed?" (OWNED BY TECHNICAL TEAM)
**Columns per module:**
- Module name
- Status badge (same)
- Latest commit (commit hash, message, date, author)
- Branch status (main? staging? feature branch?)
- Deployment status (✅ LIVE on prod | 🔨 STAGING | 🗺️ DEV ONLY)
- Version (semver tag or docker image SHA)
- Last deployed (date, deployed by)
- Pending changes (commits ahead of prod, count)
- Build status (✅ passing | ⚠️ failing | 🔨 running)

**Example — Payor Dashboard:**
```
Module: Payor Dashboard
Status: ✅ LIVE
Latest Commit: 3f8a2c9 "fix: compliance checklist date formatting" (2026-08-11, @uxa)
Branch: main
Deployment: ✅ LIVE on prod (mobile: staging)
Version: v2.3.1 (docker: gcr.io/.../payor-dashboard:v2.3.1)
Last Deployed: 2026-08-11 19:32 UTC by DevOps (CI/CD auto)
Pending Changes: 0 commits ahead of prod
Build Status: ✅ All checks passing (unit: ✅, integration: ✅, lint: ✅, deploy: ✅)
Next Deployment Window: 2026-08-18 (weekly Sunday 0200 UTC)
```

---

## 📅 Sprint Board Structure

### **Active Sprint** (Current)
**Sprint name:** Sprint 35 (Aug 12–Aug 26, 2026)  
**Modules with active work:**
- Router Agent: Optimization logic design (with Eval)
- Chat Refactor: Backend review audit
- Filler d (Web): DB url field (blocked on Database team)
- Onboarding Section: Design + build (start of new work)
- Platform Coherence: Tab alignment + sprint board (start of new work)

**Table:**
| Module | Owner | Status | Started | Est. Complete | Notes |
|--------|-------|--------|---------|---|---|
| Router optimization | Router Agent + Eval | 🔨 IN PROGRESS | 2026-08-10 | 2026-08-24 | Waiting on joint design session |
| Chat refactor audit | Chat Agent | 🔨 IN PROGRESS | 2026-08-05 | 2026-08-28 | 3 envelopes missing, pending post-RAG-P1 |
| Filler d url field | Database team | ⏸️ BLOCKED | 2026-08-01 | TBD | Awaiting DB schema review/sign-off |
| Onboarding section | PA Architect | 🔨 JUST STARTED | 2026-08-12 | 2026-08-31 | Low priority but high leverage for team scale |
| Platform coherence tabs | PA Architect | 🔨 JUST STARTED | 2026-08-12 | 2026-09-30 | Align User/Technical/Specs; add sprint board |

---

### **Previous Sprint Archive**

**Sprint 34 (Jul 29–Aug 11, 2026)** — Completed
- ✅ Specs Catalog deployment (git-backed, no-rebuild)
- ✅ Specs Catalog UI (7 tabs, agent ownership table)
- ✅ Platform schematic integration (iframe embed)
- ✅ RAG Agent story documented (Retriever → Router)

**Sprint 33 (Jul 15–Jul 28, 2026)** — Completed
- ✅ Router Agent kickoff spec (dual-allocator design)
- ✅ Observer Agent spec + ride-along logic
- ✅ Pool Agent P0 bug fixes verified (3 critical: column ref, tag-coverage, dedup)
- ✅ Filler strategies live (a/b/c/s; d blocked on DB)

**[Archive continues — older sprints visible via tabs]**

---

## 🎓 Onboarding Section

### **New Tab: Onboarding** (addition to platform view)

**Purpose:** Day-1 orientation for new team members — taxonomy, module map, workflows

**Sections:**

#### **1. Welcome & Quick Start** (2 min read)
- "You're now on the Mobius platform team. This is your guide to the system."
- 3-button quick nav: "Show me the surfaces" | "Show me the agents" | "Show me my first task"
- Link to /onboarding/checklist

#### **2. Mobius 101** (5 min)
**What is Mobius?**
- One-sentence: "Platform for healthcare team collaboration: evidence-based appeals + policy compliance via agentic RAG."
- The 3 user surfaces: Chat, Dashboard, Vault
- The 5 core intelligence layers: Retriever → Router → Eval → Agents → Skills

**Key terms (interactive glossary):**
- `RAG` — Retrieval-Augmented Generation; our evidence retrieval + ranking
- `Agent` — Autonomous module owning one domain (Appeals, Payor policy, etc.)
- `Gate` — Design milestone (8-step RCM progression)
- `Spec` — Authoritative design doc (in Specs Catalog)
- `Sprint` — 2-week work cycle with clear ownership

#### **3. Module Map** (interactive)
**Clickable module grid:**
- 23 modules in 4 groups (Surfaces, Agents, Skills, Operations)
- Click a module → 1-page sheet showing:
  - What it does
  - Who owns it
  - Current status
  - Link to spec
  - First task (if applicable)

**Example — Click "Chat Interface":**
```
# Chat Interface
One-line: Conversational query interface + vault upload for healthcare teams

Status: ✅ LIVE (with active backend refactor in progress)
Owner: Chat Agent + Chat UX Architect
Service: mobius-chat (FE + BFF)

What it does:
• Take natural language query about health plans, appeals, policies
• Return answer with citations + confidence score
• Let users upload documents to personal vault

Who uses it:
• Healthcare staff (appeals specialists, compliance managers)
• External API consumers via GraphQL

What's your first task if you own this?
→ Read: docs/mobius-thesis.md (2 min)
→ Demo: https://mobius-chat-ortabkknqa-uc.a.run.app (live, try asking "what's our appeal timeline?")
→ Explore: mobius-chat/frontend/ to see the FE stack

Current blockers (if you're joining to unblock something):
• Backend refactor: 3 missing envelopes in chat-to-RAG contract (in progress)
```

#### **4. First Week Workflow**
**Day 1:**
- [ ] Read Mobius thesis (2 min)
- [ ] Try the chat live (2 min)
- [ ] Tour the module map (5 min)
- [ ] Intro to your tech lead

**Day 2-3:**
- [ ] Read your module's spec
- [ ] Attend weekly standup (8am)
- [ ] Shadow your tech lead on a small task

**Day 4-5:**
- [ ] Contribute to a non-critical module (no gates involved)
- [ ] Review a peer's work
- [ ] Commit your first code

#### **5. Org Chart & Owners**
**Interactive table:**
| Role | Name | Modules | Slack |
|------|------|---------|-------|
| PA Architect (Lead) | Ananth | Governance, Specs Catalog, Onboarding | @ananth |
| Chat Agent | [Name] | Chat, Chat UX, Bubbles | @chat-owner |
| Retriever Agent | [Name] | RAG pipeline, Pool, Fillers | @retriever-owner |
| ... | ... | ... | ... |

**"Who do I ask about X?" quick link:**
- "Questions about chat UX?" → Chat Agent
- "Need an appeals playbook generated?" → Appeals Agent
- "PHI classifier blocking my docs?" → PHI Classifier Agent
- "Schema question?" → Database team (Platform Architects)

#### **6. Key Rituals**
- **Daily standup:** 8am (fleet health, blockers, quick ask-for-help)
- **Weekly tech review:** Thursday 2pm (one module deep-dives, sign-offs)
- **Quarterly alignment:** Oct 1, Jan 1, Apr 1, Jul 1 (all agents report status)
- **Office hours:** TBD (ad-hoc questions from team)

---

## 📈 Completion Roadmap

### **Phase 1: Framework + User Tab (100% by 2026-08-24)**
- [x] Define 23-module unified list (DONE — above)
- [ ] Update User Tab with all 23 modules + capability descriptions
- [ ] Add status badges + entry points
- **Effort:** 3–4 days  
- **Blocker:** None  
- **Owner:** PA Architect

### **Phase 2: Technical Tab (100% by 2026-09-07)**
- [ ] Create Technical Tab UI (clone User Tab structure, change columns)
- [ ] Populate all 23 modules with: owner, service, dependencies, data model, API
- [ ] Verify data accuracy against CLAUDE.md + git
- **Effort:** 4–5 days  
- **Blocker:** Database team confirms schema anchor per module  
- **Owner:** PA Architect + Platform Architects

### **Phase 3: Specs Tab Refinement (100% by 2026-09-14)**
- [ ] Verify all 23 modules have linked specs (or mark "no spec yet")
- [ ] Add gate-status column (1–8 RCM progression per module)
- [ ] Add acceptance-criteria checklist per module
- [ ] Add sign-off tracking (who signed off, when)
- **Effort:** 3–4 days  
- **Blocker:** Agents confirm their specs are authoritative  
- **Owner:** PA Architect + all agents

### **Phase 4: Eval/Test Tab (100% by 2026-09-21)**
- [ ] Create Eval/Test Tab UI (test coverage, eval metrics, confidence, outstanding issues)
- [ ] Populate all 23 modules with test coverage % from CI logs
- [ ] Add eval metrics per module (accuracy/F1/latency/cost)
- [ ] Add confidence levels + last eval run date
- [ ] Wire up "Outstanding Issues" count from bug tracking
- **Effort:** 4–5 days  
- **Blocker:** Eval Agent confirms metrics schema + CI integration  
- **Owner:** Eval Agent (primary) + PA Architect (UI/integration)

### **Phase 5: Git Tab (100% by 2026-09-28)**
- [ ] Create Git Tab UI (latest commit, branch, deployment status, version, build status)
- [ ] Populate all 23 modules with latest commit from GitHub API
- [ ] Add deployment status (prod/staging/dev) via Cloud Run metadata
- [ ] Add build status from CI/CD pipeline
- [ ] Add version tags + last deployed date
- **Effort:** 4–5 days  
- **Blocker:** DevOps confirms CI/CD metadata access  
- **Owner:** Technical team (primary) + PA Architect (UI/integration)

### **Phase 6: Sprint Board (100% by 2026-10-05)**
- [ ] Create "Active Sprint" table (current work, ETA, owner, notes)
- [ ] Archive "Previous Sprints" (clickable timeline, Sprint 34 / 33 / 32 / ...)
- [ ] Populate with data from memory + current work assignments
- **Effort:** 2–3 days  
- **Blocker:** None  
- **Owner:** PA Architect

### **Phase 7: Onboarding Section (STANDING RESPONSIBILITY)**
- [ ] Build Onboarding UI tab (Welcome, 101, Module Map, First Week, Org Chart, Rituals)
- [ ] Write all 6 sections (Mobius 101 + interactive glossary)
- [ ] Build clickable module-grid + first-task recommendations
- [ ] Populate Org Chart + Slack handles
- [ ] **Ongoing:** Update onboarding every sprint (new modules, changed rituals, Org Chart changes)
- **Effort:** 5–6 days (initial) + 1–2 hours/sprint (maintenance)  
- **Blocker:** Org chart confirmation (who owns what)  
- **Owner:** PA Architect (Ananth) — this is my standing responsibility for team scaling

### **Phase 8: Verification + Sync (100% by 2026-10-12)**
- [ ] Cross-check all 5 tabs: same module order, same status across all views
- [ ] Verify all specs links work + content is current
- [ ] Verify all eval metrics pull live from Eval Agent
- [ ] Verify all git info pulls live from GitHub API
- [ ] Test onboarding flow with a new team member (pilot)
- [ ] Commit all changes to git
- **Effort:** 2–3 days  
- **Blocker:** None  
- **Owner:** PA Architect

---

## 📊 Completion Status Tracker

| Phase | What | Status | % Complete | Est. Done | Owner |
|-------|------|--------|------------|-----------|-------|
| **Phase 1** | 23-module list + User Tab | 🔨 IN PROGRESS | 10% | 2026-08-24 | PA Architect |
| **Phase 2** | Technical Tab (services, APIs) | 🗺️ PLANNED | 0% | 2026-09-07 | PA Architect + Technical |
| **Phase 3** | Specs Tab (gates, acceptance) | 🗺️ PLANNED | 0% | 2026-09-14 | PA Architect + Agents |
| **Phase 4** | Eval/Test Tab (metrics, coverage) | 🗺️ PLANNED | 0% | 2026-09-21 | Eval Agent + PA Architect |
| **Phase 5** | Git Tab (commits, deployment) | 🗺️ PLANNED | 0% | 2026-09-28 | Technical Team + PA Architect |
| **Phase 6** | Sprint Board (current + archive) | 🗺️ PLANNED | 0% | 2026-10-05 | PA Architect |
| **Phase 7** | Onboarding (STANDING RESP.) | 🗺️ PLANNED | 0% | Initial 2026-10-05, then ongoing | PA Architect (Ananth) |
| **Phase 8** | Verification + Final Sync | 🗺️ PLANNED | 0% | 2026-10-12 | PA Architect |
| **TOTAL** | **5-Tab Platform + Onboarding** | 🔨 IN PROGRESS | **~10%** | **2026-10-12** | PA Architect + all teams |

---

## 🎯 Success Criteria (Done = All True)

- [ ] All 5 tabs (User/Technical/Specs/Eval/Git) show same 23 modules in same order
- [ ] Each tab has consistent column headers + status badge (same across all views)
- [ ] User tab: shows entry points + key features (product POV)
- [ ] Technical tab: shows owner, service, dependencies, data model, API (infrastructure POV)
- [ ] Specs tab: shows gate status, acceptance criteria, sign-offs (delivery POV)
- [ ] Eval/Test tab: shows test coverage, eval metrics, confidence, outstanding issues (quality POV)
- [ ] Git tab: shows latest commit, deployment status, build health, version (ops POV)
- [ ] All specs linked from Specs Catalog exist + are current
- [ ] Eval metrics pull live from Eval Agent infrastructure
- [ ] Git info pulls live from GitHub API + CI/CD pipeline
- [ ] Sprint board shows current + past sprints (searchable/filterable)
- [ ] Onboarding section is first thing new hires see on Day 1
- [ ] One team member can complete onboarding using Onboarding section alone (no external help)
- [ ] PA Architect (Ananth) owns onboarding updates as standing responsibility (1–2 hrs/sprint)
- [ ] All module data is version-controlled (git), not ephemeral
- [ ] Weekly standup references sprint board + flags modules with ⏸️ BLOCKED status
- [ ] Quarterly review uses Specs tab + Eval tab + Git tab to validate module maturity

---

## 📝 Implementation Notes

**Implementation order:** User → Technical → Specs → Eval/Test → Git → Sprint → Onboarding → Verification  
**Why:** Each phase builds on the previous:
1. User is foundation (capabilities)
2. Technical adds depth (infrastructure)
3. Specs adds gates (delivery criteria)
4. Eval adds validation (quality proof)
5. Git adds history (change tracking)
6. Sprint adds workflow (when)
7. Onboarding stitches it together (for new hires)
8. Verification ensures consistency

**Git commits per phase:**
- Phase 1: `docs: add 23-module unified framework + update user tab`
- Phase 2: `docs: add technical tab + service mapping`
- Phase 3: `docs: refine specs tab + gate tracking`
- Phase 4: `docs: add eval/test tab + quality metrics`
- Phase 5: `docs: add git tab + deployment status`
- Phase 6: `docs: add sprint board + archive`
- Phase 7: `docs: add onboarding section (PA Architect standing responsibility)`
- Phase 8: `docs: final verification + sync all 5 tabs`

**PA Architect's Standing Responsibilities (Onboarding)**
- **Initial build** (Phase 7, ~5–6 days): Create Onboarding section with all 6 subsections
- **Ongoing maintenance** (1–2 hours/sprint, every sprint):
  - Update Org Chart when roles change
  - Add new modules to Module Map when they launch
  - Revise "First Week" workflow based on feedback from recent hires
  - Update rituals (standup time, tech review cadence, quarterly dates)
  - File "Onboarding Gap" issues if new hires report confusion
- **Quarterly refresh** (1 hour, each quarterly review):
  - Revisit all links (do they still work?)
  - Update module ownership + Slack handles
  - Archive old rituals, announce new ones
  - Metrics: track new-hire onboarding time (target: <1 hour from first day to first code commit)

**PA Architect's Weekly Check-in (Standalone)**
- Monday: Update sprint board with current status + blockers
- Wednesday: Verify specs links (broken links → immediate file-it)
- Thursday: Check if any module's test coverage dropped below target (flag with Eval Agent)
- Friday: Sync new changes to git + update completion tracker + onboarding delta (1–2 hrs)

---

## 💡 Why This Matters

**For the team:**
- New hires onboard in **1 hour** (not 1 week) — PA Architect owns this
- Specs Catalog becomes **single source of truth** (auditable, version-controlled)
- Sprint board replaces Slack threads (persistent, searchable, archivable)
- Everyone sees same 23 modules from 5 angles: "what's done, where it runs, if it's validated, what changed, how we got here"
- Eval metrics + test coverage visible to everyone (quality becomes transparent)
- Git status shows health at a glance (no more "is this version deployed?")

**For you (PA Architect):**
- One place to manage everything (eliminates "go to different places" friction)
- **Onboarding is your standing responsibility** — new hires become your responsibility, not a one-time doc
- Forced discipline: can't claim a module is LIVE if it doesn't have spec + acceptance criteria + test coverage + git health
- Quarterly reviews run like clockwork (specs → gates → eval results → git status → archive)
- Team scales with **quality built in** (not bolted on later)

---

## 🚀 Ready to Launch

**Direction locked:**
- 5 tabs (User/Technical/Specs/Eval/Git) + Sprint Board + Onboarding
- 23 modules, same order, different lenses
- PA Architect owns onboarding as standing responsibility
- Eval Agent owns Eval/Test tab
- Technical team owns Git tab
- All others contribute data to their modules

**Next step:** Phase 1 starts 2026-08-13 (User Tab + framework)

**Timeline to 100% coherence:** 2026-10-12 (10 weeks from now)
