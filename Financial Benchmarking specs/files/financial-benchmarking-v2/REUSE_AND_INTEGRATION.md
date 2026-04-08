# Reuse & Integration Addendum
## Financial Closure Report — Shared Services, Chat Tools, API Endpoints

This document supersedes any section of TECH_SPEC.md that proposes building logic
already present in the credentialing report module. Where a conflict exists,
this document wins. The rule is simple: **if it exists, call it — don't rebuild it.**

---

## 1. Shared service map

The following table identifies every capability already built in the credentialing
report, the interface to call it, and exactly where in the financial closure report
it replaces a proposed build.

| Capability | Credentialing interface | Replaces in TECH_SPEC.md |
|---|---|---|
| Org concept + NPI grouping | `OrgService.resolve_org(org_name)` → `{org_id, npi_list, metadata}` | Phase 0.4 org_npi_list population; Phase 3.2 action owner resolution |
| Provider-to-org mapping | `OrgService.get_providers(org_id)` → `[{npi, name, role, taxonomy}]` | Phase 1.1 NPI list for KPI queries; Phase 2.3 provider drift input |
| NPI Registry lookup | `NPIService.lookup(npi)` → `{taxonomy, zip, state, name, ...}` | Phase 0.2 NPI enrichment table population |
| ICD-10 code lookup | `ICD10Service.describe(code)` → `{description, category, ...}` | Section A service line table descriptions; chatbot context enrichment |
| Task creation + assignment | `TaskService.create(task_payload)` → `{task_id, status}` | Phase 5 entirely — do not rebuild task schema or service |
| Task status update | `TaskService.update(task_id, status, notes)` | Phase 5.2 co-creation approval flow |
| Task query by org | `TaskService.list(org_id, filters)` → `[tasks]` | Phase 5.3 task-report feedback loop |

---

## 2. Dependency contracts

These are the exact interfaces the financial closure report will call.
**Do not modify the credentialing report's internals to accommodate this module.**
If an interface needs extending, add an optional parameter or a new method — never
alter existing signatures.

### 2.1 OrgService

```python
# Import path (same BQ project, shared service layer)
from credentialing.services.org_service import OrgService

# Resolve org by name — used at report onboarding
org = OrgService.resolve_org(org_name="Suncoast Community Mental Health Center")
# Returns:
# {
#   "org_id": "org_abc123",
#   "org_name": "Suncoast Community Mental Health Center",
#   "npi_list": ["1234567890", "0987654321", ...],
#   "primary_taxonomy": "261Q",
#   "state": "FL",
#   "resolved_at": "2025-03-01T00:00:00Z",
#   "confidence": "high" | "medium" | "low"   ← surface in report if low
# }

# Get all providers for an org — used to build KPI query NPI filter
providers = OrgService.get_providers(org_id="org_abc123")
# Returns:
# [
#   {
#     "npi": "1234567890",
#     "provider_name": "Dr. M. Rivera",
#     "taxonomy_code": "103T",
#     "taxonomy_description": "Psychologist",
#     "role": "servicing",
#     "zip": "33601",
#     "state": "FL",
#     "active": true
#   }, ...
# ]
```

**Financial closure report usage:**
- Call `resolve_org()` at report onboarding trigger
- Store `org_id` and `npi_list` in `report_index`
- Call `get_providers()` to build the NPI filter for all BQ queries in Phases 1 and 2
- Surface `confidence` in report cover — if "low", add caveat: "Org NPI mapping is
  partial. Some providers may not be included."

### 2.2 NPIService

```python
from credentialing.services.npi_service import NPIService

# Single NPI lookup — used for enrichment and on-demand chatbot queries
provider = NPIService.lookup(npi="1234567890")
# Returns:
# {
#   "npi": "1234567890",
#   "name": "Dr. M. Rivera",
#   "taxonomy_code": "103T",
#   "taxonomy_description": "Psychologist, Clinical",
#   "zip": "33601",
#   "state": "FL",
#   "city": "Tampa",
#   "phone": "...",
#   "credential": "PhD",
#   "enumeration_date": "2010-04-12",
#   "last_updated": "2024-01-15"
# }

# Batch lookup — used for NPI enrichment table population (Phase 0.2)
providers = NPIService.batch_lookup(npi_list=["123...", "456...", ...])
# Returns list of same structure above
# Note: credentialing module already caches these — no redundant API calls
```

