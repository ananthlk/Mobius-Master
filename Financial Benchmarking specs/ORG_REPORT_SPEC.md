# Org Report Generation Spec (v9 — Rest-of-FL P75 Benchmark)

## Benchmark Philosophy

**The CMHC sector is not the benchmark. The rest of the market at P75 is the benchmark.**

The industry landscape report established that CMHCs as a sector lag the broader FL Medicaid market. Comparing an org to the CMHC P50 normalizes that underperformance. Even comparing to Rest-of-FL P75 includes the lagging CMHCs in the comparison pool.

- **The benchmark: Rest-of-FL P75.** One number. One standard. This is what best-in-class non-CMHC providers achieve in the FL Medicaid market (excluding CMHCs from the pool). P75 is not a stretch goal — it's the operating standard for transformation.
- **CMHC P50 is context only** — shown in gray to explain "here's where your lagging sector sits." Never the target, never the comparison.
- **Do NOT use Rest-of-FL P75.** Using P50 creates ambiguity ("are we targeting P50 or P75?"). There is one benchmark: P75. You're either at best-in-class or you have a gap. Show the gap.
- **Framing:** "Best-in-class providers in the FL Medicaid market collect $78.88 per T1017 claim. Your rate is $44.86 — a 43% gap to best-in-class. The CMHC sector median ($49.58) is itself 37% below best-in-class."

This must be established in the **Sector Context Bridge** (Section 2) and used consistently in every table, card, and verdict throughout. Never switch between P50 and P75.

## Pipeline Overview

```
industry_findings.json          ← sector-level findings (3 problems, key numbers)
         +
org_canonical_input.json        ← org-level data (rates, panels, trends, peers)
         +
org_report_template.html        ← HTML/CSS shell with fill markers
         +
THIS SPEC                       ← instructions for what to write, compute, and decide
         ↓
         LLM
         ↓
org_report_final.html           ← completed report
```

## Inputs

| File | Contents | LLM may modify? |
|------|----------|-----------------|
| `industry_findings.json` | Sector-level findings: $8.1M rate gap, $157M leakage, 19x ratio, market share by stage, panel gaps, burnout cycle | NO — reference only |
| `{org}_canonical_input.json` | Org-level per-code data: rate, RPB, CPB, panel, peers, trends, service lines | NO — COPY numbers exactly |
| `org_report_template.html` | HTML structure with `<!-- FILL: ... -->` markers | YES — replace markers with content |
| This spec | Instructions | NO — follow exactly |

## Report Structure

The org report is a **continuation** of the industry landscape report. The reader has already seen the sector-level findings. This report maps those findings to their organization — benchmarked against the broader market, not against the lagging CMHC sector.

### Sections (in order)

1. **Hero** — "Your Chapter in the CMHC Landscape"
2. **Sector Context Bridge** — establish that the market (Rest-of-FL P75) is the benchmark, not the CMHC sector
3. **Revenue Mix** — service line table with care-stage tags
4. **Problem 1: Lower Effective Rates** — org's position vs the MARKET
5. **Problem 2: Lack of Patient Engagement** — org's intake-to-ongoing conversion
6. **Problem 3: Clinician Churn and Burnout** — as an OUTCOME of 1 and 2
7. **Putting It Together** — three verdict cards (one per problem)
8. **Investigation Priorities** — top 3-4 actionable questions
9. **Methodology** — data source, peer groups, limitations

### Section Details

---

### 1. Hero

**Fixed elements:**
- Title: "Your Chapter in the CMHC Landscape"
- Subtitle: "The sector landscape identified three problems facing Florida's CMHCs. Here's where your organization sits within each."
- Context paragraph referencing $8.1M, 19x, $157M from `industry_findings.json`

**Fill elements:**
- 4 stat cards: Total Revenue, Total Claims, Active Service Lines, Classification
- Source: `org_canonical_input.json` → `total_revenue`, `total_claims`, count of `service_line_breakdown`, `org_types[0]`

**Card type:** `.stat-card` (blue number, gray label, centered)

---

### 2. Sector Context Bridge

**Card type:** `.sector-ref` (blue-tinted box)

**This section must establish TWO things:**

a) The three sector-level problems (reference industry report)
b) **The benchmark is the market, not the sector.** The CMHC sector itself underperforms on rates by $8.1M. Comparing against the CMHC median just tells you where you rank among underperformers. Throughout this report, we benchmark against the FL Medicaid market — Rest-of-FL P75 is the floor, All FL P75 is the target.

**Template language:**
"Florida's 86 CMHCs collectively face three structural challenges... The industry report showed the CMHC sector lags the broader market on rates, productivity, and retention. **In this report, we don't benchmark you against the lagging sector — we benchmark you against the market.** All FL Medicaid P50 is the floor. P75 is the target. Where the CMHC sector median falls below the market, we show it for context — but it is not the standard."

---

### 3. Revenue Mix

**Table columns:** Service Line | Revenue | Share | Stage | Codes

