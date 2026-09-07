# Sourcing request contract

**Between:** Service Line Registry (consumer) and the Deep Research state machine (producer),
with Mobius chat as the transport in between.
**Status:** DRAFT — not agreed. Registry has built its half against it; Deep Research has not signed.
**Supersedes:** nothing. This is the first written form of a seam that has been running unwritten
since the first sourcing run.

---

## 0. Why this exists

The seam was never written down, so both sides drifted into prose and the drift was silent
until a backlog filled with the wrong work.

Measured, 2026-09-07:

| | |
|---|---|
| sourcing attempts recorded | 225 |
| filed as `not_answered` | 125 |
| governing rules named by a service line | 18 |
| **of those, present in the corpus and chunked** | **16 of 18** |

Three attempts filed under the same `not_answered` outcome:

- *"the full text of Rule 59G-4.087 … are not present"* — 59G-4.087 is held, 13 chunks, 8,152 chars.
- *"confirms only that rule 59G-8.700 is referenced in a policy index"* — 59G-8.700 is held, 104 chunks.
- *"the requested information is not in the provided documents"* — ambiguous; unfalsifiable as written.

Two were retrieval failures reported as corpus absences. Had we worked that backlog we would have
sent acquisition requests for documents already in hand. Only 59G-4.100 and 59G-4.280 are genuine
absences, and both are 75-character stubs rather than missing files — a third repair again.

None of this is anyone's mistake, and — this is the important part — **none of it is a missing
feature on the producer's side.** The state machine already diagnoses every one of these distinctions
and already routes each to an owner. The Registry has been asking with a prose question and reading
back a prose answer, throwing all of it away in transit.

So this contract is not a specification of work to be built. It is an **adoption**: the Registry takes
the state machine's existing vocabulary verbatim, stops maintaining a parallel one, and asks for
exactly two things it does not already have.

---

## 1. What already exists

Verified directly against `research.*` in `mobius_rag`, 2026-09-07. This is not a proposal.

**An actor-attributed event log** — `research.ledger`, 182 rows:

```
requester   asked 27          judge     batch_round 62   kept 37   refused 11
drafter     answered 12       arbiter   dispatched 4     accepted 4
assembler   typed 12          executor  executed 2       refused 7
recorder    handed_over 1     held 1                     drafter  reconnoitred 2
```

**Typed extraction with per-field provenance** — `research.attempt.evaluator_verdict`. The assembler
does not return a sentence; it returns fields, each with its own quote, document and scope:

```jsonc
{"name": "limit_1",
 "value": {"amount": 104, "period": "state_fiscal_year", "per_whom": "recipient",
           "limit_type": "units", "unit_definition": "quarter hour (15 minutes)"},
 "quote": "Medicaid reimburses a maximum of 104 quarter-hour units (26 hours) …",
 "scope": "Florida Medicaid TBOS, H2019 HR individual and family therapy",
 "document": "Behavioral Health Overlay Services"}
```

**A judge that checks each field and says why it dropped it** — the same verdict's `critique`,
with `check`, `issue`, `authority_tier`, `supported`, and a reason in words.

**A diagnoser that classifies the failure and names its owner** — `research.diagnosis`, 32 rows:

```
absent_from_source → escalate      not_retrievable    → reindex     not_in_corpus  → acquire
wrong_source_chosen → refine       no_governing_rule  → registry    exhausted      → refine
question_incoherent → registry     authority_incoherent → registry  corroborated   → refine
```

**A request shape with slots already in it** — `research.request.expects` and
`.extraction_schema`, both live, both used by other consumers.

**A console** — `deep_research/render_console.py`, rendered entirely from `research.*` with no
hand-authored data.

### 1.1 The Registry has not been using any of it

34 requests exist with `consumer='service_line_registry'`. The sourcing script does not create them —
it posts a prose question to `POST /chat` and polls `/chat/response/{cid}` for a prose `message`.
`expects` is null on every registry request. The typed extraction and the judge ran anyway, on an
unguided request, and their output was discarded in favour of the prose.

And the results have nowhere to land. `research.request.subject_type='standard_requirement'` is set
on 9 registry requests, but `subject_id` holds a composite string — `bh_therapy/service_limit_H2019_HR`,
`bh_assessment/psych_eval_provider` — not a requirement id. **Zero of the nine join to a row in
`service_line.standard_requirement`.** That is the mechanical reason sourcing has run through prose:
with no key, a typed result cannot be filed, so the prose answer was the only thing a script could use.

Two diagnoses have been addressed to `registry` — to us — and unresolved since 2026-08-22:

| gap_class | subject | what it says |
|---|---|---|
| `no_governing_rule` | `molina_fl` | *"service_line.line(molina_fl).rule_ref is null"* |
| `question_incoherent` | `bh_therapy` / H2019 | *"H2019 is not bound to bh_therapy — it belongs to bh_intervention, bh_medication_mgmt, fact"* |

