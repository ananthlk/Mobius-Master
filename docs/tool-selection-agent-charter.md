# Tool Selection Agent — charter and handoff context

**For: a new Claude seat, standing up `tool_manifest 2.0` in its own repo, with its own
DB, guarding its own boundary — the way the RAG module does.**

**From: the Platform seat (mobius-c2), 2026-09-10. Written to be read cold.**

You have no session context. This document is self-contained. Where a number appears, it
says how it was obtained; where I was wrong, it says so, because several of these findings
are corrections of my own earlier claims and you should know which parts have already been
through one revision.

Two companion documents, both in `Mobius/docs/`, both written to the same standard:
- **`tool-manifest-schematic.md`** — the evidence base. What the current node is, measured.
- **`tool-manifest-2.0-spec.md`** — the design, with every choice citing the measurement.

---

## 1. What you are being handed

**Chat's planner (`react`) is given a catalogue of every tool on every round, and picks
from it. You are taking over the picking.**

Today that catalogue is a hand-written prose blob in
`mobius-chat/app/pipeline/tool_manifest.py` — **737 lines** producing **one string** that
goes into the planner's prompt. It dispatches nothing and decides nothing. Its only output
is text a model reads.

**Your job: replace "hand the model everything" with "hand the model a short ranked set,
with reasons, chosen deterministically."**

---

## 2. What exists — measured, not asserted

### 2.1 The catalogue is twice the size of the code, and a local render lies

| | tools | ~tokens |
|---|---:|---:|
| **static** — written in `tool_manifest.py` | 28 | ~6,906 |
| **auto-discovered from MCP** at chat startup | 29 | ~6,520 |
| **production total** | **57** | **~13,062** |

Two independent measurements agree: I counted 57 tool signatures in the live
`GET /chat/skills-manifest` render; the Chat seat counted 58 entries from `turn_spans`
(57 tools + one `__unfiltered__` sentinel).

**🔴 The trap you will hit on day one:** `get_manifest_tool_names(None)` on a dev machine
returns a **plausible 28-item list and no error**, because MCP tools register at FastAPI
startup against services a laptop cannot reach. **The local render does not fail — it
silently returns half the catalogue.** Every conclusion drawn from source or a dev render
is missing 51% of the object with no way to know it.

### 2.2 The manifest is 35.8%+ of every planner prompt

Measured with the provider's own `count_tokens` against the 28-tool **local** render:
**8,137 tokens, 35.8% of the average react prompt, and up to 63.9% of the leanest.** It
renders **once per ReAct round**, not per turn — ~16,681 tokens per turn at 2.05
rounds/turn.

**That figure is a FLOOR.** It was measured against 28 of 57. Do not restate 35.8% as the
number; re-measure in situ.

### 2.3 Twenty-nine tools have never been called. Not once.

`tool.emitted` / `tool.dispatched` / `tool.result` for all 29 MCP tools: **0 rows** across
the entire recorded window.

**Half the catalogue, offered on every round, emitted zero times.** That is a stronger
argument than "they're broken", because it requires no bug to be true — if they all
dispatch perfectly, the token bill is identical.

**The caveat is load-bearing and it is the Chat seat's, not mine:** *"never emitted in the
window" is not "never useful."* The window was appeals/rates/policy traffic; these are
market/benchmark analytics. **The fair test is a turn they should serve** — *"what's the
market size for behavioral health in Tampa"* — and **it has not been run.** "Half the
catalogue is dead weight" and "half the catalogue was never asked for during a week of
appeals questions" are different conclusions and only one justifies deleting anything.

### 2.4 The failure that started this, and its real cause

A real user turn: ***"how do i appeal a carc 197 denial for sunshine health."*** Chat
answered *"our resources don't have specific instructions"* and rendered no card.

**The playbook exists.** `GET /playbook-guarded/Sunshine%20Health/197?audience=provider`
returns id 55, `PRECERT`, deadline 90 days, portal, fax, mailing address, five appeal
levels.

I found an argument-precedence bug in chat and it was fixed and deployed. **The turn still
fails, and my fix was never exercised.** Post-deploy telemetry:

```
tool.offered   appeals_get_playbook   1     ← offered
tool.emitted   appeals_get_playbook   —     ← NEVER CALLED
tool.emitted   appeals_lookup_rules   2
tool.result    appeals_lookup_rules:no_sources  2
```

**The model was offered the tool with the answer and did not call it.** And the manifest
tells it not to: `appeals_lookup_rules`' description documents *"how do I appeal CARC 22"*
and *"rules for CARC 29 timely filing denial **from Sunshine Health**"* — a near-verbatim
match for the user's sentence, payor included. `appeals_get_playbook` says only *"PREFER
THIS over rag"* — over rag, never over its sibling.

**The model followed the manifest correctly. The manifest is wrong.** No test could catch
it, because the manifest is prose.

### 2.5 The measurement you should trust least of your own instincts on

**BM25 over the live descriptions ranks the wrong tool first by 4.6×** (5.450 vs 1.184).
Query terms appearing *only* in the competing tool's text: `denial`, `do`, `i`, `health`,
`sunshine`. **The prose that misleads the model misleads retrieval by the same
mechanism** — one entry harvested the other's query shape as its own example.

