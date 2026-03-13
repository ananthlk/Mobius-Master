# Dev Retrieval: Before vs After Cutoffs

Comparison of 9 dev questions with **cutpoints** applied (BM25 normalized ≥ 0.5, Vector similarity ≥ 0.896).

- **Before:** `dev_retrieval_report_before_cutoffs.md` (no cutoffs)
- **After:** `dev_retrieval_report.md` (with cutoffs)

---

## Summary

| Question | expect_in_manual | Vector BEFORE (top sim) | Vector AFTER | BM25 paragraphs BEFORE→AFTER | BM25 sentences BEFORE→AFTER |
|----------|------------------|-------------------------|--------------|------------------------------|-----------------------------|
| dev_001  | true             | 5 results (0.881)       | **0 results** | 5 → 5 | 4 → 4 |
| dev_002  | true             | 4 results (0.889)       | **0 results** | 8 → 6 | 6 → 6 |
| dev_003  | true             | 6 results (0.913)       | 5 results (0.913) | 5 → 5 | 2 → 2 |
| dev_004  | true             | 4 results (0.920)       | 3 results (0.920) | 4 → 4 | 4 → 4 |
| dev_005  | true             | 4 results (0.933)       | 4 results (0.933) | 4 → 4 | 5 → 5 |
| dev_006  | true             | 4 results (0.906)       | 4 results (0.906) | 5 → 5 | 6 → 6 |
| dev_007  | true             | 4 results (0.903)       | 4 results (0.903) | 5 → 5 | 5 → 5 |
| dev_008  | true             | 4 results (0.974)       | 4 results (0.974) | 4 → 4 | 3 → 3 |
| dev_009  | **false** (OOS)  | 5 results (0.896)       | **0 results** | 4 → 4 | 3 → 4 |

---

## Findings

### Vector cutoff (≥ 0.896)

- **dev_001, dev_002:** Top similarity 0.881, 0.889 → both below 0.896 → **0 results after**. These in-syllabus questions now return no vector chunks; BM25 still has strong results.
- **dev_009 (out-of-syllabus):** Top similarity 0.896 (at cutoff) → **0 results after**. Intended: filters out-of-manual retrieval.
- **dev_003–008:** Top similarity above 0.896 → vector results kept; some lower-ranked chunks dropped (e.g. dev_004: 4→3).

### BM25 cutoff (normalized ≥ 0.5)

- BM25 counts are nearly unchanged; most chunks already pass the normalized cutoff.
- dev_002 paragraphs: 8 → 6 (some low-score paragraphs filtered).

### Cutoffs behaving as intended

- **Out-of-syllabus (dev_009):** Vector reduced from 5 results to 0.
- **In-syllabus with weak vector (dev_001, dev_002):** Vector reduced to 0; BM25 still returns good results.
- **Strong vector hits (dev_003–008):** Kept; only borderline results removed.
