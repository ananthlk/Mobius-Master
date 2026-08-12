# Three-Adjudicator Calibration — Design Spec

**Status:** SPEC for build. Owner: **Eval** (owns `eval/judge.py`'s
`adjudicate()` and the calibration harness). Authored by Retriever
(coordination) from the 2026-07-24 design thread (Ananth's three-mode
proposal + Eval's rigor pass). Ananth working with Eval on execution.
Nothing here overrides Eval's implementation judgment — it's the agreed
design to build against.

## 1. The problem this solves

Production queries carry **no golden answers** (no `must_facts`), so we
cannot grade prod retrieval/answers against ground truth directly. The
calibration data-collection posture (blend deactivated, see
`blend-model-design.md`) produces recall curves *offline* on a labeled
bank — but we also want a signal we can trust *in prod*, to know whether
real traffic behaves like the offline bank and whether quality is moving.

The move (Ananth): **calibrate a reference-free adjudicator against the
labeled oracle offline, then deploy the reference-free one in prod.** You
don't measure prod recall directly — you deploy a judge whose reliability
you've already characterized where labels exist.

## 1a. Weighted facts (Ananth, 2026-07-24) — load-bearing for every mode

`must_facts` must be **weighted by importance, not treated as a flat equal
set.** Not all facts matter the same: for "what is the timely filing
deadline," "180 days for claims" is the primary answer; "60 days for
appeals" is a secondary caveat. A flat set scores "got the caveat, missed
the core" identically to "got the core, missed the caveat" — but the first
is a *bad* answer and the second is a *good* one. Flat recall is therefore
the wrong metric.

Consequences (all three modes):
- Each `must_fact` carries an **importance weight, assigned at authoring/
  verification time** — folds into the bank-labeling pipeline's per-fact
  verification step (one more field per fact), not a separate pass.
- **recall@K becomes WEIGHTED recall** = Σ(weight of facts captured in
  top-K) / Σ(all weights), NOT count-based. The plateau curves then measure
  "how much of the *important* content is captured" — a strategy that nails
  the one critical fact beats one that grabs three trivial ones.
- Weight SCHEME — **Eval ruling (2026-07-24): TIERED (primary / secondary /
  tertiary), NOT numeric 0-1 for v1.** Reason: the bank is multi-author and
  the labels ARE the ground truth — cross-author inconsistency in a continuous
  0-1 weight injects noise into the very oracle we calibrate against, and a
  0.6-vs-0.7 distinction isn't reliably author-reproducible. Three named tiers
  are reproducible ("is this THE answer, a needed qualifier, or nice-to-have?").
- **Scoring — weighted sum WITH a primary gate, because Ananth's requirement
  is categorical, not continuous.** A pure Σ(tier captured)/Σ(tier all) only
  *approximates* "missing the core = bad": with 3/2/1, missing the primary but
  getting two secondaries scores 4/7 ≈ 0.57 — still reads "decent" despite
  missing THE answer. Tuning tier numbers to mimic a categorical rule is
  fragile. So the score is:
  `weighted_recall@K × primary_gate`, where **primary_gate = 1.0 if ALL
  primary facts are captured, else a hard cap (start 0.5, calibrate).** This
  encodes "no core answer → cannot be a good answer" DIRECTLY rather than
  hoping the weights approximate it. Missing any primary caps the score;
  among primary-complete answers, the weighted sum ranks by how much
  important secondary/tertiary content is also captured. Applies to all three
  modes' @K curves (and composes with the monotone envelope — gate and
  envelope are independent transforms). Tier numeric values (e.g. 3/2/1) only
  set the *ordering among primary-complete answers*; the gate does the
  categorical work, so exact tier numbers are low-stakes. Numeric per-fact
  weights = v2 only if tiers prove too coarse. Built in from fact #1.

## 1b. Judge lock (Ananth, 2026-07-24) — HARD requirement, silently invalidating if drifted

The entire calibration rests on the judge being ONE fixed instrument. If it
drifts, everything measured against it becomes uninterpretable — and the
drift is *silent* (curves keep coming, just no longer comparable). Locks,
all non-negotiable:

