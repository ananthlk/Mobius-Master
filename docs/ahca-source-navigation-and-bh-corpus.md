# Navigating AHCA: Source Harvest Guide + Medicaid BH Corpus

**Owner:** Sourcing / Crawler Agent
**Status:** Verified by crawl 2026-08-17. 1,181 documents enumerated, URL sample validated 34/34 → HTTP 200.
**Consumers:** document extractor, Curation, Payor Fact Store.

---

## 0. TL;DR

| | |
|---|---|
| Total documents enumerated | **1,181** |
| Rates corpus | 979 files across 19 pages |
| Policy corpus | 202 files across 7 pages |
| **BH-relevant subset** | **77** (65 direct + 12 cross-cutting) |
| Formats | 754 PDF · 391 XLSX · 23 ZIP · 10 XLS · 3 DOC(X) |
| Auth required | none |
| Machine-readable today | 401 XLSX/XLS |

**Do not integrate AHCA PolicyBot** (`apps.ahca.myflorida.com/policybot/`). It is RAG over exactly these files, gated behind the AMA CPT non-commercial license, served over a Blazor/SignalR circuit with no API. Everything it knows is in this manifest, and the raw files are strictly more precise than its answers. Details in §5.

---

## 1. Site topology

AHCA does not expose a sitemap for these sections. The corpus is reachable only by walking three roots, and **the roots do not link to each other**. Harvesting from any single entry point silently misses whole classes.

```
ahca.myflorida.com
│
├── /provider/policy.html ─────────────────────── "AHCA Policy Library"  [POLICY ROOT]
│     ├── /medicaid/rules/adopted-rules-general-policies.html          20 docs
│     ├── /medicaid/rules/adopted-rules-service-specific-policies.html 84 docs
│     └── /medicaid/rules/adopted-rules-main-page.html                  0 docs (hub)
│
│     ⚠ NOT linked from this root — reachable only via the sidebar on
│       historical-medicaid-reimbursement-schedules.html:
│     ├── /medicaid/rules/adopted-rules.html                           54 docs
│     ├── /medicaid/rules/adopted-rules-reimbursement-policies.html    20 docs
│     ├── /medicaid/rules/adopted-rules-other-policies.html             4 docs
│     ├── /medicaid/rules/rules-in-process.html                         9 docs
│     └── /medicaid/rules/historical-medicaid-reimbursement-schedules.html
│                                                                      19 ZIPs (2006–2024)
│
├── /medicaid/rules/rule-59g-4.002-...-billing-codes.html ──────────── [FEE SCHEDULE ROOT]
│                                                                     140 docs (105 PDF / 35 XLSX)
│
├── /medicaid/cost-reimbursement.html ───────────────────────────────── [INSTITUTIONAL ROOT]
│     └── 17 sub-pages, 813 docs total:
│         nursing-home-retroactive-rate-adjustments   285
│         nursing-home-rates                          103
│         intermediate-care-facility-rates             92
│         fqhc-rhc-rates                               76
│         diagnosis-related-group-drg-...              51
│         hospice-room-board-rates                     47
│         hospice-care-services-per-diem-rates         39
│         skilled-nursing-unit-snu-rates               34
│         nursing-home-annual-reports                  29
│         sextant-electronic-cost-reporting            16
│         swing-bed-rates                              14
│         hospice-recipient-log-reporting               8
│         hospital-rates-ambulatory-surgical-centers    7
│         county-health-department-rates                6
│         nursing-home-requirements                     4
│         nursing-home-supplemental-payments            1
│         hurricane-irma-grace-period                   1
│
└── /medicaid/medicaid-finance-and-analytics/.../medicaid-actuarial-services.html
                                                                       26 docs [CAPITATION ROOT]
```

**Harvest rule:** enumerate from all four roots *plus* the historical-schedules page. That last page is the only path to `adopted-rules.html`, `-reimbursement-policies`, and `-other-policies` — **71 documents** that are invisible from `/provider/policy.html`.

All file links resolve to a flat CDN namespace:
`https://ahca.myflorida.com/content/download/<numeric_id>/file/<filename>`

The `<numeric_id>` is stable and monotonic-ish by upload date. **Treat it as the document's durable external ID** — filenames change, IDs do not.

---

## 2. Six traps that will break a naive crawler

