# Financial Closure Report — Cursor-Ready Technical Specification

## Document purpose
This spec is the authoritative build guide for the Financial Closure Report platform module. It is written to be handed directly to Cursor for implementation. Each phase has a hard STOP/TEST gate before the next phase begins. No phase starts until the prior one passes its test criteria.

---

## Data reality & constraints (non-negotiable guardrails)

Before any build decision, every engineer must internalize these constraints:

| Constraint | Current state | Future state |
|---|---|---|
| Payor | Medicare FFS only (DOGE) | Multi-payor as claims data onboarded |
| Service type | Outpatient only | Inpatient, SNF, DME as data expands |
| Period | Through Dec 2024 | Rolling monthly as DOGE updates |
| Completeness | Not audited, not definitive | Supplemental claims data will replace |
| Geography | National (FL primary focus) | No change — already national |
| Org linkage | Custom logic per named org | Roster API as platform matures |

**The "as-if" principle:** Every UI surface, every query, every output must treat the current data as a valid but bounded snapshot. The architecture must be payor-agnostic, service-line-agnostic, and period-agnostic from day one so that adding a new payor or service line requires a data pipeline change, not a code change.

---

## System architecture overview

```
┌─────────────────────────────────────────────────────┐
│                    DATA LAYER                        │
│  BigQuery (DOGE) · NPI Registry MCP · Public APIs   │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              REPORT ENGINE (core)                    │
│  Section A: Historic performance  [facts]            │
│  Section B: Evolving trends       [facts]            │
│  Section C: Strategic matrix      [co-created]       │
└──────┬──────────────┬──────────────┬────────────────┘
       │              │              │
┌──────▼──┐    ┌──────▼──┐   ┌──────▼──────────────┐
│  Tasks  │    │ Chatbot  │   │   Alert engine       │
│  module │    │  module  │   │   (divergence watch) │
└─────────┘    └──────────┘   └─────────────────────┘
                       │
              ┌────────▼────────┐
              │   User routing   │
              │  Role · value    │
              └─────────────────┘
```

---

## Phase 0 — Foundation (STOP before Phase 1)

### 0.1 BigQuery schema contract

Define the canonical BQ view that all report queries run against. This view is the payor-agnostic abstraction layer. Raw DOGE tables sit below it; when a new payor arrives, you add it to the view, not to the report queries.

```sql
-- canonical view: vw_claims_base
CREATE OR REPLACE VIEW `{project}.{dataset}.vw_claims_base` AS
SELECT
  service_month,                          -- DATE (first of month)
  servicing_npi,
  billing_npi,
  hcpcs_code,
  icd10_code,
  provider_zip,                           -- joined from NPI registry enrichment
  provider_state,
  msa_code,                               -- joined from ZIP-MSA crosswalk
  msa_name,
  taxonomy_code,                          -- joined from NPI registry enrichment
  taxonomy_description,
  total_claims,
  total_beneficiaries,
  total_paid,
  payor_type,                             -- 'MEDICARE_FFS' for DOGE; extensible
  service_category,                       -- 'OUTPATIENT' for DOGE; extensible
  data_source                             -- 'DOGE_2024' for audit trail
FROM `{project}.{dataset}.doge_outpatient_raw` d
LEFT JOIN `{project}.{dataset}.npi_enrichment` n USING (servicing_npi)
LEFT JOIN `{project}.{dataset}.zip_msa_crosswalk` z USING (provider_zip)
```

**STOP 0.1 test:** Run `SELECT COUNT(*), COUNT(DISTINCT servicing_npi), COUNT(DISTINCT service_month) FROM vw_claims_base` and validate row counts match raw DOGE source. Zero unexplained row loss.

### 0.2 NPI enrichment table

Build the NPI enrichment table by pulling from NPI Registry MCP for all unique servicing NPIs in the DOGE dataset. This runs once on init, then nightly for new NPIs.

```sql
-- npi_enrichment schema
CREATE TABLE `{project}.{dataset}.npi_enrichment` (
  servicing_npi       STRING,
  provider_name       STRING,
  taxonomy_code       STRING,
  taxonomy_description STRING,
  provider_zip        STRING,
  provider_state      STRING,
  provider_city       STRING,
  last_updated        TIMESTAMP
)
```

**STOP 0.2 test:** Join coverage — `SELECT COUNT(*) FROM vw_claims_base WHERE taxonomy_code IS NULL`. Must be < 2% of total rows.

### 0.3 ZIP-MSA crosswalk table

Load HUD ZIP-to-CBSA crosswalk. Refresh annually.

```sql
CREATE TABLE `{project}.{dataset}.zip_msa_crosswalk` (
  provider_zip  STRING,
  msa_code      STRING,
  msa_name      STRING,
  county_fips   STRING,
  state_code    STRING
)
```

