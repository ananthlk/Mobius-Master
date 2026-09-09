#!/usr/bin/env python3
"""Human-written content for the chat turn schema: how each node works, and a
production-readiness call.

Everything mechanical (paths, line counts, callers, env vars, signals, swallow
counts) is generated elsewhere and must NOT be duplicated here — it would drift.
This file holds only the two things a generator cannot produce: an explanation
a newcomer can skim, and a judgement with reasons.

RATING, and what it means. It is about *operational readiness*, not code taste:

  green   Understood, bounded, and observable. Ship it and sleep.
  amber   Works, but has a named weakness someone should own — usually a
          silent-degradation path, an untested surface, or size that makes
          review unreliable.
  red     A failure here is invisible or unbounded. Needs work before it can
          be trusted in production.

`depth` records how far I actually looked, because "could not check" is not the
same as "checked and fine":
  code      read the implementation
  surface   read the docstring, signature, config and call sites, not the body
"""

# ── The hops before run_pipeline ────────────────────────────────────────────
CHAIN = {
"POST /chat": dict(rating="red", depth="code", how="""
The front door, and the only synchronous part of a turn. It accepts the message, does
NOT answer it, and returns {correlation_id, thread_id} for the caller to poll or stream.

Correlation id: the caller may supply one. If body.correlation_id parses as a UUID it is
used verbatim, otherwise a fresh uuid4(). This is deliberate — callers such as the appeals
agent pre-generate a CID and open the SSE stream BEFORE the POST returns, so they never
have to parse a response body to start listening.

Where things go: thread_id is upserted into Postgres chat_threads via ensure_thread()
(INSERT ... ON CONFLICT DO NOTHING). The turn payload is lpush'd onto a Redis list at
cfg.redis_request_key. The answer comes back under redis_response_key_prefix. The
authenticated user_id rides the payload through worker → pipeline → chat_turns.user_id
for audit attribution.

Auth is Depends(require_user), governed by CHAT_AUTH_MODE. The code's intent is
fail-closed: CHAT_ENV=dev is permissive, staging and prod are "fail-closed unless explicitly
configured". THE DEPLOYED SERVICE CONFIGURES ITSELF OUT OF THAT. It sets CHAT_ENV=prod and
CHAT_AUTH_MODE=optional together, so the fail-closed default is explicitly overridden and a
request without a JWT is accepted on a service that declares itself prod.

The PHI gate runs here, before anything queues — and every verdict is written to
compliance.hipaa_message_check_log with the correlation id, thread, user, action, gate,
phi_flag, identifier labels, evidence and classifier version.
""", findings=[
 ("bad", "ensure_thread swallows every DB failure. On connection_error it warns and returns "
         "the id anyway; on any other failure it returns a FRESH uuid. A turn can proceed "
         "against a thread_id that is not in chat_threads, and the conversation silently "
         "loses continuity instead of failing. The code names this 'historical behavior … so "
         "callers never see exceptions here'."),
 ("bad", "The API→worker contract is untyped. ChatRequest is a Pydantic model, but the queue "
         "payload is a plain dict built by ten sequential `if` blocks. app/queue/schemas.py "
         "defines make_request_payload/make_response_payload and NOTHING imports it — dead "
         "code exactly where the contract should be."),
 ("good", "PHI enforcement is here rather than in the client, and blocked / overridden / "
          "passed are three distinct logged outcomes rather than one boolean."),
 ("good", "Only PHI categories (identifier_labels) cross into the pipeline — never raw text "
          "or evidence. Data minimisation at the boundary, and commented as such."),
 ("good", "Per-turn model profile is scoped to the turn explicitly so concurrent turns from "
          "different users do not fight over a process-wide global."),
 ("bad", "RUNTIME LENS, 2026-09-08, mobius-chat in mobius-os-dev: CHAT_ENV=prod and "
         "CHAT_AUTH_MODE=optional are set together. The env gate is designed to fail closed "
         "on prod unless explicitly configured, and this is that explicit configuration. A "
         "service naming itself prod is accepting unauthenticated turns. Whether dev-project "
         "means this is harmless is Ananth's call, not mine — but the label and the behaviour "
         "disagree, and that is worth someone deciding on purpose."),
 ("bad", "THE HIPAA AUDIT WRITE IS FAIL-OPEN. _log_phi_msg_gate's own docstring calls it "
         "a \"Best-effort INSERT into compliance.hipaa_message_check_log\", and the failure "
         "path is except Exception -> logger.warning. So the PHI GATE is fail-closed and "
         "correct, but the RECORD THAT IT RAN is not: a database blip means turns proceed "
         "properly gated with no compliance evidence that gating happened. The HIPAA analysis "
         "log is specified append-only and fail-closed; this write path is neither. Found by "
         "the DB extractor, not by me reading the file — my hand-written description of this "
         "node did not mention the table at all."),
 ("bad", "STRUCTURE LENS RULING (Technical Review, 2026-09-08): NODE 1 IS RED, not the "
         "amber I gave it. Driving reasons in their order: the live auth gap, and the FK "
         "policy disagreement — measured and active, not theoretical. The dead-contract and "
         "ensure_thread findings are real but amber-grade alone, and they explicitly said not "
         "to let those drive the colour."),
 ("bad", "STRUCTURE RULING on ensure_thread — the swallow is NOT the defect. Degrading "
         "gracefully when db-agent is unreachable is reasonable front-door posture. The defect "
         "is that the general-exception branch does the IDENTICAL thing for a different "
         "failure class: a real write failure (constraint violation, schema drift) mints a "
         "fresh uuid and returns as if it worked. Collapsing 'the agent is down' and 'the "
         "write is broken' into one path removes the only signal an operator has to tell "
         "expected degradation from a live bug. Fix is to branch them so they log and behave "
         "distinguishably — not to stop degrading."),
 ("bad", "STRUCTURE RULING on the HIPAA audit — tracked as its OWN item, not folded into the "
         "node colour, because it is evidentiary rather than availability. The gate is "
         "correctly fail-closed; its audit record is fail-open. Backwards for a log whose "
         "only job is proving the gate fired: a write failure at the wrong moment leaves zero "
         "evidence the block happened while the block still correctly happened. The owner of "
         "compliance.hipaa_message_check_log's guarantees — me — must decide whether that "
         "write blocks the response, or at minimum gets a durable dead-letter instead of a "
         "log line. OPEN DECISION."),
 ("watch", "STRUCTURE RULING on the FKs — keep the asymmetry, but RATIFY it on purpose. Both "
           "postures are individually defensible: a turn is plausibly a standalone audit "
           "record worth keeping after its thread is gone; message bodies and session state "
           "are not independently useful once the thread is deleted. The defect is three "
           "migrations (009, 010, 011) with no shared policy. One line in the schema stating "
           "the intent, so the next migration does not 'fix' the SET NULL into a CASCADE and "
           "silently start deleting turns. OPEN ACTION."),
 ("watch", "NOT VERIFIED BY OBSERVED BEHAVIOUR, by deliberate choice of both seats: neither I "
           "nor Technical Review sent an unauthenticated POST /chat. Tech Review read the gate "
           "instead — auth_mode() returns 'optional' from the env override before the "
           "hosted-default logic runs, and require_user() under 'optional' returns "
           "result.user_id with nothing that rejects when there is no token. So the code path "
           "an anonymous caller hits proceeds with user_id=None. Exercising it live would "
           "create a real queued turn, real cost and a real hipaa log row against a service "
           "labelled prod — that needs authorising, staging first if possible."),
 ("bad", "SCOPE LENS (DB seat, 2026-09-08), verified by me against live mobius_chat: the "
         "three FKs into chat_threads DISAGREE on delete behaviour. chat_turns.thread_id is "
         "ON DELETE SET NULL; chat_turn_messages.thread_id and chat_state.thread_id are "
         "CASCADE. So deleting a thread KEEPS the turn rows and DESTROYS their messages — "
         "'delete this conversation' leaves a detached turn carrying user_id and timestamps "
         "whose content is gone. 102 of 5,705 turns are already in that state. For anything "
         "PHI- or retention-shaped this is the finding on this node, and it is completely "
         "invisible from chat.py."),
 ("bad", "SCOPE LENS: there is NO retention or cleanup path for chat_threads or chat_turns "
         "anywhere in mobius-chat. No DELETE FROM either table. rag_query_traces got a "
         "bounded prune this week; chat did not."),
 ("bad", "SCOPE LENS: db_execute is written as an MCP call to mobius-db-agent with a "
         "direct-DB fallback, which is why ensure_thread has a connection_error branch at "
         "all. My original description read as if this were a plain local INSERT."),
 ("bad", "RUNTIME LENS CORRECTS THE SCOPE LENS: live, the MCP hop DOES NOT HAPPEN. "
         "CHAT_DB_MODE=direct is set on the deployed service and DB_AGENT_MCP_URL and "
         "DB_AGENT_CALLER_ID are both UNSET — so the fallback IS the path, and the db-agent "
         "dependency the code is built around is not in use here. Two consequences: the "
         "connection_error branch that shapes ensure_thread's degradation is guarding a hop "
         "that never occurs, and any reasoning about db-agent's availability, access control "
         "or caller manifests is describing a deployment other than this one."),
 ("watch", "SCOPE LENS: mobius_chat has TWO disjoint migration ledgers — migrations_applied "
           "(24 rows, no checksum) and schema_migrations (48, with checksum), zero overlap, "
           "against 64 .sql files on disk. NEITHER registers the migrations creating "
           "chat_threads or chat_turns. The DB seat filed a correction to their own "
           "2026-08-19 ruling that mobius_rag held the instance's only ledger — they had not "
           "checked mobius_chat."),
 ("watch", "SCOPE LENS: this node writes into a NINE-table family; my model named two. The "
           "others: chat_turn_messages, chat_state, chat_progress_events, chat_tool_results, "
           "chat_feedback, chat_source_feedback, chat_cache_shadow_log. Two of them are the "
           "CASCADE children above, so they are not optional context."),
 ("bad", "THE FOURTH FK — mine to find, and I got two things wrong about it that the DB "
         "seat corrected. It is the FOURTH into chat_threads, not the fifth (the unfiltered "
         "count is 4: chat_turns SET NULL, chat_turn_messages CASCADE, chat_state CASCADE, "
         "financial_strategy_versions SET NULL). And it is NOT an external module reaching "
         "into chat's tables — mobius-chat creates it itself, "
         "db/schema/028_financial_strategy_runs.sql. What is true, and worse than I said: "
         "financial_strategy_versions has 57 live rows, every one FK-coupled to a chat "
         "thread, 0 detached — and ZERO code anywhere in the fleet reads or writes it. Chat "
         "owns the schema; nothing owns the data path. So deleting a thread detaches a "
         "financial strategy record and, because nothing reads the table, NOBODY WOULD EVER "
         "OBSERVE IT. chat_turns at least has readers who would notice 102 detached rows. "
         "Verified against live mobius_chat."),
 ("bad", "CORRECTION from the DB seat to my own text: ensure_thread treats two failures "
         "differently and I merged them. On connection_error the caller's thread_id SURVIVES "
         "(returns id_to_use if thread_id else uuid4()); only on a NON-connection failure is "
         "a fresh uuid returned, discarding it. And the orphan cannot accumulate — "
         "chat_turns.thread_id has an FK to chat_threads, so a turn against a missing thread "
         "is REJECTED at write time. The risk is a lost turn, not silent continuity drift."),
 ("bad", "CORRECTION: chat_turns.user_id is nullable TEXT with NO foreign key — unvalidated "
         "free text, and 498 of 5,705 rows are NULL. I implied it was a validated reference."),
 ("good", "RUNTIME LENS: the Redis claim holds — CHAT_QUEUE_TYPE=redis is set and takes "
          "precedence over QUEUE_TYPE in config.py. Worth recording that the code default is "
          "'memory' and QUEUE_TYPE alone is unset, so reading only QUEUE_TYPE would have "
          "produced a confident, wrong 'it uses the in-memory queue'."),
]),

"PHI gate": dict(rating="amber", depth="code",
 ux="No surface of its own. The 422 body carries phi_blocked, identifier_labels and evidence "
    "so the UI can explain a block; the audit rows have no reader anywhere.", how="""
Not a module so much as a call made at the API boundary before anything is queued:
_phi_check_message POSTs the message to the PHI classifier's /message-check.

FAIL-CLOSED, and that is the point. Any timeout, network error or non-200 returns block=True
with gate='indeterminate', so taking the classifier offline cannot bypass the gate. The
frontend pre-check fails OPEN and is a UX affordance only; this backend re-run is the
authoritative layer.

IT WRITES ITS ASSESSMENT TO THE DATABASE. Every verdict goes to
compliance.hipaa_message_check_log — id, ts, correlation_id, thread_id, user_id, org_slug,
action, gate, phi_flag, identifier_labels, phi_evidence, classifier_version. 3,259 rows live,
from 2026-07-20 to today. So the gate is genuinely instrumented, and my earlier description
of this node as having no telemetry was wrong — I had filed the write under POST /chat because
that is the file it lives in, and lost it from the node whose assessment it records.
""", findings=[
 ("good", "Fail-closed by construction, with the reasoning written at the call site."),
 ("good", "It DOES persist its assessment: 3,259 rows in compliance.hipaa_message_check_log "
          "carrying the gate, the flag, the identifier labels and the classifier version. "
          "Corrects my earlier claim that this node emits nothing."),
 ("good", "Configurable without a redeploy: PHI_GATE_URL, PHI_CLASSIFIER_URL, "
          "PHI_GATE_TIMEOUT_SEC. Has its own test file. 95 lines."),
 ("bad", "OWNER(chat): TWO IMPLEMENTATIONS OF THE SAME GATE, and only one is audited. "
         "app/api/chat.py:247 checks chat MESSAGES and writes the audit row. "
         "app/skills/phi_gate.py:66 checks FEEDBACK text with its own httpx call and writes "
         "NOTHING to the database — _log_gate emits a logger.info with labels and counts only. "
         "Same classifier, same endpoint, same fail-closed posture, two code paths, one "
         "audit trail. Feedback text passing through a PHI gate leaves no compliance record."),
 ("watch", "OBSERVATION (Ananth, 2026-09-08): the feedback path's PHI assessment should "
           "move from a log line into Postgres, so both gates land in the same audit table "
           "rather than one being queryable and the other being grep-able. Recorded as an "
           "observation, not scheduled — no action taken."),
 ("bad", "THE AUDIT WRITE IS FAIL-OPEN. _log_phi_msg_gate's docstring calls it a "
         "'Best-effort INSERT' and its failure path logs a warning and continues. The gate is "
         "fail-closed; the record that it fired is not. Technical Review ruled this as its own "
         "item — evidentiary, not availability. OPEN DECISION, mine: block the turn when the "
         "audit cannot be written, or give it a durable dead-letter."),
 ("watch", "600 rows have gate='phi' AND phi_flag=true AND identifier labels present, and "
           "action='passed' — against 18 blocked. The labels on them are License/Cert #, URL "
           "and Name, which is the expected recall-over-precision behaviour: a provider's name "
           "and licence number in a credentialing question is not patient PHI, and the "
           "classifier returns block=false for them. The gap is that the audit row records "
           "gate, flag, labels and action but NOT WHY the two disagree. From the log alone you "
           "cannot answer 'why was this PHI-flagged message allowed?' — and that is 600 of the "
           "668 PHI-flagged rows, so it is the majority case, not an edge."),
 ("watch", "Nothing reads this table. No dashboard, no query, no alert — 3,259 compliance rows "
           "with no reader. A write path whose output nobody consumes is the shape that hid "
           "the appeals outage; here it means a gate could start behaving differently and the "
           "evidence would sit in Postgres unlooked-at."),
 ("watch", "A 4-second default timeout against a remote classifier sits on the synchronous "
           "request path. It does not fail open, but it adds latency to every message before "
           "the user sees any acknowledgement."),
]),

"queue": dict(rating="red", depth="code", how="""
A Redis list used as a work queue, and the handoff between the API and the worker.

The ops, verified: publish does LPUSH onto cfg.redis_request_key; the worker does BRPOP with
a 5-second timeout. LPUSH + BRPOP is correct FIFO — push left, pop right. ORDERING IS SOUND.
Durability is not.

BRPOP removes the item atomically with no destination. There is no in-flight list, no ack,
no visibility timeout, no redelivery. The instant BRPOP returns, Redis has no record the
item ever existed. So if the worker dies between popping and publishing, THE TURN IS LOST —
silently and unrecoverably. The user sees a request that never returns, and there is no
server-side artifact of the loss: no row, no key, no log of an orphan.

The response side is a per-correlation-id key with a 24-hour TTL, written at two sites. That
is 288x the live turn deadline of 300s, so a slow turn cannot outlive its response key — a
risk I had suspected and which does not exist. But the asymmetry inverts into a real one:
THE RESPONSE HAS A TTL, THE REQUEST LIST HAS NONE. A request never consumed sits in
mobius:chat:requests indefinitely, with nothing ageing it out and nothing alerting on depth.

get_queue() picks memory or redis behind a QueueAdapter ABC, so the same code runs in tests
and production. Connection handling retries 12 times with 5s backoff, about a minute, which
covers a Redis restart without losing the process.
""", findings=[
 ("bad", "STRUCTURE RULING (Technical Review, 2026-09-08): RED — and the clean structure "
         "is a reason to rate it LOWER, not higher. A polished ABC around this gap is worse "
         "for review trust than an ugly implementation, because the cleanliness is exactly "
         "what makes a reader assume the underlying guarantee is sound too. 'LPUSH+BRPOP = "
         "correct FIFO' is true, stated confidently in comments, and irrelevant to the actual "
         "gap — while the thing the node exists to guarantee goes unmentioned. Rate the "
         "guarantee the node exists to provide, not the class hierarchy built around it. This "
         "corrects my error directly: I rated the abstraction and let it carry the node."),
 ("bad", "STRUCTURE RULING — what pushes it past 'known limitation' is the absence of DEPTH "
         "ALERTING. A worker that starts dying mid-turn produces no operator-visible signal "
         "that anything is wrong. That is not a lossy guarantee with a bounded blast radius; "
         "it is an unmeasured, unbounded one."),
 ("watch", "ACCEPTANCE CRITERION, set by Technical Review so 'add redelivery' cannot be "
           "hand-waved: durability must run CLAIM-TO-ACK, not enqueue-to-dequeue. Either an "
           "in-flight record written before the callback and cleared after publish_response "
           "succeeds, with a sweep for stale claims — or a primitive that gives it natively "
           "(Redis Streams consumer groups: XREADGROUP + XACK is exactly this pattern already "
           "built). Mechanism is Chat's call. The bar is: a worker death mid-turn is provably "
           "not silent."),
 ("watch", "STRUCTURE RULING on the two side items: flush_request_queue should be DELETED "
           "rather than left — dead, destructive and alarming-by-grep is a bad combination to "
           "carry even at zero risk today. And 'running on defaults' paired with the "
           "durability gap reads as nobody having made a deliberate call about this node's "
           "blast radius, where this service overrides defaults on purpose elsewhere. That is "
           "a gap in OWNERSHIP, not just a config fact."),
 ("bad", "No delivery guarantee at all. BRPOP with no processing list means worker death "
         "between pop and publish loses the turn with no artifact anywhere. Provable by "
         "reading, and deliberately NOT tested: proving a durability gap by causing one turns "
         "a documented risk into a real lost turn on a live service, to establish something "
         "the code already states. If it must be observed, it needs authorising against "
         "staging."),
 ("bad", "The request list has no TTL and no depth alerting, while the response key has 24h. "
         "An unconsumed request accumulates silently and forever."),
 ("good", "Ordering is genuinely correct — LPUSH + BRPOP is FIFO, and the code says so at "
          "both sites rather than leaving it to be inferred."),
 ("good", "A real abstraction: one ABC, two implementations, chosen by config, so tests and "
          "production run the same path."),
 ("good", "NEGATIVE RESULT, recorded so it is not rediscovered as a finding: "
          "flush_request_queue() deletes the entire backlog and its docstring says 'Staging "
          "debug only'. It reads alarming in a grep. It has ZERO callers anywhere in app/ — "
          "dead code, not a live risk. Found by the DB seat, verified by me."),
 ("watch", "RUNTIME LENS: every key and TTL setting is at its CODE DEFAULT — REDIS_REQUEST_KEY, "
           "REDIS_RESPONSE_KEY_PREFIX and REDIS_RESPONSE_TTL_SECONDS are all unset live. Only "
           "CHAT_QUEUE_TYPE=redis and REDIS_URL are configured. Unusual for this service, "
           "where most other defaults are overridden."),
 ("watch", "WHAT THIS EXTRACTION CANNOT SEE: whether anything outside mobius-chat writes to "
           "or drains mobius:chat:requests, and what the actual queue depth is on the live "
           "instance. Both are observable and neither has been checked, so treat this node's "
           "durability claims as code-true and runtime-unmeasured."),
]),

"worker": dict(rating="amber", depth="code", how="""
The process that actually does the work. It consumes the request queue, arms a per-turn
deadline (MOBIUS_TURN_DEADLINE_S) with a signal handler, and calls run_pipeline. The PHI
verdict travels in the payload and is handed to the pipeline so it can show a thinking
step for it. On failure it publishes a terminal failure so the poller gets an answer
rather than hanging.
""", findings=[
 ("good", "A hard turn deadline exists at all, and terminal failures are published rather "
          "than left for the client to time out on."),
 ("watch", "Seven log-and-continue handlers on the path that owns the turn's lifecycle. "
           "Worth walking individually to check none of them can drop a turn silently."),
 ("watch", "The deadline is implemented with a signal handler, which only works on the main "
           "thread of a process. Worth confirming that assumption holds under the deployed "
           "server model."),
]),

"run_pipeline": dict(rating="amber", depth="code", how="""
The orchestrator's single entry point, and everything the schema below draws happens
inside this one call. It loads state, decides between the ReAct and classic paths, runs
the chosen one, then integrates and publishes. It also owns the early exits — when the
turn needs clarification or refinement it publishes and returns without finishing.
""", findings=[
 ("bad", "1,902 lines with 42 exception handlers, 31 of which log and continue. Individually "
         "most are defensive and correct — a broken tracing init genuinely should not kill a "
         "turn. Collectively they make it very hard to know which failures are survivable by "
         "design and which are the appeals-outage shape, where a capability disappears and "
         "the turn still looks healthy."),
 ("good", "The branch and the stage sequence are explicit and readable; the flow in this "
          "diagram was parsed straight out of it."),
]),
}

