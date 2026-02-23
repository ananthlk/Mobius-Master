# Relentless User Pursuit & Continuity Plan

**Goal:** The system maintains a master objective list per thread and pursues it relentlessly until the user's question is solved—or until the user is explicitly asked for help. The user is a valid resource: when stuck, the system uses them as leverage.

**Success metric:** Did we solve the user's question? (Not: did we answer the last turn?)

---

## Principles

1. **Master objective over last turn** — Don't satisfy yourself with answering the last message. Maintain and pursue the thread's primary objective.
2. **Relentless until solved** — Keep trying (RAG, web, reasoning, tools) until the objective is achieved or we exhaust options.
3. **User as leverage** — When stuck, ask the user for help. They may have links, documents, or knowledge we don't.
4. **Explicit "not done yet"** — If we couldn't fully answer, say so clearly and either retry with new info or ask the user.

---

## 1. Master Objective List

### Data Model

Per thread, persist a **master objective** (and optional action list):

```python
# In thread state (extend DEFAULT_STATE or new table)
{
    "master_objective": {
        "id": "uuid",                    # objective id
        "created_at": "iso8601",
        "updated_at": "iso8601",
        "status": "active|solved|abandoned|blocked",
        "summary": str,                  # "ICD code for X + coverage under Medicaid FL + prior auth for Sunshine"
        "sub_objectives": [              # derived from plan.subquestions or prior decomposition
            {"id": "sq1", "text": str, "status": "pending|answered|partial|failed|blocked"},
            {"id": "sq2", "text": str, "status": "pending|answered|partial|failed|blocked"},
        ],
        "attempts": int,                 # how many turns we've tried
        "last_user_ask": "iso8601",      # last time we asked user for help
    }
}
```

### Lifecycle

| Event | Action |
|-------|--------|
| **New question (no thread or new_question)** | Create `master_objective` from plan; status=active |
| **Follow-up (slot_fill or continuation)** | Update `master_objective`; merge new sub-objectives; keep unsolved ones |
| **Turn completes with full answer** | Mark sub-objectives answered; if all done → status=solved |
| **Turn completes with partial / no evidence** | Mark partial/failed; status=active; next turn: retry or ask user |
| **User provides new info (link, doc, clarification)** | Merge into context; retry failed sub-objectives |
| **User says "never mind" / "that's enough" / "stop" / "I'm done"** | status=abandoned; return "Understood. Let me know if you'd like to ask something else." |
| **attempts ≥ MAX_ATTEMPTS_BEFORE_STOP (e.g. 4)** | status=incomplete; stop asking; publish closure_message: "You can pick this up from recents to try again." |

---

## 2. When to Ask the User for Help (User as Leverage)

The user is a valid resource. Use them when we're stuck.

### Trigger: No Evidence in Our Materials

**Scenario:** RAG returns low confidence / no relevant results; web search also fails or is insufficient.

**Ask:**
- "I couldn't find [specific thing] in our policy materials or the web. Do you have a link, document, or PDF that might contain this? I can read and summarize it."
- "Our materials don't cover [X]. Do you know where this might be documented—e.g. a payer portal, internal wiki, or manual?"

### Trigger: Missing Identifier / Code

**Scenario:** User asked for an ICD/CPT code or specific identifier; we don't have it in lexicon or docs.

**Ask:**
- "I couldn't find that specific code in our materials. Do you have a code list, CMS link, or handbook where it might be listed? If you can share it, I can help interpret it."

### Trigger: Jurisdiction Ambiguous

**Scenario:** Answer depends on payer/state; user hasn't specified.

**Ask:** (Already in clarify stage)
- "To give you an accurate answer, could you specify which health plan or payer and which state?"

### Trigger: Contradictory or Stale Info

**Scenario:** Retrieved docs conflict or seem outdated.

**Ask:**
- "I found conflicting information in our materials. Do you have a more recent source or authority (e.g. effective date, bulletin) we should prioritize?"