**STOP 0.3 test:** All FL ZIPs present. `SELECT COUNT(*) FROM zip_msa_crosswalk WHERE state_code = 'FL'` > 800.

### 0.4 Report metadata table

One row per org per report period. This is the report's system of record.

```sql
CREATE TABLE `{project}.{dataset}.report_index` (
  report_id         STRING,               -- UUID
  org_id            STRING,
  org_name          STRING,
  org_npi_list      ARRAY<STRING>,        -- servicing NPIs in this org
  report_period     STRING,               -- 'YYYY-MM' of most recent month
  payor_scope       ARRAY<STRING>,        -- ['MEDICARE_FFS']
  service_scope     ARRAY<STRING>,        -- ['OUTPATIENT']
  status            STRING,               -- GENERATING | COMPLETE | FAILED
  generated_at      TIMESTAMP,
  last_refreshed    TIMESTAMP,
  section_a_json    JSON,                 -- historic performance facts
  section_b_json    JSON,                 -- trend facts
  section_c_json    JSON,                 -- co-created strategic matrix
  tasks_seeded      BOOL,
  alerts_configured BOOL,
  chatbot_context   STRING               -- compressed context for chatbot grounding
)
```

**STOP 0.4 test:** Insert a test org row, retrieve it, validate all fields round-trip correctly.

---

## Phase 1 — Report engine: Section A (historic performance)

**Build stop: Section A renders correctly with real data for one test org before Section B begins.**

### 1.1 KPI computation queries

All three KPIs computed at all five geographic levels in a single parameterized query set.

```sql
-- KPI base: NPI + taxonomy level
-- Parameters: org_npi_list, period_start, period_end, payor_scope, service_scope
WITH base AS (
  SELECT *
  FROM `{project}.{dataset}.vw_claims_base`
  WHERE servicing_npi IN UNNEST(@org_npi_list)
    AND service_month BETWEEN @period_start AND @period_end
    AND payor_type IN UNNEST(@payor_scope)
    AND service_category IN UNNEST(@service_scope)
),
org_kpis AS (
  SELECT
    service_month,
    servicing_npi,
    taxonomy_code,
    SUM(total_beneficiaries)                                          AS panel_size,
    SAFE_DIVIDE(SUM(total_claims), SUM(total_beneficiaries))          AS claims_per_bene,
    SAFE_DIVIDE(SUM(total_paid), SUM(total_claims))                   AS payment_per_claim,
    SUM(total_claims)                                                 AS total_claims,
    SUM(total_paid)                                                   AS total_paid
  FROM base
  GROUP BY 1,2,3
)
SELECT * FROM org_kpis
```

Run equivalent query for peer group at ZIP / MSA / state / national level (excluding org NPIs). Store results in `report_index.section_a_json`.

### 1.2 Taxonomy-adjusted peer scoring

```python
def compute_taxonomy_adjusted_percentile(org_kpis_df, peer_kpis_df, kpi_col):
    """
    Weight peer distribution by org's taxonomy mix before computing percentile.
    Returns percentile rank (0-100), peer mean, peer p25, p75, n.
    """
    # Get org taxonomy weights
    org_weights = (
        org_kpis_df.groupby('taxonomy_code')['total_claims']
        .sum()
        .pipe(lambda s: s / s.sum())
        .to_dict()
    )
    # Weight peer metrics
    peer_weighted = []
    for tax, weight in org_weights.items():
        peer_subset = peer_kpis_df[peer_kpis_df['taxonomy_code'] == tax][kpi_col]
        peer_weighted.extend(peer_subset.tolist())  # extend proportionally
    peer_arr = np.array(peer_weighted)
    org_val = org_kpis_df[kpi_col].mean()
    pctile = float(scipy.stats.percentileofscore(peer_arr, org_val))
    return {
        'value': round(org_val, 2),
        'percentile': round(pctile, 1),
        'peer_mean': round(peer_arr.mean(), 2),
        'peer_p25': round(np.percentile(peer_arr, 25), 2),
        'peer_p75': round(np.percentile(peer_arr, 75), 2),
        'peer_n': len(peer_arr)
    }
```

### 1.3 Section A JSON schema

```json
{
  "period": "2024-01 to 2024-12",
  "payor_scope": ["MEDICARE_FFS"],
  "service_scope": ["OUTPATIENT"],
  "data_caveats": ["Medicare FFS only", "Outpatient only", "DOGE data not audited"],
  "kpis": {
    "panel_size": {
      "value": 147,
      "fl_percentile": 42,
      "national_percentile": 38,
      "peer_mean": 162,
      "peer_p25": 98,
      "peer_p75": 201,
      "peer_n": 312,
      "benchmark_method": "taxonomy_adjusted"
    },
    "claims_per_bene": { ... },
    "payment_per_claim": { ... }
  },
  "service_lines": [ ... ],   // per HCPCS
  "providers": [ ... ],       // per servicing NPI
  "geography": [ ... ]        // per ZIP in org footprint
}
```

