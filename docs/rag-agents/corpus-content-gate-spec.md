# Corpus Content-Quality Gate + Junk Cleanup — spec (DRAFT v0)

**Owner:** Curation (chunk→embed→tag→publish). **Status:** design 2026-07-23.
**Trigger:** Retriever + Filler-b found ~12% of the published corpus is contentless
junk winning vector top-N by cosine math (root cause verified in code below).
**Gates:** Technical Review (structural, the code change) · Eval (outcomes, the
cleanup before/after) · Data & DB (bulk-delete mechanics). Builds in the code-move
window; cleanup runs post-baseline. Respects the clean-tree freeze.

---

## 1. Finding (independently verified ×3: Filler-b, Retriever, Eval + me)
`rag_published_embeddings` (1,937,353 rows), text ≤ 30 chars:
- `"-"` — **185,261** (9.6%) · `"‐"` lookalike-dash — 14,234
- bare headers `"GOVERNOR"` 9,618 / `"SECRETARY"` 8,652
- leaked PDF-viewer UI chrome: `"MS Word Viewer"` 1,003 · `"Ok, I understand"` 1,003
  · `"Windows Media Player"` 1,002 · `"Twitter.com/AHCA_FL"` 1,530

They embed to **real, non-degenerate vectors**; short/generic text scores moderately-
high cosine against almost any query → wins top-N legitimately by the math despite
zero content. BM25 correctly zeros them, but the **vector arm doesn't consult BM25**,
so nothing filters them before a user-facing answer. ~12% combined → suppresses
recall fleet-wide.

## 2. Root cause (code-verified)
Two sibling splitters in `app/services/chunking.py`:
- **`split_paragraphs_from_markdown` (:97) — the LIVE path** (coordinator.py:24).
  Only skips truly-empty paragraphs (`if not para: continue`, :133). A bare `"-"`
  survives (`"-".strip()` is truthy) → chunk → embed → publish.
- `split_paragraphs` (:164, used ONLY by `page_to_markdown_blocks` export) **has** a
  junk-drop heuristic (:216-220). It was never applied to the live path.

The filter exists — on the wrong function. No content gate before embed/publish.

## 3. The gate (single-sourced `is_contentless(text) -> bool`)
Layered, precision-ordered. Factor into ONE helper used by BOTH the chunk-emit gate
and the publish backstop (no drifting copies — same discipline as the refactor's
one-writer/one-importer gates).

| # | rule | catches | false-positive risk |
|---|---|---|---|
| R1 | **zero-alnum**: strip to `[A-Za-z0-9]`; empty ⇒ drop | `"-"`, `"‐"`, `•`, `\|`, bare punct (~200k) | **none** — no real content is pure punctuation |
| R2 | **UI-chrome stoplist** (normalized exact-match, maintained) | `MS Word Viewer`, `Ok, I understand`, `Windows Media Player`, `Twitter.com/AHCA_FL`, … | near-none (curated list) |
| R3 | **orphan-header**: single short all-caps/Title token, no body, no terminal `.`/`:` | `GOVERNOR`, `SECRETARY` | **needs calibration** — could clip real short labels |

R1+R2 are safe (near-zero FP) and catch the bulk (~200k+chrome). **R3 ships only
after eval-bank calibration** (§4). Prefer *merge* (attach orphan header to adjacent
body) over *drop* where the split already has header-attachment logic.

**Placement:**
- Primary — `split_paragraphs_from_markdown`, right after `:133` (`if not para`).
  Root-cause: junk never chunked/embedded (saves embed cost).
- Backstop — `publish.py` row loop: skip building a `RagPublishedEmbedding` whose
  text `is_contentless` (catches fact-derived rows + anything slipping chunking).

## 4. Calibration / false-positive guard (Eval-ratified params 2026-07-23)
- **Bank:** `eval/queries_cmhc.yaml` — the FULL cmhc-26 bank (NOT `queries_cmhc_smoke.yaml`;
  same bank Pool / Filler-a / Filler-b calibrations use). NB: wrong bank ⇒ all-zeros
  must_facts — pass the full `bank_path`.
- **FP guard:** run `is_contentless` over the bank's **`golden_answer` / must_facts-
  bearing chunks specifically** (Eval's precise definition of "real answer chunk" — not
  just any chunk); assert **zero** are dropped.
- Report **per-rule drop counts** corpus-wide (R1 / R2 / R3); reconcile against §1.
- **R3 ships only at FP=0** on the bank; if it can't reach 0, ship R1+R2 only and handle
  headers via merge, not drop. (Eval: do not compromise this even if it delays R3.)

## 5. Cleanup of existing junk (~230k rows) — post-baseline, Eval-gated
- **Identify** via SQL-expressible R1+R2 (e.g. `length(regexp_replace(text,'[^A-Za-z0-9]','','g'))=0` OR `text = ANY(:stoplist)`); R3 rows fetch-and-filter.
- **Durable retire:** delete at published **and source** level (the underlying junk
  `chunk_embeddings` / `hierarchical_chunks`) — else the next publish resurrects them.
  Alternative: re-chunk affected docs with the gate (cleaner but heavier). Decide with DB.
- **Mechanics (DB):** batched delete (per-doc / bounded batches) to spread MVCC on the
  1.94M-row table — same pattern as the `main.py:1681` per-doc backfill. DB owns the
  bulk-delete execution; I own which rows.

## 6. Before/after measurement plan (Eval-ratified 2026-07-23 — protocol first, NO numbers until a real run)
1. **Baseline pins NOW** on the current (junk-included) corpus — Eval (decided 2026-07-23).
2. **Bank:** `eval/queries_cmhc.yaml` (full cmhc-26, NOT smoke).
3. **Metric:** **must_facts coverage** in the retrieved candidate set — Pool's
   `oracle_recall` methodology (empirical ceiling 0.84). Per query = fraction of
   `must_facts` findable (string/semantic match) in the retrieved pool; aggregate =
   mean across the bank. **Two slices:**
   - **Full-pool recall** (all arms) — the headline before/after number.
   - **Vector-arm-only recall** (`source_arm == "vector"`) — where junk bites (Filler-b);
     this slice proves the cleanup's *mechanism*, not just the aggregate.
4. **Before = junk baseline** (step 1). **After = post-cleanup**, re-run the identical
   bank + both slices. **Delta = attributable recall lift** from junk removal.
5. **Artifact-gated:** no lift number claimed until a real run produces the artifact.
6. **Co-run:** at the code-move window I ping Eval with the FP=0 report + per-rule drop
   counts; Eval verifies against the bank before signing off R3 shipping.

## 7. Sequencing (respects freeze + gates)
1. **Now (design):** this spec + the before/after protocol → Eval.
2. **Code-move window:** land the gate (`is_contentless` + both call sites), Tech
   Review byte/structural-gates it (it changes what publishes going forward =
   NUMBER-MOVING for new ingests; calibrated FP=0 first).
3. **Post-baseline:** run the cleanup (DB batched delete) → Eval re-runs the bank →
   report the measured lift.
