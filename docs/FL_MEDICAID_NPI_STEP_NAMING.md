# Medicaid NPI — Step naming (state-agnostic)

Pipeline outputs use a **step** prefix so the sequence is clear. **State (e.g. FL) is an input**, not part of the object name. The only state-specific **input** is the **PML** (Provider Master List); different states supply their own PML with the same structure. This keeps the pipeline reusable for other states.

---

## State as input

| Concept | How it works |
|--------|----------------|
| **State** | Supplied as input (e.g. dbt var `state_code`, default `'FL'`). Used to filter NPPES by practice state, label outputs, and select the right PML. |
| **PML** | **State-specific.** Each state has its own Provider Master List (same schema: NPI, contract dates, service location, taxonomy, etc.). Load per state (e.g. `stg_pml` from FL PML, or `stg_pml_tx` from TX PML, or one table with a `state` column). |
| **TML / DOGE / PPL** | Same idea: state-specific files, same structure. TML = state’s approved taxonomy list; DOGE/claims and PPL = state’s data. |
| **Step models** | **State-agnostic names:** `step1a`, `step1`, `step2a`, `step2`, …, `step13`. No `_fl` or state in the name. Scope is determined by the state-scoped refs they use (currently FL implementation). |

Implementing a new state: load that state’s PML (and TML, PPL, claims) into landing; run the same pipeline with `state_code` set to that state (once underlying models are parameterized by `state_code`).

---

## Naming convention

| Pattern | Meaning |
|--------|--------|
| **stepN** | Main table/view for step N (final output of that step). |
| **stepNa**, **stepNb**, … | Sub-tables or sub-views that feed into step N (built in order a → b → … → main). |

Names are state-agnostic: `step1a`, `step1`, `step2a`, `step2`, …, `step13`.

---

## Step and sub-step index

### Step 1 — Set up organization and roster
| Model | Description | Built from (current) |
|-------|-------------|----------------------|
| step1a | Organizations (billing NPI, org name, address, spend) | organizations |
| step1b | Billing–servicing pairs (state-scoped) | billing_servicing_pairs_fl |
| step1c | Facility master list | b0_facility_master_fl |
| step1d | Sub-org addresses (sites) | b0_sub_org_address_fl |
| step1e | NPI ↔ sub-org address propensity | b0_address_propensity_fl |
| step1f | Sub-org members | b0_sub_org_members_fl |
| step1g | Billing NPI → member NPIs | b0_billing_npi_members_fl |
| **step1** | **Roster list** (org_id, site_id, npi, …) | b0_roster_list_fl |

### Step 2 — Validate locations
| Model | Description | Built from (current) |
|-------|-------------|----------------------|
| step2a | Site/location list (sub-org addresses) | b0_sub_org_address_fl |
| **step2** | **Location validation** (site-level checks; today = address validation) | address_validation_fl |

### Step 3 — Validate NPIs
| Model | Description | Built from (current) |
|-------|-------------|----------------------|
| step3a | NPPES state cohort | nppes_fl |
| **step3** | **NPI validation** (in_nppes, enrollment-related flags) | provider_readiness |

### Step 4 — Validate address
| Model | Description | Built from (current) |
|-------|-------------|----------------------|
| step4a | NPI addresses (practice/mailing, B1 fields) | npi_addresses_fl |
| step4b | Address validation (B1/B2/B3 flags) | address_validation_fl |
| **step4** | **Address validation output** | address_validation_fl |

### Step 5 — Validate Medicaid ID presence
| Model | Description | Built from (current) |
|-------|-------------|----------------------|
| step5a | Medicaid ID roster per NPI | b4_medicaid_id_roster_fl |
| step5b | Per-NPI Medicaid ID status | b4_npi_medicaid_status_fl |
| **step5** | **Medicaid ID validation** (main) | b4_npi_medicaid_status_fl |

### Step 6 — Validate approved taxonomy
| Model | Description | Built from (current) |
|-------|-------------|----------------------|
| step6a | State Medicaid taxonomy (TML) | fl_medicaid_taxonomy |
| step6b | NPPES vs TML alignment (B3) | b3_taxonomy_alignment_fl |
| step6c | Taxonomy validation (C1–C4, D, F) | taxonomy_validation_fl |
| **step6** | **Taxonomy validation output** (main) | b3_taxonomy_alignment_fl |

