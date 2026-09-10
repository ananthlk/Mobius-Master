# Credentialing & Roster tools — source of truth for the manifest

**Owner:** Provider Roster & Credentialing skill · **For:** Tool Manifest seat · **Date:** 2026-09-10
**Status:** content, not shape. Compile `find_text` / `exec_text` from this; this page stays canonical.

Rules honoured: **no tool names another tool**; **no cross-tool priority language**. Boundaries below
are stated as each tool's own limits.

---

## ⚠️ Read this before compiling anything

Two things worth knowing before encoding these tools into the manifest.

### (a) `signal="no_sources"` is emitted on every success — a chat-side defect, not a tool defect

The Tool Manifest seat flagged `mcp_adapter.py:281`: the **success** branch of the MCP adapter
sets `signal="no_sources"`, identical to the failure branch. This means every call to every tool
here shows zero-source attribution in the assistant envelope, regardless of whether the tool
returned real BigQuery data.

**This is not a data quality problem in these tools.** The tools return real pre-verified BigQuery
results. The signal is a constant that accidentally passes as a negative. Do not rank these tools
low on the basis of the `no_sources` rate — that metric is broken at the collector, not at the tool.

### (b) The roster DB uses hyphens; BQ slugs use underscores — both are correct

`check_provider_credentialing` normalizes `org_slug` (hyphen→underscore) on entry. Every other tool
that accepts `org_slug` expects the underscore form from `search_orgs`. A user who copies a slug
from the credentialing UI (which shows hyphenated slugs) into a market tool will get a miss.
The fix is for the loop to always resolve slugs through `search_orgs` before passing them to tools
that query BigQuery — those tools do not normalize.

---

## Coverage — dimension 6, written bluntly

**Scope: Florida Medicaid behavioral health, fee-for-service claims, 2019–2024.**

| | |
|---|---|
| Total orgs in universe | ~334 COMMUNITY_BH (incl. CMHCs/FQHCs/SUDs); ~188 KB of geo-located records |
| Total market (2024) | $402.4M paid · 1.386M benes |
| HCPCS codes covered | ~58 BH procedure codes with claim history |
| Rate benchmark coverage | P25/P50/P75/P90 available per code per peer group |
| Time range | 2019–2024 inclusive; monthly granularity for trend tools |
| Geography | Florida only; no other states |
| Program | Medicaid FFS only — no Medicare, no commercial, no Medicaid managed care encounter data |
| Credentialing data | FL Medicaid PML enrollment + NPPES validation + compliance rules, for orgs that have run a credentialing job |

**What is not covered:** Medicare, commercial claims, managed care encounter data (AHCA 820 files), any state outside FL, any year before 2019 or after 2024. Credentialing profiles are only available for orgs that have been loaded into the `provider_roster` table — a missing profile means the org hasn't been onboarded, not that they lack credentialing.

---

# Market Tools

---

# 1. `get_market_timeseries`

## FINDING

**1. Real phrasings (8–15):**
- how has the fl medicaid bh market changed over time
- show me market trends from 2019 to 2024
- how much has the market grown
- what's the year over year trend for medicaid bh
- how did bhpf's share change between 2019 and 2024
- what share does bhpf hold vs new entrants
- did cmhcs lose share over the past five years
- how is the lookalike segment growing
- market growth medicaid behavioral health florida
- bh spend trends since 2019
- show me the entity breakdown over time
- how did fqhc share change
- total beneficiaries by year medicaid bh

**2. The decision being made:** *How has the landscape shifted, and who is winning or losing share?* This is trend orientation — a person building a narrative or deciding whether displacement is real.

**3. Entity vocabulary:** market trend, market growth, market share, share shift, year over year, 2019, 2020, 2021, 2022, 2023, 2024, BHPF, FBHA, CMHC, lookalike, FQHC, community provider, new entrant, share, percent of market, benes, beneficiaries, total paid, total claims, entity type, coalition, displacement.

**4. What the user has in hand:** a question about trajectory, not a specific org or code. May have a specific entity in mind (BHPF vs lookalike).

**5. What this tool does NOT answer (own boundary):** it does not give individual org profiles, rate data, or credentialing status. It does not explain why share shifted — only that it did.

**6. Coverage:** 2019–2024 FL Medicaid FFS. Entity breakdowns: bhpf, fbha, lookalike, fqhc, community. No sub-year granularity — annual only.

## EXECUTING

**7. Arguments**
| arg | required | meaning | how to obtain if missing |
|---|---|---|---|
| `year_from` | no | Start year string (default `'2019'`) | leave blank |
| `year_to` | no | End year string (default `'2024'`) | leave blank |
| `entity` | no | Filter to one entity: `'bhpf'`, `'fbha'`, `'lookalike'`, `'fqhc'`, `'community'` | leave blank for all entities |

**8. Sequencing:** none — callable directly.

**9. Return shape:** `years` dict keyed by year → `{total_benes, total_claims, total_paid, entities: {entity_name: {benes, claims, paid, share}}}`.

**10. Failure modes**
| condition | returns | what the loop should do |
|---|---|---|
| BQ unavailable | exception string | report as unavailable |
| entity filter typo | silently returns full data (filter applied client-side, no error) | if result is unexpected, re-read return shape |

**11. Cost/latency:** one BQ query, typically 1–3 seconds.

---

# 2. `get_market_decomposition`

## FINDING

**1. Real phrasings:**
- what service lines make up the fl medicaid bh market
- how is revenue split across outpatient vs residential
- which service line has the most bhpf revenue
- how does cmhc service mix compare to the overall market
- what share of bh revenue is from case management
- how much of total claims are crisis services
- outpatient vs crisis vs residential breakdown
- how does the service line mix differ by org type
- which service lines are growing fastest
- community bh revenue breakdown by line of service

**2. The decision being made:** *What does the market look like by service line, and where is my org type strongest or weakest?*

**3. Entity vocabulary:** service line, outpatient, residential, crisis, case management, ACT, assertive community treatment, supported housing, detox, outpatient therapy, service mix, line of service, revenue breakdown, distribution, share, percentage.

**4. What the user has in hand:** a question about composition rather than size. May want to compare one org type to another.

**5. Does NOT answer:** individual org service mix (use `get_org_service_line_profile`), rate benchmarks, or credentialing data.

**6. Coverage:** 2024 default; 2019–2024 available. All FL Medicaid FFS BH service lines.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `period_year` | no | Year (default 2024) |
| `org_type` | no | `'CMHC'`, `'FQHC'`, `'SUD'`, `'COMMUNITY_BH'`, `'BH_SPECIALTY'` |
| `service_line` | no | Single AHCA service line label |
| `service_lines` | no | List of service lines |
| `geo` | no | `'all_fl'` (default) or `'zips'` |
| `zip_codes` | no | 5-digit ZIPs when geo=`'zips'` |
| `metric` | no | `'benes'` (default) \| `'dollars'` \| `'claims'` |

**8. Sequencing:** none.

**9. Return shape:** list of `{service_line, org_type, benes, claims, paid, share_of_total}` rows.

**10. Failure modes:** BQ error → exception string. Narrow filter with no data → empty list (not an error).

**11. Cost/latency:** 1–3 seconds BQ.

---

# 3. `get_org_type_stats`

## FINDING

**1. Real phrasings:**
- what are the aggregate kpis for cmhcs
- how many benes do bhpf members serve in total
- what's the average revenue per bene for fqhcs
- what's the typical claims per bene for lookalike orgs
- how does bhpf's total revenue compare to community providers
- what's the overall bh market efficiency for cmhcs
- average bpc across community behavioral health
- how did cmhc kpis change year over year
- total paid to fqhcs in 2024

