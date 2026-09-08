# Machine integrity: six defects that keep coming back

Written 2026-09-08 by the Payor Policy / Deep Research seat, after a day in
which the same small number of mistakes produced a live 500, a permanently
unopenable sign-in, a decision surface that did the opposite of what it said,
and a card asking a person to certify that a document was silent about
something it plainly states.

None of these were exotic. Every one of them passed its tests, shipped, and was
found by a human looking at the running product. They are written down because
they are not specific to this module — several have already appeared in other
seats — and because each one has a cheap check that would have caught it.

---

## 1. A write nobody reads is indistinguishable from a working one

Eight instances now, across two seats. Today's four:

| what was written | who was supposed to read it |
|---|---|
| `research.ruling.chose` — the option a person picked | the machine, to decide what to do. The column existed; the INSERT never listed it, so every ruling landed `chose=NULL` and "Stop asking" behaved identically to "Acquire it" |
| `gateDecisions()` — disabling controls when signed out | every redraw rebuilt the buttons enabled; the gate ran once at boot |
| `boot()` in the generated page | the generator emitted a page that never called it |
| `verified_by` | **me.** My own check printed `verified_by remains: True` and I moved on |

The last one extends the rule: **a read whose result nobody acts on is the same
defect wearing a check's clothing.**

*Check:* every write path ships with one consumer that reads it back in the same
change. When your own verification prints something surprising, stop.

---

## 2. "Could not check" is not "checked, and it is not there"

Five instances in one module. The worst two reached a human as a question:

- 12 of 12 extracted fields kept, 0 refused, blocked only on a `payer` field the
  schema demanded and the extractor was never instructed to emit → diagnosed as
  **"The document is silent on this"**, with *"the rule genuinely does not say"*
  pre-selected as the recommendation.
- Molina's manual says a dispute is filed "within one (1) year". The caller's
  schema offered `days | business_days | months | calendar_days` — no `year` —
  so the extractor converted to `12 months` to fit and the judge correctly
  refused the conversion against its own quote. Same diagnosis: silent.

**A negative finding is acted on exactly like a positive one.** A biller reads
"no prior authorisation required" and does not seek it. The machine cannot prove
absence from having failed to look, and in a certified store a false negative is
indistinguishable from a real one after the fact.

*Check:* three states everywhere — true / false / **could not look**. Before
writing any "it is not there", ask what would make that a fact about the SOURCE
rather than about your run. Gate a silent-source conclusion on a non-zero count
of things actually judged and refused.

---

## 3. A gate is exercised by getting THROUGH it

`whoami()` shipped with `NameError` on its last line. Every signed-in reader got
a 500 on every request detail. Every test passed — because every test tested
REJECTION (no token, bad token, service down), and the function raises before
reaching the failing line. The one branch a real user takes was the one branch
never executed.

A permanently-locked door passes every rejection test ever written. So does a
door with no key: `localStorage` is per-origin, the console is served from
mobius-payor and the session was issued on the chat origin, so the sign-in gate
was correct, deployed, and **impossible for anyone to pass**.

*Check:* write the success-path test first, with the dependency stubbed to return
a valid subject. Then reintroduce the bug in a copy and confirm the test fails —
otherwise you have a test that agrees with you rather than one that checks you.

---

## 4. Tell the user what will happen — generated, not written alongside

The console offered *"Stop asking — close it as unavailable, with the reason on
record."* Picking it made the sweep set the request back to `open`. **"Stop
asking" caused the question to be asked again**, and all four options behaved
identically because the predicate only checked that *some* ruling existed and
never read which one was chosen.

The label and the behaviour were two sentences that happened to sit near each
other. An option that misdescribes its own effect is worse than no option: it
looks like control.

*Check:* derive the user-facing consequence from the structure the executor
branches on, and stamp it onto the row when the choice is offered, so the page
renders a string it did not compose. Make the unknown case say so rather than
inventing a reassurance.

---

## 5. The requester may not be a person

A question is asked by a *consumer* — a registry, a playbook, a person, another
agent. When the machine cannot settle it, the decision belongs to whoever asked.
That the requester is sometimes human is a property of one caller, not of the
mechanism, and building the decision as a dialog made the human case the only
case.

It also hid a real defect: the free-text endpoint dropped the option id, which a
typed contract makes impossible.

*Check:* if a surface asks a person to choose, ask who the requester could be.
If it could be a service, the options and the answer are an API first and a
rendering second — and the chosen option is validated against the options
actually offered, or a caller can be recorded as having made a choice it invented.

---

## 6. We are not here to validate the requestor

A `required` field list the caller got wrong turned a good answer into "not
answered", then into a corpus diagnosis, then into a human question about
silence. The answer was correct throughout.

> "we are not here to validate the requestor's .. the question is did it meet
> the requestor's intent" — Ananth, 2026-09-08

Acceptance is about the ANSWER. A malformed request is reported back to the
requester as a caveat about their request. A consumer that genuinely cannot
store a record without a field refuses it on its own contract — that call is
theirs, not ours.

Two corollaries that came out of the same case:

- **Identity is an input, not a finding.** Do not ask a model to restate what
  the request already fixes. Supplied values are recorded with no quote and no
  document, because pretending the corpus stated them is the exact failure the
  machinery exists to prevent.
- **Never convert a value to fit a schema.** Where a schema's vocabulary cannot
  express what the document says, emit the document's word and report the gap.
  A converted deadline is acted on just as confidently as a stated one.

---

## An unpaid invoice, filed as a knowledge gap

Service Line Registry read their acquisition backlog and found that 40 of its 62
rows gave the same reason for the corpus being silent:

    extractor error: Anthropic API error 400 ... credit balance is too low

`extract()` had four paths that mean *the extractor never ran* — a 400, an empty
completion, no JSON, unparseable JSON — and all four returned `answered: False`.
`validate()` tested `if not ext.get("answered")` and wrote outcome
`not_answered`, which 044's own comment defines as "chunks retrieved but they do
not answer it": a claim about the CORPUS. Two thirds of another team's backlog
was our billing problem wearing a knowledge gap's clothes, and a repair loop
reading it would have gone and acquired documents to fix an unpaid invoice.
`error` was already legal in the CHECK constraint. One row in 219 used it.

The write-side fix is four lines, with one trap worth naming: the could-not-run
paths now return `answered: None`, and **`None` is falsy** — so the error branch
must be tested FIRST or every row falls straight back into the old bucket with
nothing raising. The test file pins that ordering.

**The half that actually changed what anyone reads.** Relabelling 43 attempt
rows fixed nothing visible, because `sourcing_gap.last_reason` took the MOST
RECENT attempt — and for those 40 rows the most recent attempt was the 400. The
real finding ("the answer explicitly states the rule does not specify
place-of-service settings") sat one round back, unread. `last_reason` now comes
from the last attempt that REACHED the corpus, and our failures live in
`last_error` where they cannot speak for it.

And the surprise, which is the reason to measure rather than assume: the view
gained `never_asked` expecting the backlog to shrink, and it came out **zero**.
Every one of the 62 rows had between one and four attempts that genuinely
reached the corpus. The backlog was real. Only the sentence on it was wrong. A
mislabel is not evidence that the work behind it is phantom.

---

## The shape underneath all seven

Each is a place where **two things that must agree were maintained separately**:
a write and its reader, a status and its meaning, a label and its behaviour, a
test and the branch it claims to cover, a schema and the document, an outcome
label and the field that displays it. The fix is always the same shape — derive one from the other, or assert they match — and it
is always cheaper than the incident.
