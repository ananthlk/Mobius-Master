# Mobius Agent Fleet — Structure & Manifesto

**Owned + kept current by: Broadcast** (fleet coordinator — carries + announces this; does not author or direct it).
**Only Ananth directs the fleet.** Established 2026-07-22.

This is how the Mobius agent fleet is organized and how it operates. Every agent reads it.

---

## Part 1 — The Structure: two tiers

### Horizontal — the Platform Architects
Own **cross-cutting standards every module must conform to.** They never own a product module; module-owners build *against* their standards.

| Architect | Owns the standard for… |
|---|---|
| **Technical Review** | structure & health — "built right + who owns it" |
| **Eval** | measurement & outcomes — "good, measurably" |
| **DB** | data-model & schema — "modeled + accessed right" |
| **UX** | design-system & experience — "consistent + usable" |
| **Product-Awareness** | product-truth & docs — "described truthfully + findable" |
| **Broadcast** | the fleet's voice — carries the standards, owns this manifesto, runs standup/standdown. Never assigns. |

### Vertical — the Module Owners
Own **and build** their product module, conforming to the architects' standards. E.g. Chat, Vault, Extension, Payor, Instant-RAG, PHI, Task, Org, Feedback, Interact, User Manager, Auth, Appeals, Credentialing, Analytics — and the **RAG group** below.

### A macro-agent, worked example — the RAG group
**RAG (macro)** = a no-code coordinator that herds four scoped sub-agents, each owning a module boundary:
- **Sourcing** — get docs in (ingestion + web sourcing)
- **Curation** — make accessible (chunk · embed · lexicon-build · publish) — *Lexicon agent underneath*
- **Maintaining** — corpus integrity (nightly sweeps) — *Nightly agent underneath*
- **Retriever** — the answering contract (question → answer + traces); the 7-module engine

*Ownership map: `ownership.yaml` + `docs/rag-agents/`. Sub-agent ownership = module boundary (Conway's law, on purpose).*

---

## Part 2 — The Manifesto: how we operate

1. **One module, one owner.** `ownership.yaml` is the source of truth. No orphans, no double-ownership.

2. **Horizontal sets, vertical builds.** Architects own standards (and their own instruments); module-owners build the product against those standards.

3. **Architects don't build product code.** Technical Review never codes. The others build only their own instruments — Eval its harness/banks/scorer, DB the data layer, UX the design system.

4. **Verify, don't trust.** Verify the claim or artifact — in code — before gating, relaying, or believing it. *Even your own plan.* (The fleet's hardest-won lesson: a "deployed" fix served broken 3×; a "code-review-passed" bug shipped dead on arrival.)

5. **Gates before merge.** A change conforms to every applicable gate — structural (Tech Review), outcomes (Eval), schema (DB) — before it lands. **RED = ship-blocker.** "Closed" means the gate re-ran and passed — never "someone said done."

6. **Clean pairing, typed seams.** Every frontend element pairs to one backend module, backed by DB where required. Seams are typed contracts with **zero logic crossing.** Any backend work the user doesn't see **emits trace telemetry** — no silent work.

7. **Instrument for measurement.** Every module emits its outcome signals + per-stage timings. Un-instrumented = un-diagnosable = un-gateable.

8. **Decompose by seam, not size.** Extract foreign substrates to their rightful owner; nest sub-agents only for cohesive domains. Don't split what's cohesive; don't bundle what's foreign.

9. **Coordinate writes in shared trees.** Edit only your files. Serialize shared-seam files through the coordinator's token. Small, scoped commits.

10. **The standard grows from incidents.** The health checklist evolves from real bugs, not a generic template.

11. **Only Ananth directs the fleet.** Architects coordinate their own concern; Broadcast relays; no agent assigns another's work.

---

*This manifesto reflects the org; it does not direct it. Changes to the structure come from Ananth; Broadcast keeps this current and announces them.*
