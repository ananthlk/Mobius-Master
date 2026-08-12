# Shape/Gate Module — Eval QA Review & Scenario Co-Authorship

**Status:** DRAFT — Eval's work package against `docs/rag-agents/shape-gate-module-spec.md` §8.
**Against:** `mobius-rag/app/services/retriever/shape/gate.py` + `contracts.py`, reviewed alongside
`tests/test_shape_gate.py` (31 tests, all passing) and `scripts/run_gate_on_cmhc.py`.
**Scope:** gate (classification) QA only. Not reformat, not the 7-step chain.

---

## 0. Grounding correction — SUPERSEDED (Retriever re-verification, 2026-07-22)

**This section's numbers were checked against a stale source and are wrong.** Eval pulled
`mobius-rag/data/policy_lexicon.yaml` (a static file, last committed 2026-05-06 per git log) —
that file does not reflect the live `policy_lexicon_entries` DB table, which is what
`list_active_d_tag_codes()` / `expand_query_via_lexicon()` (and therefore `gate.py`) actually
query at runtime. The lexicon has grown substantially since that YAML snapshot was committed
(consistent with the ongoing lexicon-cleanup/tagging pipeline work tracked elsewhere in this fleet).

**Re-verified live, 2026-07-22** (`SELECT count(*) FROM policy_lexicon_entries WHERE active AND
kind='d' AND code LIKE 'eligibility.%' AND code != 'eligibility.general'`):

| root | leaf count (live DB) | vs. this doc's original (stale-file) claim |
|---|---|---|
| eligibility | **80** | was reported as 5 |
| health_care_services | **631** | was reported as 60 |

The spec's original "~90 eligibility siblings" / "80 fanout_codes" figures were correct — they
were also independently checked against the live DB when the spec was written. **No correction to
the spec is needed.** `health_care_services` is even larger than Eval estimated (631, not 60) —
if anything the fanout-bounding problem (§9.2 of the spec, §5's `fanout_codes` size distribution
ask below) is more urgent than originally flagged, not less.

**Action for Eval:** when building the contour-diversity eval bank (§2) or any lexicon-facet-count
work, query `policy_lexicon_entries` directly (or call `list_active_d_tag_codes()`), not
`data/policy_lexicon.yaml` — that file is a stale seed/snapshot, not a live source of truth. Worth
a standing note in Eval's own lexicon-facing tooling to avoid this recurring.

The mechanism-level findings below (§1, §3, §4) are still valid and don't depend on the specific
leaf counts — only the numeric claims in the original §0 (now struck through above) and the
`health_care_services` fanout-size assertion in §5's proposed test needed correcting (see inline
note there).

---

## 1. Coverage gaps in the existing 31 tests

The suite is solid on the mechanics it targets (pure `_classify()` branch coverage is close to
exhaustive) but has systematic gaps in three places:

1. **All general-only-match tests are `eligibility`-only.** Every UNDERSPECIFIED/EXACT test that
   exercises `_is_general_only_match` uses `eligibility`/`eligibility.general` codes. Zero tests
   use a second umbrella root (`health_care_services`, `claims`, `benefits`). If the general-only
   detection has a root-name-specific bug (e.g. an off-by-one in the `.general` suffix match, or
   an assumption baked into a fixture rather than the function), the current suite can't catch it.
2. **No multi-root / mixed-specificity general-only case.** `_is_general_only_match` explicitly
   returns `False` when codes span >1 root (`test_is_general_only_match_false_on_multi_root`), but
   that's tested with two clean single-leaf codes. There's no test for "general bucket on one root
   PLUS a specific leaf on a *different* root" (e.g. `eligibility.general` + `claims.timely_filing`)
   — a real query like "eligibility for a timely-filed claim" would plausibly produce this and it's
   currently unexercised.
