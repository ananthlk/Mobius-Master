# Exit modes out of react — the last posture question

Ananth, 2026-09-11: *"react should say I was able to understand a,b,c while x,y,z
remain open… I ran out of time… I can do this and close x,y,z if you like —
automatic continuation of the question. This is the exit mode out of react…
successful complete · unsuccessful because of budget · unsuccessful because of
lack of tools · unsuccessful because of system errors. What do we do under
each?"*

---

## 1. Exit mode is NOT the same axis as `outcome` — both are needed

The attestation shipped today records **mechanical** outcome:
`completed` · `failed` · `empty_payload` · `unknown` — *did the code finish?*

Ananth''s four are **semantic**: *did we deliver the promise, and if not, why?*

**A turn can be mechanically `completed` and semantically `unsuccessful —
budget`.** Those are the common case, not an edge case. So the attestation needs
a second field:

```
outcome     completed | failed | empty_payload | unknown     ← did the code finish
exit_mode   complete | budget | capability | error          ← did we deliver
```

**Collapsing them would be the mistake.** A conformance report built on `outcome`
alone says *"we completed 98% of turns"* while never saying *"and 40% of those
shipped with open gaps."* That is green-by-construction, which this program has
found twelve times.

---

## 2. The four modes, and what changes between them

| mode | detected by | what the user is told | continuation? |
|---|---|---|---|
| **COMPLETE** | no material gap open | the answer. **Nothing about the promise** | no |
| **BUDGET** | gaps open, budget spent | *"I established a, b, c. x, y, z remain open — I ran out of time. I can close them if you like."* | **YES — and it is cheap** |
| **CAPABILITY** | every attempt on the gap returned nothing, or Tool Manifest refused | *"I have no source for x. What would answer it is …"* | **NO — see §3** |
| **ERROR** | exception on the pipeline path | *"Something failed on our side."* | **yes, but the gap list is not authoritative** |

### Why BUDGET continuation is cheap, and only became so today

The ledger is **thread-scoped** (Ananth, same session). So accepting *"close
x,y,z"* starts a turn that **skips FRAME and DISCOVER entirely** and opens at
`EXPLORE/CLOSE(x)`. The gaps are already named, already carry `attempted_by`, and
already know which levers failed.

**That is the whole argument for thread scope made concrete:** the continuation
offer is only honest if the next turn actually starts where this one stopped.
Turn-scoped, *"I can close them if you like"* would mean rediscovering from
scratch — the same 20–24% closure odds as any other round, with the user told it
was a continuation.

---

## 3. 🔴 CAPABILITY must NOT offer continuation — and this is the sharpest distinction

**Offering *"shall I try again?"* when no tool can answer is the worst available
outcome.** It spends the user''s patience and our budget on a guaranteed
failure, and it is *more* damaging than saying nothing, because it implies the
answer is reachable.

**Distinguishing CAPABILITY from BUDGET requires knowing why the gap did not
close** — which is exactly what `attempted_by` on the gap provides:

| evidence | mode |
|---|---|
| attempts were **cut off** — budget ran out mid-gap | **BUDGET** → offer continuation |
| every attempt **ran and returned nothing** | **CAPABILITY** → do not offer |
| Tool Manifest **refused** — no tool fits the promise | **CAPABILITY**, and it names the constraint |

**Without `attempted_by` these two are indistinguishable**, and the system
defaults to the flattering one: *"I ran out of time"* sounds better than *"we
cannot answer this."* **That default is a lie the ledger prevents.**

### CAPABILITY exits are a roadmap, not a failure

A gap that exits CAPABILITY **across multiple threads and users** is the
strongest product signal this system can produce: it names a source we do not
have, in the user''s own words, with the attempts that failed attached.

`[DESIGN]` **This is where "gaps closed" stops being a quality metric and becomes
a build queue.** It also closes the loop on Tool Manifest''s refusal design —
they asked that refusals be *"explicit and reasoned, not a thin set."* **The
reason is what turns a refusal into a roadmap item.**

---

## 4. ERROR — continuation yes, gap list no

A turn that threw did not finish judging its evidence. **Its `gaps_open` is
whatever the last completed round asserted**, which may be stale or wrong.

So: offer the retry, **do not present the gap list as a finding**, and mark the
ledger entries provisional. `[DESIGN]` **An error must not silently promote a
half-judged gap list into thread-scoped state** — that would persist a wrong
gap into every subsequent turn in the thread, which is the most expensive
possible place to be wrong once the ledger outlives the turn.

**This is new risk created by thread scope**, and it did not exist when gaps died
with the turn.

---

## 5. What each mode writes

| field | why |
|---|---|
| `exit_mode` | the semantic answer |
| `gaps_open_at_exit` | ids, not a count |
| `gaps_closed_this_turn` | ids — **credit goes to the closing turn** |
| `continuation_offered` | bool — **so we can measure whether offers are accepted** |
| `capability_gaps` | ids exiting CAPABILITY — **the build queue** |

**`continuation_offered` is the one I would not skip.** An offer nobody accepts
is a worse answer dressed as a helpful one, and it is measurable from the first
day. If acceptance is near zero, *"I can close these if you like"* is noise and
should be replaced by closing them or saying we cannot.

---

## 6. Where this lands in the posture sequence

```
FRAME ──► EXPLORE ──► NARROW ──► VALIDATE ──► COMMUNICATE
                        │
                        └─ decides the EXIT MODE, and COMMUNICATE delivers it
```

**NARROW is where the exit mode is chosen** — it is the posture that decides what
is in scope, which is the same decision as deciding what is being left open and
why. **COMMUNICATE then says it.** Neither is a new posture; the taxonomy tells
NARROW what it has to determine and COMMUNICATE what it has to say.

`[OPEN]` **COMPLETE is the only mode that says nothing about the promise.** The
other three all require the answer to carry an account of itself — which means
`react.communicate` needs a slot for it, and that is a schema question for the
prompt seat, not a prompt-wording one.