### Trigger: Partial Progress, Blocked Sub-Objective

**Scenario:** Answered 2 of 3 parts; one part failed.

**Ask:**
- "I was able to answer [parts A and B], but I couldn't find information about [C]. Do you have any materials or links that might help with [C]?"

### End pursuit (user option)

The user can stop the relentless pursuit at any time with phrases such as:
- "Never mind", "That's enough", "Stop", "I'm done", "No thanks", "Cancel", "Forget it", "Don't worry", "That's ok", "Skip it", "End the search", "That's all", "No more"

When detected, we set `master_objective.status = "abandoned"` and return: "Understood. Let me know if you'd like to ask something else."

### Max Turns / Attempts

- **MAX_ATTEMPTS_BEFORE_STOP** (e.g. 4): After this many turns trying (with different angles, user-asks, retries), we stop and mark the objective `incomplete`. Prevents infinite loops.

### Clear End States

The response payload includes `objective_status` and optionally `closure_message`:

| `objective_status` | Meaning | `closure_message` |
|--------------------|---------|-------------------|
| `resolved` | All sub-objectives answered | "We've resolved your question." |
| `need_info` | Partial; waiting for user input | — |
| `unable` | Could not resolve | — |
| `user_ended` | User said never mind / stop | — |
| `incomplete` | Max attempts reached; stopped | "You can pick this up from your recent queries to try again." |

### Try Again From Recents

When the user selects a past query from recents (or history), treat it as a retry:
- Load the original message and thread state.
- Reset `attempts` to 0 (or create a fresh objective from the same plan) so the pursuit can try again.
- This allows "pick up where you left off" without endless loops in a single session.

### Guardrails

- **Don't spam:** Limit user-ask to once per objective (or once per N turns) unless user explicitly provides new info.
- **Be specific:** Tell the user exactly what we're missing.
- **Offer next step:** "If you can share X, I can …" so they know how to help.

---

## 3. Relentless Pursuit Loop

### Current vs Desired Flow

**Current:**
```
Turn N: User asks multi-part question
        → Plan → Resolve (RAG/Tool) → Integrate → Publish answer
        → Done (even if 2 of 3 parts had "no context")
```

**Desired:**
```
Turn N: User asks multi-part question
        → Plan → Create/update master_objective
        → Resolve (RAG/Tool) → Evaluate: did we solve each sub-objective?
        → If all solved: Publish, mark objective solved
        → If partial: Publish what we have + "I couldn't find [X]. Do you have..."
        → Store objective for next turn

Turn N+1: User provides link / doc / clarification
          → Load master_objective; retry failed sub-objectives with new context
          → If now solved: Publish, mark solved
          → If still stuck: Ask again (with different angle) or mark blocked
```

### Evaluation: "Did We Solve the Sub-Objective?"

| Signal | Interpretation |
|--------|----------------|
| RAG returned high-confidence answer, cited | answered |
| RAG returned "context does not contain" / low confidence | partial or failed |
| Tool (web/scrape) returned content, used in answer | answered |
| Tool failed / no results | failed |
| User provided doc/link, we used it | answered (with user leverage) |

### "Not Done Yet" Message Template

When we publish partial results:

```
I was able to answer [parts we solved]. However, I couldn't find [what's missing] in our materials or the web. 

Do you have a document, link, or source that might help? For example: [specific suggestion]. If you can share it, I can read it and summarize the answer.
```

---

## 4. Success Metric

**Primary:** Did we solve the user's question?

- **Yes:** All sub-objectives answered; user gets a complete response.
- **Partial:** Some answered; we explicitly say what's missing and ask for user help.
- **No:** We tried, asked the user, still blocked—we say so and offer alternatives (e.g. contact support, check payer portal).

**Operational check:** After each turn, we can log:
- `master_objective.status`
- `sub_objectives` with per-part status
- Whether we asked the user for help

---

## 5. Implementation Phases

