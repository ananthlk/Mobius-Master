# Gate Emit / Telemetry Schema — v1

**Status:** PROPOSED (UX work package against `shape-gate-module-spec.md` §8).
**Owner of this doc:** UX (emits/telemetry). **Consumer:** Retriever wires `GateResult` into this shape.
**Scope:** wire format only — where `GateResult` fields land in the corpus_search response, `rag_query_decisions`, `rag_query_traces`, and the chat Diagnostics tab. Does not touch gate logic itself.

---

## 0. Naming collision found first — read before wiring

`CorpusSearchAgentResponse` already has a field called **`gate`**:

```python
gate: dict[str, Any] | None = None
# "Gate result — always present. Tells the chat panel whether the
#  fail-fast gate fired and why, or confirms it passed cleanly."
```

This is the **existing strategy-(e) fail-fast pre-flight gate** (`{passed: bool, fail_fast_reason: str}`), a narrower binary concept, already rendered by the chat Diagnostics REASON section as a `gate` leaf (`app.ts` `_dcReasonSection`, reads `data.gate.passed` / `data.gate.reason`).

The new SHAPE/contour gate is a **different, richer module** (6-way contour, not pass/fail). **Do not reuse the `gate` key** — it would silently collide with fail-fast's shape and break the existing Diagnostics leaf. Use a new top-level key: **`shape_gate`**. Keep both fields coexisting; do not merge or rename the legacy one as part of this package.

---

## 1. Wire shape — `shape_gate` object

Added as a new top-level field on `CorpusSearchAgentResponse` (sibling to `gate`, `routing`, `query_profile`), always present (matches the "always present" convention already set by `gate`):

```jsonc
"shape_gate": {
  "contour": "EXACT",                 // upper-snake enum, 1:1 with GateResult.contour
  "passed": true,                     // derived: contour in {EXACT, VICINITY, UNDERSPECIFIED}
                                       // false for {CORPUS_GAP, OUT_OF_SCOPE, UNCLEAR}
  "d_codes": ["d:eligibility.medicaid"],
  "j_codes": ["j:fl"],
  "p_codes": [],
  "expansion_phrases": ["medicaid eligibility"],
  "process_intent": false,
  "missing_kinds": [],                 // ["p"] etc — which of d/j/p had zero matches
  "probe": {
    "d_docs": 41, "j_docs": 128, "p_docs": 0,
    "union_docs": 132, "intersection_docs": 9,
    "probe_ms": 68
  },
  "underspecified": null,              // object below, ONLY when contour == "UNDERSPECIFIED"; else null
  "reason": "d+j matched, intersection=9 > 0 → exact",
  "gate_ms": 71
}
```

When `contour == "UNDERSPECIFIED"`:

```jsonc
"underspecified": {
  "kind": "explore_siblings",          // or "missing_domain" / "missing_jurisdiction"
  "fanout_codes": ["d:eligibility.medicaid", "d:eligibility.chip", "..."]  // [] for missing_domain/jurisdiction
}
```

