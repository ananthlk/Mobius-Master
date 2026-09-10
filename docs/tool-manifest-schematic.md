# `tool_manifest` — schematic

**Status: IN PROGRESS. Section 1–4 written 2026-09-10. Not reviewed by Chat Master yet.**
**Author: Platform seat. Every claim carries a line reference and how it was established.**

---

## 0. Why this document exists, and how to read it

Ananth, 2026-09-10: *"we will deal with tools_manifest methodically by going line by
line and creating a ux and understanding what it does and what it does not.. we need a
schematic developed first — I CANT TRUST YOU GUYS.. so we will do that with proper
documentation."*

**The distrust is earned.** In one day I reported stale deploy state three times, shipped
a blank schema page, closed two findings on a mechanism that was never exercised, and
had four of my own detectors wrong — a telemetry regex that missed the very convention
being measured, a swallow detector that counted a hand-up as a swallow, a signals path
pointing at a dead scratchpad, and a reachability check built as transitive closure.

So this document is written to be checkable without me. **Every claim is tagged:**

| tag | means |
|---|---|
| **[READ]** | I read the code at the cited line. Says nothing about runtime. |
| **[LIVE]** | I observed it from the deployed service. |
| **[MEASURED]** | A number I computed, with the method stated. |
| **[ESTIMATE]** | An approximation, with its method and error stated. |
| **[UNVERIFIED]** | I believe it and have not established it. Do not act on these. |
| **[REPORTED]** | Another seat told me. Not independently checked. |

**No fixes are proposed in this document.** Ananth's instruction is understanding first.
Where I see a defect I record it and stop.

---

## 1. What the file is

`mobius-chat/app/pipeline/tool_manifest.py` — **737 lines** [MEASURED: `wc -l`].

It builds **one string**: the catalogue of dispatchable tools that goes into the
planner's prompt. It dispatches nothing, calls no tools, and makes no decisions. Its
entire output is prose the model reads.

**This is the first thing to hold onto:** the node is a *prompt fragment generator*. Its
failure mode is not a crash or a wrong return value — it is **the model being told
something misleading**, which surfaces three layers away as a wrong tool call. Nothing in
the file can be unit-tested for correctness of meaning.

Public surface [READ, `:664`–`:737`]:

| symbol | line | what it does |
|---|---|---|
| `get_tool_manifest(allowed)` | `:664` | returns the composed manifest string |
| `get_manifest_tool_names(allowed)` | `:690` | returns the tool names it *rendered* |
| `__getattr__(name)` | `:716` | module-level dynamic attribute access |
| `ENTITY_TOOLS` | `:733` | registry set ∪ hand-listed |
| `FOLLOW_UP_CAPABLE` | `:737` | registry-derived |

`get_manifest_tool_names` exists because a parallel list would drift from what the model
actually sees [REPORTED — Chat Master built it during the P2 telemetry pass].

---

## 2. 🔴 THE PRODUCTION MANIFEST IS TWICE THE SIZE OF THE ONE IN THE CODE

**This is the most important thing in the document and it is invisible from the repo.**

The deployed service serves its own manifest at `GET /chat/skills-manifest` [LIVE — 200,
54,376 bytes]. Reading it:

| | tools | chars | ~tokens |
|---|---:|---:|---:|
| **static** — hand-written blocks in this file | **28** | 27,624 | ~6,906 |
| **auto-discovered from MCP** at startup | **29** | 26,080 | ~6,520 |
| **total in production** | **57** | 53,705 | **~13,426** |

[MEASURED: tool signatures counted as lines matching `^[a-z][a-z0-9_]*\(`, split at the
`── Auto-discovered tools (from MCP) ──` header at manifest line 413.]
[ESTIMATE for tokens: chars/4. Chat Master's `count_tokens` measurement of the static
half was 8,137 against a chars/4 estimate of 8,110 — 0.3% apart — so chars/4 is a sound
approximation here, but these are **not** measured token counts.]

**Consequences, and each is independently significant:**

**(a) Half the catalogue does not exist in the repository.** The 29 MCP tools are
registered at chat startup from a remote server. Nobody reading this file — or grepping
the codebase — can see them. Chat Master measured 28 locally and 58 in prod and could
not reconcile it until they looked at a live turn [REPORTED].

**(b) The P6 baseline of 8,137 tokens / 35.8% of the planner's prompt is a FLOOR, not
the figure.** It was measured against the static half. The real manifest is ~1.65× that
[MEASURED, ESTIMATE]. I have already corrected the finding; the honest position is that
the true share is unknown until someone runs `count_tokens` on the production render.

**(c) A LOCAL RENDER SEES 28 OF 58, AND SUCCEEDS.** [REPORTED + independently
consistent] Chat Master's framing, sharper than mine: `get_manifest_tool_names(None)`
on a dev machine returns a plausible 28-item list and no error, because MCP tools
register at FastAPI startup against services a laptop cannot reach. **The local render
does not fail — it silently returns half the catalogue.** Any conclusion drawn from
source or from a dev render is missing 51% of the object and has no way to know it.
That is the exact failure mode this document exists to avoid, and it would have been
invisible.

**Two independent measurements agree.** I counted 57 tool signatures in the live
`/chat/skills-manifest` render; Chat Master counted 58 entries from `turn_spans`
`kind='tool.offered'` on the deployed revision — 57 tools plus the `__unfiltered__`
sentinel, which is not a tool. Their catalogue is at
`mobius-chat/docs/tool-catalogue-production-observed.md` (`c5088c3`) and records what
production *offered*, not what source says it would. They labelled its own two limits:
it is one window, not an existence proof; and the static-vs-MCP split is inferred from
source, the only claim in it not established by observation.

**26 of the 29 MCP entries are one coherent market/benchmark block from one service** —
`get_market_size`, `get_churn_benchmark`, `get_org_leakage`, `get_msa_map` and the rest
— **offered on every turn, including turns about appeal deadlines** [REPORTED,
consistent with my own count of 26 in §8.3].

**(d) A prompt-cost decision cannot be made from the code.** Any judgement about
"the manifest is too big" that reads only this file is reasoning about 51% of the object.

---

## 3. 🔴 THE `get_*` MARKET TOOLS WERE DELETED FOR ALWAYS 404-ING. THEY ARE BACK.

`:40`–`:56` is a comment recording a deliberate removal [READ]:

> `_FL_MEDICAID_DATA_ROUTING_BLOCK` removed 2026-08-04 (Chat Architecture, live-testing
> regression: agent burned 5 rounds trying `get_published_rates`/`get_rate_benchmarks`,
> both "tool not found"). This block promised ~10 `get_*`/`search_orgs` tools as a
> "read this FIRST" priority routing table, but **NONE of them are backed by a
> registered MCP tool** … A prominent routing table for tools that always 404 is worse
> than no routing table at all. **Restore this … once that service is actually wired
> into `EXTRA_MCP_URLS`.**

