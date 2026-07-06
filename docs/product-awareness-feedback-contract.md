# Product-awareness ↔ Feedback — integration contract

Status: live (feedback half), **deployed + calibrated (awareness half — τ_gap=0.544 on live Vertex+pgvector; service on Cloud Run)**. 2026-07-02.
Awareness side shipped: `product-awareness/` module (pgvector + Vertex), standalone
retrieval service, and the `product_help_search` chat builtin that files gaps in-process
via `insert_open_feedback` (trigger="auto_harvest" per feedback agent's 2026-07-02 note; 8 handler tests green).
The thin seam that lets the two modules stay independent. Neither imports the
other's internals; they meet at `product_feedback` (the shared signal bus) and
this contract.

Owners: **Feedback** = feedback agent (this repo, `docs/feedback-agent-spec.md`).
**Awareness** = product-awareness agent (its own PRD).

---

## The loop (both directions)

```
Awareness → Feedback   product_help_search misses (nothing above τ_gap)
                        → files a docs_gap item (area_tag=module, verbatim=question)
                        → no user action required; every unanswerable "how do I…"
                          becomes tracked documentation debt.

Feedback → Awareness   docs_backlog view ranks gaps by module
                        → curation priority (which doc to write next)
                        → the raw verbatims are the doc source material AND the
                          eval query bank (replay them after writing the doc).
```

**Load-bearing invariant (shared):** filing a gap is **best-effort and must never
break the answer path.** The write is wrapped so a DB failure degrades to a log,
never an exception that reaches the user's turn. See failure semantics below.

---

## Ownership split

| Concern | Owner |
|---|---|
| Category set (`docs_gap`), routing, write-path signature, `docs_backlog` view, failure semantics | **Feedback** |
| When a miss fires a gap (`τ_gap`); `docs_gap` vs `feature_request` disambiguation; the `status=planned` ingest flag; what awareness reads | **Awareness** |
| Module slug ↔ doc-file map; the best-effort invariant | **Shared** |

---

## Feedback side — OWNED (live, code-complete)

### Category + routing
`docs_gap` is a first-class category (chat-side; the user-facing classifier's 8
categories are unchanged — `docs_gap` is filed *programmatically*, never guessed
by the LLM). Routing:

| category | routed_to | filed by |
|---|---|---|
| `docs_gap` | `docs_backlog` | product-awareness on a `product_help_search` miss (demand) |
| `doc_stale` | `docs_refresh` | a module agent / git hook when a user-facing change ships (supply) |
| `feature_request` | `product_backlog` | product-awareness on a `status=planned` hit |
| `coverage_gap` | `corpus_backlog` | classifier / user-voiced |

No migration was needed: `routed_to`/`category` are unconstrained `TEXT`;
`area_tags` is shipped `JSONB`. (`docs_backlog` view added in migration 038.)

### The write-path (the seam)
`product_help` is an in-process chat builtin, so it calls the storage function
directly — no HTTP, no auth dance. **Wrap it best-effort** (the invariant):

```python
from app.storage import product_feedback as store

try:
    store.insert_open_feedback(
        trigger="inline",                 # a real user turn is behind the miss
        category="docs_gap",              # or "feature_request" — see disambiguation
        area_tags=[module_slug],          # the module product_help couldn't answer for
        verbatim=user_question,           # the user's exact "how do I…" — THE ASSET
        summary=f"no doc for: {topic}",
        routed_to=store.route_for(category),   # -> "docs_backlog"
        user_id=..., thread_id=..., correlation_id=...,
    )
except Exception:
    logger.warning("docs_gap logging failed — continuing", exc_info=True)
```

Returns `feedback_id` on success, `None` in dev when the DB is unreachable.
**One row per miss** — no dedup at write time, full verbatim retained (verbatims
are the doc source + eval bank; a lossy dedup key would destroy them).

**`trigger` provenance — 3 tiers (verified 2026-07-02).** `trigger` has **no CHECK
constraint** (the `-- inline|periodic|on_demand` in migration 037 is a doc comment).
Nothing downstream reads it as an enum, so it's the clean provenance dimension:

| tier | trigger values | meaning |
|---|---|---|
| user-voiced | `inline` · `on_demand` · `periodic` | a human gave feedback |
| user-activity-harvested | `auto_harvest` | a user asked, `product_help_search` missed → `docs_gap`/`feature_request` |
| builder-filed | `agent_signal` | a module agent / git hook filed → `doc_stale` |

So `WHERE trigger='agent_signal'` = all supply-side signals, `'auto_harvest'` =
demand-side harvest, the rest = real user voice — separable without parsing text.

### `docs_backlog` view (the read-path)
```
module | gap_hits | distinct_users | first_seen | last_seen | sample_verbatims[≤25]
```
Ranked by `gap_hits DESC`. A gap on an *undocumented* module surfaces there too
(highest-value "write this doc" signal). Full verbatims for a module (for
doc-writing + eval replay), not just the sample:
```sql
SELECT verbatim, created_at FROM product_feedback
WHERE category='docs_gap' AND area_tags ? 'chat' ORDER BY created_at DESC;
```
(`?` = JSONB-array membership of the slug.)

**Companion view — `capability_demand`** (migration 039). The symmetric partner:
`docs_backlog` ranks `docs_gap` ("which doc to write"); `capability_demand` ranks
`feature_request` by module ("which planned feature is most asked for"). Same
shape (`module | demand_hits | distinct_users | first_seen | last_seen | sample_verbatims`).
A `status=planned` hit lands here, not in `docs_backlog` — it's capability demand,
not doc debt.

### Supply side — `doc_stale` → `docs_refresh_backlog` (migration 040)
The mirror of `docs_gap`. `docs_gap` = "a user asked and we had no doc" (demand);
`doc_stale` = "a builder changed something and the doc is now behind" (supply).
A module agent (or git hook) files it:

```python
store.insert_open_feedback(
    trigger="agent_signal",           # builder-filed provenance tier
    category="doc_stale",
    area_tags=[module_slug],
    verbatim="what changed",          # e.g. "renamed sidebar Threads→Conversations"
    summary="doc behind: …",
    routed_to=store.route_for("doc_stale"),   # -> "docs_refresh"
    user_id=source_id,                # the SOURCE (agent name / git hook id)
)
```

**Two filing paths — pick by where you live:**
- **Chat-side code** (e.g. `product_help_search`, running in the chat container) → call
  `store.insert_open_feedback(...)` in-process, as above.
- **External agents** (other sessions / worktrees that CANNOT import `app.storage`) →
  HTTP `POST /chat/product-feedback` (unauth, returns `feedback_id`). Body:
  ```json
  {"verbatim": "what changed", "category": "doc_stale", "trigger": "agent_signal",
   "area_tags": ["<slug>"], "summary": "doc behind: …", "source": "agent:<name>"}
  ```
  `routed_to` is computed server-side from `category` (→ `docs_refresh`); `category`
  is accepted because it's in `ROUTING`. **Provenance (resolved 2026-07-02):** pass a
  `source` field (agent name / git-hook id) — it becomes the row's `user_id`, and any
  agent-filed write (`source` set **or** `trigger="agent_signal"`) **skips both the
  user funnel event (`log_event`) and the cadence advance (`mark_captured`)** — an
  agent isn't part of the human prompt→capture funnel and must not reset anyone's
  periodic-ask counters. The durable `product_feedback` row is still written, so
  external-agent signals attribute cleanly in `docs_refresh_backlog` (via
  `distinct_sources`) and never pollute user analytics. No need to prefix `verbatim`.

View `docs_refresh_backlog`: `module | stale_hits | distinct_sources | first_seen
| last_seen | sample_verbatims` (`distinct_sources` = distinct `user_id`, since
these are agent-filed). The weekly sweep drains it — refresh the doc, re-embed,
then close the signals through the encapsulated helper (never UPDATE the table
directly):

```python
store.close_signals(category="doc_stale", module="chat")   # -> rows drained
```
Closed rows drop out of the view. `close_signals` is fail-closed in prod, returns
`0` in dev on DB-down.

**External sweeps (can't import `app.storage`) drain over HTTP** —
`POST /chat/product-feedback/close-signals` (unauth, same pattern as filing):
```json
{"category":"doc_stale","module":"chat","before":"<iso-ts>"}  // → {"drained": N}
```
Narrow by design: `category` must be a **sweepable** signal (`docs_gap` | `doc_stale`
— never user feedback like `bug`), `module` is **required** (a sweep only closes
what it processed), and optional `before` closes only signals created at/before that
timestamp (so mid-sweep arrivals survive to next week). The full sweep loop over
HTTP: read `/backlog` → refresh + re-embed doc → `POST /close-signals`.

### Failure semantics
`insert_open_feedback` is fail-closed in hosted envs (`CHAT_ENV=staging|prod` →
raises `ProductFeedbackError`) and degrades to a log + `None` in dev. Because gap
logging must never break the answer, **awareness wraps the call** (above) — the
fail-closed raise is for *user-visible* feedback writes, not best-effort harvesting.

### Module slug ↔ doc map (SHARED)
`area_tag == module`. Conceptual slugs (what the user thinks in), mapped to docs:

| slug | doc file | corpus |
|---|---|---|
| `chat` | product-docs/mobius-chat.md | in-scope |
| `rag` | product-docs/rag-backend.md | in-scope |
| `lexicon` | product-docs/lexicon.md | in-scope |
| `skills` | product-docs/skills.md | in-scope |
| `strategy` | product-docs/story-ui-and-landing.md | in-scope |
| `eval` | product-docs/eval.md | in-scope |
| `os` | product-docs/mobius-os.md | pending |
| `credentialing` | product-docs/credentialing-and-roster.md | pending |
| `roster` | product-docs/credentialing-and-roster.md | pending |
| `auth` | product-docs/user-and-auth.md | pending |
| `document-viewer` | product-docs/mobius-document-viewer.md | pending |
| `infra` | product-docs/infrastructure.md | pending |

Canonical list also in code: `app.storage.product_feedback.MODULE_SLUGS`.

---

## Awareness side — SPECIFIED (implementation pending)

### When a miss fires a gap — and the single-threshold invariant

`product_help_search` computes a top-match cosine similarity `s_top` for every
query. **One named constant governs both answerability and gap-filing:**

> **`PRODUCT_HELP_TAU_GAP`** — the single source of truth. The skill uses the
> *same* constant to (a) tell the user it can't answer and (b) fire the gap.
> They **cannot drift, because there is only one value** — this is the invariant
> the feedback agent asked us to guarantee, satisfied by construction, not by
> keeping two numbers in sync.

Three outcomes, distinguished by the top match — no capability-existence *guess*,
it's read off the reality-gate:

| condition | user sees | filed |
|---|---|---|
| `s_top < τ_gap` (nothing relevant) | "I don't have docs on that yet." | **`docs_gap`** |
| `s_top ≥ τ_gap` **and** top chunk `status=planned` | "That's planned — not available yet." | **`feature_request`** |
| `s_top ≥ τ_gap` **and** top chunk `status=current` | the answer | nothing |

Note the correction vs. the skeleton: a `status=planned` hit is **not** a miss —
retrieval *succeeded*, it found the "not-yet-available" doc. So it's its own row
(a capability-demand signal, `routed_to=product_backlog`), still `area_tag=[module]`
— not lumped under below-`τ_gap`.

**Embedder = Vertex `gemini-embedding-001` (1536-dim, output_dimensionality-pinned)** —
the platform's own embedder (no new credential), on pgvector. **Calibrated value:**
`τ_gap = 0.544` (cosine) — set 2026-07-02 by the two-sided probe on **live Vertex+pgvector**
(in-corpus p10=0.602 vs out-corpus p90=0.486 → clean separation; midpoint). Recalibrate
on any embedder/corpus change. The probe:
- *in-corpus probe* — each in-scope doc's own section headings, re-queried, must
  score **well above** τ_gap (else we harvest false gaps on answerable questions);
- *out-of-corpus probe* — a bank of known-absent questions must score **below**
  (else we miss real gaps).

τ_gap is embedder-specific; it is set for gemini-embedding-001. (The offline TF stand-in
used for tests has no reliable separation — plumbing only, never a source of τ_gap.)

_v1 is binary on τ_gap. A middle "weak match" band (a second confidence floor that
also routes `docs_gap`) is a v2 refinement once we've seen the score distribution —
deferred to avoid shipping a second un-calibrated knob._

### The gap write is post-answer and non-blocking
The user's answer returns **first**; the gap write fires after, fire-and-forget
inside the best-effort wrapper. Gap harvesting never adds latency to the turn, and
its failure never touches the answer (the shared invariant).

### The `status=planned` ingest flag (dependency — awareness owns)
At ingest the heading-chunker stamps each chunk's `status` metadata:
- chunks under a `## Not yet available (planned)` H2 (until the next H2) → `status=planned`;
- everything else → `status=current`.

Stored as a free-form Chroma metadata key, read back on the top hit to drive the
disambiguation table above. Zero extra cost — we already chunk by heading.

### What awareness reads
- `docs_backlog` view → curation priority (top-`gap_hits` module = write next; an
  *undocumented* module surfacing here is the strongest "write this doc" signal).
- Raw `docs_gap` verbatims per module (the `?`-membership query) → doubles as
  (a) source material for writing the doc and (b) the **eval query bank** replayed
  through `product_help_search` after the doc lands, to measure the miss-rate drop.

---

## The payoff (shared closing hook)

Once both halves are live the loop is **measurable**: write the doc for the
top-gap module → replay that module's `docs_gap` verbatims through
`product_help_search` → watch its miss-rate drop. That is the eval-lift /
coherence spine (see the republishing + eval-observability work) pointed at
documentation debt. The feedback agent stops being a suggestion box and becomes
the thing that tells us which doc to write and proves we wrote it well.
