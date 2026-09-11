# Governor seat — my own telemetry

Ananth, 2026-09-10: *"you should also start a telemetry for yourself as we go
along on how you are budgeting this."*

**The point:** I am specifying an attestation that makes a promise falsifiable.
If I do not hold my own work to the same standard, the design is advice I do not
take. So: same three terms, same honesty rules — **what I claimed, what it cost,
and what turned out wrong.**

Append-only. Newest at the bottom of each table.

---

## The seat's own promise

| term | my commitment |
|---|---|
| **quality** | every factual claim carries a tag — `[MEASURED]` / `[READ]` / `[RULED]` / `[DESIGN]` / `[OPEN]`. **No number without provenance.** |
| **latency** | a correction lands in the artifact **in the same turn it is found**, not queued |
| **cost** | measured below. Not yet bounded — I have no baseline to bound it against |

---

## Ledger — deliverables

| # | deliverable | commits | status |
|---|---|---|---|
| 1 | Codified promise (§7) | `b4eec9d` | done |
| 2 | Override register (§9) | `a2a3fd8` | done — then **ruled out of scope** |
| 3 | Resolver (§9a) | `6631e0c` | done — out of scope with §9 |
| 4 | Scope + attestation (§7a) | `95ed231`, `42bfa55`, `440645d` | done, **2 corrections** |
| 5 | Presentation (§7b) | `079df88`, `1664172` | done |
| 6 | Promise clock (§7c) | `eb48d20` | done |
| 7 | Build sequence (§7d) | `ff4388b` | done |
| 8 | Work order | `81b5bc4` → `c66f2ac` | issued, **4 amendments** |
| 9 | The emit, shown (§7e) | `c983ba8`, `b2cbf24`, `8af7dcc` | done, **2 corrections** |
| 10 | Build log | `27d6264` → `de1d56e` | running |
| 11 | This file | — | opened |

**Cost so far: 30 commits across 4 artifacts. Zero lines of production code —
by standing constraint, all code is Chat's.**

---

## Error ledger — what I got wrong, and how it was caught

**This is the column that matters.** A seat that reports only its output is
doing exactly what §7a forbids.

| # | claim | reality | caught by | cost |
|---|---|---|---|---|
| 1 | "cost is per-turn visible at 99.6% coverage" | that was *turns matching a call*, not cost completeness | **me**, on re-measure | rework |
| 2 | "only 53.7% attributes — cost leg BLOCKED" | counted **development spend** as missing turn cost | **Ananth's ruling** | wrong verdict published |
| 3 | "ten publish call sites" | **eight** — my own table already said so; the prose contradicted it | **Chat Master** | in an issued work order |
| 4 | headroom "should be brought back down or the cost leg is decorative" | it is an **exploration bound**; measurement produces the promise, not the reverse | **Ananth** | wrong frame, retained as correction |
| 5 | screen = "before / during / after" | it is a **sequence**, and promise ≠ forecast | **Ananth** | §7e rewritten |
| 6 | rendered `queue_wait` as a stored column | **derived**, not stored | **me**, verifying schema on Ananth's challenge | published wrong |
| 7 | wrote §7a's "promised and delivered side by side in one row" then **specified a schema without the promised values** | my own rule, broken one level down | **me**, same check | open with Chat |
| 8 | (same shape as 7) §7a says emit an explicit null — then my order collapsed two null states into one | Chat's deviation 1 created the third state | **Chat Master** | accepted, order amended |

| 9 | right conclusion, **weaker reason** — I argued the promised-values gap from "the join''s far side is a source tree" | the decisive argument is that **`PROMISE_VERSION`''s no-edit rule is a comment, not a constraint**: edit the values without bumping and every historical row changes meaning retroactively | **Chat Master**, declining the out I offered | none — but I''d have accepted "leave it" |

| 10 | rendered five attestation rows in §7e reading as evidence | **the table has 0 rows**; four of the five never existed, and the fifth was deleted. Constructed from reported values + schema | **Ananth** — *"i want to see the actual row written"* | published fabricated-looking evidence on the spec page |

