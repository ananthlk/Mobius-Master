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
     "gate": "every segment timed; invariants I1-I7 computable from emitted "
             "telemetry alone, with no hand-written DB join",
     "blocks": "P3, P4, P5",
     "why": "REFRAMED 2026-09-09 on Chat Master's argument, better than my original 'instrument the gaps'. Every finding this program has produced is one shape: nothing here fails loudly when a PRODUCER disappears, because every consumer has a plausible default. master_objective degraded four readers to \"resolved\" for five months; variant_id made a refresh match nothing for a month; make_tool_failed has no caller so tool_failed is structurally impossible while tool_invoked and tool_completed emit normally; CallManager is wired in docstrings only. Framed as instrumenting the known gaps this phase fixes twelve instances; framed as making an absent producer detectable it fixes the class.\n\nSECOND in order, per Ananth: 'add latency across, this way we can measure when we are done we should be better and faster.' Latency lands here and is what makes 'faster' provable — but as an instance of the rule, not the point of the phase.\n\n"
            "are done we should be better and faster.' This is the phase that makes "
            "'faster' a provable claim rather than an impression — 19 of 25 modules "
            "are untimed today. It also closes the decision-visibility gaps: the "
            "governor has zero logger calls, keep is never persisted, 116 of 187 "
            "knobs run on invisible defaults.\n\nBASELINE RULE: the latency numbers "
            "captured at the END of this phase are the reference every later phase "
            "measures against. P1 sits before that line and is measured on "
            "invariants only."},
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
    ("P1", "run_pipeline",  "26 TESTS ARE ALREADY FAILING"),
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
    ("P5", "tool_manifest", "MOVE THE MANIFEST OUT OF CODE"),
    ("P5", "tool_manifest", "CONTEXT-SPECIFIC TOOL SELECTION"),
    ("P5", "prompts",       "TWO PROMPTS EXIST IN BOTH PLACES"),
    ("P5", "prompts",       "MOBIUS_PROMPT_SOURCE=composition"),
]

# Explicitly outside the refactor. Each needs a REASON, not just an exclusion —
# "a filter that makes an answer look complete" is the failure mode this guards.
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
    ("emit_envelope", "JWTs ARE IN THE REQUEST LOGS", "security posture", "access tokens written to Cloud Run request logs; needs its own investigation, not a refactor phase"),
    ("llm_manager", "LIVE MODEL LATENCY DEGRADATION", "LLM Agent", "upstream Vertex latency; a latency breaker doing its job, not a chat defect"),
    ("llm_manager", "WHY THE 'ema' NEVER GETS RE-GROUNDED", "LLM Agent", "fixed in de43bd2, pushed not deployed; model routing is theirs"),
    ("personalization", "PASS-THROUGH FOR PREFERENCES", "user-manager", "chat cannot act on preferences it forwards"),
    ("personalization", "DISPUTED ASSIGNMENT", "user-manager", "assignment itself is disputed"),
]
