# Mobius Credentialing — Scoring Methodology

**Version:** 1.0  
**Date:** March 2026  
**Owner:** Mobius Platform  
**Status:** Active

---

## Purpose

This document defines how Mobius scores and evaluates credentialing readiness at each pipeline step. Scores are designed to be explainable to a coordinator, a compliance officer, and a health plan auditor — not just an engineer.

Each pipeline step produces its own signals and tasks. Step 11 consolidates all step-level tasks into a coordinator work packet.

---

## Core Principle

> A score measures a specific, named question. It does not claim to measure overall credentialing compliance.

Every score shown in Mobius must be accompanied by:
1. The question it answers
2. The data sources it uses
3. What it does NOT measure (explicit limitations)

---

## Step 4 — NPI Reconciliation Score

### Question answered

*"Of the providers on your roster, how many have a valid, active NPI that matches the NPPES registry, and how well does their NPPES record align with what we have on file?"*

---

### Two-phase model

NPI reconciliation is fundamentally two distinct operations. Each generates its own tasks and contributes to the composite score.

#### Phase 1 — Match
*"Can we find this person in NPPES?"*

For each roster provider, Mobius attempts to locate the best-matching NPPES record:

| Route | Trigger | Match quality |
|---|---|---|
| NPI lookup | Provider has a 10-digit NPI in the roster | Confirmed — NPI is the unique identifier |
| Name search | No NPI, or NPI not found in NPPES | Probabilistic — ranked by composite score |

The **composite match score** (0–100%) weighs:
- **Name similarity** (70%) — token-set difflib comparison, normalised for credentials (MD, LCSW, etc.)
- **Location proximity** (20%) — 1.0 if practice zip matches org zip, 0.9 for state match, 0.5 no context, 0.0 if different state
- **NPPES active status** (10%) — 1.0 Active, 0.0 Deactivated, 0.7 Unknown

Candidates are presented as **strong** (≥ 65% composite) or **weaker** (< 65%) to guide review.

#### Phase 2 — Alignment
*"Does this NPPES record agree with what our roster says?"*

Once the best-matching record is found, Mobius checks five alignment dimensions on that specific record:

| Dimension | Roster field | NPPES field | Flag values |
|---|---|---|---|
| Name | `provider_name` | `basic.name` | ok / drift / mismatch |
| Taxonomy | `specialty_uploaded` | `taxonomies[0].desc` | ok / mismatch / no_roster_data |
| State | `state` | practice address state | ok / mismatch / no_roster_data |
| Zip | *(future)* | practice address zip | ok / mismatch / no_roster_data |
| Status | *(n/a)* | NPPES status field | ok / deactivated |

Flag definitions:
- **ok** — values are consistent
- **drift** — minor differences (e.g., middle name, different credential format) — informational
- **mismatch** — substantive discrepancy — requires review
- **deactivated** — NPI is marked inactive in NPPES — **high severity**
- **no_roster_data** — roster row did not include this field — no penalty

---

### Composite score formula

```
Score = clamp(
  (Match_Coverage × 0.80 + Alignment_Health × 0.20) × 100
  − Deactivated_Penalty
  − Ghost_Penalty,
  0, 100
)
```

#### Match Coverage (Phase 1)

```
Match_Coverage = matched / total_clean
```

- `matched` — providers whose NPI was found (either uploaded or discovered via name search) and confirmed by the user
- `total_clean` — all providers after LLM junk-row cleaning, regardless of user exclusion

#### Alignment Health (Phase 2)

```
Alignment_Health = alignment_clean / matched
```

- `alignment_clean` — matched providers with no hard alignment issues (deactivated, mismatch; name drift is informational and does not penalise)
- Only computed over matched providers; providers without a match don't contribute

#### Deactivated Penalty

```
Deactivated_Penalty = deactivated_count × 2
```

Deactivated NPIs are double-penalised because they imply active credentialing against a dead record.

#### Ghost Penalty

```
Ghost_Penalty = min((external_only_count / total_clean) × 50, 30)
```

Capped at 30 points. Signals data quality risk, not confirmed fraud (NPPES addresses are often stale).

#### Score bands