The second is the H2019 routing collision the Registry escalated to Chat Master as an unowned
mystery. It had already been diagnosed, precisely, and filed to us. Nobody was reading the queue.

---

## 2. The unit of work

One request resolves **one requirement against one governing document**.

```
task = (line_key, requirement_type, code?, qualifier?)
```

This is the grain `service_line.standard_requirement` already uses, so a task maps 1:1 to a row and a
result has exactly one place to land. It is also the grain `research.request` already supports:
`subject_type='standard_requirement'`, `subject_id=<requirement id>`.

**Not negotiable:** requests are never batched into "tell me everything about this service." A batch
answer cannot be filed, cannot be reviewed one decision at a time, and cannot be partially repaired.
A run over a service line is N tasks, each independently resolvable, each independently failing.
8 of the 34 existing registry requests are `subject_type='batch'`; those are the legacy shape.

---

## 3. The request — filling fields that already exist

Registry stops sending a prose question and starts filling `expects` and `extraction_schema`:

```jsonc
{
  "consumer":     "service_line_registry",
  "subject_type": "standard_requirement",
  "subject_id":   "8814",
  "jurisdiction": "Florida Medicaid",
  "question":     "Does H2015 HQ require prior authorization?",
  "expects":      ["required", "threshold_units", "threshold_period"],
  "extraction_schema": {
    "required":         "boolean — does the rule require prior authorization",
    "threshold_units":  "integer or null — units above which authorization is needed",
    "threshold_period": "enum day|week|month|state_fiscal_year or null"
  },
  "governing": {"rule_ref": "59G-4.031", "document_id": 8814, "resolvable": true, "chunks": 80}
}
```