**2. The decision being made:** *How is this org type performing as a cohort on core KPIs?*

**3. Entity vocabulary:** aggregate, cohort, KPI, revenue per bene, RPB, claims per bene, CPB, benes per clinician, BPC, paid per claim, PPC, market share, total paid, total benes, total claims, year over year, delta, change.

**4. In hand:** a specific org type and year.

**5. Does NOT answer:** individual org KPIs (use `get_org_profile`), rate benchmarks.

**6. Coverage:** entity types: bhpf, fbha, lookalike, fqhc, community. 2019–2024.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `org_type` | **yes** | One of `'bhpf'`, `'fbha'`, `'lookalike'`, `'fqhc'`, `'community'` |
| `period_year` | no | Year (default 2024) |
| `service_line` | no | Optional service line filter |

**8. Sequencing:** none.

**9. Return shape:** `{org_type, period_year, benes, claims, paid, rpb, cpb, bpc, ppc, market_share, yoy_benes, yoy_paid}`.

**10. Failure modes:** unknown org_type → empty or error string.

**11. Cost/latency:** 1–2 seconds.

---

# 4. `get_market_size`

## FINDING

**1. Real phrasings (priority tool):**
- how big is the fl medicaid bh market
- what is total medicaid bh spend in florida
- how many beneficiaries get behavioral health services in florida
- what's the total paid for fl medicaid bh in 2024
- what's the overall market size
- how many bh claims are filed per year
- market size for behavioral health in florida
- total medicaid spend on mental health and substance use
- what is bhpf's addressable market
- how large is the medicaid bh space
- florida medicaid behavioral health total revenue
- how much does medicaid pay for behavioral health annually
- how big is the market for new entrants to displace

**2. The decision being made:** *What is the absolute scale of this market, and how does it segment?* This is the first number anyone building a pitch or making a sizing decision needs.

**3. Entity vocabulary:** market size, market, total paid, total revenue, total spend, total benes, total beneficiaries, total claims, how big, how many, volume, spend, addressable market, TAM.

**4. What the user has in hand:** a question about magnitude. May want to filter to an org type, service line, or geography.

**5. Does NOT answer:** individual org revenue (use `get_org_profile`), rate benchmarks, or market share breakdown by entity (use `get_market_timeseries`).

**6. Coverage:** 2024 default (2019–2024 available). All FL Medicaid FFS BH. Verified from BigQuery financial dataset.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `period_year` | no | Single year (default 2024). Omit for all-year view. |
| `period_start` | no | Range start `'YYYY-MM'` |
| `period_end` | no | Range end `'YYYY-MM'` |
| `org_type` | no | Filter by org type: `'CMHC'`, `'FQHC'`, `'SUD'`, `'COMMUNITY_BH'` |
| `geo` | no | `'all_fl'` (default) or `'zips'` |
| `zip_codes` | no | List of ZIP codes when geo=`'zips'` |
| `service_line` | no | Filter to a single AHCA service line |
| `metric` | no | `'benes'` \| `'dollars'` \| `'claims'` |

**8. Sequencing:** none — callable as the first tool in a market-sizing turn.

**9. Return shape:** `{total_benes, total_claims, total_paid, avg_rpb, avg_cpb, org_count, period}`.

**10. Failure modes**
| condition | returns | what the loop should do |
|---|---|---|
| BQ error | exception string | report as unavailable |
| zip_codes passed without geo='zips' | zip filter silently ignored | always pair geo='zips' with zip_codes |
| empty result | `{}` or `{total_benes: 0}` | confirm the filter combination is valid with `get_valid_filters` |

**11. Cost/latency:** 1–3 seconds BQ.

---

# 5. `get_entrant_analysis`

## FINDING

**1. Real phrasings:**
- which codes did new entrants take from cmhcs
- how much share did cmhcs lose to fqhcs
- what service lines are most contested
- new entrant displacement analysis
- how many new providers entered the fl medicaid bh market
- which service lines are new entrants penetrating
- show me where lookalike orgs are gaining
- how much revenue has shifted to non-bhpf providers
- entrant competition by service line
- which codes are under the most competitive pressure

**2. The decision being made:** *Is displacement real, and which codes/service lines are most at risk?*

**3. Entity vocabulary:** new entrant, entrant, displacement, competition, competitive pressure, share erosion, CMHC loss, lookalike, FQHC, SUD, community, codes taken, service lines, market penetration, non-coalition, panel capture.

**4. In hand:** a question about competitive dynamics, possibly a specific service line or entrant type.

**5. Does NOT answer:** individual org leakage (use `get_org_leakage`), rate benchmarks.

**6. Coverage:** 2024 default; 2019–2024 available. All FL Medicaid FFS entrant types.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `period_year` | no | Analysis year (default 2024) |
| `org_type` | no | Entrant type: `'FQHC'`, `'SUD'`, `'COMMUNITY_BH'`, `'BH_SPECIALTY'` |
| `service_line` | no | Focus on a specific service line |
| `hcpcs_codes` | no | Focus on specific codes |
| `market_tier` | no | `'sparse'`, `'moderate'`, `'dense'` |
| `size_band` | no | `'small'`, `'medium'`, `'large'` |

**8. Sequencing:** none.

**9. Return shape:** list of entrant records with codes captured, service lines penetrated, CMHC share erosion metrics.

**10. Failure modes:** BQ error → exception string. Narrow filters → empty list.

**11. Cost/latency:** 2–4 seconds BQ.

---

# Org Profile Tools

---

# 6. `get_top_orgs`

## FINDING

**1. Real phrasings:**
- which org serves the most beneficiaries
- top cmhcs by revenue
- largest behavioral health orgs in florida
- who has the most claims
- which bhpf member has the most benes
- top fbha orgs by revenue
- largest community bh providers
- rank the orgs by panel size
- who are the biggest players in fl medicaid bh
- top 10 cmhcs in florida

**2. The decision being made:** *Who is the biggest player, and how does size rank across the field?*

**3. Entity vocabulary:** top, largest, biggest, most, highest, rank, ranking, who leads, who has the most, beneficiaries served, panel size, revenue, revenue ranking, claims, BHPF, FBHA, CMHC, community, new entrant.

**4. In hand:** a desire to rank or compare orgs by a single metric.

**5. Does NOT answer:** detailed profiles for specific orgs (use `get_org_profile`), rate data, credentialing.

**6. Coverage:** 2024 default. All FL Medicaid BH orgs in the financial dataset.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `metric` | no | `'benes'` (default) \| `'revenue'` \| `'claims'` |
| `period_year` | no | Year (default 2024) |
| `org_type` | no | `'CMHC'`, `'FQHC'`, `'SUD'`, `'COMMUNITY_BH'`, `'BH_SPECIALTY'` |
| `market_tier` | no | `'dense'`, `'moderate'`, `'sparse'` |
| `cmhc_tier` | no | **Critical for BHPF/FBHA questions**: `'tier1_bhpf'`, `'tier2_fbha'`, `'tier3_lookalike'`. Always set when the question mentions BHPF or FBHA — without it, all FL orgs are ranked, most of which are not coalition members. |
| `limit` | no | Max results (default 20) |

**8. Sequencing:** none. Returns `org_slug` values that are valid inputs for org-specific tools.

