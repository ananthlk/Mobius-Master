# Instant RAG — Progress & Notify Contract (P0)

**Owner:** Instant RAG agent · **Status:** Draft for build · **Date:** 2026-07-09
**Consumers:** RAG (emit side), chat (bridge + render + notify), UX (affordance + cutoff).

The P0 keystone. Replaces today's all-background flow (upload → 15 s poll thread →
system message) with one adaptive path: live foreground progress for fast docs, durable
notify for slow ones. Transport-agnostic — RAG picks the SSE mechanism (reuse
`ChunkingEvent` vs a new lightweight stream); this fixes the *event shape and semantics*.

---

## 1. Unified upload response (immediate)

`POST /chat/upload` (renamed; `/chat/roster-upload` stays a back-compat alias) returns as
soon as the doc is accepted and enqueued — never blocks on processing:

```json
{
  "document_id": "uuid",
  "upload_id": "uuid",
  "filename": "Aetna_policy.pdf",
  "status": "processing",
  "page_count": 12,
  "estimated_seconds": 9,
  "progress_channel": "/chat/uploads/{document_id}/events"
}
```

`estimated_seconds` is the client's hint for the foreground/background decision (§4). It
replaces today's `ux_path`/`eta_minutes`/`redirect_url` triad.

---

## 2. Progress event stream (SSE)

`GET /chat/uploads/{document_id}/events` — Server-Sent Events, scoped to one document.
Chat bridges it from RAG's per-`document_id` progress source. One event per stage
transition, plus periodic ticks within long stages. Every event:

```json
{
  "document_id": "uuid",
  "upload_id": "uuid",
  "stage": "chunking",
  "pct": 45,
  "chunks_done": 9,
  "chunks_total": 20,
  "eta_seconds": 5,
  "message": "chunking (9/20)",
  "terminal": false
}
```

**Stages (ordered):** `queued → extracting → chunking → embedding → publishing → ready`,
or `failed` from any stage.
- `pct` is monotonic 0–100 across the whole pipeline (not per-stage), so a single bar
  fills cleanly. Round to integer.
- `chunks_done`/`chunks_total` present once chunking starts (drive the "9/20" microcopy);
  omit before then.
- `eta_seconds` best-effort; omit if unknown rather than guessing.

**Terminal events** (`terminal: true`):
- `ready`: adds `chunks_count`, `tier: "private"`. Fast path renders "ready" and enables
  the `search_uploaded_document` tool; composer auto-fills a suggested question.