**The production manifest now contains 26 of those `get_*` tools** — `get_published_rates`
at manifest line 691, plus `get_rate_benchmarks`, `get_market_size`,
`get_org_profile`, `get_service_mix`, `get_entrant_analysis` and ~20 more [LIVE].

They arrive through the **MCP auto-discovered section**, not through the deleted static
block. So the removal held and the tools returned by a different route.

## 3.1 CORRECTED AND SHARPENED, 2026-09-10 — the premise is stale, and the real finding is better

**The 2026-08-04 premise no longer holds** [REPORTED, Chat Master, from the deployed
environment]. That note's reasoning was *"No MCP URL in dev.env points at whatever
service is meant to provide these market-analytics tools."* Production now has
`CHAT_SKILLS_MCP_URL`, `EXTRA_MCP_URLS` and `MOBIUS_MCP_AUTOREGISTER=1` set, and the
tools arrive via `registry.names_by_source("mcp")`, populated from a live MCP
`list_tools` response. **A server advertised them. They are registered, not phantom.**

Whether every one *succeeds* on dispatch is still unproven — a server can advertise a
tool that errors — and Chat Master declined to claim it without calling one. Correct.

**🔴 But the data answers a better question than "do they 404":**

```
tool.emitted     get_* / search_org* / lookup_npi / search_clinician* / check_provider*   →  0 rows
tool.dispatched  same                                                                     →  0 rows
tool.result      same                                                                      →  0 rows
```

[REPORTED — `turn_spans` across the entire recorded window.]

**Twenty-nine tools — half the catalogue — offered on every single round, emitted zero
times.**

That is a stronger argument than "broken", because **it requires no bug to be true.**
If they all dispatch perfectly, nothing about the token bill changes: their cost is
unconditional and their use is zero. The 58 → 32 reduction and ~6,500 tokens/round holds
on *never selected* rather than on *defective*.

**And the caveat, which is Chat Master's and is the same shape as my `__unfiltered__`
correction** — I am recording it as prominently as the finding, because without it the
finding is an artifact of what we happened to ask:

> *"never emitted in the window" is not "never useful".* These are market/benchmark
> analytics and the observed window is chat traffic about appeals, rates and policy. A
> fair test is whether they are selected on a turn they **should** serve — *"what's the
> market size for behavioral health in Tampa"* — not whether they appear in a window of
> appeals questions.

**That turn has not been run.** It is one turn, it is a test rather than a fix, and it is
the difference between *"half the catalogue is dead weight"* and *"half the catalogue was
never asked for during a week of appeals questions."* **Those are very different
conclusions and only one of them justifies deleting anything.**

**What I do NOT know, and this is the crux [UNVERIFIED]:**
- whether they now **dispatch successfully**, i.e. whether the MCP server that publishes
  them is actually reachable and functional from the deployed service
- or whether we have re-created the exact regression the comment documents — a
  prominent catalogue of tools that 404 — at **twice the prompt cost** and with the
  routing table's warning removed

**This is the single highest-value question in the node** and it is answerable with one
dispatch attempt against the live service. I am not guessing at it. **It belongs in the
comprehensive test.**

---

## 4. The composition path — line by line

[READ throughout this section.]

### 4.1 Static blocks (`:57`–`:461`)

Module-level string constants, one per tool or tool family:

| block | line | note |
|---|---|---|
| `_RETRIEVAL_METHODOLOGY_PRIMER` | `:57` | read once, applies to all search tools |
| `_RAG_BLOCK` | `:73` | |
| `_RECALL_EVIDENCE_BLOCK` | `:118` | |
| `_SEARCH_CORPUS_BLOCK` | `:135` | **`= ""`** — retired, backend routes to `rag` |
| `_RECALL_SEARCH_BLOCK` | `:138` | **`= ""`** — merged into `search_corpus(mode="recall")` |
| `_PRECISION_SEARCH_BLOCK` | `:141` | **`= ""`** — merged into `search_corpus(mode="precision")` |
| `_HEALTHCARE_NPI_LOOKUP_BLOCK` | `:143` | |
| `_SEARCH_UPLOADED_DOCUMENT_BLOCK` | `:162` | |
| `_REFUSE_BLOCK` | `:202` | terminal short-circuit |
| `_APPEALS_BLOCK` | `:231` | **one gate key, five callable tools** — see §5 |
| `_LOOKUP_AUTHORITATIVE_SOURCES_BLOCK` | `:289` | |
| `_INGEST_URL_BLOCK` | `:315` | |
| 8 × `_SERVICE_LINE_*_BLOCK` | `:346`–`:407` | |
| `_AUTO_DISCOVERED_HEADER` | `:464` | header for the MCP section |

**Three blocks are empty strings kept as named constants.** `_SEARCH_CORPUS_BLOCK`,
`_RECALL_SEARCH_BLOCK`, `_PRECISION_SEARCH_BLOCK` are all `""` with a retirement comment.
They render nothing. Whether anything still references them is [UNVERIFIED] — a named
empty constant is exactly the surface that reads as live to a grep.

### 4.2 `_auto_discovered_block(allowed, ...)` — `:473`

Renders the MCP section. This is the function that produces half the production manifest
and zero of the local one.

### 4.3 `_compose_manifest(allowed, ...)` — `:541`

Assembles the blocks in a fixed order. The module docstring states the order is
deliberately preserved because *"any drift in the planner prompt is a behavior change"*
[READ, `:24`–`:27`].

### 4.4 The two entry points — `:664`, `:690`

`get_tool_manifest` returns the string; `get_manifest_tool_names` returns the names
rendered. They must agree, and nothing in the file enforces that they do [READ —
no assertion or shared derivation between them; [UNVERIFIED] whether a test covers it].

---

## 5. What the node does NOT do

Stated explicitly because Ananth asked for it, and because several of the day's wrong
conclusions came from assuming otherwise.

- **It does not dispatch.** Dispatch is `react_loop.py`. A tool appearing here is not
  evidence it is callable.
- **It does not gate.** `allowed` narrows what is *rendered*; the actual permission
  resolution is `orchestrator.py:95` `_resolve_allowed_tools`, reading
  `user_tool_subscriptions`.
- **It does not know whether a tool works.** §3 is the live consequence.
- **It does not prevent two entries from claiming the same query.** [READ — this is the
  L2 cause found 2026-09-10: `appeals_lookup_rules` at manifest `:250`–`:256` claims
  *"how do I appeal CARC 22"* and *"…from Sunshine Health"*; `appeals_get_playbook` at
  `:258`–`:268` says only *"PREFER THIS over rag"*, never over its sibling. Ananth's
  query matched the sibling's examples near-verbatim, payor included, and the model
  obeyed the manifest.]
- **It emits nothing.** Zero log sites, zero telemetry sites on 737 lines [MEASURED,
  `gen_readiness.py`]. There is no record of what it rendered on any given turn.
