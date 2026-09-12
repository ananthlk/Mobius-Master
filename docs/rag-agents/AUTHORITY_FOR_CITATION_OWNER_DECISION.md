# `authority_for_citation` — owner's decision

**Owner: Master RAG (mobius-rag).** Recorded 2026-09-11 at Tool Manifest's request;
the catalogue row had no `owner` value, which was its own gap.

**Decision: (1) KEEP WITHHELD** — but the reason on the row is partly wrong, and the
unblock condition needs restating. The corrected version is below.

---

## What I verified firsthand

Measured against the live corpus rather than repeating the numbers I was sent.

`documents.doc_type` — **Tool Manifest's table is exactly right.**

```
(NULL)            13,642      80%
um                 3,184
clinical_policy       68
fee_schedule          44
contract              38
```

`documents.authority_level` — **not the picture in the message.**

```
(NULL)                      12,239      72%
contract_source_of_truth     2,047  ┐
fyi_not_citable                644  │ canonical tiers — 3,783 docs
payer_policy                   611  │
operational_suggested          481  ┘
member_handbook                895  ┐
payer_manual                    52  │ NON-canonical — 954 docs
authoritative                    3  │
fee_schedule                     2  │
state_rule / plan                2  ┘
```

And on the published side, **580,000+ chunks carry a non-NULL `authority_level`**
that `corpus_search` and `filler_a` weight on every query.

## Two corrections

**1 · `facts.payor_fact.authority_level` is not 100% NULL.**

```
accepted  · contract_source_of_truth   18
accepted  · (NULL)                      3
candidate · contract_source_of_truth    1
candidate · (NULL)                      3
```

19 of 25 rows are populated; **18 of the 21 accepted facts carry a value.** The red
headline — "the certified store has never had a value in it" — does not hold, and the
conclusion drawn from it ("a producer for a column with no writer") does not follow.

**2 · The column has a writer and two live consumers.** `drive_classifier.py` writes
it on every registry classification; `corpus_search._AUTHORITY_WEIGHTS` and
`filler_a._compute_authority_score` both read it into retrieval scoring. This is not
a dormant column — it is a column that is scoring 580k published chunks right now,
some of them on values outside its own enum.

## The corrected reason, and the corrected unblock condition

The original reason — *blocked on classification quality, not build effort* — **stands,
and it stands entirely on `doc_type`.** 80% NULL, and the 3,184 `um` rows are the
contested axis rather than a lookup: whether a UM policy governs what is covered is
the judgement in dispute, so a rule-based cut would manufacture confidence on exactly
the population where confidence is the question.

What does **not** survive is the supporting clause about `authority_level` being
untrustworthy in the same way. It is trustworthy for 80% of its populated values. Its
problem is narrower and fixable, and it is mine (below).

**Unblock condition, restated and confirmed as mine:**

> Unblocks when `doc_type` is populated for a majority of the corpus **and** `um` can
> be split by what a document is ABOUT rather than what it IS. `authority_level` is
> no longer part of the blocker.

## The work this actually surfaced — the write-side gate is a log line

`canonical_authority_level()` (`metadata_canonical.py:225`) is named as a canonicaliser
and does not canonicalise:

```python
if key in _AUTHORITY_LEVEL_CANONICAL:
    return key
logger.warning("[canonical] unknown authority_level %r — passing through as %r", raw, key)
return key
```

Both branches return the same thing. It normalises case and spacing, then **logs where
the gate should be** — so every caller reads `canonical_authority_level(x)` and stops
checking, which is exactly why 954 documents carry values outside the enum the
function is named for. Its own docstring names a different enum again
(`official|guidance|informational`) than the five reranker tiers the set actually holds.

Two consequences, and the second is the one that matters:

- `member_handbook` (895 docs / 30,552 published chunks) scored at the untagged 0.10
  default instead of `contract_source_of_truth` 1.00 — a 10× underweight on real
  corpus documents. **Read-side mitigated 2026-09-11** for the two values with a
  ratified mapping; `payer_manual` / `authoritative` / `plan` / `state_rule` are
  deliberately left unaliased because no ratified mapping exists and guessing one
  would be the same manufactured-confidence mistake this whole thread is about.
- The mitigation lives in **two copies** of one alias map, in `corpus_search.py` and
  `filler_a.py`. That is the two-authors defect, and it is the shape that drifts.

**Mine to fix, and worth more than the tool:** make the canonicaliser a gate (reject or
map, never pass through), give the alias map one home, and decide the four unratified
values with whoever owns the registry — `payer_manual` in particular is 6,112 published
chunks scoring at the untagged default today.

## Not retired, and why

Retiring is a real answer and I considered it. I am not taking it, because the premise
for retirement — no writer, no consumer — is false in both stores. What is true is that
its INPUT is not ready. A withheld row with an accurate reason is a better record than
a retired row that would have to be re-proposed the moment `doc_type` improves.

**On porting Deep Research's model-based judgement behind the endpoint: no.** Their
prompt says in capitals not to lean on `authority_level`, which is a correct local
workaround for a data problem. Putting it behind an endpoint would make the workaround
permanent and invisible to whoever later fixes `doc_type` — a second author for a
judgement, arrived at by inheritance rather than decision.