**9. Return shape:** formatted ranked list (text) with `org_name`, `bene_count`/`revenue`/`claim_count`, `org_type`, `market_tier`, `rpb`, `growth_trajectory`, `rate_position`.

**10. Failure modes:** BQ error → exception string. Missing `cmhc_tier` on BHPF/FBHA questions returns all FL orgs, not coalition members — a silent misfire.

**11. Cost/latency:** 1–2 seconds BQ.

---

# 7. `get_org_profile`

## FINDING

**1. Real phrasings:**
- what are david lawrence center's financials
- give me aspire health partners' profile
- how many benes does henderson mental health serve
- what's the total revenue for centerstone
- what service lines is dlc strong in
- how is aspire growing year over year
- what's the revenue per bene for henderson
- pull up the profile for community partnership of south florida
- how big is south florida cares
- give me the full profile for the org

**2. The decision being made:** *What are this org's key financial and clinical metrics?*

**3. Entity vocabulary:** profile, financials, panel size, bene count, total revenue, total paid, total claims, revenue per bene, claims per bene, growth, trajectory, service line mix, rate position, org metrics, org profile, org data.

**4. In hand:** an org name (possibly approximate). Needs to be resolved to an org_slug first.

**5. Does NOT answer:** peer comparisons (use `get_org_benchmark`), rate benchmarks, credentialing status.

**6. Coverage:** 2024 default. Any org in the FL Medicaid BH financial dataset. Falls back to LIKE match if exact slug misses.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `org_slug` | **yes** | Use the exact `org_slug` from `search_orgs`. Partial slugs also work — `'aspire'` matches `'aspire_health_partners'`. |
| `period_year` | no | Year (default 2024) |
| `service_line` | no | Restrict to a service line |
| `metric` | no | `'benes'` (default) \| `'dollars'` \| `'claims'` |

**8. Sequencing:** resolve slug via search first when given a display name.

**9. Return shape:** `{org_slug, org_name, org_type, market_tier, size_band, panel_size, total_claims, total_paid, rpb, cpb, growth_trajectory, rate_position, service_line_mix[]}`.

**10. Failure modes:** unknown slug → empty list (not an error). Fallback LIKE match may return multiple orgs — use first result (sorted by `total_paid DESC`).

**11. Cost/latency:** 1–2 seconds BQ; fallback adds one more.

---

# 8. `get_org_service_line_profile`

## FINDING

**1. Real phrasings:**
- what is henderson's residential revenue share
- how does dlc's outpatient bpc compare to peers
- what service lines does aspire bill
- show me the service line breakdown for community partnership
- what share of centerstone's revenue is from crisis services
- how does the org's service mix stack up
- what are the per service line kpis for this org
- where is this cmhc concentrated

**2. The decision being made:** *Which service lines drive this org's volume and revenue, and how do they compare to peer CMHCs at the service-line level?*

**3. Entity vocabulary:** service line, outpatient, residential, crisis, case management, ACT, per service line, breakdown, share, KPIs at the service line level, peer average, service mix.

**4. In hand:** an org slug. May have a service line of interest.

**5. Does NOT answer:** market-wide service line breakdown (`get_market_decomposition`), rate gap analysis (`get_org_rate_gap`).

**6. Coverage:** 2024 default. Per-service-line metrics with peer CMHC comparisons.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `org_slug` | **yes** | Org identifier |
| `period_year` | no | Year (default 2024) |
| `service_lines` | no | List of service lines to include |
| `metric` | no | `'benes'` \| `'dollars'` \| `'claims'` |
| `stat` | no | Benchmark stat: `'p25'` \| `'p50'` (default) \| `'p75'` \| `'mean'` |

**8. Sequencing:** resolve slug first.

**9. Return shape:** list of `{service_line, benes, claims, paid, share, peer_avg_*}` per service line.

**10. Failure modes:** missing slug → empty list.

**11. Cost/latency:** 1–3 seconds BQ.

---

# 9. `get_org_benchmark`

## FINDING

**1. Real phrasings:**
- how does aspire compare to peers
- is henderson above or below median on revenue per bene
- where does dlc sit on the peer benchmark
- how does this org's bpc compare to similar cmhcs
- is this org an outlier on claims per bene
- peer comparison for community partnership
- show me where this org stands on all kpis
- above or below p50 for payment per claim
- how efficient is this org vs peers

**2. The decision being made:** *Is this org performing above or below its peer cohort on core KPIs?*

**3. Entity vocabulary:** peer, peer group, benchmark, compare, comparison, median, P50, P75, P25, percentile, above, below, outlier, revenue per bene, claims per bene, payment per claim, panel per clinician, position, positioning.

**4. In hand:** an org slug. Optionally a year and peer group.

**5. Does NOT answer:** rate benchmarks (dollar rates per claim by code), service-line breakdown, credentialing.

**6. Coverage:** 2024 default. Peer groups: type_only (same org type) or all_fl. KPIs: RPB, BPC, CPB, PPC, panel_per_clinician.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `org_slug` | **yes** | Org identifier |
| `period_year` | no | Year (default 2024) |
| `peer_group` | no | `'all_fl'` \| `'type_only'` (default `'all_fl'`) |
| `service_line` | no | Optional service line restriction |
| `stat` | no | `'p25'` \| `'p50'` (default) \| `'p75'` |

**8. Sequencing:** resolve slug first.

**9. Return shape:** `{text, extra: {section_format: 'stats', items: [{label, value, note}]}}`. Each item shows org value vs P25/P50/P75 with a band label (below_p25 / p25_p50 / p50_p75 / above_p75).

**10. Failure modes:** org not in financial dataset → no KPIs → all bands null.

**11. Cost/latency:** 2–3 seconds BQ (two queries: org KPIs + distribution).

---

# 10. `get_org_leakage`

## FINDING

**1. Real phrasings:**
- how much of bhpf's panel is also going to new entrants
- which orgs are losing patients to fqhcs
- what is the patient leakage rate for henderson
- how many shared patients does dlc have with community providers
- are cmhcs losing benes to lookalikes
- shared panel analysis for aspire
- how much overlap does this org have with competitor providers
- patient leakage analysis

**2. The decision being made:** *How much of this org's panel is being seen concurrently by competitors — a proxy for erosion?*

**3. Entity vocabulary:** leakage, patient leakage, shared patients, shared panel, overlap, benes seen by competitors, losing patients, dual users, concurrent care, benes going to new entrants.

**4. In hand:** an org slug.

**5. Does NOT answer:** market-wide displacement trends (`get_entrant_analysis`), rate data, credentialing.

**6. Coverage:** 2024 default. Requires that the org has billing NPI data in `billing_npi_profiles`. Orgs without active billing NPI records in the dataset will return an error.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `org_slug` | **yes** | Org identifier |
| `period_year` | no | Year (default 2024) |
| `service_line` | no | Optional service line focus |

**8. Sequencing:** confirm org has billing data first if unsure — a missing-org error comes back as a clear message.

**9. Return shape:** leakage metrics including shared bene count, percent overlap, competing provider breakdown.

**10. Failure modes:** org not in billing_npi_profiles → `{"error": "No FL Medicaid billing records found for '…'"}` — a clear recoverable signal.

**11. Cost/latency:** 2 BQ queries, 2–5 seconds.

---

# 11. `get_service_line_opportunity`

## FINDING

**1. Real phrasings:**
- where is bhpf leaving money on the table
- what service line should cmhcs invest in next
- what's the revenue opportunity for outpatient expansion
- where is the biggest untapped revenue for this org
- size the opportunity for residential services
- what service lines are underserved relative to panel
- revenue gap by service line
- opportunity sizing for case management

