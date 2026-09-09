# Skills agent — charter

**Status:** proposed 2026-07-22 (Ananth). Created as part of the fleet ownership cleanup.
**Kind:** new standing agent (custodian model). **Source of truth for scope:** [`ownership.yaml`](../ownership.yaml).

## Mission (one line)
Be the custodian of the whole skills subsystem — the `mobius-skills` repo, its registry/dispatch law, the runtime, and the MCP bridge — and directly own every skill that has no domain owner, while domain agents own their delegated skills' logic.

## The two-level ownership model (important)
- **Skills agent = custodian.** Owns the repo, the registry/dispatch law, `mobius-skills-core` (runtime), `mobius-skills-mcp` (bridge), and any skill not delegated below.
- **Domain agents = delegates.** They own the *logic* of their specific skill; the Skills agent owns the *substrate they ride on* + skill registration/consistency.
- Glob resolution encodes it: a specific `mobius-skills/<skill>/**` rule → its domain agent; the `mobius-skills/**` fallback → Skills agent.

## Scope / owned modules
- `mobius-skills/**` (fallback: repo + registry + any undelegated skill)
- `mobius-skills-core/**` — runtime
- `mobius-skills-mcp/**` — MCP bridge
- Directly-held skills (no domain owner): `email`, `healthcare`, `vibe` (the fleet's **reference skill template** — keep), `appeals-agent` (archive candidate — hold until archived)

**Delegated skills (logic owned elsewhere, custodied here):** `phi-classifier`→PHI · `task-manager`→Task · `provider-roster-credentialing`→Credentialing · `org-intelligence`→Org · `instant-rag`,`chat-document-upload`→Instant-RAG · `doc-reader`,`google-search`,`web-scraper`→RAG · `cmhc-cost-report`,`fl-medicaid-npi`→Analytics.

## Responsibilities
- Own the Skill Registry / dispatch law (schematic `skillreg` node): every registered tool resolves, attributes correctly, and no ghosts.
- Keep the runtime + MCP bridge healthy; a new skill onboards through a documented contract.
- Maintain the undelegated skills; route defects on delegated skills to their domain agent (custodian ≠ fixer for those).
- Keep the delegation table in `ownership.yaml` current as skills are added/retired.

## Interfaces
All domain agents that own a skill (delegation counterparties) · Platform agent (contracts/config boundary) · Task agent (skill_invocations telemetry) · Technical Review Agent · Ananth.

## Non-goals
Not the owner of delegated skills' business logic. Not the contracts/config substrate (Platform agent).

## Definition of Done (ownership)
`mobius-skills-core`, `mobius-skills-mcp`, and the `mobius-skills/**` fallback show `owner: Skills agent, status: confirmed`; each delegated skill's domain agent has acknowledged its rule; a `project_skills_agent` memory is seeded.

## First tasks
1. Acknowledge scope; confirm the Skills rows in `ownership.yaml`; ping each domain agent to confirm its delegated skill.
2. Rule on `healthcare` (confirm purpose) and `email` (keep here or delegate).
3. Audit the Skill Registry for ghosts/attribution (pre-existing known gap).
