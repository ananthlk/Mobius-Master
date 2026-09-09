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
 ("bad", "OWNER(chat): JWTs ARE IN THE REQUEST LOGS. Found 2026-09-09 while measuring "
         "credentialing route traffic, not by looking for it. Cloud Run request logs for "
         "mobius-chat contain entries like `%2F%23t%3DeyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` "
         "— that is `/#t=<access token>` URL-encoded into the request PATH. Decoded, the "
         "payload carries sub, tenant_id, exp and type=access.\n\n"
         "A fragment is not normally sent to a server, so something is encoding the token into "
         "the path rather than leaving it after the #. However it happens, the consequence is "
         "that live access tokens are written to Cloud Run request logs, where they are "
         "readable by anyone with log access and by anyone a log excerpt is pasted to. Two "
         "distinct tokens appear across 30 days.\n\n"
         "NOT INVESTIGATED — I have not established which client does this, whether the tokens "
         "are still within their exp, or whether the same pattern reaches other services' "
         "logs. Logged rather than chased, per Ananth's standing instruction, and flagged to "
         "Chat Master so nobody pastes a log excerpt before it is understood. Related to the "
         "CHAT_AUTH_MODE=optional item on the POST /chat node but a separate defect."),
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
 ("bad", "OWNER(chat): THE CREDENTIALING ROUTER WOULD SURVIVE LOSING ITS IMPLEMENTATION, "
         "AND THAT IS THE PROBLEM. Chat Master found this and reversed a split I had already "
         "endorsed; I verified the mechanism and it holds, with one correction that makes it "
         "WORSE rather than better.\n\n"
         "api/credentialing.py has ZERO top-level credentialing imports — verified by AST, not "
         "grep. Every route imports its storage module INSIDE the function. Measured across "
         "the 15 decorated routes:\n\n"
         "  14 import a credentialing/roster module function-locally\n"
         "   8 of those sit inside a broad `except Exception:` that returns [] or a plausible "
         "value\n"
         "   6 have NO try at all — an ImportError would surface as a 500\n"
         "   1 imports nothing credentialing\n\n"
         "Chat Master reported 'all 16 routes follow this shape'. They do not, and the mixed "
         "picture is the more dangerous one: delete the twelve service modules and EIGHT "
         "routes start lying (200 with an empty body, forever, indistinguishable from the "
         "empty-table state they already return) while SIX start 500ing. Two different failure "
         "modes from one deletion, one silent and one loud, and NOTHING TELLS THEM APART. A "
         "uniform failure would at least be diagnosable.\n\n"
         "AND THE GATE IS BLIND TO BOTH. I1/I2/I4/I7 are computed from chat_turns.thinking_log; "
         "these routes never touch the react loop. A green gate would prove nothing about "
         "fifteen hollowed-out routes. That retires my own earlier line that 'the gate's "
         "invariants are all we'd have' for the untested twelve — they are not thin here, they "
         "are absent.\n\n"
         "THE DEEPER POINT, which is Chat Master's and is correct: the try/except MECHANISES "
         "the defect. We would ship eight routes that report success while their "
         "implementation is gone — instances thirteen through twenty of the class, created "
         "inside the phase meant to remove it. So api/credentialing.py and the twelve are ONE "
         "ATOMIC UNIT. The only orderings that leave no lie are 'delete router and services "
         "together' (routes 404 — honest) or 'delete nothing yet'. Holding."),
 ("bad", "OWNER(chat): ~25 FRONTEND FETCHES ARE 404ing TODAY AND NOBODY NOTICED — this "
         "node's class, live, not hypothetical. Found by Chat Master during the P1d sweep. "
         "app/api/roster.py was DELETED in 65c4751 and roughly 25 call sites in chat's own "
         "pipeline-*.js were never removed, so every fetch to /chat/roster-truth/* and "
         "/chat/roster-reconcile/* returns 404. The try/catch swallows it and the selector "
         "renders empty. The capability has been gone for as long as that commit is old and "
         "the page looks the same as it always did.\n\n"
         "Worth keeping beside the twelve confirmed instances because it is the only one where "
         "the producer was removed by a DELIBERATE deletion and the consumers were simply "
         "forgotten — which is precisely the risk this program runs every phase. It is also "
         "the argument for P1d taking the frontend with it rather than after it."),
 ("bad", "OWNER(chat): DELETING THE CREDENTIALING PLANNER PATH WOULD SILENTLY BREAK AN "
         "UNRELATED LIVE TOOL. Chat Master caught this before touching anything. "
         "list_thread_document_uploads is a working non-credentialing tool, and "
         "blueprint.py:173 is its ONLY planner routing path — reached exclusively through "
         "cf_intent, the object from the credentialing_flow_intent module P1d marks for "
         "deletion. Remove cf_intent and the planner loses the ability to route there. "
         "Nothing raises; the tool just stops being selected.\n\n"
         "WE WOULD HAVE CREATED A NEW INSTANCE OF THE CLASS WE ARE CATALOGUING. That is the "
         "finding: a deletion program aimed at producers-without-consumers is itself a machine "
         "for manufacturing them, unless every removal asks what ELSE reads this.\n\n"
         "blueprint.py is the one genuinely interleaved file — force_roster_tool_hint, "
         "use_credentialing_qa and cf_intent are set in credentialing branches and read by the "
         "GENERIC per-subquestion loop at :122-176, and the keyword gate at :71-84 fires on "
         "'section', 'readiness' and 'revenue opportunity', generic phrases that happen to "
         "serve credentialing today. Restructuring with harness coverage, not excision."),
 ("bad", "1,902 lines with 42 exception handlers, 31 of which log and continue. Individually "
         "most are defensive and correct — a broken tracing init genuinely should not kill a "
         "turn. Collectively they make it very hard to know which failures are survivable by "
         "design and which are the appeals-outage shape, where a capability disappears and "
         "the turn still looks healthy."),
 ("good", "The branch and the stage sequence are explicit and readable; the flow in this "
          "diagram was parsed straight out of it."),
 ("bad", "OWNER(chat): THE MASTER_OBJECTIVE GAP — filed at Ananth's direction, 2026-09-08, and "
         "IT IS A DATED REGRESSION, not a design choice.\n\n"
         "master_objective is the per-thread record of what the user is actually trying to "
         "achieve across turns: its status, its sub-objectives, its attempt count against "
         "MAX_ATTEMPTS_BEFORE_STOP. It is written by exactly one function, "
         "create_or_update_objective(), with exactly one caller — orchestrator.py:819, inside "
         "the `if not use_react` legacy branch. Every other site in the codebase READS it. On "
         "the live ReAct path orchestrator.py:725 loads it out of merged_state and nothing ever "
         "puts one there.\n\n"
         "MEASURED IN chat_state, 4,915 threads:\n"
         "  key present            4,847\n"
         "  non-null objective       216\n"
         "  explicit null          4,631\n\n"
         "And the 216 are all OLD. By last-updated month: Feb 37, Mar 176, Apr 3. Nothing after "
         "April 2026 has one. Threads updated May onward are null without exception — Jun 149, "
         "Jul 1,013, Aug 1,135, Sep 538. So the objective was genuinely live through roughly "
         "April and then stopped being created, which lines up with the ReAct path becoming the "
         "default. This is not a feature that was never finished; it is a feature that WORKED "
         "AND STOPPED, silently, about five months ago.\n\n"
         "WHAT DEPENDS ON IT, all of which has been inert since: continuity\'s "
         "should_ask_user_for_help (so response_payload[\'user_ask\'] is never set, and the "
         "frontend fallback at app.js:13338 that renders it is unreachable); continuity\'s "
         "get_objective_end_state (so EVERY turn reports objective_status=\'resolved\', "
         "including refusals and the 203 budget-exhausted turns — see the continuity node); "
         "prefill_answer_set_from_master_objective; update_objective_from_integrator, which "
         "runs at orchestrator.py:922 every turn on the live path and finds nothing to update; "
         "and the planner\'s last_master_plan on follow-ups, which is how a second turn was "
         "supposed to know what the first was pursuing.\n\n"
         "THE FAILURE MODE IS THE ONE ALREADY NAMED ON THIS PAGE — a write path with no "
         "surviving writer, where every reader degrades quietly to a default that looks like a "
         "legitimate answer. Nothing logs that the objective is absent; get_objective_end_state "
         "returns the string \'resolved\' rather than raising or reporting unknown.\n\n"
         "NOT ESTABLISHED: whether the objective SHOULD be revived on the ReAct path or "
         "retired in favour of react_loop\'s own react_unfinished_reason / react_unblock_ask, "
         "which do the equivalent job and are wired. That is chat\'s call, and the two answers "
         "lead to opposite work — one adds a call site, the other deletes continuity and four "
         "readers. Filed as the gap, not as a prescribed fix."),
 ("bad", "OWNER(chat): 26 TESTS ARE ALREADY FAILING BEFORE THE REFACTOR STARTS. First full-"
         "suite run, 2026-09-08: 2,593 collected, 2,561 passed, 26 FAILED, 6 skipped, 128s. "
         "This matters more than the count sounds, because the program's gate says 'tests pass' "
         "and that is not a state this repo is currently in — a POST run cannot distinguish a "
         "regression from a pre-existing failure until this set is characterised.\n\n"
         "Clusters, which suggest environment rather than logic in at least two cases: "
         "test_logging_config (7), test_tracing_config (5), test_skill_registry_commit3 (2), "
         "test_b1d_restoration_banner (2), and singles across corpus_confidence_tuning, "
         "latency_no_regrets, mcp_auto_discovery, section_hint_pipeline, tool_auto_retry.\n\n"
         "ONE OF THEM IS THIS PROGRAM'S OWN GUARD ALREADY BREACHED: "
         "test_react_split_phase_1i.py::TestReactLoopRatchet::test_react_loop_loc_under_ceiling. "
         "Someone built a line-count ratchet on react_loop.py to stop it growing, and it is "
         "failing — the module is over its own ceiling. That is P4's acceptance criterion "
         "failing before P4 starts, and it is the strongest single argument that the 6,113-line "
         "split is overdue rather than optional.\n\n"
         "REQUIRED BEFORE P1's GATE CAN MEAN ANYTHING: each of the 26 is triaged into "
         "pre-existing-and-accepted (recorded as a known-failing baseline the gate subtracts) "
         "or genuinely broken (fixed first). Not investigated here — logged with the numbers so "
         "nobody discovers it mid-phase."),
 ("bad", "OWNER(chat): THE CLASSIC PATH IS DEAD AND IT IS 1,159 LINES. Ananth's directive "
         "2026-09-08: find the dead code and remove it, we are not moving off ReAct.\n\n"
         "MEASURED CLOSURE — every module below is imported by NOTHING except the legacy "
         "branch or another module in this list, verified by import grep, not by reading:\n\n"
         "  app/stages/resolve.py          595   imported only by orchestrator.py\n"
         "  app/state/refined_query.py     226   only by stages/plan.py + stages/classify.py\n"
         "  app/stages/plan.py             140   only by orchestrator.py\n"
         "  app/state/clarification.py      88   only by stages/clarify.py\n"
         "  app/stages/clarify.py           86   only by orchestrator.py\n"
         "  app/stages/classify.py          24   only by orchestrator.py\n"
         "  ------------------------------------\n"
         "  1,159 lines, plus the 54-line branch at orchestrator.py:807-860.\n\n"
         "NOT IN THE CLOSURE, and this is the kind of thing that makes a bulk delete go wrong: "
         "app/state/query_refinement.py (128 lines) LOOKS legacy — it is called from "
         "stages/clarify.py — but app/planner/blueprint.py imports it too, so it stays. "
         "Removing it with the rest would break the live planner.\n\n"
         "THE REAL SIZE IS LARGER THAN 1,159. resolve.py has its own downstream callees "
         "(plan_display.py's helper documents itself as 'called from run_resolve()', and "
         "message_resolver.py references run_resolve in its contract) which may become "
         "orphaned in turn. The transitive sweep has NOT been done — this figure is the first "
         "layer only, and I am labelling it as such rather than presenting it as the total.\n\n"
         "THE ONE THING THAT MAKES THIS NOT A PURE DELETE: the path is not unreachable. "
         "POST /chat accepts a per-request `use_react: bool | None` (chat.py:84, forwarded at "
         ":330, applied at orchestrator.py:471 via use_react_override). MOBIUS_USE_REACT is "
         "unset live and defaults to 1, so no turn takes the branch by configuration — but any "
         "caller sending use_react=false still routes into it. Removing the branch means "
         "removing that API field, which is a contract change, not a cleanup. Whether any "
         "client sends it has NOT been established.\n\n"
         "The cost of leaving it is not disk. It is that ctx.classification is set only on the "
         "dead branch, so five live-looking `if ctx.classification in (...)` tests in plan.py, "
         "clarify.py and orchestrator.py read a field that is always None and always take the "
         "same arm — and that the jurisdiction ask, the route-clash ask and query refinement "
         "all sit behind it, so a reader reasonably concludes chat asks for jurisdiction when "
         "it does not (see the jurisdiction and clarification nodes)."),
 ("bad", "OWNER(chat): THE CREDENTIALING SURFACE IS 8,994 LINES IN CHAT AND ITS TABLES ARE EMPTY. "
         "Ananth 2026-09-08: credentialing_envelope needs to go, this is not a chat thing, it "
         "is legacy we are carrying forward.\n\n"
         "THE ENVELOPE ITSELF IS THE SMALL PART. credentialing_envelope.py is 177 lines with 8 "
         "public functions and SEVEN HAVE ZERO CALLERS anywhere in app/ — roster_uploads_from_"
         "active, thread_has_roster_reconciliation_data, message_requests_roster_reconciliation, "
         "message_prefers_outside_in_credentialing, envelope_routes_to_reconciliation, "
         "classify_org_vs_uploads, build_canonical_credentialing_message. The only live one is "
         "resolve_step3_roster_merge_context, imported at credentialing_run_service.py:496. "
         "Deleting the seven is a no-impact change; deleting the file is moving one function to "
         "its single caller.\n\n"
         "THE SURFACE BEHIND IT IS NOT SMALL. 14 modules whose filename names the subject: "
         "roster_credentialing_orchestrator.py 4395, credentialing_run_service.py 1033, "
         "api/credentialing.py 688 (13 routes with roster_upload), roster_truth_pg.py 602, "
         "credentialing_assertions_pg.py 538, api/roster_upload.py 329, credentialing_runs_pg.py "
         "325, plus 7 more at 1084 — 8,994 lines. Plus 125 scattered references inside SHARED "
         "modules: 50 in react_loop.py, 43 in integrate.py, 22 in blueprint.py. Those are the "
         "expensive part; they are not removable by deleting a file.\n\n"
         "ELEVEN OF THIRTEEN TABLES HAVE ZERO ROWS — credentialing_runs, credentialing_assertion, "
         "credentialing_report_runs, _step_outputs, _summaries, _documents, roster_uploads, "
         "roster_upload_members, roster_reconciliation_provider, roster_review_session, "
         "roster_line_item. The two with data are provider_roster (156 rows, last written "
         "2026-08-12) and roster_events (260, last 2026-07-06).\n\n"
         "AND THE DOMAIN HAS ANOTHER OWNER. mobius-skills/provider-roster-credentialing/ is a "
         "separate skill service with its own roster_handler, org_discovery and roster routes, "
         "referencing provider_roster directly. Chat 4,395-line orchestrator duplicates a module "
         "that already exists. That is the strongest form of the point: not a preference that "
         "chat should not do this, but that something else already does.\n\n"
         "THE 59 LIVE MENTIONS ARE NOT THE WORKFLOW. 59 turns in 60 days mention roster, "
         "credentialing or PML, but they read as ordinary policy questions (What must a "
         "practitioner submit to be credentialed by Sunshine Health; AHCA requirements for "
         "credentialing a CMHC) and the roster_report skill appears in ZERO of their thinking "
         "logs. The credentialing QUESTIONS are plain RAG and touch none of this. Removing the "
         "workflow does not remove the ability to answer those 59.\n\n"
         "RESOLVED 2026-09-08, and it inverts the conclusion. THERE IS NO PRODUCTION: three GCP "
         "projects exist and the only live chat is mobius-chat in mobius-os-dev; mobius-chat-api "
         "and -worker in both mobius-staging-mobius and mobiusos-new were last deployed "
         "2026-02-05, seven months ago. So the dev row counts ARE the evidence, not a proxy for "
         "evidence elsewhere — I had imported a dev-vs-prod caveat without checking that the "
         "second half of the distinction exists.\n\n"
         "AND THE 13 ROUTES DO HAVE CALLERS, which the row counts were hiding. "
         "mobius-chat/frontend/static/app.js carries 114 credentialing references, with more in "
         "index.html, roster-unified.html, signin.html and pipeline.html. And "
         "mobius-skills/provider-roster-credentialing/static/pipeline-chat.js calls "
         "credentialing-runs/ — THE SKILL SERVICE THAT OWNS THE DOMAIN CALLS BACK INTO CHAT'S "
         "ROUTES, and it is live at revision 00094. So this is not clean duplication with chat "
         "as the redundant copy; the two are entangled.\n\n"
         "The removal therefore takes a frontend surface and a sibling service's dependency with "
         "it. It needs the Chat FE seat. Partial signal, offered as a hint and not an audit: two "
         "of the element ids app.js binds to (credentialingPreferOutsideIn, "
         "credentialingUploadRoster) exist in NO html, so those listeners never attach — but "
         "that is 2 ids checked out of 114 references."),
]),
}