**Financial closure report usage:**
- Replace Phase 0.2 NPI enrichment build entirely
- Call `batch_lookup()` for all unique NPIs in DOGE dataset
- Write results to `npi_enrichment` table (same schema as Phase 0.2 spec)
- On chatbot "tell me about this provider" questions, call `lookup()` live

### 2.3 ICD10Service

```python
from credentialing.services.icd10_service import ICD10Service

# Single code lookup
code = ICD10Service.describe(code="F32.1")
# Returns:
# {
#   "code": "F32.1",
#   "description": "Major depressive disorder, single episode, moderate",
#   "category": "Mental and behavioral disorders",
#   "billable": true,
#   "chapter": "F00-F99"
# }

# Batch lookup — for enriching service line table in Section A
codes = ICD10Service.batch_describe(codes=["F32.1", "F41.1", ...])
```

**Financial closure report usage:**
- Enrich Section A service line table with ICD-10 descriptions alongside HCPCS
- Feed chatbot context with code descriptions so it can answer "what does F32.1 mean
  in this context" without a live lookup
- Do NOT use for KPI computation — DOGE data joins on HCPCS, not ICD-10 primarily

### 2.4 TaskService

```python
from credentialing.services.task_service import TaskService

# Create a task — called when user approves a proposed action in Section C
task = TaskService.create({
    "org_id": "org_abc123",
    "source_module": "financial_closure_report",   # NEW field — add as optional
    "source_id": report_id,                         # links back to report
    "title": "No-show audit — group therapy (90853)",
    "description": "Full text of action...",
    "owner_role": "clinical_ops",
    "owner_user_id": None,                          # assigned in co-creation flow
    "priority": 1,
    "due_date": "2025-06-01",
    "category": "financial_benchmark",              # NEW category value — add to enum
    "metadata": {
        "quadrant": "urgent",
        "item_id": "90853",
        "item_label": "Group psychotherapy",
        "revenue_at_stake": 180000,
        "kpi": "claims_per_bene"
    }
})
# Returns: { "task_id": "task_xyz", "status": "PROPOSED" }

# Update task status — called from co-creation approval flow
TaskService.update(
    task_id="task_xyz",
    status="ACTIVE",
    owner_user_id="user_123",
    notes="Approved by CFO in Q2 review"
)

# Query tasks for an org — used in Phase 5.3 monthly refresh feedback loop
tasks = TaskService.list(
    org_id="org_abc123",
    filters={
        "source_module": "financial_closure_report",
        "source_id": report_id,
        "status": ["ACTIVE", "IN_PROGRESS", "DONE"]
    }
)
```

**Coordination required with credentialing team:**
- Add `source_module` as optional string field to task payload (default: "credentialing")
- Add `"financial_benchmark"` to the category enum
- Add `metadata` as optional JSON blob field (if not already present)
- These are additive changes — no existing credentialing task functionality is affected

---

## 3. What the financial closure report still owns

These are NOT in the credentialing report and must be built new:

| Component | Reason not reused |
|---|---|
| `vw_claims_base` BQ view | DOGE-specific — credentialing has no claims data |
| KPI computation queries (Phases 1.1, 2.1) | Net-new — benchmarking logic |
| Peer group construction + taxonomy weighting | Net-new — benchmarking logic |
| Divergence detection algorithm (Phase 2.2) | Net-new — trend intelligence |
| Provider drift detection (Phase 2.3) | Net-new — trend intelligence |
| Matrix quadrant scoring (Phase 3.1) | Net-new — strategic synthesis |
| Action template generation (Phase 3.2) | Net-new — calls TaskService.create() |
| Report renderer HTML + PDF (Phase 4) | Net-new — visual output layer |
| Alert engine (Phase 6) | Net-new — may share alert schema with credentialing later |
| Chatbot context builder (Phase 7.1) | Net-new — financial-specific context |
| `zip_msa_crosswalk` table | Credentialing uses ZIP but not MSA — build new |

---

## 4. Chat tool registry

These are the tools that must be registered and available to the chatbot so that
any question — from methodology to individual provider analysis — can be answered
without running the full report. Each tool is callable independently.

### 4.1 Tool definitions