**STOP Phase 1 test criteria:**
- [ ] KPIs compute correctly for test org against known manual calculation
- [ ] Taxonomy adjustment produces different result than unadjusted (confirms it's working)
- [ ] All five geographic levels return results
- [ ] Section A JSON validates against schema
- [ ] Peer N > 30 for all taxonomy groups (flag if not — thin peer group warning)

---

## Phase 2 — Report engine: Section B (evolving trends)

**Build stop: Trend data renders with correct org-vs-industry divergence detection before Section C begins.**

### 2.1 Trend computation

For each KPI, compute monthly values for the org AND for peer groups at MSA / state / national level, over the available history (up to 24 months or all available).

```sql
-- Monthly trend: org vs peer hierarchy
-- Run for each geographic level separately
SELECT
  service_month,
  geo_level,                              -- 'ORG' | 'MSA' | 'STATE' | 'NATIONAL'
  geo_id,                                 -- org_id | msa_code | state | 'US'
  AVG(panel_size)                         AS avg_panel_size,
  STDDEV(panel_size)                      AS std_panel_size,
  AVG(claims_per_bene)                    AS avg_claims_per_bene,
  STDDEV(claims_per_bene)                 AS std_claims_per_bene,
  AVG(payment_per_claim)                  AS avg_payment_per_claim,
  STDDEV(payment_per_claim)              AS std_payment_per_claim,
  COUNT(DISTINCT servicing_npi)           AS provider_count
FROM (
  -- NPI-level KPIs by month [nest Phase 1.1 query here without org filter for peers]
)
GROUP BY 1,2,3
ORDER BY 1
```

### 2.2 Divergence detection algorithm

```python
def detect_divergence(org_series, industry_series, window=3):
    """
    Detects when org trend is statistically diverging from industry.
    Returns: divergence_start_month, severity ('mild'|'moderate'|'critical'), direction
    """
    org_arr = np.array(org_series)
    ind_arr = np.array(industry_series)
    
    # Rate of change (rolling window)
    org_roc  = np.diff(org_arr[-window:]).mean() / org_arr[-window-1]
    ind_roc  = np.diff(ind_arr[-window:]).mean() / ind_arr[-window-1]
    roc_gap  = org_roc - ind_roc
    
    # Z-score of org value vs peer distribution
    peer_mean = ind_arr[-1]
    peer_std  = np.std(ind_arr[-6:])  # rolling std of industry
    z = (org_arr[-1] - peer_mean) / peer_std if peer_std > 0 else 0
    
    severity = 'none'
    if abs(z) > 2.0 or abs(roc_gap) > 0.03:  severity = 'critical'
    elif abs(z) > 1.0 or abs(roc_gap) > 0.015: severity = 'moderate'
    elif abs(z) > 0.5 or abs(roc_gap) > 0.008: severity = 'mild'
    
    direction = 'below' if z < 0 else 'above'
    
    # Find when divergence started
    divergence_start = None
    for i in range(len(org_arr)-1, 0, -1):
        z_i = (org_arr[i] - ind_arr[i]) / peer_std if peer_std > 0 else 0
        if abs(z_i) < 0.5:
            divergence_start = i + 1
            break
    
    return {
        'severity': severity,
        'direction': direction,
        'org_roc_monthly': round(org_roc * 100, 2),
        'industry_roc_monthly': round(ind_roc * 100, 2),
        'z_score': round(z, 2),
        'divergence_start_month_index': divergence_start,
        'consecutive_months_outside_band': sum(
            1 for o, i in zip(org_arr[-6:], ind_arr[-6:])
            if abs(o - i) / i > 0.1
        )
    }
```

### 2.3 Provider drift detection

```python
def detect_provider_drift(provider_monthly_df, baseline_months=12, recent_months=3):
    """
    For each provider + KPI: compare recent trend to own baseline.
    Flags accelerating decline as highest priority.
    """
    results = []
    for npi in provider_monthly_df['servicing_npi'].unique():
        npi_df = provider_monthly_df[provider_monthly_df['servicing_npi'] == npi]
        for kpi in ['panel_size', 'claims_per_bene', 'payment_per_claim']:
            series = npi_df.sort_values('service_month')[kpi].values
            if len(series) < 4: continue
            baseline = series[:baseline_months].mean()
            recent = series[-recent_months:].mean()
            pct_change = (recent - baseline) / baseline if baseline > 0 else 0
            # Acceleration: is it getting worse faster?
            if len(series) >= 6:
                early_roc = np.diff(series[-6:-3]).mean()
                late_roc  = np.diff(series[-3:]).mean()
                accelerating = (late_roc < early_roc) if pct_change < 0 else (late_roc > early_roc)
            else:
                accelerating = False
            results.append({
                'servicing_npi': npi,
                'kpi': kpi,
                'baseline_value': round(baseline, 2),
                'recent_value': round(recent, 2),
                'pct_change_vs_baseline': round(pct_change * 100, 1),
                'accelerating': accelerating,
                'severity': 'critical' if abs(pct_change) > 0.2 and accelerating
                            else 'moderate' if abs(pct_change) > 0.15
                            else 'mild' if abs(pct_change) > 0.08
                            else 'none'
            })
    return results
```

**STOP Phase 2 test criteria:**
- [ ] Trend series produces correct monthly values for all KPIs (validate against raw BQ query)
- [ ] Divergence algorithm correctly identifies known test cases (inject synthetic divergence)
- [ ] Provider drift correctly flags providers with >15% decline
- [ ] Section B JSON validates against schema
- [ ] Peer quartile bands (p25/p75) computed and stored for all 24 months

---

## Phase 3 — Report engine: Section C (strategic matrix, co-created)

**Build stop: Matrix renders with correct quadrant placement and actions are editable before integration begins.**

### 3.1 Quadrant scoring

```python
def score_for_matrix(section_a, section_b):
    """
    Scores each item on two axes:
    x = historical performance (0-100, FL percentile composite)
    y = forward trajectory (0-100, derived from trend divergence)
    Returns list of items with x, y, label, category, revenue_at_stake
    """
    items = []
    
    # Strategic KPIs
    for kpi_name, kpi_data in section_a['kpis'].items():
        trend = section_b['kpi_trends'][kpi_name]
        x = kpi_data['fl_percentile']
        # Forward trajectory: 50 = flat, >50 = improving, <50 = deteriorating
        y = 50 + (trend['org_roc_monthly'] - trend['industry_roc_monthly']) * 500
        y = max(0, min(100, y))
        items.append({
            'id': kpi_name,
            'label': kpi_name.replace('_', ' ').title(),
            'category': 'kpi',
            'x': round(x, 1),
            'y': round(y, 1),
            'revenue_at_stake': section_a['kpis'][kpi_name].get('total_paid', 0),
            'divergence': trend['divergence']
        })
    
    # Service lines
    for sl in section_a['service_lines']:
        x = sl['fl_percentile_payment']
        trend_data = next((t for t in section_b['hcpcs_trends'] if t['hcpcs_code'] == sl['hcpcs_code']), None)
        y = 50 if not trend_data else 50 + trend_data['org_roc_monthly'] * 400
        y = max(0, min(100, y))
        items.append({
            'id': sl['hcpcs_code'],
            'label': sl['hcpcs_code'],
            'category': 'service_line',
            'x': round(x, 1),
            'y': round(y, 1),
            'revenue_at_stake': sl['total_paid']
        })
    
    # Providers
    for prov in section_a['providers']:
        x = (prov['panel_percentile'] + prov['utiliz_percentile']) / 2
        drift = next((d for d in section_b['provider_drift']
                      if d['servicing_npi'] == prov['servicing_npi']
                      and d['kpi'] == 'claims_per_bene'), None)
        y = 50 if not drift else 50 - drift['pct_change_vs_baseline'] * 1.5
        y = max(0, min(100, y))
        items.append({
            'id': prov['servicing_npi'],
            'label': prov['provider_name'],
            'category': 'provider',
            'x': round(x, 1),
            'y': round(y, 1),
            'revenue_at_stake': prov['total_paid']
        })
    
    return items
```

### 3.2 Action generation

Actions are generated by the platform, then confirmed/edited by the user. They are NOT auto-committed to the task module until the user explicitly approves them.

```python
QUADRANT_ACTION_TEMPLATES = {
    'urgent': [  # x < 50, y < 50
        {
            'priority': 1,
            'template': "Conduct root-cause audit on {item_label}: {kpi} at {percentile}th pctile and declining at {roc}%/mo.",
            'owner_role': 'clinical_ops',
            'horizon_days': 30
        },
        {
            'priority': 2,
            'template': "Set 60-day recovery plan for {item_label} with measurable targets on {kpi}.",
            'owner_role': 'clinical_director',
            'horizon_days': 60
        },
        {
            'priority': 3,
            'template': "Weekly monitoring cadence for {item_label} until above 35th pctile.",
            'owner_role': 'operations',
            'horizon_days': 90
        }
    ],
    'fix_accelerate': [ ... ],  # x < 50, y > 50
    'defend': [ ... ],          # x > 50, y < 50
    'protect_scale': [ ... ]    # x > 50, y > 50
}

def generate_actions(matrix_items, section_a, section_b):
    actions = []
    for item in matrix_items:
        quadrant = (
            'urgent'          if item['x'] < 50 and item['y'] < 50 else
            'fix_accelerate'  if item['x'] < 50 and item['y'] >= 50 else
            'defend'          if item['x'] >= 50 and item['y'] < 50 else
            'protect_scale'
        )
        templates = QUADRANT_ACTION_TEMPLATES[quadrant]
        for t in templates[:3]:  # top 3 per item
            actions.append({
                'action_id': str(uuid.uuid4()),
                'item_id': item['id'],
                'item_label': item['label'],
                'category': item['category'],
                'quadrant': quadrant,
                'priority': t['priority'],
                'description': t['template'].format(**item, **extract_kpi_context(item, section_a, section_b)),
                'owner_role': t['owner_role'],
                'horizon_days': t['horizon_days'],
                'status': 'PROPOSED',           # user must approve to become ACTIVE
                'revenue_at_stake': item['revenue_at_stake']
            })
    return sorted(actions, key=lambda a: (a['priority'], -a['revenue_at_stake']))
```

**STOP Phase 3 test criteria:**
- [ ] All matrix items score correctly (validate x/y against manual calculation)
- [ ] Quadrant assignment correct for all test cases
- [ ] Actions generated for all four quadrants
- [ ] Actions remain PROPOSED until user approval (no auto-commit)
- [ ] Section C JSON validates against schema

---

## Phase 4 — Report renderer (HTML + PDF)

**Build stop: Full report renders correctly in browser and exports to PDF before module integration begins.**

### 4.1 Report renderer architecture

```
report-renderer/
├── index.ts               — entry point, accepts report_id, renders HTML
├── sections/
│   ├── cover.ts           — org name, period, badges, caveats
│   ├── section-a.ts       — executive scorecard + service lines + providers + geo
│   ├── section-b.ts       — trend intelligence (4 subsections)
│   └── section-c.ts       — strategic matrix + quadrant actions
├── charts/
│   ├── kpi-trend.ts       — org vs industry, quartile band, Chart.js
│   ├── hcpcs-trend.ts     — per-code trend charts
│   ├── provider-drift.ts  — drift matrix with sparklines
│   ├── market-cascade.ts  — 4-level trend comparison
│   └── matrix-bubble.ts   — 2×2 strategic matrix bubble chart
├── pdf/
│   └── export.ts          — Puppeteer PDF generation from HTML
└── styles/
    └── report.css         — print-safe styles, matches design system
```

### 4.2 Data caveats — mandatory display rules

These strings must appear verbatim in every rendered report. Non-negotiable.

```typescript
const DATA_CAVEATS = {
  primary: "This report uses Medicare fee-for-service claims from the DOGE dataset (outpatient only, through Dec 2024). It reflects billing activity for a single payor type and does not represent the organization's complete financial picture.",
  payor_scope: "Payor scope: Medicare FFS only. Medicaid, Medicare Advantage, and commercial claims are not included.",
  period_scope: "Period: data through December 2024. DOGE dataset is updated periodically; refresh dates may vary.",
  completeness: "DOGE data is not audited and should be treated as indicative, not definitive.",
  scalability_note: "This report is designed to expand as additional payor and service line data becomes available. Current scope will be clearly labeled on each metric."
}
```

### 4.3 PDF export spec

```typescript
// Puppeteer config for PDF export
const PDF_OPTIONS = {
  format: 'Letter',
  printBackground: true,
  margin: { top: '0.75in', bottom: '0.75in', left: '0.75in', right: '0.75in' },
  displayHeaderFooter: true,
  headerTemplate: `<div style="font-size:9px;width:100%;text-align:center;color:#888">
    {org_name} · Financial Closure Report · {period} · CONFIDENTIAL
  </div>`,
  footerTemplate: `<div style="font-size:9px;width:100%;text-align:center;color:#888">
    Page <span class="pageNumber"></span> of <span class="totalPages"></span>
  </div>`
}
```

**STOP Phase 4 test criteria:**
- [ ] HTML report renders all 9 sections without errors
- [ ] All charts render with real data (not synthetic)
- [ ] PDF exports at correct dimensions with header/footer
- [ ] Data caveats appear on every page (PDF) and in caveat block (HTML)
- [ ] Report loads in < 3 seconds on real data
- [ ] Mobile-responsive (CEO reads this on phone)

---

## Phase 5 — Task module integration

**Build stop: Approved actions appear in task module and are trackable before alert engine integration.**

### 5.1 Task schema

```sql
CREATE TABLE `{project}.{dataset}.tasks` (
  task_id           STRING,             -- UUID
  report_id         STRING,             -- FK to report_index
  org_id            STRING,
  action_id         STRING,             -- FK to section_c generated action
  title             STRING,
  description       STRING,
  owner_role        STRING,
  owner_user_id     STRING,             -- assigned after co-creation
  priority          INT,                -- 1 = highest
  horizon_days      INT,
  due_date          DATE,
  status            STRING,             -- PROPOSED | ACTIVE | IN_PROGRESS | DONE | DISMISSED
  quadrant          STRING,
  category          STRING,             -- provider | service_line | kpi | market | ops
  item_id           STRING,             -- the NPI, HCPCS code, etc.
  revenue_at_stake  FLOAT,
  created_at        TIMESTAMP,
  updated_at        TIMESTAMP,
  resolved_at       TIMESTAMP,
  resolution_notes  STRING
)
```

### 5.2 Co-creation flow

```
1. Section C renders with all actions in PROPOSED state
2. User reviews each action:
   - Approve → status = ACTIVE, assign owner, set due date
   - Edit → modify description, owner, or horizon, then Approve
   - Dismiss → status = DISMISSED, reason required
3. On Approve: task written to tasks table, notification sent to owner
4. Task module shows tasks grouped by: quadrant | priority | owner | due date
5. Monthly report refresh checks task status and updates section C accordingly
```

### 5.3 Task-report feedback loop

```python
def refresh_section_c_with_task_status(report_id, section_c_json, tasks_df):
    """
    On monthly refresh, update the strategic matrix to reflect:
    - Tasks completed → did the metric improve?
    - Tasks overdue → escalate priority
    - New divergences → propose new actions
    """
    for item in section_c_json['matrix_items']:
        related_tasks = tasks_df[tasks_df['item_id'] == item['id']]
        item['task_summary'] = {
            'active': len(related_tasks[related_tasks['status'] == 'ACTIVE']),
            'done': len(related_tasks[related_tasks['status'] == 'DONE']),
            'overdue': len(related_tasks[
                (related_tasks['status'] == 'ACTIVE') &
                (related_tasks['due_date'] < pd.Timestamp.today())
            ])
        }
    return section_c_json
```

**STOP Phase 5 test criteria:**
- [ ] Approved action creates task in tasks table
- [ ] Dismissed action does not create task
- [ ] Task appears in task module UI grouped correctly
- [ ] Monthly refresh updates task status in section C
- [ ] Overdue tasks escalate correctly

---

## Phase 6 — Alert engine integration

**Build stop: Alerts fire correctly on new data before chatbot integration.**

### 6.1 Alert schema

```sql
CREATE TABLE `{project}.{dataset}.alerts` (
  alert_id          STRING,
  org_id            STRING,
  report_id         STRING,
  alert_type        STRING,         -- DIVERGENCE | DRIFT | THRESHOLD | OPPORTUNITY
  severity          STRING,         -- CRITICAL | MODERATE | MILD
  kpi               STRING,
  item_id           STRING,         -- NPI, HCPCS, ZIP, etc.
  item_label        STRING,
  description       STRING,
  metric_value      FLOAT,
  peer_value        FLOAT,
  z_score           FLOAT,
  roc_monthly       FLOAT,
  detected_at       TIMESTAMP,
  acknowledged_at   TIMESTAMP,
  resolved_at       TIMESTAMP,
  status            STRING,         -- NEW | ACKNOWLEDGED | RESOLVED | DISMISSED
  linked_task_id    STRING          -- if action taken
)
```

### 6.2 Alert trigger logic

```python
def run_alert_engine(org_id, new_section_b, prior_section_b, thresholds):
    alerts = []
    
    for kpi in ['panel_size', 'claims_per_bene', 'payment_per_claim']:
        new_trend  = new_section_b['kpi_trends'][kpi]
        prior_trend = prior_section_b['kpi_trends'][kpi]
        
        # New divergence this month
        if new_trend['divergence']['severity'] in ('critical', 'moderate'):
            if prior_trend['divergence']['severity'] == 'none':
                alerts.append(build_alert('DIVERGENCE', kpi, new_trend, severity=new_trend['divergence']['severity']))
        
        # Divergence accelerating
        if (new_trend['org_roc_monthly'] < prior_trend['org_roc_monthly'] and
            new_trend['divergence']['severity'] == 'critical'):
            alerts.append(build_alert('DIVERGENCE', kpi, new_trend, severity='critical',
                                      description="Divergence accelerating — rate worsening month-over-month"))
        
        # Provider drift crossing threshold
        for drift in new_section_b['provider_drift']:
            if drift['severity'] == 'critical' and drift['accelerating']:
                alerts.append(build_alert('DRIFT', drift['kpi'], drift,
                                          item_id=drift['servicing_npi'],
                                          severity='critical'))
    
    return alerts
```

### 6.3 Alert routing by user role

```python
ALERT_ROUTING = {
    'DIVERGENCE': {
        'critical':  ['ceo', 'cfo', 'clinical_director', 'revenue_cycle'],
        'moderate':  ['clinical_director', 'revenue_cycle'],
        'mild':      ['operations']
    },
    'DRIFT': {
        'critical':  ['clinical_director', 'hr'],
        'moderate':  ['clinical_director'],
        'mild':      ['operations']
    },
    'OPPORTUNITY': {
        'any':       ['strategy', 'business_dev', 'cfo']
    }
}
```

**STOP Phase 6 test criteria:**
- [ ] Alert fires when divergence crosses severity threshold
- [ ] Alert does NOT fire if already acknowledged this period
- [ ] Routing sends alert to correct roles only
- [ ] Alert links to correct section of report
- [ ] Alert-to-task pipeline: alert can spawn a proposed action

---

## Phase 7 — Chatbot integration

**Build stop: Chatbot correctly answers questions grounded in report data before user routing integration.**

### 7.1 Chatbot context construction

```python
def build_chatbot_context(report_id, report_index_row):
    """
    Compress report into a chatbot system prompt context.
    Must be under 8k tokens. Prioritize: KPIs > alerts > top actions > caveats.
    """
    ctx = f"""
    FINANCIAL CLOSURE REPORT CONTEXT
    Org: {report_index_row['org_name']}
    Period: {report_index_row['report_period']}
    Payor scope: {', '.join(report_index_row['payor_scope'])}
    Service scope: {', '.join(report_index_row['service_scope'])}
    
    DATA CAVEATS (always surface when asked about financials):
    - Medicare FFS outpatient only. Not complete financial picture.
    - DOGE data through Dec 2024. Not audited.
    
    KEY METRICS (vs taxonomy-adjusted FL peers):
    {format_kpis_for_context(report_index_row['section_a_json'])}
    
    ACTIVE ALERTS:
    {format_alerts_for_context(report_index_row)}
    
    TOP PRIORITY ACTIONS:
    {format_actions_for_context(report_index_row['section_c_json'])}
    
    TREND SIGNALS:
    {format_trends_for_context(report_index_row['section_b_json'])}
    """
    return ctx.strip()
```

### 7.2 Chatbot question taxonomy

The chatbot must handle three question types differently:

```python
QUESTION_TYPES = {
    'strategic': {
        'examples': ['What is our biggest risk?', 'Where should we focus?', 'How do we compare to peers?'],
        'response_style': 'synthesis + recommendation',
        'always_include': ['data_caveats', 'confidence_level']
    },
    'operational': {
        'examples': ['What is wrong with Dr. Johnson?', 'Why is 90853 declining?'],
        'response_style': 'specific data + root cause hypotheses',
        'always_include': ['metric_values', 'trend_direction', 'peer_comparison']
    },
    'financial': {
        'examples': ['What is our payment rate?', 'How much are we losing on group therapy?'],
        'response_style': 'precise numbers + context',
        'always_include': ['data_caveats', 'payor_scope_reminder', 'calculation_shown']
    }
}
```

### 7.3 Mandatory chatbot response rules

```python
CHATBOT_GUARDRAILS = [
    "Always surface data caveats when answering financial questions.",
    "Never extrapolate DOGE data to represent full org revenue.",
    "Always qualify peer comparisons with: 'among taxonomy-matched Medicare FFS peers'.",
    "When asked about a provider by name, confirm NPI match before citing data.",
    "When trend data is < 6 months, flag as insufficient for trend conclusions.",
    "Never recommend specific payer contracts, codes, or clinical protocols.",
    "Always offer to show the underlying data when making a claim."
]
```

**STOP Phase 7 test criteria:**
- [ ] Chatbot correctly answers 10 test questions from each category (strategic / operational / financial)
- [ ] Data caveats appear in every financial response
- [ ] Chatbot refuses to extrapolate beyond payor/service scope
- [ ] Chatbot correctly references task status when asked about actions
- [ ] Response time < 5 seconds for all question types

---

## Phase 8 — User routing & access control

**Build stop: Role-based access correctly limits report sections before full system integration test.**

### 8.1 Role definitions

```python
USER_ROLES = {
    'executive': {
        'sees': ['cover', 'section_a_summary', 'section_b_summary', 'section_c_matrix', 'top_alerts'],
        'chatbot_depth': 'strategic',
        'task_access': 'view_approve'
    },
    'clinical_director': {
        'sees': ['all_sections', 'provider_detail', 'service_line_detail'],
        'chatbot_depth': 'operational',
        'task_access': 'full'
    },
    'revenue_cycle': {
        'sees': ['section_a_payment', 'section_b_payment_trends', 'service_line_detail'],
        'chatbot_depth': 'financial',
        'task_access': 'payment_tasks_only'
    },
    'strategy': {
        'sees': ['all_sections', 'market_archetype', 'geographic_detail'],
        'chatbot_depth': 'strategic',
        'task_access': 'view_propose'
    },
    'analyst': {
        'sees': ['all_sections'],
        'chatbot_depth': 'all',
        'task_access': 'full'
    }
}
```

### 8.2 Value-based routing

```python
def compute_user_value_tier(user_id, org_id, report_id):
    """
    Derive user value tier from report findings.
    High-value users = those whose operational domain is in urgent/defend quadrant.
    """
    section_c = get_section_c(report_id)
    urgent_domains = [
        item['owner_role'] for item in section_c['matrix_items']
        if item['quadrant'] in ('urgent', 'defend')
    ]
    user_role = get_user_role(user_id, org_id)
    if user_role in urgent_domains:
        return 'high'        # proactive alerts, priority chatbot, dashboard prominence
    elif user_role in ['executive']:
        return 'high'
    else:
        return 'standard'
```

---

## Phase 9 — Full system integration test

**This is the final gate before production. All modules must pass together.**

### 9.1 End-to-end test scenario

```
1. Onboard test org (use Suncoast CMHC synthetic data)
2. Report engine runs automatically → verify all 3 sections generated
3. HTML report renders → verify all 9 report sections visible
4. PDF exports → verify formatting, caveats, header/footer
5. User reviews section C → approves 5 actions, dismisses 2
6. Tasks appear in task module → verify correct owners, dates, priorities
7. Inject new monthly data with known divergence
8. Alert engine fires → verify correct severity, correct routing
9. Chatbot answers 20 test questions → verify accuracy, guardrails
10. Second user with different role logs in → verify section visibility is correct
11. Monthly refresh runs → verify report updates, task status carried forward
```

### 9.2 Performance benchmarks

| Operation | Target | Fail threshold |
|---|---|---|
| Report generation (full) | < 90 seconds | > 3 minutes |
| HTML render | < 3 seconds | > 8 seconds |
| PDF export | < 15 seconds | > 45 seconds |
| KPI query (BQ) | < 10 seconds | > 30 seconds |
| Trend query (24mo) | < 20 seconds | > 60 seconds |
| Alert engine run | < 30 seconds | > 2 minutes |
| Chatbot response | < 5 seconds | > 12 seconds |

### 9.3 Scalability validation

- Confirm adding a new payor requires only: (a) new rows in `vw_claims_base`, (b) new value in `payor_type`. Zero report code changes.
- Confirm adding a new service category requires only: (a) new rows in `vw_claims_base`, (b) new value in `service_category`. Zero report code changes.
- Confirm adding a new org requires only: (a) org record in `report_index`, (b) NPI list. Zero schema changes.

---

## Build sequence summary

| Phase | What | Gate |
|---|---|---|
| 0 | Foundation: BQ schema, NPI enrichment, crosswalk, report index | All tables populated, join coverage > 98% |
| 1 | Section A: historic performance facts | KPIs correct, peer scoring validated |
| 2 | Section B: evolving trends facts | Divergence detection validated on synthetic data |
| 3 | Section C: strategic matrix, co-created | Quadrant scoring correct, actions PROPOSED only |
| 4 | Report renderer: HTML + PDF | Full render < 3s, PDF exports correctly |
| 5 | Task module integration | Approved actions in task module, refresh loop works |
| 6 | Alert engine integration | Alerts fire on divergence, routing correct |
| 7 | Chatbot integration | 30 test questions pass, guardrails enforced |
| 8 | User routing | Role-based access correct for all role types |
| 9 | Full system integration test | All 11 E2E scenarios pass, performance benchmarks met |

---

## File structure for implementation

```
financial-closure-report/
├── data/
│   ├── schemas/
│   │   ├── vw_claims_base.sql
│   │   ├── npi_enrichment.sql
│   │   ├── zip_msa_crosswalk.sql
│   │   ├── report_index.sql
│   │   ├── tasks.sql
│   │   └── alerts.sql
│   └── pipelines/
│       ├── npi_enrichment_pipeline.py
│       └── zip_msa_crosswalk_load.py
├── report-engine/
│   ├── section_a.py
│   ├── section_b.py
│   ├── section_c.py
│   ├── kpi_queries.py
│   ├── trend_queries.py
│   ├── peer_scoring.py
│   ├── divergence_detection.py
│   └── provider_drift.py
├── report-renderer/
│   ├── index.ts
│   ├── sections/
│   ├── charts/
│   ├── pdf/
│   └── styles/
├── modules/
│   ├── tasks/
│   │   ├── task_schema.sql
│   │   ├── task_service.py
│   │   └── task_ui.ts
│   ├── alerts/
│   │   ├── alert_schema.sql
│   │   ├── alert_engine.py
│   │   └── alert_routing.py
│   ├── chatbot/
│   │   ├── context_builder.py
│   │   ├── question_classifier.py
│   │   └── guardrails.py
│   └── user_routing/
│       ├── role_definitions.py
│       └── value_tier.py
├── tests/
│   ├── phase_0_tests.py
│   ├── phase_1_tests.py
│   ├── phase_2_tests.py
│   ├── phase_3_tests.py
│   ├── phase_4_tests.py
│   ├── phase_5_tests.py
│   ├── phase_6_tests.py
│   ├── phase_7_tests.py
│   ├── phase_8_tests.py
│   └── e2e_integration_test.py
└── docs/
    ├── TECH_SPEC.md           (this file)
    ├── DATA_DICTIONARY.md
    └── REPORT_SCHEMA.md
```
