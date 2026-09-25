# Scope — model-based failed-query pair miner

**Author:** Deep Research · **Date:** 2026-09-25 · **Status:** SCOPE ONLY, not built
**Consumer:** Curation's tag-selectivity loop · **Supersedes:** the lexical
version, withdrawn as a dead end (`mobius-rag/scripts/checks/tagging_deficit_pairs.py`, 38dc4c7)

## 1. What a pair is, and why the lexical version failed

A pair is **a chunk that ANSWERS a gapped predicate and that the fact loop's
own natural-language query did not retrieve.** The gap between "a specific
wording finds it" and "the real question does not" IS the tagging deficit.

Three lexical probes failed because the definition is semantic, not lexical:
AND over the predicate's words returned zero on a known deficit; OR returned
a nurse advice line and a provider directory; OR plus a value-shape filter
returned the same. The one verified pair (Molina p.184) was found only
because a human picked *"Availity Essentials portal"* — a term **from the
answer**.

## 2. The design: the judge already exists

**Do not build a new judge or register a new LLM stage.**
`mobius-payor/app/fact_loop.py::shape_answer(rag_response, predicate_desc,
value_shape)` already decides exactly this question. It takes
`{chunks, llm_answer}`, runs stage `fact_shape` (already in chat's
`_SKILL_LLM_ALLOWED_STAGES` since 2026-09-09), and either extracts a fact or
does not.

So a pair becomes a statement with no new machinery behind it:

> **a chunk the fact producer WOULD have extracted a fact from, had
> retrieval surfaced it.**

Pipeline, per gapped predicate in a run:

1. **Recall, cheap and lexical.** OR over the predicate's terms, filtered to
   the payer's documents, cap ~120 chunks. Precision does not matter here —
   this is a net, not a decision.
2. **Subtract what the loop already saw.** Re-run the loop's own final query
   through the retriever; drop every chunk it returned. What remains is
   "present in the corpus, missed by the question".
3. **Judge the remainder.** `shape_answer({"chunks": batch, "llm_answer": ""},
   predicate_desc, value_shape)` in batches of ≤6 (its own truncation limit).
   A batch that yields a fact identifies the carrying chunk.
4. **Verify the quote mechanically.** The shape schema returns a verbatim
   `quote`. **Require it to appear literally in the chunk text.** This is the
   precision guard and it is not optional — it turns a model assertion into
   a checkable one.
5. **Emit** `{predicate, payer, nl_query, chunk_id, doc, page, quote,
   loop_retrieved_pages}`.

## 3. Cost

`ceil(120/6) = 20` shape calls per gapped predicate, batched, `max_tokens=900`.
A 2-predicate run like the Molina one is ~40 calls. Bounded by construction:
the candidate cap is the only knob that grows it.

## 4. Acceptance (write these before building — they decide it, not a demo)

| must | case |
|---|---|
| EMIT | Molina p.184 for `appeal.submission_channels` — "Submit requests directly to Molina Healthcare of Florida via the Availity Essentials portal" |
| NOT emit | p.6 24-hour nurse advice line |
| NOT emit | p.10 provider directory page |
| NOT emit | p.2 "No substantive policy content was provided" |
| NOT emit | any chunk whose returned `quote` is not literally present in its text |

The three negatives are the exact rows the lexical version produced. If the
model version cannot separate them it has not improved on the dead end.

## 5. Risks, honestly

- **False positives poison the consumer.** A noisy pair stream is worse than
  none — it trains the loop on junk. Mitigated by step 4 and by the
  precision-first acceptance bar, not by a recall target.
- **Self-consistency is a feature AND a blind spot.** Reusing `fact_shape`
  means a pair is defined by the producer's own judgement, so the miner
  cannot see deficits the producer is also blind to. State this wherever the
  output is used; do not let it be read as ground truth.
- **Judgement drift.** `fact_shape` is a live stage owned elsewhere; a prompt
  change silently changes what counts as a pair. The acceptance cases are the
  regression guard, so run them on every batch, not once.

## 6. Dependencies and ownership

- **None new.** `fact_shape` is registered and live; no chat allowlist entry
  needed (that was the August 400 blocker and it is closed).
- Miner: Deep Research. Judge stage: payor / LLM Manager. Consumer: Curation.
- Runs offline against completed fact runs. Touches no serving path.

## 7. What it still cannot do

It **confirms and localises** a deficit once a gap exists. It does not
discover deficits unprompted, because step 1 still needs a corpus subset
worth judging. Volume is therefore bounded by fact-producer gap volume, not
by the corpus.

## 8. Effort

Small — roughly a day, mostly acceptance cases and the quote check. The
judgement, the stage, the schema and the telemetry all exist; this is
plumbing plus a guard.

## 9. Recommendation

**Do not build it yet.** It is downstream of two things that outrank it:
Curation's summary-prefix strip (#2) and the section re-extraction (D-14).
Both change what retrieval returns, which changes what counts as a gap —
so pairs mined today may not be pairs afterwards. Build it when the producer
is running at volume against a corrected corpus, and when Curation's loop
actually has capacity to consume pairs.
