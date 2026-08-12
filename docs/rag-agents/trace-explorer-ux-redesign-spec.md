# Trace Explorer — UX Redesign Spec

> **Owner:** Retriever (Payor Policy Agent). **Status:** draft for review.
> **Requested by:** Ananth, 2026-08-05 — "I think we start with a structured
> UX change to trace... it has 3 functions... we should use this UX design
> so that it follows the same structure... very intuitive and ux, backend,
> persist consistency too."

## 1. Problem statement

`trace_explorer.html` grew feature-by-feature over this session: a single-query
form, a bank-run form, and (most recently) a Priors Lab panel, stacked
vertically with no grouping. Three real gaps follow from that:

- **No information architecture.** The page reads as one long scroll of
  forms, not "here are the 3 things I can do here." Ananth's own words:
  he can't follow it.
- **Inconsistent persistence.** Bank runs persist to GCS and are browsable
  (`run-bank/list`). Single-trace runs do **not** persist at all — close the
  tab and it's gone, no "review a previous question." Priors Lab computations
  don't persist either (by design, for now — see §4).
- **No design-system consistency.** The page hand-rolls its own dark-mode-only
  palette. Mobius has a real token system (`mobius-design/tokens.css`) used
  elsewhere; this page ignores it entirely.

## 2. Goals

1. **One intuitive top-level structure**: the page organizes around exactly
   3 functions, matching how Ananth actually uses it — not how features were
   added.
2. **UX/backend/persistence consistency**: every function that produces data
   follows the *same* pattern — run → persist → list/browse → reload. Today
   only bank runs do this; the other two don't, for no principled reason.
3. **Mobius design-system compliance**: adopt `mobius-design/tokens.css`
   instead of the bespoke palette.
4. **No regression**: every capability that exists today (forced strategy,
   caller mode, must-facts recall check, fan-out overrides, Priors Lab
   compute/auto-select) keeps working, just reorganized.

## 3. Non-goals

- **Not the DB-backed eval-workflow layer.** Question Bank management,
  comprehensive multi-strategy sweeps, and the compute→publish→retrieve
  provenance-sha pipeline are Eval-RAG/Eval-architect's build
  ([eval-workflow-tooling-spec.md](eval-workflow-tooling-spec.md)). This spec
  covers the **shell** they'll eventually build inside — not their tables,
  not their endpoints.
- **Not migrating priors_bootstrap.yaml persistence.** Priors Lab's "apply"
  stays local-file-only, per Ananth's phased directive, until that separate
  piece of work lands.
- **Not multi-user.** Single admin-key auth, no accounts, no concurrent-edit
  handling — matches today's reality.
- **Not a from-scratch visual identity.** This is an internal admin/debug
  tool; adopt the design tokens for consistency, not a bespoke landing-page
  treatment (see `artifact-design` calibration: utilitarian tools get
  polish, not a hero).

## 4. Information architecture

Three top-level tabs, each following the identical run → persist → browse
pattern:

```
┌─ Trace Explorer ────────────────────────────────────────────────┐
│  [ Run a Trace ]  [ Run the Full Bank ]  [ Compute & Capture Priors ] │
├───────────────────────────────────────────────────────────────────┤
│                                                                     │
│   (selected tab's content)                                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────┘
```

### Tab 1 — Run a Trace
Two modes, toggled at the top of the tab (not two separate tabs — they
share the same result view below):
- **New query**: today's single-trace form (query, forced strategy, caller
  mode, must-facts, run-eval checkbox).
- **Review previous**: a list of past single-trace runs (query snippet,
  strategy, mode, status, timestamp), click to reload — the missing half of
  today's "run vs. review" gap.

### Tab 2 — Run the Full Bank
Today's bank-run form (unchanged functionally): launch, load-by-job-id,
browse previous runs. Clicking a bank row reuses the *same* result view as
Tab 1.

### Tab 3 — Compute & Capture Priors
Today's Priors Lab panel (unchanged functionally): auto-selected latest
jobs, bucket/mode controls, compute, and the local apply mechanism.

**Shared result view** (Emits / Telemetry / Detailed Trace / Eval tabs)
stays below the 3 function-tabs — it's the same view whether you just ran a
trace, reloaded a previous one, or clicked into a bank row. This is the
consistency principle from §2.2 applied concretely: **one result-viewing
surface, three ways to populate it.**

## 5. Backend / persistence consistency contract

The core technical decision this spec makes: **all three functions persist
through the same shape** (GCS blob body + cheap blob-metadata for listing),
matching the pattern bank runs already use. Concretely:

| Function | Persists to | List endpoint | Load endpoint | Status |
|---|---|---|---|---|
| Run a Trace | `eval-artifacts/trace_explorer_single/{id}.json` | `GET /admin/trace-explorer/list` | `GET /admin/trace-explorer/result?trace_id=` | **new, this spec** |
| Run the Full Bank | `eval-artifacts/trace_explorer_bank/{id}.json` | `GET /admin/trace-explorer/run-bank/list` | `GET /admin/trace-explorer/run-bank/result` | exists today |
| Compute & Capture Priors | *(not persisted — read-only compute)* | n/a | n/a | intentional, see below |

Priors Lab is the one intentional exception: it computes from already-persisted
bank-run data and produces a preview, not a new artifact — persisting *every*
compute call would just be re-deriving the same bank-run rows redundantly.
(Eval-architect's build adds real computation-history persistence later, in
their DB layer — not a gap in this shell, a deliberate boundary with their
future work.)

## 6. Requirements

**P0 (this redesign):**
- [ ] 3-tab top-level structure, shared result view below
- [ ] Single-trace persistence (`_persist_single_trace`, done) + list/load
      endpoints (done) + "Review previous" UI in Tab 1
- [ ] Mobius design tokens imported, page re-themed (light/dark via
      `prefers-color-scheme`, matching tokens.css + tokens-dark.css)
- [ ] Zero functional regression on any existing control

**P1 (fast follow, not blocking):**
- [ ] Search/filter on the single-trace and bank-run history lists (bank
      history has no search today either)
- [ ] Empty-state guidance in each tab ("no traces yet — run one above")

**P2 (explicitly deferred):**
- [ ] Any UI for Eval-architect's DB-backed Question Bank / comprehensive
      sweep / publish-review-audit flow — out of scope here, their build

## 7. Open questions

- **Design tokens — dark-only today, tokens.css is light-first.** Need
  `tokens-dark.css` reviewed for parity before wiring `@media
  (prefers-color-scheme: dark)` — engineering, not blocking start.
- **UX (Platform Architects) has an open ask** (sent 2026-08-05) on the
  Question Bank surface shape for Eval-architect's later build — separate
  thread, not blocking this spec.

## 8. What ships from this spec

This spec covers the **shell redesign** only — IA, shared result view,
single-trace persistence, and design-token adoption. It's the "so that I can
follow along" fix Ananth asked for, sized to ship today, not gated on
Eval-architect's DB build or UX's Question Bank design.
