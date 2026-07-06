# Feedback agent — design spec

Status: design only (no code yet). Author-reviewed 2026-07-02.

A proactive **feedback** skill for chat, carrying two instruments over one spine
(§3b): **open** product feedback (categorical + free text) and a **satisfaction
survey** (scored — CSAT / CES / NPS). Modeled on the `vibe` skill (standalone
Cloud Run service + chat-side `SkillSpec` handler returning a `SkillEnvelope`),
but — unlike vibe — it **persists**, and it lives *inside* the ReAct loop rather
than beside it (§6). It carries its own envelope and persistence modules.

---

## 1. Why this exists (and what it is *not*)

Chat already has a **turn-scoped, reactive quality rating**: the 👍/👎
`FeedbackComponent` under every assistant message, writing to `chat_feedback`
(plus `chat_source_feedback`, `llm_performance_feedback`, `adjudication_feedback`).
That answers *"was this answer good?"*

This skill answers a different question: *"what do you think of the product?"*
Open feedback — a wish, a complaint, a bug, a bit of praise — captured across
categories, **thread/session-scoped**, and volunteered rather than rated.

| | Thumbs (`chat_feedback`) | Feedback skill (`product_feedback`) |
|---|---|---|
| Scope | one turn / one answer | thread, session, or the product as a whole |
| Shape | closed: up/down + canned reason | open: category + free text + sentiment |
| Trigger | user clicks after a message | inline-detected · periodic · on-demand |
| Persists to | `chat_feedback` | `product_feedback` (+ prompt state/events) |
| Stays | yes — unchanged | new, complementary |

It sits beside the thumbs, never replaces them. The two never render at once
(see §6 — the nudge is suppressed on any turn where the user just rated).

## 2. Naming

- Skill name (planner tool): `product_feedback`
- Display name: "Share feedback"
- Service: `mobius-feedback` (standalone, Cloud Run, parallels `mobius-skills/vibe`)
- Chat handler: `mobius-chat/app/skills/builtin/product_feedback.py`
- Tables: `product_feedback`, `feedback_prompt_state`, `feedback_prompt_events`

Deliberately *not* named `feedback` to avoid collision with the existing
`chat_feedback` turn-rating path.

## 3. Categories

Eight, tuned for a healthcare-ops RAG product. The classifier picks one; the
user can override in the capture card.

| key | label | routes to |
|---|---|---|
| `accuracy_trust` | Wrong / unsupported answer | triage queue |
| `coverage_gap` | Missing payer / state / topic | corpus backlog |
| `bug` | Something broke or errored | triage queue |
| `speed` | Too slow | product backlog |
| `usability` | Confusing UI / navigation | product backlog |
| `feature_request` | "I wish it could…" | product backlog |
| `praise` | What's working well | none (store only) |
| `other` | Anything else | product backlog |

Categories apply to the **open** instrument. The **survey** instrument (§3b) is
scored, not categorized — though its optional follow-up comment reuses these.

## 3b. Two instruments, three altitudes

The skill carries two feedback *instruments* over one shared spine (same
react-loop signal-in, cadence machinery, persistence, envelope, funnel):

1. **Open** — categorical + free text (§3). Volunteered or nudged. "Tell us anything."
2. **Survey** — a *scored* instrument, `survey_type ∈ {csat, ces, nps}`.
   Quantitative, sampled, benchmarkable over time. This is the customer-satisfaction
   flavor.

Together with the thumbs you already have, that's **three altitudes** — each
answers a different question, none replaces another:

| altitude | instrument | question | scope | status |
|---|---|---|---|---|
| turn | thumbs (`chat_feedback`) | was this answer good? | one message | exists |
| thread | CSAT / CES survey | how did that go? | a resolved task | new |
| relationship | NPS survey | would you recommend Mobius? | the product | new |
| any | open feedback (§3) | anything on your mind? | product-wide | new |

**Instruments compose (the two-step).** A survey is score-first — one tap, low
friction (NPS 0–10, CSAT 1–5, CES 1–5). *After* the score, an optional open
follow-up ("what's the main reason for your score?") reuses the open-capture card
and links back via `parent_feedback_id`. A detractor's score can escalate into a
full categorized item; a promoter's can stop at the tap. The two instruments feed
each other rather than competing.