0. **THE LOAD-BEARING FIX — offline must route through the locked proxy,
   FAIL-CLOSED (Eval, verified in code 2026-07-24).** The lock (`rag_eval_
   adjudicate` eligible ONLY on gemini-2.5-pro) lives in the LLM Manager
   PROXY's model_registry and governs only the PROD path. Offline
   calibration BYPASSES it: `judge.py` → `llm_manager_client` → when the
   proxy is unreachable (every local run) → `_dev_fallback` → a DIRECT
   Vertex call on `VERTEX_MODEL` (this repo's `.env` sets it to
   **gemini-2.5-flash**; code default is gemini-1.5-pro — either way NOT the
   locked pro), returning `model="unknown"` — never touching model_registry,
   never seeing the
   lock. **Consequence: every offline number to date (the 0.146 baseline,
   forced-leg scores, the recall curves, the ~0.31 F1) was graded by the
   dev-fallback ruler, NOT the locked gemini-2.5-pro that prod uses** — a
   live, structural eval-judge ≠ prod-scorer violation (and the likely
   cause of the monotonicity breakage: a weaker/older model is less
   consistent). FIX: calibration must run through the LLM Manager proxy
   (set `CHAT_INTERNAL_LLM_URL`, in practice **run on GCP** where the proxy
   is reachable) AND must **REFUSE to run (fail-closed) rather than
   dev-fall-back** when it can't reach the locked proxy. The authoritative
   numbers must be re-run through the locked pro judge on GCP; current
   offline numbers remain valid only as *relative/methodology* signal, not
   authoritative. This is the real fix — not the model name.

1. **Use the PRODUCTION QA AGENT as the judge — not a bespoke calibration
   judge.** The offline judge MUST be the same instrument as the prod one,
   or the offline-measured reliability (the ~0.31 bound, the (c)-vs-(a)
   correlation) doesn't transfer to prod. `adjudicate()`/`prefix_grade` must
   BE the production QA agent (or route through it), not a parallel path.
   This IS the standing "eval judge == prod scorer == bandit reward"
   principle — made load-bearing here.
2. **Lock the PROMPT** — versioned, frozen. Any prompt change is a new judge
   and requires re-baselining.
