# AHCA rerun — live status

**Generated** 2026-08-20T13:30:04+00:00 · regenerate with `python3 scripts/ahca_sprint_status.py --write`

> Every number here is a live query against the database, not a tally. A hand-kept status drifts silently while still looking authoritative; this one is either current or obviously stale by its own timestamp.

## Progress

```
AHCA reingested   ░░░░░░░░░░░░░░░░░░░░  0 / 1,160   (0.0%)
```

| | count |
|---|---|
| AHCA documents in scope | 1,160 |
| **reingested (tables captured)** | **0** |
| reingested corpus-wide | 13 |
| tables captured | 431 |
| table rows captured | 16,365 |
| pages carrying a breadcrumb | 429 |
| classified today | 8 |

## Index health

| | count |
|---|---|
| published chunks | 1,682,590 |
| no-substance chunks | _not checked — run with `--deep`_ |
| corpus active | 9,716 |

## Reingest transactions

`{"created": 3}`

## Lifecycle

`{"active": 10, "retired": 161, "shelved": 441, "unset": 9265}`

## Duplicate gate — latest run

last decided: `2026-08-19 16:58:18.919304+00:00`

| verdict | pairs |
|---|---|
| ordering_unknown | 398 |
| period_series | 370 |
| duplicate | 336 |
| product_variant | 78 |
| near_duplicate | 10 |
| near_identical_review | 10 |
| product_unknown | 2 |

## Chunking jobs, last 12h

`{"completed": 6, "processing": 1}`

---

**Scope + owners:** `docs/AHCA_RERUN_SPRINT.md` · **machine-readable:** `docs/ahca_rerun_status.json`