**Why the scores earn their place here.** NPS/CSAT trended against `qc_audit`
pass-rate and `lexicon_revision` ties *satisfaction* to the quality metrics you
already track — did the last corpus republish move CSAT? That's the same
eval/observability spine, extended to the human signal (see the eval-observability
and republishing-agent work). A raw thumbs-up rate can't answer "are users more
satisfied this month"; a sampled CSAT/NPS can.

## 4. How it fires (the trigger surface)

All three converge on the **same capture flow** (§5). They differ only in how
the flow is *entered*.

### A. Inline detection (implicit)
No separate classifier. `product_feedback` is in the planner's live tool manifest
with a `vibe`-style "use when" description, so the planner selects it by normal
ReAct reasoning when a user message *is* a product opinion / wish / complaint
rather than a question or task (§6, seam 2). It then confirms rather than
assuming: *"Sounds like feedback about search coverage — want me to log it?"*

This is the headline behavior the user asked for: *if the user had a thought in
the chat session, this skill gets invoked* — and it costs nothing extra, because
the loop already reasons over the manifest every turn.

### B. Periodic (cadence *signal*, not a gate)
This is **not** a post-loop gate that fires on its own. It's a **signal injected
into the planner's context** each turn — a new section in `build_reasoning_context`
(`app/pipeline/react/prompts.py`), sitting beside the existing strategy-bandit
state and guidance-mode injections. A small provider computes it from
`feedback_prompt_state` and, when feedback is *eligible*, adds a line the planner
reasons over:

```
FEEDBACK SIGNAL: due (5 threads since last ask, generic).
After you have answered the user's request, you MAY offer feedback by setting
offer_feedback on your final step. Skip it if the user is mid-task or frustrated.
```