**Stage classification logic:**
For each service line in `org_canonical_input.service_line_breakdown`, assign a stage badge:
- **Intake** (white badge): codes in `industry_findings.three_segment_classification.intake.codes`
- **High-Acuity** (yellow badge): codes in `industry_findings.three_segment_classification.high_acuity.codes`
- **Ongoing** (green badge): codes in `industry_findings.three_segment_classification.ongoing.codes`
- If a service line spans multiple stages, use the stage of the majority revenue code.

**Card type:** Standard `<table>` + `<blockquote>` for data scope caveat

---

### 4. Problem 1: Lower Effective Rates

**Structure:**

a) **Sector reference box** (`.sector-ref`):
   - Pull from `industry_findings.three_problems.problem_1_rates`
   - Include per-stage RPB comparison and total gap
   - **Key addition:** "The CMHC sector collects less per claim than the market on most codes. Matching the CMHC median means matching underperformance. The benchmark below is Rest-of-FL P75 — what the broader market collects."

b) **Rate table:**
   - Columns: Code | Service | Your Rate | Best-in-Class (P75) | CMHC P50 (gray) | Gap | Trend
   - **Best-in-Class = Rest-of-FL P75.** One benchmark. One column. No P50.
   - CMHC P50 shown in small gray text for context ("your sector sits here")
   - `Gap` = ((org - rest_p75) / rest_p75 * 100), green if above P75, red if below
   - For each code:
     - `Your Rate` = `payment_per_claim`
     - `Best-in-Class` = `industry_findings.rest_of_fl_benchmarks.{code}.rest_p75_ppc`
     - `CMHC P50` = `industry_findings.rest_of_fl_benchmarks.{code}.cmhc_p50_ppc`
     - `Trend` = `trend_arrow` + `trend_label`

c) **Strength and gap cards** (`.card` with colored top border):
   ALL THRESHOLDS MEASURED AGAINST REST-OF-FL P75:
   - **Green card** for codes where org rate is AT or ABOVE P75 (best-in-class)
   - **Red card** for codes where org rate is 20%+ below P75
   - **Yellow card** for codes within 20% of P75 (within striking distance)
   - Each card: 1 paragraph positioning org vs best-in-class, note where CMHC sector sits, 1 "Question:"

**Decision logic for cards:**
```
for each code:
  org_vs_p75 = (org_rate - rest_p75) / rest_p75

  if org_vs_p75 >= 0:
    → green strength card ("At or above best-in-class")
  elif org_vs_p75 >= -0.20:
    → yellow card ("Within striking distance of best-in-class")
  elif org_vs_p75 < -0.20:
    → red gap card ("Significant gap to best-in-class")
```

d) **Verdict box** (`.insight-box`):
   - WRITE 2-3 sentences: How many codes are above/below market P50? What is the total rate gap vs the market? Is the org beating the market on any codes, or uniformly below?

---

### 5. Problem 2: Lack of Patient Engagement

**Structure:**

a) **Sector reference box** (`.sector-ref`):
   - Pull from `industry_findings.three_problems.problem_2_engagement`
   - Include 23.6% → 5.0% share drop and $157M leakage

b) **RPB cards** (`.grid-3`, three cards):
   Pick the three most important codes by revenue. For each:
   - Card title: service name
   - Big number: org's `revenue_per_bene`
   - Subtitle: **"Market P50: {All FL peer RPB}"** (was CMHC P50 in v8)
   - Percentage gap vs market, colored green/red
   - Footer: code + beneficiary count

   **Card border color logic (vs Rest-of-FL P75 RPB):**
   - Green if org RPB at or above best-in-class P75
   - Yellow if within 20% of best-in-class
   - Red if 20%+ below best-in-class

c) **Engagement math paragraph:**
   - WRITE: Explain the org's RPB on the largest code, decomposing into rate + visit frequency
   - Compare each component to Rest-of-FL P75 (not CMHC P50)

d) **Care continuum mix** (`.grid-2`):
   - Left card: table showing % of revenue by stage (intake/high-acuity/ongoing)
   - Right card: WRITE 2-3 sentences comparing org's mix to the sector pattern

e) **Beneficiary pipeline table:**
   - Columns: Stage | Code | Unique Benes | Revenue | RPB | Market P50 RPB | Signal
   - Signal: compare RPB to Rest-of-FL P75 RPB

f) **Verdict box** (`.insight-box`)

---

### 6. Problem 3: Clinician Churn and Burnout

**Framing:** This section is explicitly labeled as an **OUTCOME** of Problems 1 and 2.

**Structure:**

a) **Sector reference box** (`.sector-ref`)

b) **Panel size table:**
   - Columns: Code | Service | Your Panel | Market P50 | CMHC P50 | vs Market | Clinicians | Signal
   - **Market P50 is the PRIMARY comparison** = `peers["All FL Medicaid Orgs"].p50_bpc`
   - CMHC P50 shown for context in gray
   - `vs Market` = percentage difference vs Rest-of-FL P75

   **Signal badge logic (vs Rest-of-FL P75 panels):**
   ```
   if org_panel > all_fl_p50 * 1.25:
     → badge-yellow "High load" (or badge-red "Extreme" if > 2.0x)
   elif org_panel < all_fl_p50 * 0.75:
     → badge-red "Bottleneck?"
   elif org_panel > all_fl_p50 * 0.90:
     → badge-white "At market"
   else:
     → badge-white "Below market"
   ```

