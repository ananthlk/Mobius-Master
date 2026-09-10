"""Refactor roadmap — the mapping from findings to phases.

This file is the ONLY hand-written part of the roadmap. Everything else
(counts, owner rollups, the tracker table, the page section) is generated
from docs/chat-schema-findings.md's source, so the roadmap cannot drift
from the bug log the way a hand-maintained plan would.

The rule that makes it a tracker rather than a snapshot: EVERY bug must
land in a phase or in OUT_OF_PROGRAM. gen_roadmap.py exits non-zero when
one does not, so a new finding cannot silently escape the roadmap — it
either gets sequenced or it gets an explicit reason for being outside.
"""

# Phase status. Hand-written because completion is a JUDGEMENT (the gate passed,
# the seats ruled), not something derivable from the findings file.
#
# ADDED 2026-09-09 on Chat Master's finding: gen_roadmap.py hardcoded
# "☐ not started" on EVERY phase, so the tracker claimed the program had not
# begun while P1, P2 and the first P3 node were done. Generated, therefore not
# fixable by hand-editing the output — the same "green because nobody looked"
# shape as the sign-off table, one file over, found the same day.
PHASE_STATUS = {
    "P1": "☑ **COMPLETE** 2026-09-08 — ~31,900 lines removed across P1.1/P1a/P1b/P1c/P1d, zero regressions",
    "P2": "☑ **COMPLETE** 2026-09-09 — P2a planner orphans, P2b latency telemetry deployed with spans bound to schema node keys",
    "P3": "◐ **IN PROGRESS** — `state_load` closed (StateUnavailable + first contract tag); `tool_manifest` opened 2026-09-09",
    "P4": "☐ not started",
    "P6": "☐ not started — blocked on P3 `tool_manifest` closing; (c) needs P3's Stage 0 funnel as its baseline",
    "P5": "☐ not started — and correctly so; Prompt Studio has deliberately not been asked to sign yet",
}

