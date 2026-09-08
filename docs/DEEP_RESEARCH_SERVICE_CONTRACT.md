# Deep Research — the service contract

What a caller must give us, what they will get back, and what they are allowed
to decide. The caller may be a person or a service; nothing here distinguishes
them.

> **The one promise.** Every question reaches an answer or a stated reason.
> Nothing is left open forever, and nothing is closed quietly.
>
> — Ananth: *"our responsibility is to make sure each transaction (query) is
> closed out, and that's our north star."*

---

## 1. What a good input looks like

| field | required | what it is |
|---|---|---|
| `consumer` | yes | who is asking. A person, a registry, a playbook, another agent. Decisions come back to this name. |
| `subject_id` | yes | `line_key/aspect` — **readable on both halves**. `bh_overlay/medical_necessity`, not `bh_overlay/125`. A numeric id from your own table is not a name and renders as a bug. |
| `question` | yes | one question, in the words a document would use. |
| `evaluator_prompt` | yes | how to judge an answer. We do not know what a good answer looks like for your domain; without this we cannot grade one. |
| `extraction_schema` | yes | the fields you want, and the vocabulary each may take. |
| `required` | no | fields you cannot use the record without. **See §4 — this is a statement about you, not about us.** |
| `authority` | no | `standard` (published authority only) · `any_cited` (any source the answer cited) · `lead` (uncited; NOT certifiable). Defaults to `standard`. |
| `due_at` | no | when you need it. Absent, a policy floor applies. |

### The two input mistakes that cost the most

**A schema whose vocabulary cannot express the document.** A `deadline_unit` of
`days | business_days | months | calendar_days` met a manual saying "one (1)
year". The extractor converted to `12 months` to fit; the judge correctly
refused the conversion against its own quote; the machine then reported the
document as *silent*. Nothing was silent. **If your enum cannot say what the
source says, we will tell you rather than bend the value** — a converted
deadline is acted on just as confidently as a stated one.

**Requiring what you already know.** `payer` was required and the instructions
never asked for it, so a correct answer was refused for not restating a value
present in the question. Identity is an INPUT. Pass it as `known` and it is
recorded with **no quote and no document**, because pretending the corpus stated
it is the failure this machinery exists to prevent.

---

## 2. What comes back

```
sourced     answered. Fields kept, each with its own verbatim quote and the
            document id it came from.
abandoned   closed with a stated reason in `quiet_because`. Not silence.
open        still being worked.
escalated   we cannot settle it; a decision is waiting for YOU (§3).
halted      deliberately stopped.
```

Every record carries:

- `accepted` — **did the answer stand up.** `bool(kept)`.
- `meets_required` — **did it satisfy YOUR required list.** Separate on purpose.
- `missing_required` — which of your fields were not produced.
- per field: value, verbatim quote, document id, and the judge's reasoning.
- per field: `check` — `judged` (checked against the answer), `given` (you
  supplied it; not a corpus finding), or `human` (a person overruled the judge,
  recorded in `research.judge_override` with the verdict it overrode).

**Read `meets_required`, not just `accepted`.** They mean different things.

---

## 3. What you may decide

We come back to you only when the machine cannot settle it. Ask
`GET /api/research/decisions?consumer=<you>`; each option states what it will
do, in text generated from the code that does it. Answer with
`POST /api/research/decide {resolution_id, chose, why}`.

| choice | what happens |
|---|---|
| `stop` | question CLOSED, your reason on the record, never asked again |
| `genuinely_silent` | recorded as a finding that the source is silent — see the warning below |
| `widen_authority` | **your requirement drops one step**; asked again at the lower bar, and what is found is recorded as meeting *that* bar. At the bottom of the ladder the question is closed instead |
| `another_document` / `substitute` | re-asked against the document you name |
| `acquire` | an acquisition is raised; the question waits for it |
| `ask_named` / `rewrite` | the machine does it itself — you are not asked |

Plus, per refused field:
`POST /api/research/override` — `approve` the judge was wrong · `correct` supply
the value · `uphold` the refusal stands (**the default; omission accepts
nothing**).

> **On `genuinely_silent`.** A negative finding is acted on exactly like a
> positive one — a biller reads "no prior authorisation required" and does not
> seek it. We will not assert silence from having failed to find; that is why
> the choice is yours and why it is recorded with your name on it.

### Relaxing a requirement is yours alone

You set the bar. We honour it while it stands and report honestly when we cannot
meet it. **We never quietly lower it.**

> *"we did not find an authoritative doc and they had asked for it; we honoured
> the contract and we tried to get one but we could not — then the caller can
> override that requirement. Our intent is to close everything."*

A question that can never be answered under its own requirement is otherwise
open forever, which breaks the one promise. So the relaxation is offered as a
choice, and taking it is recorded as your decision.

---

## 4. We do not validate your request

> *"we are not here to validate the requestor's .. the question is did it meet
> the requestor's intent."*

A `required` list you got wrong will not turn a good answer into "not answered".
Acceptance is about the ANSWER. Your unmet requirements come back as a caveat
about your request, and a consumer that genuinely cannot store a record without
a field refuses it on its own contract — **that call is yours, not ours.**

---

## 5. Deadlines: when the clock is up, we LOOK

> *"even though we will be waiting on some work, when the time is up we should
> just check if the required condition was met and we were just not informed, or
> some other task gave us a different avenue."*

**Absence of notification is not evidence of incompletion.** A document can
arrive by another route; a second question can answer the first; a person can do
the work and never come back and say so. Every one of those satisfies the
condition and none of them sends us anything.

So a task is not late because its deadline passed. It is late because the
deadline passed **and the condition is still unmet, checked at that moment**.
`settle_due()` re-evaluates every past-due row before anything reports lateness,
and distinguishes three outcomes:

- **met after all** — closed, noted as satisfied without being reported.
- **genuinely late** — checked now, still not done.
- **could not check** — our own outage. Not late; saying otherwise is an
  accusation built on our silence.

Two clocks are reported apart: the TASK clock and the QUESTION clock. A day
where every task landed on time and no question closed is a good day for
everyone except the caller.

---

## 6. What we will never do

- Assert a source is silent because we failed to find something.
- Convert a value to fit a schema.
- Record a caller-supplied value as though a document stated it.
- Lower a requirement you set without you deciding it.
- Report a task late without checking whether it is done.
- Close a question without a reason a person can read.
