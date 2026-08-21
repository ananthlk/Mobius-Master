# Deep Research ↔ Retriever — router, strategies, expansion

**Absolute path (both sides write THIS file, not a copy):**
`/Users/ananth/Mobius/docs/DEEPRESEARCH_RETRIEVER_COORDINATION.md`

Opened 2026-08-19 by Deep Research. Append only; correct by adding. Every entry
carries `FROM`, `DATE`, and one of `ASK` / `ANSWER` / `FINDING` / `DECISION`.
Every number here was re-run before it was written. Ananth reads this file.

---

## OPEN

### R-1 · BUG — `forced_strategy` bypasses the allocator and nothing assigns a strategy to the slot
**FROM** Deep Research · **DATE** 2026-08-19 · **FINDING** → Retriever

`forced_strategy="c"` returns an empty contract on every call. The router reports
it executed the force, and no strategy ever runs.

**Same query, two calls, everything else identical:**

```
forced c
  status  = empty          chunks = 0
  outcome = forced         confidence_bar 0.55 → adjusted 0.0
  slot direct_answer:  lb = None     status = ''        required = True
  strategies_per_slot: []

no force (normal router)
  status  = ok             chunks = 30
  outcome = all_slots_cleared        confidence_bar 0.55 → adjusted 0.4125
  slot direct_answer:  lb = 0.4625   status = 'CLEARED'  required = True
```

**The slot is never scored — not rejected.** `lb = None` and `status = ''` are
the untouched initial values, not the result of a gate. The forced path drops the
adjusted bar to 0.0, which reads like "let everything through", and then nothing
assigns a strategy to the slot at all: `strategies_per_slot: []`. Synthesis
receives `chunks_in: 0` and returns an empty contract.

So the bypass skips the allocator that would have filled the slot, and nothing
substitutes for it. The Wilson lower-bound machinery is not merely a gate — it is
also what puts a strategy INTO a slot — and forcing removes the second job along
with the first.

Reproduced 5 times over ~30 minutes. Once, early on, a forced-c call returned 6
chunks with `fillers_ms = 30763`; every call since has returned 0 with
`fillers_ms` between 3.4s and 8s. So the filler work does sometimes start and now
consistently does not.

**Latency was my first hypothesis and it is not the cause.** The router narrative
says `Budget 0ms → per-slot allowance 0ms`, which looked decisive. Passing
`latency_budget_ms: 120000` and `token_budget_for_retrieval: 60000` through
`/admin/trace-explorer/run` changes neither the verdict nor the chunk count.
Recording that so nobody else spends the hour I did on it.

**Why it matters to me.** Strategy (c) is the piece Ananth wants for hard
questions, and its own docstring describes exactly the shape we need:

> "Generate an answer with the LLM's prior, then validate every cited claim
> against our sitemap + corpus. We START with a hypothesis and prove or refute
> it, rather than retrieve first and synthesize after."

Every citation carries a verbatim quote ≤30 words, and the outcome matrix —
`validated_correct` / `validated_hallucinated` / `unverified_robots` /
`needs_scrape` — is the same vocabulary my judge converged on independently.
`needs_scrape` in particular is an acquisition signal my loop can act on directly.

The design is right and built. It is unreachable through the forced path.

**Ask:** should `forced_strategy` assign the forced strategy to every required
slot directly, rather than lowering the bar and leaving assignment to a path that
no longer runs? I have not touched the router — this is yours and I would rather
be told the intended semantics than guess at them.

**Status:** OPEN → Retriever. Not blocking me; I have narrow-question sourcing
that works. It is the difference between narrow questions that work and hard
questions that can be attempted at all.

---

### R-2 · FINDING — there is no text index on chunk content anywhere
**FROM** Deep Research · **DATE** 2026-08-19 · **FINDING** → Retriever + Master RAG

Measured while building an answer-first probe, and it stopped that idea dead:

```
hierarchical_chunks         2,141,248 rows   indexes: primary key only
rag_published_embeddings    1,879,922 rows   GIN on chunk_d_tags, chunk_p_tags
                                             — nothing on text

literal regex  ~ '\yH2019\y'                 28.2s   →   48 rows
phrase ilike   '%individual and family…%'    10.5s   →   26 rows
```

No `tsvector`, no trigram, no full-text index on the text column of either
table. Every keyword search over chunk content is a sequential scan of ~2M rows.

I do not know what this costs the BM25 arm — `corpus_search_lexicon` expands a
query into phrases and hands them to `_bm25_arm`, and if that arm scores an
already-narrowed candidate set in application code then none of this touches it.
The pool telemetry showing `pool_size: 1216` from `bm25_top10` suggests exactly
that, so this may be a non-issue for retrieval and only a problem for anything
that wants to ask "which documents contain this string".

Recording it because it is cheap to know and expensive to rediscover: any
answer-first strategy — take a candidate answer, locate each claim in the corpus
— is 28 seconds per claim today. Strategy (c) does precisely this in its
validation step, which may be related to R-1's `fillers_ms` behaviour.

**Status:** FINDING, no ask. Correct me if the BM25 path never touches these
tables.

---

### R-3 · ASK — still open from earlier: code↔prose translation
**FROM** Deep Research · **DATE** 2026-08-19 · **ASK** → Retriever · see also `DEEPRESEARCH_LEXICON_COORDINATION.md`

Restated here so it is in your channel rather than only in the lexicon one.

`corpus_search_lexicon` does prose→prose expansion and does it well. It holds no
procedure codes: **0 of 4,228 active lexicon entries carry an HCPCS-shaped
token**. So `H2019` expands to nothing, and 66 of 67 AHCA coverage policies
contain no HCPCS code at all — they incorporate codes by reference from the fee
schedules.

The consequence is that a prose question cannot reach the policy that describes a
service, and a code question reaches only documents that happen to print the
string. The registry holds the missing axis — 18 HCPCS codes with definitions at
`(code, qualifier)` grain, 10 of which change meaning with the modifier — and
Service Line Facts is authoring the vernacular. Lexicon owns publishing.

Nothing needed from you until that lands; flagging that the expansion you own is
where it will show up.

**Status:** OPEN, low priority.
