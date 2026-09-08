# What we found by looking at the machine work

2026-09-08. Every finding here came from opening the console and reading a real
run — not from tests, which passed throughout. They are recorded because the
same shapes will recur, and because several were invisible in exactly the way
that matters: the page looked complete.

---

## 1 · The cost page was showing one percent of the bill

`research.llm_call` held rows for the **judge** and the **assembler** — the two
cheap actors. The **drafter**, which spends a hundred-odd reasoning steps a turn
through chat, recorded nothing at all.

| actor | one turn |
|---|---|
| judge + assembler | **0.23 tenths of a cent** |
| drafter (measured) | **7.8 cents**, 14 model calls, 152,678 input tokens |
| drafter (priciest recent) | **$0.44**, 19 calls, 515,357 input tokens |

So the page was showing roughly **1%** of the spend and presenting it as the
total. The join key existed on both sides and was held by neither: we generated
a `correlation_id` per chat call and threw it away; chat's `llm_calls` is
indexed on exactly that value.

**Fixed** — the id is kept, the spend is read back from chat, and the numbers
are copied into our own row so the console reads one table.

**Two second-order findings from the same thread:**

- `llm_calls.turn_id` is documented as `== chat_turns.correlation_id` and looks
  like the better key. It is written only by the newer CallManager path, so it
  is **sparse**. Joining on it silently loses most rows and reports a *lower*
  cost with no error anywhere. Chat Master warned us; nobody would have found
  this by testing.
- The cost panel counted the rows it *had* and said nothing about rows that were
  **absent**, so historical turns read as a complete bill. Counting absent as
  not-applicable is the same error as counting unknown as zero, one level up.

---

## 2 · Almost all of the elapsed time is waiting, not thinking

Run and wait are the same wall clock and completely different problems. Nothing
distinguished them until there was a panel that did.

| question | end to end | computing | waiting |
|---|---|---|---|
| request 114 | 385 s | **22 s** | 364 s (94%) |
| request 113 | 833 s | **19 s** | 814 s (98%) |

A round that takes 26 minutes of which 2 are compute is a queueing problem. The
same 26 minutes spent computing is a model problem. One number cannot tell them
apart, and we had one number.

---

## 3 · "Working" was true of nothing

`open` is one database status meaning "not finished". The page rendered all of
it as **"Working · Still looking"** — untrue of **twelve of twelve** open
requests at the moment it was checked: none had a round running.

```
before   sourced 31 · open 12 · escalated 6 · abandoned 2
after    sourced 31 · machine's move 7 · waiting 4 · needs a person 7 · dropped 2
```

The reader-facing state is derived from what is *happening*, and the list, the
detail, the filter and the dashboard now count the same way — the dashboard had
its own tally and disagreed with the list beside it.

---

## 4 · A turn ran for 110 minutes showing no sign of life

`in_flight` was "running **and** created in the last 10 minutes"; `turn_stuck`
was "running **and** older than 2 hours". Between them sat a 110-minute hole
where a turn showed **neither badge** and simply looked dead.

Measured against 64 completed turns: median **2.2 min**, 90th percentile
**26 min**, longest **159 min**. So **19%** of real work fell in that hole — and
the 2-hour "stuck" label would have libelled turns that went on to finish.

Worse: there was nothing to stream. `thinking_log` is written to the attempt
only when a turn **concludes**, so for a turn's whole life the database held
nothing to show — while the lines existed all along, printed to a terminal
nobody was watching.

**Fixed** — `research.turn_stream` carries them live, and the console tails a
running round.

---

## 5 · The account claimed the machine corrected itself

A withdrawn diagnosis was recorded under `actor=diagnoser` with the label
**"Corrected itself"**. The machine detected nothing: a person reframed the
question, a person changed the rule, and a person re-ran the diagnosis.

A reader deciding whether to trust a correction needs to know who made it. It
reads **"Withdrawn"** now and carries the author, and `withdraw_diagnosis()`
refuses a withdrawal with no name on it.

---

## 6 · Two of three is not complete

"Extracted" meant done, so a turn that got two of the three fields the requestor
named closed as **Answered** with the third simply absent — and a round still
available.

The field was lost because our own extractor attached a quote that was not in
the answer. That is repairable. Completeness is now measured against what was
**asked for**, and the reason a field is missing decides *how* to ask again:

| missing because | the re-ask says |
|---|---|
| our fault | quote the exact sentence, word for word, do not paraphrase |
| not stated | look specifically for this; if the document does not state it, say so |

And a related cause: `runner open` had **no `--schema-file`** and passed
`extraction_schema=None`, so every question opened from that CLI carried no
statement of what the caller wanted. "2 of 3 complete" could not be computed
because nothing said *3*.

---

## The shape underneath

Every one of these is a place where **the page looked finished**. A cost with a
missing actor, a duration with no elapsed time, a status that covered three
situations, a correction with no author, an answer with a field quietly absent.

None of them failed a test. All of them were found by opening the thing and
reading it — which is the only method that works on a surface whose job is to
tell you the truth about something else.
