# Follow-up Continuity: Current State vs Proposed Changes

Schematic of the chat pipeline for multi-turn conversations and where follow-up continuity improvements apply.

---

## Current State

```mermaid
flowchart TB
    subgraph state_load [State Load]
        SL1[get_state thread_id]
        SL2[extract_state_delta]
        SL3[merged_state: active jurisdiction, refined_query]
        SL4[last_turns: user + assistant content]
        SL5[last_turn_sources: document_id, document_name]
        SL6[build_context_pack]
    end

    subgraph classify [Classify]
        C1[slot_fill vs new_question]
        C2[effective_message]
    end

    subgraph plan [Plan Stage]
        P1["parse(message, context=parser_context)"]
        P2[parser_context = context_pack + capabilities]
        P3["plan.subquestions (from LLM or legacy)"]
        P4[compute_refined_query]
        P5["build_blueprint(plan) — no retrieval context"]
    end

    subgraph blueprint [Blueprint]
        B1[For each sq: agent from capabilities_primary, kind]
        B2["reframe_for_retrieval(sq.text, intent) — text only"]
        B3[reframed_text = as-is today]
    end

    subgraph resolve [Resolve]
        R1[RAG: question = reframed_text]
        R2[Tool: text = reframed_text]
        R3[Reasoning: text = reframed_text]
    end

    SL1 --> SL2 --> SL3
    SL3 --> SL4 --> SL5 --> SL6
    SL6 --> P2
    SL4 --> C1
    C1 --> C2 --> P1
    P1 --> P3 --> P4 --> P5
    P5 --> B1 --> B2 --> B3
    B3 --> R1
    B3 --> R2
    B3 --> R3
```

### Data Flow Today

| Component | What it receives | What it uses |
|-----------|------------------|--------------|
| **Parser** | `message` + `context_pack` (jurisdiction, last turn user/assistant) | LLM sees prior turn; may or may not expand "it", "their" |
| **reframe_for_retrieval** | `sq.text`, `intent` only | Returns text as-is (no merge with prior topic/jurisdiction) |
| **build_blueprint** | `plan` only | No `last_refined_query`, no `jurisdiction_summary`, no `is_followup` |
| **compute_refined_query** | `classification`, `last_refined_query`, `plan_subquestion_text` | slot_fill → merge jurisdiction; new_question → use plan text |
| **Resolve** | `reframed_text` from blueprint | RAG retrieves with that query; Tool uses that text |

### Gaps

1. **"can you search the web for it"** — Parser gets last turn in context but may output `sq.text = "can you search the web for it"`; `reframe_for_retrieval` passes it through. No merge of prior topic (income criteria, Florida Medicaid).
2. **"can you read their website"** — Same: "their" and "specific income criteria" rely on prior turn; no explicit merge into retrieval query.
3. **classification** — "can you search for it" may be `new_question` (not slot_fill), so `refined_query` becomes plan text, losing prior topic.
4. **reframe_for_retrieval** — Never receives `last_refined_query` or jurisdiction; cannot merge.

---

## Proposed Changes

```mermaid
flowchart TB
    subgraph state_load [State Load — unchanged]
        SL1[get_state, last_turns, context_pack]
    end

    subgraph classify [Classify — extend]
        C1[slot_fill vs new_question]
        C2["NEW: is_followup_continuation heuristic"]
        C3[effective_message]
    end

    subgraph plan [Plan Stage — extend]
        P1[parse with context_pack]
        P2["NEW: Planner prompt: resolve 'it'/'their' from last turn"]
        P3[plan, refined_query]
        P4["build_blueprint(plan, retrieval_ctx)"]
    end

    subgraph retrieval_ctx [NEW: Retrieval Context]
        RC1[last_refined_query]
        RC2[jurisdiction_summary]
        RC3[is_followup]
    end

    subgraph blueprint [Blueprint — extend]
        B1[agent routing unchanged]
        B2["reframe_for_retrieval(sq.text, intent, last_refined_query, jurisdiction_summary, is_followup)"]
        B3["reframed_text = merge prior topic + jurisdiction when follow-up"]
    end

    subgraph resolve [Resolve — unchanged]
        R1[RAG / Tool / Reasoning with reframed_text]
    end

    SL1 --> C1 --> C2 --> C3
    C2 --> RC3
    SL1 --> RC1
    SL1 --> RC2
    C3 --> P1
    P2 --> P3
    P3 --> P4
    RC1 --> RC2 --> RC3 --> P4
    P4 --> B1 --> B2
    RC1 --> B2
    RC2 --> B2
    RC3 --> B2
    B2 --> B3 --> R1
```