**So similarity over the planner prose reproduces the bug faster and more confidently.**
Whatever corpus you match against, it must not be text written to steer a model.

---

## 3. What is already proven to work

All measured against the **live** 57-tool manifest. No code was built.

**Shortlisting works; selection does not.** BM25 puts the right tool at **#4 of 57** — but
inside the top 5, with 4 of 5 in the right family. **Reframe: react today picks 1-of-57;
a shortlist makes it 1-of-5-already-relevant. Those are different asks.**

**Token reduction, three queries: −85%, −93%, −87%.**

**Three tiers, and the tier changes the mechanism not the score:**
- `default` (`rag`, `recall_evidence`) — **always present, a floor, not a competitor**
- `specific` — admitted on clearing an **absolute** floor; if nothing clears it, **serve
  defaults only**
- `utility` — not domain-selected

A relative threshold alone admits noise, because 35% of a weak top score is weaker. With
an absolute floor, *"what is prior authorization"* correctly returns **defaults only, 2
tools, −93%**.

**Three signals, each covering a gap the others leave:**

| signal | strong at | blind to |
|---|---|---|
| **Lexicon tags** (`d:`/`p:`/`j:`) | entity and domain — `j:payor.sunshine_health` resolves exactly | implied intent — **no `p:` tag fires on *"how do i appeal"*** |
| **BM25** | exact procedural terms — *deadline/submit/filing* → playbook **#1** | harvested example text; short generic queries |
| **vector** (`text-embedding-004`, 768-dim) | short generic queries; different wording | **blurs the exact terms that discriminate siblings** |

**The counterintuitive result: BM25 beats vector on the procedural query.** Vector put the
playbook #2; BM25 #1. Embeddings dissolve *deadline/submit/filing* into a general
"appeals" topic. **Fuse by reciprocal rank (RRF), not weighted score** — no magic constant
on an unnormalised scale.

**Cleaning the descriptions helps both signals.** Rewriting the five appeals tools as
*"describe the tool and its best use"* — no priority language, no trigger tables, **no
example queries** — made the appeals block **72% smaller** (5,448 → 1,548 chars) and moved
the procedural query to **unanimous #1** on vector *and* BM25. **The harvested examples
were corrupting the embedding too, not just BM25.**

---

## 4. What you are being asked to build

A **deterministic per-turn selector**: four stages, each a pure function of declared
inputs. No model in the loop, so fixtures either pass or fail.

```
A  authority   caller ∩ mode ∩ visible_to_planner ∩ subscriptions   → hard filter
B  requires    drop tools whose required tags do not resolve        → hard filter
C  score       tag overlap + BM25 + vector, fused by RRF            → rank
D  admit       defaults always · specific over an absolute floor
               · top-N budget-derived · each with ITS REASON        → render
```

**Two rules that are not negotiable, and both have a reason:**

**Authority and `requires` are filters, never rank inputs.** A high-relevance tool must not
outrank its own permission boundary, and a tool that cannot function must be *excluded with
a stated reason* rather than ranked low — because a low-ranked tool still surfaces on a
thin turn and then gets called without what it needs.

**Emit the reason, and persist it.** A selection nobody records is a producer with no
consumer. Chat's existing `tool.offered` span recorded the string `__unfiltered__` — the
fact that no filter ran — rather than what was on offer, and that single choice is why a
day of investigation could not answer "was the tool offered?"

---

## 5. What you own, what you guard, and what you must not own

**Yours:**
- the **catalogue snapshot schema** and the tool **declarations**: `tier`, `subscribes`,
  `requires`
- the **selector** and its scoring
- the **golden set** — *this is the real prerequisite and it is currently unowned*
- the **UX**, which is the test surface, not a demo
- the **fixture suite** and the **collision test**
- your **DB**: declarations, tool embeddings + the text they were embedded from,
  the golden set, fixture results, A/B assignments, selection history

**Not yours, and do not absorb them:**
- **dispatch** — stays in `mobius-chat/app/pipeline/react_loop.py`. A tool being selected
  is not evidence it works.
- **MCP registration** — happens in chat's FastAPI startup. You cannot see it; you consume
  an export.
- **authority source of truth** — `user_tool_subscriptions` is chat's table.
- **the Lexicon** — owned by RAG/Curation. You consume tags; you do not add them. Payor
  coverage grows with onboarding and is *not* a constraint you design around.
- **the descriptions' semantics** — each tool's owner writes what it does. You own the
  *shape* and the collision test, not the prose.
- **answer quality** — Eval's, and out of scope for the invariant set.

**🔴 The one boundary that will bite you:** a standalone selector cannot see half the
catalogue (§2.1). **Chat exports the catalogue; you consume the export.** The snapshot must
carry `exported_at`, the chat revision, and the tool count — and **a run against a snapshot
older than the deployed revision must fail loudly, not proceed.** Three artifacts in this
system decay the same way and all three have bitten someone this week: the snapshot, your
tool embeddings (a description that changes without re-embedding ranks on stale meaning),
and Lexicon tag versions.

