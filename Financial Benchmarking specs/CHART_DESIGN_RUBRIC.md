# Chart Design Rubric — Financial Benchmarking Visuals

## Scoring: 1 (poor) → 5 (excellent)

### 1. Typography & Hierarchy (weight: 25%)
- [ ] **Title** — Bold, clearly largest element, sufficient padding below (≥20px from chart)
- [ ] **Subtitle** — Lighter weight/color, smaller font, explains the chart in plain English
- [ ] **Column headers** — Distinct from axis labels, clear visual separation from data
- [ ] **Axis labels** — Readable at intended size, not cramped, consistent alignment
- [ ] **Data labels** — Don't overlap marks or other labels, legible font size (≥9px)
- [ ] **Font pairing** — Max 2 font weights (bold for headers, regular for labels)

### 2. Spacing & Layout (weight: 25%)
- [ ] **Title-to-chart gap** — Minimum 24px, title should "breathe"
- [ ] **Column spacing** — Even, no overlap between adjacent KPI columns
- [ ] **Row spacing** — Enough vertical room per peer group row (≥40px)
- [ ] **Margins** — Left margin accommodates longest label without truncation
- [ ] **Right margin** — Trend signal labels fit without clipping
- [ ] **Aspect ratio** — Chart doesn't feel stretched or squished

### 3. Color & Contrast (weight: 20%)
- [ ] **Above/below encoding** — Green vs red is instantly parsed (no ambiguity)
- [ ] **P50 marker** — Visually distinct from band (different element type, not just color)
- [ ] **Band opacity** — Subtle enough to not compete with data markers
- [ ] **Text on dark bg** — Sufficient contrast ratio (≥4.5:1 for body, ≥3:1 for decorative)
- [ ] **Color consistency** — Same meaning everywhere (green = above, red = below, blue = peer)

### 4. Data Clarity (weight: 20%)
- [ ] **Hover info** — Shows all relevant values + context (n, signal, exact numbers)
- [ ] **Scale consistency** — Same KPI uses consistent scale across rows within a column
- [ ] **Outlier handling** — Extreme values (H2019 at $144 vs peers at $75) don't crush other data
- [ ] **Signal labels** — Trend direction immediately understandable (↑↓→ symbols help)
- [ ] **Peer group N** — Visible or hoverable so reader knows sample credibility

### 5. Presentation Readiness (weight: 10%)
- [ ] **Standalone clarity** — Chart tells its story without verbal explanation
- [ ] **Client-safe language** — No internal jargon, taxonomy codes, or technical labels
- [ ] **Print-friendly** — Would work in a PDF or projected slide (dark theme may need light variant)
- [ ] **Consistent with other charts** — Same visual language across radar, trend, deep dive

---

## Current v2 Assessment

| Criterion | Score | Notes |
|-----------|-------|-------|
| Title hierarchy | 2/5 | Title too close to chart, subtitle runs into column headers |
| Column headers | 2/5 | Same visual weight as title, no separation from data rows |
| Axis labels | 3/5 | Readable but cramped on left side |
| Data labels | 3/5 | Diamond markers clear, but no value annotations visible without hover |
| Spacing | 2/5 | Title/header/data zones bleed together, needs clear bands |
| Color | 4/5 | Green/red encoding works, band is subtle, good contrast |
| Data clarity | 4/5 | Hover info is excellent, scales reasonable |
| Signal labels | 4/5 | ↑↓ symbols work, right-aligned, color-coded |
| Standalone | 3/5 | Needs the subtitle to be more prominent to explain the visual |
| Client language | 5/5 | Labels are client-friendly, no jargon |

**Overall: 3.2/5 — Good data, needs typography and spacing polish**

## Priority Fixes
1. Add 30px padding between title block and chart area
2. Make column headers a distinct band (larger font, horizontal rule below)
3. Add subtle value annotations next to each diamond (showing org's actual rate)
4. Increase row height to prevent vertical crowding
5. Add a thin horizontal separator between peer group rows for scannability
