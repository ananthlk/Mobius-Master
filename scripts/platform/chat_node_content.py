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
"POST /chat": dict(rating="amber", depth="code", how="""
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

Auth is Depends(require_user), governed by CHAT_AUTH_MODE — required by default when
CHAT_ENV is staging or prod, off in dev. The PHI gate runs here, before anything queues.
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
]),

"PHI gate": dict(rating="green", depth="code", how="""
Not a module of its own so much as a call made at the API boundary before anything is
queued: _phi_check_message POSTs the message text to the PHI classifier's /message-check.

It is FAIL-CLOSED, and this is the whole point. Any timeout, network error or non-200
returns block=True with gate='indeterminate'. Taking the classifier offline therefore
cannot be used to bypass the gate. The docstring is explicit that the frontend pre-check
fails OPEN and is a UX affordance only — this backend re-run is the authoritative layer.

A blocked message returns HTTP 422 carrying phi_blocked, the identifier labels and the
evidence, so the UI can explain itself. An attested override (body.phi_override) is
allowed but logged as its own outcome. Downstream only ever sees the categories.
""", findings=[
 ("good", "Fail-closed by construction, with the reasoning written down at the call site."),
 ("good", "Small (95 lines), single-purpose, has its own test file, and is configurable "
          "without a redeploy: PHI_GATE_URL, PHI_CLASSIFIER_URL, PHI_GATE_TIMEOUT_SEC."),
 ("watch", "A 4-second default timeout against a remote classifier sits on the synchronous "
           "request path. A slow classifier does not fail open, but it does add latency to "
           "every message before the user sees any acknowledgement."),
]),

"queue": dict(rating="green", depth="code", how="""
A Redis list used as a work queue. get_queue() returns a memory or redis adapter chosen by
QUEUE_TYPE, both behind a QueueAdapter ABC, so the same code runs in tests and production.
publish_request lpush'es the JSON payload; the worker pops from the other end.

Connection handling retries 12 times with a 5-second backoff — about a minute — before
giving up, which covers a Redis restart without dropping the process.
""", findings=[
 ("good", "A real abstraction rather than a Redis import scattered through the codebase: "
          "one ABC, two implementations, chosen by config."),
 ("watch", "No test file for the redis adapter specifically. The retry/backoff path is the "
           "part most likely to matter in an outage and the least likely to be exercised."),
 ("watch", "A plain Redis list gives no delivery guarantee. A worker that dies after popping "
           "and before publishing loses that turn; nothing re-queues it."),
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
"state_load": dict(rating="green", depth="code", how="""
The first thing that runs, on every turn, before the path is even chosen. It reads the
thread's stored state, works out what this message changes, applies that delta, saves it
back, and builds the context pack the rest of the pipeline reads.

Concretely: get_state(thread_id) → ThreadState → extract_state_delta(message, state) →
apply_delta → save_state_full. Continuity fields that are not part of the ThreadState
model (active_skill, last_failed_query, active_context) are carried across by hand so they
survive the round trip. With no thread_id it degrades to empty state rather than failing.

It does NOT check PHI — that happened at the API boundary, before the queue.
""", findings=[
 ("good", "Small, single-purpose, and the state transition is explicit: no patch merging, "
          "deltas applied through one function."),
 ("watch", "No test file, and it is the module every turn depends on for continuity."),
 ("watch", "Its docstring is one line, which is why this node was the first thing that read "
           "as empty when Ananth pressure-tested the diagram."),
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

Two execution modes, chosen per turn. MOBIUS_INTEGRATOR_MODE forces parallel or
sequential; if unset, MOBIUS_INTEGRATOR_PARALLEL_PCT samples a percentage of turns.
Default is sequential at 0% parallel — a deliberately conservative rollout.

On top of that sits dynamic enrichment (Task #76, a Chat Master ruling):
MOBIUS_DYNAMIC_ENRICHMENT_PCT samples per turn, and when react_loop's sufficiency check
says the answer is already good enough, Call A is SKIPPED and B/C are launched in the
background. Parallel path only; the sequential path is untouched by it.

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
 ("good", "Both rollouts are percentage-sampled and default to off, so a bad change is "
          "bounded to a slice of traffic rather than everyone."),
 ("good", "One swallow is explicitly reasoned — 'audit must never break the turn'."),
]),

"continuity": dict(rating="green", depth="surface", how="""
The 'do not flail' stage. Detects when to ask the user for help rather than keep trying
(user-as-leverage), when the user has dropped the thread, and when the attempt ceiling is
hit. Spec'd in docs/RELENTLESS_CONTINUITY_PLAN.md.
""", findings=[("good", "One of only four modules with telemetry of its own, and it has tests."),
               ("good", "105 lines for a real product behaviour.")]),
"react_loop": dict(rating="red", depth="code", how="""
The engine of the ReAct path: reason about what to do, call a tool, look at what came
back, go again. It replaces run_plan and the classic sub-question answering, does the core
synthesis, and can skip the integrator entirely via ctx.react_bypass_integrate.

It also emits nearly all of the pipeline's telemetry — thirteen distinct signals, on behalf
of itself and of the sub-modules it drives. Every critic signal comes from here, not from
critic.py.
""", findings=[
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
 ux="Prompt Composition Studio — frontend/prompts.html + app/api/admin_prompts.py "
    "(blocks, compositions, versions, monitoring)", how="""
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
 ("good", "There is a prompt-authoring surface: frontend/prompts.html backed by "
          "app/api/admin_prompts.py — blocks, compositions, versions and monitoring, with "
          "append-only versioning that never DELETEs or UPDATEs an existing block row. "
          "Prompts are editable and reversible without a deploy. I rated this module "
          "'invisible' before finding it; that was wrong."),
 ("bad", "1,365 lines and NO test file — including the parameter functions above, which set "
         "every turn's round and corpus-call budget. A wrong constant here silently changes "
         "cost and answer quality for every user and nothing fails."),
 ("watch", "Two prompt sources, code and composition, switched by MOBIUS_PROMPT_SOURCE. "
           "Whichever one is not in use drifts silently, and the trace does not record which "
           "source built the prompt for a given turn."),
]),

