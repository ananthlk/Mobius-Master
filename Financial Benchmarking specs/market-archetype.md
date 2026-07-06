# Market Archetype Methodology

## Purpose
Characterize FL ZIPs and MSAs as distinct market types so that KPI findings are interpreted in the right context. A high panel size in an underserved rural market is a very different signal than the same number in a saturated urban market.

---

## Data Inputs

| Input | Source | How to Get |
|-------|--------|-----------|
| Provider density (NPIs per market) | DOGE BQ | COUNT(DISTINCT servicing_npi) per ZIP/MSA |
| Total beneficiaries per market | DOGE BQ | SUM(total_beneficiaries) per ZIP/MSA |
| Panel size distribution | DOGE BQ | Computed KPI |
| Claims per beneficiary distribution | DOGE BQ | Computed KPI |
| Payment per claim distribution | DOGE BQ | Computed KPI |
| Physicians per 1,000 Medicaid | HRSA / CMS | Web search/fetch (see below) |
| Medicaid enrollment by county/ZIP | CMS | Public download |

### Fetching Public Data
- HRSA Area Health Resources Files: https://data.hrsa.gov/topics/health-workforce/ahrf
- CMS Medicaid enrollment: https://www.medicaid.gov/medicaid/program-information/medicaid-and-chip-enrollment-data
- Use `web_search` + `web_fetch` to retrieve current files
- Cross-reference by FIPS county code → ZIP → MSA

---

## Archetype Scoring Framework

Score each market on 4 dimensions (0–3 scale each):

### Dimension 1: Provider Availability
- 0 = Bottom quartile NPIs per 1,000 beneficiaries (most scarce)
- 3 = Top quartile (most dense)

### Dimension 2: Demand Pressure (Panel Size)
- 0 = Bottom quartile avg panel size (low demand pressure)
- 3 = Top quartile (high demand pressure)

### Dimension 3: Utilization (Claims per Beneficiary)
- 0 = Bottom quartile (underutilizing)
- 3 = Top quartile (high utilization)

### Dimension 4: Payment Environment (Payment per Claim)
- 0 = Bottom quartile (low reimbursement)
- 3 = Top quartile (high reimbursement)

---

## Archetype Labels

| Archetype | Provider Avail | Demand | Utilization | Payment | Description |
|-----------|---------------|--------|-------------|---------|-------------|
| **Underserved / High Demand** | Low (0-1) | High (2-3) | Any | Any | Few providers, many patients — access crisis signal |
| **Saturated / Competitive** | High (2-3) | Low (0-1) | Any | Low | Many providers competing for limited patients |
| **Underutilizing** | Any | Any | Low (0-1) | Any | Patients enrolled but not using services — no-show / engagement problem |
| **High Intensity** | Any | Any | High (2-3) | High (2-3) | Frequent visits, high payment — complex population or strong billing |
| **Low Reimbursement Trap** | Any | High (2-3) | Any | Low (0-1) | High demand but poor payment — sustainability risk |
| **Balanced / Healthy** | Mid (1-2) | Mid (1-2) | Mid (1-2) | Mid (1-2) | No extreme flags — stable market |

> Markets may match more than one archetype. Flag primary and secondary archetypes.

---

## FL MSA Reference

Key FL MSAs for CMHC benchmarking:

| MSA Name | CBSA Code | Key Counties |
|----------|-----------|--------------|
| Miami-Fort Lauderdale-West Palm Beach | 33100 | Miami-Dade, Broward, Palm Beach |
| Tampa-St. Pete-Clearwater | 45300 | Hillsborough, Pinellas, Pasco |
| Orlando-Kissimmee-Sanford | 36740 | Orange, Osceola, Seminole |
| Jacksonville | 27260 | Duval, Clay, St. Johns |
| Cape Coral-Fort Myers | 15980 | Lee |
| North Port-Sarasota-Bradenton | 35840 | Sarasota, Manatee |
| Deltona-Daytona Beach | 19660 | Volusia |
| Pensacola-Ferry Pass-Brent | 37860 | Escambia, Santa Rosa |
| Tallahassee | 45220 | Leon, Wakulla |
| Gainesville | 23540 | Alachua |

---

## Output Format for Market Archetype Report

For each MSA / ZIP cluster:

```
Market: [Name]
Archetype: [Primary] / [Secondary if applicable]
---
Provider Density:   X NPIs per 1,000 beneficiaries  [FL pctile: XX | National pctile: XX]
Avg Panel Size:     X beneficiaries/NPI              [FL pctile: XX | National pctile: XX]
Claims per Member:  X                                [FL pctile: XX | National pctile: XX]
Payment per Claim:  $X                               [FL pctile: XX | National pctile: XX]
---
Physicians/1,000:   X (HRSA)
---
Strategic Signal:   [2-3 sentence interpretation]
```
