# SHAPE / Slots Module Spec (Step 1d) — v1 Kickoff

**Status:** KICKOFF — 3 open architecture questions resolved, module-contract drafted. Ready for Ananth review before build.

**Owner:** Shape:Slots Agent (4th sibling under Shape: Gate → Reformat → Structure → Slots)

**Timeline:** Unblocks Fillers (Step 3) → Router (Step 4). Gate-critical path.

---

## 1. The Gap (Why This Module Exists)

`StructureResult` has NO slot fields. Fillers blocks on a real slot model. Ananth's 2026-07-23 call: build it as a proper Shape sub-step, same rigor as Gate/Reformat/Structure, not a shortcut inside Fillers.

**Where Slots sits:**
```
Shape: [Gate→Reformat→Structure→Slots] → Pool (parallel, doesn't depend on Slots)
                              ↓
                           Fillers (blocked on Slots) → Router → Synthesis → Contract
```

---

## 2. Input Contract

**Primary input:** `StructureResult` (to be updated per Option A decision):
- `query: str`
- `rewritten_queries: list[str]` (passthrough from Reformat)
- `posture: ReformatPosture` (PRECISE / FAN_OUT / CLARIFY / RELY_ON_EXTERNAL / DECLINE / CLARIFY_REPHRASE)
- `fanout_themes: list[FanoutTheme]` (FAN_OUT only, len ≤ 4) — **NEW, passed through from ReformatResult**
- `resource_posture: ResourcePosture` (breadth / confidence_bar / max_attempts / speed_budget)
- `reason: str`
- `structure_ms: int`

---

## 3. Output Contract (Slots → Fillers Input)

**`AnswerSlots` dataclass (new, to be defined):**

```python
@dataclass
class AnswerSlot:
    """One slot in the answer structure."""
    slot_id: str              # "direct_answer" | "fanout_0" | "external_context" | etc.
    slot_semantics: str       # "direct_answer" | "thematic_exploration" | "external_context"
    capacity: int             # target chunk count for this slot (from resource_posture.breadth)
    rewritten_query: str = "" # FAN_OUT only: which rewritten_query this slot corresponds to
    required: bool = True     # must this slot be filled, or is it optional fallback?
    priority: int = 0         # ranking hint for Fillers' assignment algorithm (0=highest)

@dataclass
class AnswerShapeResult:
    """Everything Slots decided about one StructureResult (Step 1d output)."""
    query: str = ""
    posture: ReformatPosture = ReformatPosture.CLARIFY_REPHRASE
    slots: list[AnswerSlot] = field(default_factory=list)  # the real slot model
    reason: str = ""
    slots_ms: int = 0
```

---

## 4. Slot Derivation Logic (by Posture)

### PRECISE
- **Slot count:** 1
- **Semantics:** `"direct_answer"`
- **Capacity:** `resource_posture.breadth`
- **Required:** True
- **Priority:** 0
- **Rationale:** One clear query with complete corpus/lexicon coverage. Fillers picks the single best match.

### FAN_OUT
- **Slot count:** N (one per fanout theme, capped at MAX_FANOUT_THEMES=4)
- **Semantics:** `"thematic_exploration"`
- **Capacity per slot:** `resource_posture.breadth / N` (distribute breadth across themes)
- **Rewritten query:** Populated for each slot — maps to the specific sub-question this theme addresses
- **Required:** True for all
- **Priority:** 0..N-1 (ranked by fanout_theme.score, highest score = priority 0)
- **Rationale:** Multiple thematic angles on the same question. Each theme gets its own slot with query linkage for semantic matching.

**Slots receives `fanout_themes[]` from StructureResult (Option A — decided 2026-07-23).** This carries theme labels, scores, and member_codes from Reformat through Structure. Slots maps each theme to its corresponding `rewritten_query` text, giving Fillers full semantic context for chunk assignment (no re-derivation needed).

### CLARIFY
- **Slot count:** 0
- **Rationale:** Query is missing essential slots (domain or jurisdiction). No answer structure; Chat clarifies instead.

### RELY_ON_EXTERNAL
- **Slot count:** 1
- **Semantics:** `"external_context"` (Router strategy c/d will handle)
- **Capacity:** `resource_posture.breadth`
- **Required:** False (escalation fallback)
- **Priority:** 1 (lower than default answers)
- **Rationale:** Corpus is incomplete. Router strategies c/d (LLM+Vertex search) handle this. One slot for fallback.

### DECLINE
- **Slot count:** 0
- **Rationale:** Query is out of scope. No answer slots; Chat declines gracefully.