**2. The decision being made:** *Where is the gap between current revenue and potential revenue, by service line?*

**3. Entity vocabulary:** opportunity, opportunity sizing, revenue gap, untapped, leaving money on the table, expansion, underserved, potential revenue, market penetration, gap, upside.

**4. In hand:** optional org slug or org type, plus a target service line or set of codes.

**5. Does NOT answer:** realized rate benchmarks, credentialing, individual bene records.

**6. Coverage:** 2024 default. Opportunity is estimated from panel size × benchmark rates vs. current billing.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `org_slug` | no | If set, sizes opportunity for a specific org |
| `org_type` | no | If set, sizes for an org type cohort |
| `period_year` | no | Year (default 2024) |
| `service_line` | no | Focus on a specific service line |
| `hcpcs_codes` | no | Specific codes to size |
| `market_tier` | no | Market density filter |

**8. Sequencing:** for org-specific analysis, resolve slug first.

**9. Return shape:** list of `{service_line, current_revenue, potential_revenue, gap, gap_per_bene, codes_with_gap[]}`.

**10. Failure modes:** BQ error → exception string. Estimates are modeled, not actuals — present as opportunity sizing, not a revenue guarantee.

**11. Cost/latency:** 2–4 seconds BQ.

---

# Rate / Benchmark Tools

---

# 12. `get_rate_benchmarks`

## FINDING

**1. Real phrasings (priority tool):**
- what is the market rate for h2019
- what's the p50 for cmhc outpatient
- what does the market pay for act h0040
- what is the benchmark rate for supported housing
- how does the bhpf rate compare by market density
- what's the typical payment per claim for t1017
- rate benchmarks for behavioral health codes
- p25 p50 p75 for h2019
- what are orgs actually collecting per claim
- what's the market payment for this procedure code
- show me rate benchmarks across org types
- how does rate vary by market tier for h2019
- what is the p75 for large cmhcs on this code
- rate distribution across florida medicaid bh

**2. The decision being made:** *What is the market actually paying for this procedure, and where should this org's rate land?* This is the core rate intelligence decision — a person setting rates, negotiating with payors, or evaluating whether an org is under- or over-collecting.

**3. Entity vocabulary:** rate, rate benchmark, payment per claim, PPC, market rate, P25, P50, P75, P90, percentile, median, actual collected, realized rate, HCPCS, procedure code, H2019, H0040, T1017, H2014, H0020, ACT, outpatient therapy, residential, crisis, case management, peer group, org type, size band, market tier, CMHC, FQHC, dense market, sparse market.

**4. What the user has in hand:** one or more HCPCS codes. May also have an org type, size, or market tier they want to compare against.

**5. What this tool does NOT answer (own boundary):** it does not give published fee schedule rates (what the state *says* it will pay) — that is `get_published_rates`. It does not give per-org rate data. It does not give rate trends over time — that is `get_rate_trends`. It does not give a gap vs. a specific org's rate — that is `get_org_rate_gap`.

**6. Coverage:** pre-computed from all FL Medicaid FFS claims 2019–2024. ~58 BH HCPCS codes. Multiple peer group cuts: all_fl, by_org_type, by_size, by_market. P25/P50/P75/P90 available. **These are realized rates (what was actually collected), not theoretical maximums.**

## EXECUTING

**7. Arguments**
| arg | required | meaning | how to obtain if missing |
|---|---|---|---|
| `hcpcs_codes` | one of | List of codes: `['H2019', 'T1017']` | from the conversation or service line |
| `hcpcs_code` | one of | Single code shorthand | same |
| `org_type` | no | Filter to org type cut | leave blank for all-FL |
| `size_band` | no | `'small'`, `'medium'`, `'large'` | leave blank |
| `market_tier` | no | `'sparse'`, `'moderate'`, `'dense'` | leave blank |
| `peer_group` | no | Explicit peer group: `'all_fl'`, `'by_org_type'`, `'by_size'`, `'by_market'` | leave blank — default is all FL |
| `dimension_value` | no | Specific value for peer_group: `'CMHC'` for `by_org_type` | only needed with peer_group |

**8. Sequencing:** none — callable directly when codes are known. If no code is known, identify service lines first.

**9. Return shape:** single-code → `{text, extra: {section_format: 'bars', bars: [{label, p25, p50, p75, p90}]}}`. Multi-code → `{text, extra: {section_format: 'table', table_headers, table_rows}}`. Dollar values are pre-formatted as `'$12.34'`.

**10. Failure modes**
| condition | returns | what the loop should do |
|---|---|---|
| code not in dataset | empty list | say data is not available for that code; confirm the code is a FL Medicaid BH code |
| BQ error | exception string | report as unavailable |
| no filter, returns all cuts | large dataset | narrow by peer_group if result is overwhelming |

**11. Cost/latency:** 1–3 seconds BQ. Cheap to call per-code.

---

# 13. `get_published_rates`

## FINDING

**1. Real phrasings:**
- what is the medicaid fee schedule rate for h2019
- what does fl medicaid pay for act
- what is the official rate for t1017
- show me the published rate vs what orgs actually collect
- what is the state rate for this code
- fee schedule for behavioral health codes
- ahca published rates for bh procedures
- what's the maximum medicaid payment for this service
- official fee schedule rates for cmhcs

**2. The decision being made:** *What does the state say it will pay — the ceiling rate?* This is the regulatory reference number, not the realized market rate.

**3. Entity vocabulary:** published rate, fee schedule, AHCA, state rate, maximum payment, ceiling rate, official rate, FL Medicaid rate, Rule 59G-4.002, procedure rate, modifier, unit, facility rate, modifier count, category.

**4. In hand:** one or more HCPCS codes, or a desire to see the full BH fee schedule.

**5. Does NOT answer:** what providers actually collect (use `get_rate_benchmarks`), rate trends, org-specific rates.

**6. Coverage:** 58 BH HCPCS codes from the FL AHCA fee schedule. Includes modifier counts, rate high/low where applicable, facility rate.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `hcpcs_codes` | no | List of codes. Returns all 58 codes if omitted. |
| `hcpcs_code` | no | Single code shorthand. |

**8. Sequencing:** none.

**9. Return shape:** list of `{hcpcs_code, category, description, published_rate, published_rate_high, facility_rate, unit, time_unit, source, modifier_count, modifiers_json}`.

**10. Failure modes:** code not in fee schedule → empty list (not an error).

**11. Cost/latency:** 1–2 seconds BQ.

---

# 14. `get_rate_trends`

## FINDING

**1. Real phrasings:**
- how have rates moved over time
- are cmhc rates converging or diverging
- what is the rate trajectory for h0040
- how has the market rate for h2019 changed since 2019
- show me monthly rate trends for outpatient therapy
- are rates declining for this code
- rate trajectory for act services
- how has the p50 for h0040 moved

**2. The decision being made:** *Is the market rate moving, and in which direction?*

**3. Entity vocabulary:** trend, rate trend, trajectory, monthly, year over year, converging, diverging, moving, declining, rising, 2019 to 2024, time series, historical rate, rate history.

**4. In hand:** one or more HCPCS codes and a time period of interest.

**5. Does NOT answer:** current snapshot benchmarks (`get_rate_benchmarks`), published rates, individual org rate gaps.