Field-for-field this is `GateResult` unchanged, just nested (`d_codes`/`j_codes`/`p_codes`/`expansion_phrases`/`process_intent`/`missing_kinds`/`reason`/`gate_ms` at the top of the object, `CorpusProbe` under `probe`, and the two UNDERSPECIFIED-only fields folded into one `underspecified` sub-object instead of two parallel nullable fields — cleaner for the frontend to branch on one key, and it's an established pattern here (`fail_fast` is its own nested object rather than flattened fields on the response)).

**`normalized` is intentionally dropped from the wire shape.** It's a normalized-but-still-raw-text derivative of the query — same category the PHI scrub already excludes from `query_profile` (`semantic_core`, `literal_anchors`, `untagged_meaningful_tokens` are all excluded for exactly this reason, replaced with counts/flags). Keep it in-process for Retriever's own logic; don't emit it.

## 2. PHI-safety requirement on `reason`

`reason` is a free-text string. Per the established rule in the `rag_query_traces` scrub-write (query and answer text go through `/redact` before storage; raw-text-derived fields are dropped, not allowlisted), **`reason` must be built from structural facts only — contour name, code lists, doc counts — never an echo of the raw query.** ("d+j matched, intersection=9 > 0 → exact" is fine; a reason string that quotes back user query text is not.) This keeps `shape_gate` PHI-free by construction like the rest of `full_response`, with no separate redact call needed for this field. Retriever: please audit `gate.py`'s reason-string construction against this before sign-off.

## 3. Timing — fold into the existing `timing_ms` bucket

Diagnostics already aggregates a flat `timing_ms` dict per strategy arm and renders every positive numeric entry as a `key Nms` chip (`_dcActRetrieveContent`, the `"timings"` line). Mirror `gate_ms` in there too so it shows up for free without new frontend code:

```jsonc
"telemetry": {
  "timing_ms": { "gate_ms": 71, "embed_ms": ..., "bm25_ms": ... }
}
```

`probe_ms` stays nested under `shape_gate.probe` only (it's sub-detail of the gate step, not a top-level pipeline stage) — don't duplicate it into `timing_ms`.

## 4. `rag_query_decisions` (lean summary row) — add two scalar columns

The decisions row is deliberately lean (bandit's index-only hot path); today it stores scalars like `retrieval_grade`, `synthesis_grade`, `leaf_key` rather than nested JSON. Contour is strategy-relevant (same category as those), so add:

```sql
ALTER TABLE rag_query_decisions ADD COLUMN gate_contour TEXT;
ALTER TABLE rag_query_decisions ADD COLUMN gate_underspecified_kind TEXT;  -- nullable
```

Both indexable, both useful for eval slicing ("show me all VICINITY-contour queries") without touching the traces table. This is a DB-owned migration — flagging here so DB's work package (§8 of the gate spec) picks it up; UX doesn't own the migration, just the recommendation that these two fields graduate from trace-only to decision-row columns.

Full `shape_gate` (everything above) goes into `rag_query_traces.full_response.shape_gate` alongside `query_profile`, `routing`, etc. — no schema change needed there, it's JSONB.

## 5. Chat Diagnostics — REASON section, new leaf

`_dcReasonSection` in `mobius-chat/frontend/src/app.ts` renders `gate` (fail-fast) as the first leaf, then `cleanup` → `rewrite` → `classify` → `scorer`. Add a **new leaf, `shape`, immediately after `gate`** (SHAPE runs conceptually before the existing cleanup/classify sub-steps in the eventual pipeline order):

- **Summary line** (collapsed): `` `${contour} · ${d_codes.length}d/${j_codes.length}j/${p_codes.length}p · union=${probe.union_docs}` ``
- **Dot color**: `ok` for EXACT/VICINITY, `warn` for UNDERSPECIFIED/CORPUS_GAP, `gray`/muted for OUT_OF_SCOPE/UNCLEAR (mirrors the existing ok/warn/gray leaf convention used elsewhere in this file, e.g. the fact-store/rerank "not executed" leaves).
- **Expanded body** (`_dcKV` rows, matching the `classify` leaf's style exactly):
  - `contour`, `reason`
  - `d_codes` / `j_codes` / `p_codes` (joined, same style as existing `domain_tags`/`jurisdiction_tags`/`process_tags` rows)
  - `probe`: `union=N intersection=N (d=N j=N p=N)`
  - `process_intent` (only shown if true)
  - if `underspecified` present: `kind: explore_siblings`, `candidates: N` (show the **count** of `fanout_codes`, not the full list — 80 codes is a wall of text; keep the list itself as a `<details>`-style expandable KV if Retriever wants it inspectable, but count-first)
  - `gate_ms`

## 6. Answering the open questions

**Q1 (emit schema):** §1–§5 above — new `shape_gate` key (not `gate`), nested `probe`/`underspecified`, `gate_ms` mirrored into `telemetry.timing_ms`, two new lean columns on `rag_query_decisions`, full object into `rag_query_traces.full_response`.

**Q2 (`explore_siblings` visibility):** **Backend/Diagnostics-only for now.** Don't add a new top-level user-visible "exploring options" state as part of this telemetry package — Reformat (Step 1b, the thing that would actually execute the fan-out) isn't built yet, so there's nothing real happening for a live status to describe. Diagnostics gets the `kind` + candidate count (§5) so it's inspectable by anyone drilling in, but the main answer surface shows nothing different yet. This question is explicitly Chat's work package in the spec's §8 table ("surfacing `explore_siblings` as a visible 'exploring options' state?") — once Reformat exists and actually runs a fan-out, that's the right time for Chat to design a live status treatment; flagging that this telemetry package intentionally doesn't preempt that decision.

**Q3 (existing conventions matched):**
- snake_case field names throughout, `_ms` suffix for all timings.
- Nested-object-per-pipeline-stage (`query_profile`, `routing`, `fail_fast`, `themes`, `assembly`) rather than flattening — `shape_gate` follows suit as its own object rather than `shape_gate_contour`, `shape_gate_reason`, etc. scattered on the response root.
- `reason: str` as a human-readable trace string is already the pattern (`fail_fast.reason`, routing's own reason strings) — matched.
- "always present, never null" for a top-level gate-shaped field is the existing contract on `gate` itself — matched for `shape_gate`.
- PHI scrub excludes raw-query-derived free text rather than allowlisting fields — matched by dropping `normalized` and constraining `reason` (§2).
- Decision row = lean scalars, trace row = full JSONB — matched (§4).
- `d:`/`j:`/`p:` prefix convention exists on `query_profile.tag_matches` but NOT on the already-split `d_tags`/`j_tags`/`p_tags` arrays — `GateResult.d_codes/j_codes/p_codes` follow the split-array (unprefixed) convention since they're already kind-separated by field name.

---

**Open item for Retriever before wiring:** confirm the `gate` vs `shape_gate` key collision (§0) is understood and `gate` (fail-fast) is left untouched — this is the one thing in this package that isn't a green-field naming choice, it's a bug-in-waiting if missed.

---

## 7. Addendum — narrative layer placement (UX review, 2026-07-22)

A user-facing narrative layer (`app/services/retriever/shape/narrate.py`) was built after this spec, per Ananth's direct ask for the gate's reasoning to read like a visible thinking trace. Two functions, two homes:

- **`narrate(result)`** — one-paragraph, chat-bubble-register summary. States the J/D/P path found, then a collaborative closing line (never the raw `Contour` enum name — e.g. "So I'll explore the likely angles myself..." not "Resolved to: UNDERSPECIFIED"). **Wire into the 12-field contract's `thinking_trace` slot** — that's exactly what it was reserved for, don't invent a new top-level key.
- **`narrate_full(result)`** — the full step-by-step trace (query → lexicon expansion → corpus probe → which heuristic branch fired and why → closing line). Diagnostics-only, behind an expandable "show reasoning" affordance — **never default-visible**. Computed on-demand for the live Diagnostics view only — **NOT wired to any persisted field** (see PHI note below); no `shape_gate.reasoning_trace` or equivalent gets written.

**PHI-safety, STRENGTHENED per TECH's 2026-07-22 review (supersedes this doc's original "redact before persisting" framing):** `narrate_full()`'s first line echoes the raw query verbatim ("You asked: ..."). Per this fleet's standing "PHI default OFF, fail closed" policy, a rule dependent on every future caller remembering to redact before persisting is not fail-closed. **`narrate_full()` output must never be written to `rag_query_traces` or any other persisted storage — compute on-demand for Diagnostics only, discard after render.** `narrate()` has no such exposure (states codes/counts only, never the raw query string) and persists normally via `thinking_trace`.

Voice check: passes Mobius brand conventions (`mobius-design/BRANDING.md` §7) and matches existing first-person copy precedent in `mobius-chat/frontend/src/app.ts`. One wording fix applied: "checked our document index" → "checked what we actually have on file" (avoids a system-y noun).