"tool_manifest": dict(rating="green", depth="code", how="""
The menu of tools the planner is shown. If a tool is not described here the planner cannot
choose it, which makes this file a control surface rather than a list.

It is mid-migration and says so: five tools are now registry-owned, their descriptions
living on SkillSpec.description and rendered through registry.manifest_text(), so adding a
skill is one file and no edit here. The rest are still described inline.
""", findings=[
 ("good", "694 lines, zero exception handlers, has a test file. Clean."),
 ("good", "The registry migration is documented in the module itself, including what it buys."),
 ("watch", "No config and no telemetry: you cannot tell from the trace what manifest the "
           "planner was shown on a given turn. The second of the two the Chat seat and I "
           "agreed are worth a real signal."),
]),
"capabilities": dict(rating="green", depth="surface", how="""
The single source of truth for what each agent path can answer, fed to the parser and
planner so questions get decomposed into sub-questions something can actually handle. Each
tool declares its capabilities explicitly, so when one fails ReAct can pick another.
""", findings=[("good", "Declared rather than inferred, and named as the single source of truth."),
               ("watch", "No test file, and four callers depend on its shape.")]),
"parsing": dict(rating="amber", depth="surface", how="""
Pulls a structured decision out of the reasoning model's free-text reply. Each round is
supposed to emit {thought, tool, inputs, is_complete}; in practice it arrives wrapped in
code fences, with trailing commas, or with unescaped characters. These are the pure,
context-free helpers that recover it.
""", findings=[("bad", "No test file. This is parsing hostile input from a model — precisely "
                       "the code that should be table-driven and heavily tested."),
               ("good", "Pure and context-free, so it is trivially testable once someone does.")]),
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
 ("bad", "The most interesting control loop in the product is an un-named `max_it += 1` "
         "inside an if-block in a 6,113-line file. It is invisible to search, cannot be "
         "unit-tested in isolation, and is the reason this node was missing from the schema "
         "until the Chat seat pointed at a line number."),
 ("bad", "The governor is OFF by default, so this never fires in production today. The "
         "static per-mode constants in prompts.py are the live policy. Real, working, "
         "quality-driven adaptation that nothing currently runs."),
 ("watch", "The contract table defines max_extension_rounds=1 for copilot, but the gate "
           "requires mode_label == 'agentic'. Copilot's extension budget is therefore "
           "defined and unreachable — either the gate or the table is wrong."),
 ("good", "The wall-clock guard (#107) is the right shape: it reserves 25s for final "
          "synthesis rather than letting an extension eat the answer."),
 ("good", "A completion-critic failure degrades to satisfied and falls through to the "
          "normal finalize path, with the reasoning written at the call site. A swallow I "
          "would defend — it fails toward answering rather than toward hanging."),
]),

"react_retry_guard": dict(rating="green", depth="surface", how="""
Stops the loop burning calls re-running a tool that already failed with the same inputs.
Written against a specific pathology seen in production, where the bandit or the model
picked the same dead path round after round.
""", findings=[("good", "Has telemetry of its own AND two test files — the best-covered "
                        "module in the pipeline."),
               ("good", "Written against an observed failure rather than a hypothetical.")]),
"curator_tools": dict(rating="amber", depth="surface", how="""
Two tools that let the assistant work on the corpus mid-conversation:
lookup_authoritative_sources queries RAG's /sources/search to enumerate URLs Mobius has
seen for a payer and topic, and ingest_url pulls one in through the import pipeline.
""", findings=[("watch", "Three swallows on calls that cross a service boundary into RAG. A "
                         "failed ingest that logs and continues looks identical to a "
                         "successful one from the conversation's point of view."),
               ("good", "Has a test file.")]),
