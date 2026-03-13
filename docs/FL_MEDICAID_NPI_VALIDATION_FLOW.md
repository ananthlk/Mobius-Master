# FL Medicaid NPI Validation Pipeline — Strategy Schematic

## B0–B6 validation layers (canonical)

Single read head for front end and chat: **B6**. Query by **org_id**, **npi**, or **site_id**; B6 returns all details from B0–B5. See `mobius-dbt/docs/B6_INTEGRATED_REPORT.md`.

| Layer | Purpose | Consumers |
|-------|---------|-----------|
| **B0** | Roster / org structure (facility list, sub-org by address, billing-NPI groups, roster list) | B6 only |
| **B1** | NPPES vs PML alignment (service location / address, e.g. ZIP+9) | B6 only |
| **B2** | Address info (mailing vs practice; informational) | B6 only |
| **B3** | Taxonomy alignment (NPPES vs FL allowed) | B6 only |
| **B4** | Medicaid ID check (roster per NPI, permissible) | B6 only |
| **B5** | Medicaid ID + NPI + taxonomy + site alignment (combined rule) | B6 only |
| **B6** | **Integrated report** — all B0–B5 detail; query by org_id, npi, or site_id | Front end, Chat |

---

## Data flow and table relationships

```mermaid
flowchart TB
    subgraph sources [Source Data]
        DOGE[stg_doge: DOGE claims]
        PML[stg_pml: FL Medicaid PML]
        PPL[stg_ppl: FL Pending Provider List]
        TML[stg_tml: Taxonomy Master]
        NPPES[NPPES npi_optimized]
    end

    subgraph step11 [Step 1.1: Organizations]
        ORG[organizations]
        ORG -->|org_key = billing_tin| ORG
    end

    subgraph step12 [Step 1.2: Org → Billing NPIs]
        OBN[org_billing_npis]
    end

    subgraph step13 [Step 1.3: Billing → Servicing]
        BSP[billing_servicing_pairs]
    end

    subgraph step14 [Step 1.4: NPI Taxonomies]
        NPI_TAX[npi_taxonomies]
    end

    subgraph step15 [Step 1.5: NPI Addresses]
        NPI_ADDR[npi_addresses]
    end

    subgraph step2 [Step 2: Probabilistic Mapping]
        THS[taxonomy_hcpcs_scores]
    end

    subgraph step3 [Step 3: Granular Validation]
        DVG[doge_validation_granular]
    end

    subgraph step4 [Step 4: Aggregated Scoring]
        AGG[aggregated_scores]
    end

    subgraph step5 [Step 5: Report for Chat]
        PY[Python skill: fetch + format]
    end

    subgraph readiness [Provider Readiness]
        PR[provider_readiness]
        PRS[provider_readiness_summary]
    end

    DOGE --> ORG
    DOGE --> OBN
    DOGE --> BSP
    NPPES --> ORG
    PML --> ORG

    ORG -->|org_key| OBN
    DOGE --> OBN

    OBN -->|billing_npi| BSP
    DOGE --> BSP

    NPPES --> NPI_TAX
    TML --> NPI_TAX
    PML --> NPI_TAX

    NPPES --> NPI_ADDR
    PML --> NPI_ADDR

    DOGE --> THS
    NPPES -->|servicing NPI → taxonomy| THS

    ORG --> DVG
    BSP --> DVG
    NPI_TAX --> DVG
    NPI_ADDR --> DVG
    THS --> DVG

    DVG --> AGG

    AGG --> PY
    DVG --> PY

    BSP --> PR
    NPPES --> PR
    PML --> PR
    PPL --> PR
    PR --> PRS
    PRS --> PY
```

## Table dependency chain

| Step | Table | Depends on | Feeds into |
|------|-------|------------|------------|
| **1.1** | `organizations` | DOGE (billing_tin), NPPES, PML | 1.2, 3 |
| **1.2** | `org_billing_npis` | DOGE, organizations | 3 |
| **1.3** | `billing_servicing_pairs` | DOGE | 3 |
| **1.4** | `npi_taxonomies` | NPPES, TML, PML | 2, 3 |
| **1.5** | `npi_addresses` | NPPES, PML | 3 |
| **2** | `taxonomy_hcpcs_scores` | DOGE, NPPES | 3 |
| **3** | `doge_validation_granular` | All of 1.1–1.5, 2 | 4, 5 |
| **4** | `aggregated_scores` | doge_validation_granular | 5 |
| **5** | Python skill | aggregated_scores, doge_validation_granular | Chat UI |
| — | `provider_readiness` | billing_servicing_pairs, NPPES, PML, PPL | provider_readiness_summary |
| — | `provider_readiness_summary` | provider_readiness | Chat UI |

## Key relationships

```
organizations (org_key = billing_tin)
    ↓
org_billing_npis (org_key → billing_npi list)
    ↓
billing_servicing_pairs (billing_npi → servicing_npi, hcpcs, spend)
    ↓
doge_validation_granular (per-claim row + taxonomy_score, address_match, fl_enrolled)
    ↓
aggregated_scores (org / billing_npi / servicing_npi level, weighted by spend)
    ↓
Python → Chat
```

## Problems today vs next quarter

### Problems today (current scope)

**Provider identity and enrollment** — 1/0 score per NPI per claim period:

- Valid NPI (exists in NPPES)
- Enrolled in FL Medicaid (in PML)
- Effective dates overlap claim period (when PML has contract_effective_date / contract_end_date)

Output: `provider_readiness` and `provider_readiness_summary` with `report_date` (point-in-time). Run monthly; for March 1st: `dbt run --vars 'report_date: 2026-03-01' --select provider_readiness provider_readiness_summary`.

### Problems next quarter

- Taxonomy reconciliation (NPPES vs TML vs PML) — surface discrepancies
- Taxonomy–HCPCS alignment (service validity)
- Address match (enrolled vs NPPES)
- NCCI / service-level edits