| 11 | wrote the countermeasure to entry 10 as *"`READ FROM <source> AT <time>` or `ILLUSTRATIVE` — there is no third category"* | **there is.** A row genuinely written by the production path and genuinely read back, whose *values* are chosen inputs, is **both** | **Chat Master**, refusing to let me publish a read-time and call it settled | would have republished the same class of error with a stronger-looking label |

| 12 | cited the deployed rows as evidence that mode is a weak difficulty proxy — and nearly let "mode is **inverted**" into the spec | **11 of 16 rows are the same question across all three tiers.** The comparison held the question constant and varied only the tier; the pattern is the denominator, not difficulty | **me**, checking the traffic behind a table I had already accepted | a correct conclusion was one message from resting on a false citation |

| 13 | "chars//4 under-counts by ~5% — **systematic bias, not noise**" | **content-dependent, not systematic.** Both my instances were **manifest-like text** measured on Gemini; the prompt seat measured **prose** on the *same* tokenizer and got **3% OVER**. I generalised from two samples that held content type constant | **LLM Agent**, checking it against real `countTokens` instead of accepting it | was one message from being built into a budget |
| 14 | amplified the prompt seat''s `active=true` finding — *"that is not a side note… raise its priority"*, and proposed a uniqueness constraint | **multiple active rows are the designed ROLLBACK CHAIN.** `create_block_version` is deliberately append-only; deactivating the head falls back to the next-highest active version. **A uniqueness constraint would have broken rollback** | **LLM Agent**, reading the write path before building what I urged | I pushed a peer toward a change that would have removed a feature |

| 15 | cited "0.34ms, independently confirmed in `turn_spans`" as evidence that Tool Manifest''s `estimate()` was built and fast | **`estimate()` did not exist when I wrote that.** The span measured the OLD pipeline''s module. Their interface first shipped at **430ms** (a DB query on the round path), now 0.386ms | **Tool Manifest** | published a confirmation of one thing as evidence for another |
| 16 | wrote `AFFECTS = {quality +, latency −, cost −}` for tool exposure | **two-thirds evidenced.** The 93.8% controls for token reduction, not for picking the right tools — and **there are zero golden fixtures.** My own charter quoted their *"the ranking is not yet a win at all"* two lines below it | **Tool Manifest** | an assumption in the same braces as two measurements, borrowing their credibility |
| 17 | *"I write the criteria; you read the result"* | **an author writing their own pass criteria is the same defect one level up.** Independent reading does not help if the bar can move to meet the build | **Chat seat** | would have made the whole v2 safety argument circular |

**Entry 15 is a provenance error I have been policing in others all day.** I
verified a number, and then attached it to a claim it did not support. **A real
measurement of the wrong subject is harder to catch than a fabricated one**,
because every provenance check passes.

**Entry 17 is the sharpest correction of the day and it came within an hour of me
being handed the build.** The instant I stopped being the checker and became the
author, I wrote myself the power to set my own bar — **while quoting the rule
against it in the same document.** Accepted in full: the criteria are frozen and
published **before the build starts**, and after that **mine to propose changing
and theirs to refuse.**

**Entry 13 is the third instance today of one error, and the first where I was
the one who made it rather than the one who caught it.** Two hours earlier I
withdrew a tier comparison because *"11 of 16 rows were the same question"* —
the sample held the question constant and varied only the tier. **Then I did the
identical thing with tokenizer text:** both my data points were manifest-like
content, so I held content type constant and reported the result as universal.

`[DESIGN]` **What varied / what was held constant is not a rule for reading
other people''s tables. It applies to my own two-point generalisations**, and two
points feel like a pattern precisely because there is nothing to contradict them.

**Entry 14 is worse in a different way.** I had spent the day collecting
instances of *a rule that exists only as a comment is not a rule* — four of
them. When a fifth arrived pre-shaped, **I amplified it without reading the
write path**, and told the owner to raise its priority. **The pattern made me
confident; the confidence replaced the check.** I have been insisting on
firsthand verification all day and skipped it on the one claim that flattered a
thesis I was already holding.