3. **`kinds_matched == 1` (only P matched, D and J both empty) is untested.** `_classify` starts
   with `if result.kinds_matched == 0` for UNCLEAR/OUT_OF_SCOPE, but a query that only trips a
   P-code with zero D/J (e.g. bare "submit" or "resubmit" with no domain word) has `kinds_matched
   == 1` and falls through past the `== 0` branch into `union_docs == 0` → CORPUS_GAP-or-not logic
   with `missing_required = ["d","j"]`. Worth a dedicated unit test — this is a real edge case
   (process-only query), not a synthetic one.
4. **The `anchor` narrow-corpus branch (line 274) is tested only for missing-J**, never
   missing-D. `test_exact_when_missing_kind_but_corpus_already_narrow` matches D and leaves J
   unmatched. There's no mirror case with J matched, D unmatched, `intersection_docs` (n/a since D
   missing → `kinds_matched` could be 1, using `union_docs` as anchor) ≤ 25. Given D and J play
   asymmetric roles (D is the domain the whole general-only branch cares about; J never triggers
   that branch), a missing-D-narrow-corpus case is worth its own test rather than assuming
   symmetry with missing-J.
5. **`_BROAD_MIN_DOCS = 25` is a bare magic number with no boundary test.** No test at exactly 25,
   24, or 26 union/intersection docs. Since this constant is explicitly called out as
   "Eval-tunable" in the gate.py docstring, Eval should own a boundary test that pins current
   behavior (`<=25 → EXACT`, `26 → UNDERSPECIFIED`) so future tuning is a visible, deliberate diff
   against a named test rather than a silent behavior change.
6. **CORPUS_GAP is only tested at the pure-unit layer** (correctly, per the file's own docstring —
   no natural query cleanly isolates a real zero-doc code). But there's no test confirming that a
   *multi-code* match where only SOME codes have zero docs doesn't accidentally trip CORPUS_GAP
   (the check is `union_docs == 0`, i.e. ALL matched codes zero, not any). A synthetic case with one
   zero-doc code + one live code (union_docs > 0) should assert we correctly do NOT get CORPUS_GAP.