| Score | Label | Color | Meaning |
|---|---|---|---|
| 85–100 | Roster in good shape | Green | High match coverage, clean alignment |
| 65–84 | Some gaps to address | Amber | Notable missing NPIs or alignment issues |
| < 65 | Credentialing risk | Red | Significant unconfirmed or misaligned providers |

---

### Known limitations and gaming prevention

**Exclusions do not improve the score.** Denominator is always `total_clean`, not the current visible list.

**NPPES staleness.** Taxonomy descriptions, addresses, and org associations in NPPES may be months out of date. Alignment mismatches are tasks to investigate, not automatic failures.

**Name drift vs. mismatch.** A coordinator using a nickname or different credential format will show as "drift" (amber `~`), not "mismatch" (red `✗`). Only substantial name differences penalise alignment health.

**Match confidence threshold.** A provider counts as "matched" only after the user confirms ("Use this NPI" or "Confirm"). Auto-suggested matches below 80% do not contribute to the score until confirmed.

---

## Step 4 — Task Signal Taxonomy

Tasks are grouped by phase. Phase 1 tasks (finding the right record) take priority over Phase 2 tasks (alignment) — you cannot fix alignment on a record you haven't found yet.

### Phase 1 — Match tasks

| Signal | Data source | Severity | Task generated |
|---|---|---|---|
| No NPI in file and no NPPES match found | NPPES search | Medium | Search NPPES or enter NPI manually |
| NPI in file but NPPES lookup returned no result | NPPES lookup | Medium | Verify NPI is correct; search by name |
| NPI in file but NPPES NPI differs from search result | NPPES lookup | Medium | Decide which NPI is correct and confirm |
| Low-confidence match (< 50%) not yet confirmed | NPPES search | Low | Review — may be wrong person |
| User rejected all NPPES matches, no NPI assigned | User action | Medium | Search NPPES manually or enter NPI directly |

### Phase 2 — Alignment tasks (only after match is found)

| Signal | Data source | Severity | Task generated |
|---|---|---|---|
| NPPES status = Deactivated | NPPES status field | **High** | Remove from active credentialing, notify provider |
| Name substantially different from NPPES | Name comparison | Medium | Verify correct provider was matched |
| Taxonomy/specialty does not align | Taxonomy comparison | Low | Update roster specialty or verify NPPES taxonomy |
| Practice state differs from roster state | Address comparison | Low | Confirm correct practice location |
| Provider in NPPES at this org's address, not on roster | NPPES org lookup | Medium | Add to roster or request NPPES address update |

### Planned signals (not yet active)

| Signal | Data source | Target step | Status |
|---|---|---|---|
| OIG / Medicaid exclusion | CMS LEIE | Step 6 | Planned |
| License expired | State licensing board APIs | Step 6 | Planned |
| Taxonomy optimisation opportunities | NPPES taxonomy + claims | Step 9 | Planned |
| PML enrollment gap | Plan PML export | Step 6 | Planned |

Planned signals appear as placeholder task types in the UI labelled *"not yet available"* so coordinators know coverage is coming.

---

## Step 11 — Master Task Consolidation (planned)

Step 11 will aggregate all tasks generated across Steps 4, 6, 7, 8, and 9 into a single coordinator work packet.

### Planned task sources

| Source step | Task category |
|---|---|
| Step 4 | NPI integrity (missing, deactivated, mismatch, ghosts) |
| Step 6 | PML enrollment gaps, OIG exclusions, license validity |
| Step 7 | Billing anomalies (inactive providers billing, taxonomy billing mismatches) |
| Step 8 | Historic billing pattern outliers |
| Step 9 | Taxonomy optimisation opportunities |

### Export formats (planned)

- CSV — one row per task, columns: provider, issue type, action required, severity, status, step source
- PDF — formatted coordinator report
- Copy as plain text — for pasting into ticketing systems (Jira, ServiceNow, etc.)

---

## Version history

| Version | Date | Change |
|---|---|---|
| 1.0 | March 2026 | Initial — Step 4 NPI Reconciliation Score defined |
| 1.1 | March 2026 | Two-phase model: Phase 1 (Match) + Phase 2 (Alignment); composite score splits 80/20; alignment dimensions: name, taxonomy, state, zip, status |
