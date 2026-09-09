# Fleet Ownership Cleanup — Final Structure + New-Agent Specs

**Status:** proposed 2026-07-22 (Technical Review Agent draft, for Ananth to ratify + create).
**Enforced as:** the fleet's **first cleanup**, starting this week.
**The rule:** *every module has exactly one owner, and everyone understands it.*

Companion files: [`ownership.yaml`](../ownership.yaml) (machine source of truth) · [`docs/ownership.md`](ownership.md) (readable map) · [`docs/technical-review-agent-spec.md`](technical-review-agent-spec.md).

---

## 0. The principle & how it's enforced

1. **One module → one owner.** No module is unowned; no module has two owners. `mobius-skills` is owned at the *subdirectory* level (one owner per skill), not the repo level.
2. **`ownership.yaml` is the source of truth.** Git can't derive ownership (every commit is authored "Ananth"), so ownership is declared here. Every defect the Technical Day assigns resolves its assignee through this file.
3. **Item #9 becomes a hard gate.** The Technical Review Agent's AUTO check #9 fails for any path with no `confirmed` owner. Once ratified, an unowned or `proposed` module is itself a tracked defect until an owner accepts it.
4. **Creating the four new agents + confirming the scope-expansions is what makes #9 pass.** This spec is the closure plan.