**1. URLs contain raw spaces.** Must be percent-encoded. Unencoded, `curl` returns `000`, which reads like a Cloudflare block but is not. This failed 33 of 34 downloads on first attempt. Encode the path segment only; leave `/` unescaped.

**2. Three pages are orphaned from the policy root.** See §1. Enumerate from multiple entry points.

**3. Filenames are not identity.** Real, uncorrected typos in the live source:

| On the site | Means |
|---|---|
| `2025 CHB Fee Schedule.xlsx` | **CBH** — Community Behavioral Health |
| `2025 Community Behavoir Health Fee Schedule.pdf` | Behavio**r**al |
| `2026 Hearing Services Fee Schdule 4.6.26.xlsx` | Sche**d**ule |
| `2025 Licensed Midwife Fee Schedulen.xlsx` | Schedule |

Match on content and on the `<a>` anchor text, never on filename alone.

**4. Anchor text carries information the filename does not.** On the actuarial and cost-reimbursement pages the human-readable title holds the true period:
`Dental Final Base Rates RY 24-25 Post Update.pdf` → *"2024/2025 Dental Post-Implementation Capitation Rates (February 1, 2025 – September 30, 2025)"*.
**Persist `link_text` alongside the filename.** It is the single best date and scope signal in the corpus.

**5. Effective dates are absent or mixed-precision.** 261 of 979 rate files and 167 of 202 policy files have no date parseable from name or anchor. Those that do parse are inconsistent: `2025`, `July 1, 2026`, `10/01/2025`. This is the same month-precision problem already documented in `mobius-payor/migrations/020` ("half the corpus dates itself at month precision"). Do not write a guessed date into `documents.effective_date` — that column is now DATE-typed with a fail-closed gate, and month-precision values have nowhere to go. Extract the effective date from *inside* the document; leave NULL until then.

**6. The 23 ZIPs are containers, not documents.** 19 historical "All Fee Schedules" archives (2006–2024) plus 4 in the current rate set. Each expands to a full year of per-schedule files. Unzip before ingestion or the corpus will show 19 documents where it should show several hundred.

---

## 3. The three rate grains — do not merge them

The 979 rate files are three incompatible schemas. Loading them into one table will silently double-count.

| `rate_class` | Files | Natural key | Unit |
|---|---|---|---|
| `fee_schedule` | 140 | `(hcpcs_code, modifier, schedule, effective_date)` | $ per unit of service |
| `cost_reimbursement` | 813 | `(facility_id/provider_id, rate_component, rate_period)` | $ per diem |
| `actuarial` | 26 | `(plan, region, rate_cell, rate_year)` | $ PMPM capitation |

The modifier is load-bearing on the fee-schedule side: **`H0031` and `H0031 HA` are different rates on different schedules.** A lookup keyed on code alone is wrong. This is the same class of defect as the NPI grain mismatch already logged in the data-model review.

---

## 4. The Medicaid BH corpus — 77 documents

Delivered as `ahca_BH_sources.csv` / `.jsonl`. Two tiers, flagged by the `bh_direct` and `bh_crosscut` columns.

### Tier 1 — Direct BH (65 files)

**Named 59G rules** — the spine of BH coverage policy:

| Rule | Title |
|---|---|
| 59G-4.027 | Behavioral Health Overlay Services |
| 59G-4.028 | Behavioral Health Assessment Services |
| 59G-4.029 | Behavioral Health Medication Management Services |
| 59G-4.031 | Behavioral Health Community Support Services |
| 59G-4.052 | Behavioral Health Therapy Services |
| 59G-4.120 | Statewide Inpatient Psychiatric Program (SIPP) |
| 59G-4.127 | Florida Assertive Community Treatment (FACT) |
| 59G-4.295 | Therapeutic Group Care Services |
| 59G-4.300 | State Mental Health |
| 59G-4.310 | TCM for Children at Risk of Abuse and Neglect |
| 59G-4.370 | Behavioral Health Intervention Services |
| 59G-8.700 | Child Health Services Targeted Case Management |
| 59G-13.070 | DD iBudget Waiver Services *(adjacent — overlapping population)* |

**BH fee schedules** — both vintages, so rate deltas are computable:

```
2026 CBH Fee Schedule.pdf            2025 Community Behavoir Health Fee Schedule.pdf
2026 BHOS Fee Schedule.pdf           2025 Behavioral Health Overlay Services Fee.Schedule.pdf
2026 BA Fee Schedule.pdf             2025 Behavior Analysis Fee Schedule.pdf
2026 TCM Fee Schedule.pdf            TCM Fee Schedules - October 1, 2025.pdf
2025 CHB Fee Schedule.xlsx  ← the only BH schedule available as XLSX
Specialized Therapeutic Services - July 8, 2025.pdf
Specialized Therapeutic Services Fee Schedule January 1, 2025.pdf
2025 Community-Based Substance Abuse County Match Fee Schedule.pdf
```

⚠ **Only one BH fee schedule is XLSX** (`2025 CHB`). Every 2026 BH schedule is PDF-only. BH rate extraction is therefore a **PDF-parsing problem**, not a spreadsheet problem — unlike Practitioner/Radiology/Lab, which are XLSX. Budget accordingly; this is the single biggest cost driver in the BH cut.

**Certification and authorization forms** (~20 files) — the MHTCM certification appendices (`Appendix_B` … `Appendix_L`), the AHCA MedServ authorization forms, and the CBHA / STFC / Therapeutic Group Care self-certifications. These are what determine *whether a claim is payable*, and they are the least indexed part of the corpus.

### Tier 2 — Cross-cutting (12 files)

BH claims are governed by general rules that never mention BH:

`59G-1.001` Purpose · `59G-1.010` Definitions · `59G-1.050` General Medicaid Policy · `59G-1.058` Eligibility · `59G-1.100` Fair Hearings · plus Prior Authorization, Third Party Liability, Medicaid Forms, County of Residence, and Generally Accepted Professional Medical Standard.

**A BH corpus that excludes these will answer eligibility, PA, and appeal questions wrong.** They are not BH documents; they are the documents that decide BH cases.

### Known limits of this cut

Selection is by title and filename matching over the manifest. It is **recall-limited**: a rule whose title carries no BH signal but whose body governs BH services will be missed. Two candidates worth a manual read before freezing the set — `59G-4.002` (billing codes, contains BH codes) and the SMMC contract exhibits (not in this manifest; managed-care BH carve-ins live there). Re-run selection against extracted body text once ingestion completes, and treat the current 77 as a **starting set, not a certified one**.

---

## 5. Why PolicyBot is excluded

`https://apps.ahca.myflorida.com/policybot/` — two tabs, Policy Search and Rate Inquiry.

- **No API.** Blazor Server: `_blazor/negotiate` opens a stateful SignalR circuit shipping DOM diffs. `/swagger`, `/api`, `/api/chat`, `/api/rates`, `/health` all 404. Only integration path is headless-browser puppetry behind an active Cloudflare bot challenge.
- **AMA CPT point-and-click license** gates entry: *"personal use only… non-commercial"*, prohibits derivative works and commercial use. Hard blocker for a product surface. (HCPCS Level II is public domain; CPT Level I is not.)
- **`robots.txt`**: `Content-Signal: search=yes, ai-train=no, use=reference`; ClaudeBot / GPTBot / CCBot / Google-Extended explicitly `Disallow: /`. `ai-input` unspecified.
- **Self-declares** *"not… an official source of record"* — fails the Fact Store's `accepted ⟹ grounded` bar by construction.
- **Less precise than its own sources.** Asked for H0031 it returns *"$57.28 … effective 2026"* — year granularity — while the underlying files carry `July 8, 2025`, `October 1, 2025`. Direct ingestion beats the bot on the bot's own corpus.

**Legitimate use:** hand-driven eval oracle. Because its corpus is now known exactly, any disagreement between PolicyBot and Mobius on an AHCA question is a pure retrieval/extraction delta on our side — a clean signal, with no shared-input confound. Eval's call, low volume, human in the loop. Never a retrieval source, never an MCP tool.

---

## 6. Fact Store integration

The schema needed for this already exists. Three hooks, in order of leverage.

### 6.1 AHCA is sourced once, inherited by every MCO

`mobius-payor/migrations/015_regulatory_authority.sql` puts `regulatory_authority` on `facts.fact_template` — the predicate, not the fact. Its own header states the intent: *AHCA needs to be sourced only once per predicate, not once per MCO.*

This is the correct landing zone for the BH corpus. A ruling extracted from 59G-4.052 (BH Therapy Services) is a **state-level floor** that every FL Medicaid MCO inherits unless the plan is more generous. One extraction, N payors covered.