PHASES = [
    {"id": "P1", "name": "Delete", "owner": "chat", "ratifier": "DB seat, Tech Review",
     "gate": "lines removed; handler count down; ZERO invariant movement",
     "blocks": "P2, P4",
     "why": "FIRST, per Ananth 2026-09-08: clearing the dead code makes the rest of "
            "the list legible — you are no longer reasoning about code that will not "
            "exist. It can lead because its gate needs nothing we do not already "
            "emit: I1-I7 are all computable from today's telemetry. If any invariant "
            "moves, the deletion was not dead code.\n\nThe cost of leading with it, "
            "stated plainly: this phase CANNOT CLAIM A LATENCY WIN, because the "
            "latency baseline does not exist yet. Deleting unreachable code should "
            "not move latency at all — that is the argument for it being safe to go "
            "first, and it is also why it forfeits the claim."},
    {"id": "P2", "name": "Make absent producers detectable", "owner": "chat + Eval",
     "gate": "every segment timed AND each timed segment's attribution verified "
             "against a known-external call — an LLM or HTTP boundary crossed inside "
             "a segment must appear as such, not as our processing; invariants I1-I7 "
             "computable from emitted telemetry alone, with no hand-written DB join",
     "blocks": "P3, P4, P5",
     "why": "REFRAMED 2026-09-09 on Chat Master's argument, better than my original 'instrument the gaps'. Every finding this program has produced is one shape: nothing here fails loudly when a PRODUCER disappears, because every consumer has a plausible default. master_objective degraded four readers to \"resolved\" for five months; variant_id made a refresh match nothing for a month; make_tool_failed has no caller so tool_failed is structurally impossible while tool_invoked and tool_completed emit normally; CallManager is wired in docstrings only. Framed as instrumenting the known gaps this phase fixes twelve instances; framed as making an absent producer detectable it fixes the class.\n\nSECOND in order, per Ananth: 'add latency across, this way we can measure when we are done we should be better and faster.' Latency lands here and is what makes 'faster' provable — but as an instance of the rule, not the point of the phase.\n\n"
            "are done we should be better and faster.' This is the phase that makes "
            "'faster' a provable claim rather than an impression — 19 of 25 modules "
            "are untimed today. It also closes the decision-visibility gaps: the "
            "governor has zero logger calls, keep is never persisted, 116 of 187 "
            "knobs run on invisible defaults.\n\nBASELINE RULE: the latency numbers "
            "captured at the END of this phase are the reference every later phase "
            "measures against. P1 sits before that line and is measured on "
            "invariants only.\n\nGATE AMENDED 2026-09-09, Chat Master's finding, "
            "from having executed it rather than read it. The gate used to read only "
            "'every segment timed'. They met it and the numbers were still wrong "
            "three times in one day: a 30s RAG call read as 30s of OUR processing "
            "(external wait, no span); 11.5s of integrator MODEL time read as "
            "integrate's own code (worker-thread calls invisible to the trace); "
            "connection-acquire time read as QUERY time (a per-target counter cannot "
            "see the cost of REACHING the target). Every one passed 'segment timed'. "
            "TIMED IS NOT ATTRIBUTED — and a timed segment that misattributes is "
            "WORSE than an untimed one, because it sends someone to optimise a module "
            "that is idle. That is not hypothetical: it is what their own integrate "
            "finding did to me before they retracted it."},
    {"id": "P3", "name": "One decision point", "owner": "chat", "ratifier": "Tech Review",
     "gate": "modules that can grant an extension round: 2 -> 1; audited "
             "budget-exhausted turns: 0 -> the rule's target",
     "blocks": "P5",
     "why": "Do not build a UX over a policy that lives in two places. This is the "
            "one phase where I4/I5 move BY DESIGN — the delta must be predicted "
            "before the cut and compared after."},
    {"id": "P4", "name": "Split", "owner": "chat", "ratifier": "Tech Review + Eval",
     "gate": "every extracted unit has a test file; total lines roughly flat",
     "blocks": None,
     "why": "Highest blast radius. Only after the gate has worked three times."},
    {"id": "P5", "name": "Config UX", "owner": "chat + Prompt Studio", "ratifier": "Tech Review",
     "gate": "max_rounds / max_extension_rounds / soft_target_s editable without a "
             "deploy; confidence_bar NOT shipped",
     "blocks": None,
     "why": "Lands 'change model speed and latency without a deploy'.\n\nSCOPE "
            "NARROWED by the LLM Agent's ruling: only _MODE_DEFAULTS' three numeric "
            "fields move, into a NEW table keyed by chat_mode cloning ConfigManager's "
            "pattern — NOT into llm_configs, which is keyed by module_key and shaped "
            "for LLM-call knobs. Global scope, matching migration 050's ratified "
            "precedent. Both selector maps stay in code: they are composition "
            "semantics, not tuning knobs.\n\nconfidence_bar is EXCLUDED ENTIRELY, "
            "which is stronger than the bound I asked for. A value that can disable "
            "the safety floor needs a second sign-off from whoever owns the Product "
            "Promise contract before it is exposed at all — not a clamp a config UI "
            "enforces on its own."},
    {"id": "P6", "name": "Tool selection", "owner": "chat + Prompt Studio",
     "ratifier": "Tech Review + Eval",
     "gate": "manifest editable without a deploy; tools offered per turn: ALL -> a "
             "retrieved subset; prompt tokens spent on the manifest: measured before, "
             "lower after; tool-selection accuracy NOT worse than the P3 baseline; "
             "and the retrieval decision is INSPECTABLE — given a situation, the UX "
             "shows which tools were selected and why, and a real past turn can be "
             "asked the same question",
     "blocks": None,
     "why": "SEQUENCED, NOT OUT OF SCOPE — Ananth, 2026-09-09, correcting my draft, "
            "which had parked these as 'enhancements'. They are real work with a real "
            "gate and they get a phase.\n\nThree parts, in dependency order:\n"
            "(a) A UX for the tool and capabilities manifest, WRITTEN TO PERSISTENCE, "
            "so changing a tool does not need a deploy. Today the catalogue is code "
            "(app/pipeline/tool_manifest.py, 694 lines). Half the substrate already "
            "exists: user_tool_subscriptions (migration 035) already persists per-user "
            "policy and get_allowed_tools_for_user already reads it at turn start. The "
            "gap is the CATALOGUE being in code, not the POLICY. Shares P5's control "
            "plane rather than growing a second one.\n"
            "(b) Access provisioning — WHO may use a tool. Adjacent to (a) and a "
            "different question: (a) is what exists, (b) is who may use it. The "
            "per-user table is a SUBSCRIPTION model, not an AUTHORIZATION model; "
            "conflating them is the mistake to avoid early, while it is still cheap.\n"
            "(c) RETRIEVE the tools for a turn instead of offering all of them. "
            "Ananth's mechanism, 2026-09-09: 'a simple even vector search for tool "
            "will be helpful or some kind of search — this will cut short on tokens "
            "and make a real good determination and make the latency also faster.' "
            "Three effects, and they are worth separating because they are measured "
            "differently: FEWER TOKENS (the manifest is prompt text on every turn — "
            "count it, it is a direct cost), BETTER SELECTION (a short relevant list "
            "beats a long one; this is the P3 bug's own failure mode, so P3's funnel "
            "is the before-measurement), and LOWER LATENCY (a consequence of the first "
            "two, not an independent claim — do not claim it separately).\n\n"
            "WHY IT FOLLOWS P3 AND CANNOT LEAD IT: retrieval changes WHICH tools are "
            "offered. If it ships while selection is still sporadic, a miss is "
            "unattributable — retrieval did not surface the tool, or the tool was "
            "surfaced and not called, and we are back to the exact ambiguity P3 exists "
            "to resolve. P3's Stage 0 funnel is also (c)'s training signal and its "
            "baseline. Ananth: 'get current to work then add these features.'\n\n"
            "EMBEDDING NOTE: pgvector is the standard; do not introduce a second "
            "vector store for a catalogue of this size. A tool catalogue is small "
            "enough that exact search over the whole set is viable — measure before "
            "reaching for an index.\n\nTHE RETRIEVAL DECISION IS PART OF THE UX, "
            "NOT A SEPARATE FEATURE — Ananth, 2026-09-09: 'that should be part of the "
            "ux build given a situation what tools are selected.' The manifest UX is "
            "not only an editor; it answers, for a given query, WHICH TOOLS THIS TURN "
            "GETS AND WHY — the retrieved set, the scores, and what fell below the "
            "cut. This is a correctness requirement. A retrieval step that silently "
            "narrows the tool list is A PRODUCER WHOSE DECISION NOTHING RECORDS: when "
            "the model then says it cannot do something, nobody can tell whether the "
            "tool was withheld or the model failed to call it — which is exactly the "
            "ambiguity P3 exists to remove, reintroduced one layer earlier, right "
            "after we paid to remove it. So the per-turn retrieval decision must be "
            "PERSISTED, not merely rendered: the UX previews it for a hypothetical "
            "query, the turn record answers it for a real one. A preview that reads "
            "live code while the log keeps nothing is a read-back of the wrong "
            "artifact.\n\nTWO REPRESENTATIONS, NOT ONE — Ananth, 2026-09-09: 'it "
            "allows a tool to fully represent itself, for selection, and a narrow set "
            "of short react briefs travel with it.' This is the design, and it is what "
            "makes the token claim and the accuracy claim compatible instead of in "
            "tension. A tool gets a SELECTION REPRESENTATION, read only by the "
            "retriever, matched against but NEVER SPENT AS PROMPT TOKENS — so it can "
            "be long and complete: when to use it and when not, worked examples, "
            "failure modes, the phrasings users actually type. And a REACT BRIEF, "
            "short, which is the only part that travels into the prompt. Today there "
            "is ONE representation doing both jobs, which is why it is bad at both: "
            "every word that helps the model choose is paid for on every turn, so the "
            "description gets trimmed for cost and selection gets worse. 694 lines of "
            "that compromise. Splitting them removes the tension outright — which is "
            "also why fewer tokens and better determination are ONE structural change "
            "with two effects, not two wins to be counted separately. Two "
            "consequences: the pair must be authored TOGETHER and stay consistent (a "
            "rich selection text promising what the brief does not describe gets a "
            "tool retrieved and then not called — P3's funnel with a new cause), so "
            "the UX edits both side by side; and RETRIEVAL QUALITY BECOMES TESTABLE "
            "ON ITS OWN, no LLM in the loop — given a query, does the right tool come "
            "back? Fixture-and-assert, the cheapest test in this program.\n\n"
            "THE SECOND-ORDER EFFECT IS THE REAL PRIZE (Ananth: 'this will allow for "
            "better options'). Today a tool's cost is paid by EVERY turn, including "
            "every turn that will never use it — so each new tool taxes the whole "
            "system and the rational design is FEW, BROAD tools. That is a constraint "
            "imposed by the prompt budget, not by the problem. Retrieval inverts it: "
            "once a tool costs ~nothing on turns that do not retrieve it, MANY NARROW, "
            "SPECIFIC, WELL-DESCRIBED TOOLS BEAT A FEW GENERAL ONES. A tool serving 3% "
            "of turns is not worth its prompt weight today and is obviously worth "
            "building after. The token saving is a one-time win; the change in what is "
            "WORTH BUILDING compounds — and it makes the catalogue somewhere product "
            "knowledge accumulates instead of somewhere additions cost. CAVEAT, so "
            "this is not read as a licence to proliferate: more tools means more ways "
            "for retrieval to be wrong, and a wrong retrieval is INVISIBLE TO THE "
            "MODEL — it cannot call what it was never offered. Which is why the "
            "inspector and the persisted per-turn decision are gate items, not "
            "nice-to-haves. The economics only improve while selection stays honest "
            "and checkable."},
]