```python
FINANCIAL_CHAT_TOOLS = [

    {
        "name": "get_org_kpis",
        "description": "Returns panel size, claims per beneficiary, and payment per claim for an org over a specified period. Includes FL and national percentile ranks vs taxonomy-matched peers.",
        "parameters": {
            "org_id": "string — org identifier",
            "period_start": "string — YYYY-MM",
            "period_end": "string — YYYY-MM",
            "payor_scope": "list[string] — default ['MEDICARE_FFS']",
            "benchmark_level": "string — 'zip'|'msa'|'state'|'national' default 'state'"
        },
        "returns": "KPI values + percentile ranks + peer distribution stats",
        "source": "financial_closure_report.kpi_queries.compute_org_kpis()"
    },

    {
        "name": "get_provider_kpis",
        "description": "Returns KPIs for a single servicing NPI. Includes trend over trailing N months and comparison to org average and peer group.",
        "parameters": {
            "npi": "string",
            "period_months": "int — trailing months, default 12",
            "compare_to_org": "bool — default true"
        },
        "returns": "Provider KPIs + trend direction + org comparison + drift flag",
        "source": "financial_closure_report.kpi_queries.compute_provider_kpis()"
    },

    {
        "name": "get_hcpcs_trend",
        "description": "Returns payment per claim trend for a specific HCPCS code for an org vs FL peers and national peers. Flags if org is outside the peer quartile band.",
        "parameters": {
            "org_id": "string",
            "hcpcs_code": "string",
            "months": "int — default 24"
        },
        "returns": "Monthly payment per claim series (org + peer median + p25/p75) + divergence flag",
        "source": "financial_closure_report.trend_queries.get_hcpcs_trend()"
    },

    {
        "name": "get_market_archetype",
        "description": "Returns market archetype characterization for a ZIP or MSA. Includes provider density, KPI distributions, and archetype label (underserved/saturated/underutilizing/etc.).",
        "parameters": {
            "geo_type": "string — 'zip'|'msa'",
            "geo_id": "string — ZIP code or MSA CBSA code",
            "taxonomy_filter": "list[string] — optional, default all"
        },
        "returns": "Archetype label + scoring dimensions + KPI distributions + public data overlay",
        "source": "financial_closure_report.market_archetype.score_market()"
    },

    {
        "name": "get_divergence_signals",
        "description": "Returns current divergence signals for an org — which KPIs are diverging from industry, at what severity, and for how long. Does not require running the full report.",
        "parameters": {
            "org_id": "string",
            "kpis": "list[string] — default all three",
            "window_months": "int — default 6"
        },
        "returns": "Per-KPI divergence severity, direction, rate-of-change, months outside band",
        "source": "financial_closure_report.divergence_detection.detect_divergence()"
    },

    {
        "name": "get_provider_drift",
        "description": "Returns drift signals for all providers in an org — who is declining on which KPI, whether decline is accelerating, and severity vs own 12-month baseline.",
        "parameters": {
            "org_id": "string",
            "severity_filter": "string — 'all'|'critical'|'moderate' default 'all'",
            "kpi_filter": "string — optional"
        },
        "returns": "Per-provider per-KPI drift severity + direction + acceleration flag",
        "source": "financial_closure_report.divergence_detection.detect_provider_drift()"
    },

    {
        "name": "get_peer_comparison",
        "description": "Compares a specific org, provider, or service line to taxonomy-matched peers at a specified geographic level. Returns percentile rank, z-score, and peer distribution.",
        "parameters": {
            "entity_type": "string — 'org'|'provider'|'hcpcs'",
            "entity_id": "string — org_id, NPI, or HCPCS code",
            "kpi": "string — 'panel_size'|'claims_per_bene'|'payment_per_claim'",
            "benchmark_level": "string — 'zip'|'msa'|'state'|'national'",
            "period": "string — YYYY-MM of most recent month"
        },
        "returns": "Percentile rank + z-score + peer mean/p25/p75/n + taxonomy adjustment applied",
        "source": "financial_closure_report.peer_scoring.compute_percentile()"
    },

    {
        "name": "lookup_npi",
        "description": "Returns provider details for a given NPI — name, taxonomy, location, credentials. Wraps credentialing NPIService.",
        "parameters": {
            "npi": "string"
        },
        "returns": "Provider profile from NPI Registry",
        "source": "credentialing.services.npi_service.NPIService.lookup()"   # REUSE
    },

    {
        "name": "lookup_icd10",
        "description": "Returns description and category for an ICD-10 code. Useful for explaining what condition a service line is treating.",
        "parameters": {
            "code": "string — ICD-10 code e.g. F32.1"
        },
        "returns": "Code description, category, billable flag",
        "source": "credentialing.services.icd10_service.ICD10Service.describe()"  # REUSE
    },

    {
        "name": "get_open_tasks",
        "description": "Returns open tasks for an org filtered by status, quadrant, owner role, or category. Wraps credentialing TaskService.",
        "parameters": {
            "org_id": "string",
            "status_filter": "list[string] — default ['PROPOSED','ACTIVE','IN_PROGRESS']",
            "quadrant_filter": "string — optional",
            "owner_role_filter": "string — optional"
        },
        "returns": "Task list with title, owner, due date, status, linked report section",
        "source": "credentialing.services.task_service.TaskService.list()"    # REUSE
    },

    {
        "name": "create_task_from_chat",
        "description": "Creates a new task directly from a chatbot conversation — without requiring the user to go through the full report co-creation flow. Proposed status until approved.",
        "parameters": {
            "org_id": "string",
            "title": "string",
            "description": "string",
            "owner_role": "string",
            "priority": "int — 1-3",
            "horizon_days": "int"
        },
        "returns": "task_id + status PROPOSED",
        "source": "credentialing.services.task_service.TaskService.create()"   # REUSE
    },

    {
        "name": "explain_methodology",
        "description": "Returns a plain-language explanation of how a specific metric, benchmark, or algorithm works. Covers: KPI definitions, taxonomy adjustment, peer group construction, divergence detection, quadrant scoring.",
        "parameters": {
            "topic": "string — e.g. 'taxonomy adjustment' | 'panel size' | 'divergence detection' | 'peer group'"
        },
        "returns": "Plain-language methodology explanation with data caveats",
        "source": "financial_closure_report.methodology.explain()"   # static lookup, no BQ
    },

    {
        "name": "get_report_summary",
        "description": "Returns a compressed summary of the most recent financial closure report for an org — KPI scorecard, top alerts, and top 3 actions. Fast path — no recomputation.",
        "parameters": {
            "org_id": "string",
            "sections": "list[string] — default ['kpis','alerts','actions']"
        },
        "returns": "Compressed report summary from report_index cache",
        "source": "financial_closure_report.report_index.get_summary()"
    }
]
```