### Proposed Data Flow

| Component | Change |
|-----------|--------|
| **Planner prompt** | Add: "For follow-ups that reference prior topic ('it', 'their', 'that'), expand into concrete terms from the last turn. E.g. 'can you search for it' → 'Search for [prior topic from last turn]'." |
| **Classify** | Add `is_followup_continuation`: same thread, message looks like continuation (short, references "it"/"their"/"that"), last turn had substantive answer. |
| **build_blueprint** | Accept `retrieval_ctx`: `{last_refined_query, jurisdiction_summary, is_followup}`. Pass to `reframe_for_retrieval`. |
| **reframe_for_retrieval** | New params: `last_refined_query`, `jurisdiction_summary`, `is_followup`. When follow-up: merge topic from `last_refined_query` into `sq.text`, append jurisdiction if missing. |
| **run_plan** | After `compute_refined_query`, build `retrieval_ctx` from `ctx.refined_query`, jurisdiction from `ctx.merged_state`, `is_followup` from classify. Pass to `build_blueprint`. |

### Example: "can you search the web for it"

**Current:**
```
last_turn: User: "can you read their website and tell me the specific income criteria"
           Assistant: "The system cannot provide..."
sq.text = "can you search the web for it"
reframed_text = "can you search the web for it"  (no change)
RAG/Tool receives: "can you search the web for it"  → vague, no topic
```

**Proposed:**
```
last_refined_query = "specific income criteria for Florida Medicaid from Sunshine Health website"
jurisdiction_summary = "Sunshine Health, Florida"
is_followup = true
sq.text = "can you search the web for it"  (or planner expands to "Search for Florida Medicaid income eligibility")
reframe_for_retrieval merges: "Search for Florida Medicaid income eligibility criteria"
reframed_text = "Search for Florida Medicaid income eligibility criteria"
Tool receives concrete search query
```

---

## Files to Change

| File | Change |
|------|--------|
| `config/prompts_llm.yaml` | Add follow-up expansion instruction to `decompose_system_mobius` |
| `app/state/refined_query.py` | Add `is_followup_continuation()` or extend `classify_message` |
| `app/stages/plan.py` | Build `retrieval_ctx`, pass to `build_blueprint` |
| `app/planner/blueprint.py` | Accept `retrieval_ctx`, pass to `reframe_for_retrieval` |
| `app/state/query_refinement.py` | Extend `reframe_for_retrieval` with `last_refined_query`, `jurisdiction_summary`, `is_followup` |

---

## Master Objective List & User as Leverage

**Problem:** The system tends to satisfy itself with answering the question in the *last turn*, not with achieving the user’s original objective. It lacks a persistent master list of objectives.

**Desired behavior:**
- Maintain a **master action list / objective list** per thread.
- Be **relentless** until the user’s objective is achieved.
- Use the **user as leverage** when stuck: e.g. “I couldn’t find the code—do you know where I can find it?” or “Do you have a link or document that might help?”
- **Success metric:** Did the system solve the user’s question?

The real test for the system is: **did it solve the user’s question?** Not “did it answer the last turn?”

---

**→ Full design:** [RELENTLESS_CONTINUITY_PLAN.md](./RELENTLESS_CONTINUITY_PLAN.md) — data model, user-ask triggers, implementation phases.

---

## Out of Scope (This Schematic)

- **Day 2 routing** — "Search for X" → tool (blueprint pattern override)
- **Empty/malformed input** — "empty message", "payor.community_care_plan" handling
- **Option B (previous documents)** — Include prior turn sources in retrieval (FOLLOWUP_CONTINUITY_PLAN Phase 2)
