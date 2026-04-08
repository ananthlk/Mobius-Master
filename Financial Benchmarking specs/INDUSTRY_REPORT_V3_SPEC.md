# Industry Report v3 — Full Spec

## Content Changes

### 1. "Rest of FL" Benchmark
- Exclude CMHCs from the All FL comparison pool
- Compare CMHCs vs non-CMHCs (everyone else in FL Medicaid)
- Requires dbt model change (new peer_group: `all_fl_excluding_cmhc`) or runtime query
- Changes every gap % in the report

### 2. Per-Unit Calculation at Point of Use
- For time-based codes, show implied units per claim: CMHC P50 ÷ published per-unit rate
- Example: T1017 CMHC P50 $49.58 ÷ $14.82/unit = ~3.3 units/claim
- Compare to rest-of-FL implied units: Rest-of-FL P50 ÷ $14.82 = ~4.2 units/claim
- This tells the CEO: "CMHCs bill shorter sessions, not just lower rates"
- Pre-compute in canonical, add to dashboard and each code section

### 3. Move Cross-Cutting Patterns to After Exec Summary
- The "front-door strength / ongoing-care gap" insight is the headline
- Currently buried after 25 code deep dives
- Promote to Section 2, push dashboard to Section 3, deep dives to Section 4

### 4. Replace Dashboard Table with Scatter Plot
- X-axis: Rate gap % (CMHC vs Rest-of-FL)
- Y-axis: Total CMHC claims volume (or revenue)
- Color: 🟢🟡🔴 by signal
- T1017 and 90837 stand out as high-volume + large gap = biggest revenue exposure
- Keep simplified table as appendix/reference

### 5. Org Scoring Rubric
- Domain-based scoring (Care/Therapy, Case Management, E&M/Med Mgmt, Assessment)
- Each domain: rate, engagement, productivity components
- Composite score per org that can be compared to sector average
- "Use this rubric to evaluate your CMHC's own positioning against the FL Medicaid sector benchmarks"

### 6. Four Actions for CMHC Leadership
- Not prescriptive but investigative prompts
- "Audit your H0031 contract rates"
- "Review T1017 units per claim"
- "Confirm H0031 modifier strategy"
- "Investigate your 99214 positioning"

## Rendering/Design Changes

### Hero Section
- Large headline: "Where does your CMHC stand in the FL Medicaid market?"
- Subtitle: "A sector-level analysis of 25 service codes across 86 Florida CMHCs"
- Three stat cards: service codes analyzed | CMHCs in the data | FL Medicaid FFS 2024

### Card-Based Layout
- Each section in a card with rounded corners, subtle border
- Dark background with lighter card surfaces
- Section headers with colored accent bars

### Scatter Plot (Primary Visualization)
- Interactive Plotly scatter: gap % vs volume
- Hover shows code name, CMHC P50, Rest-of-FL P50, gap %, claims
- Quadrant labels: "High volume + large gap = biggest exposure"

### Gap Means in Dollars
- Three hero stats: total claims, total revenue gap, average per-claim gap
- "Closing half the gap on T1017 alone would recover $X across the sector"

### Compression Corridor
- Visual showing Published → Rest-of-FL → CMHC for key codes
- Shows where the sector sits in the compression stack

### Scoring Rubric Cards
- 4 domain cards, each with 3-4 sub-scores
- Green/yellow/red dots per component
- Composite bar at bottom

### Action Items
- 4 numbered cards with icon, title, description
- Each links back to a specific finding in the report

### Footer
- "What this data can't tell you — and what to ask next"
- Honest limitations in plain language
- Methodology notes (brief)

## Data Requirements
- `hcpcs_rate_benchmarks` with new `all_fl_excluding_{org_type}` tier
- Or runtime query excluding target org_type from all_fl
- Published rates per code (already in sector_and_published_rates.json)
- Implied units calculation: P50_ppc ÷ published_per_unit_rate
- Total revenue and claims by code at CMHC and Rest-of-FL levels

## Technical Stack
- Plotly for scatter plot + compression corridor
- HTML/CSS cards (not just markdown tables)
- Same dark theme as org reports but with card layout
- Hero section with stat cards