**6. Coverage:** 2019–2024, monthly granularity. All FL Medicaid FFS BH codes.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `hcpcs_codes` | no | List of codes |
| `hcpcs_code` | no | Single code |
| `org_type` | no | Filter to org type |
| `size_band` | no | Filter to size band |
| `market_tier` | no | Filter to market density |
| `peer_group` | no | `'all_fl'` (default) \| `'by_org_type'` \| `'by_size'` \| `'by_market'` |
| `period_start` | no | `'YYYY-MM'` start |
| `period_end` | no | `'YYYY-MM'` end |

**8. Sequencing:** none.

**9. Return shape:** list of `{hcpcs_code, peer_group, year_month, p50_ppc, claim_count}` rows sorted by month.

**10. Failure modes:** BQ error → exception string.

**11. Cost/latency:** 1–3 seconds BQ.

---

# 15. `get_org_rate_gap`

## FINDING

**1. Real phrasings:**
- how does aspire's rates compare to the market
- is henderson collecting above or below market rates
- where is this org leaving money on the table by service line
- rate gap for david lawrence center
- is dlc under-market on outpatient therapy
- how does this org's payment per claim compare to peers
- show me the rate index for centerstone
- where is the biggest rate gap for this org

**2. The decision being made:** *Is this org collecting above or below the market benchmark per claim, by service line?*

**3. Entity vocabulary:** rate gap, rate index, payment per claim, PPC, peer p50, above market, below market, rate comparison, gap per claim, service line rate, org vs market.

**4. In hand:** an org slug. Optionally a service line focus.

**5. Does NOT answer:** market-wide rate benchmarks (`get_rate_benchmarks`), published fee schedule rates, credentialing.

**6. Coverage:** 2024 default. Per service line. Optional MSA-level cut (pass `include_msa_cut=True`).

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `org_slug` | **yes** | Org identifier |
| `period_year` | no | Year (default 2024) |
| `hcpcs_codes` | no | Limit to specific codes |
| `service_line` | no | Filter to a service line |
| `stat` | no | `'p50'` (default) \| `'p75'` |
| `include_msa_cut` | no | When True, appends MSA-level gap table in `extra.sections[]` |

**8. Sequencing:** resolve slug first.

**9. Return shape:** `{text, extra: {section_format: 'table', table_headers, table_rows}}`. Columns: service line, org PPC, peer P50, rate index, gap/claim. Rate index > 1 = above market; < 1 = below market.

**10. Failure modes:** BQ error on MSA cut → logged warning, MSA section omitted from result.

**11. Cost/latency:** 1–2 seconds BQ; +1 second if include_msa_cut.

---

# 16. `get_benchmark_dimensions`

## FINDING

**1. Real phrasings:**
- what's the range of revenue per bene across cmhcs
- what is the p75 bpc for large orgs
- show me the kpi distribution for all fl orgs
- what's the spread on payment per claim
- what's the typical range of efficiency metrics for cmhcs
- distribution of claims per bene by size band
- show me peer group distributions for all kpis
- what's the interquartile range for bpc

**2. The decision being made:** *What does the full distribution of this metric look like across a peer cohort?*

**3. Entity vocabulary:** distribution, spread, range, IQR, P25, P50, P75, mean, KPI distribution, peer distribution, all FL, by org type, by size, by market, RPB, BPC, CPB, PPC.

**4. In hand:** a desire to understand the shape of the distribution, not just one org's position.

**5. Does NOT answer:** individual org positioning (use `get_org_benchmark`), rate benchmarks (per-code).

**6. Coverage:** 2024 default. All peer group dimensions. KPIs: RPB, BPC, CPB, PPC, panel_per_clinician.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `period_year` | no | Year (default 2024) |
| `org_type` | no | Filter to org type |
| `service_line` | no | Filter to service line |
| `peer_group` | no | `'all_fl'` (default) \| `'by_org_type'` \| `'by_size'` \| `'by_market'` |
| `stat` | no | `'p25'` \| `'p50'` (default) \| `'p75'` \| `'mean'` |

**8. Sequencing:** none.

**9. Return shape:** list of `{metric, p25, p50, p75, mean, n, peer_group}`.

**10. Failure modes:** BQ error → exception string.

**11. Cost/latency:** 1–3 seconds BQ.

---

# Story / Fact-Pack Tools

---

# 17. `get_fact_pack`

## FINDING

**1. Real phrasings:**
- what are the headline numbers for the story deck
- what is bhpf's market share
- how much did the market grow
- give me the cover stats for the story
- what are the key metrics for the presentation
- what are the bhpf summary numbers
- market share, total paid, and growth for bhpf
- fact pack for the narrative

**2. The decision being made:** *What are the official numbers used in the story deck narrative?* This is the single source of truth for presentation metrics — not raw BQ queries.

**3. Entity vocabulary:** fact pack, story deck, presentation, headline, cover, summary, market share, total paid, growth, entity KPIs, narrative, bhpf, fbha, all_cmhc.

**4. In hand:** a request for the story metrics, an entity name.

**5. Does NOT answer:** granular analysis not in the story deck, rate benchmarks, credentialing.

**6. Coverage:** 2019–2024, all entities. The fact-pack is pre-computed; it will not reflect filters applied at query time.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `entity` | no | `'bhpf'`, `'fbha'`, `'all_cmhc'` (default `'bhpf'`) |
| `scope` | no | `'entity'` \| `'org'` |
| `scope_value` | no | Org name or slug when scope=`'org'` |

**8. Sequencing:** none.

**9. Return shape:** full fact-pack dict with market totals, entity KPIs, rate positions, service-line mix, churn benchmarks, cover statistics.

**10. Failure modes:** BQ error → exception string.

**11. Cost/latency:** 1–5 seconds BQ (multiple sub-queries).

---

# 18. `get_churn_benchmark`

## FINDING

**1. Real phrasings:**
- how much clinician turnover does bhpf have vs peers
- is cmhc workforce stable
- what is the churn rate for fbha orgs
- how many clinicians left bhpf year over year
- workforce stability signal for cmhcs
- clinician retention benchmark
- what fraction of clinicians stay year to year

**2. The decision being made:** *How stable is the workforce for this entity relative to peers?*

**3. Entity vocabulary:** churn, turnover, retention, clinician retention, workforce stability, clinicians who left, NPI churn, billed year N but not year N+1, year over year, bhpf, fbha, lookalike, community.

**4. In hand:** an entity and a base year.

**5. Does NOT answer:** credentialing status of individual clinicians, rate data, org financials.

**6. Coverage:** 2019–2024 (churn is year-over-year, so 2019 base = 2019→2020 cohort). Entities: bhpf, fbha, lookalike, community.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `period_year` | no | Base cohort year string (default `'2019'`) |
| `entity` | no | `'bhpf'`, `'fbha'`, `'lookalike'`, `'community'` (default `'bhpf'`) |

**8. Sequencing:** none.

**9. Return shape:** churn fraction, retained NPI count, total NPI count for the cohort year.

**10. Failure modes:** BQ error → exception string.

**11. Cost/latency:** 1–2 seconds.

---

# 19. `get_service_mix`

## FINDING

**1. Real phrasings:**
- what percent of bhpf revenue is outpatient
- are cmhcs over-indexed on residential
- service line revenue mix for bhpf
- how does bhpf's service mix compare to the market
- what share of fbha revenue is from case management
- how is bhpf's revenue distributed across service lines
- is bhpf concentrated in any particular service line

**2. The decision being made:** *What is this entity's revenue composition by service line, and how does it compare to the market?*

**3. Entity vocabulary:** service mix, revenue mix, distribution, outpatient, residential, crisis, case management, percent of revenue, over-indexed, concentration.

