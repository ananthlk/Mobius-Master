# AHCA Rerun Live Dashboard

**LIVE STATUS** (reloads every 30s from `docs/ahca_rerun_status.json`)

This dashboard is **integrated into the Platform dashboard** at:
`https://mobius-chat-ortabkknqa-uc.a.run.app/platform`

Select the **AHCA Rerun** tab to view:

- **Primary Metric**: Progress 0/1,160 (AHCA documents reingested)
- **Invariant Check**: No-substance chunks = 0 (must stay green)
- **Tables Captured**: 431 tables, 16,365 rows (excised from corpus)
- **Pages with Breadcrumb**: 429 (from table excision)
- **Published Chunks**: 1.69M indexed
- **Blockers**: Eval BEFORE baseline, Fact Store adjudication, Trace verification
- **Gate Verdicts**: Before-snapshot diffs (161 retirements at risk)
- **Lifecycle Status**: Active/Retired/Shelved/Unset

**Read from:** `docs/ahca_rerun_status.json` (machine-generated, never hand-edit)  
**Regenerate with:** `python3 scripts/ahca_sprint_status.py --write`  
**Last generated:** 2026-08-20 13:30:04 UTC (9 min ago)

## Freshness Indicator

- ✓ Green (< 5 min): Trust current status
- ⚠️ Orange (5–30 min): Status aging, may be stale
- 🔴 Red (> 30 min): Rerun may have completed; regenerate JSON

## Key Signals

| Signal | What it means | Action |
|--------|---------------|--------|
| Progress 0/1160 | AHCA rerun not started yet | Blocked on Eval BEFORE |
| Invariant "NOT CHECKED" | Deep scan required (`--deep` flag) | Optional; junk may exist |
| Gate diff pending | 161 retirements have stale proofs | Fact Store will adjudicate after run |
| Blockers: BLOCKED | ⛔ Eval BEFORE baseline missing | Start cannot proceed without it |

## For Platform Architects

This tab shows the **operational view** of a single high-stakes rerun. Data is:
- **Read from JSON only** (never live queries—API saturated during run)
- **Regenerated via Python script** every N minutes
- **Timestamp always visible** so staleness is obvious

This pattern is reusable for other sprints: platform sprint board + live operational dashboard in one place.