3. **Lock the MODEL — Gemini 2.5 Pro** (Ananth's call). Note the correction
   from item 0: the offline runs were NOT on 2.5-flash as first assumed — they
   were on the dev-fallback (`VERTEX_MODEL`, default gemini-1.5-pro, reported
   "unknown"), which is even further from the prod-locked 2.5-pro. Once offline
   routes through the locked proxy (item 0), the model IS 2.5-pro by the
   existing model_registry lock — so "lock to pro" is satisfied by fixing the
   routing, not by a separate model config. Pro is more capable/consistent,
   likely reduces the judge non-determinism already observed (the
   recall@1=0.25→@3=0.00 impossibility the monotone envelope patches over).
4. **Version-stamp the (prompt, model) pair on every graded artifact** so any
   future judge change is *detectable* rather than silent — the whole point
   of the lock is that a drift can't hide.

## 2. The three adjudicators

Run all three on the **same** offline labeled queries (where golden answers
exist). This is what makes calibration possible.

| Mode | Input graded | Reference? | Measures |
|---|---|---|---|
| **(a)** Chunk-recall | Retrieved chunks directly | Golden `must_facts` | Retrieval recall — are the facts *present in the chunks* |
| **(b)** Answer-completeness | Chunks → LLM synthesis → answer | Golden `must_facts` | End-to-end — facts the *synthesized answer* actually carries |
| **(c)** Groundedness | The synthesized answer | **None (reference-free)** | Is every claim traceable to a retrieved chunk — **the prod-deployable proxy** |

Mode (a) is what `adjudicate()` does today (rubric mode; its score on a
top-K prefix **is** recall@K — Eval's realization, no new judge internals).

## 3. THE load-bearing design decision — (c) is a groundedness critic, NOT a plausibility critic

This is the one thing that, done wrong, invalidates the whole scheme
(Eval's decisive correction, 2026-07-24):

**A reference-free judge's error is not random noise around the truth — it
is biased UP exactly where the system fails.** A reference-free judge grades
what it can see: fluency, plausibility, completeness-of-*looking*. But a
confident, fluent, *wrong* answer (a hallucination) is precisely what a
*failing* retrieval produces: low recall → synthesis confabulates → reads
great. So a plausibility-style (c)'s optimism is **correlated with the true
(unobserved) failure**, not independent of it. You therefore **cannot**
calibrate it as `c ≈ a + constant` — a scalar bias correction assumes
independent error, and this error is conditional on the very thing you're
trying to measure. Such a (c) is least trustworthy exactly in the failure
cases that matter most.

**The fix:** build (c) to grade **"is every claim in this answer traceable
to a retrieved chunk?"** — faithfulness/groundedness — NOT "does this look
complete and good?" Groundedness is reference-free (needs no golden answer)
AND *anti-correlated* with hallucination (it catches the confident-
unsupported answer instead of being fooled by it). Only a groundedness (c)
has a bias a calibration can characterize.

## 4. The honest bound — do not oversell "prod is interpretable"

We already have a reference-free-ish faithfulness critic: **fact_checker's
grounding mode**, and Eval already measured its reliability on this corpus:
**honesty-critic F1 ≈ 0.31.** That number IS a calibration result — it says
the reference-free judge is **weak here** (the c-strategy is a hallucination
engine in that data). Consequence:

- **prod-(c) is trusted for TREND / relative movement, not absolute recall.**
  It's a noisy, regime-dependent proxy — useful, but bounded, and already
  bounded. "With this we can reason more comfortably" means about
  *direction*, not absolute quality.
- Build (c) by cross-checking against the existing fact_checker grounding
  mode first — it may BE (c) with a rubric tweak; don't reinvent it.

## 5. Calibration methodology

1. Run (a), (b), (c) on the offline labeled bank (golden answers present).
2. (a) and (b) are the ground-truth oracles (reference-based).
3. Measure **how (c) tracks (a)/(b)** — the correlation, and critically its
   *conditional* behavior (does (c) stay honest when (a) is low? that's the
   failure regime that matters). This correlation is the calibration.
4. In prod, (c) runs alone; its scores are interpreted through the offline-
   measured correlation — as trend, within the ~0.31-bounded reliability.

## 6. Caveats that must be built in (Eval)

- **(b) is synthesizer-conditional.** A better synthesizer scores higher on
  identical chunks — so (b) measures "chunks + THIS synthesizer." If the
  offline synthesizer ≠ prod Chat, (b) is a **lower bound** — label it so.
  Ideally run (b) with the prod synthesizer (Chat) for parity.
- **(c)'s calibration drifts.** It's valid only while prod resembles the
  offline bank — needs periodic re-validation against fresh labeled samples
  (ties to prod-sampled queries feeding the bank; see bank-sourcing in
  `blend-model-design.md`).
- **Monotone envelope on all @K curves.** Judge non-determinism can break
  recall monotonicity (observed: recall@1=0.25 then @3=0.00, impossible
  since top-3 ⊇ top-1). Enforce `recall@K := max over K'≤K` across all three
  modes' prefix curves. (Eval caught this live and is adding it.)

## 7. The prize — (a)-vs-(b) gap is the synthesis-loss curve

Prefix-grade **both** (a) and (b) → two plateau curves:
- (a)@K = facts present in the top-K *chunks*.
- (b)@K = facts the synthesized answer *uses* from top-K.

**Their gap at each K is the synthesis-loss curve** — directly answers "how
much does synthesis drop, and does fetching deeper help or just add noise
the synthesizer ignores?" The earlier synthesis-gap question, turned into a
measurable curve. For (c): prefix-grading is part of calibration — check
whether (c)@K tracks (a)@K/(b)@K.

## 8. Dependencies & effort

- **(c) grader — RESOLVED (Eval, 2026-07-24): a WRAPPER over existing code,
  not a new rubric.** fact_checker.py ALREADY contains the reference-free
  groundedness critic — its prompt says verbatim "There is NO answer key —
  judge the ANSWER only against the PASSAGES, never your own outside
  knowledge; decide whether the answer is GROUNDED," emitting
  hallucinated_claims + honest_abstain + per-claim support. That IS mode (c).
  So the work is: (i) `adjudicate(mode='reference_free')` routes to that
  existing rubric; (ii) reduce its ledger output to a single 0-1 SCALAR
  comparable to (a)/(b) so the correlation in §5 is computable; (iii) guard
  against cross-wiring the reference-BASED grounding path (fact_checker has
  both — the ref-free path must receive NO must_facts). Well under the 1-2 day
  estimate, and (c)'s reliability is ALREADY characterized (~0.31 F1 is this
  exact critic). Big de-risk on §3.
- **(b) synthesis step:** capability exists (`prove_synthesis_gap.py` via
  `llm_manager_client.generate`; `calibrate.py --synthesize`) but needs
  **GCP** (429'd locally) and ideally prod-synthesizer parity.
- **Authority fix GATES (b), not (a):** (b) can only reward citing
  `contract_source_of_truth` over a low-authority chunk if authority
  survives to synthesis. The `document_authority_level` → `FilledChunk.
  authority_level` → `_infer_authority` fix (Retriever/fillers +
  Synthesizer) must land before (b) is meaningful. Not needed for (a) or
  (c)-groundedness.
  - **Update 2026-08-05:** a/b enforce per-chunk authority via `_infer_authority`
    today; c/d now carry a real binary signal too — `payer_domain_match`
    (filler_c/filler_d `_domain_matches_payer`, landed 08-04), set when a
    chunk/citation URL is on the payer's own official domain. So the per-chunk
    authority SIGNAL now exists for all of a/b/c/d; the remaining gap is only
    that c/d's PRE-FILL categorical exclusions (NON_CITABLE_STRATEGIES for d,
    the 0.6 authority-prior threshold for c) stop that signal from ever being
    consulted. Relaxing the d pre-fill floor is an Ananth call ("accurate ≠
    citable"); modeled as a yield prior P(chunk survives the citable filter).
- **Prefix-grading** applies to (a) and (b) (two plateaus); for (c) it's a
  calibration check, not a standalone curve.

## 9. Ownership

- **Eval:** all three graders, the calibration harness, the correlation
  analysis, the monotone-envelope guard, the ~0.31 reliability bound.
- **Retriever + fillers:** the authority fix that gates (b) (separate work,
  tracked in `blend-model-design.md` open items).
- **Retriever (done):** `fill_depth` emit (occupancy@capacity = k₀ per
  observation) — the retrieval substrate all three modes grade.
- **Chat:** prod-synthesizer parity for (b), if we want (b) to match prod
  rather than be a labeled lower bound.

## 10. Open questions

- ~~Does (c) reuse fact_checker's grounding rubric wholesale?~~ **RESOLVED
  (§8):** yes — fact_checker already has the reference-free groundedness
  critic; (c) is a wrapper + scalar-output tweak, not a new rubric.
- ~~(b) offline synthesizer vs prod Chat?~~ **RESOLVED (Eval): START offline,
  labeled lower-bound, now.** The offline synthesizer can only UNDERSTATE
  synthesis quality (weaker than prod Chat), so offline-(b) is a conservative
  FLOOR, and the (a)−(b) gap's shape-vs-depth is synthesizer-robust. Waiting
  for Chat-parity serializes our timeline on theirs for no measurement gain.
  Upgrade to Chat-parity as v2 once (b) becomes the live signal and Chat's
  refactor lands. (a) and (c) proceed immediately; (b) proceeds offline once
  the authority fix lands.
- **STILL OPEN:** Re-validation cadence for (c)'s calibration drift — tie to
  what fraction of the bank refreshes from prod samples per cycle. Eval to set
  once we have the first calibration and a drift-rate estimate.