**4. In hand:** an entity name and year.

**5. Does NOT answer:** individual org service line data (`get_org_service_line_profile`), rate data.

**6. Coverage:** 2024 default. All FL Medicaid BH service lines. Entity-level (not org-level) data.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `period_year` | no | Year string (default `'2024'`) |
| `entity` | no | `'bhpf'`, `'fbha'`, `'lookalike'`, `'fqhc'`, `'community'` (default `'bhpf'`) |

**8. Sequencing:** none.

**9. Return shape:** list of `{service_line, entity_share, market_share, entity_paid, market_paid}`.

**10. Failure modes:** BQ error → exception string.

**11. Cost/latency:** 1–2 seconds.

---

# 20. `get_market_retention`

## FINDING

**1. Real phrasings:**
- how sticky is bhpf's patient base
- are cmhcs losing patients to fqhcs
- what fraction of bhpf benes return each year
- how well does bhpf retain its panel year over year
- beneficiary retention for cmhcs
- how much panel churn do bhpf members have
- panel retention benchmarks

**2. The decision being made:** *How well does this entity retain its panel year-over-year vs. competitors?*

**3. Entity vocabulary:** retention, panel retention, patient retention, bene retention, sticky, panel churn, switching, returning benes, year over year, fraction retained, bhpf, fbha, lookalike, community.

**4. In hand:** an entity and year.

**5. Does NOT answer:** individual org leakage (`get_org_leakage`), clinician churn (`get_churn_benchmark`), rate data.

**6. Coverage:** 2024 default. FL Medicaid BH. Note: the `entity` parameter is accepted but the current implementation returns all-categories data — filter by entity client-side if needed.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `period_year` | no | Year (default 2024) |
| `entity` | no | `'bhpf'`, `'fbha'`, `'lookalike'` (default `'bhpf'`) — note: entity filtering is done client-side; call returns all categories |
| `service_line` | no | Optional service line focus |

**8. Sequencing:** none.

**9. Return shape:** retention rates by category including fraction retained, fraction switched, bene counts.

**10. Failure modes:** BQ error → exception string.

**11. Cost/latency:** 2–3 seconds BQ.

---

# Org Universe Tools

---

# 21. `get_org_universe`

## FINDING

**1. Real phrasings:**
- list all bhpf member orgs
- give me the full list of fbha members
- what orgs are in the bhpf coalition
- list all cmhcs in florida
- how many bhpf orgs are there
- enumerate the orgs in tier 1
- show me all large cmhcs
- what are the dense market cmhcs
- give me a list of all behavioral health orgs
- how many lookalike orgs are there

**2. The decision being made:** *What orgs exist in this category, and what are their key identifiers?* This is a directory lookup, not an analysis.

**3. Entity vocabulary:** list, enumerate, all orgs, full list, member list, bhpf, fbha, tier1, tier2, lookalike, large, medium, small, dense market, sparse market, cmhc coalition, directory.

**4. In hand:** a coalition or tier specification. May want to filter by size or market.

**5. Does NOT answer:** financial profiles (`get_org_profile`), rate data, credentialing status, market size.

**6. Coverage:** ~188KB of geo-located org metadata from the org universe dataset. All FL Medicaid BH org types.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `entity` | no | `'bhpf'`, `'fbha'`, `'lookalike'`, `'fqhc'` (default: all) |
| `tier` | no | Size tier: `'large'`, `'medium'`, `'small'` |
| `market_tier` | no | `'sparse'`, `'moderate'`, `'dense'` |

**8. Sequencing:** none. Returns `org_slug` values usable in org-specific tools.

**9. Return shape:** `{orgs: [{org_name, org_slug, org_type, entity, market_tier, cmhc_tier, npi_count, is_active}], summary: {total_orgs, by_entity, by_market_tier}}`.

**10. Failure modes:** BQ error → exception string. `tier` filter is applied client-side after query.

**11. Cost/latency:** 1–3 seconds BQ (full universe query).

---

# 22. `get_market_share_timeseries`

## FINDING

**1. Real phrasings:**
- show me henderson's market share trend
- how did bhpf's collective share change
- which cmhc grew fastest between 2019 and 2024
- what is aspire's market share over time
- how has fbha's share moved
- market share growth by org
- year over year share for david lawrence center
- who gained the most share since 2019

**2. The decision being made:** *How has this org's or entity's share of the FL Medicaid BH market changed over time?*

**3. Entity vocabulary:** market share, share trend, share over time, share history, grew, lost share, gained share, year by year, 2019 to 2024, share trajectory, org share.

**4. In hand:** an org slug or entity name, plus a time window.

**5. Does NOT answer:** absolute financial totals (`get_market_size`), rate data, credentialing.

**6. Coverage:** 2019–2024, annual. Per-org and per-entity cuts.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `org_slug` | no | Filter to a single org |
| `entity` | no | Filter to entity type (`'bhpf'`, `'fbha'`, `'lookalike'`) |
| `year_from` | no | Start year (default `'2019'`) |
| `year_to` | no | End year (default `'2024'`) |
| `service_line` | no | Restrict to a service line's share |

**8. Sequencing:** resolve slug via search first when given a display name.

**9. Return shape:** `{rows: [{year, org_name, entity, benes, claims, paid, share_of_fl_market}], summary}`.

**10. Failure modes:** BQ error → exception string. Unknown slug → empty rows.

**11. Cost/latency:** 1–3 seconds BQ.

---

# Lookup / Reference Tools

---

# 23. `get_valid_filters`

## FINDING

**1. Real phrasings:**
- what service lines are valid filter values
- what org types exist in the data
- what are the valid values for market tier
- what msa codes are available
- before i filter can you show me what's valid
- what service line labels should i use
- how do i spell outpatient therapy in the filter
- what are the valid market tiers

**2. The decision being made:** *What exact values should I pass to filter parameters?* This is a guard call — validates before a query with a filter that might be invalid.

**3. Entity vocabulary:** valid values, filter values, what are the options, org type list, service line list, market tier list, MSA list, valid filter, accepted values.

**4. In hand:** uncertainty about which exact string values are accepted in filters.

**5. Does NOT answer:** data counts or analysis — only the set of valid filter values for a given year.

**6. Coverage:** reflects values actually present in the data for the requested year. 2024 default.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `period_year` | no | Year to pull filter values for (default `'2024'`) |

**8. Sequencing:** call before any tool that uses `service_line`, `org_type`, `market_tier`, or MSA filters when those values are uncertain.

**9. Return shape:** `{service_lines: [...], org_types: [...], market_tiers: [...], msas: [...]}`.

**10. Failure modes:** BQ error → exception string.

**11. Cost/latency:** sub-second (lightweight distinct query).

---

# 24. `get_service_line_code_map`

## FINDING

**1. Real phrasings:**
- what codes belong to the outpatient therapy service line
- which hcpcs codes are in case management
- what service line is h2019 in
- look up what service line h0040 belongs to
- what codes are covered in the act service line
- show me the full code universe
- which codes map to residential services
- give me the ahca categories for bh codes
- what is h2019
- what does t1017 map to

**2. The decision being made:** *What is the service line or AHCA category for a given code, or which codes belong to a given service line?*

**3. Entity vocabulary:** HCPCS code, procedure code, H2019, H0040, T1017, H2014, service line, service line mapping, AHCA category, code to service line, code universe, code reference, what is this code, code description, primary metric.

**4. In hand:** either a code (want to know its service line) or a service line name (want its codes).

