# v2 — the A/B design, and what it should save

`[RULED]` Ananth, 2026-09-11: *"we should make an estimate of savings here and
try A/B with the old router to make sure we see it — across all aspects of the
promise. We should route A/B for a while to do that."* And: *"prominently display
which version it is so that I can follow."*

---

## 1 · A/B replaces phased routing, and my phased plan was confounded

**I specified:** `R1 = single-round fast only`, v1 keeps everything else.

**That compares v2-on-fast against v1-on-everything.** Version is confounded with
tier, with turn shape, and with whatever traffic happened to arrive in each
window. **It is the same defect I withdrew a tier comparison for this afternoon**
— 11 of 16 rows were one question fanned across three tiers, and the pattern was
the denominator, not the finding.

**A/B fixes it by construction:** same tier, same window, same traffic
distribution, **version assigned at random.**

```python
# at POST, once, recorded on the attestation
orchestrator_version = "v2" if hash(correlation_id) % 100 < AB_PCT else "v1"
```

**Deterministic on `correlation_id`** — so a turn cannot flip mid-flight, a
retry lands on the same arm, and the assignment is reproducible from the row
alone.

**Still route, never fork.** One decision at POST; no turn is ever handled by
both.

### Ramp

| stage | v2 share | purpose |
|---|---|---|
| **R0** | **0%** | shadow — v2 computes, v1 decides, both emit, equality asserted |
| **R1** | 5% | does anything break |
| **R2** | 25% | the comparison window — **this is where the numbers come from** |
| **R3** | 50% | confirm at scale |
| **R4** | 100% | v1 retires |

---

## 2 · Estimated savings — per promise term, with the arithmetic shown

**Every input is `[MEASURED]`. The estimate is arithmetic over them, and it is an
estimate — it is exactly what the A/B exists to falsify.**

### LATENCY

| source | saving | applies to | measured basis |
|---|---|---|---|
| **LLM card writer skipped** | **−5.2s p50 / −10.3s p90** | **82% of turns** (1,239/1,514 have zero gaps at round 1) | enricher 5.2s/10.3s; `deterministic_format()` already exists |
| **stuck-gap rule** | **−78s** net (88.6s after the rule fires, minus ~1 NARROW round ≈ 10.3s) | **21.7%** of multi-round turns (182/837) | fires at round 4.5 avg; 66.7% of the turn follows it |
| tool manifest | (already live, **not v2's credit**) | all | 890 vs 14,271 tok |

**Expected on `fast`:** `1 round + enricher = 12.9s p50` → `7.7s` — **−40% of a
13s promise.**

### COST

| source | saving | applies to |
|---|---|---|
| enricher prompt not composed | **−4,028 tok** | 82% of turns |
| rounds not bought | ~**−2 to −7 rounds** × round cost | 21.7% of multi-round turns |

⚠ **Cost is understated on both arms equally** — `react_1` reports cost on
**686/1,236** calls. **The A/B delta is still valid** (same bias on both sides);
**the absolute figure is not.** Report the delta, never the total.

### QUALITY

> **No saving is claimed, and none may be.** Recall has no measure; `AFFECTS`
> for tool exposure was corrected to `quality: UNMEASURED` today for exactly this
> reason.

**Quality appears in the A/B only as a GUARD**, never as a win:

- `gaps_closed_per_turn(v2) ≥ v1` — **v2 must not buy fewer answers for its
  better latency**
- `CAPABILITY_rate(v2) ≤ v1` — **a rise means v2 stopped reaching tools**

**Every other metric improves when v2 does less.** Latency, cost and conformance
all move the right way if v2 quietly stops working. **These two move the wrong
way, which is what makes them the test and the rest the dashboard.**

---

## 3 · What the A/B must control for — the part that is easy to get wrong

| control | why |
|---|---|
| **same window** | cold-start is bimodal (13 warm @ 0.023s, 3 cold @ 3.76s). Run the arms **concurrently**, never sequentially |
| **same tier mix** | report **per tier**; a shift in mode distribution between arms would masquerade as a v2 effect |
| **exclude self-generated traffic** | `[RULED]` chat seat: *v2 must not pass on traffic v2 generated.* **A sample you constructed yourself passes every provenance check** |
| **exclude `VERIFY-ROW%`** | already in the §5 queries |
| **report distributions, not just p50** | a p50 called the queue wait negligible and was wrong about 1 turn in 5 |
| **state what varied** | version. **Nothing else may vary between arms** |

---

## 4 · Version display — visible in three places

`[RULED]` *"prominently display which version it is so that I can follow."*

| surface | where | shape |
|---|---|---|
| **the stream** | **first emit of every turn**, before anything else | `▣ v2 · normal · promise 31s ±8 · postures: FRAME→EXPLORE→NARROW→COMMUNICATE` |
| **the row** | `turn_attestations.orchestrator_version` | `v1` / `v2` — **the join key for the whole comparison** |
| **every decision emit** | prefix | `v2 · round 3 · CLOSE(G3) — …` |

**Why the first emit and not a footer.** The version has to be visible **while
the turn is running**, not discovered afterwards — otherwise a slow turn cannot
be attributed to an arm without a query. **And it is the cheapest possible
guard against the confound**: if a turn looks wrong, the first line says which
orchestrator to blame.

`[DESIGN]` **`orchestrator_version` is cheap now and expensive after 200 turns**
— the chat seat's point. The attestation is written from `run_pipeline`'s
outermost `finally`; **whichever orchestrator owns that `finally` owns the row**,
so without the column the comparison cannot tell which arm produced which row.

---

## 5 · Reading the result

**Stop and investigate on ANY of:**

```
in_band(v2)              <  in_band(v1)              same tier, same window
CAPABILITY_rate(v2)      >  CAPABILITY_rate(v1)      v2 stopped reaching tools
gaps_closed_per_turn(v2) <  v1                       fewer answers for the latency
turns != rows  OR  duplicates > 0  OR  queue_wait < 0
unknown_outcomes         >  0
```

**Advance only when all hold over ≥200 turns per arm.**

**And the estimate in §2 is a prediction to be falsified, not a target to be
hit.** If the A/B shows less, the estimate was wrong — **do not go looking for
the missing saving.** Four claims were withdrawn today for reasoning backwards
from a number someone wanted.
