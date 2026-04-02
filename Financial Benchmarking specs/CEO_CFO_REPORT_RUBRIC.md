# CEO/CFO Report Rubric — Financial Rate Benchmarking

## What they're asking when they open this report

1. **"Are we getting paid fairly?"** — Am I leaving money on the table vs what the market pays for the same services?
2. **"Are we losing patients?"** — Is our panel shrinking? Are patients disengaging?
3. **"Are patients showing up?"** — Are no-shows increasing? Are treatment episodes getting shorter?
4. **"Where's the revenue risk?"** — Which service lines are trending in the wrong direction?
5. **"What do I do about it?"** — Not prescriptive, but: what should I investigate first?

## Report Structure (what they expect)

### Page 1: "Why this report and how to read it"
- What data source (FL Medicaid claims, 2019–2024)
- What we measured (4 KPIs) and why each one matters to operations
- Who we compared against (peer groups) and why each one is relevant
- What the charts show (how to read them in 30 seconds)
- Key limitations in plain language (not buried in an appendix)

### Page 2: Executive Dashboard
- One badge per service line per KPI: Green/Yellow/Red
- Trend arrows: ↑ ↓ → for each
- At a glance: where are we strong, where are we exposed
- No detail — just the signal map

### Pages 3+: Service Line Deep Dives (one per service line)
- **Opening line:** What this service line is and why it matters to your revenue
- **Rate Position:** Are you at market? Badge + one sentence
- **Productivity:** Panel size trend — gaining or losing patients per clinician? Badge + one sentence
- **Utilization:** Claims per beneficiary — are patients engaging? Badge + one sentence
- **Revenue Intensity:** Revenue per patient — the combined effect. Badge + one sentence
- **Peer comparison chart** (the bullet chart across peer groups)
- **Trend chart** (2019–2024, 4 KPIs)
- **Key question:** One sentence framing what to investigate

### Final Page: Caveats & Methodology
- Per-metric caveats (what each KPI can and can't tell you)
- Data source limitations
- Peer group construction

## Badge System

Each code gets 4 badges, one per KPI:

| Badge | Static Position | Trend | Color |
|-------|----------------|-------|-------|
| **Strong** | Above P50 on most axes | Pulling ahead or stable | Green |
| **At Market** | Near P50 | Stable | Gray |
| **Watch** | Below P50 on some axes OR above but converging | Converging or mixed signals | Yellow |
| **Concern** | Below P50 on most axes | Falling behind | Red |

### Badge logic (per KPI):
```
position = org value vs CMHC peer P50 (primary comparison)
trend = trend signal vs CMHC peers

if position == WELL ABOVE and trend in (Pulling ahead, Stable): → Strong
if position in (Above, ≈ P50) and trend in (Stable, Pulling ahead): → At Market
if position == WELL ABOVE and trend == Converging: → Watch (was strong, losing edge)
if position in (Below, ≈ P50) and trend == Converging: → Watch (improving but not there)
if position in (Below, WELL BELOW) and trend == Falling behind: → Concern
if position == WELL BELOW and any trend: → Concern
```

### Special flags:
- **Anomaly** — WELL ABOVE on $/claim but ≈ P50 on claims/bene → investigate billing structure
- **Volume caution** — fewer than 100 claims → sample too small for confident benchmarking
- **Market collapse** — if ALL orgs in the peer group show declining claims/bene → systemic issue, not org-specific

## Scoring the Report

### Must-haves (fail without these):
- [ ] Every number traceable to the data
- [ ] Every KPI explained in operational terms (what it means for the business)
- [ ] Every finding framed as a question, not a conclusion
- [ ] Caveats stated where the data has limitations (per-claim not per-unit, modifier rollup, etc.)
- [ ] Badge dashboard that lets a CEO scan in 30 seconds

### Should-haves:
- [ ] Revenue impact quantification where possible ("this rate gap represents $X annually")
- [ ] COVID context for 2020-2021 trend anomalies
- [ ] Comparison to published fee schedule where applicable
- [ ] Clinician mix context (why psychiatry-heavy orgs have different rate profiles)

### Nice-to-haves:
- [ ] Actionable investigation checklist per flagged code
- [ ] Comparable org anonymized case studies ("Organization A faced a similar pattern and found...")
- [ ] Forward-looking: if current trends continue, projected position in 12 months

## Language Standards

| Instead of... | Say... |
|---|---|
| "Payment per claim is $49.69" | "Your average payment per case management claim is $49.69" |
| "WELL BELOW P50" | "Below the market median" |
| "Diverging DOWN" | "The gap between your rate and the market has been widening" |
| "bene_per_clinician" | "Patients per clinician" or "caseload" |
| "claims_per_beneficiary" | "Visits per patient" or "treatment frequency" |
| "CMHC peer group (n=34)" | "34 similar community mental health centers across Florida" |
| "Modifier rollup" | "This code can be billed in multiple ways, and the data combines all billing variations" |
| "Unit-of-service limitation" | "This measures what you're paid per claim submission, not per 15-minute session — organizations that bill longer sessions will show higher per-claim amounts" |