**5. Does NOT answer:** rate data for those codes, credentialing, org-specific billing patterns.

**6. Coverage:** ~58 FL Medicaid BH HCPCS codes. Static mapping from `_SERVICE_LINE_MAP` + live BQ `fl_bh_code_reference` table.

## EXECUTING

**7. Arguments:** none — returns the complete map.

**8. Sequencing:** call before filtering by `service_line` or `hcpcs_code` when uncertain which codes belong where.

**9. Return shape:** `{service_lines: {sl_key: {display_name, codes[]}}, code_index: {hcpcs_code: {service_line, ahca_category, description, primary_metric}}, ahca_categories: {cat: [codes]}, service_line_keys: [...], ahca_category_keys: [...]}`.

**10. Failure modes:** BQ unavailable → returns static map only (AHCA category enrichment missing, code_index may be partial).

**11. Cost/latency:** sub-second; static map loaded once at module import.

---

# 25. `search_orgs`

## FINDING

**1. Real phrasings (priority tool):**
- find aspire health partners
- look up david lawrence center
- what is the org slug for henderson mental health
- search for community partnership of south florida
- find the org named centerstone
- what orgs match south florida behavioral
- look up an org called dlc
- find all cmhcs named community
- which org is this — aspire behavioral
- what slug do i use for henderson

**2. The decision being made:** *Which org is the user referring to, and what is its canonical identifier?* This is the name-resolution step that all other org-specific tools depend on.

**3. Entity vocabulary:** org name, find, look up, search, who is, which org, slug, org slug, name, full name, partial name, abbreviation, display name, canonical name.

**4. What the user has in hand:** a display name — possibly approximate, abbreviated, or spelled differently from the database. They do NOT have the slug.

**5. What this tool does NOT answer (own boundary):** it does not give financial profiles, rate data, or credentialing status. It returns identification metadata only: org_slug, org_type, market_tier, bene_count, billing_npi_count, billing_npis.

**6. Coverage:** all orgs in the `org_entities` table joined with `billing_npi_profiles` and `org_profile_v2`. Fuzzy LIKE match on `norm_org_name`. Sorted by bene_count DESC so the most active org appears first when multiple orgs match a partial name.

## EXECUTING

**7. Arguments**
| arg | required | meaning | note |
|---|---|---|---|
| `name` | **yes** | Full or partial org name | pass as much as known — `'aspire health partners'` is better than `'aspire'` |
| `entity` | no | Reserved — currently ignored | do not pass |
| `org_type` | no | `'CMHC'`, `'FQHC'`, `'SUD'`, `'COMMUNITY_BH'`, `'BH_SPECIALTY'` | narrows results |
| `limit` | no | Max results (default 20) | |

**8. Sequencing:** call this first, before passing `org_slug` to any other market or credentialing tool. The slug format from this tool's output (`norm_org_name` derived) uses underscores; the credentialing handler normalizes hyphens to underscores, so either form works there.

**9. Return shape:** list of `{org_entity_id, org_name, norm_org_name, org_slug, org_type, market_tier, billing_npi_count, billing_npis, bene_count, revenue}` sorted by `bene_count DESC`.

**10. Failure modes**
| condition | returns | what the loop should do |
|---|---|---|
| no match | empty list | retry with a shorter substring; ask the user for more of the org name |
| multiple matches | list sorted by bene_count | use the first result (most active); confirm with the user if ambiguous |
| BQ error | exception string | report as unavailable |

**11. Cost/latency:** 1–2 seconds BQ.

---

# 26. `lookup_npi`

## FINDING

**1. Real phrasings:**
- look up npi 1234567890
- what org is this npi
- give me the identity for billing npi 1003058965
- what taxonomy is on file for npi 1003058965
- find the org for this npi number
- npi lookup for david lawrence center
- what legal name is registered for this npi
- who is billing under npi 1234567890

**2. The decision being made:** *What identity and taxonomy information is registered for this NPI, and which org does it belong to?*

**3. Entity vocabulary:** NPI, billing NPI, 10-digit NPI, NPI number, legal name, taxonomy, provider type, city, state, zip, org identity, NPPES, billing organization, who bills as.

**4. In hand:** an NPI number, an org name, or an org slug. At least one of the three.

**5. Does NOT answer:** FL Medicaid PML enrollment or credentialing status — for that, use `check_provider_credentialing`. Does not return claim history or financial data.

**6. Coverage:** `billing_npi_profiles` (FL Medicaid FFS billing records) joined with `org_entities` and the public NPPES `npi_optimized` table. Returns up to 50 rows.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `npi` | one of | 10-digit NPI string |
| `org_slug` | one of | Org slug — converted to LIKE pattern against norm_org_name |
| `org_name` | one of | Display name — used as LIKE pattern |

Pass at least one. All three may be passed to narrow.

**8. Sequencing:** none — callable directly with an NPI. For org name lookup, prefer `search_orgs` first since that returns full financial metadata; use this tool when the query is explicitly about NPI identity or NPPES registration.

**9. Return shape:** list of `{billing_npi, norm_org_name, org_state, org_zip5, billing_taxonomy_code, org_name, org_type, market_tier, org_taxonomy_code, legal_name, city, state, taxonomy_1, taxonomy_2}`.

**10. Failure modes:** no match → empty list. Org-name LIKE on a broad name returns up to 50 rows — narrow with NPI if ambiguous. BQ error → exception string.

**11. Cost/latency:** 1–2 seconds BQ.

---

# 27. `get_msa_map`

## FINDING

**1. Real phrasings:**
- what msa is miami in
- what is the zip3 code for tampa
- map orlando to its msa
- which msa codes are available in the data
- how many orgs are in the miami msa
- find valid msa codes before i filter
- what markets are sparse vs dense
- how do i find the msa for a city in florida
- which zip3 prefix maps to jacksonville

**2. The decision being made:** *What MSA code should I use for a geography filter, and how many orgs are in each market?*

**3. Entity vocabulary:** MSA, market area, zip3, zip prefix, market code, city to MSA, Miami, Tampa, Orlando, Jacksonville, Tallahassee, Fort Lauderdale, West Palm Beach, Fort Myers, Gainesville, Sarasota, market density, org count per market.

**4. In hand:** a city name or a desire to understand market geography before filtering.

**5. Does NOT answer:** financial data for those MSAs, rate benchmarks, credentialing.

**6. Coverage:** all FL Medicaid BH zip codes present in the org dataset for the requested year. Includes a hardcoded FL city→zip3 reference mapping (Miami=331, Tampa=336, Orlando=328, Jacksonville=322, etc.).

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `period_year` | no | Year (default `'2024'`) |

**8. Sequencing:** call before any filter that uses a `msa` or zip3-level geography to validate the code.

**9. Return shape:** `{msas: [{msa, market_tier, org_count, cmhc_count, coalition_count}], fl_city_to_msa: {city: msa_code}, note: "..."}`. Falls back to static `fl_city_to_msa` map on BQ error.

**10. Failure modes:** BQ error → returns static city map only, `msas` key absent or empty.

**11. Cost/latency:** 1–2 seconds BQ.

---

# Credentialing Tools

---

# 28. `check_provider_credentialing`

## FINDING

**1. Real phrasings (priority tool):**
- get me a credentialing report for david lawrence center
- what is the credentialing status for npi 1234567890
- show me the credentialing profile for henderson
- is dr. johnson enrolled in medicaid
- is this provider on the pml
- how is aspire's panel doing with credentialing
- how many providers need credentialing attention at dlc
- are there nppes or pml errors for this org
- which providers need action at this org
- show me the panel readiness for centerstone
- credentialing status for this npi at david lawrence center
- any compliance flags for this provider