"critic": dict(rating="amber", depth="code", how="""
Audits a draft answer against the sources it claims to rest on, before the user sees it.
The module's own docstring states the gap it fills: when the planner says is_complete and
produces a draft, nothing else checks whether the claims are grounded. Shape validators
only look at structure, and the post-run adjudicator runs after delivery.
""", findings=[("good", "Two test files, including one for call resilience."),
               ("good", "Gated by MOBIUS_REACT_CRITIC and MOBIUS_REACT_GROUNDEDNESS_HEURISTIC, "
                        "so it can be turned on or off without a redeploy."),
               ("watch", "Emits nothing itself; react_loop emits every critic signal. The Chat "
                         "seat's position, which I accept, is that this is correct by design — "
                         "react_loop owns the loop state and critic.py should not know it is "
                         "being observed.")]),
"governor": dict(rating="amber", depth="surface", how="""
The round policy: how many rounds this turn gets and what it is told to do next, driven by
a Product Promise contract instead of the round rules that used to be scattered through
react_loop. Built to a spec owned by another seat.
""", findings=[("watch", "Gated entirely behind MOBIUS_PRODUCT_PROMISE_ENABLED, default OFF. "
                         "It is 380 lines of unexercised policy — the risk is not that it "
                         "breaks, it is that it silently rots until someone turns it on."),
               ("good", "Has a test file, and replacing scattered rules with one contract is "
                        "the right direction.")]),
"feedback_signal": dict(rating="green", depth="surface", how="""
Decides whether this is the turn where the user gets asked for feedback, based on their own
cadence rather than a fixed interval. The decision is made here; the planner only chooses
whether to surface it.
""", findings=[("good", "77 lines, extracted specifically to keep react_loop under its LOC "
                        "ratchet — the extraction programme working as intended."),
               ("watch", "No test file.")]),
"context": dict(rating="amber", depth="surface", how="""
The object every stage reads and writes: correlation_id, thread_id, state, plan and stage
data. Stages mutate it in place; state moves only through explicit apply_delta transitions
rather than patch merging.
""", findings=[("bad", "Sixteen callers — by far the highest coupling in the pipeline. Every "
                       "stage depends on its shape, so any change is a wide blast radius."),
               ("good", "Zero exception handlers and explicit transitions: it is a data "
                        "structure, not a service, which is the right choice."),
               ("watch", "No test file of its own.")]),
"message_resolver": dict(rating="green", depth="surface", how="""
Works out what the user means by 'it'. Two problems solved together: resolving pronouns
against the previous turn ('search the web for it' after a failed query), and noticing when
the answer already exists in something we produced earlier ('how many NPIs have issues'
after a credentialing report) so it answers from that instead of searching again.
""", findings=[("good", "Zero exception handlers, has a test file, and solves a real "
                        "conversational failure rather than a hypothetical.")]),
"personalization": dict(rating="green", depth="surface", how="""
Splices the user's own preferences into the prompt and honours their autonomy setting.
Implements the chat side of a contract owned by mobius-user
(CONSUMER_RECIPE_PROFILE.md): splice_user_profile drops the rendered prompt between the
base system prompt and what follows; autonomy_for gates tools. A no-op for anyone who has
not onboarded.
""", findings=[("good", "Implements a written cross-service contract rather than an "
                        "assumption, and degrades to a no-op."),
               ("watch", "Seven callers and no test file.")]),
"active_context": dict(rating="green", depth="surface", how="""
Remembers which tool the conversation is currently inside, so a follow-up lands in the
right place instead of starting over. Replaced an older active_skill notion with something
generic to any tool.
""", findings=[("good", "60 lines, zero exception handlers."),
               ("watch", "No test file.")]),
"credentialing_envelope": dict(rating="green", depth="surface", how="""
Routing helpers for credentialing conversations — works out when a message is really about
roster reconciliation, and resolves the context that path needs. Shared with the ReAct
path so both routes agree on what counts.
""", findings=[("good", "Zero exception handlers, and sharing it prevents the two paths "
                        "disagreeing about routing."),
               ("watch", "No test file.")]),
"stages": dict(rating="green", depth="code", how="""
Eleven lines listing the canonical names of the seven classical pipeline stages:
state_load, classify, plan, clarify, resolve, integrate, publish. Every non-ReAct emit
event and trace entry is keyed on these strings. The ReAct path uses its own stage keys,
which are not in this list.
""", findings=[("good", "Constants in one place instead of string literals scattered through "
                        "the pipeline.")]),
"orchestrator": dict(rating="amber", depth="code", how="""
See run_pipeline above — this module is that function plus its helpers.
""", findings=[("bad", "1,902 lines and 31 log-and-continue handlers on the module that owns "
                       "the turn."),
               ("good", "The stage sequence is explicit enough that this diagram's flow was "
                        "parsed directly from it.")]),
}