# ── Cross-cutting ───────────────────────────────────────────────────────────
CROSS = {
"llm_manager": dict(rating="amber", depth="code", how="""
The single entry point for every LLM call in chat. Nothing should call a provider
directly; everything goes through here.

It does more than proxy. It wires a ModelRouter that picks the model per stage rather than
per process, so the planner and the integrator can run on different models in the same
turn. It takes phi_detected from pipeline context so a turn carrying PHI can be routed
differently. It sets ab_variant to the selected model id for analytics, and calls
router.update_ema() after each call so the bandit learns from what actually happened.
""", findings=[
 ("good", "One chokepoint for every LLM call is exactly what you want for cost control, "
          "model routing, PHI-aware routing and A/B analytics. This is the right shape."),
 ("good", "Has its own tests, including an attachments suite."),
 ("watch", "Fourteen callers and 432 lines make it the highest-blast-radius module in the "
           "pipeline. A regression here touches every path at once."),
 ("watch", "Six log-and-continue handlers. On a chokepoint, a swallowed failure means a "
           "degraded answer nobody is told about — the exact pattern that hid the appeals "
           "outage for 29 days."),
]),
"retrieval_budget": dict(rating="green", depth="code",
 ux="No surface — the computed number rides in the RAG call payload; visible only in the "
    "retrieval trace if you look for token_budget_for_retrieval", how="""
The token adjuster. Task #98, and it exists because RAG was guessing.

RAG's Structure stage used a static per-caller_mode table (chat.default 3000,
chat.thinking 16000) for how many tokens of retrieved context it could afford, because
chat never sent a real number. Ananth's correction was that RAG does not have to guess:
chat knows its own context window, its system prompt, the conversation so far, and how
much it must reserve to generate an answer.

  token_budget_for_retrieval = context_window
                             - system_prompt_tokens
                             - conversation_history_tokens
                             - answer_generation_reserve

conversation_history_tokens is the term that moves — a thread's first turn and its
twentieth differ by thousands of tokens — so the budget is genuinely per-turn rather than
per-mode. react_loop computes it at five separate call sites and passes it with the RAG
request.
""", findings=[
 ("good", "Replaces a guess with arithmetic, and the arithmetic is stated in the docstring "
          "in the same form RAG's own docs use — the two sides agree on the formula."),
 ("good", "Small, single-purpose, pure: takes ctx, returns an int."),
 ("watch", "Computed at five call sites in react_loop rather than once per turn and reused. "
           "Cheap, but five places can drift if one is missed when a new tool call is added."),
 ("watch", "No test file, for arithmetic that decides how much corpus every retrieval gets."),
]),
}

