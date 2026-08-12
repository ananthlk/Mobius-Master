# SHAPE Gate — Simulation & Sign-Off Tracker

**Purpose:** track real simulated end-to-end outputs (not abstract spec review) against the actual `shape_gate` emit + narrative layer, with per-agent sign-off status and telemetry per test case. This is the live scoreboard for the gate module's Eval test.

**Method:** each test case runs the real `run_gate()` + `narrate()` against the live DB, producing the actual emit JSON + user-facing narrative + telemetry. Agents review the REAL OUTPUT, not the design doc, and sign off per case.

---

## Test cases run (2026-07-22, all 6 contours covered) — FINAL FORMAT

**Design change (per Ananth):** abandoned trying to synthesize one "best topic phrase" (two rounds of guessing wrong — first by match-order, then by length — a genuinely hard salience problem). Replaced with a transparent **J/D/P path statement**: state what was actually found on each axis, then the resulting posture. Sidesteps the guessing problem entirely and is more honest about what the gate actually knows.

| # | Query | Contour | gate_ms | Narrative |
|---|---|---|---|---|
| 1 | "Eligibility for Medicaid" | UNDERSPECIFIED (explore_siblings, 80) | 3908 | *"I found you are asking about **eligibility**, for **medicaid**. Checked — this domain has 80 more specific facets and nothing narrowed which one you mean, so I'll explore the likely ones myself rather than guess or ask right away."* |
| 2 | "What is the timely filing deadline for Sunshine Health FL Medicaid claims?" | EXACT | 1571 | *"I found you are asking about **claims, timely filing**, for **florida, medicaid, sunshine health**. Checked, and I have exact material for this — 3249 document(s) cover it directly."* |
| 3 | "How do I get credentialed with Sunshine Health?" | UNDERSPECIFIED (missing_domain) | 345 | *"I found you are asking for **sunshine health**. Checked, but I don't know the specific topic within this area — too broad to answer confidently without it. I may need to ask a follow-up."* |
| 4 | "What's the weather forecast for tomorrow?" | OUT_OF_SCOPE | 20 | *"I understood your question, but it doesn't match anything in scope here — not something I'm set up to answer."* |
| 5 | "What is the prior authorization process in Clarendon, AR?" | VICINITY | 524 | *"I found you are asking about **prior authorization**, for **clarendon ar**. Checked, and I have material in this area (1696 documents), but nothing covers this exact combination — I'll need to piece it together from related content."* |
| 6 | "asdkfjqwoeiru" | UNCLEAR | 16 | *"I wasn't able to make sense of that question — could you rephrase it?"* |

CORPUS_GAP not included — no clean natural-language trigger exists (documented gate.py limitation); narrative template exists and is unit-testable but not exercised end-to-end here.

**No open narrative bugs.** The J/D/P path format resolved both prior rounds' salience issues by construction (states everything found, on the correct axis, no single-phrase pick required).

**Raw output artifacts:** `narrate.py` (final), reproducible against live DB via `run_gate()` + `narrate()`.

---

## Per-agent sign-off status — CORRECTED 2026-07-22 (TECH's review caught this table was stale)

This table went un-updated after the actual sign-offs landed — TECH's structural review flagged the mismatch between this doc (claiming Chat/UX/Eval "Pending") and the real state. Corrected below.

| Agent | Reviewed real output? | Sign-off | Notes |
|---|---|---|---|
| Chat | Yes — reviewed spec + integration questions | ✅ Signed off | No integration requirements now (backend-only until 12-field contract exists); flagged 2 message templates needed later (out_of_scope redirect vs. unclear rephrase-ask) |
| UX | Yes — TWO rounds | ✅ Signed off | Round 1: emit schema (`shape_gate` key, avoided `gate` collision). Round 2 (after narrative layer built): tone/voice passes brand check, `narrate()`→`thinking_trace`, `narrate_full()`→Diagnostics-only, one wording fix applied, PHI flag raised (see below) |
| Eval | Yes — bank + scenarios, independently re-verified twice | ✅ Signed off | Co-authored `queries_gate_contours.yaml` v2 (26 queries), caught a stale-YAML lexicon-count error I'd made, re-ran everything independently both times rather than trusting reports |
| DB | Yes — query pattern + isolated latency re-measurement | ✅ Signed off | Root cause found: reported 630-1500ms was dev-proxy tunnel artifact; true server-side execution ≈52ms. Independently re-verified against the GIN-index migration's own benchmark. |
| Curation | Yes — 2 D-tag gaps + YAML staleness | ✅ Signed off | Gaps logged in tag-selectivity-loop backlog; unrelated stale `policy_lexicon.yaml` file investigated and deleted (root cause: their `publish_lexicon()` bypasses the RAG export path) |
| TECH | Yes — full independent structural review | ⏳ **In progress** | First pass (2026-07-22) found 2 real gaps: (1) this tracker was stale — now fixed; (2) Eval's 5 drafted pytest classes were never actually landed in `test_shape_gate.py` — now fixed, 33/33 pass. Also strengthened the PHI recommendation for `narrate_full()` (never persist, not just "redact before persisting" — applied). Re-requesting final sign-off with these fixes. |

**PHI note (strengthened per TECH):** `narrate_full()` must never be written to persisted storage (not even redacted) — compute on-demand for Diagnostics only. Applied in `narrate.py`'s docstring and `gate-emit-schema-spec.md` §7.

---

## Telemetry tracking (running log — append per test round)

| Date | Test round | Cases run | gate_ms range (min–max) | Narrative bugs found | Fixed? |
|---|---|---|---|---|---|
| 2026-07-22 | 1 (first pass) | 4 | 16–4265 | 1 (`_topic_phrase` salience) | Yes — replaced with J/D/P path format |
| 2026-07-22 | 2 (contour bank v2) | 26 | varies, see DB latency finding | 0 | — |
| 2026-07-22 | 3 (TECH review + fixes) | 33 unit + 6 integration | — | 0 (found: stale tracker, missing Eval unit tests — both process gaps, not narrative bugs) | Yes — tracker corrected, tests landed |

---

**Next:** awaiting TECH's re-review of the 2 fixes (tracker corrected, Eval's tests landed). Once confirmed, Shape Gate closes and Retriever moves to Reformat or Pool.