c) **Two insight cards** (`.grid-2`)
d) **Burnout connection table**
e) **Verdict box** (`.insight-box`)

---

### 7. Putting It Together

**Three verdict cards** (`.grid-3`):

**Verdict assignment logic (ALL vs Rest-of-FL P75, not CMHC P50):**

Problem 1 (Rates):
- Count codes where org rate > Rest-of-FL P75. If majority → "Favorable". If minority → "Exposed". If mixed → "Mixed".

Problem 2 (Engagement):
- Compare org's ongoing-care bene count to intake bene count. If ongoing >> intake → "Opportunity". If ongoing << intake → "Exposed". If roughly equal → "At Risk".

Problem 3 (Burnout):
- Find the service line with highest panel / Rest-of-FL P75 ratio. If > 1.5 AND clinician count ≤ 3 → "Critical". If > 1.25 → "Concentrated". If panels generally at or below market → "At Risk".

**Card border colors:** Green for Favorable/Opportunity, Yellow for Mixed/Concentrated/Manageable, Red for Exposed/At Risk/Critical.

---

### 8. Investigation Priorities

**Cards** (`.grid-2`):
- Red border: Investigate (rate >15% below Rest-of-FL P75, or anomalous)
- Yellow border: Monitor (rate within 15% of Rest-of-FL P75, or trend declining, or high panels)
- Green border: Strength (rate >10% above Rest-of-FL P75 — protect)

**Selection logic:** Pick top 3-4 by impact:
1. Any code with rate >15% below Rest-of-FL P75 → red card
2. Any declining rate trend where org is already below market → red card
3. Any panel > 1.5x Rest-of-FL P75 with ≤ 3 clinicians → yellow card (concentration risk)
4. Highest RPB strength vs All FL → green card

---

### 9. Methodology

**Add note:** "This report benchmarks against the full FL Medicaid market (Rest-of-FL P75), not against the CMHC sector median. The CMHC sector median is shown for context where relevant. The rationale: the industry landscape report demonstrated that the CMHC sector systematically underperforms the broader market. Benchmarking against the sector normalizes that underperformance."

---

## CSS Component Reference

| Component | Class | When to use |
|-----------|-------|-------------|
| Stat card (hero) | `.stat-card` | 4 cards in hero section |
| Sector reference | `.sector-ref` | Blue box at top of each problem section |
| Content card | `.card` | General-purpose container with optional `border-top: 3px solid {color}` |
| Insight verdict | `.insight-box` | Yellow-amber box at bottom of each problem section |
| Badge pill | `.badge .badge-{color}` | green/yellow/red/white for inline status labels |
| Problem header | `.problem-header` + `.problem-num` | "PROBLEM 1" numbered tag |
| 2-column grid | `.grid-2` | Side-by-side cards |
| 3-column grid | `.grid-3` | Three verdict cards or three RPB cards |

## Color Semantics

| Color | Hex | Meaning |
|-------|-----|---------|
| Green | `#22c55e` | Above market, strength, favorable |
| Yellow/Amber | `#f59e0b` | Monitor, near market, concentrated risk |
| Red | `#ef4444` | Investigate, below market, exposed |
| Blue | `#3b82f6` | Neutral data, sector reference, primary accent |
| Gray | `#94a3b8` | Context (CMHC sector position), at market |

## Rules

1. **NEVER compute numbers.** All numbers come from `org_canonical_input.json` or `industry_findings.json`. Copy exactly.
2. **NEVER diagnose causes.** Frame findings as questions ("What drives this?") not conclusions ("This is caused by").
3. **ALL FL P50 IS THE BENCHMARK.** Every rate, RPB, and panel comparison is primarily against Rest-of-FL P75. CMHC P50 is shown for context only.
4. **Establish the benchmark philosophy early.** The Sector Context Bridge must explicitly state that the market is the benchmark, not the sector.
5. **When showing CMHC P50, frame it as "your sector sits here."** Never frame it as the target or the standard of comparison.
6. **Card insertion is algorithmic against Rest-of-FL P75.** Green/yellow/red cards are triggered by distance from market P50, not sector P50.
7. **Verdicts are algorithmic against Rest-of-FL P75.**
8. **Caveats near claims.** Wherever a finding references beneficiary counts across stages, include the deduplication caveat.
9. **Data scope caveat in revenue mix section.**
10. **Problem 3 is an outcome.** Always frame it as resulting from Problems 1 and 2.
11. **Problem 4 (IT spend) is deferred.**
12. **When an org is ABOVE Rest-of-FL P75, call it out as a strength.** When above All FL P75, call it exceptional.
13. **When an org is below Rest-of-FL P75 but above CMHC P50, say:** "You're above your sector — but your sector is below the market. The gap to market P50 is your opportunity."