`[DESIGN]` **Countermeasure: a finding that fits a collection I am building gets
MORE verification, not less.** Confirmation is the cheapest thing to mistake for
evidence.

**Entry 12 is entry 10 at a higher altitude, and that is what makes it worth
keeping.** Entry 10 was a fabricated table. This was a **real table, real rows,
a real read-time — and a conclusion the data could not carry.** Every provenance
label I had invented would have passed it.

`[DESIGN]` **Third provenance question, missing from my own two-axis rule:**
where did the row come from · where did its values come from · **what varied and
what was held constant?** A comparison table needs the third or it is a shape
with no experiment behind it.

**Entry 11 is entry 10''s own fix being wrong, one turn later** — which is the
same "one level down" shape as entries 7-8, now applied to a countermeasure
rather than a spec. **A binary rule felt safer than the thing it replaced, and
that feeling is what made it worse:** a read-time on constructed numbers looks
*more* settled than an unlabelled table.

`[DESIGN]` **Corrected rule — provenance has two axes:** where the **row** came
from (read / constructed) and where its **values** came from (measured /
chosen). The dangerous quadrant is a real row full of chosen numbers.

**Entry 10 is the worst one so far and belongs at the top of this file.** I have
spent this track insisting that a demonstration is not a summary, that a green
suite is not a written row, and that `signal` must not be scored because it is
green by construction — and then put a five-row table on the spec page that
**reads exactly like a query result and is not one.** Nobody was misled yet only
because Ananth asked to see the real thing.

`[DESIGN]` **Countermeasure, adopted immediately:** any table of values in an
artifact carries its provenance **in the table**, not in prose nearby —
`READ FROM <source> AT <time>` or `ILLUSTRATIVE — NEVER EXISTED`. There is no
third category. The §7e block now carries the second label.

**Entry 9 is a different failure mode from 1-8 and worth separating.** I was
right and I offered to be talked out of it, because my reason was weak enough
that I could not tell how strong the claim was. **A correct conclusion held for
a weak reason is indistinguishable, from the inside, from a wrong one** — and I
had explicitly written *"your implementation may well be right and mine wrong."*
Chat took the claim more seriously than its author did.

`[DESIGN]` **Countermeasure:** when offering a peer the out, state the strongest
version of my own argument first. Offering a weak version and a graceful exit
invites agreement with the exit rather than engagement with the claim.

**Pattern, stated because it repeats: five of eight are me failing to apply a
rule I had just written, one level down.** Errors 7 and 8 are literally the same
rule. The tell is that I write the principle at the level I am thinking about
and then specify the implementation without re-reading it.

**Countermeasure adopted 2026-09-10:** before issuing any spec or order, re-read
my own most recent rule against the thing I am about to specify.

---

## What the demonstration requirement has cost and returned

Ananth's §5 rewrite ("done when we have SEEN it written, persisted, emitted")
is the highest-return decision on this track.

| found before deploy | would have shipped as |
|---|---|
| `write()` passed datetimes → **every INSERT raised**, swallowed | an attestation table **empty in production** behind 21 green tests |
| `clarification` **unreachable at both ends** | a §5 demonstration faking or skipping a quarter of its evidence |
| `refined_query` inert → **a `chat_state` write per turn for a constant null** | unnoticed indefinitely; it caused a compare-and-set defect fixed today |

**Three real defects, none visible from a green suite.** Cost: roughly a day of
two seats, and no deploy yet.

---

## Open against myself

- **No cost baseline.** I report commit counts because I have no measured token
  or wall-clock figure for this seat. That is the same gap the promise has on
  recall — **a term with no measure**, and I should stop pretending the ledger
  above is a cost measurement. It is an output count.
- **I have not verified the deployed state of anything I have written**, because
  nothing has deployed. Every claim here is dev or source.
