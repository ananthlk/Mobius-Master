# Mobius Chat — capabilities

This document reflects **V1 intent**, **published corpus snapshots**, and the **code registry** in `mobius-chat/app/stages/agents/capabilities.py`. When behavior and this file disagree, prefer the code and operational config.

---

## 1. RAG corpus (documents)

### V1 target scope (locked plan)

Per [docs/V1_DAY_BY_DAY_PLAN.md](../V1_DAY_BY_DAY_PLAN.md), the corpus work aims for:

- **Six document types** (metadata/schema): `provider_manual`, `member_manual`, `clinical_policy`, `payment_policy`, `pa_lookup`, `web_scrape`
- **Up to ten health plans** with representative docs per type
- **AHCA** (Florida) regulatory / Medicaid materials, tagged for jurisdiction (e.g. `state=FL`, `regulatory_agency=AHCA`)
- Quality gates: high recall on a curated eval set and strong answer accuracy when retrieval succeeds (see V1 Week 3 in that plan)

### Live inventory (point in time)

Operational counts change whenever sync and ingestion run. A snapshot is recorded in:

- [reports/chat_rag_inventory.md](../../reports/chat_rag_inventory.md)

Example snapshot (2026-02-20): **1,914** chunk/fact rows, **20** distinct documents, with named examples such as *Sunshine Provider Manual* and *Sunshine Member Handbook*. Re-check that file or your database for current numbers.

### How chat retrieves

- **Production path**: Vertex AI Vector Search (embeddings) plus Postgres **`published_rag_metadata`** for metadata and filtering. See [mobius-chat/docs/PUBLISHED_RAG_SETUP.md](../../mobius-chat/docs/PUBLISHED_RAG_SETUP.md).
- **RAG scopes** (planner JSON): `payer_manuals`, `state_contracts`, `internal_docs` — see `available_capabilities_json()` in `capabilities.py`.

### Optional metadata filters (deployment)

If operators set default filters, **only** matching published documents are returned:

| Environment variable | Role |
|---------------------|------|
| `CHAT_RAG_FILTER_PAYER` | Restrict to payer |
| `CHAT_RAG_FILTER_STATE` | Restrict to state |
| `CHAT_RAG_FILTER_PROGRAM` | Restrict to program |
| `CHAT_RAG_FILTER_AUTHORITY_LEVEL` | Restrict to authority level |

Details: [mobius-chat/docs/ENV.md](../../mobius-chat/docs/ENV.md). Leave all unset to search across whatever the index contains.

---

## 2. Path-level capabilities (high level)

From `PATH_CAPABILITIES` in `capabilities.py`:

| Path | Meaning |
|------|---------|
| **rag** | Policy and handbook-style Q&A: appeals, PA, eligibility, claims, benefits, member handbook topics; may use web search when corpus confidence is low |
| **patient** | **Stub** — no access to user-specific records; user gets an appropriate refusal / warning |
| **clinical** | **Stub** — future |
| **tool** | Google search, web scrape, NPI/org lookups, credentialing and roster flows, uploads |
| **reasoning** | Explanations and definitions without requiring a document hit |

---

## 3. Tools and skills (per-tool registry)

The table below mirrors `TOOL_CAPABILITIES` in code. **Requires** means user or thread context must satisfy the condition before the tool can succeed.

| Tool | Can answer | Cannot answer / notes | Requires |
|------|------------|----------------------|----------|
| `ask_credentialing_npi` | PML readiness, NPI profile from credentialing report | NPPES-only questions; anything without a report | Report run / org context (`report_run_id` or `last_report_org`) |
| `healthcare_query` | ICD-10-CM meaning, NCD/LCD-style coverage context, NPI-by-number registry facts, diagnosis/procedure codes where lookup applies | PML without report; NPI for org by name | — |
| `healthcare_npi_lookup` | NPPES lookup by **10-digit NPI** | ICD-10, CPT, HCPCS, coverage questions (use `healthcare_query`); PML / credentialing report data | — |
| `lookup_npi` | NPI numbers for an **organization by name** | Lookup by NPI number; PML | — |
| `run_credentialing_report` | Full credentialing report; co-pilot step-by-step | — | — |
| `validate_credentialing_step` | Advance co-pilot after confirm/edit | — | Active copilot run / `credentialing_run_id` |
| `run_roster_reconciliation_report` | Roster vs outside-in comparison, mismatch buckets | — | Roster uploaded on thread (CSV/Excel); org context |
| `document_upload_skill` | How to attach files; API contract; multiple uploads on thread | Parsing file bytes from plain chat text | — |
| `list_thread_document_uploads` | Files already on thread | — | Active `thread_id` |
| `search_corpus` | Policy, PA, eligibility, claims, enrollment, credentialing process | — | — |
| `google_search` | Web search when corpus misses or user asks | — | Configured skills URL / MCP |
| `web_scrape` | Read a specific URL | — | Configured MCP / scraper |

**Routing hints** (from `available_capabilities_json()`): NPI + PML → `ask_credentialing_npi` (needs report). Codes and coverage → `healthcare_query`. Ten-digit NPI registry → `healthcare_query` or `healthcare_npi_lookup`. Org name → NPI lookup tool.

---

## 4. Skills services (repository layout)

Implementation and deployment of HTTP/MCP skills live under [mobius-skills/](../../mobius-skills/). Examples referenced from chat env:

- Google search — `mobius-skills/google-search` (see `CHAT_SKILLS_GOOGLE_SEARCH_URL` in [mobius-chat/docs/ENV.md](../../mobius-chat/docs/ENV.md))
- Web scraper — `mobius-skills/web-scraper`
- Provider roster / credentialing — `mobius-skills/provider-roster-credentialing`

---

## 5. Global rules: what we refuse or qualify

- **Patient-specific data**: The architecture treats patient subquestions separately; there is **no patient RAG** yet. Do not expect answers about “my” care, medications, or records — see [mobius-chat/docs/ARCHITECTURE.md](../../mobius-chat/docs/ARCHITECTURE.md).
- **No relevant context**: Non-patient path may return that nothing relevant was found in the corpus; degradation behavior may offer web search when configured.
- **Accuracy**: Answers should be grounded in retrieved material or tool output; hallucination is a failure mode the pipeline tries to reduce.

---

## 6. Maintenance

- **Authoritative tool list**: `TOOL_CAPABILITIES` and related helpers in [mobius-chat/app/stages/agents/capabilities.py](../../mobius-chat/app/stages/agents/capabilities.py).
- **Canned capability Q&A** (e.g. “Can you search Google?”): `CAPABILITY_ANSWERS` in the same file.
- Update this markdown when V1 corpus gates are met or when major tools are added — or add a dated note at the top if the doc temporarily lags code.