Concretely: extend the `regulatory_authority = 'AHCA'` predicate set beyond the five appeal predicates currently marked, to the BH coverage predicates the 13 named rules actually rule on — service limits, PA requirements, provider qualification, place-of-service restrictions. **Marking a predicate is the unit of work here, not writing facts.**

Note the direction of the constraint, taken verbatim from the AHCA disclaimer and worth encoding as a rule: plans *may* cover above the Agency's schedules and *may* pay negotiated rates, but **cannot be more restrictive than the Agency**. AHCA facts are floors on coverage, not equalities on rate.

### 6.2 Content signals are already carried

`migrations/020` added `documents.content_signals` specifically for robots.txt policy. Every AHCA document must be stamped:

```
ai-train=no use=reference search=yes
```

`ai-train=no` is binding and must propagate to any training-set extraction. `use=reference` means served answers must cite back to the source document — which the Fact Store's `source_ref` already supports.

### 6.3 Effective dates: leave NULL rather than guess

`migrations/020` converted `documents.effective_date` to DATE with a fail-closed gate, after a real defect where a `SELECT`-only gate silently NULLed malformed rows. The manifest's `effective` column is **filename-derived and mixed-precision** — it is a hint for triage, not a value to write. Writing `2025` into a DATE column manufactures `2025-01-01`, which is a false claim about when a rate took effect.

Sequence: ingest with `effective_date` NULL → extract the real date from document body → write ISO. The 19 historical ZIPs give a clean check: year is unambiguous from the archive, so per-file dates inside can be validated against it.

### 6.4 Suggested manifest → document mapping

| Manifest column | Destination |
|---|---|
| `url` | fetch URL (already encoded) |
| CDN `<numeric_id>` from URL | durable external doc ID |
| `filename` | display only — **never identity** (§2.3) |
| `link_text` | title; primary date/scope signal |
| `rule_number` | join key to 59G rule; 93 of 202 policy docs carry one |
| `rate_class` | grain selector (§3) — drives which extractor runs |
| `corpus` | `rates` \| `policy` |
| `effective` | triage hint only — do **not** write to `effective_date` |
| `source_page_url` | provenance |
| `bh_direct` / `bh_crosscut` | BH corpus tier (§4) |

---

## 7. Refresh

- **Fee schedules** turn over on rule-adoption cycles — observed effective dates cluster at Jan 1, Jul 1, Oct 1. Re-crawl 59G-4.002 monthly; both 2025 and 2026 vintages sit on the page simultaneously, so a diff on the CDN `<numeric_id>` set detects new postings without downloading.
- **Cost reimbursement** pages update continuously (nursing-home retroactive adjustments alone hold 285 files). Weekly.
- **Policy rules** change on rulemaking timelines. `rules-in-process.html` (9 docs) is the **leading indicator** — watch it to see BH policy changes before adoption.
- **Historical ZIPs** are immutable. Fetch once.

---

## 8. Open items

1. **BH set is recall-limited** (§4). Re-select against body text after extraction; the 77 is a starting set.
2. **SMMC contract exhibits are not in this manifest.** Managed-care BH carve-ins and plan-specific BH terms live there. Separate harvest, separate root.
3. **BH rate extraction is PDF-bound** — only 1 of 9 BH fee schedules is XLSX. Confirm PDF table fidelity before committing to a BH rate benchmark.
4. **Predicate marking (§6.1) is unowned.** Which BH predicates get `regulatory_authority='AHCA'` is a Fact Store decision, not a Sourcing one.
5. **`ai-train=no` enforcement path is unverified.** The column exists; whether anything reads it before building training sets has not been checked.

---

## Appendix — deliverables

| File | Rows | Contents |
|---|---|---|
| `ahca_ALL_sources.csv` / `.jsonl` | 1,181 | master manifest, both corpora |
| `ahca_rate_sources.csv` / `.jsonl` | 979 | rates only |
| `ahca_policy_sources.csv` / `.jsonl` | 202 | policy only |
| `ahca_BH_sources.csv` / `.jsonl` | 77 | BH cut, tiered |
| `ahca_ALL_urls.txt` | 1,181 | bare URL feed |

Columns: `filename, link_text, url, format, effective, rule_number, source_page, source_page_url, rate_class, corpus` (+ `bh_direct`, `bh_crosscut` in the BH cut).