`expects` replaces the compound prose question (*"…and if so after how many units or under what
conditions"*), which asked two things in one sentence and reliably returned a paragraph.

`governing` is the one field the request shape does not have today. See §6.

---

## 4. Findings are a projection of `gap_class`, not a rival taxonomy

The Registry does **not** define its own outcome vocabulary. It projects the state machine's onto the
four states a reviewer must act on differently, and stores the original alongside so nothing is lost.

| `gap_class` | registry `finding` | closes it? | repair owner |
|---|---|---|---|
| `sourced`, `corroborated` | `stated` | yes | — |
| `absent_from_source` | `silent` | **yes** | — |
| `not_retrievable` | `unresolved` / `retrieval_miss` | no | Retriever (`reindex`) |
| `not_in_corpus` | `unresolved` / `not_held` | no | Acquisition (`acquire`) |
| `wrong_source_chosen` | `unresolved` / `wrong_source` | no | Deep Research (`refine`) |
| `exhausted` | `unresolved` / `exhausted` | no | Deep Research |
| `no_governing_rule` | `unresolved` / `registry_gap` | no | **Registry** |
| `question_incoherent` | `unresolved` / `registry_gap` | no | **Registry** |
| `authority_incoherent` | `unresolved` / `registry_gap` | no | **Registry** |
| `open` | — still running | — | — |

`absent_from_source` mapping to a **closing** state is the substantive claim here. It means the
document was read and does not address the question — that is an answer, and today the Registry files
it as an unsourced gap and re-asks it forever.

---

## 4.5 Ask 1 — a join key that resolves

`subject_id` must be the `service_line.standard_requirement.id` when `subject_type` says so, or the
subject must become structured (`{line_key, requirement_type, code, qualifier}`). Either is fine;
the composite string is not, because it cannot be joined and cannot be validated. This is the
smallest change on the list and it unblocks every other one — without it a typed finding still has
nowhere to be filed, and the pipeline stays prose-bound no matter what else improves.

Registry will carry the mapping in `service_line.sourcing_link` for requests already made.

---

## 5. Ask 2 — explicit negation

There is no `gap_class` for *"the document says no requirement applies."*

The Registry holds 7 such statements, filed identically to the 82 that state a requirement.
`bh_community_support` has *"no service-specific authorization criteria"* stored exactly the way
`behavior_analysis` has *"require prior authorization"*. Any query counting sourced prior-auth
requirements gets 8 and is wrong about 5.

`sourced` covers it today, because it *is* sourced. But `sourced` cannot distinguish a rule from its
negation, and to a biller those are opposite instructions.

**Ask 2 — add `none_applies` to the `gap_class` vocabulary.** A document that explicitly excludes a
requirement is a positive finding, not a silence and not a statement.

`silent` and `none_applies` both mean "no requirement" to a biller and are **not** the same fact. One
is defensible in an audit; the other is an absence of evidence.

---

## 6. `governing` — supplied by Registry, so `silent` is decidable

A model cannot tell *"this document is silent"* from *"I did not find this document"* unless it is
told which document it was supposed to read. Only the Registry knows: 18 of 31 lines carry a
`rule_ref`, and the Registry can resolve each to a document id and chunk count in one query.

**Ask 3 — accept `governing` on the request, and treat it as binding.** If Registry states the
document is held with 80 chunks and the state machine could not read it, that is `not_retrievable` by
construction — never `not_in_corpus`. This is exactly the misclassification in §0, and it becomes
structurally impossible rather than a judgement call.

Registry emits `governing_resolved` into the event log before the request goes out. It depends on
nobody, which is why the review surface can be built and be useful before either ask lands.

### 6.1 `silent` must be proved

A bare claim of silence is unfalsifiable. Registry accepts `absent_from_source` → `silent` only with
a document id and the sections read. A reviewer must be able to check a negative the same way they
check a positive. `hierarchical_chunks.section_path` already carries this.

---

## 7. The stream and the audit log are one object

The Registry's review surface shows a live run and, later, replays why a value was chosen. These are
the same rows read twice — live is a tail, provenance is a replay, one renderer. There is deliberately
no second provenance store, because a provenance store written separately from the run drifts from it.

`research.ledger` is that object. It is actor-attributed, ordered, and already written. Registry tails
it by `request_id`.

**Ask 4 — carry `request_id` on every ledger row, and emit one row per actor step.** Today the ledger
is written at coarse points; a live view needs the judge's `kept`/`refused` and the diagnoser's
classification to arrive as they happen, attributed to the actor that produced them. The vocabulary
does not change — only its completeness and its key.

**Narration is not provenance.** `thinking` lines are welcome on the wire for a human watching, but
they are display-only and are not stored. If the only record of why a value was chosen is a sentence a
model wrote about itself, the defect in §0 has been rebuilt inside the audit log.

---

## 8. Division of ownership

| | Registry | Deep Research |
|---|---|---|
| names the governing document, `resolvable`, `chunks` | ✅ | |
| names the slots (`expects`, `extraction_schema`) | ✅ | |
| owns the `gap_class` / actor / action vocabulary | | ✅ |
| reads the document, types the value, judges the fields | | ✅ |
| classifies the gap and names the repair owner | | ✅ |
| works the `action='registry'` queue | ✅ | |
| projects `gap_class` → `finding` for reviewers | ✅ | |
| stores review state and human decisions | ✅ | |

The Registry does not re-judge, re-extract, or re-classify. Where it disagrees, it files a repair —
it does not maintain a shadow answer.

---

## 9. Compatibility

- A request without `expects` is answered as today. Registry marks the result `origin: interpreted` —
  a reviewer must read it properly — and does **not** count it as typed.
- A `gap_class` the Registry does not recognise maps to `unresolved` / `unknown_class` and raises,
  rather than being silently bucketed. An unrecognised state must be loud.
- Nothing here requires the producer to move before the consumer benefits: §6's `governing_resolved`
  and §4's projection are Registry-side and land immediately.

---

## 10. Open, for sign-off

1. **Where `none_applies` is decided** — assembler, judge, or diagnoser. It is arguably a judge call,
   since it is a claim about what the document establishes.
2. **Whether `expects` should be per-requirement-type in the Registry or a shared schema registry.**
   Ten types, listed in §11. Duplicating them invites drift.
3. **Confidence semantics.** Currently a model self-report. It should mean something calibrated or be
   dropped — a number nobody can interpret is worse than no number.
4. **Re-sourcing policy.** When a document is superseded, which findings re-open automatically, and
   does a human-confirmed finding survive a document change?

---

## 11. Slots per requirement type

Registry supplies these as `expects`. The value is what chat, the review surface and every future
consumer read; the quote is evidence for it. A sentence can be re-read but not queried — *"which
services need prior authorization above a unit threshold"* is unanswerable against 89 paragraphs
without a model, which is the cost this contract exists to remove.

| requirement_type | expects |
|---|---|
| `prior_authorization` | `required` · `threshold_units` · `threshold_period` |
| `place_of_service` | `pos_codes[]` · `settings[]` · `telehealth_allowed` |
| `age_population` | `min_age` · `max_age` · `population` |
| `supervision` | `supervisor_credential` · `ratio` · `contact_type` |
| `provider_qualification` | `credentials[]` · `licence_levels[]` |
| `credentialing` | `enrollment_required` · `certification` · `programme` |
| `documentation` | `elements[]` · `retention_period` |
| `coverage_criteria` | `criteria[]` · `diagnosis_required` |
| `referral_order` | `orderer_credential` · `order_required` |
| `setting` | `facility_type` · `staffing` |

`null` in a slot means the document did not address it, and is distinct from the slot being absent
from the request.

---

## 12. Change discipline

Changes go to this document **first**, and only then to either side's code. Same rule as the
Lexicon↔Registry contract, and for the same reason: two owners, one seam, and a failure mode that is
invisible until a backlog fills with the wrong work. It already happened once — and a queue addressed
to us sat unread for sixteen days.