### CLARIFY_REPHRASE
- **Slot count:** 0 or 1 (TBD with Ananth)
- **Rationale:** Tentative/passthrough posture. Behavior TBD pending final design of CLARIFY_REPHRASE semantics in Reformat.

---

## 5. Slot Semantics Vocabulary (DRAFT)

UX's draft guessed `direct_answer / context / edge_case`. Refining with posture as the driver:

| Posture | Slot Semantics | Notes |
|---|---|---|
| PRECISE | `direct_answer` | Complete, high-confidence answer |
| FAN_OUT | `thematic_exploration` | One thematic angle on a multi-faceted question |
| RELY_ON_EXTERNAL | `external_context` | Fallback when internal corpus insufficient |
| (bonus slots TBD) | `context` | Supporting facts, background (if posture ever calls for it) |
| (bonus slots TBD) | `edge_case` | Boundary cases, exceptions (if posture ever calls for it) |

**Action:** Confirm with UX whether this taxonomy matches their Fillers draft, or if they need a different set.

---

## 6. Capacity Derivation

**Rule:** Never hardcode. Derive from `resource_posture.breadth`.

- **PRECISE:** `capacity = breadth`
- **FAN_OUT:** `capacity_per_slot = breadth / num_themes`
- **RELY_ON_EXTERNAL:** `capacity = breadth` (same as default)

**Rationale:** Pool already derived its own per-strategy widths from breadth (verified in Pool's design). Slots follows the same discipline.

---

## 7. What Slots Does NOT Do

- Touch Gate/Reformat/Structure logic (all three closed)
- Assign Pool's chunks to slots (Fillers' job)
- Make routing decisions (Router's job)
- Generate answer text (Synthesis' job)
- Emulate the legacy `answer_shape` string hint (essay/structured/binary/any) — that's a Chat UI preference, dead weight for the slot model

---

## 8. Process — Same Rigor as Prior Shape Modules

1. **Resolve the open questions with Ananth:** FAN_OUT theme handling (contract change?) + CLARIFY_REPHRASE behavior + slot-semantics vocabulary alignment with UX.
2. **Implement:** Pure compute, zero DB calls (same as Structure). Unit tests on slot-derivation logic.
3. **Test:** Eval input (is slot-shape correctness measurable at this layer, or only downstream?). Characterization test (same query → byte-identical slots before/after refactors).
4. **Cross-agent sign-off:** UX (aligns Fillers draft), Chat, Eval, DB, TECH.
5. **Live tracker:** `shape-slots-simulation-tracker.md` (same pattern as every other module).
6. **Commit:** Module-prefixed filenames in `shape/` (e.g., `slots.py`, `slots_contracts.py`). Ping before touching `shape/contracts.py`.

---

## 9. Remaining Open Questions for Ananth (BEFORE build)

1. ✅ **FAN_OUT theme handling:** DECIDED — Option A. StructureResult carries `fanout_themes[]`. Structure agent implementing. Slots ready to consume once landed.

2. **CLARIFY_REPHRASE behavior:** This posture is "tentative, not yet confirmed" (corpus_search_router.py comment). What should Slots do with it? 0 slots (passthrough)? Or conditional logic pending Reformat clarification?

3. **Slot-semantics vocabulary alignment:** UX's draft `direct_answer / context / edge_case` vs. the posture-driven taxonomy above. Do they need refinement? Confirm before building.

---

## 10. Success Criteria

- ✅ AnswerSlots contract defined, ratified by UX/Chat/Eval/DB/TECH
- ✅ All three open questions resolved
- ✅ Unit tests on slot-derivation logic (posture → slots, breadth → capacity)
- ✅ Characterization test (same input → byte-identical slots)
- ✅ Integration test with Fillers (does Fillers successfully consume AnswerSlots?)
- ✅ Live tracker current and signed off
- ✅ Unblocks Fillers build (Step 3)

---

## 11. Appendix: FAN_OUT Theme Re-derivation (Fallback Option C)

If the contract cannot be changed to pass fanout_themes, Slots could re-derive them from `rewritten_queries[]` + lexicon context:

1. For each `rewritten_query`, parse the intent/theme via lexicon lookup (same mechanism Reformat uses)
2. Group queries by theme
3. Assign priorities based on prevalence or position in the list

**Downside:** Loses Reformat's careful scoring/clustering (vector similarity, prevalence weighting, is_catchall flag). Less precise. Only if contract change is ruled out.

---

**Next:** Structure agent implements fanout_themes pass-through in StructureResult. Once that lands, Slots proceeds with build (still awaiting Ananth answers to §9 questions 2–3).