> **Decisions locked 2026-07-22 (Ananth):** **6 new agents** — Platform, Skills, Analytics, Extension, **Auth** (dedicated P0 security surface), **Appeals** (important domain — created, not archived). Skills agent is *custodian* of the whole `mobius-skills` subsystem (repo + registry + runtime + MCP bridge + every undelegated skill: `email`/`healthcare`/`vibe`[=reference template]); individual skills are **delegated** to domain agents for their logic. User Manager stays unchanged (auth split into its own agent). Charters: [platform](platform-agent-spec.md) · [skills](skills-agent-spec.md) · [analytics](analytics-agent-spec.md) · [extension](extension-agent-spec.md) · [auth](auth-agent-spec.md) · [appeals](appeals-agent-spec.md).
>
> **Sequence (base version, target end of week):** (1) Eval + RAG baseline first → (2) Chat UI cleanup (UI + Chat agents) → (3) **stand up this tech structure** (create the 6 agents, confirm ownership, gate #9 live) → re-run the review against a fully-owned fleet.

---

## 1. Final target structure (every module owned)

Legend: **[NEW]** create this agent · **[+SCOPE]** existing agent's remit grows · unmarked = already clean.

### Product / service agents (unchanged owners)
| Module | Owner |
|---|---|
| mobius-chat | Chat agent |
| mobius-rag *(+ retriever, rag-api, answer-cache, document-viewer)* **[+SCOPE]** | RAG agent |
| mobius-payor | Payor agent |
| mobius-vault | Vault agent |
| mobius-interact | Interact agent |
| mobius-feedback | Feedback agent |
| mobius-db-agent *(+ migrations, dbt)* **[+SCOPE]** | DB agent → **Data & DB agent** |
| mobius-qa (+ qa-modules) | Eval agent |
| product-awareness | Product-Awareness agent |
| mobius-design | UX agent |
| Mobius-user | User Manager agent |
| mobius-auth **[NEW]** | **Auth agent** *(dedicated P0 security surface)* |
| mobius-os **[NEW]** | **Extension agent** |

### mobius-skills — subdir owners
| Subdir | Owner |
|---|---|
| phi-classifier | PHI Classifier agent |
| task-manager | Task agent |
| provider-roster-credentialing | Credentialing agent |
| org-intelligence | Org agent |
| instant-rag, chat-document-upload | Instant-RAG agent |
| doc-reader, google-search, web-scraper **[+SCOPE]** | RAG agent |
| email, healthcare, vibe *(vibe = reference template)* | **Skills agent** *(custodian — undelegated skills)* |
| appeals-agent **[NEW]** | **Appeals agent** *(important domain — dedicated)* |
| cmhc-cost-report, fl-medicaid-npi **[NEW]** | **Analytics agent** |

### The new domains (6 new agents)
| Module(s) | Owner |
|---|---|
| mobius-contracts, mobius-config, superrepo-root build/scripts (`module-hub`, `mstart/mstop/meval`, `requirements.txt`, root `*.py`) **[NEW]** | **Platform agent** |
| mobius-skills (repo + registry), mobius-skills-core, mobius-skills-mcp, undelegated skills **[NEW]** | **Skills agent** *(custodian; domain agents own delegated skills)* |
| mobius-story-ui, skills `cmhc-cost-report` + `fl-medicaid-npi`, Financial-Benchmarking specs, *Strategy* node **[NEW]** | **Analytics agent** |
| mobius-os **[NEW]** | **Extension agent** |
| mobius-auth **[NEW]** | **Auth agent** |
| appeals skill + *Appeals* node **[NEW]** | **Appeals agent** |

After this, **nothing** is on a catch-all — every module resolves to exactly one owner.

---

## 2. NEW AGENT — Platform agent

**Mission (one line):** Own the shared substrate every other module depends on — cross-module contracts, config, the skills runtime/bridge, and the superrepo's build/deploy scaffolding — and keep that blast-radius safe.

**Why it must exist:** these are the highest-blast-radius, lowest-watched files in the fleet. A breaking change to `mobius-contracts` silently breaks many modules; today nobody owns it. This is the single most important ownership gap.

**Owns:**
- `mobius-contracts/**` — cross-module schemas/interfaces (the seams between agents)
- `mobius-config/**` — shared configuration
- `mobius-skills-core/**`, `mobius-skills-mcp/**` — the skills runtime + MCP bridge that all skill subdirs ride on
- Superrepo-root build/deploy: `Dockerfile.module-hub`, `cloudbuild.module-hub.yaml`, `mstart`/`mstop`/`meval`, `requirements.txt`, root orchestration `*.py`

**Responsibilities:**
- Version and change-control `mobius-contracts` with an explicit compatibility policy (a contract change is a fleet event, announced before merge).
- Keep config + build reproducible; the served artifact traces to committed HEAD (feeds Technical-Day items #7, #19).
- Be the reachable owner for any superrepo-level or cross-cutting defect the Technical Day raises.

**Interfaces:** every agent (as the contract/config counterparty) · Technical Review Agent (receives platform defects) · DB agent (migrations/data-platform boundary) · Ananth (escalation).

**Non-goals:** does not own product features, any single service's business logic, or the data layer (that's Data & DB agent).

**Definition of ownership done:** `mobius-contracts`, `mobius-config`, `skills-core`, `skills-mcp`, and root build files show `owner: Platform agent, status: confirmed` in `ownership.yaml`, and the agent has acknowledged the scope.

---

## 3. NEW AGENT — Analytics agent (Market Intelligence)

**Mission (one line):** Own the market-intelligence and financial-benchmarking surfaces — the Strategy deck, provider/cost analytics, and the NPI/benchmarking skills — so the "Strategy" node finally has a home.

**Why it must exist:** there's a live *Strategy* schematic node and substantial financial-benchmarking/DOGE/KPI work, but no owning agent — cost-report and NPI skills are literally ownerless. This is a coherent, active domain.

**Owns:**
- `mobius-story-ui/**` — the Strategy deck / market-intelligence surface
- `mobius-skills/cmhc-cost-report/**` — CMHC cost reports
- `mobius-skills/fl-medicaid-npi/**` — FL Medicaid NPI validation/analytics
- `Financial Benchmarking specs/**` (superrepo dir) — the benchmarking spec set

**Responsibilities:**
- Own the Strategy node's accuracy (schematic status honest: planned ≠ live).
- Maintain the benchmarking/cost/NPI skills against real data; coordinate data needs with Data & DB agent.
- Receive + close any Technical-Day defect on these surfaces.

**Interfaces:** Data & DB agent (data source) · RAG/Payor (facts) · Product-Awareness (Strategy node render) · Technical Review Agent · Ananth.

**Non-goals:** not the data pipeline owner (consumes, doesn't own the warehouse); not a general reporting service.

**Definition of ownership done:** the four paths above show `owner: Analytics agent, status: confirmed` in `ownership.yaml`.

---

## 4. Scope-expansions for EXISTING agents (no new agent — just tell them)

These need a one-line "you now also own X" to the existing owner; no new session.

| Agent | Now also owns | Rationale |
|---|---|---|
| **RAG agent** | mobius-retriever, mobius-rag-api, mobius-answer-cache, mobius-document-viewer; skills doc-reader/google-search/web-scraper | all part of the retrieval/corpus/curation stack it already anchors |
| **DB agent** → *Data & DB agent* | mobius-migrations, mobius-dbt | migrations + data-build are its data-layer domain |

*(User Manager agent is unchanged — auth split into its own Auth agent, so no rename/expansion.)*

---

## 5. Open decisions — all resolved (2026-07-22)

None outstanding. `mobius-os` → Extension agent · auth → **dedicated Auth agent** · appeals → **dedicated Appeals agent** (important domain, not archived) · email/healthcare/vibe → Skills custodian · skills subsystem → Skills agent. Every module resolves to one owner.

---

## 6. Rollout — sequenced, base version, target end of week

**This ownership stand-up is step 3 of a 3-step week** (Ananth's sequence):
1. **Eval + RAG baseline** (Eval + RAG agents) — get that set first.
2. **Chat UI cleanup** (UI + Chat agents).
3. **Stand up this tech structure** ← then re-run the review against a fully-owned fleet.

Step 3, in order:
1. **Ananth creates** the 6 new agents — Platform, Skills, Analytics, Extension, Auth, Appeals — opening a session per agent pointed at its charter (`docs/<agent>-agent-spec.md`).
2. **Ananth notifies** the 2 existing agents of their §4 scope-expansions (RAG, Data & DB).
3. **Each new/expanded agent acknowledges** — flips its `ownership.yaml` rows `proposed`→`confirmed` + seeds a `project_<agent>` memory.
4. **Technical Review Agent** verifies every row resolves to a `confirmed` owner, then flips `ratified: true`.
5. **Gate goes live:** item #9 fails on any unowned/`proposed` path — an unowned module is itself a tracked defect.
6. **Re-run Technical Day** against a fully-owned fleet — every defect has a reachable assignee.

### Per-agent launch prompt (paste as the new session's first message)
> You are the **&lt;Name&gt; agent** for the Mobius fleet. Read your charter at `docs/&lt;name&gt;-agent-spec.md` and the ownership map at `ownership.yaml`. You own exactly the modules mapped to you there — no more, no less. Acknowledge your scope, flip your `ownership.yaml` rows from `proposed` to `confirmed`, seed a `project_&lt;name&gt;_agent` memory, and do your charter's "First tasks." You report to Ananth; the Technical Review Agent assigns you health-check defects on Technical Day.
