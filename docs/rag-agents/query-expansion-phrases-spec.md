# Spec: `query_expansion_phrases` — separating query-expansion from doc-tagging

**Owner:** Lexicon (Curation leg) · **Requested by:** Retriever (Gate) 2026-08-08 · **Status:** proposed, awaiting Retriever wiring + DB-seat convention ratification

## Problem

`policy_lexicon_entries.spec.strong_phrases` is **dual-use**: the same array is consumed by

1. **doc-tagging** — `policy_path_b.get_phrase_to_tag_map` / `_apply_tags_to_line_text`: every strong phrase that matches a corpus line tags that chunk with the entry's code (score 1.0).
2. **query-expansion** — `corpus_search_lexicon.expand_query_via_lexicon` (Gate): a strong phrase matching the user's query expands it to that code (routing/coverage).

These two faces have **opposite** tolerance for generic phrases. A broad phrase like `how to apply` or `application process` is *good* for query matching (users phrase questions that way) but *toxic* for doc-tagging — verified live: adding those to `eligibility.enrollment` would have false-tagged ~3,000 off-concept chunks (facility/license/grant "applications") into the enrollment pool on the next retag, wrecking selectivity. Today the only way to get the query-side benefit is to accept the doc-side damage.

## Solution

Add an **expansion-only** phrase list: `spec.query_expansion_phrases` (JSONB array of strings).

- **No migration** — `spec` is already `jsonb`; this is a new optional key. Absent ⇒ empty. Fully backward compatible.

## Contract (the whole point — who reads what)

| Consumer | reads `strong_phrases` | reads `weak_keywords` | reads `query_expansion_phrases` |
|---|---|---|---|
| **doc-tagging** (`policy_path_b`, mine) | yes (1.0) | yes (0.6) | **NO — must ignore** |
| **query-expansion** (`corpus_search_lexicon`/Gate, Retriever) | yes | (as today) | **yes** |

So `query_expansion_phrases` maps a **query phrase → tag code for routing only**, and can *never* tag a document. That lets generic phrases help Gate reach the right code without polluting the corpus tag pool.

## Population rule (Lexicon content policy)

- **`strong_phrases`** — anchored, specific phrases safe for BOTH faces (carry a domain noun): `apply for medicaid`, `medicaid application`, `apply for coverage`.
- **`query_expansion_phrases`** — generic/broad phrases that help match questions but would over-tag docs: `how to apply`, `application process`, `how do i enroll`, etc.
- Still subject to the query-side single-word stoplist (`_SINGLE_WORD_STOPLIST`) — expansion phrases don't bypass existing generic-word guards.

## Work split

- **Lexicon (me):** add the field to content policy; migrate the reviewed generic phrases (e.g. `eligibility.enrollment`'s `how to apply`/`application process`, removed from `strong_phrases` on 2026-08-08) into `query_expansion_phrases`; own ongoing population.
- **Retriever:** wire `expand_query_via_lexicon` to read `strong_phrases ∪ query_expansion_phrases` for query matching.
- **doc-tagging (me):** confirm `get_phrase_to_tag_map` reads only `strong_phrases` + `weak_keywords` (it already does — this field is simply not added there).
- **DB seat (Platform Architects):** no DDL; ratify the `spec` sub-field convention.

## Validation

After wiring: (1) a query that only matched via a generic phrase still expands correctly (Gate no CLARIFY); (2) a retag does NOT add the generic phrase's code to chunks that only contain the generic phrase (doc-tag pool unchanged); (3) `eligibility.enrollment` "how to apply for Medicaid through DCF" stays covered.
