# Fleet Ownership Map

**Source of truth:** [`ownership.yaml`](../ownership.yaml) (repo root). This doc is the readable view; the YAML is what the Technical Review Agent consumes to resolve `module → owner` when assigning defects.

**Why it exists:** git can't tell us ownership — every commit fleet-wide is authored as "Ananth Lalithakumar" because the agents all commit as Ananth. Ownership is a *logical* assignment; this file declares it so it's checkable and assignable (checklist item #9).

**Status:** DRAFT, produced by the Technical Review Agent 2026-07-22. **Not yet ratified** — entries marked `proposed` need Ananth's confirmation. Only Ananth assigns fleet ownership.

---

## Clean single owner ✅ (confirmed)

| Repo | Owner |
|---|---|
| mobius-chat | Chat agent |
| mobius-rag | RAG agent |
| mobius-payor | Payor agent |
| mobius-vault | Vault agent |
| mobius-interact | Interact agent |
| mobius-feedback | Feedback agent |
| mobius-db-agent | DB agent |
| mobius-qa (+ mobius-qa-modules) | Eval agent |
| product-awareness | Product-Awareness agent |
| mobius-design | UX agent |
| Mobius-user | User Manager agent *(was contested; settled)* |

## mobius-skills — one repo, many agents (subdir-level)

| Subdir | Owner | Status |
|---|---|---|
| phi-classifier | PHI Classifier agent | confirmed |
| task-manager | Task agent | confirmed |
| provider-roster-credentialing | Credentialing agent | confirmed |
| org-intelligence | Org agent | confirmed |
| instant-rag, chat-document-upload | Instant-RAG agent | confirmed |
| doc-reader | Instant-RAG agent | **proposed** |
| email | Email agent | **proposed** |
| google-search, web-scraper | RAG agent (web curator) | **proposed** |
| appeals-agent | Appeals agent | **archive candidate** |
| cmhc-cost-report, fl-medicaid-npi, healthcare, vibe | Ananth (platform) | **proposed — no agent found** |

## Ambiguous single repos — need ratification

| Repo | Proposed owner | Question |
|---|---|---|
| mobius-answer-cache | RAG agent | RAG vs Chat? |
| mobius-auth | User Manager agent | Confirm — no dedicated Auth agent |

## Infrastructure / plumbing — Ananth (platform) catch-all

`mobius-config`, `mobius-contracts`, `mobius-migrations`, `mobius-dbt`, `mobius-retriever`, `mobius-rag-api`, `mobius-os`, `mobius-document-viewer`, `mobius-story-ui`, `mobius-skills-core`, `mobius-skills-mcp`, plus all superrepo-root loose files (`decomp_v2_*.py`, `landing_server.py`, `module-hub` build, `meval`/`mstart`/`mstop`, `requirements.txt`, …).

*Reassignment candidates flagged in the YAML:* `mobius-migrations → DB agent`, `mobius-retriever`/`mobius-rag-api → RAG agent`.

## Reviewer-owned (Technical Review Agent)

`ownership.yaml`, `reports/techday/**`, `scripts/techday/**` — the map and the read-only AUTO harness.

---

## To ratify

1. Confirm/reassign the **`proposed`** rows (skills subdirs, answer-cache, auth).
2. Rule on **Appeals** — archive it, or keep and confirm the owning session.
3. Name the 4 **ownerless skills** (`cmhc-cost-report`, `fl-medicaid-npi`, `healthcare`, `vibe`) or leave as platform.
4. Flip `ratified: true` in the YAML (or tell me to).