# ── Cross-cutting ───────────────────────────────────────────────────────────
CROSS = {
"emit_envelope": dict(rating="red", depth="code", how="""
Builds every telemetry envelope the pipeline emits — the typed events the frontend renders
and the log everything downstream is reconstructed from.

IT IS ALSO WHERE THE CODEBASE'S SIGNATURE DEFECT IS MOST MEASURABLE, which is why it has a
node of its own. Ananth, 2026-09-08: log the CallManager pattern as a systemic finding.

THE CLASS, stated once: a capability is implemented — often carefully, often with tests —
and nothing in the live path ever calls it, reads it back, or persists what it produced.
Each instance looks healthy in isolation. The code is present, the tests pass, the docstring
describes real intent. The capability is simply absent at runtime, and health stays green.
""", findings=[
 ("bad", "A NAME-BASED SEARCH ANSWERS 'IS THERE A SYMBOL CALLED X', NEVER 'DOES X "
         "HAPPEN'. Chat Master's self-correction, 2026-09-09, and it is the third distinct "
         "way this codebase hides a live thing from a competent search.\n\n"
         "They were about to report completion_extension_gate as a stale schema entry with no "
         "code, and shipped that claim in code as NODES_WITHOUT_CODE before catching it. The "
         "node IS live: ~60 lines INLINE in react_loop's main loop — the completion critic "
         "plus the `max_it += 1` bump — with no module, class or function of its own. A "
         "nameless inline block has NO SYMBOL, so a symbol search returns empty and the empty "
         "result proves nothing.\n\n"
         "IT WAS INVISIBLE TWO INDEPENDENT WAYS AT ONCE, which is why it mattered most of the "
         "set: nothing to decorate meant its LLM call was charged to the enclosing round's "
         "processing (the un-instrumented-wait defect above), AND nothing to grep meant a "
         "reader concluded it did not exist. Now opens an explicit span.\n\n"
         "Related to but distinct from 'an import edge is not a consumption edge': that one is "
         "a false POSITIVE from a name (an import that proves nothing is consumed); this is a "
         "false NEGATIVE from the absence of a name."),
 ("bad", "AN UN-INSTRUMENTED EXTERNAL WAIT IS INDISTINGUISHABLE FROM OUR OWN WORK — the "
         "most expensive variant of this node's class, because it does not merely hide a "
         "failure, it MISDIRECTS THE FIX. Chat Master, 2026-09-09, retracting three of their "
         "own numbers, and I verified the corrected ones from turn_spans before recording "
         "them.\n\n"
         "The three retractions were one defect: an external wait with no span of its own has "
         "its wall time fall through to the enclosing module's PROCESSING column. So:\n"
         "  'integrate is ~1,079ms/turn of pure processing, the largest block of code we "
         "control' -> actually 240ms; the integrator's own LLM calls had no spans and their "
         "wall landed in the processing column, reading as 12,087ms on one turn\n"
         "  'state_load has a read loop' -> the smoke test reuses fixed cids, so four runs "
         "counted as one turn, ~14x inflation\n"
         "  a 5,770ms RAG call reported as 5,770ms of our processing -> same cause\n\n"
         "NOTHING FAILED. The number was present, plausible, and named the wrong module. That "
         "is worse than a missing metric: a missing number prompts someone to go measure, "
         "while a wrong one sends an engineer to optimise code that was idle the whole time.\n\n"
         "VERIFIED FROM turn_spans on the cited turn (7897f928, 56.5s wall): react_loop root "
         "44,274ms wall of which 12,978 llm and a single tool:healthcare_query span at "
         "30,099ms; integrate 11,726ms wall of which 11,486 llm. Our own processing across "
         "the turn is ~1.4-1.5s. CHAT'S OWN CODE IS 2.7% OF THE TURN.\n\n"
         "TWO STRUCTURAL GUARDS SHIPPED WITH THE RETRACTION, and the reasoning behind the "
         "first is the transferable part: turn_spans.concurrent (migration 064) so parallel "
         "siblings contribute max() rather than sum() — a COLUMN rather than a naming "
         "convention, because a convention is a rule with no enforcement. And turn_matrix() "
         "takes injectable spans so shape rules test without a DB, after the previous version "
         "shipped a broken write precisely because every test patched db_execute."),
 ("bad", "A READ-BACK OF THE WRONG ARTIFACT IS INDISTINGUISHABLE FROM A SUCCESSFUL ONE. "
         "Chat Master's sharpening of this node's class, earned from a failure we produced "
         "together on 2026-09-09 and worth more than the bug that caused it.\n\n"
         "The PHI correlation_id fix failed in two independent halves. MINE: I traced "
         "classifier.py:301 passing `correlation_id=correlation_id` and read it as forwarding "
         "to the LLM call — it populates MessageCheckEnvelope, the diagnostics record. Two "
         "destinations; I did not check which. THEIRS: they verified end-to-end by reading a "
         "log line that contained the field —\n"
         "  INFO phi_message_check {\"correlation_id\": \"f0927dcc-...\", \"gate\": \"clean\"}\n"
         "— which IS that same envelope. They performed a read-back and it PASSED, on the "
         "wrong row.\n\n"
         "Either half alone would have been caught by the other. Together they produced a "
         "green gate, a correct-looking diff, and a confident false claim that the fix worked. "
         "What caught it was querying the destination of record — llm_calls — after a real "
         "turn.\n\n"
         "THE RULE THIS CHANGES: 'ship a reader with the writer' is not sufficient, because a "
         "reader can read the wrong thing and pass. The acceptance criterion must NAME THE "
         "ARTIFACT — for P2b, the test asserts against the stored span row that diagnostics "
         "actually renders from, not an emitter log, not an in-memory object, not the nearest "
         "thing that happens to carry the field. An unnamed read-back is a producer-consumer "
         "check that can be satisfied by a coincidence."),
 ("watch", "NAMING COLLISION, recorded so the next reader is not misled: 'fast mode' means TWO "
           "DIFFERENT THINGS. To Ananth it means chat_mode=copilot — the fast caller mode, "
           "selectable per request, and that is the settled meaning for the latency exercise. "
           "In react_loop.py it names the _rich_evidence early exit above, plus "
           "_build_fast_mode_hedge, _fast_mode_synthesize_answer and "
           "_FAST_MODE_SYNTHESIS_SYSTEM. Both are real and they are not the same mechanism. "
           "Eval's P2b answer inferred the first from the phrase and the inference was right "
           "about intent while the code says something else — which is exactly how a reader "
           "arrives at _FAST_MODE_MIN_CHUNKS and concludes it configures copilot."),
 ("bad", "AN IMPORT EDGE IS NOT A CONSUMPTION EDGE — Chat Master's generalisation of the "
         "P1a orphan, and it belongs beside the producer/consumer class because it is how that "
         "class hides from a sweep.\n\n"
         "P1a asked 'does anything IMPORT this?' The question that establishes liveness is "
         "'does anything CONSUME this?' A re-export makes those two give opposite answers: "
         "planner/__init__.py re-exported `parse`, so parser.py had an importer for its entire "
         "dead life. The same trick works three other ways — a module imported by something "
         "itself unreached, a package nobody imports, a name referenced only from a fixture. "
         "All four look live to a grep.\n\n"
         "THE FIX IS REACHABILITY, NOT HOPS: resolve __init__ re-exports to the defining "
         "module, then ask whether any module TRANSITIVELY IMPORTED FROM AN ENTRY POINT "
         "(app/main.py, app/worker/run.py) consumes the name. Present-in-the-tree is not "
         "reachable. Chat Master's own note is the strongest argument for it: this check would "
         "have flagged the entire planner subtree the INSTANT stages/plan.py was deleted, so it "
         "pays for itself on the very phase that created the orphan rather than a phase later.\n\n"
         "Same family as the swallowed ImportError in the credentialing router — a signal that "
         "reports CONNECTED while nothing flows."),
 ("bad", "A STALE TEST WAS ASSERTING A VULNERABILITY. Found by Chat Master during P1b, "
         "verified by me at app/api/uploads.py:153-159 and tests/test_b1d_restoration_banner.py.\n\n"
         "Two tests asserted `auth_scope == \"global\"` for an UNAUTHENTICATED caller — that "
         "the restoration banner returns cross-session uploads to someone with no identity. "
         "One user's filenames in another user's banner. The path was deliberately removed; "
         "the handler now returns `{auth_scope: \"none\", count: 0, uploads: []}` with the "
         "comment 'returning cross-session uploads to an unauthenticated caller is a "
         "data-isolation violation'.\n\n"
         "So the tests documented the HOLE, not the requirement. Anyone triaging them the "
         "obvious way — make the failing test pass — restores the global path and "
         "reintroduces the leak, and THE SUITE GOES GREEN WHILE DOING IT. A failing test that "
         "looks like a chore is the most dangerous shape a security regression can take, "
         "because the fix and the exploit are the same edit. Rewritten to assert the secure "
         "behaviour with a DO NOT RESTORE note in the source and in the baseline's "
         "shrink_log.\n\n"
         "This is a NEW VARIANT of this node's class and worth naming separately: not a "
         "producer without a consumer, but a TEST WHOSE ASSERTION OUTLIVED THE CONTRACT IT "
         "ENCODED. The producer changed correctly and the check kept demanding the old "
         "behaviour — pressure, pointed backwards.\n\n"
         "It also vindicates the P1b framing. Had we treated the 25 as noise to be cleared, "
         "or 'fixed' them to get a green suite, this is the one that would have cost "
         "something real."),
 ("bad", "FIVE OF THE ELEVEN P1b FAILURES DEGRADED SILENTLY RATHER THAN FAILING LOUDLY — the "
         "same property as this node, observed in the test suite itself. "
         "_execute_tool_with_retry caught a TypeError and returned an exception envelope, so "
         "the retry never fired and the test failed on a retry COUNT rather than on the type "
         "error. _write_async reads record[<col>] under try/except, so a missing key became a "
         "silent no-op. build_pre_built_sections skipped a malformed hint and wrote no key at "
         "all. In each case the real fault was one layer up from where the test complained, "
         "which is why 'the test is stale' and 'the code is broken' were hard to tell apart "
         "without checking live behaviour first — which Chat Master did before touching any "
         "assertion."),
 ("bad", "OWNER(chat): THE DEPLOY SCRIPT PRINTS A FALSE REASSURANCE. Found by Chat Master, "
         "verified by me at scripts/deploy.sh:113. On a dirty tree it emits:\n\n"
         "  warn: working tree has uncommitted changes — image will reflect committed HEAD only\n\n"
         "That claim is not true and nothing implements it. It is a bare echo. The build at "
         ":147 runs `gcloud builds submit \"${PARENT_DIR}\"`, which tars the WORKING DIRECTORY "
         "(596 files on the P1c run), and deploy/cloudbuild.yaml does a plain `docker build .` "
         "on that context — no git checkout, no archive of HEAD, and deploy/.gcloudignore has "
         "no rule covering the dirty paths. Uncommitted work ships while the operator is told "
         "it does not.\n\n"
         "This is the same class as the rest of this node, one layer up: the WARNING is the "
         "producer and the behaviour it promises is the consumer that was never built. Worse "
         "than silence, because it converts a hazard an operator would otherwise check into "
         "one they have been told to ignore.\n\n"
         "CONSEQUENCE FOR THIS PROGRAM, and it is not small: every deploy so far has run "
         "against a dirty tree, so NO REVISION IS A CLEAN BEFORE/AFTER REFERENCE POINT. P1a's "
         "image carried another session's platform.html and 051_*.sql; P1c's carries the same "
         "two. Neither affects chat behaviour, but any claim of the form 'this revision "
         "differs from the last one only by phase X' is unsupported while the tree is dirty."),
 ("bad", "OWNER(chat): THE FAILURE-PATH EMITTERS WERE BUILT, TESTED, AND NEVER WIRED. Four "
         "envelope builders in this module have ZERO callers in app/ and one test file each:\n\n"
         "  make_tool_failed                     0 callers, 1 test file\n"
         "  make_rate_limit_hit                  0 callers, 1 test file\n"
         "  make_turn_started                    0 callers, 1 test file\n"
         "  make_confidence_filter_dropped_all   0 callers, 1 test file\n\n"
         "NOW LOOK AT WHAT ACTUALLY EMITS. Across 400 live turns in 7 days: tool_invoked 13, "
         "tool_completed 11, and tool_failed ZERO — not rare, STRUCTURALLY IMPOSSIBLE, because "
         "nothing calls the builder. turn_completed 380, turn_started ZERO.\n\n"
         "So the telemetry can record that a tool was invoked and that it completed, and has "
         "no way to record that one failed. It can count completions and not starts, which "
         "means A COMPLETION RATE CANNOT BE COMPUTED — only a completion count, which always "
         "looks like success. The observability is biased toward health BY CONSTRUCTION.\n\n"
         "That is the mechanism behind 'health stayed green' during the 29-day appeals "
         "outage, and it is not a one-off: it is this module's shape."),
 ("bad", "OWNER(chat): 184 UNWIRED CANDIDATES ACROSS app/, 86 OF THEM WITH TESTS. Measured by "
         "scripts/platform/gen_unwired.py — public defs whose only references are their own "
         "module and the tests covering them, after excluding what a name-grep can never see "
         "called (FastAPI route handlers, Pydantic models, decorated hooks, enums). 620 public "
         "defs scanned.\n\n"
         "Stated as a CANDIDATE LIST, not a verdict: anything reached by getattr, a registry "
         "or an entrypoint will false-positive, and I removed 160 such cases by hand-checking "
         "the filter rather than shipping the raw 344. The 86 with tests are the strongest "
         "signal — somebody verified it works and nothing uses it.\n\n"
         "Concentration: bubble_backend 9, control_vocab 9, credentialing_envelope 7, "
         "emit_envelope 7, workflow_selection 6, model_registry 5.\n\n"
         "THE DETECTOR ONLY SEES THE MECHANICAL HALF. A column nobody writes and a JSON key "
         "nobody emits leave no symbol to grep, so the confirmed instances below are mostly "
         "INVISIBLE to it. The real count is higher and cannot be produced by this tool."),
 ("bad", "OWNER(chat): THE CONFIRMED ROSTER — twelve instances of one class, each found "
         "separately during this review before anyone was looking for a pattern:\n\n"
         "  CallManager             built, unit-tested, never instantiated outside its own "
         "file; its docstring names it as the home for the module_key/variant_id wiring\n"
         "  variant_id              refresh filters WHERE variant_id='default'; writer never "
         "set it. 1,820 of 1,822 rows NULL in 24h\n"
         "  keep                    curator's decision never persisted. 0 occurrences in "
         "5,713 turns\n"
         "  critic                  0 of 575 stored messages carry the key\n"
         "  cited_source_indices    parsed from model output, never computed. Non-empty on "
         "~11% of turns for 3+ weeks\n"
         "  master_objective        writer stranded inside the dead legacy branch; nothing "
         "since April 2026\n"
         "  user_ask                never set, so the frontend fallback at app.js:13338 is "
         "unreachable\n"
         "  objective_status        always 'resolved'; four other end states unreachable\n"
         "  state_version           inserted and incremented, never read or compared\n"
         "  blueprint_snapshot      declared column, 0 of 2,744 rows ever written\n"
         "  tool-manifest filtering built to cut prompt length, gated off, unused\n"
         "  make_tool_failed etc.   four failure-path emitters, tested, zero callers\n\n"
         "WHY IT KEEPS HAPPENING, and this is the part worth acting on: in every case the "
         "PRODUCING side was built and the CONSUMING side was assumed. Nobody asks 'who reads "
         "what I told it to produce?' A test proves the producer works; nothing proves anyone "
         "listens. That is why tests pass, code review passes, and the capability is absent.\n\n"
         "THE CHEAPEST GUARD is a same-change read-back: no write path ships without a reader "
         "in the same change, and no emitter ships without a caller. Not proposed as work "
         "here — logged as the systemic finding Ananth asked for, and as the thing P2 "
         "(instrument) should be designed against rather than around."),
 ("watch", "This reframes several findings already on this page as one defect rather than "
           "several. The governor being unobservable, the curation decision being unreadable, "
           "the critic never persisting and the appeals outage lasting 29 days are not four "
           "independent gaps in discipline — they are four instances of a producer shipped "
           "without a consumer. Worth saying because fixing them one at a time treats the "
           "symptom."),]),

"model_registry": dict(rating="red", depth="code",
 ux="No surface. The bandit's choices appear only as ab_variant on an llm_calls row — "
    "there is no page that shows what it is learning or which model it currently prefers.",
 how="""
THE MODEL BANDIT — the thing that decides which model serves each call. Ananth,
2026-09-09: "it is one of the silent yet effective instruments we have." Silent is
exactly the problem, which is why it earns a node instead of a paragraph inside
llm_manager.

It is a real Thompson-sampling bandit over a Beta posterior, not a config table:

  Phase 1  < 10 quality samples    explore on per-model benchmark priors (ema_quality)
  Phase 2  10-100 samples          blend prior with observed data
  Phase 3  100+, confidence=locked exploit the best, with 5% drift detection
  plus     forced exploration      every EXPLORATION_INTERVAL turns the least-sampled
                                   model gets a slot, so a model can never starve out

Hard constraints are applied BEFORE the draw and are technical, not quality judgements:
phi_detected routes to hipaa_eligible models only; the planner and react_* rounds
require spec_context_k >= MIN_PLANNER_CONTEXT_K; small-context models are confined to
CHEAP_STAGES; and mode=copilot excludes heavy benchmark_category values so only
Flash-class tiers compete. ReAct rounds are separate arms — react_1..react_4 carry
their own caps and their own PG rows, so round 1 and round 4 learn independently.

IT IS DOING REAL WORK, measured over 7 days: 8,104 calls, of which 3,244 were
hard-pinned and 4,860 — 60% — were chosen by the bandit.
""", findings=[
 ("good", "This is the right shape for the problem. A per-stage Beta posterior with forced "
          "exploration and a benchmark prior is a genuine solution to cold-start, and the "
          "hard constraints being applied before the draw — rather than as low weights — is "
          "the correct way to express 'never route PHI off BAA infrastructure'. A weight can "
          "be overcome by evidence; a filter cannot."),
 ("bad", "OWNER(chat): THE CIRCUIT BREAKER DID NOT PULL A PROVIDER THAT FAILS 100% OF THE "
         "TIME, FOR TWO DAYS. The module documents 'immediate pull if error_rate_24h > 15% or "
         "hard_error_rate > 20%'. Measured against llm_calls:\n\n"
         "  2026-09-06   471 anthropic selections, 469 succeeded\n"
         "  2026-09-07   132 selections,  70 succeeded  <- outage begins 00:58Z\n"
         "  2026-09-08   130 selections,   0 succeeded\n"
         "  2026-09-09    73 selections,   0 succeeded\n\n"
         "203 selections across two full days at a 100% failure rate, and the breaker never "
         "fired. Every one of those turns paid a round-trip to a dead provider before falling "
         "back.\n\n"
         "THE LIKELY MECHANISM IS THE SAME NULL COLUMN THAT BROKE THE ema. The 24h "
         "error-rate breaker reads model_performance_by_stage, which model_registry.py:2293 "
         "filters `WHERE variant_id = 'default'` — the column the writer never populated "
         "until the LLM Agent's fix landed on 2026-09-09. A matview whose row set never "
         "advances cannot report the last 24 hours of anything. So the bandit's safety "
         "mechanism was reading a frozen snapshot while live traffic failed.\n\n"
         "NOT CONFIRMED end to end — I have not traced the breaker's read path to that "
         "matview myself, and the LLM Agent's fix may have already changed the picture. "
         "Recorded as the leading mechanism with the failure measured, not as a proven "
         "chain."),
 ("bad", "OWNER(chat): THE TEST SUITE MUTATES THE BANDIT'S LIVE STATE — TO BE TESTED IN "
         "THE BANDIT'S OWN PASS (Ananth, 2026-09-09). Found by Chat Master while a P2b test "
         "file shifted collection order; root cause verified by me independently.\n\n"
         "MODEL_ROSTER is a process-wide MUTABLE SINGLETON and the specs are written in place "
         "at runtime: spec.ema_quality (model_registry.py:1987, 2030), spec.call_count += 1 "
         "(:1983), spec.quality_samples += 1 (:1988, 2031), plus a PG refresh overwriting both "
         "at :2317-2323.\n\n"
         "Measured during ONE full-suite run: gemini-2.5-flash accumulated call_count=38 and "
         "quality_samples=37, dragging its ema_quality from a seeded 0.78 down to 0.609 — "
         "below gemini-2.0-flash-lite's untouched 0.65, inverting the model ordering a test "
         "asserts on.\n\n"
         "THE BROKEN TEST IS THE SMALL HALF — but narrower than Chat Master and I first "
         "framed it, and the correction is worth keeping. They reported that 37 samples "
         "promotes a model to 'medium' confidence, two tiers above cold start, and called "
         "that an input to selection. I checked: `confidence` (model_registry.py:861-865) is "
         "read in exactly ONE place, :2042, where it is REPORTED in a stats dict. Nothing "
         "selects on it. `spec.quality_samples` is likewise never read by the selection path. "
         "So the confidence tier moving is COSMETIC — a changed label, not a changed "
         "decision.\n\n"
         "WHAT IS REAL, AND IT IS ENOUGH: the suite corrupts `ema_quality`, which feeds "
         "`beta_prior` (:868), which is the PRIOR IN EVERY DRAW at :1626. That is genuine "
         "contamination of model selection.\n\n"
         "IT ALSO BOUNDS THE BLAST RADIUS, which the first framing did not. The draw's "
         "observation weight comes from PG — `total_calls = int(stats.get(\"total_calls\"))` "
         "at :1627, not from the in-process spec — and the roster does not persist. So the "
         "damage is one process's priors for the life of that process: contained in a test "
         "run, and a real concern only in a long-lived Cloud Run instance."
         "WHAT THE BANDIT'S PASS MUST TEST, recorded now so it is not re-derived:\n"
         "  1. a full-suite run leaves MODEL_ROSTER's seeded values unchanged\n"
         "  2. phase transitions are driven by persisted traffic, not by in-process "
         "accumulation from any source\n"
         "  3. the beta_prior test asserts its stated intent (per-model ema_quality, not a "
         "constant) without depending on unmutated seeds — the incidental ordering assertion "
         "is a property of test order, not of the code under test\n"
         "  4. a sibling file already documents this hazard and works around it with source "
         "inspection (test_claude_current_gen_models.py:29-35). One test file knew and the "
         "bandit's did not — the workaround should be the rule, not local knowledge.\n\n"
         "Ananth ruled the immediate test fix proceeds so P2b is not blocked. A GREEN TEST "
         "DOES NOT CLOSE THIS."),
 ("bad", "OWNER(chat): THE BANDIT HAS NO SURFACE. It picks the model for 60% of calls, learns "
         "a posterior per model per stage, runs forced exploration on a schedule, and there "
         "is NOWHERE to see any of it. Its only trace is ab_variant on an llm_calls row. "
         "Nobody can answer 'which model does the bandit currently prefer for the planner', "
         "'is it still exploring or has it locked', or 'when did it last change its mind' "
         "without writing SQL.\n\n"
         "That matters more here than for a quiet module, because a bandit is SUPPOSED to "
         "change its behaviour over time. An instrument that silently changes what it does "
         "and reports nothing is indistinguishable from one that has stopped working — which "
         "is precisely what the two days above look like."),
 ("watch", "It is the natural consumer of P2b's per-model latency stamp, and nobody has "
           "connected them. The bandit optimises on a quality posterior; the stamp measures "
           "that gemini-2.5-pro has a p50 of 20.0s against flash at 4.7s. A bandit that "
           "cannot see a 4x latency difference will happily pick the slow model on quality "
           "grounds — which is one candidate explanation for the routing-latency layer Eval "
           "identified. Flagged as a connection to make, not a defect to fix."),
 ("watch", "2,411 lines, and it holds the roster, the sampler, the constraints, the circuit "
           "breakers and the stage eligibility tables. Its own docstring is 30 lines of "
           "operating rules — the module is doing five jobs and the docstring is the only "
           "place the shape is written down.")]),

"llm_manager": dict(rating="amber", depth="code", how="""
The single entry point for every LLM call in chat. Nothing should call a provider
directly; everything goes through here.

It does more than proxy. It wires a ModelRouter that picks the model per stage rather than
per process, so the planner and the integrator can run on different models in the same
turn. It takes phi_detected from pipeline context so a turn carrying PHI can be routed
differently. It sets ab_variant to the selected model id for analytics, and calls
router.update_ema() after each call so the bandit learns from what actually happened.
""", findings=[
 ("bad", "OWNER(chat): 45% OF llm_calls ROWS CANNOT BE JOINED TO A TURN. Measured 2026-09-09 "
         "while designing the latency telemetry: correlation_id is NULL on 790 of 1,979 rows in "
         "24h. It is not random — FOUR STAGES ARE AT ZERO PERCENT:\n\n"
         "  parser           360 rows, 0 with correlation_id\n"
         "  rag_fact_check   164 rows, 0\n"
         "  phi_classify      98 rows, 0\n"
         "  integrator        23 rows, 0\n"
         "  react_1          233 rows, 94 (40%)\n"
         "  ...every other stage is at 97-100%\n\n"
         "So the per-stage LLM cost of PHI classification, fact-checking and parsing is "
         "attributable to no turn at all. The column exists, the writer populates it for most "
         "stages, and these four never pass it. Note `parser` still logs 360 calls a day after "
         "P2a deleted the planner subtree. RESOLVED 2026-09-09 by the query Chat Master could "
         "not run: parser's last call was 01:12:21Z and P1a deployed at 01:44Z — ZERO parser "
         "calls after it. Those 360 rows are pre-P1a runtime inside a 24h window, exactly as "
         "they predicted. Closed.\n\n"
         "THE OTHER THREE ARE LIVE, which makes their 0% a real defect rather than a deletion "
         "artifact: phi_classify last ran 05:48:41Z, rag_fact_check 05:44:03Z, integrator "
         "05:46:53Z — all current. So the LLM cost of PHI CLASSIFICATION AND FACT-CHECKING "
         "ATTRIBUTES TO NO TURN AT ALL, and anyone costing a turn today undercounts silently "
         "while the total still looks plausible. Same shape as cited_source_indices being "
         "non-empty 11% of the time and nobody noticing.\n\n"
         "NOT A BLOCKER FOR THE LATENCY WORK, per Ananth 2026-09-09: module-level telemetry "
         "measures LLM time INSIDE the module span, so duration does not depend on this join. "
         "The join is for attribution — which model, which variant — not for timing. Logged as "
         "its own defect rather than folded into the telemetry design, and the telemetry is "
         "explicitly designed not to need it."),
 ("good", "One chokepoint for every LLM call is exactly what you want for cost control, "
          "model routing, PHI-aware routing and A/B analytics. This is the right shape."),
 ("good", "Has its own tests, including an attachments suite."),
 ("watch", "Fourteen callers and 432 lines make it the highest-blast-radius module in the "
           "pipeline. A regression here touches every path at once."),
 ("watch", "Six log-and-continue handlers. On a chokepoint, a swallowed failure means a "
           "degraded answer nobody is told about — the exact pattern that hid the appeals "
           "outage for 29 days."),
 ("bad", "OUT OF PROGRAM — LIVE MODEL LATENCY DEGRADATION, 2026-09-08/09. Found while "
         "verifying P1a's deploy, not by looking for it, and logged at Ananth's direction. "
         "EVERY LLM stage is running on the least-bad fallback:\n\n"
         "  thread_summary        gemini-2.5-flash   recent avg  9,970ms vs ema  3,016ms\n"
         "  integrator_critic     gemini-2.5-flash   recent avg 10,435ms vs ema  2,724ms\n"
         "  integrator_enrichment gemini-2.5-flash   recent avg 10,435ms vs ema  2,724ms\n"
         "  phi_classify          gemini-2.5-flash   recent avg 13,180ms vs ema  2,500ms\n"
         "  adjudicator           gemini-2.5-pro     recent avg 28,669ms vs ema  8,000ms\n\n"
         "READ THE MECHANISM BEFORE THE ALARM: this is a LATENCY breaker, not an availability "
         "one. The rule is `recent avg > 3.0x ema`, so it fires when a model gets three times "
         "slower than its own moving average. Flash has gone ~2.5-3.0s -> ~10s and Pro ~8s -> "
         "~25-29s. 'All candidates tripped -> using least-bad' still calls a real model, just "
         "without breaker protection, so the effect is SLOWNESS, NOT WRONGNESS — a live turn "
         "during verification returned a correct 4,487-character answer with 13 sources on "
         "gemini-2.5-flash. I first reported this to Ananth as answers being produced by "
         "fallback selection rather than normal routing; true, but it read more alarming than "
         "the facts warranted, and the correction is recorded here.\n\n"
         "Volume: 74 occurrences on revision 00941, continuing on 00942. Zero on 00940, so it "
         "began during 00941's window (16:29 on 2026-09-08). NOT caused by P1a — deleting "
         "unreachable code cannot slow a provider — and P1a's own deploy sits inside the "
         "affected window, which is why the attribution matters.\n\n"
         "THE CONSEQUENCE WORTH WATCHING is phi_classify, because the PHI gate is FAIL-CLOSED: "
         "sustained classifier latency produces BLOCKED turns, not leaked ones. That is the "
         "safe direction, and `[phi-feedback] redact unreachable (ReadTimeout) — dropping "
         "text` is already in the logs. A refusal during testing in this window is more likely "
         "this than a defect.\n\n"
         "ROOT CAUSE FOUND, and it is NOT Vertex latency — I said that twice and both times "
         "was wrong. TWO OF THREE PROVIDERS RETURN AN ERROR ON EVERY CALL. From llm_calls over "
         "36 hours:\n\n"
         "  anthropic   ALL 11 Claude models   100% failure   ~180-350ms\n"
         "  groq        llama-3.3-70b          24 of 24 fail  ~193ms\n"
         "  vertex      gemini-2.5-flash       1371 calls, 7 fail, avg 5,731ms\n"
         "  vertex      gemini-2.5-pro          971 calls,10 fail, avg 19,702ms\n\n"
         "Last successful Anthropic call: 2026-09-07 00:58:43Z. A clean cliff, not a "
         "degradation. The ~200ms failure time is the signature of an immediate credential or "
         "credit rejection, not a timeout — Ananth's read (out of credit) matches the shape. "
         "Groq also fails 24/24 but succeeded as recently as 01:36 today, so that is "
         "intermittent and probably a different cause.\n\n"
         "SO THE WHOLE FLEET HAS COLLAPSED ONTO VERTEX GEMINI, and gemini-2.5-pro genuinely "
         "averages 19.7 SECONDS. That is the latency the breaker sees. Vertex did not slow "
         "down; the router lost its fast candidates and everything queues behind Pro.\n\n"
         "AND THE 'EMA' IS NOT AN EMA. llm_health.py:206 builds ema_lookup from "
         "spec.ema_latency_ms in MODEL_ROSTER — static literals, 2500.0 for flash and 8000.0 "
         "for pro (model_registry.py:1051,1072). The rule at :236 is recent_avg > 3.0 x that "
         "CONSTANT, so with real latency at 5.7s and 19.7s the breaker can never close. The "
         "name says it adapts; it does not.\n\n"
         "THE REAL DEFECT IS THE REPORTING, and it is the appeals-outage shape again. The "
         "system loudly reports five separate per-stage breaker failures and NOWHERE says that "
         "two of three providers are rejecting every call. error_type is the bare string "
         "'Exception' for all 374 Anthropic failures; llm_calls has no message column and the "
         "provider's actual response is recorded nowhere. So the cause is unrecoverable from "
         "our own telemetry — I could establish THAT every call fails and not WHY.\n\n"
         "ANANTH'S CALL 2026-09-08: test on Gemini for now; the credit question is his, not a "
         "fix for this program. OWNER of the reporting gap: LLM Agent."),
 ("bad", "OUT OF PROGRAM — WHY THE 'ema' NEVER GETS RE-GROUNDED. The LLM Agent took my "
         "static-literal finding to its cause, and theirs is the deeper one. Verified by me "
         "against live data before recording it as fact.\n\n"
         "model_registry.py:2292-2293 refreshes the ema from model_performance_by_stage "
         "`WHERE variant_id = 'default'` — a filter migration 052 added and labelled a "
         "REQUIRED COUPLED CODE CHANGE. But the writer, llm_analytics.build_record(), never "
         "populated module_key or variant_id. Migration 051's backfill set existing rows "
         "ONCE; nothing in the ongoing write path ever set either column again.\n\n"
         "MEASURED: 1,820 of 1,822 llm_calls rows in the last 24h have variant_id NULL. The "
         "only two non-NULL rows are the LLM Agent's own verification write, minutes ago. So "
         "the refresh query has matched NOTHING for over a month and the roster's hardcoded "
         "seed (2500ms flash / 8000ms pro) is never overwritten — which is exactly why my "
         "'the ema is a static literal' observation was true. Symptom and cause fit together: "
         "the value is static because the thing that would replace it selects on a column "
         "nobody writes.\n\n"
         "CallManager — the module whose own docstring names it as the intended home for this "
         "wiring — is referenced only in prompt_manager docstrings and its own tests. Built, "
         "unit-tested, never connected to the live path. That is the fifth instance on this "
         "page of the same class: a write path with no writer, a gate with no caller, an "
         "instruction nobody reads back.\n\n"
         "BLAST RADIUS BEYOND THE BREAKER: model_winner_by_stage and model_composite_scores "
         "(admin dashboards) have been frozen on pre-2026-08-05 data, and the 24h error-rate "
         "breaker cannot reflect the last 24h because its row set never advances.\n\n"
         "FIXED by the LLM Agent in de43bd2 (pushed, NOT deployed): build_record() now writes "
         "module_key=stage and variant_id='default'. I verified the commit is clean — two "
         "files, no P1c deletions swept — which matters, because it was authored into the same "
         "shared working tree as an in-flight refactor phase."),
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
 ("bad", "OWNER(chat): ROOT CAUSE OF THE PER-READ OVERHEAD — EVERY POOLED ACQUIRE RUNS "
         "`SELECT 1` AND A COMMIT. Diagnosed by Eval from source, verified by me at "
         "db_client.py:334-338 before relaying:\n\n"
         "    conn = pool.getconn()\n"
         "    with conn.cursor() as _cur:\n"
         "        _cur.execute(\"SELECT 1\")     # liveness probe\n"
         "    conn.commit()                    # and a commit\n"
         "    return conn, True\n\n"
         "In CHAT_DB_MODE=direct — which is what is LIVE — every db_query and db_execute does "
         "its own acquire -> execute -> release. So each read costs THREE round-trips where "
         "one would do, and a turn's 5-10 DB ops become 15-30. The pool amortises the "
         "CONNECT; it does not amortise this probe, which runs on every acquire.\n\n"
         "That closes the gap I measured and could not attribute: my direct read via the "
         "proxy is 45ms; the service's reads on the same tables are 260-630ms. Three "
         "round-trips accounts for the floor, and the VARIABILITY is the getconn contention "
         "path — the PoolError branch sleeps 50ms and retries within a 5s deadline, so a "
         "contended acquire adds 50ms increments before the query starts.\n\n"
         "THE FIX, endorsed by Eval, has two halves and the second is the one that bites if "
         "omitted: one connection per TURN rather than per query, which removes the "
         "per-query getconn and SELECT 1 entirely; and GUARANTEED RELEASE on every exit path "
         "including the 20s LLM timeout — otherwise a turn that times out leaks its "
         "connection and starves a max=10 pool. That is the same cleanup-on-failure shape as "
         "the state_load bug this node just fixed.\n\n"
         "HONEST LIMIT, kept from Eval's filing: the SELECT 1 is confirmed from source; the "
         "BASE Cloud Run to Cloud SQL round-trip time is unmeasured, so the arithmetic above "
         "is a floor and not a full account of 630ms. The fix holds regardless — three "
         "round-trips to one is a real reduction whatever the base RTT turns out to be.\n\n"
         "AND THE P2b SPAN WILL SHOW IT: its connection-acquire vs query-execute split is "
         "exactly this distinction. The SELECT 1 is acquire-time wearing query-time's "
         "clothes — which is why the counts, which record per-TARGET reads, said n=1 while "
         "the wall said otherwise."),
 ("bad", "OWNER(chat): state_load IS 1.2s AT p50 AND IT IS ALL SEQUENTIAL DB READS — "
         "measured 2026-09-09 from turn_spans, the first finding this node's own "
         "instrumentation produced.\n\n"
         "  p50 1,229ms · p95 2,192ms · max 3,337ms across 107 spans\n"
         "  57 OF 107 SPANS EXCEED ONE SECOND, and it is not the smoke test alone — a "
         "source=real span sits at 2,333ms.\n\n"
         "The counts break it down completely, and this is exactly the discrimination Eval "
         "specified when they insisted a count carry its TARGET. Worst span:\n"
         "    chat_state           n=1    369ms\n"
         "    chat_turn_messages   n=1    909ms\n"
         "    chat_turns           n=1  1,452ms\n"
         "    chat_threads         n=1    605ms\n\n"
         "EVERY n IS 1. So this is NOT a loop — the bug class the instrument was built to "
         "hunt — it is FOUR SEQUENTIAL ROUND-TRIPS, each slow on its own. A bare duration "
         "would have said 'state_load is slow'; count+target says 'four reads, none "
         "repeated, all slow', which is a different fix entirely: parallelise or collapse "
         "the reads, do not go looking for a loop.\n\n"
         "It also corrects the attribution doc, which reported state_load at 345ms "
         "processing + 140ms db on one turn. That turn was not representative: across 107 "
         "spans the median is 1.2s and the work is essentially all DB. Chat Master had "
         "already retracted a state_load claim for smoke-test cid reuse; this is the "
         "opposite direction — the module is slower than the single sampled turn suggested, "
         "not faster.\n\n"
         "IN SCOPE FOR THIS NODE'S PASS as the latency half of production readiness."),
 ("bad", "OWNER(chat): A TRANSIENT READ FAILURE DESTROYS ACCUMULATED THREAD STATE. get_state returns None "
         "for a DB error and None for no-row — identical, and its docstring says only 'or None "
         "if no row', never mentioning the error case. state_load does `raw = get_state(...) "
         "or {}`, builds ThreadState from DEFAULT_STATE, and if the message carries a delta "
         "calls save_state_full, whose UPSERT is a FULL REPLACE by design. One failed read plus "
         "any delta-bearing message overwrites the whole conversation with defaults plus that "
         "turn. Not skipped — destroyed."),
 ("bad", "OWNER(chat): AND NOTHING CAN DETECT IT AFTERWARDS. state_version increments on the same write, so "
         "the row goes 11 -> 12 exactly as a normal turn would. There is no artifact "
         "distinguishing 'turn 12 of a conversation' from 'state reset, now calling itself 12'."),
 ("bad", "OWNER(chat): THE FIX IS LOCAL, NOT A REDESIGN. The same file already uses the right pattern thirty "
         "lines down: _write_state_row warns and returns on connection_error but RAISES on "
         "anything else. Write path loud, read path silent, one module — and the silent one "
         "loses data. get_state is the one function not following its own file's convention."),
 ("bad", "OWNER(chat): state_version is WRITE-ONLY — inserted, incremented, never read or compared anywhere "
         "in app/. So it cannot detect the above, AND read-modify-write through "
         "get_state/save_state_full is unguarded: two concurrent turns on one thread are a "
         "lost update."),
 ("bad", "OWNER(db-seat): CROSS-NODE, invisible to any code read: mobius_chat has NO query guards. "
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

"jurisdiction": dict(rating="red", depth="code", how="""
WHO THE ANSWER IS SCOPED TO — which payer, state, program, regulatory agency. Everything
downstream filters on it: RAG's retrieval filters are built from it (rag_filters_from_active),
the clarify guard reads it, and the answer's correctness depends on it. 137 lines.

AND THE MODULE THAT DECIDES IT IS NOT ON THE LIVE PATH.

There are three separate places jurisdiction is settled, and they do not run together:

  1. classify_message()          state/refined_query.py:85 — regex patterns decide whether
                                 this turn is a jurisdiction_change ("how about for United")
                                 versus a new question or a slot fill.
  2. need_jurisdiction_clarification()  state/clarification.py:30 — decides whether to STOP and
                                 ask the user. Primary signal is the JPD tag matcher against
                                 the RAG lexicon; the parsed payor/state/program is only a
                                 fallback when the tagger returns nothing.
  3. get_jurisdiction_from_active()  state/jurisdiction.py:62 — reads the carried-forward
                                 jurisdiction out of merged_state["active"].

Only (3) runs on the live ReAct path. (1) and (2) are reached ONLY from run_classify and
run_clarify, and both of those are inside the `if not use_react:` branch at
orchestrator.py:807. The live service does not set MOBIUS_USE_REACT, the code default is "1",
and orchestrator.py:763 logs "USE_REACT=true — taking ReAct path (no clarify/plan steps)".
""", findings=[
 ("bad", "OWNER(chat): THE JURISDICTION CLARIFICATION IS DEAD CODE ON THE LIVE PATH. "
         "need_jurisdiction_clarification() decides whether chat should stop and ask 'Which "
         "health plan or payer are you asking about?' before answering. It is called from "
         "run_clarify, which is called from ONE site — orchestrator.py:826 — inside the "
         "`if not use_react` branch. MOBIUS_USE_REACT is unset on the deployed service and the "
         "code default is 1, so that branch never executes.\n\n"
         "CONFIRMED AGAINST LIVE DATA, not just by reading the branch: across 2,741 turns in 60 "
         "days, the string 'Which health plan or payer are you asking about' appears in ZERO "
         "final_messages. So does 'could you please specify' (the multi-slot variant). So does "
         "the route-clash question 'I can either search the web or search our policy materials'. "
         "Three user-facing asks, all reachable only through run_clarify, all with zero live "
         "occurrences.\n\n"
         "The consequence is not that a stage is missing — it is that NOTHING on the live path "
         "asks for jurisdiction before answering. A question with no payer, no state and no "
         "program gets answered anyway, scoped by whatever happens to be carried forward in "
         "merged_state['active'] from an earlier turn, or by nothing at all. The guard that "
         "existed for exactly this was left behind on the other branch."),
 ("bad", "OWNER(chat): jurisdiction_change is decided by regex on the raw message and only "
         "matters on a path that does not run. classify_message() at refined_query.py:85 is a "
         "cascade of literal patterns — INFO_PROVISION_PATTERNS, JURISDICTION_CHANGE_PATTERNS, "
         "SLOT_ANSWER_PATTERNS, NEW_QUESTION_PATTERNS — plus word-count thresholds (>=5 words, "
         "<=5 words, <=4 words). ctx.classification is set at exactly one site, "
         "stages/classify.py:15, which is again inside the legacy branch. Every downstream "
         "reader of ctx.classification (plan.py:51, clarify.py:74, classify.py:17, "
         "orchestrator.py:835 and :866) is therefore reading a field that is never set on the "
         "live path — it falls through as None and every `in (\"slot_fill\", "
         "\"jurisdiction_change\")` test silently evaluates False.\n\n"
         "That is the worst version of dead code: not unreachable, but reachable and always "
         "answering the same way. A reader of plan.py or clarify.py sees a live-looking branch."),
 ("watch", "What DOES survive on the live path is get_jurisdiction_from_active() and "
           "rag_filters_from_active() — the carried-forward jurisdiction is read every turn and "
           "does shape retrieval. So jurisdiction is not absent; it is INHERITED WITHOUT EVER "
           "BEING ESTABLISHED. Worth stating precisely, because 'jurisdiction is broken' would "
           "be wrong — the read path works, the acquisition path is on the dead branch."),
 ("watch", "Rated RED on the strength of the acquisition gap, not the code. state/jurisdiction.py "
           "itself is 137 clean lines with a clear API and no findings against it. The rating is "
           "the guarantee, not the construction — per Technical Review's ruling. Test files: "
           "none found for clarification.py.")]),

"clarification": dict(rating="red", depth="code", how="""
WHEN CHAT STOPS AND ASKS INSTEAD OF ANSWERING. There are FOUR mechanisms and they belong to
three different owners.

  A. Jurisdiction ask      state/clarification.py — "Which health plan or payer?"  DEAD (legacy branch)
  B. Route-clash ask       stages/clarify.py:30 — "web or policy materials?"        DEAD (legacy branch)
  C. Query refinement      state/query_refinement.py                                DEAD (legacy branch)
  D. RAG clarify bypass    react_loop.py:1760 — terminal stop mid-loop              THE ONLY LIVE ONE

D is the one the user actually experiences, and it does not originate in chat at all. RAG
returns routing_keys.clarify_questions in its corpus telemetry; when RAG's status is
"no_retrieval" AND those questions survive two chat-side filters, react_loop sets
react_bypass_integrate, puts the clarify text in final_message and exits the loop. So the
question the user is asked was WRITTEN BY THE RETRIEVER, and chat's only role is to decide
whether to relay it.

The two filters (react_loop.py:961, added 2026-08-08 on a Chat Master directive because RAG
was firing CLARIFY on well-formed queries) are:

  1. SPECIFICITY — reject if the text matches any of 15 generic templates
     ("could you clarify", "please specify", "more details"...); accept if it contains one of
     20 domain terms (payer, plan, code, cpt, hcpcs, icd, state...), OR any digit, OR any
     capitalised word after the first.
  2. CONTEXT — reject if chat's own carried-forward state/payor already appears in the query
     text, i.e. don't ask what we already know.
""", findings=[
 ("bad", "OWNER(chat): THE ONLY LIVE CLARIFY IS WRITTEN BY ANOTHER MODULE AND FILTERED BY "
         "KEYWORDS. 83 turns in 60 days took the RAG clarify bypass — measured from "
         "thinking_log, and every one of them skipped the integrator entirely (see the "
         "integrate node). Chat does not compose the question, does not know why RAG thinks "
         "the query is ambiguous, and cannot tell a genuine ambiguity from a retrieval miss: "
         "the trigger is RAG's status=='no_retrieval', which is also exactly what an empty "
         "corpus looks like. A question the corpus simply does not cover and a question that "
         "is genuinely ambiguous produce the same user-facing behaviour.\n\n"
         "The guard is a keyword heuristic doing semantic work, and it is honest about it — "
         "the code says 'deliberately keyword/substring heuristics, not new inference'. But "
         "_is_specific_clarify_question() accepts on ANY DIGIT or ANY capitalised word after "
         "the first. 'Which Sunshine plan?' passes on the capital S; so does almost any clarify "
         "text a model writes with a proper noun in it. The generic-template list is 15 literal "
         "strings — a sixteenth phrasing passes the filter by not being on the list. This is a "
         "denylist standing where a decision belongs."),
 ("bad", "OWNER(chat): FOUR CLARIFY MECHANISMS, THREE OF THEM DEAD, ALL FOUR STILL IN THE TREE. "
         "A, B and C above are reachable only from run_clarify inside the `if not use_react` "
         "branch at orchestrator.py:807. Zero live occurrences of any of their three user-facing "
         "strings across 2,741 turns. Meanwhile the live mechanism D lives in react_loop and "
         "shares no code, no message format and no telemetry with them. Anyone asked to 'change "
         "how chat asks for clarification' has a 1-in-4 chance of editing the live one."),
 ("watch", "The clarify bypass is terminal and unlogged as a decision: _should_bypass_on_clarify "
           "returns a bare bool. When it returns False the clarify questions are treated as "
           "advisory and the loop continues — a real branch in behaviour with no counter, no "
           "reason string and no trace field. The critic and governor both got reason strings; "
           "this one did not."),
 ("watch", "No test file found for state/clarification.py. The two filters in react_loop.py:961 "
           "are pure functions over strings — the cheapest possible unit tests, and exactly the "
           "kind of deterministic-rule case flagged on the critic node. Assigned to Eval's "
           "catalogue.")]),

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
 ("bad", "OWNER(chat): 13% OF TURNS NEVER REACH THE INTEGRATOR, AND THE USER CAN TELL. "
         "Measured over 2,740 live turns / 60 days by whether the integrator's own "
         "'Composing answer' emit appears in thinking_log: 2,357 ran it, 383 did not.\n\n"
         "  refuse (PHI / clinical guidance)  217\n"
         "  clarify (needs clarification)      83\n"
         "  task mode                           5\n"
         "  unexplained by any known bypass    83\n\n"
         "All four publish ctx.final_message as raw markdown straight from react_loop — no "
         "answer card, no citations, no critique, no enrichment. That is exactly Ananth's "
         "report of sometimes getting a message that reads like it came from react and "
         "sometimes not: it did. The bypass is set at three sites in react_loop "
         "(1222 refuse, 1767 clarify, 2426 still-indexing) and honoured by two early returns "
         "in orchestrator.py (870 task, 894 bypass), each building its own assistant_envelope "
         "inline with empty ui_blocks, empty sources and empty next_steps.\n\n"
         "THE 83 UNEXPLAINED ARE A SEPARATE ITEM. They match none of the three bypass markers "
         "and are not task mode. Cause not established — do not fold them into the same "
         "finding until someone looks.\n\n"
         "The bypasses are individually defensible (a refusal genuinely has no card to build) "
         "but the CONSEQUENCE is not scoped to formatting: on those 383 turns nothing runs the "
         "critic, nothing runs the enricher, nothing emits the diagnostics, and the evidence "
         "ledger assembled during the loop is discarded unread."),
 ("watch", "PROPOSAL, Ananth 2026-09-08 — EVERY LOOP FALLS THROUGH THE INTEGRATOR, with a "
           "deterministic parser as the cheap path and the enricher/critic/diagnostics as "
           "things the integrator may then call.\n\n"
           "THE DETERMINISTIC PARSER ALREADY EXISTS. Under dynamic enrichment (Task #76) Call "
           "A's LLM call is skipped and react_draft is structured by regex alone — no "
           "synthesis — with B and C demoted to fire-and-forget background patches. So the "
           "'quickly reformat the react output deterministically' half is BUILT AND LIVE "
           "(MOBIUS_DYNAMIC_ENRICHMENT_PCT=100 on the deployed service). What is missing is "
           "not the mechanism, it is the ENTRY: that path is reachable only from the parallel "
           "branch behind a four-condition gate, and never at all from the 383 bypass turns, "
           "because those return from the orchestrator BEFORE run_integrate is called.\n\n"
           "So the change is smaller than it sounds: make the integrator the single exit, and "
           "let the bypasses select the deterministic pass instead of skipping the stage. A "
           "refusal or a clarify prompt would then still get a card, citations where they "
           "exist, the diagnostics envelope, and — the part that matters — a place for the "
           "critic to run.\n\n"
           "OPEN, and not mine to rule on: (1) a PHI refusal deliberately does not want an LLM "
           "anywhere near it, so 'falls through the integrator' must mean the deterministic "
           "path is GUARANTEED for that class, not merely available — a sampling gate is the "
           "wrong control for a safety refusal; (2) the still-indexing defer is a status "
           "message, not an answer, and wrapping it in answer-card chrome may be worse UX, so "
           "this is per-bypass, not blanket; (3) it is the same shape as the stage-selector "
           "item on the governor node — integrate becomes the mandatory exit, the governor "
           "says which of its calls run. These two proposals should be scoped together."),
 ("good", "WHERE EACH ROUND'S SYNTHESIS GOES — traced, because it was an open question. Every "
          "round appends one dict to ctx.react_trace_rounds (round, directive, reason, "
          "agent_role, composition_id, elapsed_s, reasoning_depth, latency_budget_ms) at "
          "react_loop.py:4579, and the round's ENRICHMENT — learned, running_answer, "
          "gaps_closed, gaps_open — is written onto that SAME dict later in the round rather "
          "than a parallel structure. integrate.py:625 flattens those into the evidence ledger "
          "that is the enricher's primary reasoning input, so per-round synthesis genuinely "
          "does reach the answer; the enricher formats from the ledger instead of re-deriving "
          "from raw evidence. Rounds with no enrichment key are skipped rather than padded, so "
          "the ledger degrades to react_draft-only rather than erroring. That is a sound "
          "design and it is documented in the code."),
 ("watch", "Two lossy edges on that ledger, both by construction and neither logged anywhere. "
           "learned and running_answer are truncated to 500 characters per round and "
           "gaps_closed/gaps_open to 5 items of 200 characters — so a round that learned a lot "
           "hands the enricher a clipped version with no marker that clipping occurred. And "
           "the per-round emit() strings (the thinking-log lines the user watches stream) are "
           "display only: they go to thinking_chunks and are never read back as input. Worth "
           "stating plainly because the streaming text LOOKS like the reasoning being carried "
           "forward, and it is not — the ledger is."),
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

"continuity": dict(rating="red", depth="code", how="""
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
 ("bad", "OWNER(chat): CONTINUITY RUNS EVERY TURN AND CANNOT DO ANYTHING, BECAUSE ITS INPUT IS "
         "NEVER CREATED ON THE LIVE PATH. Ananth 2026-09-08 read it as duplicative; it is worse "
         "than duplicative — it is inert, and it reports a fixed answer.\n\n"
         "Both of its functions key off ctx.merged_state['master_objective']. That objective is "
         "created by create_or_update_objective(), which has EXACTLY ONE caller: "
         "orchestrator.py:819, inside the `if not use_react` legacy branch. On the ReAct path "
         "the objective is only ever READ (orchestrator.py:725 loads it out of merged_state) "
         "and nothing on that path ever writes one. So obj is None every turn, and:\n\n"
         "  should_ask_user_for_help()  -> (False, None) always. ctx.response_payload['user_ask'] "
         "is NEVER set. The frontend has a fallback at app.js:13338 that renders user_ask as the "
         "next question when the integrator returned none — that branch is unreachable.\n"
         "  get_objective_end_state()   -> ('resolved', None) always, by the `if not obj` early "
         "return at continuity.py:83-84.\n\n"
         "THE SECOND ONE IS NOT MERELY DEAD, IT IS WRONG. Every turn sets "
         "response_payload['objective_status'] = 'resolved' — including refusals, clarify "
         "bypasses, groundedness failures shipped with a warning, and the 203 budget-exhausted "
         "turns that ran out of rounds without the planner ever being satisfied. The four other "
         "end states (need_info, unable, user_ended, incomplete) are unreachable. The module "
         "whose stated purpose is that 'a stop is always a stated kind of stop' currently states "
         "the same kind of stop for every outcome. I previously rated this node GREEN on the "
         "strength of its typed end states; that was rating the construction and not the "
         "guarantee, and the rating is corrected to RED here.\n\n"
         "THE DUPLICATION IS REAL AND THE OTHER COPY IS THE LIVE ONE. react_loop already "
         "computes the same three judgements and its versions ARE wired: "
         "ctx.react_unfinished_reason (no_path_forward, incomplete_coverage, need_more_info, "
         "need_more_time — measured firing on live turns), ctx.react_unfinished_summary and "
         "ctx.react_unblock_ask. integrate.py reads react_unfinished_reason at four sites, "
         "orchestrator.py at one, progress.py at one. So the product does have typed stop "
         "reasons that work; they are react_loop's, not continuity's."),
]),

"react_loop": dict(rating="red", depth="code", how="""
The engine of the ReAct path: reason about what to do, call a tool, look at what came
back, go again. It replaces run_plan and the classic sub-question answering, does the core
synthesis, and can skip the integrator entirely via ctx.react_bypass_integrate.

It also emits nearly all of the pipeline's telemetry — thirteen distinct signals, on behalf
of itself and of the sub-modules it drives. Every critic signal comes from here, not from
critic.py.
""", findings=[
 ("bad", "OWNER(chat): _rich_evidence IS AN UNRECORDED BRANCH THAT CHANGES ROUND COUNT — "
         "invisible drift inside the latency instrument. Found by Chat Master while answering "
         "Eval's control-set question, verified by me at react_loop.py:357-358 and :5864.\n\n"
         "  _FAST_MODE_MIN_CHUNKS = 3 · _FAST_MODE_MIN_CHARS = 500\n"
         "  _rich_evidence = (_chunk_count >= 3 and _total_chars >= 500) -> early-exit synthesis\n\n"
         "It is NOT SELECTABLE: no request field, no env var — grepped and confirmed. It fires "
         "on what RETRIEVAL HAPPENS TO RETURN, so the same question takes the early exit or "
         "does not depending on the corpus that day. Early exit means fewer rounds, fewer "
         "rounds means fewer LLM calls, and LLM call count is the routing multiplier the "
         "latency baseline is trying to hold still.\n\n"
         "So a run where 8 of 22 questions exit early is NOT COMPARABLE to one where 3 did, "
         "and NOTHING IN TODAY'S DATA WOULD REVEAL THAT HAPPENED. A branch that changes round "
         "count and is never recorded is drift you cannot see — the same shape as every other "
         "finding on this node, sitting inside the instrument built to detect drift.\n\n"
         "RECORD IT PER TURN, do not try to force it. You cannot pin a content-triggered "
         "branch; you can log whether it fired, which makes two runs comparable or honestly "
         "incomparable."),
 ("bad", "OWNER(chat): THE CURATION DECISION IS NEVER PERSISTED, which makes "
         "evidence_review untestable after the fact. Measured against 5,713 live turns: 568 "
         "carry gaps_closed and 701 carry gaps_open, so the gap half genuinely records. But "
         "the persisted round is {round, tool, learned, running_answer, gaps_closed, "
         "gaps_open} — and `keep` appears ZERO times in any turn. In memory the round also "
         "carries kept_chunk_count and kept_chunk_chars; neither survives to the database "
         "either.\n\n"
         "So you can see THAT chunks were curated and you cannot see WHICH. The question a "
         "rigorous test most wants to ask — did the model keep the chunks its answer actually "
         "rests on — cannot be asked of any turn that has already run. It can only be observed "
         "live, in memory, on a turn you are watching.\n\n"
         "CHECKED AND NOT A BUG, recorded so nobody re-raises it: there are TWO round shapes "
         "and both readers are right for their own. In memory ctx.react_trace_rounds carries "
         "gaps flat AND nested under `enrichment` (react_loop.py:4987-4995), which is what "
         "react_loop:3819 reads. The persisted final_message.reasoning_trace is flattened, "
         "enrichment stripped, which is what storage/turns.py:428 reads. I went looking for a "
         "shape mismatch and there isn't one."),
 ("watch", "final_message is a TEXT column holding sometimes-JSON: 5,276 rows parse as a JSON "
           "object, 437 are plain prose, 7 are null. Any analysis over the trace has to guard "
           "for that — my first query over it failed on a row beginning with the word "
           "'Which'."),
 ("watch", "WHERE GAPS AND CURATED EVIDENCE ARE KEPT — Ananth asked whether this is "
           "post-RAG or after ReAct. Neither: it is INSIDE the loop, once per round, "
           "immediately after each tool result, and it has no module of its own.\n\n"
           "The mechanism is evidence_review, a block the MODEL emits in its own decision JSON "
           "each round — the code comment is explicit that 'react now actively curates via "
           "evidence_review (keep: [chunk numbers]) instead of us silently deciding for it'. "
           "Four fields: keep (which chunk numbers from the LAST tool result actually matter), "
           "running_answer (the best answer from kept evidence so far, recomputed from scratch "
           "as a confidence check), gaps_closed (what THIS round resolved) and gaps_open (what "
           "is still unresolved).\n\n"
           "What is not kept is NOT deleted. _store_evidence_memory snapshots every chunk into "
           "ctx._evidence_memory BEFORE any pruning, so a later round can pull a set-aside "
           "chunk back with recall_evidence by ref '<call_idx>.<chunk_num>' without spending "
           "one of the 3 rag-call budget slots re-querying for something already retrieved.\n\n"
           "The parsing is deliberately regex over the '[N] header\\ntext' shape rather than a "
           "structured chunk list, and the comment gives the reason: that rendered shape is the "
           "only stable contract between corpus_search's _format_context and this file, so "
           "reparsing it beats threading a parallel structured list through the whole "
           "tool-dispatch path.\n\n"
           "Where it persists: final_message.reasoning_trace[].gaps_closed on chat_turns, read "
           "back up to 8 turns later by get_prior_resolved_entities — and only when "
           "is_continuation is set."),
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

"tool_manifest": dict(rating="red", depth="code", how="""
The menu of tools the planner is shown. If a tool is not described here the planner cannot
choose it, which makes this file a control surface rather than a list.

It is mid-migration and says so: five tools are now registry-owned, their descriptions
living on SkillSpec.description and rendered through registry.manifest_text(), so adding a
skill is one file and no edit here. The rest are still described inline.
""", findings=[
 ("bad", "OWNER(chat): TOOL SELECTION IS SPORADIC, AND THE MODEL NARRATES A MISS AS A "
         "BROKEN TOOL. Ananth, live, 2026-09-09 — and his word for it, 'sporadic', is the "
         "accurate one and worse than 'broken'.\n\n"
         "  13:27:21  'can i offer some feedback'          -> model: 'my feedback tool isn't "
         "working right now'\n"
         "  13:28:34  'the feedback is the tool section...'-> tool fired FULLY: capture card "
         "rendered, category correctly classified Bug, verbatim stored, Done button\n\n"
         "Seventy seconds apart, same session, same user. The feedback service is healthy — I "
         "called /classify directly: HTTP 200 in 1.3s, mobius-feedback rev 00002-2xm ready. So "
         "the tool is not broken; it is INTERMITTENTLY NOT SELECTED, and when it is not, the "
         "model tells the user it is broken.\n\n"
         "THAT IS HARDER TO DIAGNOSE THAN A DEAD TOOL, not easier. A tool that always fails "
         "gets reported and fixed. One that works most of the time and blames itself the rest "
         "produces user reports nobody can reproduce, and the last three such reports (appeals "
         "playbook, PHI verification, this) all had a healthy backend.\n\n"
         "AND THE TELEMETRY CANNOT TELL THE THREE APART. I pulled the failing turn's "
         "thinking_log: it carries NO TOOL ENVELOPES AT ALL — no tool_invoked, no "
         "tool_completed, and tool_failed is structurally impossible because make_tool_failed "
         "has zero callers. So 'never selected', 'selected and returned empty' and 'selected "
         "and errored' are indistinguishable after the fact. The model has the same problem in "
         "real time, which is why it guesses — and its own trace shows the guess hardening "
         "across rounds: 'failed... likely because it wasn't triggered correctly' becomes "
         "'failed repeatedly, indicating it's not currently functional'.\n\n"
         "CORRECTION TO MY OWN EARLIER FRAMING: I told Ananth the model 'fabricated' a broken "
         "tool, comparing it to the appeals 'Unknown tool' case. That was half right. The tool "
         "genuinely did not fire; what was fabricated was the CAUSE, not the failure. His "
         "'sporadic' is the better description and it points at selection, not at the "
         "service."),
 ("bad", "OWNER(chat): A TOOL RETURNED A REAL PLAYBOOK AND CHAT REPORTED THERE WAS NONE. "
         "Found by Ananth testing live, 2026-09-09, cid 0985d25a and bb898cf5. Logged for the "
         "tool node, NOT fixed — his ruling.\n\n"
         "Query: 'how do I appeal a CARC 197 denial for Sunshine Health in Florida?' Chat "
         "emitted 'No playbook — using FL Medicaid defaults' and, in copilot mode, gave up "
         "after 3 rounds with unfinished_reason=no_path_forward.\n\n"
         "THE PLAYBOOK EXISTS. I called the same endpoint chat calls:\n"
         "  GET /playbook-guarded/Sunshine%20Health/197?audience=provider -> 200\n"
         "  deadline_appeal_days 90 · submission_method portal · fax 1-833-504-0580\n"
         "  mail Post Office Box 3070, Farmington MO 63640-3823\n"
         "  appeal_levels: Internal Appeal (L1), Peer-to-Peer Review (L2), ...\n\n"
         "So the answer the user wanted was one HTTP call away and the handler took its "
         "found=False branch anyway. The suspect is react_loop.py:3127 — "
         "`lookup = carc_group or str(carc) if carc else carc_group`. Python parses that as "
         "`carc_group or (str(carc) if carc else carc_group)`, so whatever the planner passes "
         "decides the path: a carc_group of 'PRECERT' builds /playbook-guarded/{payor}/PRECERT "
         "while the row is keyed 197. NOT CONFIRMED — I did not capture the planner's actual "
         "inputs, so this is the leading suspect and not the established cause.\n\n"
         "THEN THE MODEL FABRICATED A TOOL ERROR AND TOLD THE USER. It reported "
         "'Unknown tool: appeals_get_playbook' and 'the appeals tools are currently "
         "unavailable'. I searched the stored turn: EVERY occurrence of that string is inside "
         "the model's own thought field and NONE is in any tool result. The dispatcher is a "
         "single function, the appeals branch at react_loop.py:3005 is reachable, its own emit "
         "strings appear in the trace, and the service returns 200. The tool handed back "
         "success=True with a useless payload; the model could not tell why it was not "
         "helping, invented a mechanical explanation, and shipped that explanation to the "
         "user as fact.\n\n"
         "THIS IS THE SYSTEMIC FINDING TWICE IN ONE TURN. The tool reports success while its "
         "payload is a failure, and tool_failed CANNOT be emitted because make_tool_failed has "
         "no caller (see the emit_envelope node). So nothing in the system could report that "
         "this tool was failing — the model was the only thing that noticed, and the only "
         "thing it could do was guess. That is what reached the screen.\n\n"
         "MODE MATTERS: agentic recovered by falling back to rag in round 3 and produced a "
         "correct answer with the real deadlines and address; copilot's 3-round budget ran out "
         "first. Same defect, different visibility.\n\n"
         "NOT CAUSED BY P1a OR P1c — the appeals dispatch is untouched by both and the "
         "found=False branch predates them. Not verified against the pre-refactor revision.\n\n"
         "Node moved GREEN -> RED. A control surface that silently reports 'no data' when the "
         "data exists is not green, however clean the migration around it is — rating the "
         "guarantee, not the construction."),
 ("bad", "OWNER(chat): SPORADIC TOOL SELECTION — FOLDED INTO THE TOOLS REFACTOR, with the "
         "three candidate layers named. Ananth 2026-09-09: 'we will have to touch the module "
         "anyway... i think the retries or json formatting or something is wrong.. not clear "
         "if it is in react not getting right, tool manifest or executor.'\n\n"
         "THE THREE CANDIDATES, and what would prove each:\n\n"
         "  1. REACT / PLANNER — the model never emits the tool call, or emits it in a shape "
         "the parser rejects. Tell: a planner decision exists for the round but no dispatch "
         "follows, or the raw completion contains a tool name that failed to parse. Ananth's "
         "'json formatting' suspicion lives here — parsing is claimed 100% deterministic (see "
         "the parsing node), so a malformed emission is silently dropped rather than retried "
         "as a parse failure.\n\n"
         "  2. TOOL MANIFEST — the tool is not in the menu for that turn. The manifest is "
         "mode- and subscription-filtered (ctx.allowed_tools), so a tool present in one turn "
         "can be absent in the next with no error anywhere. Tell: the tool's block is missing "
         "from the rendered manifest for that turn while present for the neighbouring one.\n\n"
         "  3. EXECUTOR — dispatched and failed. Tell: a dispatch record with a non-success "
         "result. THIS IS THE ONE WE CAN ALREADY RULE OUT for the feedback case — the "
         "mobius-feedback service answered /classify with 200 in 1.3s while the model was "
         "saying the tool was down. Ananth's 'retries' suspicion lives here: "
         "_execute_tool_with_retry catches TypeError and returns an exception envelope, so a "
         "retry can be consumed without ever firing (found during P1b).\n\n"
         "WE CANNOT DISCRIMINATE TODAY, and that is the point. The failing turn's "
         "thinking_log has NO tool envelopes at all; tool_invoked fired 13 times and "
         "tool_completed 11 across 7 days, and tool_failed is structurally impossible. So "
         "layers 1, 2 and 3 produce IDENTICAL EVIDENCE — none.\n\n"
         "REQUIREMENT ON P2b, and it must land in the span schema before the tools pass "
         "starts or the question stays unanswerable: per turn, record (a) the manifest "
         "actually rendered — which tools were offered, (b) each tool the planner NAMED, "
         "including names that failed to parse, and (c) each dispatch with its outcome. Those "
         "three counts separate the three layers at n=1, which is exactly the discrimination "
         "Eval's count-based design is for. A duration cannot tell them apart; a count can."),
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
                         "being observed."),
               ("bad", "OWNER(chat): THE TURNS THAT MOST NEED AUDITING ARE THE ONES THAT SKIP IT. "
                       "Measured on 1,600 live react_traces in chat_turns.thinking_log over 60 days "
                       "(2026-07-10..09-08), not inferred:\n\n"
                       "  floor ran     966    floor skipped  634\n"
                       "  quick    306 / 306 skipped  (correct — confidence_bar=low trusts self-report)\n"
                       "  copilot  328 ran / 192 skipped\n"
                       "  agentic  633 ran / 136 skipped\n"
                       "  task       5 ran /   0 skipped\n\n"
                       "The 328 non-quick skips are the finding. The floor only runs when the planner "
                       "PROPOSES COMPLETION. When the loop instead runs out of rounds it falls through "
                       "to react_loop.py:6113, which finalizes with a prose caveat and never calls the "
                       "critic at all. 173 of the copilot skips are exactly rounds_used=3 of max=3, and "
                       "30 of the agentic skips are 10 of 10 — the ceiling, every time. A turn that "
                       "exhausted its budget without the planner ever being satisfied is the LEAST "
                       "trustworthy output the loop produces, and it is the one class shipped with no "
                       "groundedness check. The apology text is not a substitute for the audit.\n\n"
                       "167 further skips carry unfinished_reason=none — ended normally, floor still "
                       "never ran. Cause not yet established; do not assume it is the same bug."),
               ("bad", "OWNER(chat): NO STATED RULE FOR WHEN THE CRITIC IS REQUIRED. Three independent "
                       "gates decide it and no document says which turns MUST be audited: "
                       "(1) critic_enabled() on MOBIUS_REACT_CRITIC, off live; (2) should_run_critic(), "
                       "a regex scan for dollar amounts, day counts, HCPCS/CPT/ICD codes, percentages, "
                       "phone fragments and the literal word 'deadline'; (3) the Product Promise floor, "
                       "which bypasses both. The regex is the load-bearing one whenever gate 1 is on, "
                       "and it is a proxy for risk, not a rule: an unsupported 'prior authorization is "
                       "required' contains no number and scores as safe, which is the exact modal-claim "
                       "class critic.py's own docstring says regex cannot catch.\n\n"
                       "NEEDED, and this is a testing item not a fix: write down the rule — which turn "
                       "classes require groundedness before delivery — then build a DETERMINISTIC "
                       "version of that rule and test it independently of the LLM critic. The LLM call "
                       "is unavoidable for semantic claim-matching, but WHETHER TO AUDIT should be a "
                       "pure function over (mode, sources, signal, answer, terminated_by) with fixture "
                       "cases and no model in the loop. should_run_critic() is already pure and already "
                       "returns a reason string; it is 80% of that function and has no test asserting "
                       "the two classes that matter — budget-exhausted turns, and modal claims with no "
                       "numerals. Assigned for rules-first, then fixtures."),
               ("watch", "36 of 966 audited turns failed groundedness (3.7%). 34 shipped with the "
                         "'Groundedness notice' warning appended and 8 bought an extra round. So the "
                         "floor's dominant live outcome is ship-with-warning, not retry — worth knowing "
                         "before anyone tunes the prompt on the assumption that it mostly self-corrects.")]),
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
 ("bad", "OWNER(chat): THE GOVERNOR IS CONFIG IN EVERYTHING BUT DELIVERY — IT IS A PYTHON "
         "DICT. Every number that defines what a turn is allowed to do lives in _MODE_DEFAULTS "
         "at governor.py:81-85 as a frozen literal: max_rounds, max_extension_rounds, "
         "confidence_bar and soft_target_s for each of quick/copilot/agentic/task. So are "
         "_DIRECTIVE_TO_AGENT_ROLE (which composition each directive selects) and "
         "_AGENT_ROLE_TO_REASONING_DEPTH (which speed tier the model bandit is asked for). "
         "Exactly ONE value in the module is externalised — MOBIUS_TURN_DEADLINE_S — and "
         "default_contract_for_mode() is the only caller of the table, from a single site at "
         "react_loop.py:4344. There is no per-org, per-user or per-tenant override path and no "
         "DB-backed row anywhere: changing 'agentic gets 10 rounds' to 12 is a code edit and a "
         "redeploy of mobius-chat.\n\n"
         "This is the same complaint already logged against tool_manifest, and it has the same "
         "shape: a table of operating parameters that operators need to tune, sitting in a "
         "source file behind a deploy.\n\n"
         "THE ASYMMETRY IS THE POINT. The governor and the prompts are ONE control plane — "
         "governor.py:182 says so outright, the directive REPLACED react_agent_role() as the "
         "live composition selector, so the governor now CHOOSES WHICH PROMPT RUNS. But the "
         "prompt half already has a UX (the Prompt Composition Studio, blocks + versions, "
         "DB-backed, changeable without a deploy) and the half that selects between them does "
         "not. One turn's behaviour is split across a versioned studio and a redeploy-only "
         "dict, and the dict is upstream of the studio."),
 ("bad", "SCOPE LENS (DB seat, 2026-09-08): chat_turns.blueprint_snapshot is 0 of 2,744 — a "
         "DECLARED COLUMN NOTHING HAS EVER WRITTEN. It is the same shape as "
         "document_pages.source_url: any reader gets NULL for every row and reads uniform "
         "behaviour where the truth is a missing input. Recorded here because the refactor "
         "baseline reconstructs turn inputs from these columns, and a silently-empty one would "
         "look like a signal. context_summary is also only 1,853 of 2,750, which is why the "
         "frozen baseline stratifies on it."),
 ("bad", "OWNER(chat): 116 OF 187 CONFIG KNOBS RUN ON INVISIBLE CODE DEFAULTS. Counted, not "
         "estimated: app/ reads 187 distinct environment variables; the deployed revision sets "
         "81. The other 116 are running on whatever literal is written in the `or` clause at "
         "the read site, and nothing anywhere lists them or their effective values. This is the "
         "generalisation of an error already made twice on this page — reading a code default "
         "and calling it deployed behaviour (governor 'off' when it is true, integrator "
         "'sequential' when it is parallel, enrichment '0%' when it is 100). The reason that "
         "error keeps happening is that there is no surface which states the effective value, "
         "so the source literal is the only thing anyone can read."),
 ("watch", "PROPOSAL, Ananth 2026-09-08 — a config UX over the governor + planner/prompt plane, "
           "raised as the easiest of the platform items to complete and the one that would let "
           "an operator change model speed and latency without a deploy. It is a genuinely "
           "small surface: 4 modes x 4 numbers, 4 directive->composition rows, 3 "
           "role->reasoning_depth rows, plus the ~10 react env flags.\n\n"
           "CORRECTION, 2026-09-08 — I NAMED THE WRONG MAP, caught by the LLM Agent and verified "
           "by me before accepting it. I wrote that agent_role_to_reasoning_depth() is the "
           "latency lever. It is NOT LIVE: grep shows zero callers outside a docstring mention "
           "in prompts.py, and its own docstring says 'KNOWN LOSSY'. react_loop.py:4559-4566 "
           "calls directive_to_reasoning_depth() against a DIFFERENT four-row map keyed on the "
           "DIRECTIVE (search->fast, consolidate->fast, extend->thinking, finalize->fast), then "
           "wraps it in resolve_reasoning_depth() with a pre-loop query-intent FLOOR that can "
           "raise a round's depth but never lower it — a third element I did not know existed. "
           "The live map also carries more reasoning than the one I quoted: consolidate and "
           "finalize are both time-pressure states deliberately kept fast despite resembling "
           "synthesize/draft, and extend is the one case where spending more is correct. The "
           "latency lever is real, but it is 4 directives with a floor, not 3 agent roles.\n\n"
           "NOT COSTED, and three things must be settled before anyone builds it: (1) where the "
           "values live — the Prompt Composition Studio's control plane is the obvious home "
           "since the governor already selects its compositions, but that is the studio owner's "
           "call, not mine; (2) what a bad edit can do — max_rounds and soft_target_s are "
           "bounded by hard_ceiling_s and the turn deadline, but confidence_bar is NOT bounded, "
           "and setting agentic to 'low' silently disables the mandatory groundedness floor for "
           "every agentic turn (see the critic node) — a dropdown that can turn off the safety "
           "audit needs a guard, not just a save button; (3) whether it is per-org or global. "
           "Logged as direction, not scoped work."),
 ("watch", "PROPOSAL, Ananth 2026-09-08 — THE GOVERNOR AS THE STAGE SELECTOR, not just the "
           "round policy. The observation is that the governor is the only thing in the turn "
           "that holds the full picture, so it is the right place to decide WHICH STAGES RUN: "
           "should the integrator run, should the critic, should enrichment.\n\n"
           "The structural case is strong, and it is that the alternative is already failing. "
           "Today those decisions are scattered across 13 module-level *_enabled() predicates "
           "and 4 should_*() gates, each private to its own module, each reading its own "
           "environment variable, and NONE of them able to see the turn's contract or its "
           "remaining budget. critic.py's should_run_critic() takes (answer, sources, signal, "
           "message) — it cannot see elapsed_s, so it cannot decide 'skip the audit, we are "
           "110s into a 120s soft target', and it cannot see how the loop terminated, which is "
           "exactly why 203 budget-exhausted turns ship unaudited (see the critic node). "
           "integrate.py's _dynamic_enrichment_enabled() reads one env var and cannot see "
           "rounds remaining. Each gate is locally reasonable and the set of them is not a "
           "policy.\n\n"
           "The governor already has every input those gates lack. RoundState carries "
           "elapsed_s, base_rounds_remaining, extension_rounds_available, "
           "self_reported_confidence, critic_verdict and groundedness_passed; the contract "
           "carries the mode's bar and both time budgets. evaluate() is already a PURE "
           "function over exactly that pair, already returns (decision, reason), and is already "
           "tested as one. Returning a stage set alongside the directive needs no new "
           "information — only a wider return type. That is the cheapest version of this and "
           "it is why the proposal is credible.\n\n"
           "WHAT IS NOT SETTLED, and none of it is mine to rule on: (1) the flags do not all "
           "mean the same kind of thing — MOBIUS_REACT_CRITIC is an operator kill switch, "
           "should_run_critic() is a per-turn risk judgement, and CACHE_ASSIST_SKIP_CRITIC_WHEN_"
           "PREAUDITED is a provenance claim about an older answer; collapsing three different "
           "questions into one selector is how a policy surface becomes a place bugs hide. "
           "(2) it inverts the dependency — stages would be told whether to run instead of "
           "deciding, which is better structure but touches every stage's call site. (3) the "
           "governor is currently gated OFF by default in code, so a stage selector living "
           "inside it inherits a flag that, if ever flipped off, would take the whole selection "
           "policy with it. Logged as direction. Belongs with the config-UX item above — same "
           "control plane, and the UX is what would make the resulting policy legible."),
 ("bad", "OWNER(chat): TWO EXTENSION POLICIES, ONE LEDGER, AND THEY DISAGREE ON TIME. "
         "Ananth's read is right — the completion-extension gate does the governor's job, and "
         "it does it WITHOUT CALLING THE GOVERNOR.\n\n"
         "The groundedness floor asks evaluate() and gets back 'extend' under the governor's "
         "own rule: extension_rounds_available > 0 AND elapsed_s < contract.soft_target_s, with "
         "FINALIZE_MARGIN_S = 5.0. The completion critic at react_loop.py:5118 decides the same "
         "thing inline with its own rule: _cc_elapsed_s + 25 < _cc_deadline_s, where "
         "_cc_deadline_s is a FRESH os.environ read of MOBIUS_TURN_DEADLINE_S with a literal "
         "120 fallback. It ignores contract.hard_ceiling_s — already computed, already clamped, "
         "sitting in scope — ignores soft_target_s entirely, and hardcodes 25 where the "
         "governor has a named 5.0 margin.\n\n"
         "WITH THE LIVE NUMBERS THE TWO RULES ARE 155 SECONDS APART. MOBIUS_TURN_DEADLINE_S=300 "
         "on the deployed service; agentic soft_target_s=120. The governor stops extending at "
         "120s. The completion critic keeps extending until 275s. For every agentic turn "
         "between 120 and 275 seconds there is a window where the completion gate spends "
         "extension rounds the governor's own policy would have refused — and it spends them "
         "from _pp_extension_rounds_used, THE SAME LEDGER the governor reads back as "
         "extension_rounds_available. The counter has two writers and only one is the policy.\n\n"
         "OBSERVED, not inferred: over 60 days and 1,600 react_traces, 190 turns were granted "
         "extension rounds (187 agentic, 3 copilot) and 102 of those finished past their mode's "
         "soft target — the exact region where the two rules give different answers. 62 agentic "
         "turns spent the full 3-round extension budget.\n\n"
         "Two further shapes worth separating. The fallback defaults DISAGREE: the governor's "
         "_DEFAULT_TURN_DEADLINE_S is 90, the completion gate's inline fallback is 120 — same "
         "variable, two modules, 30s apart if it were ever unset. And the governor CLAMPS the "
         "deadline into [min, 900] at contract construction; the inline read does not, so a "
         "misconfigured value is bounded on one path and unbounded on the other.\n\n"
         "This is the concrete instance of the stage-selector item above. The fix is not to "
         "reconcile the two constants — it is that a second module should not be deciding "
         "'extend' at all. evaluate() already returns that directive."),
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
