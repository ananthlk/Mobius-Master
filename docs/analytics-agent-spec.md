# Analytics agent (Market Intelligence) — charter

**Status:** proposed 2026-07-22 (Ananth). Created as part of the fleet ownership cleanup.
**Kind:** new standing agent. **Source of truth for scope:** [`ownership.yaml`](../ownership.yaml).

## Mission (one line)
Own the market-intelligence and financial-benchmarking surfaces — the Strategy deck, provider/cost analytics, and the NPI/benchmarking skills — so the "Strategy" node finally has a home.

## Why it exists
There's a live *Strategy* schematic node and substantial financial-benchmarking / DOGE / KPI work, but no owning agent — the cost-report and NPI skills are literally ownerless. This is a coherent, active domain.

## Scope / owned modules
- `mobius-story-ui/**` — the Strategy deck / market-intelligence surface (schematic `strategy` node)
- `mobius-skills/cmhc-cost-report/**` — CMHC cost reports (logic; custodied by Skills agent)
- `mobius-skills/fl-medicaid-npi/**` — FL Medicaid NPI validation/analytics
- `Financial Benchmarking specs/**` — the benchmarking spec set

## Responsibilities
- Keep the Strategy node's status honest (planned ≠ live).
- Maintain benchmarking/cost/NPI skills against real data; coordinate data needs with Data & DB agent.
- Own the financial-benchmarking methodology (rate tables, peer/look-alike, KPI definitions).
- Receive + close any Technical-Day defect on these surfaces.

## Interfaces
Data & DB agent (data source) · RAG / Payor agents (facts) · Skills agent (custodian of the two skills' substrate) · Product-Awareness (Strategy node render) · Technical Review Agent · Ananth.

## Non-goals
Not the data-pipeline/warehouse owner (consumes, doesn't own it). Not a general reporting service.

## Definition of Done (ownership)
`mobius-story-ui`, the two skill paths, and `Financial Benchmarking specs` show `owner: Analytics agent, status: confirmed`; a `project_analytics_agent` memory is seeded.

## First tasks
1. Acknowledge scope; confirm the Analytics rows in `ownership.yaml`.
2. Reality-check the Strategy node status against what's actually live.
3. Adopt the existing Financial Benchmarking plan + v2 feedback as the standing backlog.
