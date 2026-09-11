# The prompt budget — measured inventory, and what it says

Ananth, 2026-09-10: *"you are going to have to count the prompt length and
optimize for it… we know the objective of react — fill gaps, close, synthesize,
draft and communicate. We need to make sure we have custom prompts for it and
each measured, and the only variable is the tool output which we will have to
wing it for now."*

All figures `[MEASURED]` from `prompt_blocks` / `prompt_compositions` in dev,
2026-09-10. **Character counts only.**

> **CORRECTION.** An earlier version said chars/4 *"under-counted by ~5% in two
> independent instances, which makes it a systematic bias."* **Withdrawn.** The
> prompt seat measured it against Gemini's real `countTokens` on prose and got
> **3% OVER** — opposite sign, same tokenizer. **Both of my instances were
> manifest-like text**, so I held content type constant across two samples and
> reported the result as universal. The bias is **content-dependent**, not
> systematic, and its direction is not predictable from the method alone.
> Retained rather than deleted: this is the same *what-varied* error I withdrew
> a tier comparison for two hours earlier.

---

## 1. 🔴 The headline: three of react's objectives are ONE prompt wearing three names

```
react_draft      | identity | mode_quality_bar | tool_manifest | response_shape | format_rules | critical_rules | user_profile
react_explore    | identity | mode_quality_bar | tool_manifest | response_shape | format_rules | critical_rules | user_profile
react_synthesize | identity | mode_quality_bar | tool_manifest | response_shape | format_rules | critical_rules | user_profile
```

**Identical seven blocks, identical order, 16,185 chars each.** The composition
keys are already separate — the machinery to differentiate them exists and is
wired — but **the content is the same.**

So Ananth's ask is not "build a prompt system." It is: **the seams are cut, and
nothing has been put in them.** `explore` (find evidence), `synthesize` (combine
it) and `draft` (write the answer) are different jobs given the same
instructions.

**And the missing two objectives have no composition at all:** *close* (resolve a
named gap) and *communicate* (present it). `react_no_tools` exists as a fourth,
884 chars, unrelated to these.

---

## 2. Where the 16,185 chars actually sit

| # | block | chars | share | owner |
|---|---|---|---|---|
| 1 | `react.identity` | 142 | 0.9% | product |
| 2 | `react.mode_quality_bar` | 21 | 0.1% | react-agent |
| 3 | **`react.tool_manifest`** | **24** | 0.1% | react-agent |
| 4 | `react.response_shape` | 1,818 | 11.2% | react-agent |
| 5 | `react.format_rules` | 1,445 | 8.9% | react-agent |
| 6 | **`react.critical_rules`** | **12,712** | **78.5%** | chat-architecture |
| 7 | `react.user_profile` | 23 | 0.1% | user-manager |

**Two findings fall straight out.**

**a. `react.tool_manifest` is a 24-char template.** The 14,271 tokens are
**injected at render**, not stored. So the static prompt and the manifest are
independently budgetable — and Tool Manifest's **890 median** lands in this slot
without touching anything else. **The Pareto win is cleanly separable from the
prompt work.**

**b. `react.critical_rules` is 78.5% of the static prompt** — 12,712 chars in
one block, owned by `chat-architecture`, and **identical across explore,
synthesize and draft.** It is the largest single fixed cost after the manifest,
and it is the least likely thing to be equally relevant to three different jobs.
`[OPEN]` **The first question for the prompt seat is not "write new prompts" but
"how much of these 12,712 chars does each objective actually need?"**

---

## 3. The budget identity

```
round_token_budget
  − static prompt      (measured per objective — table above)
  − tool manifest      (Tool Manifest's estimate(); 890 median, 319–1,535 observed)
  − thread history     (measurable per turn)
  − evidence carried   (measurable per round)
  ─────────────────────────────────────────────────────────
  = headroom for TOOL OUTPUT  ← the only unbounded term
```

**Every term is measurable except the last**, which is Ananth's "wing it for
now."

**How to wing it without lying about it:** carry tool output as a **range** with
a declared assumption, exactly as §1 of the round protocol requires the round
envelope to be a range. A point estimate on the one unbounded term would be the
least defensible number in the cascade. And **record the assumption alongside
the actual** — that is how the winged term stops being winged, by the same
declared-vs-delivered mechanism the tool latencies use.

**Order of operations matters and follows from the identity:** the manifest is
priced by Tool Manifest's `estimate()` *before* the prompt is built, so the
prompt builder is spending a **known remainder** rather than guessing.

---

## 4. What I will send the prompt seat

```
objective       ∈ {explore, close, synthesize, draft, communicate}
gap_targeted    the named gap this round is buying
direction       what to do about it
token_budget    the remainder after manifest, history and evidence
```

**`objective` and `gap_targeted` are the two the governor does not send today.**
`react_loop.py:4760`/`:4792` compute role and depth and pass those; **no gap and
no direction travel with a round.** So a round bought to close a specific named
gap does not tell the model which gap. That is a prompt-input change, not an
architecture change, and it is close to free.

---

## 5. Open

| item | status |
|---|---|
| three objectives share one prompt | `[OPEN]` — **the seams exist, the content does not** |
| `close` and `communicate` have no composition | `[OPEN]` |
| `critical_rules` 12,712 chars, undifferentiated | `[OPEN]` — biggest static cost after the manifest |
| per-objective **measured token** counts | `[OPEN]` — I have chars; tokens need `count_tokens` per composition |
| tool-output headroom | **winged, as a range with a recorded assumption** |
| governor sends `objective` + `gap_targeted` | `[OPEN]` — near-free, blocked only on gap identity |