### Phase 1: Master Objective in Thread State (No Pipeline Change)

| Task | File | Change |
|------|------|--------|
| Extend thread state schema | `app/storage/threads.py` | Add `master_objective` to DEFAULT_STATE or new column |
| Load/save master_objective | `app/storage/threads.py` | `get_state`, `save_state_full` include it |
| Create objective from plan | `app/state/master_objective.py` (new) | `create_or_update_objective(plan, thread_state) -> master_objective` |

### Phase 2: Evaluate Resolution Outcome

| Task | File | Change |
|------|------|--------|
| Map retrieval/answer to sub-objective status | `app/stages/resolve.py` or post-resolve | `evaluate_sub_objective_status(sq_id, answer, retrieval_signal) -> status` |
| Update master_objective after resolve | `app/pipeline/orchestrator.py` | After run_resolve, call `update_objective_from_answers(ctx)` |

### Phase 3: User-as-Leverage Prompts

| Task | File | Change |
|------|------|--------|
| Detect "stuck" (no evidence, partial) | `app/stages/clarify.py` or new `app/stages/continuity.py` | `should_ask_user_for_help(ctx) -> (bool, message)` |
| Build ask message | `app/communication/user_leverage.py` (new) | `format_user_ask(stuck_reason, sub_objective) -> str` |
| Add to response when partial | `app/pipeline/orchestrator.py` | When partial, append user-ask to final message or clarification |

### Phase 4: Integrate Into Response

| Task | File | Change |
|------|------|--------|
| Partial-response template | `app/responder/final.py` or integrator | "I was able to answer X. I couldn't find Y. Do you have..." |
| Retry with user-provided context | `app/stages/state_load.py` | When user pasted link/doc, include in retrieval context for retry |

### Phase 5: Persistence & Turn Continuity

| Task | File | Change |
|------|------|--------|
| DB schema | migrations | `chat_threads.master_objective JSONB` or `thread_state` extension |
| Load objective at state_load | `app/stages/state_load.py` | Merge `master_objective` into ctx |
| Save objective at end of turn | `app/storage/threads.py` | Persist updated objective |

---

## 6. User-Ask Message Library

Concrete prompts for `format_user_ask`:

| `stuck_reason` | Example message |
|----------------|-----------------|
| `no_evidence` | "I couldn't find information about [X] in our policy materials or the web. Do you have a document, link, or PDF that might contain this? I can read and summarize it for you." |
| `missing_code` | "I couldn't find that specific code in our materials. Do you have a code list, CMS link, or payer handbook where it might be listed?" |
| `conflicting_info` | "I found conflicting information. Do you have a more recent source or effective date we should prioritize?" |
| `partial_answer` | "I was able to answer [A] and [B], but I couldn't find [C]. Do you have any materials or links that might help with [C]?" |
| `tool_failed` | "The [scrape/search] didn't return useful results for [X]. Do you have a direct link or alternative source I could try?" |

---

## 7. Out of Scope (For Now)

- **Automatic retry in same turn** (e.g. RAG fails → auto web search) — already partially in blueprint `on_rag_fail`
- **Proactive "let me try one more thing"** — could add in Phase 4
- **User satisfaction feedback** — "Did this answer your question?" button (product decision)

---

## 8. Dependencies

- Thread state persistence (`chat_threads`, `thread_state`)
- Clarify stage (jurisdiction ask already exists; extend for user-ask)
- Integrator / final response (append partial + user-ask when needed)

---

## 9. Acceptance Criteria

- [ ] Master objective created from plan on new question
- [ ] Master objective updated on follow-up; unsolved sub-objectives carried forward
- [ ] When RAG/tool returns "no evidence", we append a specific user-ask (not generic "I couldn't find")
- [ ] User-ask is specific: "Do you have [X]?" not "Can you help?"
- [ ] Partial responses explicitly list what we answered and what we couldn't
- [ ] Success metric logged: objective status at end of turn