# (phase, node or None for any, distinctive substring). First match wins.
RULES = [
    # ── P2 — instrument: latency + the decision-visibility gaps ───────────
    ("P2", "governor",      "STRUCTURALLY UNOBSERVABLE"),
    ("P2", "react_loop",    "CURATION DECISION IS NEVER PERSISTED"),
    ("P2", "orchestrator",  "LATENCY MEASUREMENT"),
    ("P2", "governor",      "116 OF 187 CONFIG KNOBS"),
    ("P2", "governor",      "blueprint_snapshot is 0 of 2,744"),
    ("P2", "emit_envelope", "A STALE TEST WAS ASSERTING A VULNERABILITY"),
    ("P2", "emit_envelope", "FIVE OF THE ELEVEN P1b FAILURES DEGRADED SILENTLY"),
    ("P2", "emit_envelope", "THE DEPLOY SCRIPT PRINTS A FALSE REASSURANCE"),
    ("P2", "emit_envelope", "FAILURE-PATH EMITTERS WERE BUILT, TESTED, AND NEVER WIRED"),
    ("P2", "emit_envelope", "184 UNWIRED CANDIDATES"),
    ("P2", "emit_envelope", "THE CONFIRMED ROSTER"),
    ("P1", "run_pipeline", "MASTER_OBJECTIVE WAS RETIRED INCOMPLETELY"),
    ("P1", "run_pipeline",  "26 TESTS ARE ALREADY FAILING"),
    ("P1", "run_pipeline", "THE CREDENTIALING ROUTER WOULD SURVIVE LOSING ITS IMPLEMENTATION"),
    ("P4", "model_registry", "THE TEST SUITE MUTATES THE BANDIT'S LIVE STATE"),
    ("P2", "model_registry", "THE CIRCUIT BREAKER DID NOT PULL A PROVIDER"),
    ("P2", "model_registry", "THE BANDIT HAS NO SURFACE"),
    ("P3", "tool_manifest", "TOOL SELECTION IS SPORADIC, AND THE MODEL NARRATES"),
    ("P3", "state_load", "ROOT CAUSE OF THE PER-READ OVERHEAD"),
    ("P3", "state_load", "state_load IS 1.2s AT p50"),
    ("P2", "react_loop", "_rich_evidence IS AN UNRECORDED BRANCH"),
    ("P2", "PHI gate", "'blocked_indeterminate' IS AMBIGUOUS BY CONSTRUCTION"),
    ("P3", "PHI gate", "THE GATE FAILS OPEN ON MISCONFIGURATION"),
    ("P3", "PHI gate", "THERE IS NO SUCH THING AS 'THE PHI GATE TIMEOUT'"),
    ("P2", "llm_manager", "45% OF llm_calls ROWS CANNOT BE JOINED"),
    ("P1", "run_pipeline", "~25 FRONTEND FETCHES ARE 404ing TODAY"),
    ("P1", "run_pipeline", "DELETING THE CREDENTIALING PLANNER PATH WOULD SILENTLY BREAK"),
    ("P2", "state_load",    "state_version is WRITE-ONLY"),
    ("P2", "active_context", "writes two keys into the turn record"),
    ("P2", "plan",          "parse-failure fallback is invisible"),
    ("P2", "curator_tools", "DOES IT DO ANYTHING"),
    ("P2", "feedback_signal", "inputs it cannot cheaply obtain"),

    # ── P1 — delete (leads) ───────────────────────────────────────────────
    ("P1", "run_pipeline",  "CLASSIC PATH IS DEAD"),
    ("P1", "run_pipeline",  "CREDENTIALING SURFACE"),
    ("P1", "jurisdiction",  "DEAD CODE ON THE LIVE PATH"),
    ("P1", "jurisdiction",  "jurisdiction_change is decided by regex"),
    ("P1", "clarification", "FOUR CLARIFY MECHANISMS"),

    # ── P3 — one decision point ───────────────────────────────────────────
    ("P3", "governor",      "TWO EXTENSION POLICIES"),
    ("P3", "completion_extension_gate", "un-named"),
    ("P3", "completion_extension_gate", "CONFIRMED BUG"),
    ("P3", "critic",        "TURNS THAT MOST NEED AUDITING"),
    ("P3", "critic",        "NO STATED RULE"),
    ("P3", "critic",        "does NOT disable the critic"),
    ("P3", "run_pipeline",  "MASTER_OBJECTIVE GAP"),
    ("P3", "continuity",    "CANNOT DO ANYTHING"),
    ("P3", "clarification", "WRITTEN BY ANOTHER MODULE"),
    ("P3", "integrate",     "NEVER REACH THE INTEGRATOR"),
    ("P3", "governor",      "default-off flag"),

    # ── P4 — split ────────────────────────────────────────────────────────
    ("P4", "react_loop",    "REFACTOR react_loop"),
    ("P4", "react_loop",    "6,113 lines"),
    ("P4", "react_loop",    "Twenty-one log-and-continue"),
    ("P4", "react_loop",    "react_loop"),
    ("P4", "integrate",     "Three distinct responsibilities"),
    ("P4", "integrate",     "29 exception handlers"),
    ("P4", "orchestrator",  "1,902 lines and 31 log-and-continue"),
    ("P4", "run_pipeline",  "1,902 lines with 42 exception handlers"),
    ("P4", "prompts",       "SEPARATE THE PARAMETER PLANNER"),
    ("P4", "prompts",       "1,365 lines and NO test file"),
    ("P4", "parsing",       "NO TEST FILE"),
    ("P4", "classify",      "24-line wrapper"),
    ("P4", "context",       "Sixteen callers"),
    ("P4", "context",       "FIELD DOCSTRINGS"),
    ("P4", "message_resolver", "hand-maintained regex"),

    # ── P5 — config UX ────────────────────────────────────────────────────
    ("P5", "governor",      "IT IS A PYTHON DICT"),
    ("P3", "tool_manifest", "A TOOL RETURNED A REAL PLAYBOOK AND CHAT REPORTED THERE WAS NONE"),
    ("P3", "tool_manifest", "SPORADIC TOOL SELECTION — FOLDED INTO THE TOOLS REFACTOR"),
    ("P5", "tool_manifest", "MOVE THE MANIFEST OUT OF CODE"),
    ("P5", "tool_manifest", "CONTEXT-SPECIFIC TOOL SELECTION"),
    ("P5", "prompts",       "TWO PROMPTS EXIST IN BOTH PLACES"),
    ("P5", "prompts",       "MOBIUS_PROMPT_SOURCE=composition"),
]

