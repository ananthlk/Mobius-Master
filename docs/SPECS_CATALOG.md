# Mobius Specs Catalog
**Master Index of All Product Governance, Architecture, and Design Specifications**

> **Last Generated:** 2026-08-11  
> **This is the source of truth.** Every feature, gate, and product promise is traced here with acceptance criteria and sign-off status.

---

## Quick Navigation

- [Product Governance](#product-governance) — RCM gates, quarterly alignment, business model
- [Product Surfaces](#product-surfaces) — Chat, Vault, Appeals, Credentialing
- [Retrieval & Intelligence](#retrieval--intelligence) — RAG pipeline, Router, Observer, Synthesis, Eval
- [Agents & Ownership](#agents--ownership) — Agent charters and responsibilities
- [Design Systems](#design-systems) — Governance surfaces, UX patterns, components

---

## Product Governance

### RCM Model & Gates (Foundation)

| Spec | Status | Owner | Updated | Purpose |
|------|--------|-------|---------|---------|
| [The Mobius Model](product-docs/mobius-model.md) | ✅ Live | PA Architect | 2026-07-30 | 8 RCM gates, 3-tier progression, economics, current position |
| [Why Mobius? (Philosophy)](product-docs/WHY_MOBIUS_NAME.md) | ✅ Live | PA Architect | 2026-08-11 | Möbius strip metaphor, care/finance as one surface |
| [Mobius Self-Awareness](product-docs/mobius-thesis.md) | ✅ Live | PA Architect | 2026-08-11 | "Tell me about yourself" positioning, RCM gate progression |
| [CMHCs Partner Pitch](product-docs/MOBIUS_PARTNER_PITCH.md) | ✅ Live | PA Architect | 2026-08-06 | Quantified economics, FL Medicaid BH opportunity, 5 live gates |

**Acceptance Criteria:**
- [ ] Model correctly maps all 8 gates to deployment status
- [ ] Economics align with actual FL Medicaid BH data (2019–2024)
- [ ] Current position reflects real, verified product state
- [ ] All references use this as authoritative source

---

### Quarterly Alignment & Governance

| Spec | Status | Owner | Updated | Purpose |
|------|--------|-------|---------|---------|
| [Quarterly Vision Alignment](product-docs/quarterly-vision-alignment.md) | ✅ Live | PA Architect | 2026-07-30 | Standing review (Jan/Apr/Jul/Oct), gate owner reporting, blocker tracking |
| [Q4 2026 Alignment Template](product-docs/quarterly-alignment-q4-2026-TEMPLATE.md) | ✅ Template | PA Architect | 2026-07-30 | Gate owner checklist, Oct 1–7 deadline |
| [Governance Surface Pattern](mobius-design/GOVERNANCE_SURFACE_SPEC.md) | 🔨 UX Review | UX Architect | 2026-07-30 | Reusable dashboard pattern (tier/gate cards, status badges, detail panels) |
| [Hub Dashboard Prototype](product-docs/hub-dashboard-prototype.html) | ✅ Live | PA Architect | 2026-07-30 | Interactive prototype, 3 tabs (Dashboard/Status/Blockers) |
| [UX Review Package](mobius-design/UX_REVIEW_PACKAGE.md) | 🔨 Review | UX Architect | 2026-07-30 | Comprehensive UX review checklist + testing steps |

**Acceptance Criteria:**
- [ ] Gate owners submit quarterly status with blockers + dependencies
- [ ] Product-truth alignment verified (docs ≠ live flagged as ⏸️ Blocked)
- [ ] UX Architect approves Governance Surface pattern
- [ ] Hub Dashboard deployed and accessible to all agents

---

## Product Surfaces

### Chat (Gate 4–7: Payor Policies, Credentialing, Appeals, Coding)

| Spec | Status | Owner | Updated | Purpose |
|------|--------|-------|---------|---------|
| [Mobius Chat Product Doc](product-docs/mobius-chat.md) | ✅ Live | Chat FE/UX Agent | 2026-08-11 | User-facing product spec, all modes, training, Vault, diagnostics |
| [Chat v2 FE Sign-Off (§2.1, §3)](product-docs/mobius-chat.md#current-work-in-progress-2026-08-11) | ⏸️ Awaiting | PA Architect | 2026-08-11 | §2.1 progressive summary ≤5 lines, §3 surface roadmap v1 final, v2 messaging, PHI egress disclosure |
| [Chat Refactor (Backend Review)](product-docs/mobius-chat.md#current-work-in-progress-2026-08-11) | 🔨 In Progress | Chat FE/UX Agent | 2026-08-11 | 3 missing envelopes post-RAG-P1, audit required |
| [Answer Cache Service](product-docs/mobius-chat.md#current-work-in-progress-2026-08-11) | 🔨 Dev → Chat Edge | CACHE Agent | 2026-08-11 | pgvector service LIVE, awaiting Chat edge integration |

**Acceptance Criteria:**
- [ ] Chat v2 messaging aligns with §2.1 progressive summary (product-truth sign-off locked)
- [ ] Answer Cache edge wired and tested
- [ ] FE refactor 3 envelopes complete
- [ ] Training mode, Vault block, Diagnostics tab all verified live

---

### Appeals (Gate 6: Authorization/Appeals, W7 Roadmap)

| Spec | Status | Owner | Updated | Purpose |
|------|--------|-------|---------|---------|
| [Appeals Agent Charter](appeals-agent-spec.md) | ✅ Confirmed | Appeals Agent | 2026-07-22 | Ownership of appeals domain end-to-end (denials→letters) |
| [Appeals Decision Engine Product-Truth Sign-Offs](product-docs/mobius-chat.md#current-work-in-progress-2026-08-11) | ✅ Locked | PA Architect | 2026-08-11 | (1) Mode visibility: hidden until live, (2) Promise fidelity: from governor state, (3) Corpus timing: post-M1 |

**Acceptance Criteria:**
- [ ] Appeals W1 DB build approved (Status: ✅ Approved)
- [ ] Tech-health sign-off unconditional (Status: ✅ Approved)
- [ ] Eval ratified decision engine (Status: ✅ Approved)
- [ ] W7 chat surface integrates mode rules
- [ ] Post-M1: product-help docs filed to corpus with real usage data

---

### Credentialing & Roster (Gate 5: Credentialing)

| Spec | Status | Owner | Updated | Purpose |
|------|--------|-------|---------|---------|
| [Credentialing & Roster Product Doc](product-docs/credentialing-and-roster.md) | ✅ Live | Credentialing Agent | 2026-07-14 | Provider enrollment verification, reconciliation, roster operations |

**Acceptance Criteria:**
- [ ] check_provider_credentialing MCP tool returns real PML + NPPES + compliance data
- [ ] Roster reconciliation model (in_both / external_only / internal_only) deployed
- [ ] Ghost-billing checks wired

---

## Retrieval & Intelligence

### RAG Pipeline (Steps 1–5: Shape→Pool→Fillers→Router→Observer/Synthesis)

| Spec | Status | Owner | Updated | Purpose |
|------|--------|-------|---------|---------|
| [RAG Backend Product Doc](product-docs/rag-backend.md) | ✅ Live | Retriever Agent | 2026-08-11 | Complete 5-step pipeline, all strategies a–e, observer/synthesis status |
| [Retriever Fleet Schematic (LIVE STATUS)](rag-agents/retriever-fleet-schematic.md) | ✅ Authoritative | Retriever Agent | 2026-08-11 | Source of truth for all Steps 1–5 real state, P0 fixes, blockers |

#### Step 1: Shape (Query Classification & Structuring)

| Spec | Status | Owner | Updated | Purpose |
|------|--------|-------|---------|---------|
| [Shape Gate Module (1a)](rag-agents/shape-gate-module-spec.md) | ✅ Closed | Retriever Agent | 2026-03-15 | 6-contour classification, routing decision |
| [Shape Reformat Module (1b)](rag-agents/shape-reformat-module-spec.md) | ✅ Closed | Retriever Agent | 2026-03-15 | Contour → posture + rewrites |
| [Shape Structure Module (1c)](rag-agents/shape-structure-module-spec.md) | ✅ Closed | Retriever Agent | 2026-03-20 | ResourcePosture 6 fields (breadth, confidence_bar, max_attempts, speed_budget, token_budget, authority_requirement) |
| [Shape Slots Module (1d)](rag-agents/shape-slots-module-spec.md) | ✅ Closed | Retriever Agent | 2026-04-01 | AnswerShapeResult slots with semantics + capacity |

**Acceptance Criteria:**
- [ ] All 6 fields in ResourcePosture properly threaded through Router
- [ ] Slot semantics match Router's assignment logic
- [ ] Per-caller-mode defaults work (token_budget unbounded by default)

#### Step 2: Pool (Candidate Retrieval)

| Spec | Status | Owner | Updated | Purpose |
|------|--------|-------|---------|---------|
| [Pool Module Spec](rag-agents/pool-module-spec.md) | ✅ Closed | Retriever Agent | 2026-03-20 | One shared pool per query, multi-strategy union, dedup, neighbor expansion |

**Acceptance Criteria (P0 Fixes 2026-07-24):**
- [ ] authority_level column bug FIXED (was nonexistent, broke tag-select/vector/inherited arms)
- [ ] tag-coverage clamping FIXED (was false-positive 1.0 scores)
- [ ] Content dedup by normalized-text-grouping VERIFIED (not content_sha)

#### Step 3: Fillers (Multi-Strategy Ranking)

| Spec | Status | Owner | Updated | Purpose |
|------|--------|-------|---------|---------|
| [Fillers Schematic (a–e)](rag-agents/fillers-schematic-spec.md) | ✅ All Built | Retriever Agent | 2026-07-24 | BM25 + Vector + LLM-validate + Web + Payor fact-store |

**Per-Filler Status:**

| Filler | Status | Owner | Purpose |
|--------|--------|-------|---------|
| **a (BM25)** | ✅ Live | Retriever Agent | Deterministic rerank, authority-weighted vocabulary |
| **b (Vector)** | ✅ Live | Retriever Agent | Junk-defense (length floor, exact-text dedup) |
| **c (LLM Retrieval)** | ✅ Live | Retriever Agent | Quote-verification gate, hallucination detection |
| **d (Web Search)** | ✅ Live | Retriever Agent | Vertex AI Grounding primary, DDG legacy fallback, speculative prefetch |
| **s (Fact Store)** | ✅ Live | Payor Platform Agent | Deterministic chunk_id (payer_key\|record_type\|predicate\|answer_text) |

**Acceptance Criteria:**
- [ ] All 5 fillers wired and returning ranked results
- [ ] Quote-verification catches hallucinations (c real case validated)
- [ ] Speculative prefetch delivers 20–53% latency savings (d measured)
- [ ] Fact-store determinism verified (same fact = same id every call)

#### Step 4: Router (Strategy Allocation & Continuation)

| Spec | Status | Owner | Updated | Purpose |
|------|--------|-------|---------|---------|
| [Router Build Spec](rag-agents/router-build-spec.md) | ✅ Live | Retriever Agent | 2026-07-15 | Thompson sampling, shadow allocator, authority/citability gates, continuation logic |
| [Router Module Spec](rag-agents/router-module-spec.md) | ✅ Live | Retriever Agent | 2026-07-15 | Detailed execution rules, permutation-invariance |

**Acceptance Criteria:**
- [ ] Payload/token gate enforced (capacity × PAYLOAD_TOKENS_PER_CHUNK ≤ allowance)
- [ ] Authority/citability gate blocks d for required slots when "citable_required"
- [ ] Execution-order permutation-invariance verified (contract test passes)
- [ ] Continuation verdicts (WOULD_BENEFIT/SATISFIED/EXHAUSTED_ATTEMPTS/EXHAUSTED_BUDGET/ERROR) logged per slot

#### Step 4e: Observer (Per-Slot Continuation Verdicts)

| Spec | Status | Owner | Updated | Purpose |
|------|--------|-------|---------|---------|
| [Observer Module Spec](rag-agents/observer-module-spec.md) | 🔨 Built+Validated | Retriever Agent | 2026-07-24 | Per-slot "would this benefit from another turn?" logic, strategy-specific verdicts |

**Acceptance Criteria:**
- [ ] Observer BUILT + LIVE-VALIDATED ✅
- [ ] Real logic shipped for a/b/c/s; d placeholder ⏳
- [ ] Emits Router verdict enum + reason string for Eval
- [ ] ⏸️ **AWAITING GATE:** Eval's calibration plan before wiring to production

#### Step 5: Synthesis (Result Compilation)

| Spec | Status | Owner | Updated | Purpose |
|------|--------|-------|---------|---------|
| [Synthesis Module Spec](rag-agents/synthesis-module-spec.md) | 🔨 Built+Spec | Retriever Agent | 2026-07-24 | Per-slot rerank, cross-slot dedup, neighbor completion, doc-name resolution, telemetry compilation |

**Acceptance Criteria:**
- [ ] Synthesis v1 BUILT ✅
- [ ] Spec WRITTEN ✅
- [ ] Verified/unverified + planned/live passthrough BYTE-FOR-BYTE ✅
- [ ] ⏸️ **AWAITING GATE:** AsyncSession threading (Fillers already have this) before orchestrator integration

---

### Eval & Calibration

| Spec | Status | Owner | Updated | Purpose |
|------|--------|-------|---------|---------|
| [Eval Workflow Tooling](rag-agents/eval-workflow-tooling-spec.md) | ✅ Live | Eval Agent | 2026-07-15 | Question-bank, priors, provenance-sha spine |
| [Adjudicator Calibration](rag-agents/adjudicator-calibration-spec.md) | ✅ Live | Eval Agent | 2026-07-15 | gemini-2.5-pro ruler consistency (judge == prod-scorer == bandit) |

**Acceptance Criteria:**
- [ ] Observer calibration plan drafted and ready for sign-off
- [ ] Synthesis calibration plan queued after Observer ships

---

## Agents & Ownership

### Standing Agents (Fleet Ownership)

| Agent | Status | Charter | Updated | Purpose |
|-------|--------|---------|---------|---------|
| [Appeals Agent](appeals-agent-spec.md) | ✅ Confirmed | 2026-07-22 | 2026-07-22 | Own appeals domain end-to-end (denials→letters) |
| [Payor Platform Agent](platform-agent-spec.md) | ✅ Confirmed | 2026-07-22 | 2026-07-22 | Own cross-module contracts, config, build (highest-blast-radius files) |
| [Retriever Agent](rag-agents/retriever-fleet-schematic.md) | ✅ Confirmed | — | 2026-08-11 | Own entire RAG pipeline (Steps 1–5) + Fillers a–e + Router + Observer + Synthesis |
| [Eval Agent](rag-agents/eval-workflow-tooling-spec.md) | ✅ Confirmed | — | 2026-07-15 | Own QA, calibration, judge loop, two-grade scoring |

**Acceptance Criteria:**
- [ ] Each agent's scope in ownership.yaml marked "confirmed"
- [ ] Agent has reachable session and can accept handoffs
- [ ] Critical gate owners documented (Eval for Observer/Synthesis, UX Architect for Governance Surface)

---

## Design Systems

### Governance Surfaces (Reusable Pattern)

| Spec | Status | Owner | Updated | Purpose |
|------|--------|-------|---------|---------|
| [Governance Surface Spec](mobius-design/GOVERNANCE_SURFACE_SPEC.md) | 🔨 UX Review | UX Architect | 2026-07-30 | Tier card, Gate card, Status badge, Detail panel — reusable across any agent |
| [UX Review Package](mobius-design/UX_REVIEW_PACKAGE.md) | 🔨 Review | UX Architect | 2026-07-30 | Comprehensive review checklist (layout, states, tokens, accessibility, responsive) |
| [Hub Dashboard Reference](product-docs/hub-dashboard-prototype.html) | ✅ Live | PA Architect | 2026-07-30 | Interactive prototype showing Dashboard/Status/Blockers tabs |
| [Business Model Lens](product-awareness/product_awareness/static/schematic.html) | ✅ Live | PA Architect | 2026-08-11 | Platform schematic with Business Model button (Tier A/B/C gates) |

**Acceptance Criteria:**
- [ ] UX Architect approves layout + tokens + accessibility
- [ ] Figma symbols created (TierCard, GateCard, StatusBadge, DetailPanel)
- [ ] Appeals Agent adopts for V1/V2/V3 roadmap
- [ ] Router Agent adopts for Phase 1/2/3 milestones

---

## Status Legend

| Badge | Meaning |
|-------|---------|
| ✅ Live | Deployed, verified, in production |
| 🔨 In Progress | Under active development, sign-off pending |
| 🗺️ Planned / Roadmap | Designed, not yet built |
| ⏸️ Blocked | Built but blocked on upstream dependency |
| 🔍 Under Review | Awaiting review/sign-off |

---

## Sign-Off Checklist

Use this as your onboarding checklist. Every team member should review and accept the spec corresponding to their role:

- [ ] **Product Lead** — Read [The Mobius Model](product-docs/mobius-model.md), [Quarterly Vision Alignment](product-docs/quarterly-vision-alignment.md)
- [ ] **Chat Owner** — Read [Chat Product Doc](product-docs/mobius-chat.md), accept v2 sign-off gates
- [ ] **RAG/Retriever Owner** — Read [Retriever Fleet Schematic](rag-agents/retriever-fleet-schematic.md), verify all Step 1–5 acceptance criteria
- [ ] **Appeals Owner** — Read [Appeals Charter](appeals-agent-spec.md), confirm locked gates, review product-help corpus timing
- [ ] **Payor Platform Owner** — Read [Payor Platform Charter](platform-agent-spec.md), draft contracts compatibility policy
- [ ] **UX/Design Lead** — Review [Governance Surface Spec](mobius-design/GOVERNANCE_SURFACE_SPEC.md), create Figma symbols
- [ ] **Eval Owner** — Draft Observer calibration plan, review Synthesis calibration requirements
- [ ] **Tech Review / QA** — Read [Technical Review Agent](technical-review-agent-spec.md), prepare for Tech Day

---

## How to Use This Catalog

1. **For team onboarding:** Share this page. Each role has a checklist above.
2. **For acceptance criteria:** Each spec section lists what "done" looks like. Review before handoff.
3. **For dependencies:** Check "Awaiting Gate" notes to see what's blocking each feature.
4. **For sign-offs:** Every spec has an "Acceptance Criteria" checkbox list — use these to gate releases.
5. **For status drift:** Compare the "Updated" date to today. If stale, file a `doc_stale` issue or ask the owner.

---

**Last reviewed:** 2026-08-11 by PA Architect  
**Next quarterly review:** 2026-10-01 (Q4 alignment)