### 4.2 Tool availability by user role

```python
TOOL_ACCESS_BY_ROLE = {
    "executive": [
        "get_org_kpis",
        "get_divergence_signals",
        "get_report_summary",
        "get_open_tasks",
        "explain_methodology"
    ],
    "clinical_director": [
        "get_org_kpis",
        "get_provider_kpis",
        "get_provider_drift",
        "get_hcpcs_trend",
        "get_open_tasks",
        "create_task_from_chat",
        "lookup_npi",
        "lookup_icd10",
        "explain_methodology",
        "get_report_summary"
    ],
    "revenue_cycle": [
        "get_org_kpis",
        "get_hcpcs_trend",
        "get_peer_comparison",
        "lookup_icd10",
        "get_open_tasks",
        "create_task_from_chat",
        "explain_methodology"
    ],
    "strategy": [
        "get_org_kpis",
        "get_market_archetype",
        "get_peer_comparison",
        "get_divergence_signals",
        "get_report_summary",
        "explain_methodology"
    ],
    "analyst": [
        # all tools
    ]
}
```

### 4.3 Tool chaining patterns

Common multi-tool sequences the chatbot should execute automatically (without
asking the user to re-prompt between steps):

```python
TOOL_CHAINS = {
    # "What's wrong with Dr. Johnson?"
    "provider_deep_dive": [
        "lookup_npi",           # get provider profile
        "get_provider_kpis",    # get their metrics
        "get_provider_drift",   # get drift signals
        "get_open_tasks"        # any existing tasks about this provider
    ],

    # "Why is our group therapy revenue declining?"
    "service_line_investigation": [
        "get_hcpcs_trend",      # payment trend for the code
        "get_peer_comparison",  # vs peers
        "lookup_icd10",         # describe associated diagnoses
        "get_open_tasks"        # any existing tasks on this service line
    ],

    # "How does Tampa compare nationally?"
    "market_context": [
        "get_market_archetype", # Tampa MSA archetype
        "get_peer_comparison",  # org vs national on each KPI
        "get_divergence_signals" # where is org diverging
    ],

    # "What should we focus on in the next 90 days?"
    "strategic_summary": [
        "get_report_summary",       # compressed report
        "get_divergence_signals",   # current signals
        "get_open_tasks"            # what's already in flight
    ]
}
```