# Explicitly outside the refactor. Each needs a REASON, not just an exclusion —
# "a filter that makes an answer look complete" is the failure mode this guards.
# Lessons, not defects. A generalisation filed as a bug CAN NEVER BE CLOSED — it
# sits ☐ forever, inflates its node's count, and makes the tracker's completion
# metric unreachable by construction. Chat Master's finding, 2026-09-09, and they
# are right: these are theirs, they are worth keeping, and a table with checkboxes
# is the wrong container. Rendered as principles the roadmap links, not as rows.
PRINCIPLES = [
    ("emit_envelope", "AN IMPORT EDGE IS NOT A CONSUMPTION EDGE"),
    ("emit_envelope", "A NAME-BASED SEARCH ANSWERS"),
    ("emit_envelope", "A READ-BACK OF THE WRONG ARTIFACT"),
    ("emit_envelope", "AN UN-INSTRUMENTED EXTERNAL WAIT"),
]

OUT_OF_PROGRAM = [
    ("POST /chat", "CHAT_ENV=prod",       "security posture", "needs Ananth's authorisation + staging; no clean unauthenticated POST sent"),
    ("POST /chat", "HIPAA AUDIT WRITE",   "compliance decision", "fail-open write under a fail-closed gate; posture decision pending"),
    ("PHI gate",   "AUDIT WRITE IS FAIL-OPEN", "compliance decision", "same item, second node"),
    ("PHI gate",   "TWO IMPLEMENTATIONS", "own workstream", "feedback-text gate writes no audit row; compliance, not structure"),
    ("queue",      "No delivery guarantee", "own workstream", "durability; not reachable by a chat-internal refactor"),
    ("queue",      "no TTL and no depth alerting", "own workstream", "same"),
    ("queue",      "STRUCTURE RULING (Technical Review", "own workstream", "same"),
    ("queue",      "what pushes it past",  "own workstream", "same"),
    ("state_load", "TRANSIENT READ FAILURE", "own workstream", "state durability; own fix, own test"),
    ("state_load", "NOTHING CAN DETECT IT", "own workstream", "same"),
    ("state_load", "THE FIX IS LOCAL",     "own workstream", "same"),
    ("state_load", "NO query guards",      "DB seat",        "cross-node, storage governance"),
    ("POST /chat", "NO retention or cleanup path", "DB seat",  "storage governance"),
    ("POST /chat", "three FKs",            "DB seat",        "FK ratification, awaiting sign-off"),
    ("POST /chat", "FOURTH FK",            "DB seat",        "same"),
    ("POST /chat", "db_execute is written as an MCP call", "DB seat", "MCP hop; runtime lens already corrected it"),
    ("POST /chat", "MCP hop DOES NOT HAPPEN", "DB seat",     "same"),
    ("POST /chat", "ensure_thread swallows", "own workstream", "Tech Review ruled the swallow is not the defect"),
    ("POST /chat", "STRUCTURE RULING on ensure_thread", "own workstream", "same"),
    ("POST /chat", "API→worker contract is untyped", "own workstream", "entry contract, not chat-internal"),
    ("POST /chat", "NODE 1 IS RED",        "rating",         "a rating ruling, not a unit of work"),
    ("POST /chat", "STRUCTURE RULING on the HIPAA audit", "compliance decision", "tracked as its own item by Tech Review"),
    ("POST /chat", "CORRECTION",           "correction",     "a correction to my own text, not work"),
    ("curator_tools", "LOOK INTO RAG'S WRITE SURFACE", "payor-policy", "unauthenticated corpus write in mobius-rag; 1 of 79 routes audited"),
    ("curator_tools", "ADMIN KEY IS NOT CHECKED", "payor-policy", "same"),
    ("POST /chat", "JWTs ARE IN THE REQUEST LOGS", "security posture", "access tokens written to Cloud Run request logs; needs its own investigation, not a refactor phase"),
    ("llm_manager", "LIVE MODEL LATENCY DEGRADATION", "LLM Agent", "upstream Vertex latency; a latency breaker doing its job, not a chat defect"),
    ("llm_manager", "WHY THE 'ema' NEVER GETS RE-GROUNDED", "LLM Agent", "fixed in de43bd2, pushed not deployed; model routing is theirs"),
    ("personalization", "PASS-THROUGH FOR PREFERENCES", "user-manager", "chat cannot act on preferences it forwards"),
    ("personalization", "DISPUTED ASSIGNMENT", "user-manager", "assignment itself is disputed"),
]