---

## 6. Phasing, and why the order is this

| phase | what runs | exit |
|---|---|---|
| **−1 standalone** | library + CLI + UX against a snapshot | no chat import · six UX panels · fixtures with an owner · collision test over all 57 · stale snapshot fails loudly |
| **0 shadow, brief** | you compute, chat serves | recall vs tools react actually called ≥ 99%, **every miss read by name** |
| **1 A/B — THE GATE** | you serve one arm, **sticky by thread** | cost · latency · accuracy tradeoff |
| **2 default** | you serve; 1.0 retained one full cycle | |
| **3 round N** | governor gaps + tried-tools feed stage C | last, and most valuable |

**The A/B is the gate, not shadow** — shadow cannot measure latency, cost or accuracy,
because chat still serves the manifest. **Assign by THREAD, not turn**: context, gaps and
cost carry forward within a conversation, so a mid-thread split blends arms.

**The three metrics do not decide together.** Cost is near-deterministic and decidable in
**tens** of turns; latency is noisy and decidable in **hundreds**, p50 only; accuracy needs
Eval's judge over a bank. **And the honest latency claim is on prompt processing, not
turn-wall** — a 12,000-token reduction against a 78-second continuation turn is noise, so a
flat turn-wall p50 is *not* a failure. Pre-declare that or a real win reads as a null
result.

**Fail open to chat's full manifest, and count it.** A *gate* decides what is allowed and
fails closed; a *selector* decides what is offered and its worst case is today's behaviour.
But **alert on the fallback rate** — a selector silently falling back every turn is
indistinguishable from one never enabled.

**Round-N is last because it is the most valuable and the least grounded.** The CARC 197
turn is a **round-N failure**: the loop called one tool, got `no_sources` **twice**, held
the same two gaps for **three rounds**, and never tried the sibling sitting in the
manifest. Fixing rank does not fix that. But it depends on `tool.result` history that only
began existing 2026-09-10, and on the governor's gap state being **stale by one round by
construction**.

---

## 7. Discount these, because they are mine and they were wrong

Stated so you calibrate the rest of this document rather than trusting it evenly.

- **I invented a "domain" taxonomy** by classifying 57 tools on name prefixes, concluded
  "analytics is 45% of the catalogue", and reasoned from it. It had no owner and no
  existence in the system. Ananth discarded it and pointed at the Lexicon instead. **The
  tier membership in §3 is also mine and is unratified.**
- **I argued the `p:` axis would break the playbook/rules tie.** Then measured it: **no
  `p:` tag fires on *"how do i appeal"***, only on explicit procedural language. The axis
  is right and does not fire when you need it most.
- **I closed two findings on the precedence fix** before checking whether that mechanism
  was the one actually firing. It wasn't. Both reopened.
- **Four of my own detectors were wrong in one day**: a telemetry regex that missed the
  very convention it was built to measure, a swallow detector that counted handing an error
  *up* as swallowing it, a signals path pointing at a dead scratchpad, and a reachability
  check built as transitive closure.
- **I reported deploy state from stale checks three times**, once claiming an 11-hour
  silence that was a 6-minute-early check.

**The habit that caught all of these: run the thing, and re-check at the moment of
reporting.** A grep proves presence, never execution. A point-in-time check is not current
state.

---

## 8. Open questions, with owners

| # | question | owner |
|---|---|---|
| 1 | **the golden set — who owns it, how many fixtures before the ranker is trusted** | **unowned. This gates everything.** |
| 2 | `tier`/`subscribes`/`requires` for the 28 static tools | each tool's semantics owner |
| 3 | same for the 29 MCP tools — server-declared in `list_tools`, or your override table? | contract with the MCP team |
| 4 | do the 29 market tools dispatch at all, and are they selected on a market query? | one turn; halves the catalogue either way |
| 5 | which corpus each signal reads — return-field semantics, tags, or curated triggers? | yours |
| 6 | absolute floor and top-N — normalised how? | yours; a magic constant on a raw score is a smell |
| 7 | re-embed on description change — who triggers it? | yours |

**Question 1 is the one that gates the rest.** A deterministic selector with no ground
truth is *reproducibly* wrong. Shadow-mode recall is a partial substitute — production
calls as labels — but it can only tell you that you dropped a tool react wanted. **It
cannot tell you react wanted the wrong tool, which is the actual CARC 197 failure.**

---

## 9. First week, if it were me

1. **Get the export before anything else.** Without it you are building against 28 of 57
   and will not know.
2. **Build the UX before the ranker.** The signals panel — tag/BM25/vector side by side,
   **losers included** — is what makes every later disagreement legible. BM25 and vector
   win opposite query types; a UI showing only the fused result hides the most diagnostic
   thing on the screen.
3. **Write the collision test third.** It is the property that survives the tool explosion
   Ananth is planning for, and it is the one thing prose could never give us: a new tool
   that collides with an existing one **fails a test rather than a live turn**.
4. **Then the ranker.** It is the easy part, and everything above tells you whether it
   works.