---

## 5. REST API endpoints

All endpoints below are net-new for the financial closure report module.
They call shared services internally where applicable (see Section 2).

```
BASE: /api/v1/financial-report

# Report lifecycle
POST   /reports/generate          — trigger report for org_id (onboarding hook)
GET    /reports/{report_id}       — fetch full report JSON
GET    /reports/{report_id}/html  — rendered HTML report
GET    /reports/{report_id}/pdf   — PDF export
GET    /orgs/{org_id}/report      — latest report for org

# Section-level endpoints (for partial rendering / chatbot grounding)
GET    /reports/{report_id}/section-a     — historic performance facts
GET    /reports/{report_id}/section-b     — trend facts
GET    /reports/{report_id}/section-c     — strategic matrix (co-created)

# On-demand analysis (no full report required — powers chatbot tools)
GET    /analysis/kpis             — ?org_id=&period_start=&period_end=&benchmark_level=
GET    /analysis/provider         — ?npi=&period_months=&org_id=
GET    /analysis/hcpcs-trend      — ?org_id=&hcpcs_code=&months=
GET    /analysis/peer-comparison  — ?entity_type=&entity_id=&kpi=&benchmark_level=
GET    /analysis/divergence       — ?org_id=&kpis=&window_months=
GET    /analysis/provider-drift   — ?org_id=&severity=
GET    /analysis/market           — ?geo_type=&geo_id=&taxonomy_filter=

# Co-creation (Section C actions → tasks)
POST   /reports/{report_id}/actions/{action_id}/approve   — approve → creates task
POST   /reports/{report_id}/actions/{action_id}/edit      — edit before approve
POST   /reports/{report_id}/actions/{action_id}/dismiss   — dismiss with reason

# Alert engine
GET    /alerts                    — ?org_id=&status=&severity=
POST   /alerts/{alert_id}/acknowledge
POST   /alerts/{alert_id}/create-task    — alert → proposed task

# Chatbot tools (thin wrappers over /analysis endpoints, role-gated)
POST   /chat/tools/invoke         — { tool_name, parameters, user_id }
GET    /chat/context/{org_id}     — compressed report context for chatbot grounding
```

---

## 6. Updated build sequence (with reuse)

Phase 0 changes:
- 0.2 NPI enrichment → call `NPIService.batch_lookup()` instead of building from scratch
- 0.4 Report index → add `org_id` FK to credentialing org table; populate via `OrgService.resolve_org()`

Phase 1 changes:
- 1.1 KPI queries → NPI filter populated by `OrgService.get_providers()` not raw BQ join

Phase 3 changes:
- 3.2 Action generation → calls `TaskService.create()` not custom task insert
- Remove Phase 5 task schema build — use credentialing task schema + two additive fields

Phase 5 changes (now Phase 5-lite):
- Task schema: add `source_module` + `metadata` fields to credentialing tasks table (migration, not rebuild)
- Task service: no rewrite — just call existing `TaskService` with new fields
- Feedback loop: `TaskService.list(source_module='financial_closure_report')` gives correct task subset

Net new build phases unchanged: 2, 4, 6, 7, 8, 9.

---

## 7. Coordination checklist with credentialing team

Before financial closure report Phase 0 begins, confirm the following with the
credentialing report team:

- [ ] `OrgService.resolve_org()` returns `confidence` field — add if missing
- [ ] `TaskService.create()` accepts optional `source_module` string field
- [ ] `TaskService.create()` accepts optional `metadata` JSON blob field
- [ ] `TaskService.list()` supports filtering by `source_module`
- [ ] `"financial_benchmark"` added to task category enum
- [ ] NPI enrichment cache is shared — financial module will not make redundant
      NPI Registry API calls for NPIs already cached by credentialing
- [ ] ICD-10 lookup cache is shared — same principle
- [ ] Confirm BQ dataset access: financial module needs READ on credentialing
      org and provider tables; no WRITE access required
- [ ] API versioning: confirm credentialing endpoints are on `/api/v1/` and
      will not change signatures during financial module build window
