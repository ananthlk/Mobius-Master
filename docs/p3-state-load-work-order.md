# P3 · `state_load` — work order

**Node:** `state_load` · RED · 5 findings · coverage **ABSENT** (no test calls it)
**Owner:** Chat Master · **Gate:** P3, plus the module's own findings (fix-inside-refactor)
**Raised by:** Payor Policy / platform seat, 2026-09-09. All five verified against the code.

---

## The shape: this is ONE defect with four amplifiers, not five bugs

A transient DB read failure **destroys** accumulated thread state, nothing can detect it
afterwards, and the fix already exists thirty lines away in the same file.

### The core — `threads.py:560-577`

```python
def get_state(thread_id) -> dict | None:
    """Return state_json for thread_id, or None if no row."""   # ← the docstring
    result = db_query(...)
    if _err_code(result) is not None:
        logger.warning("Failed to get state: %s", ...)
        return None                                              # ← ERROR
    if not rows:
        return None                                              # ← NO ROW
```

**Error and absence are the same value**, and the docstring only mentions the second.
So every caller reasonably reads `None` as "new thread".

`state_load.py:35` then does `raw = get_state(ctx.thread_id) or {}`, builds `ThreadState`
from `DEFAULT_STATE`, and when the message carries a delta calls `save_state_full` —
docstring *"Replace state entirely (no merge)"*, an UPSERT that is a full replace by
design (`:622-629`).

**One failed read + any delta-bearing message = the whole conversation overwritten with
defaults plus that turn.** Not skipped. Destroyed.

**Blast radius:** `get_state` has **9 callers**; five use the `or {}` idiom —
`state_load.py:35`, `react_loop.py:3494`, `main.py:2261`, `skills/document_upload.py:73`,
`skills/builtin/document_uploads.py:54`. `save_state_full` has **6 call sites** across
`state_load`, `react_loop` and `orchestrator`. This is not one path.

### Amplifier 1 — the reset is indistinguishable from a normal turn

`state_version` increments on that same write, so the row goes 11 → 12 exactly as a
healthy turn would. **No artifact distinguishes "turn 12 of a conversation" from "state
reset, now calling itself 12".**

### Amplifier 2 — `state_version` is write-only

Grepped: it appears only in the INSERT and two docstrings, **never in a comparison
anywhere in `app/`**. So it cannot detect the reset, *and* read-modify-write through
`get_state`/`save_state_full` is unguarded — two concurrent turns on one thread are a
lost update.

### Amplifier 3 — the file already knows better

`_write_state_row` (`:580-601`) warns and returns on `connection_error` but
**`raise RuntimeError`** on anything else. **Write path loud, read path silent, one
module — and the silent one is the one that loses data.** `get_state` is the single
function not following its own file's convention.

### Amplifier 4 — not chat's, do not fix here

`mobius_chat` has **no query guards**: `statement_timeout = 0`, no idle-in-transaction
guard, while `mobius_rag` carries a 120s idle timeout and is the only per-database
override on the instance. DB seat's. Its consequence for this node: SQLSTATE 57014
cannot fire, so `db_client`'s `timeout` branch is dead-looking code that would come alive
the moment anyone sets one.

---

## The change

**1 · Distinguish error from absence.** `get_state` must not return the same value for
both. Shape is yours — an exception on error matching `_write_state_row`'s convention, or
a sentinel — but the caller has to be *able* to tell. Update the docstring; it is
currently wrong, and the wrong docstring is why every caller's `or {}` looks reasonable.

**2 · A read failure must never lead to a full-replace write.** The rule, not the
mechanism: *state is only replaced from state that was actually read.* Whether that is a
guard in `state_load`, a refusal in `save_state_full`, or both is your call.

**3 · Make `state_version` guard the write.** It is already incremented and already
unread. Compare-and-set on the version we read closes both the lost-update race and gives
the reset an artifact.

**4 · Fix all five `or {}` sites, or none.** Fixing `state_load` alone leaves
`react_loop.py:3494` doing the same thing on the same table — the half-true outcome we hit
on the PHI fix, where four call sites existed and two were scoped.

---

## Gate

Standard P3 gate, plus two conditions specific to this node:

- **Coverage is ABSENT — there is nothing to regress against.** A test that proves a
  failed read does **not** overwrite state is part of the change, not a follow-up. Per
  Eval's rule the assertion goes against the **stored row**, not a return value: force a
  read error, send a delta-bearing message, assert `chat_state.state_json` is unchanged
  and `state_version` did not advance.
- **`state_load` emits spans; `POST /chat` does not.** You can see the load's timing but
  not the boundary feeding it. Do not read a 0 there as "free".

**Do not fix inside this pass:** the query guards (DB seat), and anything in
`POST /chat`'s 15 findings — most are FK rulings and auth posture belonging to other
seats.

---

## Owner tags

All five findings are currently **owner-unassigned** — they came from my review and the
DB seat's scope lens and were never tagged `OWNER(chat)`. Findings 1–4 are chat's;
finding 5 is the DB seat's. I will retag rather than leave the counts misleading.