# ── The 25 pipeline sub-modules ─────────────────────────────────────────────
SUB = {
"state_load": dict(rating="red", depth="code", how="""
Runs on every turn, before the path is chosen. It is not one load — it assembles NINE BLOCKS
from four different sources, and a route decides how many of them reach the model.

WHAT IT LOADS, block by block:

  1  Thread state          chat_state.state_json -> ThreadState. The persisted conversation.
  2  Run defaults          DEFAULT_STATE, a code constant, used when there is no row. Its
                           shape: active{payer, program, domain, jurisdiction, user_role,
                           jurisdiction_obj} all None; open_slots []; resolved_slots {};
                           recent_entities []; last_user_intent, last_updated_turn_id,
                           refined_query, master_objective all None; and
                           safety{patient_allowed: FALSE} — the safety default is deny.
  3  Three un-modelled keys  active_skill, last_failed_query, active_context. In the stored
                           JSON but NOT in ThreadState, restored by a hardcoded name list.
  4  report_run_id         from merged.active, so "ask about this report" can resolve.
  5  Last turns            get_last_turn_messages(limit_turns=2) — the last TWO turns.
  6  Last turn sources     get_last_turn_sources(limit_turns=2) — deduped by document_id,
                           and it feeds the retriever include_document_ids, not just the prompt.
  7  Prior resolved entities  get_prior_resolved_entities, reaching 8 turns back, and GATED
                           on is_continuation: a fresh turn skips the query entirely because
                           there is nothing prior to resolve (Task #90).
  8  Rolling summary       chat_threads.summary_long, the canonical per-thread brief updated
                           in place each turn, with a fallback to the latest per-turn
                           context_summary for threads predating migration 036. Threaded to
                           the integrator so it REFINES rather than rebuilds.
  9  Ephemeral jurisdiction  _reset_reason, _jurisdiction_new, _prior_payer computed onto
                           active for emit_jurisdiction_context. Explicitly marked as NOT to
                           be persisted.

Then route_context returns STANDALONE, LIGHT or STATEFUL, and build_context_pack turns the
above into the string prepended to the user message — jurisdiction, payer, program,
perspective, domain, open questions, and up to 10 source names, with resolved slots capped
at 6. On STANDALONE it returns the EMPTY STRING and the stage also evicts slots and clears
tool results, so a standalone turn starts genuinely clean.

TURN 2 OF THE SAME THREAD — how it actually gets its context. Four channels, and only the
first is what people mean by "the state".

  A  PERSISTED STRUCTURED STATE — chat_state.state_json, one row per thread.
     Jurisdiction (payer, program, state, perspective), open_slots, resolved_slots,
     recent_entities, last_user_intent, refined_query, master_objective, safety. Plus the
     three keys carried outside the model: active_skill, last_failed_query, active_context.

  B  TURN HISTORY — three separate reads, three different depths:
       get_last_turn_messages(limit_turns=2)  the last TWO turns, from chat_turn_messages
       get_last_turn_sources(limit_turns=2)   sources from the last two turns of chat_turns,
                                              deduped by document_id — and this one does more
                                              than inform the prompt: its own docstring says it
                                              feeds the retriever's include_document_ids, so
                                              turn 2 is STEERED toward the documents turn 1
                                              cited.
       get_prior_resolved_entities(limit_turns=8)  eight turns back, gaps_closed only, and
                                              skipped entirely unless is_continuation is set.

  C  THE ROLLING BRIEF — chat_threads.summary_long, a different table from the state, threaded
     to the integrator so it refines the previous brief rather than rebuilding one.

  D  PER-TURN CALLER INPUT — the profile, re-sent by the frontend on every turn, plus
     thread_id and any system_context. Never persisted here.

AND THERE IS A TOOL THAT REACHES PRIOR TURNS — transform_previous_answer, a registry-owned
builtin (app/skills/builtin/transform_previous.py). It exists because reshape requests
("convert this to an appeal letter", "make it shorter", "rewrite for the credentialing team")
used to fall through to search_corpus and come back with generic results unrelated to the
actual prior answer, leaving the bot asking the user to re-paste their own content.

The precision that matters: IT DOES NOT LOAD ANYTHING ITSELF. Its handler reads
pipeline_ctx.last_turns — already populated by this stage — and takes the most recent
assistant message from it. So it is a CONSUMER of channel B, not a fifth channel. It then
asks the LLM to apply the transformation with no corpus call and no curator call, and the
envelope carries signal=system_context precisely because the answer is synthesised from
in-thread material rather than a retrieval source.

Two consequences of it reading ctx rather than the database: the tool inherits channel B's
depth, so it can only ever see the last TWO turns; and if state_load's read failed, the tool
transforms whatever survived rather than reporting that it lost the thread.

cached_answer.py is the other builtin that reaches into chat_turns.

THEN THE MESSAGE ITSELF CAN BE REWRITTEN TWICE before planning:
  message_resolver resolves "it" / "that" / "try again" against the prior turn;
  classify, on a slot_fill, discards what the user typed and REBUILDS the whole prior question
  from the stored refined_query plus jurisdiction — which is why a one-word answer does not
  lose the question.

AND WHAT REACHES THE MODEL is not the raw blocks: build_context_pack renders a header
(jurisdiction, payer, program, perspective, domain, open questions), up to 10 source names and
at most 6 resolved slots, prepended to the message — or the EMPTY STRING when the route is
STANDALONE, which also evicts slots and clears tool results.

WHAT IT DOES NOT LOAD, which is the part people assume:
  * The USER PROFILE. It never touches state_load. It arrives per-turn in the POST payload,
    rides worker/run.py:111 to run_pipeline(user_profile=...) at orchestrator:487, and is
    spliced into five prompts by the personalization module. It is caller input, not
    conversation state, and is never persisted here.
  * The SYSTEM PROMPT. Not state either — assembled at the LLM call from prompts.py or, live,
    from versioned blocks in Postgres via MOBIUS_PROMPT_SOURCE=composition.
  * PHI. Checked at the API boundary, before the queue.
""", findings=[
 ("bad", "A TRANSIENT READ FAILURE DESTROYS ACCUMULATED THREAD STATE. get_state returns None "
         "for a DB error and None for no-row — identical, and its docstring says only 'or None "
         "if no row', never mentioning the error case. state_load does `raw = get_state(...) "
         "or {}`, builds ThreadState from DEFAULT_STATE, and if the message carries a delta "
         "calls save_state_full, whose UPSERT is a FULL REPLACE by design. One failed read plus "
         "any delta-bearing message overwrites the whole conversation with defaults plus that "
         "turn. Not skipped — destroyed."),
 ("bad", "AND NOTHING CAN DETECT IT AFTERWARDS. state_version increments on the same write, so "
         "the row goes 11 -> 12 exactly as a normal turn would. There is no artifact "
         "distinguishing 'turn 12 of a conversation' from 'state reset, now calling itself 12'."),
 ("bad", "THE FIX IS LOCAL, NOT A REDESIGN. The same file already uses the right pattern thirty "
         "lines down: _write_state_row warns and returns on connection_error but RAISES on "
         "anything else. Write path loud, read path silent, one module — and the silent one "
         "loses data. get_state is the one function not following its own file's convention."),
 ("bad", "state_version is WRITE-ONLY — inserted, incremented, never read or compared anywhere "
         "in app/. So it cannot detect the above, AND read-modify-write through "
         "get_state/save_state_full is unguarded: two concurrent turns on one thread are a "
         "lost update."),
 ("bad", "CROSS-NODE, invisible to any code read: mobius_chat has NO query guards. "
         "statement_timeout = 0 and no idle-in-transaction guard. mobius_rag carries "
         "idle_in_transaction_session_timeout = 120s and is the ONLY per-database override on "
         "the instance. A pathological chat query runs unbounded holding a connection, and "
         "SQLSTATE 57014 cannot fire, so db_client's `timeout` branch is dead-looking code that "
         "would come alive the moment anyone sets a timeout."),
 ("watch", "WHERE THE THREAD SUMMARY LIVES — not in the state, and there are THREE stores "
           "with three lifecycles. (1) chat_threads.summary_long, the canonical rolling brief, "
           "written by responder/thread_summarizer.py, updated in place each turn, server-side "
           "only, read here as previous_thread_summary and threaded to the integrator so it "
           "REFINES rather than rebuilds. Live: 1,349 of 5,330 threads have one, avg 185 chars, "
           "max 600 — the docstring says under about 60 words, so the cap is a target not an "
           "enforcement. (2) chat_turns.context_summary, per-turn, the fallback this stage "
           "walks when summary_long is absent — 3,134 of 5,712 turns. (3) And summaries DO sit "
           "inside chat_state.state_json after all, nested: 216 rows under master_objective, 54 "
           "under active_context, 2 under active. Those two keys are exactly the size inflators "
           "the DB seat measured at 145 kB and 82 kB, so the summaries in the state are the "
           "ones bloating it."),
 ("watch", "The canonical store is written for roughly HALF of threads — 31% to 74% by week "
           "over the last eight weeks, 51% this week — so this is current behaviour, not a "
           "migration-036 backfill artifact. I have NOT established why: single-turn threads "
           "plausibly need no brief, but I did not verify the summariser's firing condition, so "
           "treat the split as measured and unexplained."),
 ("watch", "NINE blocks from four sources, assembled in one 127-line function with no "
           "structure separating them. Block 7 is conditionally skipped, block 8 has a legacy "
           "fallback, block 9 must never be persisted — three different rules a reader has to "
           "hold at once, none of them named as a step."),
 ("watch", "Three keys persisted OUTSIDE the model, kept alive by a hardcoded allowlist copied "
           "in THREE places within this one file — before the delta save, in the merge, and "
           "again in the STANDALONE eviction path. A fourth such key is silently dropped."),
 ("watch", "State size is bimodal and NOT conversation length. Verified live: 4,895 rows, p50 "
           "441 B, p95 918 B, p99 72 kB, 59 over 32 kB, corr(state_version, size) = 0.009. "
           "master_objective is the inflator (up to 145 kB), active_context second (82 kB). "
           "Both uncapped, while uploaded files ARE capped at 15 records."),
 ("watch", "An empty thread_id returns empty state and never touches storage — the landing "
           "zone for node 1's failure modes. The 102 NULL-thread_id turns and every "
           "ensure_thread fresh-uuid path arrive here and are treated as brand-new "
           "conversations."),
 ("good", "The safety default is DENY: DEFAULT_STATE sets safety.patient_allowed = False, so a "
          "thread with no state cannot start permissive."),
 ("good", "STANDALONE genuinely resets: context_pack returns empty, slots are evicted and tool "
          "results cleared, so stale context cannot bleed into a fresh question."),
 ("good", "RUNTIME LENS: CHAT_RAG_DATABASE_URL IS set on the live service, so state is being "
          "persisted. The failure mode above is a real risk, not an active outage."),
 ("watch", "WHAT THIS CANNOT SEE: whether the data-loss path has ever fired. It leaves no "
           "artifact by construction, so its rate is not recoverable — absence of evidence "
           "here is guaranteed, not reassuring. Also unmeasured: whether concurrent turns on "
           "one thread occur, and whether any writer outside mobius-chat/app mutates "
           "chat_state."),
]),

"classify": dict(rating="amber", depth="code", how="""
Twenty-four lines, and the hinge on which conversational continuity turns.

It asks one question — is this a new question, or the user filling a blank we left? —
by calling classify_message(message, last_turn, open_slots, last_refined). Three outcomes
matter: slot_fill, jurisdiction_change, or neither.

The interesting branch is what happens on the first two. If there is a stored refined
query, it does NOT plan from what the user just typed. It rebuilds the whole thing:
build_refined_query(last_refined, jurisdiction_from_active). So a one-word reply — "Florida"
— becomes the entire previous question re-asked with Florida attached. That is why a slot
fill does not lose the question.

Otherwise it preserves an effective_message that message_resolver already set (pronoun
resolution), falling back to the raw message. That fallback chain is an ordering
dependency: message_resolver must have run first or "it" never gets resolved.
""", findings=[
 ("bad", "The stage is a 24-line wrapper; the actual logic is 226 lines in "
         "app/state/refined_query.py, which is NOT in this catalogue. Reading the node tells "
         "you almost nothing about the behaviour — the same boundary error as the PHI gate, "
         "a third time."),
 ("watch", "No test file, for the code that decides whether a follow-up keeps its question."),
 ("good", "Pure and side-effect free: reads merged_state, writes two ctx fields."),
]),

"plan": dict(rating="amber", depth="code", how="""
Turns the effective message into a Plan — a list of SubQuestions — plus a refined query and
a blueprint. Only the classic path runs it; ReAct plans as it goes.

Two shortcuts matter more than the main path.

_plan_from_master_objective: on a slot fill, if a master objective is stored, it reuses the
sub-objectives already agreed rather than re-parsing. A follow-up does not get re-decomposed
into a different set of questions than the one the user was answering.

_minimal_plan: when parsing fails, rather than erroring it emits one subquestion carrying the
raw message with kind=non_patient and intent_score 0.5. The turn continues on a degraded
plan. That is a deliberate choice — a bad plan beats no answer — but it is silent.

It feeds capabilities_for_parser in, so the decomposition only produces sub-questions
something can actually answer, and runs parse_credentialing_flow_intent over the text.
""", findings=[
 ("bad", "The parse-failure fallback is invisible. A turn planned from _minimal_plan looks "
         "identical downstream to one that parsed cleanly — same shape, no signal, nothing in "
         "the trace says the planner gave up. This is the appeals pattern in miniature."),
 ("watch", "No test file, for the stage that decides what the classic path will try to answer."),
 ("good", "Reusing the master objective on slot fill is the right call and is the reason a "
          "follow-up does not silently become a different question."),
]),

"clarify": dict(rating="green", depth="code", how="""
The stage that turns a bad answer into a question. It returns resolvable — False means stop
and ask rather than proceed.

Three checks, in order. Route clash first: detect_route on the message, and when confidence
is below 1.0 with competing choices, it asks outright — "I can either search the web or
search our policy materials" — rather than guessing which the user meant. Then jurisdiction:
need_jurisdiction_clarification against the plan's subquestions and active state, consulting
the RAG lexicon URL so the tagger can judge scope. Then query refinement.

There is a deliberate exemption worth knowing: when the turn is a follow-up about a stored
credentialing report — an active roster_report skill, or a stored report_run_id — the
jurisdiction ask is skipped, because answering from a report we already produced needs no
RAG scope. Asking "which state?" about a report already on screen is the failure that
exemption exists to prevent.
""", findings=[
 ("good", "Has tests, including one specifically for ReAct clarify questions."),
 ("good", "Asking rather than guessing is a product stance and it lives in one small module "
          "with the three triggers visible in order."),
 ("watch", "The report-context exemption is matched with lowercase substring checks on the "
           "message ('pml', 'npi', 'section', 'how many'). It works, but it is phrase "
           "matching standing in for intent, and it will not survive rewording."),
 ("watch", "Delegates to app/state/clarification.py (88 loc) and query_refinement.py (128 "
           "loc), neither of which is in this catalogue."),
]),

"resolve": dict(rating="amber", depth="code", how="""
The classic path's dispatcher, and the only stage with an explicit, numbered escalation
ladder. Each subquestion is answered by walking layers until one succeeds:

  0  hard stop
  1  RAG — the corpus
  2  system tool
  3  web / scrape
  4  reasoning — the model answering without retrieval
  5  ask_user

Every hop is announced: emit_layer_attempt as each is tried, emit_fallback when one gives
way to the next, so the thinking chain shows the escalation rather than only its outcome.

The guard worth knowing is on layer 4. Reasoning is allowed to answer only when sources are
present; if none are, layer 4 is skipped and the cascade falls through to ask_user. That is
the difference between an ungrounded answer and an honest question, and it is one comparison
in the middle of a 595-line file.
""", findings=[
 ("good", "The ladder is explicit and numbered, and layer_used is returned, so which layer "
          "answered is knowable per subquestion rather than inferred."),
 ("good", "The layer-4 groundedness guard — no sources means no reasoning answer, ask instead "
          "— is exactly the right default."),
 ("watch", "595 lines and only indirect test coverage; the tests named for it are about "
           "fetch_document and message resolution, not the cascade itself."),
 ("watch", "validate_tool_result returns (is_valid, failure_reason) and an invalid result "
           "triggers the next layer — so a tool that returns something useless is "
           "indistinguishable downstream from one that failed outright."),
]),

"integrate": dict(rating="amber", depth="code", ux="Answer card in the chat bubble; step labels 'Composing your answer' and 'Critique & citations'", how="""
Not one step — THREE LLM calls plus a mode switch, which is why it is 1,887 lines.

  Call A  integrator_a — the first answer. Core synthesis: turns reasoning and tool
          output into the answer card the user sees.
  Call B  the critic pass.
  Call C  the enricher — produces display_summary, the fuller prose behind the card.

Two execution modes. MOBIUS_INTEGRATOR_MODE forces parallel or sequential; if unset,
MOBIUS_INTEGRATOR_PARALLEL_PCT samples. The CODE default is sequential at 0% parallel — but
the deployed service sets MOBIUS_INTEGRATOR_MODE=parallel, so the conservative default is
not what runs.

There are also two paths that skip calls entirely, and the second is subtler than "skip A".

The disambiguation fast-path skips A, B and C outright — when the turn is a disambiguation
there is nothing to synthesise.

Dynamic enrichment (Task #76) needs FOUR conditions together: not disambiguation, the
parallel path, the percentage gate open, and react_loop's own
_is_sufficient_for_deterministic_pass(ctx). When all four hold, Call A's LLM call is skipped
and react_draft is structured DETERMINISTICALLY — regex only, no synthesis. B and C still
run, but as fire-and-forget background jobs that patch the persisted card when they land and
never block the response. So the user gets a regex-formatted answer immediately and a
critiqued, enriched one moments later, in place.

The deployed service sets MOBIUS_DYNAMIC_ENRICHMENT_PCT=100, so the percentage gate is
always open — but the sufficiency check still decides per turn, so this is not
unconditional.

It runs on BOTH pipeline paths. On the ReAct path react_loop does the core synthesis and
this handles what follows — unless ctx.react_bypass_integrate was set, in which case the
ReAct answer is published directly and none of this runs.
""", findings=[
 ("bad", "Three distinct responsibilities (synthesis, critique, enrichment), two execution "
         "modes and a per-turn sampling gate in one 1,887-line module. The passes are "
         "already conceptually separate — A, B and C are named as such throughout — so the "
         "seam for splitting them exists and has not been taken."),
 ("bad", "29 exception handlers, 20 log-and-continue, and the only test named for it covers "
         "the fallback path. This decides what the user sees."),
 ("watch", "Both rollouts are percentage-sampled and default to off, which reads as safe — "
           "but the deployment sets mode=parallel and DYNAMIC_ENRICHMENT_PCT=100, so the "
           "sampling machinery is not sampling. The Chat seat confirms 100 is a lit canary "
           "rather than a broken one, and the per-turn sufficiency check still gates it. "
           "Whether someone meant to leave it fully lit is a question for Ananth."),
 ("watch", "When the deterministic path fires the user's first answer is regex-formatted, "
           "not LLM-composed, and is patched in place when B/C land. That is a visible "
           "product behaviour with no signal of its own — nothing in the trace says which "
           "of the three integrator paths produced the card the user first saw."),
 ("good", "One swallow is explicitly reasoned — 'audit must never break the turn'."),
]),

"continuity": dict(rating="green", depth="code", how="""
The 'do not flail' stage. Three questions: should we ask the user for help (user-as-leverage),
has the user ended the pursuit, and have we hit the attempt ceiling.

It types its vocabulary rather than passing strings around. StuckReason is a Literal —
no_evidence, missing_code, conflicting_info, partial_answer, tool_failed — and there are five
named objective end states (resolved, need_info, unable, user_ended, incomplete), so a stop is
always a stated kind of stop rather than an absence of an answer. MAX_ATTEMPTS_BEFORE_STOP
comes from MasterObjective. Spec'd in docs/RELENTLESS_CONTINUITY_PLAN.md.
""", findings=[
 ("good", "One of only four modules with telemetry of its own, and it has two test files."),
 ("good", "Typed end states mean 'we stopped' always carries WHY — the difference between a "
          "product that gives up legibly and one that just goes quiet."),
 ("watch", "Delegates detection to app/state/continuity_checks.py and master_objective.py, "
           "neither in this catalogue — the wrapper pattern again, though thin here."),
]),

"react_loop": dict(rating="red", depth="code", how="""
The engine of the ReAct path: reason about what to do, call a tool, look at what came
back, go again. It replaces run_plan and the classic sub-question answering, does the core
synthesis, and can skip the integrator entirely via ctx.react_bypass_integrate.

It also emits nearly all of the pipeline's telemetry — thirteen distinct signals, on behalf
of itself and of the sub-modules it drives. Every critic signal comes from here, not from
critic.py.
""", findings=[
 ("bad", "OWNER(chat): REFACTOR react_loop — raised by Ananth as an item, and measuring it "
         "makes it far more tractable than 6,113 lines suggests. TWO FUNCTIONS ARE 69% OF THE "
         "FILE: _execute_tool is 2,253 lines (L1153) and run_react is 1,966 (L4149); with "
         "_finalize_response at 337 the top three are 4,556 lines, 74% of the file. The "
         "remaining 24 top-level defs are 684 lines between them. So this is not 36 things to "
         "untangle — it is essentially two.\n\n"
         "AND THE BIGGER ONE IS MECHANICAL. _execute_tool is a 25-BRANCH DISPATCH CHAIN over "
         "tool names — appeals_*, service_line_*, healthcare_query, google_search, web_scrape, "
         "recall_search, precision_search, document_upload_skill and the rest — averaging ~90 "
         "lines of handler inlined per tool. The target shape is one handler per tool behind a "
         "registry, and THE PRECEDENT ALREADY EXISTS IN THIS CODEBASE: curator_tools.py holds "
         "exactly two of those handlers (lookup_authoritative_sources, ingest_url) in their own "
         "module, called from _execute_tool. The pattern is established and applied to 2 of 25.\n\n"
         "The mechanism also exists: the Phase 1i extraction programme, with a LOC ratchet test "
         "(tests/test_react_split_phase_1i) that has already pulled out prompts, parsing, "
         "round0, critic, governor and feedback_signal.\n\n"
         "WHY IT MATTERS BEYOND TIDINESS, and this reconciles it with Technical Review's ruling "
         "that line count is a SYMPTOM rather than the defect: the actual defect is 21 "
         "log-and-continue handlers sitting on capability paths. You cannot reliably audit 21 "
         "swallows spread across a 2,253-line function. Splitting per tool is what makes each "
         "swallow reviewable in a file small enough to hold in your head — the refactor is the "
         "ENABLER for the fix, not a substitute for it."),
 ("bad", "6,113 lines. Well past the size at which review is reliable, and it is the single "
         "most important file in the product. Phase 1i has been extracting pieces (prompts, "
         "parsing, round0, critic, governor, feedback_signal) and there is an explicit LOC "
         "ratchet test, so the direction is right — but the bulk is still here."),
 ("bad", "Twenty-one log-and-continue handlers, and unlike the orchestrator's these sit on "
         "capability paths: 'corpus search failed', 'recall_search skill failed', "
         "'precision_search skill failed'. A degraded answer is returned and the user is not "
         "told the search never ran."),
 ("bad", "react_loop.py:3922 swallows a failure to emit react_trace. When telemetry fails, "
         "the diagnostic panel for that turn is silently empty — the observability layer has "
         "the same blind spot as the thing it observes."),
 ("good", "It does have a test file, and the extraction programme is real and ratcheted."),
]),
"round0": dict(rating="amber", depth="code", how="""
A shortcut that runs before round 1. When the caller supplied verified ground truth in
system_context — a story presentation node, a skill card with computed metrics — this
answers straight from it and never enters the tool loop. It also handles mid-turn
truncation recovery: a 'Continue' after the model was cut off.
""", findings=[
 ("watch", "No test file, for a module whose whole job is a short-circuit that skips the "
           "main loop. A wrong short-circuit returns a confident answer from stale context."),
 ("watch", "Its short-circuit is marked by preflight_round0_short_circuit_taken at "
           "react_loop.py:4223, but that is a logger.info gated on the step taking >= 50ms, "
           "not an EmitEnvelope. A fast short-circuit is not recorded, so the rate cannot be "
           "measured. Agreed with the Chat seat as one of two worth a real signal."),
]),
"prompts": dict(rating="amber", depth="code",
 ux="Prompt Composition Studio — LIVE at https://mobius-chat-ortabkknqa-uc.a.run.app/admin/prompts "
    "(served from frontend/prompts.html via main.py:3160, backed by app/api/admin_prompts.py). "
    "Blocks, compositions, versions and monitoring. Note the route is /admin/prompts — "
    "/prompts and /prompts.html both 404.", how="""
Two jobs, and the second one is easy to miss.

1. THE REACT PARAMETER PLANNER. This is where a turn's ReAct budget is decided, and the
   answer to 'who sets up the ReAct parameters':
     react_chat_mode_label   normalises the mode — copilot (default), agentic, quick, task
     react_max_iterations_for_mode   rounds per mode: quick 2, copilot/task 3, agentic 10
     _rag_call_ceiling_for_mode      corpus calls per turn: 6 for chat.thinking/agentic,
                                     3 for everything else (Task #103 ruling)
     react_agent_role(iteration, max_it)   what the model is told it is, per round
     guidance_mode_threshold(max_it)       when the loop switches into guidance mode
   The governor can override the round policy, but it is OFF by default, so in practice
   these functions are the policy.

2. THE PROMPT TEXT ITSELF — the system prompt builder and the per-round reasoning context.
   And this does NOT all live in code: with MOBIUS_PROMPT_SOURCE=composition the prompts
   are assembled from versioned blocks in Postgres instead, authored through a real UI.
""", findings=[
 ("watch", "PROMPT MIGRATION AUDIT, 2026-09-08, measured against the live studio tables.\n\n"
           "IN THE STUDIO — 8 module keys, 18 composition versions, 51 block rows across 18 "
           "distinct block keys:\n"
           "    react_explore      v1-v4, v4 active, 7 blocks\n"
           "    react_synthesize   v1-v4, v4 active, 7 blocks\n"
           "    react_draft        v1-v4, v4 active, 7 blocks\n"
           "    react_no_tools     v1 active, 1 block\n"
           "    critic_audit       v1 active, 2 blocks\n"
           "    integrator_enricher_answer   v1 ACTIVE, 5 blocks\n"
           "    integrator_enricher_blended  v1 INACTIVE, 5 blocks\n"
           "    integrator_enricher_factual  v1 INACTIVE, 5 blocks\n"
           "    rag_strategy_c_validate      v1 active, 1 block\n"
           "The block library is real: react.identity, react.critical_rules (6 versions), "
           "react.format_rules, react.tool_manifest, react.user_profile, react.response_shape, "
           "react.output_intent_instruction, react.mode_quality_bar, react.no_tools_body, "
           "critic.audit_rules, enricher.answercard_schema_and_rules (FOURTEEN versions), "
           "module.enricher (8), module.enricher.{answer,blended,factual}, forced_json, "
           "hipaa_context, rag.filler_c_validate.system.\n\n"
           "STILL HARDCODED IN PYTHON — 13 prompts:\n"
           "    pipeline/react/critic.py      CRITIC_SYSTEM_PROMPT, COMPLETION_CRITIC_SYSTEM_PROMPT\n"
           "    pipeline/react_loop.py        _FAST_MODE_SYNTHESIS_SYSTEM, _FAST_MODE_RICH_SYNTHESIS_SYSTEM\n"
           "    pipeline/react/prompts.py     REACT_NO_TOOLS_PROMPT\n"
           "    services/reasoning_agent.py   REASONING_SYSTEM, SKILL_CONTEXT_SYSTEM\n"
           "    services/provider_summary.py  SUMMARY_SYSTEM, ONELINER_SYSTEM\n"
           "    services/doc_assembly.py      RETRIEVAL_SIGNAL_SYSTEM_CONTEXT\n"
           "    state/context_router.py       _ROUTE_CLASSIFIER_SYSTEM\n"
           "    api/email_thread.py           _SUMMARY_SYSTEM\n"
           "    api/product_feedback.py       _FOLLOWUP_PROMPT\n"
           "(A 14th grep hit, retrieval_budget._SYSTEM_PROMPT_RESERVE_TOKENS, is a token count "
           "and not a prompt — excluded.)"),
 ("bad", "OWNER(chat): TWO PROMPTS EXIST IN BOTH PLACES AT ONCE, which is the drift the "
         "migration is supposed to end rather than create. critic_audit is an active "
         "composition AND CRITIC_SYSTEM_PROMPT is still a Python constant. react_no_tools is "
         "an active composition AND REACT_NO_TOOLS_PROMPT is still a constant. With "
         "MOBIUS_PROMPT_SOURCE=composition live, the DB copy is what runs and the Python copy "
         "is dead text that still reads authoritative to anyone opening the file — and nothing "
         "in the trace records which source built a given turn's prompt."),
 ("watch", "THREE ENRICHER COMPOSITIONS EXIST, TWO ARE INACTIVE. "
           "integrator_enricher_answer is active; _blended and _factual are validated, carry 5 "
           "blocks each, and are switched off. Either they are staged for a rollout nobody "
           "finished, or they are abandoned — the table cannot tell you which, and neither can "
           "the code."),
 ("watch", "enricher.answercard_schema_and_rules has FOURTEEN versions and module.enricher has "
           "eight, against one or two for most blocks. Version count is a fair proxy for churn, "
           "and the answer-card schema is where the churn is."),
 ("good", "There is a prompt-authoring surface: frontend/prompts.html backed by "
          "app/api/admin_prompts.py — blocks, compositions, versions and monitoring, with "
          "append-only versioning that never DELETEs or UPDATEs an existing block row. "
          "Prompts are editable and reversible without a deploy. I rated this module "
          "'invisible' before finding it; that was wrong."),
 ("bad", "OWNER(chat): SEPARATE THE PARAMETER PLANNER FROM THE PROMPT GENERATOR — Ananth's "
         "point, and measuring it makes the case rather than the principle doing it. The two "
         "jobs are NOT evenly sized:\n\n"
         "  PARAMETER PLANNER    90 lines, 6 pure functions — react_chat_mode_label, "
         "react_max_iterations_for_mode, _rag_call_ceiling_for_mode, react_agent_role, "
         "guidance_mode_threshold, is_guidance_round.\n"
         "  PROMPT GENERATOR  1,223 lines, 10 defs — build_reasoning_context alone is 582, the "
         "Jinja env 194, _react_guidance_instruction 113, the composition resolution 85.\n\n"
         "So the planner is 7% of the file and it is the 7% that decides how many rounds every "
         "turn gets and how many corpus calls it may spend. It is six pure functions over a "
         "mode string with no dependency on Jinja, on composition resolution, or on the LLM "
         "call — it can be lifted whole.\n\n"
         "WHY THE SEPARATION IS WORTH MORE THAN TIDINESS. Those 90 lines are currently "
         "untestable in practice because they sit behind 1,276 lines of template machinery: "
         "importing them drags in the Jinja environment and the prompt-composition path. "
         "Extracted, they are the easiest table-driven test in the pipeline — mode in, integer "
         "out — and that test is exactly what does not exist today for the constants governing "
         "every turn's cost.\n\n"
         "A THIRD RESPONSIBILITY is in there too, which the split should not leave behind: "
         "_call_llm_json (118 lines) is an LLM INVOCATION, not prompt generation. Three jobs in "
         "one module, not two."),
 ("bad", "1,365 lines and NO test file — including the parameter functions above, which set "
         "every turn's round and corpus-call budget. A wrong constant here silently changes "
         "cost and answer quality for every user and nothing fails."),
 ("bad", "MOBIUS_PROMPT_SOURCE=composition on the deployed service, so the LIVE prompts are "
         "the versioned DB blocks and the 1,365 lines of code prompts are the dormant half. "
         "The untested module is real, but the text it holds is not what production reads — "
         "and the trace does not record which source built a given turn's prompt."),
]),

"tool_manifest": dict(rating="green", depth="code", how="""
The menu of tools the planner is shown. If a tool is not described here the planner cannot
choose it, which makes this file a control surface rather than a list.

It is mid-migration and says so: five tools are now registry-owned, their descriptions
living on SkillSpec.description and rendered through registry.manifest_text(), so adding a
skill is one file and no edit here. The rest are still described inline.
""", findings=[
 ("bad", "OWNER(chat): MOVE THE MANIFEST OUT OF CODE — Ananth's point, and the cost is "
         "measurable. 16 blocks are hardcoded here totalling 19,191 characters, roughly 4,800 "
         "TOKENS injected into the planner prompt. The biggest are _SERVICE_LINE_ROUTING "
         "(~798 tok), _APPEALS (~736), _RAG (~705) and _SEARCH_UPLOADED_DOCUMENT (~636). "
         "Every wording change to any of them is a code edit and a redeploy.\n\n"
         "THE TARGET ALREADY EXISTS IN TWO FORMS and this is half-built rather than unbuilt: "
         "five tools are registry-owned, their text living on SkillSpec.description and "
         "rendered through registry.manifest_text() — the module says adding one of those is "
         "one file and no edit here. And the Prompt Composition Studio already holds a "
         "react.tool_manifest BLOCK, so the manifest has a home in the versioned, "
         "UI-editable store. The remaining 16 blocks have simply not moved."),
 ("bad", "OWNER(chat): CONTEXT-SPECIFIC TOOL SELECTION IS BUILT AND UNUSED. The full plumbing "
         "for Ananth's second ask is already there — get_tool_manifest(allowed=[...]) filters "
         "the rendered text, storage/tool_policy.py computes the list, and the orchestrator "
         "folds it into ctx.allowed_tools. It is not being used to cut prompt length:\n\n"
         "  USER-ACCESSIBLE: a user_tool_subscriptions table exists and works — but it holds "
         "25 rows for exactly ONE user. The capability is real and nobody has it.\n"
         "  CONTEXT-SPECIFIC: mode_defaults narrows for exactly one mode. `task` gets [] (no "
         "tools); copilot, agentic and quick all get None, which means UNRESTRICTED — the "
         "entire ~4,800-token manifest, every turn.\n"
         "  PER-REQUEST: request_policy exists and its own comment calls it a 'future hook'.\n\n"
         "So the answer to 'can we make tool choice user-accessible and context-specific to cut "
         "prompt length' is that both switches are already wired and both are set to "
         "everything-on for every mode a real user runs."),
 ("watch", "The dominant blocks are domain routing rather than tool descriptions — "
           "_SERVICE_LINE_ROUTING at ~798 tokens is the single largest, and appeals is second. "
           "So a context filter keyed on the QUESTION rather than the mode would cut the most: "
           "a credentialing question does not need the appeals routing table, and vice versa."),
 ("good", "694 lines, zero exception handlers, has a test file. Clean."),
 ("good", "The registry migration is documented in the module itself, including what it buys."),
 ("watch", "No config and no telemetry: you cannot tell from the trace what manifest the "
           "planner was shown on a given turn. The second of the two the Chat seat and I "
           "agreed are worth a real signal."),
]),
"capabilities": dict(rating="amber", depth="code", how="""
The single source of truth for what each agent path can answer, fed to the parser and planner
so questions are only decomposed into sub-questions something can actually handle. Each tool
declares can_answer explicitly, so when one fails ReAct has a basis for picking another.
""", findings=[
 ("watch", "VISIBILITY, not a functional defect — Ananth's call, and it is the right "
           "read. A comment dated 2026-04-18 records that ask_credentialing_npi was removed "
           "along with the other credentialing and roster tools, and that the declaration "
           "'rebuilds when credentialing ships as a proper skill integration'. Several "
           "cannot_answer lines still redirect to check_provider_credentialing, which is not "
           "among the 17 declared tools. Nothing misroutes as a result — the tools genuinely "
           "are not there — so this is a register that has not caught up with a deliberate "
           "removal, not a routing bug. Downgraded from bug to observation."),
 ("good", "Declared rather than inferred, and the file says so."),
 ("watch", "No test file, and four callers depend on its shape."),
]),

"parsing": dict(rating="amber", depth="code", how="""
Recovers a structured decision from the reasoning model's free text. Each round is supposed to
emit {thought, tool, inputs, is_complete}; real output arrives in code fences, with trailing
commas, with unescaped newlines, or buried in markdown prose. This is where the tolerance
lives, and it is explicit about how much.

FOUR TIERS, in order: strip a triple-backtick json fence; json.loads verbatim;
json_repair.loads for common LLM hiccups; extract the first balanced {...} block and re-run the
previous two on it. If all four miss the ReAct loop stops — except for one narrow class, 'NPIs
for <org>', which keeps a heuristic fallback so a mangled planner response still routes to
lookup_npi rather than becoming a blank refusal.

It deliberately imports nothing from react_loop, which is what makes it testable in isolation.
""", findings=[
 ("bad", "NO TEST FILE — and the determinism makes this worse, not better. VERIFIED "
         "2026-09-08: parsing.py imports only json, logging, re and the context type. No LLM "
         "call, no randomness, no clock, no IO, no database, no await. Same input, same output, "
         "always. Ananth is right that it is 100% deterministic — which makes it the single "
         "easiest module in this pipeline to test exhaustively, four fallback tiers and all, "
         "and it is the one with nothing. A table of malformed LLM outputs would be a complete "
         "suite."),
 ("good", "The tiers are ordered, documented and bounded, and the one heuristic escape hatch is "
          "scoped to a single named question shape rather than being a general guess."),
]),

"completion_extension_gate": dict(rating="amber", depth="code",
 ux="No surface. ctx.completion_critic_ran / _satisfied / _gaps are set but nothing renders them",
 how="""
THE dynamic ReAct parameter adjuster — and the reason it took a message to the Chat seat
to find it is that it has no module, no class and no name. It is roughly sixty lines
inline in react_loop's main loop body (react_loop.py:5077-5133), from Task #104 with the
wall-clock guard added by #107.

What it does: when the model says is_complete=true and a draft exists, it runs a cheap
second opinion — the completion critic, a 400-token fast call with a 1500ms latency
budget — asking whether the answer actually covers the question. If the critic says no,
the loop does not finish. It appends a synthetic tool result naming what is still missing
and a suggested next query, then:

    _pp_extension_rounds_used += 1
    max_it += 1            # react_loop.py:5120 — mutates the local ceiling
    continue

So the round ceiling is raised for THIS TURN ONLY, in response to observed answer quality.
That is the whole adjuster.

Six conditions must all hold: the governor is on, a contract was built, the mode is
agentic, the turn is not already at ceiling, extension budget remains
(max_extension_rounds - used > 0), and there is wall-clock left — elapsed + 25s < the turn
deadline, the 25 seconds reserving room to synthesise the final answer.
""", findings=[
 ("good", "OBSERVED FIRING, 2026-09-08. One agentic turn against the deployed service came "
          "back with react_trace max_rounds=12 where the per-mode constant is 10 — two "
          "extensions granted, 2 of the contract's 3 spent. The gate is not theoretical and it "
          "is not dormant; it is adjusting the round ceiling on live turns today."),
 ("bad", "The most interesting control loop in the product is an un-named `max_it += 1` "
         "inside an if-block in a 6,113-line file. It is invisible to search, cannot be "
         "unit-tested in isolation, and is the reason this node was missing from the schema "
         "until the Chat seat pointed at a line number."),
 ("watch", "I first wrote that this never fires because the governor is off by default. "
           "Wrong: the deployed service sets MOBIUS_PRODUCT_PROMISE_ENABLED=true, so this "
           "gate IS live for agentic turns. It is the depth half of the per-turn adaptation "
           "pair whose breadth half is retrieval_budget."),
 ("bad", "CONFIRMED BUG (Chat seat, 2026-09-08). governor.py:82 gives copilot "
         "max_extension_rounds=1; the gate at react_loop.py:5080 requires mode_label == "
         "'agentic'. Copilot's budget is defined and can never be spent. Fix is one of two: "
         "widen the gate to ('agentic','copilot'), or set copilot's budget to 0. The table "
         "looks authoritative and is not."),
 ("good", "The wall-clock guard (#107) is the right shape: it reserves 25s for final "
          "synthesis rather than letting an extension eat the answer."),
 ("good", "A completion-critic failure degrades to satisfied and falls through to the "
          "normal finalize path, with the reasoning written at the call site. A swallow I "
          "would defend — it fails toward answering rather than toward hanging."),
]),

"react_retry_guard": dict(rating="green", depth="code", how="""
Stops the loop burning calls re-running a tool that already failed. Written against a pathology
observed in production, where the bandit or the model picked the same dead path round after
round.

Three rules. Same tool plus same inputs plus no new evidence means skip — a failure is recorded
when a tool raises, returns success=False, or comes back with an ErrorEnvelope, and before the
next execution the guard checks whether any NEW tool result has landed since; if not it refuses
and tells the model to choose differently. Fail-fast at loop end: if every round failed and
nothing succeeded, it short-circuits the 'escalate honestly' path and emits a typed refusal.
And tool exhaustion: N consecutive failures of one tool with no success between blocks that
tool for the turn.
""", findings=[
 ("good", "Telemetry of its own AND two test files — the best-covered module in the pipeline."),
 ("good", "Written against an observed production failure, and the rule is 'no new evidence' "
          "rather than a blanket ban, so a legitimate retry after new information still runs."),
 ("good", "A typed refusal beats a hedged answer: the fail-fast path produces something the "
          "caller can branch on rather than prose that looks like an answer."),
]),

"curator_tools": dict(rating="amber", depth="code", how="""
Two tools that let the assistant work on the corpus mid-conversation, called from
react_loop._execute_tool. lookup_authoritative_sources queries RAG's /sources/search to
enumerate URLs Mobius has seen for a payer, state and topic — both ingested and not. ingest_url
POSTs to /documents/import-from-html (or import-from-gcs for uploaded PDFs) to pull one URL
through chunking, embedding, lexicon and publish.

Both are HTTP rather than direct DB, deliberately and with the reasoning written down:
/sources/search runs on RAG so the same shape works whether chat shares a Postgres or talks to
a future split-out curator service, and ingest_url has side effects that belong in RAG's
process rather than being triggered across the wire by SQL.
""", findings=[
 ("bad", "DOES IT DO ANYTHING? Yes — and answering that properly corrected two of my own "
         "claims. It is fully wired: both tools are in _execute_tool's dispatch, both have "
         "manifest blocks and router entries, and since no mode except `task` restricts tools, "
         "the planner is offered them on every copilot and agentic turn. Zero log lines in 30 "
         "days does NOT mean unused: all four logger calls in this module are on FAILURE paths "
         "(logger.warning on HTTP error, logger.exception on failure) and nothing logs a "
         "success. So silence means no failures, not no calls. I had read it the other way."),
 ("bad", "OWNER(payor-policy): LOOK INTO RAG'S WRITE SURFACE — an unauthenticated corpus "
         "write, surfaced from this node but belonging to mobius-rag, which is my module not "
         "chat's. VERIFIED: mobius-rag carries roles/run.invoker for allUsers, and "
         "/documents/import-from-html's only Depends is get_db — no auth dependency of any "
         "kind. An unauthenticated POST from this machine was accepted and the service went on "
         "to fetch the URL; the 502 came from the probe URL 404ing, not from auth. So anyone "
         "who can reach the service can have a URL fetched, classified, chunked, embedded and "
         "queued into the corpus the whole product answers from.\n\n"
         "SCOPE OF WHAT I CHECKED, stated so nobody reads more into it: that ONE route and the "
         "service IAM. mobius-rag exposes 79 write routes and I have audited one. Whether this "
         "is a single endpoint or the pattern is exactly what the audit is for, and I have not "
         "done it — logged to look into, not investigated."),
 ("bad", "AND THE ADMIN KEY IS NOT CHECKED AT ALL. I recorded that MOBIUS_RAG_ADMIN_KEY being "
         "unset means 'rag may 401'. Tested it: RAG's /documents/import-from-html accepted an "
         "unauthenticated POST from this machine and proceeded to fetch the URL — the 502 came "
         "from the probe URL being a 404, not from auth. /sources/search likewise returns 200 "
         "unauthenticated. So the tool is not degraded by the missing key; the key is simply "
         "not a factor. That is a finding about RAG, not about chat — see below."),
 ("good", "The HTTP-not-SQL choice is argued in the module rather than assumed, and it "
          "anticipates a service split that has not happened yet."),
 ("good", "Reuses RAG_API_URL rather than adding env vars — the file says so explicitly."),
 ("watch", "Three swallows on calls crossing a service boundary; a failed ingest that logs and "
           "continues looks the same to the conversation as a successful one."),
]),

"critic": dict(rating="amber", depth="code", how="""
Audits a draft answer against the sources it claims to rest on, before the user sees it.
The module's own docstring states the gap it fills: when the planner says is_complete and
produces a draft, nothing else checks whether the claims are grounded. Shape validators
only look at structure, and the post-run adjudicator runs after delivery.
""", findings=[("good", "Two test files, including one for call resilience."),
               ("good", "Gated by MOBIUS_REACT_CRITIC and MOBIUS_REACT_GROUNDEDNESS_HEURISTIC, "
                        "so it can be turned on or off without a redeploy."),
               ("bad", "MOBIUS_REACT_CRITIC=0 does NOT disable the critic, and reads exactly as though "
                       "it does. With the governor on, the Product Promise mandatory groundedness floor "
                       "invokes critic.py independently of critic_enabled() — react_loop:5140-5145 says "
                       "so explicitly, and the only flag authorised to bypass those gates is "
                       "MOBIUS_PRODUCT_PROMISE_ENABLED, not this one. The deployed service has "
                       "CRITIC=0 and the governor on, so the critic is running while its apparent "
                       "off-switch reads off. Confirmed by the Chat seat."),
                       ("watch", "Emits nothing itself; react_loop emits every critic signal. The Chat "
                         "seat's position, which I accept, is that this is correct by design — "
                         "react_loop owns the loop state and critic.py should not know it is "
                         "being observed.")]),
"governor": dict(rating="amber", depth="code", how="""
The round policy, contract-driven: how many rounds this turn gets, what directive the model
is given next, and — since Chat Architecture's 2026-07-30 ruling — which prompt composition
is selected, replacing react_agent_role() as the live selector.

IT IS ON. The code default is OFF, but deploy/dev.env sets
MOBIUS_PRODUCT_PROMISE_ENABLED=true and the deployed service has it true. I previously wrote
that it never fires; that was reading the default and calling it behaviour.

That makes it the live complement to retrieval_budget. retrieval_budget adapts how much
CONTEXT a turn gets; the governor and its completion-extension gate adapt how many ROUNDS a
turn gets. Breadth and depth, both per-turn, both adaptive — and both running.

One consequence worth knowing: with the flag on, the Product Promise groundedness floor runs
the critic INDEPENDENTLY of critic_enabled(). The deployed service sets MOBIUS_REACT_CRITIC=0,
which turns off the optional path only. The mandatory floor still runs.
""", findings=[
 ("good", "VERIFIED WORKING, 2026-09-08, by exercising it — not by reading the flag. I sent "
          "one agentic turn to the deployed service and read the react_trace it emitted. "
          "governor_enabled=True; mode=agentic; final_directive=complete; per-round directives "
          "issued (search on rounds 1-6); groundedness_floor_ran=True and groundedness_passed="
          "True; total_elapsed_s=114.1 against a 300s deadline.\n\n"
          "THE DECISIVE NUMBER IS max_rounds=12. react_max_iterations_for_mode returns 10 for "
          "agentic. The trace says 12. So the completion-critic extension gate FIRED TWICE, "
          "spending 2 of the contract's 3 max_extension_rounds — the dynamic parameter "
          "adjuster raising the ceiling mid-turn in response to the critic saying the answer "
          "did not yet cover the question. That is the whole mechanism, observed rather than "
          "inferred.\n\n"
          "It also settles the critic flag empirically: MOBIUS_REACT_CRITIC=0 on this service, "
          "and groundedness_floor_ran came back True. The mandatory Product Promise floor runs "
          "the critic regardless of that flag, exactly as the Chat seat and I concluded from "
          "the code."),
 ("good", "It is the depth half of a per-turn adaptation pair whose breadth half "
          "(retrieval_budget) is already live and unconditional. The pairing is coherent."),
 ("bad", "OWNER(chat): THE GOVERNOR IS STRUCTURALLY UNOBSERVABLE. governor.py contains "
         "ZERO logger calls — verified by grep, not inferred. It makes the round policy, "
         "issues the per-round directive, selects the prompt composition and grants extension "
         "rounds, and it says nothing about any of it.\n\n"
         "Its ONLY window is the react_trace envelope, and react_loop emits that, not the "
         "governor — so the observability belongs to a different module than the decisions. "
         "That envelope carries governor_enabled, max_rounds and the per-round directives, "
         "which is how I verified the thing works at all.\n\n"
         "AND THAT SINGLE WINDOW CAN FAIL SILENTLY. react_loop.py:3922 wraps the react_trace "
         "emit in `except Exception as _rt_exc: logger.debug(...)` — debug level, no re-raise, "
         "no counter. So if the trace emit fails, the governor becomes completely invisible AND "
         "nothing anywhere says so. One swallow at debug level is the difference between "
         "'observable' and 'not'.\n\n"
         "The extension gate has the same shape one level down: it sets "
         "ctx.completion_critic_ran, _satisfied and _gaps, and nothing renders any of them.\n\n"
         "The practical consequence, measured today: with zero chat traffic in 24h and no "
         "logger calls in the module, there was NO way to answer 'is the governor working' "
         "except to send a live turn and read the trace. Exercising production should not be "
         "the only instrument."),
 ("bad", "It was shipped behind a default-off flag that the deployment turns on, which means "
         "the code reads as dormant and the system is not. Two of us — the Chat seat and I — "
         "independently said 'off by default, never fires' from reading the default."),
 ("watch", "Enabling it changes control flow AND prompt-composition selection at once. Those "
           "are two rollouts wearing one flag; a regression cannot be attributed to one."),
 ("good", "Has a test file, and replacing scattered round rules with one contract is the "
          "right direction."),
]),

"feedback_signal": dict(rating="amber", depth="code", how="""
Decides whether this is the turn where the user gets asked for feedback, computed from their own
cadence state rather than a fixed interval. The decision is made here and stashed on
ctx.feedback_signal; the planner only chooses whether to surface it via offer_feedback.

Gated by FEEDBACK_PERIODIC_ENABLED, default ON. Extracted from react_loop specifically to keep
that file under its LOC ratchet — the extraction programme working as designed.
""", findings=[
 ("bad", "The module states that inputs it cannot cheaply obtain at plan time — thread turn "
         "count, last-turn QC, whether the user just rated — DEFAULT TO THE CONSERVATIVE VALUE "
         "so the ask never over-fires, and that wiring them in is a follow-up. So the cadence "
         "runs on partial inputs today. It is honest about it, but a reader of the output "
         "cannot tell a real 'not yet' from a 'we did not know'."),
 ("good", "Failing toward not-asking is the right direction for a feedback prompt, and the gap "
          "is documented at the function rather than discovered later."),
 ("watch", "No test file."),
]),

"context": dict(rating="amber", depth="code", how="""
The object every stage reads and writes: correlation_id, thread_id, message, state, plan and
per-stage data. Stages mutate it in place; state moves only through explicit apply_delta
transitions rather than patch merging.

Its field docstrings carry real cross-stage contracts. is_retry is the clearest: it is set when
the raw message was detected as a bare retry phrase and `message` was OVERWRITTEN with the
thread's prior question before the planner ran — and the docstring states that cache-assist
MUST skip its lookup on a retry turn, because re-serving the cached answer the user is
explicitly asking to redo defeats the point.
""", findings=[
 ("bad", "Sixteen callers — the highest coupling in the pipeline. Any change has a wide blast "
         "radius."),
 ("bad", "Cross-stage contracts live in FIELD DOCSTRINGS. 'cache-assist MUST skip its lookup "
         "on a retry turn' is a real invariant enforced by nothing — a reader who does not open "
         "this dataclass will not know it exists, and no test names it."),
 ("good", "Zero exception handlers, explicit transitions: a data structure, not a service, "
          "which is right for something sixteen modules touch."),
 ("good", "SCOPE LENS (DB seat): N/A, with reasoning rather than a null grep. No storage import "
          "of any kind, and PipelineContext is never serialised wholesale — no to_dict, no "
          "asdict(ctx), no json.dumps(ctx). Its fields reach storage only because other stages "
          "read and write them, so those decisions belong to those nodes."),
 ("watch", "FORWARD NOTE from the DB seat, now confirmed: because ctx fields reach storage only "
           "via other stages, this object is the route by which an unmodelled key gets "
           "persisted. active_context is that node — it writes two ctx fields into the turn "
           "record by name."),
 ("watch", "No test file of its own."),
]),

"message_resolver": dict(rating="amber", depth="code", how="""
Works out what the user means by 'it'. Two problems in one module.

Pronoun resolution: 'can you search the web for it?' after a failed query resolves 'it' from the
prior turn before planning. The trigger is REFERENCE_SIGNALS, a regex alternation of literal
phrases — it, that, this one, the same, try again, google it, look it up, what about that, try
a different approach, and a dozen more.

Skill-output awareness: 'how many NPIs have issues with PML?' after a credentialing report is
answered from the report already in context rather than sent to RAG or the web.

It must run BEFORE classify, which preserves the effective_message it sets. Nothing enforces
that order.
""", findings=[
 ("bad", "Reference detection is a hand-maintained regex of literal English phrases. It fires "
         "for the phrasings someone thought of and silently does not for the rest — and a "
         "missed reference does not error, it plans the wrong question."),
 ("good", "Zero exception handlers, has a test file, and it solves an observed conversational "
          "failure rather than a hypothetical one."),
 ("watch", "The ordering dependency with classify is real and implicit."),
]),

"personalization": dict(rating="amber", depth="code",
 ux="The personalization_applied envelope — the user sees their preferences were honoured. "
    "Preferences are AUTHORED in mobius-user, not here.", how="""
Chat's side of a contract owned by another module: Mobius-user/CONSUMER_RECIPE_PROFILE.md.

WHERE COMMUNICATION PREFERENCES LIVE. In profile.communication, three fields with closed
vocabularies:

  tone                  professional | friendly | concise
  ai_experience_level   beginner | regular | expert
  greeting_enabled      boolean

Siblings in the same profile: autonomy{routine_tasks, sensitive_tasks} each automatic |
confirm_first | manual; preferred_name; tasks; timezone; version; generated_at; and
rendered_prompt.

HOW THEY REACH THE MODEL — and this is the part that is not obvious. They do NOT reach it as
fields. mobius-user pre-renders them into rendered_prompt, a 4-6 line paragraph of about 150
tokens, and THAT is what chat splices. The structured communication block is read in exactly
one place in the entire service — personalization.py:114-123 — and only to build the
personalization_applied envelope. It never steers behaviour.

What steers is the rendered prose, spliced at six call sites covering the planner/ReAct
reasoning prompt, the critic, the integrator (both sequential and parallel responders) and
the post-run adjudicator. So a preference shapes tool choice, the quality bar, the voice and
the grade — but only in whatever words mobius-user chose.

The profile arrives per-turn in the POST payload. It is never persisted in chat's thread
state, so it is caller input, not conversation state.
""", findings=[
 ("good", "autonomy_for defaults to confirm_first when the profile is missing. The safe "
          "fallback is the default, not the permissive one."),
 ("good", "Implements a written cross-service contract rather than an assumption about what a "
          "profile contains, and degrades to a no-op for anyone who has not onboarded."),
 ("good", "The emit payload reports the NEGATIVE case too — {applied: false, reason: "
          "no_profile | feature_disabled_via_env} — so 'personalization did nothing' is "
          "visible rather than silent."),
 ("bad", "CHAT IS A PASS-THROUGH FOR PREFERENCES AND CANNOT ACT ON THEM. The communication "
         "block is read once, for reporting. Behaviour comes entirely from rendered_prompt, "
         "prose composed by mobius-user. So chat cannot itself honour tone='concise' — it can "
         "only inject whatever paragraph it was handed. If that rendering is wrong, stale or "
         "empty, nothing here detects it."),
 ("bad", "OWNER(user-manager): DISPUTED ASSIGNMENT. THE VERSION CHECK IS NEVER PERFORMED. The profile "
         "carries a `version` field and nothing in mobius-chat reads it. "
         "BUT THE CONTRACT ALREADY SPECIFIES THE OBLIGATION, and it does not fall on "
         "mobius-user: CONSUMER_RECIPE_PROFILE.md line 116 says '`version` field changes -> "
         "Drop cache, treat as the user updated something', and lines 145-147 say 'Watch for "
         "the version field — if it changes between your cached copy and a fresh fetch, the "
         "template was upgraded server-side and you should discard the cache.' The contract is "
         "explicit and complete. The duty sits with WHOEVER CACHES, and the contract also says "
         "'Don't poll /me per turn ... once per session boot is enough' — so the cache is in "
         "the chat FRONTEND, which fetches at session boot and on preferences PUT and then "
         "passes the profile through on every turn. The chat BACKEND receives it per-turn and "
         "has no cache to invalidate. On the evidence this is a chat-frontend bug, not a "
         "user-manager one. Assigned as directed and flagged rather than silently re-pointed — "
         "one word changes the owner."),
 ("watch", "The module docstring says splicing happens at five stages; there are six call "
           "sites (react/prompts.py:545, react_loop.py:5146 and :5401, responder/final.py:600, "
           "final_parallel.py:269, adjudication/full.py:66). Close, but the count in the "
           "documentation and the count in the code are not the same number."),
 ("watch", "Seven callers and no test file, for something that alters six prompts."),
]),

"active_context": dict(rating="amber", depth="code", how="""
Remembers which tool the conversation is currently inside, so a follow-up lands in the right
place instead of starting over. Replaced an older active_skill notion with something generic
to any tool.

Two functions, and the first is the one that matters: persist_active_context(ctx, turn_record)
ADDS active_context and failed_query to the turn record before it is saved. load_active_context
reads them back out of merged_state or the last turns.

So this 60-line module is a WRITER INTO chat_turns — which makes it exactly the node the DB
seat's forward note pointed at when they said the unmodelled-key failure would recur through
whichever node writes turns.
""", findings=[
 ("bad", "It writes two keys into the turn record by name — active_context and failed_query — "
         "and both are among the three keys state_load also carries outside ThreadState by a "
         "hardcoded allowlist. The same un-modelled pair is hand-copied in two different "
         "modules. The DB seat predicted this node would be where that failure recurs, before "
         "either of us had read it."),
 ("good", "60 lines, zero exception handlers, no config."),
 ("watch", "No test file."),
]),

"credentialing_envelope": dict(rating="green", depth="code", how="""
Routing helpers for credentialing conversations, shared between the classic and ReAct paths so
both agree on what a message is asking for.

The core is resolve_step3_roster_merge_context, which reads thread state and the credentialing
options and returns three things: the roster upload id, whether the user chose outside-in
(external_only), and whether to include roster members. The rest are predicates — does this
thread have reconciliation data, is the message asking for reconciliation, does the envelope
route there.
""", findings=[
 ("good", "Zero exception handlers, and sharing it between both paths is what stops the two "
          "routes disagreeing about whether a message is a credentialing one."),
 ("good", "Returns a typed tuple with each flag's meaning documented, rather than a dict the "
          "caller has to interpret."),
 ("watch", "No test file, for logic that decides which of two workflows a message enters."),
]),

"stages": dict(rating="green", depth="code", how="""
Eleven lines listing the canonical names of the seven classical pipeline stages:
state_load, classify, plan, clarify, resolve, integrate, publish. Every non-ReAct emit
event and trace entry is keyed on these strings. The ReAct path uses its own stage keys,
which are not in this list.
""", findings=[("good", "Constants in one place instead of string literals scattered through "
                        "the pipeline.")]),
"orchestrator": dict(rating="amber", depth="code", how="""
See run_pipeline above — this module is that function plus its helpers.
""", findings=[("bad", "OWNER(chat): LATENCY MEASUREMENT ACROSS THE PIPELINE — Ananth's item, and "
                       "the gap is measurable. NINETEEN OF TWENTY-FIVE pipeline modules carry ZERO "
                       "timing: no perf_counter, no monotonic, no elapsed, no _ms. Every "
                       "classic-path stage is untimed — state_load, classify, plan, clarify, "
                       "resolve — as are tool_manifest (which renders ~4,800 tokens every turn), "
                       "parsing, round0, message_resolver, personalization, curator_tools and "
                       "react_retry_guard. Only six have any: react_loop 41 references, "
                       "orchestrator 24, governor 10, integrate 9, prompts 6, critic 1 — so timing "
                       "exists exactly where the file is already too big to reason about, and "
                       "nowhere else. What is measurable today is the TURN, not its parts: "
                       "react_trace carries total_elapsed_s, and _react_pf logs preflight steps "
                       "only when one exceeds 50ms, so anything fast is invisible by construction. "
                       "'Where did the 114 seconds go' cannot be answered from what the pipeline "
                       "emits. THE STANDARD IS TECHNICAL REVIEW'S — their role lock names "
                       "instrumentation explicitly, every segment timed, no untimed work. The "
                       "implementation is chat's."),
               ("bad", "1,902 lines and 31 log-and-continue handlers on the module that owns "
                       "the turn."),
               ("good", "The stage sequence is explicit enough that this diagram's flow was "
                        "parsed directly from it.")]),
}