Eligibility (all AND — computed in code, this is the hard ceiling the model
can't override):

- `threads_since_prompt ≥ FEEDBACK_CADENCE_THREADS` (default 5) **or**
  `turns_since_prompt ≥ FEEDBACK_CADENCE_TURNS` (default 25)
- `snooze_until` is null or in the past
- `opted_out = false`
- not already nudged this thread (`FEEDBACK_SESSION_COOLDOWN`, default 1)
- the current turn did **not** carry a thumbs rating (don't double-ask)

When eligible, the signal is injected; when not, it's absent and the planner
never sees it. If the current turn's `qc_audit.passed = false` (a visible miss),
the provider tags the signal `kind=targeted_miss, category=accuracy_trust` and
the injected line becomes *"the last answer missed — you may ask what they
expected."* A failure is a great feedback moment; a chirpy "how are we doing?"
right after it is tone-deaf, so the model gets a different instruction.

The planner expresses its decision as an `offer_feedback` field on its finalize
step (§6) — **not** by calling a tool. The integrator renders the resulting
**nudge chip** (open) or **score widget** (survey). Dismiss → the client posts a
`dismissed` event; the service sets `snooze_until = now + FEEDBACK_SNOOZE_ON_DISMISS threads`.

**Three cadence policies feed one signal.** The eligibility above is the *open*
policy. The survey instrument (§3b) adds two more, each computed by the same
provider and expressed through the same `offer_feedback` field — only the clock
and the rendered widget differ:

| policy | `offer_feedback.kind` | clock / eligibility | never fires when |
|---|---|---|---|
| `open_periodic` | `generic` · `targeted_miss` | ≥5 threads or ≥25 turns since last | just rated · snoozed · opted-out |
| `csat_thread` | `csat` | a task just resolved (`is_complete`, ≥3 turns), sampled at `CSAT_SAMPLE_RATE` | error/degraded turn · already CSAT'd this thread |
| `nps_relationship` | `nps` | `now − last_nps_at ≥ NPS_INTERVAL_DAYS` (default 45), sampled | right after a miss · < interval · opted-out |

Only one signal is ever injected per turn (priority: explicit > inline > NPS >
CSAT > open), so the planner is never handed two asks at once. CSAT rides the
back of a *good* thread completion (its natural moment); NPS is deliberately
decoupled from any single answer, and — unlike the open path — is suppressed
right after a miss, because a relationship score taken in a moment of frustration
is noise, not signal.

### C. On-demand (explicit)
A persistent "Share feedback" affordance (message-tools menu + composer) opens
the flow directly, ignoring the cadence gate. Typing "I have feedback" / "can I
suggest something" also routes here (the planner sees `product_feedback` in its
manifest). Always available.

## 5. The capture flow (shared by A/B/C)

This is the body of **Act 2** in §6 — it *is* the `product_feedback` tool
dispatch. All three triggers enter here the same way: the planner emits
`tool: product_feedback` and the loop dispatches it.

```
enter(trigger, verbatim?, context_excerpt, thread_id, turn_id, user_id, org)
  │
  1. classify           POST mobius-feedback /classify
  │    verbatim + last-3-turns excerpt  →  {category, sentiment,
  │                                          severity, summary, tidied}
  │    (LLM call in the service, like vibe; cheap model)
  │
  2. render capture card (§7)
  │    prefilled: category chip (editable), sentiment, tidied text,
  │    optional area tags (chat / roster / pipeline / rag / …)
  │
  3. user acts ─── submit ──► 4
  │           └── edit ─────► stays in 2
  │           └── dismiss ──► log dismiss event, snooze, END
  │
  4. capture            POST mobius-feedback /capture  (envelope → §8)
  │    write product_feedback row
  │    route by category (triage queue / backlog / none)
  │    if bug|coverage_gap → spawn mobius_task, store linked_task_id
  │
  5. update prompt state   reset threads/turns counters,
  │                        set last_captured_at, bump capture_count
  │
  6. ack                one short vibe-style line, e.g.
  │    "Logged — filed under coverage. Thanks for the nudge."
  │    (returned as SkillEnvelope.text)
  │
  7. telemetry          append feedback_prompt_events row(s)
       (shown → opened → submitted, or shown → dismissed)
```

Steps 1 and 4 are the two service endpoints that do real work; step 6 is the
only thing spliced into the assistant's reply.

## 6. Where it lives in the ReAct loop

There is **no** `after_turn()` state machine. The chat is a bounded ReAct loop
(`app/pipeline/react_loop.py`, `for iteration in range(max_it)`): each round the
planner reads `build_reasoning_context()`, emits a decision JSON
(`{thought, tool, inputs, is_complete}`), a tool is dispatched via
`registry.dispatch`, and the observation feeds the next round. Feedback plugs
into that machinery at exactly two existing seams — **one signal in, two acts
out** — and nothing else.

**Seam 1 — signal in (`build_reasoning_context`).** A cadence provider adds the
`FEEDBACK SIGNAL` line (§4B) when eligible. That is the *entire* periodic
mechanism. It rides the same rail as the bandit-state and guidance-mode lines
already injected there.

**Seam 2 — the tool manifest (`_react_reasoning_system`).** `product_feedback`
is a registered `SkillSpec`, so it appears in the live manifest. The planner
selects it by normal reasoning — no classifier, no threshold, no pre-pass. This
covers **inline** (planner sees a product opinion in the message) and
**on-demand** (user clicked, or asked "can I suggest something").

Two acts come out of the loop:

```
Act 1 — the ASK (nudge chip).  Cheap, no tool call, no added latency.
  When the FEEDBACK SIGNAL is present AND the moment is right, the planner adds
  a field to its finalize step:
      { "thought": ..., "tool": null, "is_complete": true,
        "answer": "...the real answer...",
        "offer_feedback": { "kind": "generic"|"targeted_miss"|"csat"|"nps" } }
  parsing.py reads offer_feedback; the integrator renders the chip beside the
  answer. If the signal was absent or the planner judged the moment wrong, the
  field is omitted and nothing renders.

Act 2 — the CAPTURE (product_feedback tool).  A real in-loop dispatch.
  Emitted whenever the planner selects the tool — inline, on-demand, or after
  the user taps a chip (that tap starts a fresh turn whose message routes here):
      { "thought": ..., "tool": "product_feedback",
        "inputs": { "trigger": "inline|periodic|on_demand",
                    "verbatim": "...", "context_excerpt": "..." } }
  dispatch → the skill returns a SkillEnvelope:
      SkillEnvelope(text=ack_line, signal="no_sources",
                    extra={ "feedback_id", "category", "capture_card": {...} })
  The loop observes it; the integrator renders capture_card and splices ack_line.
```

Division of labor: the **model owns the decision** (ask now? which category?
skip because they're mid-task?). **Code owns the accounting and the ceiling** —
the provider computes eligibility, and the service (§10) writes `product_feedback`
/ `feedback_prompt_events` and advances `feedback_prompt_state`. The model can
never ask more often than eligibility allows, because a suppressed signal is
simply never injected.

No new post-loop hook, no parallel gate — the feedback path is just three edits
to files the loop already runs: a context section, a manifest entry, and one
optional field on the finalize JSON.

## 7. UI states

All inline in the chat stream (never a blocking modal — respects the
iframe/`window.confirm` constraint noted in prior work):

1. **Nudge chip** (open) — one line + "Share feedback" / dismiss (✕). Low-weight,
   below the assistant message. Generic or targeted-miss variant.
2. **Score widget** (survey) — the score-first step: a 0–10 row (NPS) or 1–5 row
   (CSAT/CES) with a one-line prompt and dismiss. One tap records the score and
   advances to the optional follow-up. Lowest friction of all the states.
3. **Capture card** (open, or survey follow-up) — expands in place. Category chips
   (one pre-selected), sentiment toggle, textarea (pre-filled with the tidied
   verbatim on the inline path; empty on the periodic path; seeded with "main
   reason for your score?" on the survey follow-up), optional area tags,
   Submit / Cancel.
4. **Acknowledgement** — collapses to a one-line confirmation with the assigned
   category/score and, if routed, a "tracked" pill. Auto-settles after ~3s like
   the thumbs component.

The React/DOM component lives beside `FeedbackComponent.ts` in
`mobius-os/extension/src/components/feedback/`, injected by `SystemMessage.ts`
under a new `productFeedback` render flag (parallel to the existing
`feedbackComponent` flag).

## 8. FeedbackEnvelope (the skill's contract + persisted shape)

Dataclass with `to_dict()`, same pattern as `InstantRagEnvelope` / `ReadEnvelope`.
It *is* the output contract and maps 1:1 to a `product_feedback` row.

```python
@dataclass
class FeedbackEnvelope:
    feedback_id: str            # uuid4
    trigger: str                # inline | periodic | on_demand
    status: str = "captured"    # draft | captured | triaged | routed | closed

    # instrument (§3b)
    kind: str = "open"                  # open | survey
    survey_type: str | None = None      # csat | ces | nps (null for open)
    score: float | None = None          # the numeric score (null for open)
    score_scale: str | None = None      # nps_0_10 | csat_1_5 | ces_1_5
    parent_feedback_id: str | None = None   # links survey score ↔ its follow-up

    # context / identity
    thread_id: str = ""
    correlation_id: str = ""    # the turn it attaches to (nullable for on_demand)
    user_id: str = ""
    org_slug: str = ""

    # classification (open instrument; also the survey follow-up)
    category: str = "other"     # §3 keys
    sentiment: str = "neutral"  # positive | negative | neutral | mixed
    severity: str = "low"       # low | medium | high
    summary: str = ""           # one line (classifier)
    verbatim: str = ""          # the user's own words
    tidied: str = ""            # cleaned-up phrasing (classifier)
    area_tags: list[str] = []   # module names: chat, roster, pipeline, rag…

    # routing
    routed_to: str | None = None    # triage_queue | product_backlog | support | none
    linked_task_id: str | None = None

    # provenance / parity with chat_turns
    config_sha: str = ""
    source_context_hash: str = ""

    created_at: str = ""        # ISO
    updated_at: str = ""
    usage: dict = {}            # LLM token metadata (classify step)
    extra: dict = {}            # escape hatch

    def to_dict(self) -> dict: ...
```

The chat handler wraps the ack in the standard `SkillEnvelope`:

```python
SkillEnvelope(
    text=ack_line,
    signal="no_sources",
    extra={"feedback_id": ..., "category": ..., "capture_card": {...}},
)
```

## 9. Persistence (three tables + one view)

Postgres, `CHAT_RAG_DATABASE_URL` (same instance as `chat_feedback`). Migrations
in `mobius-chat/db/schema/NNN_*.sql`. Service-side `feedback_db.py` uses the
db-agent MCP client with psycopg2 fallback (the
`provider-roster-credentialing` pattern).

### `product_feedback` — the items (one row per envelope)
```sql
CREATE TABLE product_feedback (
    feedback_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger          TEXT NOT NULL CHECK (trigger IN ('inline','periodic','on_demand')),
    status           TEXT NOT NULL DEFAULT 'captured',

    kind             TEXT NOT NULL DEFAULT 'open' CHECK (kind IN ('open','survey')),
    survey_type      TEXT CHECK (survey_type IN ('csat','ces','nps')),
    score            NUMERIC,                   -- null for open
    score_scale      TEXT,                      -- nps_0_10 | csat_1_5 | ces_1_5
    parent_feedback_id UUID REFERENCES product_feedback(feedback_id),

    thread_id        UUID REFERENCES chat_threads(thread_id),
    correlation_id   TEXT,                      -- turn, nullable
    user_id          TEXT NOT NULL,
    org_slug         TEXT,

    category         TEXT,                      -- required for open, null for a bare survey score
    sentiment        TEXT DEFAULT 'neutral',
    severity         TEXT DEFAULT 'low',
    summary          TEXT,
    verbatim         TEXT,
    tidied           TEXT,
    area_tags        JSONB DEFAULT '[]',

    routed_to        TEXT,
    linked_task_id   TEXT,

    config_sha       TEXT,
    source_context_hash TEXT,
    usage            JSONB DEFAULT '{}',
    extra            JSONB DEFAULT '{}',

    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- a survey row must carry a score; an open row must carry a category
    CHECK ((kind = 'survey' AND score IS NOT NULL AND survey_type IS NOT NULL)
        OR (kind = 'open'   AND category IS NOT NULL))
);
CREATE INDEX product_feedback_user_idx     ON product_feedback(user_id, created_at DESC);
CREATE INDEX product_feedback_category_idx ON product_feedback(category, created_at DESC);
CREATE INDEX product_feedback_status_idx   ON product_feedback(status) WHERE status <> 'closed';
CREATE INDEX product_feedback_survey_idx   ON product_feedback(survey_type, created_at DESC) WHERE kind = 'survey';
```

### `feedback_prompt_state` — per-user cadence (one row per user, upsert)
```sql
CREATE TABLE feedback_prompt_state (
    user_id               TEXT PRIMARY KEY,
    threads_since_prompt  INT NOT NULL DEFAULT 0,
    turns_since_prompt    INT NOT NULL DEFAULT 0,
    last_prompted_at      TIMESTAMPTZ,
    last_captured_at      TIMESTAMPTZ,
    last_csat_at          TIMESTAMPTZ,           -- csat_thread clock
    last_nps_at           TIMESTAMPTZ,           -- nps_relationship clock
    snooze_until          TIMESTAMPTZ,           -- set on dismiss
    opted_out             BOOLEAN NOT NULL DEFAULT false,
    prompt_count          INT NOT NULL DEFAULT 0,
    capture_count         INT NOT NULL DEFAULT 0,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `feedback_prompt_events` — append-only funnel log
```sql
CREATE TABLE feedback_prompt_events (
    event_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     TEXT NOT NULL,
    thread_id   UUID,
    trigger     TEXT NOT NULL,                   -- inline | periodic | on_demand
    kind        TEXT,                            -- open | csat | nps (which instrument was offered)
    action      TEXT NOT NULL,                   -- shown | opened | scored | submitted | dismissed | snoozed | opted_out
    category    TEXT,
    score       NUMERIC,                         -- set on a `scored` survey event
    feedback_id UUID REFERENCES product_feedback(feedback_id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX feedback_prompt_events_funnel_idx ON feedback_prompt_events(trigger, action, created_at DESC);
```

### `feedback_health` — view for the admin dashboard
Two rollups over the same spine:
- **Open funnel** — shown / opened / submitted / dismissed rates, category mix,
  sentiment trend, targeted-miss capture rate.
- **Satisfaction** — rolling **NPS** (`%promoters − %detractors`, 9–10 vs 0–6 on
  the 0–10 scale) and **CSAT** (`%top-2-box`), each as a trend, plus response
  rate (`scored / shown`). The payoff join: NPS/CSAT bucketed against
  `qc_audit` pass-rate and `lexicon_revision` — does a corpus republish move the
  score? Powers a panel next to the existing `/chat/admin/queries` view.

## 10. Service surface (`mobius-feedback`)

Parallels `mobius-skills/vibe/app/`. FastAPI, Cloud Run, pinned `min=max=1` if it
ever holds in-process job state (it doesn't today, but note the RAG-API lesson).

| endpoint | purpose |
|---|---|
| `POST /classify` | verbatim + excerpt → `{category, sentiment, severity, summary, tidied}` (LLM) · open only |
| `POST /capture`  | FeedbackEnvelope → persist, route, spawn task, return ack line · open **or** survey (a bare survey score skips `/classify`) |
| `POST /score`    | one-tap survey score → persist survey row, return `{parent_feedback_id, followup_prompt}` for the optional two-step |
| `GET  /cadence?user_id=` | reads `feedback_prompt_state` → `{signal, kind, reason}` across all three policies (§4B) |
| `POST /event`    | append a `feedback_prompt_events` row |
| `GET  /health`   | health check |

Files (vibe parity): `app/main.py`, `app/config.py`, `app/prompts.py`,
`app/llm_client.py`, `app/policy.py` (safety filter — never surface PHI/clinical
content back), plus `app/models.py`, `app/envelope.py`, `app/feedback_db.py`.

## 11. Config knobs (env, all tunable)

```
# open_periodic policy
FEEDBACK_CADENCE_THREADS     5      # open nudge every N threads
FEEDBACK_CADENCE_TURNS       25     # …or N turns, whichever first
FEEDBACK_SNOOZE_ON_DISMISS   3      # threads to snooze after a dismiss
FEEDBACK_SESSION_COOLDOWN    1      # max asks per thread (any instrument)

# csat_thread policy
FEEDBACK_CSAT_SAMPLE_RATE    0.25   # survey 1 in 4 substantive thread completions
FEEDBACK_CSAT_MIN_TURNS      3      # only after a real interaction

# nps_relationship policy
FEEDBACK_NPS_INTERVAL_DAYS   45     # at most one NPS ask per user per window
FEEDBACK_NPS_SAMPLE_RATE     1.0    # of eligible users (dial down for large N)

FEEDBACK_MODEL               (cheap classify model)
FEEDBACK_SKILL_URL           http://localhost:8060/  (dev)
FEEDBACK_TIMEOUT_SEC         6
```

Note: `FEEDBACK_INLINE_TAU` is gone — inline is planner-selected from the
manifest (§4A), there's no threshold to tune.

## 12. Open questions

1. **User identity for cadence.** `chat_turns.user_id` exists (migration 032);
   confirm it's populated for all sessions, else cadence keys on `session_id`.
2. **Org-level rollup.** Do we want per-org feedback digests for CS, or just the
   global admin view? Affects whether `org_slug` needs a backfill join.
3. **Task spawn target.** `bug`/`coverage_gap` → `mobius_task` (roster pattern)
   vs. a dedicated `feedback_triage` queue. Leaning `mobius_task` for reuse.
4. **`offer_feedback` reliability.** The nudge now rides an optional field on the
   planner's finalize JSON (§6). Two risks to watch: the planner *over-offering*
   (asks whenever the signal is present — mitigated by the eligibility ceiling +
   an explicit "skip if mid-task" instruction) and *under-offering* (never sets
   it). Needs an eval on a turn bank: given the signal, does the planner offer at
   the right moments? Fallback if unreliable: promote the ask to a deterministic
   render when eligible AND the planner didn't object.
5. **Opt-out UX.** Where does "stop asking" live — a per-user toggle in settings,
   or only the implicit snooze-on-dismiss ladder?