### Step 7 — Validate billing codes
| Model | Description | Built from (current) |
|-------|-------------|----------------------|
| step7a | Taxonomy → HCPCS volume | taxonomy_hcpcs_volume_fl |
| step7b | Volume with indexing / outliers | taxonomy_hcpcs_volume_indexed_fl |
| step7c | Danger opportunities (code unusual for taxonomy) | provider_danger_opportunities_fl |
| **step7** | **Billing code validation** (main) | taxonomy_validation_fl |

### Step 8 — Comprehensive check (NPI + Medicaid ID + taxonomy + location)
| Model | Description | Built from (current) |
|-------|-------------|----------------------|
| **step8** | **Integrated report** (B6; single read head) | b6_integrated_report_fl |

### Step 9 — Produce error report with recommendations
| Model | Description | Built from (current) |
|-------|-------------|----------------------|
| step9a | Provider readiness report (status, issues) | provider_readiness_report |
| step9b | Executive summary | provider_readiness_executive_summary |
| **step9** | **Error report** (main) | provider_readiness_report |

### Step 10 — Reserved
| Model | Description | Built from (current) |
|-------|-------------|----------------------|
| step10 | *(Reserved; placeholder view)* | — |

### Step 11 — Validate billing rates
| Model | Description | Built from (current) |
|-------|-------------|----------------------|
| **step11** | **Billing rate validation** (stub until rate data) | Placeholder / stub |

### Step 12 — Develop missed codes and billing
| Model | Description | Built from (current) |
|-------|-------------|----------------------|
| step12a | Missed opportunities (add taxonomy to unlock codes) | provider_missed_opportunities_fl |
| step12b | Danger opportunities (review billing) | provider_danger_opportunities_fl |
| **step12** | **Missed/billing opportunities** (main) | provider_missed_opportunities_fl |

### Step 13 — Develop revenue enhancement report
| Model | Description | Built from (current) |
|-------|-------------|----------------------|
| step13a | Propensity score | provider_propensity_score_fl |
| **step13** | **Revenue enhancement report** (summary) | provider_readiness_executive_summary |

---

## dbt model layout

Step models live in `models/marts/medicaid_npi/` with filenames matching the model name:

- `step1a.sql` … `step1.sql`
- `step2a.sql`, `step2.sql`
- …
- `step13a.sql`, `step13.sql`

Each is a **view** that `select * from {{ ref('existing_model') }}` (or a thin wrapper). Pipeline logic stays in the current b0_*, provider_*, etc. models; the step layer is naming and sequence only.

---

## Run order

To build the full step layer (views only; refs build first):

```bash
dbt run --select step1a step1b step1c step1d step1e step1f step1g step1 \
  step2a step2 step3a step3 step4a step4b step4 \
  step5a step5b step5 step6a step6b step6c step6 \
  step7a step7b step7c step7 step8 step9a step9b step9 \
  step10 step11 step12a step12b step12 step13a step13
```

Or by step: `dbt run --select step1*` then `step2*`, etc.

---

## Parameterizing for multiple states (future)

To support more than one state without duplicating logic:

1. **dbt var:** `state_code` (e.g. `'FL'`, `'TX'`). Default `'FL'`. Use in NPPES filter and any state-specific logic.
2. **Landing:** One PML (and TML, PPL, claims) per state. Options:
   - Separate dataset per state: `landing_medicaid_npi_fl`, `landing_medicaid_npi_tx`, and point `BQ_LANDING_MEDICAID_DATASET` at the chosen one; or
   - Single dataset with state-prefixed or state-keyed tables: `stg_pml_fl`, `stg_pml_tx`, or `stg_pml` with a `state` column.
3. **Marts:** Either state-specific datasets (`mobius_medicaid_npi_fl`, `mobius_medicaid_npi_tx`) or a single dataset with `state` on each table. Step model names stay `step1`, `step1a`, etc.; scope comes from the refs and the dataset they write to.
4. **Run:** `dbt run --vars '{"state_code": "TX"}'` (and appropriate landing dataset) to build for that state.