**2. The decision being made:** Two different decisions depending on whether NPI is supplied:
- **(NPI supplied):** Is this specific provider clean, or do they need attention? What exactly is wrong?
- **(NPI omitted):** Is this org's panel in good shape, or are there providers I need to deal with?

**3. Entity vocabulary:** credentialing, credentialing status, credentialing profile, credentialing report, NPPES, NPPES status, NPPES validation, PML, PML enrollment, FL Medicaid enrollment, enrolled, not enrolled, terminated, revalidation, compliance, compliance flag, compliance check, readiness, clean, flagged, action required, review needed, error, warning, violation, flag, NPI, panel readiness, panel summary, org panel.

**4. What the user has in hand:**
- Provider-level: an org slug AND an NPI (10-digit).
- Org summary: an org slug only.

**5. What this tool does NOT answer (own boundary):** it does not answer credentialing POLICY questions — PA rules, payer manual requirements, appeal procedures. It does not return billing history or financial data. It does not search for a provider by name — a name alone requires a prior lookup to obtain the NPI.

**6. Coverage:** providers in the `provider_roster` table for orgs that have run a credentialing job. A missing profile (`"No credentialing profile found"`) means the org hasn't been onboarded, not that the provider lacks credentials. PML enrollment is FL Medicaid only. NPPES is the national registry.

## EXECUTING

**7. Arguments**
| arg | required | meaning | how to obtain if missing |
|---|---|---|---|
| `org_slug` | **yes** | Org slug — hyphens normalized to underscores internally. Do NOT guess from a display name; resolve via search first. | search by org name first |
| `npi` | no | 10-digit NPI for provider-level profile. Omit for org summary. | if you have a name but not an NPI, look up the clinician by name first |

**8. Sequencing:**
- Have a display name but no org_slug? Resolve the org slug first.
- Have a clinician name but no NPI? Search clinicians by name first, then call this with org_slug + NPI.
- Have both org_slug and NPI? Call this directly.

**9. Return shape:**

*Provider-level:*
```
{
  "text": "## Credentialing Profile — {name}...",  // markdown
  "extra": {
    "credentialing_card": {
      "npi", "provider_name", "org", "status" (enrolled|flagged|pending),
      "flags": [{"text", "severity": error|warning}],
      "action_url"  // link to roster UI
    }
  }
}
```
Markdown sections: Readiness / Status / Specialty / License / NPPES / FL Medicaid (PML) / Compliance / Recent changes.

*Org summary:*
```
{
  "text": "## Panel Credentialing Summary — {org}...",
  "extra": {
    "credentialing_card": {
      "org", "provider_name", "status", "flags", "action_url", "org_summary": true
    }
  }
}
```
Org summary includes: total active providers, clean/review_needed/action_required/incomplete counts, validation coverage timestamps (NPPES/PML/compliance), and a list of providers needing attention with issue details.

**10. Failure modes**
| condition | returns | what the loop should do |
|---|---|---|
| NPI not found for org | plain string: `"No credentialing profile found for NPI … in org '…'. Confirm the org_slug is correct…"` | confirm the slug and that a credentialing run has been completed for this org |
| Org not onboarded | `"No active providers found for org '…'"` | tell the user this org has not been added to the roster |
| Handler exception | exception string | report as unavailable |

**11. Cost/latency:** database read (PostgreSQL), sub-second. Org summary includes additional compliance query, ~1 second total.

---

# 29. `search_clinician_by_name`

## FINDING

**1. Real phrasings:**
- find jane smith at david lawrence center
- what is dr. edwards' npi
- is there a rodriguez at henderson
- look up a counselor named johnson at aspire
- find a clinician named chen
- npi for maria garcia at community partnership
- find all clinicians named williams at dlc
- who is the johnson at aspire

**2. The decision being made:** *Which clinician matches this name, and what is their NPI so I can look up their credentialing profile?* This is a name-to-NPI resolution step.

**3. Entity vocabulary:** clinician, provider, counselor, therapist, LCSW, LMHC, MD, name, first name, last name, full name, NPI, find, search, who is, is there a, look up.

**4. What the user has in hand:** a partial or full name. May also have an org. Does NOT have the NPI.

**5. What this tool does NOT answer (own boundary):** it does not return the full credentialing profile — it returns roster status, specialty, and NPI. The credentialing detail (NPPES validation, PML enrollment, compliance flags) requires a follow-up call.

**6. Coverage:** all active clinicians in the `provider_roster` table across all onboarded orgs. Partial last-name matches work. Name formats accepted: `'Smith'`, `'Jane Smith'`, `'Smith, Jane'`. Inactive/terminated roster entries are excluded.

## EXECUTING

**7. Arguments**
| arg | required | meaning |
|---|---|---|
| `name` | **yes** | First name, last name, or full name. Partial matches work. `'Smith'` matches all Smiths. |
| `org_slug` | no | Restrict to one org (e.g. `'david-lawrence-center'`). Omit to search all orgs. |

**8. Sequencing:**
- If you have the name and need the NPI before calling `check_provider_credentialing`, call this first.
- If you have an org name but not the slug, resolve the org slug via org search before passing `org_slug` here.
- After receiving results, call `check_provider_credentialing(org_slug, npi)` for the full credentialing profile.

**9. Return shape:**
```
{
  "text": "## Clinician Search — 'name'\nFound N matches:\n- {display_name}, {credential} (NPI `{npi}`) — {specialty}  | Org: `{org_slug}` | Status: {status}",
  "results": [{"npi", "display_name", "org_slug", "specialty", "credential", "status"}]
}
```
No match: `{"text": "No active clinicians matching '…' found in the roster…", "results": []}`.

**10. Failure modes**
| condition | returns | what the loop should do |
|---|---|---|
| No match | text message with suggestions (try partial last name, remove org_slug) | suggest shorter partial name or removing org filter |
| Multiple matches | all matching rows | present options; ask user which they mean |
| Handler exception | `{"error": "…"}` | report as unavailable |

**11. Cost/latency:** PostgreSQL roster query, sub-second.

---

## Answering the dimension-6 ask directly

The Tool Manifest seat asked for the coverage section to be written bluntly because it is the least inferable from outside. So:

**What these tools are:** a Florida-only, Medicaid-FFS-only, behavioral-health-only market intelligence layer on top of ~6 years of pre-verified BigQuery data. The 22 market/rate/org tools are not general-purpose healthcare databases — they answer FL Medicaid BH questions and only those. The 3 credentialing tools answer provider-credential-status questions and only for orgs that have been onboarded into the roster.

**What these tools are not:** they do not cover Medicare, commercial claims, Medicaid managed care encounter data, any state outside FL, any service category outside behavioral health, or any period outside 2019–2024. They do not write anything, file anything, or take any action. They do not interpret policy documents or produce clinical guidance.

**The coverage is real and verified.** Unlike some toolsets, the market numbers here come from an actual BigQuery dataset of FL Medicaid FFS claims. The $402.4M / 1.386M benes / 334-org figures are sourced, not synthesized. Rate benchmarks are pre-computed from real claims, not fee schedule approximations. The coverage gap is not data quality — it is scope: if someone asks about a payor outside FL Medicaid, about a service line that is not behavioral health, or about a credentialing topic that is policy rather than enrollment status, these tools correctly return nothing rather than a plausible-sounding wrong answer.
