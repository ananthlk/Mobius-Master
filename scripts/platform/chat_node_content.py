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
"classify": dict(rating="green", depth="surface", how="""
Twenty-four lines. Decides whether the message is a new question or the user filling in a
blank the system asked about (slot_fill), and computes the effective message to work from.
That distinction changes routing downstream, which is why it runs this early.
""", findings=[("good", "Small enough to be obviously correct."),
               ("watch", "No test file, though the branch it sets is read by later stages.")]),
"plan": dict(rating="amber", depth="surface", how="""
Parses the message into a plan: the refined query, and a blueprint of the sub-questions
that would answer it. Only runs on the classic path — the ReAct loop plans as it goes.
""", findings=[("watch", "No test file for a stage that decides what the rest of the classic "
                         "path will try to answer.")]),
"clarify": dict(rating="green", depth="surface", how="""
Catches the turns that cannot be answered yet: a missing jurisdiction, a route clash, or a
query that needs refining. Sets resolvable and the messages to send back. This is what
turns a bad answer into a question.
""", findings=[("good", "Has tests, including one specifically for ReAct clarify questions."),
               ("good", "Asking rather than guessing is a deliberate product stance and it "
                        "lives in one small module.")]),
"resolve": dict(rating="amber", depth="surface", how="""
The classic path's dispatcher. Routes each sub-question to the agent that can answer it,
collects the answers, and walks a fallback cascade when the first choice cannot.
""", findings=[("watch", "595 lines with a fallback cascade and only indirect test coverage."),
               ("watch", "One swallow on a dispatch path — worth checking whether a failed "
                         "agent call is distinguishable from one that returned nothing.")]),
"integrate": dict(rating="amber", depth="code", how="""
Turns reasoning and tool output into the answer card the user actually sees: formats the
response, builds the payload, decides how it is presented.

It runs on BOTH paths. On the ReAct path react_loop does the core synthesis and this
module handles the enrichment that follows — unless react_loop set
ctx.react_bypass_integrate, in which case the ReAct answer is published directly and this
is skipped entirely.
""", findings=[
 ("bad", "1,887 lines, 29 exception handlers, 20 of them log-and-continue, and the only test "
         "named for it covers the fallback path. This is the module that decides what the "
         "user sees, and it is the least well covered of the large ones."),
 ("good", "One swallow is explicitly reasoned — 'audit must never break the turn' — which is "
          "the right call, written down."),
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
"prompts": dict(rating="amber", depth="surface", how="""
Everything the reasoning model actually reads. Mode labels and max-round constants the
planner uses to decide how much leeway it has, the system prompt builder, and the
per-round reasoning context that tells the model where the turn has got to. Extracted from
react_loop to keep the text-generation surface separate from tool dispatch.
""", findings=[
 ("bad", "1,365 lines and NO test file. This is the text that determines model behaviour; a "
         "silent change here moves every answer and nothing fails."),
 ("good", "The separation from tool dispatch is the right cut, and five callers use it."),
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