- **`_APPEALS_BLOCK` is gated on one key while documenting five callable tools**
  [REPORTED — Chat Master, during the telemetry pass: recording only the gate key would
  have shown `appeals_get_playbook` as never-offered on turns the model called it].

---

## 6. Open questions for the review

For Chat Master, as the person who knows the dispatch side:

1. **Do the 26 `get_*` MCP tools dispatch, or do they 404?** (§3 — the crux.)
2. Which MCP server publishes them, and is it in `EXTRA_MCP_URLS` on the deployed
   revision?
3. Do the three empty `""` blocks still have referents anywhere?
4. Is there a test that `get_tool_manifest` and `get_manifest_tool_names` agree?
5. What is the **measured** `count_tokens` figure for the *production* render, so §2's
   estimate can be replaced?

---

## 7. Not yet written

- the UX Ananth asked for (what a maintainer needs to see and change)
- per-tool trigger-phrase overlap map across all 57 entries
- the `allowed`-narrowing path end to end
- what a reader of the planner prompt actually sees, in order

---

# 8. PROPOSED MODEL — deterministic per-turn tool selection

**Ananth's design, 2026-09-10. Written up as a schematic, not a plan. No code.**

> *"every user loaded /api caller — we can shortlist the tools they have access to, this
> is our list.. then a user query comes in.. we have to say this query can be in many
> domains, which domains make sense.. we can do a simple vector match or bm25 match or
> hybrid to get this.. then we pick the top x domains and their tools.. this is what we
> need to build.. the UX should be the place to test it.. in the next turn the governor
> knows the gaps (which is trailing by 1 round as react has not closed after that
> round's execution).. so we should see what happens — this is clearly deterministically
> doable"*

## 8.1 The pipeline

```
  ┌─ STAGE A ── AUTHORITY ─────────────── deterministic, cacheable, no query ──┐
  │  caller identity (user / API key / service)                               │
  │    ∩ supports_modes[chat_mode]                                            │
  │    ∩ visible_to_planner                                                   │
  │    ∩ user_tool_subscriptions  (enable / block per user)                   │
  │  ─────────────────────────────────────────────────────────────────────────│
  │  = THE CALLER'S LIST      "what this caller may ever use"                 │
  └───────────────────────────────────────────────────────────────────────────┘
                                     │
                  query ────────────►│
                                     ▼
  ┌─ STAGE B ── DOMAIN MATCH ────────────────── vector / BM25 / hybrid ───────┐
  │  score(query, domain) for each domain the caller's list covers            │
  │  → rank domains, take top-K                                              │
  │  emit: domain, score, matched terms          ← THE REASON, not just rank  │
  └───────────────────────────────────────────────────────────────────────────┘
                                     ▼
  ┌─ STAGE C ── TOOL EXPANSION + RANK ────────────────────────────────────────┐
  │  tools of the selected domains ∩ caller's list                           │
  │  rank within: trigger match · health · past success · cost · retryability │
  │  emit: ranked tools, each with its reason                                │
  └───────────────────────────────────────────────────────────────────────────┘
                                     ▼
  ┌─ STAGE D ── THE MANIFEST REACT ACTUALLY SEES ─────────────────────────────┐
  │  rank-ordered, reasons attached, ~top-N only                             │
  │  react CONFIRMS against what it needs — it does not search a catalogue   │
  └───────────────────────────────────────────────────────────────────────────┘

  ROUND N>0 — same pipeline, three extra inputs into Stage B/C:
      open gaps (governor)   ·   tools already tried   ·   what they returned
```

**Why this is testable and the current manifest is not:** every stage is a pure function
of declared inputs. Stage A is set arithmetic. Stage B is a scored retrieval over a
fixed corpus with a pinned embedding. Stage C is a sort. **No model in the loop**, so a
fixture — *query → expected ranked tools* — either passes or fails.

## 8.2 What exists, what doesn't

| stage | exists today | gap |
|---|---|---|
| **A** authority | `supports_modes`, `visible_to_planner`, `user_tool_subscriptions`, `_resolve_allowed_tools` (`orchestrator.py:95`) | it narrows **rendering**, and is a *subscription* model, not an *authorization* model |
| **B** domain match | `SkillSpec.category` — 8 values, already drives the tool-settings UI | **no scoring at all.** Nothing matches a query to a domain. No domain description text to match *against* |
| **C** rank | — | **nothing.** No health, no past-success, no cost, no retryability field |
| **D** ranked output | — | **nothing.** The manifest is unordered prose, identical every turn |
| **round N** | governor computes gaps; `tool.result` telemetry landed 2026-09-10 | no history yet; the selector has never seen a gap |

## 8.3 🔴 The finding that shapes the design: domains are wildly uneven

[MEASURED — 57 tools from the live manifest, classified by name prefix.]

| domain | tools | share |
|---|---:|---:|
| **analytics** (`get_*`, `search_orgs`, …) | **26** | **45%** |
| service_line | 7 | 12% |
| corpus/search | 6 | 10% |
| appeals | 5 | 8% |
| provider/npi | 4 | 7% |
| utility/other | 4 | 7% |
| healthcare | 2 | 3% |
| documents | 2 | 3% |
| web | 1 | 1% |

**One domain is 45% of the catalogue.** So "pick the top 3 domains and their tools"
narrows almost nothing whenever analytics is one of them — you have selected 26 tools
and ~6,500 tokens. **Stage B alone is not sufficient**; Stage C's within-domain ranking
is doing the real work, not the optional polish.

Three consequences:

**(a) `analytics` must be split** into sub-domains (market · org · rate · service-mix)
or Stage B's top-K is meaningless for half the catalogue.

**(b) The cheapest possible win is not the ranker — it is §3.** Those 26 analytics tools
are exactly the `get_*` set a code comment says were deleted for always 404-ing.
**If they do not dispatch, deleting them takes the catalogue 57 → 31 and cuts ~6,500
tokens per round, before a line of selector code is written.** One dispatch attempt
answers it.

**(c) Domain sizes must be a monitored property.** A domain that grows to 26 entries
silently defeats the mechanism that was supposed to narrow it.

## 8.4 Design constraints I would hold

**1 · Authority is a FILTER, never a rank input.** Stage A produces a set; Stage B and C
may only reorder within it. If authority becomes a score component, a high-relevance
tool can outrank its own permission boundary. Same reason the PHI gate is fail-closed
rather than weighted.

**2 · Determinism requires a pinned embedding and a golden set.** A deterministic ranker
with no ground truth is *reproducibly* wrong. And an embedding-model change silently
re-ranks everything, so the model version is part of the contract — same decay problem
as the mutation ledger, and it wants the same treatment.

**3 · Match against structured triggers, not the planner prose.** The current
descriptions are written to persuade a model, and two of them already claim the same
query (§5). Retrieving over that text inherits the collision. Structured trigger phrases
make the overlap a **build-time test failure** — which is the thing prose can never give
us, and the real prize.

**4 · Emit the reason, and persist it.** Stage D's reasons let react confirm rather than
re-derive — and a selection nobody records is a producer with no consumer, which is what
`tool.offered` already was when it recorded `__unfiltered__` instead of the names.

**5 · The governor's gap state is stale by one round, by construction.** Ananth's own
point, and it must be stated rather than discovered: at round N the gaps were computed
from round N−1's results, so the selector is always reasoning from the previous round's
picture. That is not a bug and cannot be fixed by ordering — it means gap-closure must
never be read as *current*, and a selector that assumes freshness will re-offer a tool
whose result has already landed.

## 8.5 The UX is the test surface — what it has to show

Ananth: *"the UX should be the place to test it."* For that to be true it must show, for
a typed query:

- **Stage A** — the caller's list, and what authority excluded
- **Stage B** — every domain with its score, including the ones that lost
- **Stage C** — the ranked tools with each reason
- **Stage D** — the manifest react would actually receive, and its token count
- and for a **real past turn**: what was selected, what react then called, and whether
  the two agreed

**That last row is the one that makes it an instrument rather than a demo.** Everything
above it is a preview of a hypothetical; only the last row can tell you the selector was
right.

## 8.6 Open questions before any of this is built

1. **Do the 26 analytics tools dispatch?** (§3 — halves the problem either way.)
2. What text does Stage B match against — and who writes it?
3. Sub-domain split for analytics: what are the axes?
4. Where do health / past-success / cost / retryability live — `SkillSpec` fields, or a
   separate table fed by `tool.result`?
5. Top-K and top-N: what are they, and are they fixed or budget-derived from the
   remaining prompt space?
6. Who owns the golden set, and how many fixtures before the ranker is trustworthy?
   (The CARC 197 turn is fixture #1: expect `appeals_get_playbook` ranked first.)

---

# 9. CORRECTION TO §8 — match against the LEXICON, not invented domains

**Ananth, 2026-09-10:** *"analytics is the wrong domain.. we should try and match it with
lexicon.. because that is the easiest way"* … *"we can match the query against the
lexicon and we can match the tools against the lexicon."*

**He is right and §8.3's domain table was my own invention.** I classified 57 tools by
name prefix — `get_*` → "analytics", `appeals_*` → "appeals" — and then reasoned about
the distribution as if it meant something. It does not. It is a taxonomy I made up an
hour ago from string matching, with no owner, no definition, and no existence anywhere
in the system. **Treat §8.3's domain labels as discarded.** The 45%-in-one-bucket
observation survives only as *"the catalogue is lopsided under any grouping"*, which is
weaker than I stated it.

## 9.1 Why the Lexicon is the right substrate

The Lexicon is a **curated, embedded, already-live tag vocabulary** on three axes
[READ, `mobius-rag`]:

| axis | meaning | examples observed in code |
|---|---|---|
| **d:** | domain / document-type | `d:claims`, `d:appeals_and_disputes`, `d:benefits`, `d:credentialing`, `d:utilization_management`, `d:eligibility`, `d:billing_codes` |
| **p:** | process | `p:prior_authorization`, `p:process`, `p:utilization_management` |
| **j:** | jurisdiction / party | `j:payor.<slug>`, `j:regulatory_authority.<slug>`, `j:service_line.<slug>` |

It is embedded in pgvector (`vector(768)`, `text-embedding-004`) and **already used
query-side in production retrieval** — `corpus_search.py` reads `chunk_d/p/j_tags` off
`rag_published_embeddings`, and `payer_context.extract_payer_slug` pulls `j:payor.*`
out of a query's tag matches.

**Five reasons this beats invented domains:**

1. **It answers §8.6's open question #2 — "what text does Stage B match against, and who
   writes it?"** Nobody has to author domain descriptions. The vocabulary exists, is
   curated, and has an owner.
2. **Both sides project into the same space.** Query → tags is already built. Tool → tags
   is a declaration. The match is then set overlap plus similarity in one shared
   vocabulary, not cosine distance between a question and a paragraph of marketing prose.
3. **The reason becomes human-checkable.** *"Query matched `d:appeals_and_disputes` +
   `j:payor.sunshine_health`; these three tools declare those tags"* is auditable by a
   person. A similarity score is not. That matters more here than anywhere, because the
   whole point of this node is to be trustworthy.
4. **It reuses a live, tuned instrument** rather than standing up a second retrieval
   path — and per the pgvector standard, there is no second vector store to introduce.
5. **It sidesteps the overlap trap.** §5's collision exists because two tools' *prose*
   claims the same query. Tags are discrete: two tools declaring `d:appeals_and_disputes`
   are *visibly* siblings, and the tie-break becomes an explicit rule rather than an
   accident of wording.

## 9.2 What Stage B becomes

```
  query ──► lexicon tag match  (vector / BM25 / hybrid — already live query-side)
              │
              ├─ d: tags  ──┐
              ├─ p: tags  ──┼──► tag set, each with a score
              └─ j: tags  ──┘
                            │
  tools ──► declared tags ──┤   ← THE ONE THING THAT DOES NOT EXIST YET
                            ▼
              overlap + score ──► ranked tools, reason = the shared tags
```

**The single missing piece is the tool side.** Each tool needs to declare its Lexicon
tags — a `lexicon_tags` field on `SkillSpec`, which already spans builtins *and* MCP
tools (`source="mcp"`), so the whole 57 can carry them.

CARC 197 as the worked example [ILLUSTRATIVE — not yet measured]:

| | tags |
|---|---|
| query *"how do i appeal a carc 197 denial for sunshine health"* | `d:appeals_and_disputes`, `j:payor.sunshine_health`, plausibly `d:claims` |
| `appeals_get_playbook` | `d:appeals_and_disputes` + **`j:payor.*` required** |
| `appeals_lookup_rules` | `d:appeals_and_disputes`, **no payor axis** |

**The `j:` axis is what discriminates them, and it is exactly what the prose failed to
express.** The playbook tool is payor-scoped; the rules tool is CARC-scoped. A human
reading the two descriptions could not tell — I could not, and the model could not. A
tag declaring *this tool needs a payor* makes it mechanical.

**Whether that is what actually happens is UNVERIFIED** and is the first fixture: run
the real query through live query-side tagging and see which tags come back. That is a
measurement I can take without building anything, and it should come before the design
is settled.

## 9.3 What this changes in §8

- **Stage B** — "domain match" becomes **Lexicon tag match**; the domain taxonomy is
  deleted rather than fixed.
- **§8.3's analytics-is-45% table** — discarded as a made-up grouping. The real question
  is how the 57 distribute across `d:`/`p:`/`j:`, which is **[UNMEASURED]** and needs
  the tool-side tags to exist first.
- **§8.6 question #2** — answered: the Lexicon, owned by Curation/RAG.
- **§8.6 question #3** ("sub-domain split for analytics") — **void.** There is no
  analytics domain.
- **§8.4 constraint 2 stands and gets sharper:** the pinned-embedding requirement now
  means the Lexicon's own embedding version is part of the selector's contract, and
  Lexicon curation changes re-rank tools. That is a real coupling and it wants the same
  decay treatment as the mutation ledger.
- **§8.4 constraint 3 is largely satisfied by this** — tags *are* the structured triggers
  I was arguing for, and they already exist.

**Lexicon coverage is NOT a design constraint — corrected by Ananth, 2026-09-10.** I had
filed the absence of `florida_blue` / `florida_medicaid` as `j:payor.*` keys as a risk
the selector had to be designed around. His ruling: *"that's not your problem, that's
someone else's problem about the completeness.. so don't bother — when we onboard them
we will have those payors included."*

He is right, and my framing was wrong in a specific way: **payor coverage is an
onboarding output, not a vocabulary defect.** The `j:payor.*` set grows as payors are
onboarded, by design. Designing the selector around today's snapshot would be building
against a moving input that is *supposed* to move.

What survives is one line, not a risk section: **the selector needs a defined behaviour
when a query's tags do not resolve** — a stated fallback plus a countable "no tags
matched" signal. Not because coverage is broken, but because onboarding is incremental
by nature, so *some* query will always arrive ahead of its tags. That is a requirement
on the selector, not a dependency on Curation.

## 9.4 The cheapest next measurement

Before any of this is built, and answerable today:

1. **Run the CARC 197 query through live query-side Lexicon tagging.** What tags come
   back? If `j:payor.sunshine_health` and `d:appeals_and_disputes` both resolve, the
   substrate works and §9.2's example is real rather than illustrative.
2. **§3 still stands** — do the 26 `get_*` tools dispatch? Independent of all of this,
   and it halves the catalogue either way.

---

# 10. THE TOOL-SIDE DECLARATION — subscribes vs requires

**Ananth, 2026-09-10:** *"so tools will have to declare few things — what lexicon
categories they subscribe to and what requirements they have on a lexicon basis.. the
only thing is real lexicon drift but we will handle it."*

**The two-field split is the load-bearing idea in the whole design**, and it is worth
separating carefully because they do different jobs at different stages:

| field | question it answers | stage | effect |
|---|---|---|---|
| **`subscribes`** | *"which tags am I relevant to?"* | Stage C rank | contributes to **score** |
| **`requires`** | *"which tags must resolve or I cannot function?"* | Stage A/B **gate** | **eligibility, not score** |

**Why the distinction matters more than it looks:** a tool that cannot work should be
**excluded with a stated reason**, not ranked eighth. If "I need a payor and there isn't
one" is expressed as a low score, then on a thin turn it can still surface — and it
surfaces *without* the thing it needs, which is how a tool gets called and returns
nothing. That is `appeals_get_playbook` with no payor: a guaranteed empty result,
reachable today.

So `requires` is a **hard filter** — same posture as authority in §8.4 constraint 1, and
for the same reason. Eligibility is not a weight.

## 10.1 The worked example, and where it stops working

| tool | subscribes | requires | returns |
|---|---|---|---|
| `appeals_get_playbook` | `d:appeals_and_disputes` | **`j:payor.*`** | deadline, submission_method, portal, fax, mail, appeal_levels |
| `appeals_lookup_rules` | `d:appeals_and_disputes` | **a CARC code** | appeal_argument, triggers_when, requires |

[Return fields READ from the live endpoint and the manifest text.]

**`requires` makes the ineligible cases mechanical**, which is real value:
- query with a CARC but no payor → **playbook is ineligible**, stated, not silently
  called and empty
- query with a payor but no CARC → **rules is ineligible**

**🔴 But it does not solve Ananth's actual turn, and I am not going to pretend it does.**
*"how do i appeal a carc 197 denial for sunshine health"* supplies **both** a payor and
a CARC. Both tools are eligible. `requires` discriminates nothing here, and both
`subscribes` sets contain `d:appeals_and_disputes`. **On this model the tie is unbroken**
— which is the same position we are in today, reached by a cleaner route.

## 10.2 What actually discriminates them: the `p:` axis

The two tools answer **different kinds of question about the same subject**, and the
Lexicon already has an axis for that:

- `appeals_get_playbook` returns **deadline, submission method, portal, fax, address,
  escalation ladder** → this is **process / logistics**. *How do I file, where, by when.*
- `appeals_lookup_rules` returns **appeal_argument, triggers_when, requires** → this is
  **substance**. *What do I say.*

*"How do I appeal…"* is a **process** question. So the discriminator is a `p:` tag, not
the `j:` axis I proposed in §9.2 — **and I should correct that: §9.2 credited `j:` with
the discrimination, and on this turn `j:` resolves for both.** The `j:` axis makes
`requires` work; the `p:` axis is what breaks the tie.

[UNVERIFIED — whether live query-side tagging actually emits a `p:` tag for *"how do i
appeal"*, and whether the existing `p:` vocabulary (`p:prior_authorization`,
`p:process`, `p:utilization_management` observed in code) has the granularity to
separate *how-to-file* from *what-to-argue*. **This is the measurement that decides
whether the design works.** It needs no code: tag the real query and look.]

## 10.3 Lexicon drift — the cheap half, since Ananth has the rest

He is right that drift is the real exposure and that it is handled elsewhere. **One
mechanical piece belongs in this node and costs nothing:**

**A tool declaring a tag that no longer exists in the Lexicon must fail a build, not
silently never match.** A `requires: j:payor.*` against a retired axis makes the tool
permanently ineligible and *invisible* — no error, no log, just a tool that is never
offered again. That is the `make_tool_failed` shape exactly: a condition that can never
be satisfied looks identical to a condition that is never met.

The check is a set-difference between declared tags and the live vocabulary, run at
startup or in CI. It is the same decay problem the mutation ledger solved by recording
`verified_at` and demoting when the referenced files move — and it wants the same
treatment: **declared-against-vocabulary-version, re-checked, demoted loudly.**

## 10.4 Open, ordered by what unblocks the most

1. **Does live query-side tagging emit a usable `p:` tag for *"how do i appeal…"*?**
   (§10.2 — decides whether the tie can be broken at all. Measurable today, no code.)
2. Who authors `subscribes` / `requires` for the **29 MCP tools**? Their descriptions
   come from a remote `list_tools` response — so either the MCP server declares them, or
   chat maintains an override table. This is a contract question with another team.
3. Does `requires` support disjunction (`j:payor.* OR j:regulatory_authority.*`)? The
   appeals ladder escalates to AHCA, so at least one tool spans both.
4. Do the 26 `get_*` tools dispatch? (§3 — unchanged, and still halves the catalogue.)

---

# 11. 🔴 MEASURED: BM25 OVER THE CURRENT DESCRIPTIONS PICKS THE WRONG TOOL BY 4.6×

**Ananth, 2026-09-10:** *"that's why the balancing with pgvector or bm25 helps."*

The architecture is right — discrete tags for eligibility, similarity for fine ranking.
**But I tested it against the real text and the similarity layer does not break the tie;
it amplifies the error.** [MEASURED — BM25, k1=1.5, b=0.75, over the two tool blocks
extracted from the live `/chat/skills-manifest` render.]

Query: *"how do i appeal a carc 197 denial for sunshine health"*

| tool | BM25 | matched terms |
|---|---:|---|
| **`appeals_lookup_rules`** | **5.450** | how×2, do×1, i×1, appeal×5, a×2, carc×7, denial×2, for×3, **sunshine×1, health×1** |
| `appeals_get_playbook` | **1.184** | how×1, appeal×4, a×1, carc×4, for×1 |

**Query terms appearing ONLY in `appeals_lookup_rules`: `denial`, `do`, `i`, `health`,
`sunshine`.**
**Query terms appearing only in `appeals_get_playbook`: none.**

**The reason is §5, quantified.** `appeals_lookup_rules`' description contains the
example *"rules for CARC 29 timely filing **denial** from **Sunshine Health**"* — so the
payor name and the word *denial* are literally in the competing tool's text. The prose
that misleads the model misleads BM25 **for the same reason and by the same mechanism**:
one entry harvested the other entry's query shape as its own example.

**So "retrieval would pick the wrong tool confidently and faster" is no longer an
argument I was making — it is a measurement.** 4.6× in the wrong direction.

## 11.1 What this does and does not invalidate

**It does NOT invalidate the design.** Tags for eligibility and similarity for ranking is
still right. What it establishes is a constraint on the **corpus**:

> **Similarity must not run over the planner prose.** That text is written to persuade a
> model, contains hand-picked example queries, and is therefore adversarial to lexical
> retrieval — a tool that lists more example phrasings wins, regardless of fit.

Candidate corpora that are not adversarial, in rough order of cheapness:

1. **the tool's return-field semantics** — `deadline_appeal_days, submission_method,
   portal_url, fax, mail_address` vs `appeal_argument, triggers_when, requires`. These
   are *what the tool gives you*, are already declared, and nobody wrote them to win a
   match.
2. **Lexicon tags** — discrete, curated, the `p:` axis distinction from §10.2.
3. **a curated trigger set per tool**, with the §5 collision test asserting no query maps
   to two tools' triggers. More work, and the only option that catches future collisions
   at build time.

## 11.2 And the harder truth about this particular query

**On *"how do i appeal a carc 197 denial for sunshine health"*, no lexical signal favours
the playbook — because the query is genuinely ambiguous.** *"How do I appeal"* can mean
*what do I argue* (rules) or *how do I file, by when, to where* (playbook). A human
expert would answer both, or ask.

Which means the honest target for this turn is **not a single correct pick.** It is
Ananth's own stated output: *"a clear rank ordered set of tools that we think will be
useful along with the reasoning so that react can confirm based on what it needs to
do."*

**Both appeals tools should be offered, ranked, with their reasons** — *"substance"* and
*"process/logistics"* — and react picks or calls both. Judged that way, **today's failure
is not that the model chose wrongly. It is that the loop called one tool, got
`no_sources` twice, kept the same two gaps open for three rounds, and never tried the
sibling that was sitting in the manifest.** That is a Stage-D and round-N failure, not a
Stage-B ranking failure.

Which relocates the fix and makes §8.1's round-N path the important half of the design,
not the refinement.

## 11.3 The measurement that now matters most

**Not "which tool ranks first" but "does the eligible set contain both, and does round N
try the second one when the first returns nothing?"**

Answerable against today's telemetry: on Ananth's turn, `appeals_lookup_rules` returned
`no_sources` **twice** and the gaps stayed open. Nothing escalated to the sibling. The
governor saw the gaps; the selector never got the chance to act on them because there is
no selector.

---

# 12. MEASURED: "if we cannot determine top 5 by lexical match, why do we expect react to"

**Ananth, 2026-09-10.** Two experiments, both run against the **live** production
manifest and the **live** Lexicon. No code built.

## 12.1 BM25 over all 57 tool blocks — the right tool is #4, and that is the finding

Query: *"how do i appeal a carc 197 denial for sunshine health"*

| rank | tool | BM25 | block len |
|---:|---|---:|---:|
| 1 | `appeals_lookup_rules` | **25.97** | 74 |
| 2 | `appeals_find_carc` | 14.29 | 65 |
| 3 | `appeals_assemble_letter` | 10.76 | 472 |
| **4** | **`appeals_get_playbook`** ← the tool with the answer | **10.01** | 85 |
| 5 | `rag` | 8.77 | 425 |

[MEASURED — BM25 k1=1.5 b=0.75 over 57 blocks extracted from the live
`/chat/skills-manifest`. 56 of 57 score non-zero.]

**So the honest answer to your question has two halves, and they point opposite ways:**

**Lexical match cannot SELECT.** It puts the wrong tool first, by 2.6×, for the reason
in §11 — `appeals_lookup_rules`' own example text contains *"denial"* and *"Sunshine
Health"*.

**Lexical match CAN SHORTLIST, and well.** 57 → 5 with the right tool inside, and **4 of
the 5 are the appeals family.** That is not a weak result; that is the job.

**Which reframes "why do we expect react to":** we should not. Today react picks from
**57** entries, ~13,062 tokens, on a prompt where the manifest is already the largest
single block. A shortlist makes it a **5-way choice among siblings, four of them in the
right domain.** Those are different tasks. **Expecting a model to pick 1-of-57 and
expecting it to pick 1-of-5-already-relevant are not the same ask** — and the second one
is the one your design actually creates.

**The token payoff, three queries:**

| query | top-5 tools | top-5 tokens | vs full 13,062 |
|---|---|---:|---:|
| appeal CARC 197 sunshine | 4 appeals + rag | ~1,971 | **−85%** |
| market size behavioral health Tampa | `get_msa_map`, `get_rate_benchmarks`, `get_market_size`, `get_service_line_opportunity`, `lookup_npi` | ~926 | **−93%** |
| what is prior authorization | `transform_previous_answer`, `search_uploaded_document`, `rag`, … | ~1,799 | **−87%** |

**Note the second row: the market query DOES surface the market tools.** Which is
evidence for Chat Master's caveat in §3.1 — those 29 are not unreachable, they were
never *asked for* in an appeals-heavy window.

**And note the third row, which is the weakest result:** *"what is prior authorization"*
ranks `transform_previous_answer` first and never surfaces a UM/prior-auth tool.
Lexical match on a short generic query is poor, and this is where the tag axis has to
carry it.

## 12.2 Tag match against the LIVE Lexicon — and the `p:` axis I proposed does NOT fire

The Lexicon is live and queryable at `GET /policy/lexicon` [LIVE]:
**5,570 tags — `d:` 4,843 · `j:` 472 · `p:` 255**, `lexicon_version v1.0.0`, revision 3480.

**Its own metadata confirms the axis semantics I had inferred** — this is the source of
truth, not my reading:
> *"p-tags = procedural intent (what can be done with the statement)"*
> *"d-tags = domain/topic (provider manual sections: claims, pharmacy, …)"*

Matching the real queries against the real tag phrases, word-boundary anchored:

| query | tags matched | `p:` axis |
|---|---|---|
| *"how do i appeal a carc 197 denial for sunshine health"* | `d:claims.denial`, `d:disputes.appeal`, `j:payor.sunshine_health` | **NONE** |
| *"what is the filing deadline to submit an appeal to sunshine health"* | `d:claims.timely_filing`, `d:disputes.appeal`, `j:payor.sunshine_health`, **`p:submission.submit`** | ✅ |
| *"what argument should i use to appeal carc 197"* | `d:disputes.appeal` | **NONE** |

[MEASURED. Caveat: this is *my* matcher — word-boundary phrase and code matching over
the published tag specs — **not** production's tagger, which may use embeddings and
score tiers. Treat the *presence* of hits as sound and the exact set as indicative.]

**🔴 The result kills my §10.2 proposal as stated.** I argued the `p:` axis would break
the playbook-vs-rules tie. **On Ananth's actual query no `p:` tag fires at all** — and it
does not fire on the *what-argument* phrasing either. The axis only engages when the user
uses procedural vocabulary (*"filing deadline"*, *"submit"*). So:

- `p:` **is** the right discriminator when it resolves — `p:submission.submit` is exactly
  *how-to-file*, and would rank the playbook over the rules tool
- but it resolves on **explicit** process language, and *"how do i appeal"* is not that,
  even though a human reads it as procedural

**Three tags on the real query — `d:claims.denial`, `d:disputes.appeal`,
`j:payor.sunshine_health` — and both appeals tools would match all three.** Tag matching
alone leaves the tie exactly where lexical matching leaves it.

## 12.3 What the two experiments together actually establish

1. **Shortlisting works; selection does not.** Both methods narrow 57 → 5 with the right
   tool inside. Neither ranks it first. **Your design's output — a ranked set with
   reasons for react to confirm — is the right shape, and "pick the one correct tool" is
   the wrong target.**
2. **The two methods fail differently, which is why hybrid helps** — but not as a
   tie-breaker. Lexical is strong on specific, term-rich queries and poor on short
   generic ones (*"what is prior authorization"*). Tags are strong on entity and domain
   (`j:payor.*` resolved cleanly) and silent on implied intent. **Hybrid buys coverage,
   not discrimination.**
3. **Nothing available today separates the two appeals tools on that query** — not BM25,
   not tags. The discriminating fact (*payor-scoped vs CARC-scoped*, *process vs
   substance*) exists in neither corpus. It has to be **declared**, which is §10's
   `subscribes`/`requires`, and §10's own limit stands: on a query supplying both a payor
   and a CARC, both tools remain eligible and correctly so.
4. **Therefore the real fix is round-N, as §11.2 concluded** — offer both, and when the
   first returns `no_sources` twice, try the sibling. Today the loop held the same two
   gaps for three rounds and never did.

---

# 13. MEASURED: three tiers + an absolute floor — and the design holds

**Ananth, 2026-09-10:** *"we have 2 different sections — these domain/specific tools and
generic tools like corpus_search; few others which are defaults if nothing else."*

**That resolves §12's worst result**, and the experiment says so. Run against the live
57-tool manifest, no code built.

## 13.1 The tiers

| tier | count | how it is selected | examples |
|---|---:|---|---|
| **default** | 2 | **always present.** A floor, not a competitor | `rag`, `recall_evidence` |
| **specific** | 42 | admitted only on a match clearing a threshold | `appeals_*`, `service_line_*`, `get_*` |
| **utility** | 14 | not domain-selected — conversation/document helpers | `vibe`, `transform_previous_answer`, `refuse`, `fetch_document` |

**⚠️ The tier assignment above is MY strawman and needs an owner.** I invented a
"domain" taxonomy in §8.3 and Ananth correctly discarded it; I am not repeating that
mistake silently. This split is derived from observable behaviour (what answers anything
vs what needs an entity vs what serves the conversation) and it belongs as a declared
`SkillSpec` field, not a platform-seat guess. **Treat the tier *mechanism* as measured
and the tier *membership* as unratified.**

**Why the tier changes the mechanism and not just the score:** a default that *competes*
can be crowded out; a default that is a *floor* cannot. §12.1's third row —
*"what is prior authorization"* ranking `transform_previous_answer` first — is a utility
tool winning a domain contest it should never have entered.

## 13.2 The refinement the experiment forced: a relative threshold is not enough

First attempt admitted specific tools scoring ≥ 35% of the top specific score. On the two
strong queries it was right. On *"what is prior authorization"* it admitted
`service_line_requirements` (3.8), `appeals_find_carc` (2.7), `search_orgs` (2.3),
`service_line_code_lookup` (1.5) — **noise, because the top score itself was weak and
35% of weak is weaker.**

**A relative threshold cannot tell "several good matches" from "no good matches".** It
needs an **absolute floor**: if the best specific match does not clear it, admit *nothing*
specific and serve defaults only.

## 13.3 Results with tiers + floor (BM25, floor = 6.0)

| query | selected | tools | tokens | vs 13,062 |
|---|---|---:|---:|---:|
| *how do i appeal a carc 197 denial for sunshine health* | defaults + **all 4 appeals tools** | 6 | ~2,186 | **−84%** |
| *what's the market size for behavioral health in Tampa* | defaults + `get_msa_map`, `get_rate_benchmarks`, `get_market_size`, `get_service_line_opportunity` | 6 | ~1,634 | **−88%** |
| *what is prior authorization* | **defaults only** — best specific 3.8 < 6.0 | 2 | ~919 | **−93%** |
| *what is the filing deadline to submit an appeal to sunshine health* | defaults + **`appeals_get_playbook` FIRST**, then `appeals_lookup_rules` | 4 | ~1,183 | **−91%** |

**Four things this establishes:**

**1 · The generic query now behaves correctly.** *"What is prior authorization"* gets
`rag` + `recall_evidence` and nothing else — which is the right answer for a question no
specific tool serves. The floor turned §12's worst result into the cleanest one.

**2 · The fourth row is the payoff, and it was not planted.** On *procedural* phrasing —
*"filing deadline to submit"* — **`appeals_get_playbook` ranks FIRST**, above the sibling
that beat it 2.6× on the ambiguous phrasing. BM25 gets it right when the query carries
process vocabulary, which is exactly the `p:submission.submit` case from §12.2 arriving
by a different route. **So the collision is not general — it is specific to the ambiguous
phrasing.**

**3 · And on the ambiguous phrasing, both appeals tools are in the set.** Which per
§11.2 is the correct outcome, not a failure: *"how do i appeal"* genuinely spans
what-to-argue and how-to-file, and the design's job is to hand react both with reasons.
**Ananth's stated output was right and my "the tie is unbroken" framing in §10.1 was the
wrong test.**

**4 · The token reduction is 84–93% across all four**, on a block that is currently the
largest single element of the planner prompt.

## 13.4 What is still not settled

- **tier membership** — mine, unratified (§13.1)
- **the floor value** — 6.0 is fitted to four queries. It is a threshold on an unnormalised
  BM25 score, so it will not transfer across corpora or query lengths. **A score-shape
  that needs a magic constant is a smell**; normalising (e.g. score ÷ top-possible, or a
  z-score over the specific pool) is the version that survives.
- **`requires` is not in this experiment at all.** §10's eligibility gate would remove
  `appeals_get_playbook` on a query with no payor — none of these four test that.
- **the golden set** — four queries chosen by me is not an evaluation. §8.6 question 6
  stands: who owns it, and how many fixtures before the ranker is trustworthy.

---

# 14. MEASURED: vector similarity added — and it beats BM25 on exactly the queries BM25 loses

**Ananth, 2026-09-10:** *"lets pick a vector score on similarity also.. a tool has its
description and bullet points of its requirements and capabilities.. can we not do a
vector match.. so we have a tag match.. and then we can also assign a similarity match..
is this not possible."*

**Yes, and I ran it.** Real embeddings, not a simulation: **`text-embedding-004` on
Vertex, 768-dim — the same model the Lexicon uses** [LIVE]. All 57 live tool blocks
embedded, four queries embedded, cosine similarity computed.

## 14.1 Vector vs BM25, side by side

| query | vector top-3 | BM25 top-3 |
|---|---|---|
| *how do i appeal a carc 197 denial for sunshine health* | lookup_rules **.734** · find_carc .669 · **playbook .608 (#3)** | lookup_rules 1.00 · find_carc .55 · assemble_letter .41 → **playbook #4** |
| *filing deadline to submit an appeal to sunshine health* | lookup_rules .674 · **playbook .599 (#2)** · find_carc .550 | **playbook 1.00 (#1)** · lookup_rules .83 · rag .60 |
| *what argument should i use to appeal carc 197* | find_carc .609 · lookup_rules .608 · **playbook .557 (#3)** | lookup_rules 1.00 · find_carc .66 · **playbook .55 (#3)** |
| *what is prior authorization* | **service_line_requirements .541 · rag .494** | **transform_previous_answer 1.00** · search_uploaded_document .99 · rag .98 |

**Three results, and the second is the one that matters:**

**1 · Vector improves the ambiguous query.** The playbook moves **#4 → #3**. Better, still
not first — because the collision is semantic as well as lexical: the two tools genuinely
are about the same subject.

**2 · 🔴 BM25 BEATS VECTOR on the procedural query.** On *"filing deadline to submit"*
BM25 ranks the playbook **#1** and vector ranks it **#2**, behind the sibling. That is the
opposite of what you would expect — and it is the strongest argument for hybrid in this
whole document. The terms *deadline*, *submit*, *filing* are **exact lexical signals**
that BM25 rewards and an embedding partially dissolves into a general "appeals" topic.
**Embeddings blur precisely the distinction we need; term matching preserves it.**

**3 · Vector fixes the generic query, decisively.** *"What is prior authorization"* —
BM25 ranks `transform_previous_answer` **#1** (nonsense, a utility tool winning a domain
contest). Vector ranks `service_line_requirements` #1 and `rag` #2, which is sensible.
**So vector solves §13's problem without needing the utility tier as a hack** — though
the tier is still right for other reasons.

**And a shape difference worth knowing:** vector scores are compressed (0.45–0.73 across
all 57), so an absolute cosine threshold has far less room than §13's BM25 floor. The
appeals family clusters at 0.49–0.73 — narrow. **Whatever gating we use cannot be a
single constant on a raw cosine.**

## 14.2 Hybrid — reciprocal rank fusion, k=60

| query | RRF top-3 | playbook lands |
|---|---|---|
| *how do i appeal a carc 197…* | lookup_rules · find_carc · **playbook** | **#3** |
| *filing deadline to submit…* | lookup_rules · **playbook** · find_carc | **#2** |
| *what argument should i use…* | find_carc · lookup_rules · **playbook** | **#3** |
| *what is prior authorization* | service_line_requirements · rag · find_carc | n/a |

**RRF puts the right tool in the top 3 on every appeals query, and keeps the generic query
sane.** It does not make the playbook #1 on the ambiguous phrasing — and per §11.2 and
§13.3 it should not have to: *"how do i appeal"* spans both tools, and the design's
output is a ranked **set** with reasons.

**What RRF buys, stated precisely:** not a better #1, but **robustness across query
shapes.** Each method has a failure mode the other does not share — BM25 is fooled by
harvested example text and by short queries; vector blurs exact procedural terms. Fusing
by *rank* rather than score also sidesteps §13.4's magic-constant problem: no threshold
on an unnormalised scale.

## 14.3 So the answer to *"is this not possible"* is yes, with three signals not two

| signal | strength | failure mode |
|---|---|---|
| **tag match** (Lexicon `d:`/`p:`/`j:`) | entity and domain — `j:payor.sunshine_health` resolves exactly; `requires` becomes mechanical | silent on implied intent — **no `p:` tag fires on *"how do i appeal"*** (§12.2) |
| **BM25** over tool text | exact procedural terms — *deadline/submit/filing* → playbook #1 | harvested example phrasings (§11); nonsense on short generic queries |
| **vector** (`text-embedding-004`) | short generic queries; topical similarity when wording differs | blurs the exact terms that discriminate siblings; compressed score range |

**None of the three is sufficient. Each covers a gap the other two leave.** That is a
better argument for hybrid than "hybrid is usually better", and it is measured on this
corpus rather than assumed.

## 14.4 Still not settled

- **the corpus each signal reads.** §11's constraint stands: BM25 over the *planner prose*
  is adversarial. These measurements use that prose because it is what exists — **the
  numbers above are a floor on what a purpose-written corpus would achieve**, not a
  ceiling.
- **weights.** RRF k=60 is the textbook default, untuned. Anything tuned on four queries
  is fitted, not learned.
- **cost.** One query embedding per turn (~10ms, cheap) plus 57 stored tool vectors
  (embed once, re-embed on description change) — but *that* is a drift dependency: a
  tool whose description changes without re-embedding ranks on stale meaning, silently.
  Same decay shape as §10.3.
- **the golden set.** Four queries I chose. Unchanged and still the real prerequisite.
