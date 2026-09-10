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

**Cost so far: 27 commits across 3 artifacts. Zero lines of production code —
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