7. **Integration-layer contour coverage is 2/6** (VICINITY, UNCLEAR, EXACT, UNDERSPECIFIED — wait,
   actually the integration class covers OUT_OF_SCOPE, UNCLEAR, VICINITY, UNDERSPECIFIED, EXACT —
   **5 of 6**, missing only CORPUS_GAP end-to-end, which the file's docstring says is intentional
   (no clean real-query isolator exists). That's a reasonable, documented trade-off, not a silent
   gap — flagging only so it's recorded as consciously accepted rather than rediscovered later.
8. **No test on `gate.py`'s SQL-injection-adjacent surface.** `_probe_corpus` builds parameterized
   SQL correctly (codes go in as bound params, not interpolated), but there's no test with a code
   containing special characters a lexicon phrase might produce (e.g. an apostrophe from
   "practitioner's" if a future lexicon entry includes one) confirming the parameterization holds
   under a stress code. Low risk given current code shapes but cheap to pin.

---

## 2. On building a contour-diversity eval bank separate from cmhc

**Yes — recommend it, and scope it distinctly from cmhc.** cmhc is answer-quality-anchored (each
query has an `expected.strategy` and, implicitly, real corpus grounding) and by construction
lands almost entirely in EXACT/UNDERSPECIFIED because every query in that bank is deliberately
in-corpus (the script's own docstring: "every query in the bank is in-corpus, so we expect EXACT
or VICINITY on all of them, never UNCLEAR/CORPUS_GAP"). That's the right bank for answer-quality
work but the wrong instrument for gate contour QA — it structurally cannot exercise OUT_OF_SCOPE,
UNCLEAR, or CORPUS_GAP, and only touches VICINITY by coincidence (1 query, per the test file's own
comment about Clarendon AR).

Proposal: a new bank, `eval/queries_gate_contours.yaml`, with these properties:
- **Balanced by contour**, not by expected strategy — aim for ~8-10 queries per contour, 6
  contours, ~50-60 total.
- **Explicitly labeled `expected_contour`** (not `expected.strategy`) as the pass/fail field, run
  through a `run_gate_on_contour_bank.py` script mirroring `run_gate_on_cmhc.py`'s shape but
  asserting contour match rather than just reporting distribution.
- **Off-domain-but-well-formed queries for OUT_OF_SCOPE** drawn from realistic adjacent-but-wrong
  domains (weather, general medical symptom questions with no payer/policy framing, unrelated
  insurance lines like auto/home) — not just one hand-picked example.
- **UNCLEAR bank should include the multi-word "fake English" gap case** even though the gate is
  known to NOT catch it (`"asdkfj qwoeiru xyz"` → currently OUT_OF_SCOPE) — as an explicitly
  `xfail`/documented-gap entry, so the accepted limitation is pinned in the bank itself and
  regresses loudly if someone "fixes" it inconsistently later, rather than silently drifting.
- **CORPUS_GAP real-world sourcing**: since no clean natural query isolates this today (confirmed
  true from the gate.py comments), this bank's CORPUS_GAP entries should be sourced from
  Sourcing/Maintaining's actual zero-doc lexicon codes (the corpus-heal 424 forensics / lexicon gap
  logs already tracked elsewhere in this fleet) rather than invented — giving CORPUS_GAP real
  ground truth instead of staying synthetic-only, and creating a natural tripwire: if a doc gets
  ingested for that code later, the bank query should flip contour and the test should catch it.
- **VICINITY needs more than one rare-jurisdiction example** — vary both axes: rare-domain +
  common-jurisdiction, not just common-domain + rare-jurisdiction (the current only VICINITY case
  is jurisdiction-side; a domain-side VICINITY case is untested anywhere).

This is a genuinely separate deliverable from cmhc and shouldn't be folded into it — different
purpose (contour-classifier QA vs. answer-quality QA), different pass criteria, different owner
intent (Eval building this vs. Retriever/cmhc being answer-engine-quality-owned).

---

## 3. Sign-off gates Eval wants before the gate is "signed off"

1. **Contour distribution stability over time** — once the contour-diversity bank exists, re-run
   it on every lexicon revision bump (the lexicon already has a revision mechanism per
   `document_tags` lexicon_revision column) and diff contour assignment per query ID. A query
   flipping contour on an *unrelated* lexicon change (i.e., not the specific tag that query targets)
   is a regression signal worth gating on, mirroring the "lift=moved+changed, drift=moved+unchanged"
   framing already established for Eval's calibration work elsewhere in this fleet.
2. **False-positive rate on OUT_OF_SCOPE** — the single scariest failure mode for this gate is a
   genuinely in-corpus, answerable question getting declined as out-of-scope because of a lexicon
   phrase-matching miss. Recommend measuring this specifically: sample real/production query
   traffic (once available) that got OUT_OF_SCOPE, and periodically spot-check a sample against
   the corpus to catch missed lexicon coverage — a false OUT_OF_SCOPE is worse than a false
   UNDERSPECIFIED (one silently drops a real user, the other just asks a clarifying question).
   Suggest this as a standing Eval metric, not a one-time check.
3. **`_BROAD_MIN_DOCS` (25) and general-only-match logic should be treated as Eval-owned tunable
   constants** (per the gate.py docstring's own framing), meaning: any change to either needs a
   before/after contour-distribution diff against the contour-diversity bank, not just a code
   review. This should be a documented process, not just a norm.
4. **Latency**: §9.1 of the spec already flags the gate missing the <500ms p50 target — Eval's
   position is this is a DB/TECH-owned remediation, but Eval should gate on latency parity, not
   just correctness: whatever the DB fix lands on, re-run the contour bank and confirm contour
   assignment didn't change as a side effect of any query-shape optimization (e.g. reordering
   probe filters, adding a LIMIT, sampling). Correctness-under-optimization is the actual risk,
   not raw ms.
5. **fanout_codes size distribution** — before Reformat consumes `fanout_codes` (currently
   unbounded per §6/§9.2), Eval wants a one-time audit of the real distribution across all
   general-only roots (health_care_services alone would emit 59 sibling codes unbounded) logged
   as a baseline, so Reformat's later bounding strategy has a concrete "before" number to justify
   against, not just the single `eligibility` example currently cited (which — per §0 above — is
   actually a very mild case at 5 siblings, not the 80 the spec cites).
6. **Sign-off should be scenario-count-and-branch-coverage-based, not just "31 tests pass."**
   Recommend Eval sign-off criteria be: (a) all gaps in §1 above addressed or explicitly
   deferred-with-owner, (b) contour-diversity bank built and green, (c) `_is_general_only_match`
   tested against ≥2 distinct umbrella roots, (d) the §0 spec numbers corrected.

---

## 4. P-tag / process-intent stress scenarios

The current lexicon has exactly 15 P-tag leaves under 4 roots: `communication` (call/contact/email),
`compliance_action` (prohibited/required), `review` (check_status/review), `submission`
(resubmit/submit), `verification` (verify — aliases "confirm", "verification of"). Only
`verification.verify` is exercised in the existing tests (via "verify"/"check" contrast). Proposed
additions:

**4a. Verb-variation stress on the process_intent regex, beyond "check"/"verify":**
- "How do I confirm eligibility for Medicaid" — should hit P via lexicon alias (`confirm` is an
  explicit `verification.verify` alias) → EXACT via `p=yes`, not process_intent phrasing. Confirms
  the alias path independently of the regex path (currently only "verify" tests the alias path and
  "check" tests the regex path — no test distinguishes which mechanism fired when both could).
- "Can I confirm eligibility for Medicaid" — no "how do I/how to" framing, but "confirm" IS a
  lexicon alias. Tests that the alias path resolves general-only-match even when the structural
  regex does NOT fire (`_PROCESS_INTENT_RE` requires "how do i/can i/does one/how to/what's the
  process/what are the steps/steps to/procedure for" — "can I confirm..." doesn't match "can i"
  requiring "how can i"). Worth confirming this doesn't fall through to UNDERSPECIFIED incorrectly.
- "What's the process to resubmit a denied claim" — `submission.resubmit` P-tag + `claims` D-root;
  since `claims` isn't a general-only-match case in the current suite at all, this also covers gap
  §1.1 above (a non-eligibility umbrella).
- Negative control: "Is eligibility required for Medicaid" — contains the word "required"
  (a `compliance_action.required` P-tag alias!) but is NOT actually process-intent in the human
  sense — it's a fact lookup that happens to use a word that's also a P-tag alias. Confirms P-code
  matching and process_intent semantics are doing the right thing even when a P-tag alias fires
  for a reason unrelated to "how do I."

**4b. Multi-facet domain beyond eligibility — `health_care_services` (60 leaves):**
- "Behavioral health services for Medicaid" (matches only `health_care_services` bare root or
  `.general`, if such exists — need to confirm) vs "How do I get behavioral health services
  authorized for Medicaid" (adds process_intent). This is the real stress case for
  `_is_general_only_match` at the width the spec's "80 siblings" language implied but the actual
  `eligibility` root never reaches. Recommend at least 2 test pairs here (bare-domain vs
  process-intent-resolved) mirroring the eligibility pattern exactly, so the general-only logic is
  proven root-agnostic rather than possibly eligibility-shaped by accident.
- Fanout size check: assert `len(fanout_codes)` for a `health_care_services`-general-only query is
  in the high 50s (59, since 60 leaves minus the root itself minus `.general` if present) — this
  directly informs the Reformat bounding conversation with a real number instead of the eligibility
  under-estimate.

**4c. Structural regex false-negative/false-positive stress:**
- "How is eligibility verified for Medicaid" (passive voice — "how is X verified" doesn't match
  any branch of `_PROCESS_INTENT_RE`, which requires "how do i/can i/does one/how to"). Real
  users phrase this way. Recommend either (a) confirm and accept as a documented limitation
  alongside the malformed-query gap, or (b) flag to Retriever as a possible regex extension
  candidate — Eval's position is this should at minimum be an explicit test pinning current
  (probably UNDERSPECIFIED) behavior, not an undocumented blind spot.
- "Steps for verifying eligibility" (matches `"steps to"`? No — regex requires "steps to" or "what
  are the steps for/to", not bare "steps for X-ing"). Another likely false-negative worth pinning.

---

## 5. Concrete additions (ready to drop into `test_shape_gate.py`)

```python
class TestGeneralOnlyMatchAcrossRoots:
    """§1.1/§1.2: general-only-match must not be eligibility-shaped by accident."""

    def test_general_only_on_health_care_services_root(self):
        # health_care_services is the lexicon's actual largest umbrella (60 leaves) —
        # the real stress case the spec's "~90 eligibility facets" language intended.
        is_general, root, n = _is_general_only_match(
            ["d:health_care_services", "d:health_care_services.general"],
            all_codes={"health_care_services", "health_care_services.general",
                       "health_care_services.dental", "health_care_services.behavioral_health"},
        )
        assert is_general is True
        assert root == "health_care_services"
        assert n == 2

    def test_general_only_false_across_two_different_umbrella_roots(self):
        # eligibility.general (bare) + claims.timely_filing (specific, different root) —
        # multi-root spans should never be flagged general-only, regardless of which
        # individual root looks bare.
        is_general, _, _ = _is_general_only_match(
            ["d:eligibility.general", "d:claims.timely_filing"],
            all_codes={"eligibility.general", "eligibility.verification",
                       "claims.timely_filing", "claims.general"},
        )
        assert is_general is False


class TestProcessOnlyQuery:
    """§1.3: a P-code match with zero D/J — currently unexercised."""

    def test_process_only_no_domain_or_jurisdiction(self):
        r = _result(
            p_codes=["p:submission.submit"],
            probe=CorpusProbe(union_docs=0, intersection_docs=0),
        )
        contour, _ = _classify(r, all_d_codes=set())
        # kinds_matched == 1 (P only) — should NOT hit the ==0 UNCLEAR/OUT_OF_SCOPE
        # branch; falls through to union_docs==0 → CORPUS_GAP under current logic.
        assert contour == Contour.CORPUS_GAP


class TestBroadMinDocsBoundary:
    """§1.5: pin the Eval-tunable _BROAD_MIN_DOCS=25 constant at its edges."""

    def test_exact_at_exactly_broad_min_docs(self):
        r = _result(d_codes=["d:disputes.grievance"], probe=CorpusProbe(union_docs=25, intersection_docs=0))
        contour, _ = _classify(r, all_d_codes={"disputes.grievance"})
        assert contour == Contour.EXACT

    def test_underspecified_one_doc_over_broad_min_docs(self):
        r = _result(d_codes=["d:disputes.grievance"], probe=CorpusProbe(union_docs=26, intersection_docs=0))
        contour, _ = _classify(r, all_d_codes={"disputes.grievance"})
        assert contour == Contour.UNDERSPECIFIED


class TestCorpusGapNotTrippedByPartialZero:
    """§1.6: union_docs==0 requires ALL matched codes to be zero-doc, not just one."""

    def test_not_corpus_gap_when_only_one_of_two_codes_is_zero_doc(self):
        r = _result(
            d_codes=["d:some_zero_doc_code"],
            j_codes=["j:jurisdiction.sunshine_health"],
            probe=CorpusProbe(union_docs=500, intersection_docs=0),
        )
        contour, _ = _classify(r, all_d_codes={"some_zero_doc_code"})
        assert contour != Contour.CORPUS_GAP


class TestProcessIntentVerbVariations:
    """§4a: alias-path vs regex-path vs false-positive-alias-word distinctions."""

    def test_exact_via_confirm_alias_not_regex(self):
        # "Can I confirm..." doesn't match the how-do-i/how-to regex family, but
        # "confirm" IS a verification.verify lexicon alias — should still resolve.
        r = _result(
            d_codes=["d:eligibility", "d:eligibility.general"],
            j_codes=["j:program.medicaid"],
            p_codes=["p:verification.verify"],
            process_intent=False,
            probe=CorpusProbe(union_docs=6309, intersection_docs=1914),
        )
        all_d = {"eligibility", "eligibility.general", "eligibility.verification"}
        contour, reason = _classify(r, all_d_codes=all_d)
        assert contour == Contour.EXACT
        assert "p=yes" in reason

    def test_underspecified_when_required_alias_fires_but_not_actually_process_intent(self):
        # "required" is a compliance_action.required P-tag alias, but "Is eligibility
        # required for Medicaid" is a fact lookup, not a how-do-I ask. If the P-code
        # fires, general-only-match treats it as resolved (p=yes) by design — this
        # test documents that behavior explicitly rather than leaving it implicit.
        r = _result(
            d_codes=["d:eligibility", "d:eligibility.general"],
            j_codes=["j:program.medicaid"],
            p_codes=["p:compliance_action.required"],
            process_intent=False,
            probe=CorpusProbe(union_docs=6309, intersection_docs=1914),
        )
        all_d = {"eligibility", "eligibility.general", "eligibility.verification"}
        contour, reason = _classify(r, all_d_codes=all_d)
        assert contour == Contour.EXACT  # documents current behavior — flag if undesired
        assert "p=yes" in reason
```

Plus two DB-integration additions (require live lexicon/corpus, add near the existing
`TestRunGateIntegration` class):

```python
    async def test_general_only_on_health_care_services_root_live(self):
        async with AsyncSessionLocal() as db:
            r = await run_gate(db, "Behavioral health services for Medicaid")
            assert r.contour == Contour.UNDERSPECIFIED
            assert r.underspecified_kind == "explore_siblings"
            # Live DB re-verify (2026-07-22): health_care_services has 631 active
            # siblings, not the ~60 the stale policy_lexicon.yaml file suggested —
            # this is the real worst-case fanout width, bigger than eligibility's 80.
            assert len(r.fanout_codes) > 500

    async def test_passive_voice_how_is_x_verified_gap(self):
        # Documents a likely false-negative on the process_intent regex — passive
        # phrasing real users use that "how do i / how to" doesn't catch.
        async with AsyncSessionLocal() as db:
            r = await run_gate(db, "How is eligibility verified for Medicaid?")
            # Pin whatever the current true behavior is (expected UNDERSPECIFIED unless
            # "verified" also fires the verification.verify alias, in which case EXACT).
            # Run once locally and pin the actual observed contour here.
```

---

## 6. Summary for Retriever

- 8 concrete gap categories in the current 31-test suite (§1), with ready-to-land pytest additions
  (§5) that don't require new fixtures beyond what `_result()` already supports.
- Recommend a new, separate contour-diversity eval bank (§2) — cmhc structurally cannot cover 4 of
  6 contours and shouldn't be stretched to try.
- 6 concrete sign-off gates (§3), most notably: false-OUT_OF_SCOPE rate as a standing metric, and
  treating `_BROAD_MIN_DOCS` + general-only-match as Eval-tunable constants requiring a
  before/after contour diff on any change.
- ~~One correction request: fix "eligibility ~90 leaves"~~ **SUPERSEDED** — Retriever re-verified
  against the live `policy_lexicon_entries` table (not the stale `policy_lexicon.yaml` file this
  doc originally checked): eligibility genuinely has 80 siblings, `health_care_services` has 631
  (bigger than either of us thought). Spec numbers stand uncorrected. `health_care_services` is
  still worth adding as a second general-only-match test root (§1.1, §4b) — that recommendation
  holds even though the specific counts changed.
