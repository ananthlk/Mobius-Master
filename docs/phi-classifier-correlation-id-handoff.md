# PHI classifier — `correlation_id` never reaches the LLM call

**For:** PHI classifier seat · **Raised by:** Payor Policy / platform seat, 2026-09-09
**Status:** logged, not urgent. Ananth: "we will work on this later."
**Repo:** `mobius-skills/phi-classifier` · **Also touched:** `mobius-chat` (already fixed)

---

## What's wrong

Every `phi_classify` row in `mobius_chat.llm_calls` has `correlation_id = NULL` — 113
before the chat-side fix, and still NULL after it. So the LLM cost of PHI classification
attributes to **no turn at all**, on a gate that runs on **every turn**.

Verified live, not inferred. One real turn on revision `00948-t5t`:

```
react_1        cid OK       13:20:09
phi_classify   cid MISSING  13:20:16   ← same turn, between two rows that have it
react_2        cid OK       13:20:19
```

## Where it breaks — one hop, in this repo

```
mobius-chat  api/chat.py           sends correlation_id in the /message-check payload   ✅ fixed, 02b4376
phi-classifier  app/main.py:99     receives it, passes to check_message()               ✅ works
                app/classifier.py:301  stamps it on MessageCheckEnvelope (diagnostics)  ← dead end
                app/detectors/llm.py:85-89  builds the /internal/skill-llm payload:
                                      {system, user, stage, max_tokens}                 ← correlation_id
                                                                                           absent, and the
                                                                                           function never
                                                                                           receives one
mobius-chat  main.py:2576/2642     accepts + forwards correlation_id → llm_calls        ✅ ready
```

**The fix:** thread `correlation_id` from `check_message()` through to the LLM detector
and add it to the payload dict. A parameter on one function, one dict key. Both ends
already support it — this is the only missing hop.

**Chat's side is done and was necessary but not sufficient** — without it the classifier
had nothing to forward. Four chat call sites now send it (`api/chat.py`,
`skills/phi_gate.py`, `api/product_feedback.py:113`, `skills/builtin/product_feedback.py:260`).

**Do NOT widen the payload further.** The classifier receives raw clinical text; a UUID
is the only safe addition. That caution is written into chat's source at the call site.

## Why it matters

- **Cost attribution.** The PHI gate runs on every turn. Anyone costing a turn today
  undercounts by the whole PHI classification pass, and the total still looks plausible.
- **It is a producer-without-consumer instance** — the systemic finding of the chat
  review (12 confirmed). A join column populated on some paths and dead on others is
  worse than absent, because a future consumer joins `llm_calls` to turns, gets ~55% of
  rows, and believes it has all of them. Same silent-partial shape as
  `blueprint_snapshot` at 0-of-2,744.

## My error, recorded because it caused work

I traced this chain and reported to Ananth and to Chat Master that **"every hop already
supports it except the first — two lines."** That was wrong. I saw
`classifier.py:301` passing `correlation_id=correlation_id` and read it as forwarding to
the LLM call; it populates `MessageCheckEnvelope`, the PHI diagnostics record. Two
different destinations, and I did not check which. Chat implemented against my trace.

**An assignment is not a delivery** — the same shape as *an import edge is not a
consumption edge*, which this program logged four hours earlier. Only sending a real turn
and reading the row caught it; the gate was green and the code review looked right.

## Not in scope here

- `rag_fact_check` at 0% — eval-path only, so the NULL may be truthful. mobius-rag's.
- `integrator` at 0% — untraced.
- Marking `llm_calls.correlation_id` non-joinable until all paths populate it — Eval's
  flag, chat's column.
