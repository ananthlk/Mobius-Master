# Curation — RAG sub-agent charter

**Status:** proposed 2026-07-22 (Ananth). **NEW agent.** Reports to: RAG (macro).

## Mission (one line)
Make sourced documents accessible — chunk, embed, tag, and publish them into the searchable corpus.

## Scope (leg — module detail comes in layer 2)
- Chunking.
- Embedding (embedding-workers).
- Lexicon (j/p/d tags).
- Publish → searchable corpus.

## Coordinates underneath
- **Lexicon agent** (exists) — moves underneath; owns the lexicon module.

## Non-goals
Not sourcing (that's Sourcing). Not retrieval/answering. Not corpus-integrity upkeep (that's Maintaining).

## First tasks
1. Confirm leg scope; bring the Lexicon agent underneath.
2. Layer 2 — take the assigned modules (chunking / embedding / publish); confirm `ownership.yaml` rows.
3. Define the curated-chunk contract the Retriever's pool consumes.

---

## Open asks waiting for this seat

*Added by Deep Research 2026-09-25. There was no Curation session running to
message, so the asks live in
`docs/DEEPRESEARCH_RAG_COORDINATION.md` and this is the pointer. Read D-14
before D-13 — D-14 withdraws and replaces D-13's ask.*

**D-14 — `section_path` is not a section column (supersedes D-13).**
It holds five different kinds of value: running page headers, body text
misread as a heading, table fragments, **table cell values**, and real
headings. The first three separate mechanically; the last two do not.
`T1030`, `V5140` and `Yes` are stored as section paths and are the first
cell of a table row. `Caregiver` and `Complaints, grievance and appeals
process` are both short, capitalised and unrepeated, and no rule over the
stored text tells them apart.

- **Do NOT run a backfill.** I dry-ran the forward-fill: it works and
  propagates the wrong value (Molina p.184, the Availity submission channel,
  inherits a mid-section address block).
- **The ask is re-extraction capturing heading LEVEL**, populating
  `chapter_path` — empty on all 2,339,099 published rows — as the coarse
  level with `section_path` as the fine one. Both levels are already in the
  schema. PDF outline/bookmarks, if available at extraction, are the
  cheapest source of truth.
- **NO RE-EMBEDDING NEEDED.** `embedding_worker._build_text_for_chunk`
  embeds `summary + "\n" + text` and never reads `section_path`, so the
  section was never in any vector. Metadata reprocess only; chunk boundaries
  and chunk text unchanged.
- Scope: all 9,084 documents, one chunker (`hierarchical`). Per-document
  coverage: 1,691 full · 1,290 at 90-99% · 2,371 at 50-89% · 2,546 under
  50% · 1,188 at zero.

**Why it matters:** the payor fact producer returns honest `gap` on answers
that ARE in the corpus, because nothing can ask for a section. Not blocking,
but it caps what more producer volume can achieve.

**Related, same seat, smaller:** Molina p.184 carries `disputes.appeal` once
against p.183's eleven while holding the appeal submission channel, and
`tag_coverage` is 0.40 of the reranker's weight — so an appeal-framed query
ranks it nowhere. Chunk tagging, not section structure.

### Withdrawn: the automated failed-query pair stream

*Deep Research, 2026-09-25, after the Curation session ended. You accepted
my offer to feed failed-query pairs into the tag-selectivity loop ("feed
them; the loop consumes them"). **Do not wait for them.** I built it and it
produces noise, so I am withdrawing the automated version.*

Three lexical probes over a real gap run, all wrong:

- **AND over the predicate's words** — zero pairs, on a run whose deficit I
  had already found by hand. Molina p.184 holds *"Submit requests … via the
  Availity Essentials portal"* and contains neither "appeal" nor "channels",
  so the AND excluded the one chunk the pair was about.
- **OR over the same words** — a 24-hour nurse advice line, a provider
  directory page, and a chunk reading *"No substantive policy content was
  provided"*.
- **OR + value-shape from `fact_template.value_shape`** (a deadline answer
  must contain `<n> days`) — still the advice line and the directory,
  because a long chunk contains some day-count somewhere.

**The root:** a pair is "a chunk that ANSWERS this predicate", which is a
semantic judgement. The one verified pair exists because I picked *"Availity
Essentials portal"* — a term taken from the answer. No probe that does not
already know the answer selects that term.

**What you have instead:** one hand-verified pair (Molina p.184) with the
two-query proof, already in the messages and in D-14. Not a stream.

**What would work**, if you still want volume: read the gapped predicate and
the candidate chunks with a model and ask which one carries the answer.
That is its own piece of work, not a by-product — say so and I will scope
it. The script is kept as a marked dead end at
`mobius-rag/scripts/checks/tagging_deficit_pairs.py` (38dc4c7) so the three
probes are not re-walked.

A noisy pair stream is worse than none: it trains the consumer on junk.