- `failed`: adds `error` (short human string), `retryable: true|false`, and
  `failed_stage`. **Retry semantics depend on where it failed:**
  - Failed *during processing* (extract/chunk/embed/publish — bytes already persisted to
    RAG's GCS, `document_id` exists): retry **re-triggers the pipeline on the existing
    `document_id`** (RAG re-process, no re-upload). This is the common case.
  - Failed *before persistence* (the upload/store itself, no durable `document_id`):
    retry requires the user to re-select the file (re-POST `/chat/upload`).
  - `retryable` reflects whether a retry can succeed at all (e.g. a corrupt/unreadable
    file is `retryable: false` → offer Remove, not Retry).

The stream closes after the terminal event. If the client (re)subscribes after the doc is
already terminal, the endpoint immediately emits the terminal event and closes — so a
late/background subscriber is never left hanging (replaces the poll-then-timeout race).

---

## 3. Durable notify (works whether or not anyone is watching)

Independent of the SSE stream, so a user who navigated away still learns the doc is ready:

1. **System message** into the origin thread (`role='system'` in `chat_turn_messages`) —
   kept from today. `ready`: "✓ {filename} is ready — ask me about it." `failed`:
   "⚠ {filename} failed to process." Idempotent per `document_id` (don't double-post if
   the foreground client already surfaced ready).
2. **Task-manager signal** keyed to the owning `user_id`
   (`instant_rag_uploads.user_id`) → surfaces a Vault badge / task-card wherever the user
   is. `step_done` on ready, `step_failed` on failure. This is the cross-surface,
   cross-thread notify the poll-thread never had.
3. **Catalog update** — `instant_rag_uploads`: set `chunks_count`; `status` stays
   `active` (processing lifecycle lives on the document, not the catalog row).

---

## 4. Foreground vs background — one path, client decides the *feel*

No server-side `ux_path` branch, no user-facing toggle. The client:

- Renders **inline foreground progress** (the §2 bar + stage microcopy) while
  `status=processing` **and** the user is still on the thread **and**
  `elapsed < FOREGROUND_CUTOFF_S`.
- On `ready` while foreground: fill the composer with a suggested question, let them ask.
- At the cutoff, or when the user navigates away, **drop to background**: stop rendering
  inline progress; rely entirely on §3. The SSE endpoint's replay-on-terminal (§2) means
  re-entering the thread later still shows the final state.

**`FOREGROUND_CUTOFF_S`** is a single client constant (default **12 s**), owned by UX.
It's a display decision only — backend behavior is identical either way.

> **REVISION 2026-07-09 (Ananth, live testing): always show progress.** The original model
> only opened the SSE stream on the foreground path, so background/large docs showed *nothing*
> — confirmed in prod logs (`/chat/uploads/{id}/events` was never subscribed for real uploads).
> That's backwards: progress matters *most* for the slow docs. New rule: **open the SSE and
> show live progress for EVERY upload.** Foreground vs background decides whether the user is
> **blocked** (prominent strip, stay-and-watch) vs **freed** (compact persistent indicator they
> can glance at), NOT whether progress is visible. The user must always be able to see where
> their doc is — never a silent "processing" with no signal.

---

## 5. What each agent builds

- **RAG** — expose a per-`document_id` progress source emitting the §2 stages/fields
  (decide: extend `ChunkingEvent` SSE vs a new endpoint). Must emit a terminal `ready`
  with `chunks_count` and `failed` with `error`/`retryable`. Late-subscribe replay of the
  terminal state.
- **chat** — rename endpoint + unify the two entry points onto the composer; on upload,
  open the SSE channel and render §2; implement §3 (system message idempotency + the
  task-signal keyed to `user_id` + catalog `chunks_count`); the §4 cutoff logic.
- **UX** — the progress affordance (bar + stage microcopy + ready→auto-ask), the failed
  state + retry, the background "I'll ping you" copy, and the `FOREGROUND_CUTOFF_S` value.

---

## 5b. Querying a doc that's still indexing (the "ask again" anti-pattern)

When the ReAct loop resolves an attached doc for a query but it isn't `ready` yet,
**never return "please wait and ask again"** — that pushes polling onto the user. The
loop already knows the doc's progress (§2 endpoint). Branch on ETA, mirroring the
foreground cutoff:

- **Wait (short) — the common case.** If the doc is nearly done or ETA ≤ ~15 s
  (`WAIT_BUDGET`, safely under the 60 s LB idle limit), **hold the turn**: keep the
  "reading your document…" state, poll progress until `ready`, then run
  `search_uploaded_document` and answer in the same turn. The user just waits a beat and
  gets their answer — they never see "not indexed."
- **Defer + auto-deliver (long).** If ETA > `WAIT_BUDGET`, answer:
  *"Your document is still indexing (~N). I'll answer the moment it's ready — no need to
  re-ask."* Register the pending query to **auto-run on the doc's `ready` event** (the §3
  notify hook) so the answer is delivered proactively, not re-requested.
- **Failed indexing** → surface the failure + retry affordance (§2 failed), not a wait.

Principle: **wait, or promise-and-deliver — never make the user re-ask.** Owners: chat
(ReAct loop / `search_uploaded_document` / `_resolve_upload_document_id`), UX (the wait
state copy + the "still indexing, I'll answer when ready" message).

## 6. Out of scope for P0 (later phases)
- Vault surface (P1) — consumes the same catalog + notify.
- Promotion tiers / separate org store (P2) — `tier` in the ready event is always
  `"private"` in P0.
