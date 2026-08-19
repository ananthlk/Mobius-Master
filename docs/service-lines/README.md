# Service Line Registry

The master scope contract: what Mobius serves, and what every module owes each line.

Schema `service_line.*` in `mobius_rag`. Migration: [`033_service_line_registry.sql`](../../mobius-payor/migrations/033_service_line_registry.sql).

## What it does not hold

Two deliberate exclusions. Both exist to stop the registry becoming a second copy of something that already has an owner.

| Not held | Owner | Why |
|---|---|---|
| Rates, fees, weights, DRG relative weights | `facts.*` (Fact Store) | Different clock — a rate changes when the payer publishes, the scope changes when we ship |
| Payor-specific variation of any rule | `facts.*` (Fact Store) | Varies by payor, so it is not ours. See *What we own vs. what we source* |
| Code dictionaries | `reference.*` | 74,719 ICD-10-CM, 8,725 HCPCS and 1,330 APR-DRG rows already exist. The registry records which codes *belong to a line*, not what a code means |

The registry **does** hold the service limit and unit definition stated by the state rule (`line_code.general_rule`) — that varies by code, not by payor. Never a dollar amount; the loader drops any statement containing one.

## The binding role

A service line relates to codes in three structurally different ways. Conflating them is what makes inpatient impossible to model.

| `binding_role` | Code system | Meaning |
|---|---|---|
| `rendered_as` | HCPCS / CPT | The procedure code you actually bill |
| `classified_by` | ICD-10-CM | The diagnosis that places an encounter in this line |
| `grouped_to` | APR-DRG | The payment group the encounter resolves to |

An outpatient therapy line is `rendered_as` `H2019` + `HR`. An inpatient psych stay is never *rendered as* anything — it is `classified_by` ICD-10-CM chapter F and `grouped_to` an APR-DRG. Same registry, different binding.

## The qualifier

`line_code.qualifier` carries the second half of a compound key, and `code_system.qualifier_kind` says what it means:

- **HCPCS** → modifier. `H2000`+`HP` (doctoral) and `H2000`+`HO` (master's) are different services in the same document. `H2019` appears six times with six meanings.
- **APR-DRG** → severity of illness (1–4). Same lesson: the grain is a pair, never the bare code.

## Tables

| Table | Holds |
|---|---|
| `line` | 31 service lines — key, authority, payment_grain, scope |
| `line_code` | Code bindings by role, with adjudication state and citation |
| `code_system` | Which dictionaries exist, which we hold, licence constraints |
| `qualifier` | Modifier / severity glossary |
| `code_relation` | Edges — same-day exclusions, bundling |
| `module_obligation` | What each module owes each line, and whether it has delivered |
| `source` | Provenance, including `held = false` for what we still need |
| `linked_store` | Per domain: who holds the standard, what we own, and the question we ask them |
| `line_predicate` | Which Fact Store predicates apply to a line |
| `exception_answer` | One answer per (line, domain, payor): follows_standard or has_exception |
| `code_exception` | Detail for a recorded exception, when one exists |
| `standard_authority` | The regulatory sources we hold the standard from — AHCA, CMS |
| `payor_conformance` | Whether a payor follows the standard or departs from it |

Views: `line_bindings`, `completion` (module scoreboard, with expiry), `payor_requirements`,
`payor_requirement_coverage`, `requirement_resolution` (standard vs delta vs unsourced),
`exception_asks` (what linked stores still owe us).

## Scope and mode

`line.scope` is `serve` or `decline_well`. The second is not a gap — it names a service CMHCs really run that Mobius deliberately does not support, so modules decline correctly instead of missing the question in silence. On those lines Fact Store, Credentialing, Appeals and Analytics are `not_applicable` with a stated reason; Lexicon and Chat still owe work.

## What we own vs. what we source

One rule, not five special cases:

> **The registry owns whatever varies by service code. The linked store owns whatever varies by payor.**

The *standard* therefore sits on different sides depending on which axis it varies on:

| Domain | Standard held by | Registry owns | Linked store owns |
|---|---|---|---|
| `payment` | **registry** | The payment rule by code — unit definition and service limits, as the state rule states them | Fact Store: every payor-specific value — rate, PA, altered limit, required modifier |
| `appeals` | **Appeals agent** | Appeal exceptions by service code — anything about appealing *this code* that departs from the payer's standard | Appeals: the standard process per payer — deadlines, channels, required documents |
| `credentialing` | registry | Who may render, per the state rule (largely carried by the modifier) | Credentialing: payor-specific enrollment beyond the state rule |
| `vocabulary` | registry | The canonical line name, its codes, and aliases | Lexicon: the retrieval index |
| `code_dictionary` | registry | Which codes belong to a line, in what role | `reference.*`: what each code means |

Declared in `service_line.linked_store`, including the exact question the registry puts to each store. For appeals that question is: *"For this service code, does anything depart from your standard appeals process for this payer? If nothing, say so — that is an answer."*

Where the standard is theirs, the registry stores **one answer per (line, payor)** in
`service_line.exception_answer` — `follows_standard` or `has_exception` with a statement.
Nothing more. Pulling their standard's details onto every line duplicates their store and
manufactures permanently-unanswered rows; an earlier revision did exactly that with four
`appeal.*` predicates per line, which surfaced a payer's appeals fax number as a service-line
requirement. `service_line.exception_asks` lists what is still unanswered, per payor.

`follows_standard` is a complete answer and closes the ask. Only `serve` lines are asked —
we do not bill the declined ones, so appeals does not apply.

## Standard vs. payor delta

The registry holds the **regulatory standard** — AHCA for Florida Medicaid, CMS federally (`service_line.standard_authority`). Fact Store holds only where a payor **departs** from it.

A payor that conforms needs no fact. "Standard" is itself an answer, recorded once in `service_line.payor_conformance`, and the value resolves from the registry. That is what keeps the payor axis sparse — source the floor once, record only deltas.

`service_line.requirement_resolution` classifies every requirement as `standard` (registry), `payor_delta` (Fact Store) or `unsourced` (nobody yet). Current state: 81 standard, 21 payor deltas, 64 unsourced.

**Open question for Fact Store:** 42 rows in `facts.payor_fact` carry `payer_key = 'AHCA|FL|Medicaid'`. Under this split those are standard, not payor facts. The view classifies them correctly without moving rows; where they should ultimately live is Fact Store's call.

## Support is computed

`module_obligation.status = 'complete'` carries an `expires_at`. A completion that outlives its expiry, or a corpus republish, drops the line out of supported *before* a customer finds it. Support is never declared by a human flipping a flag.

## Regenerating

The database is the master. `build_master.py` seeded it from AHCA sources; from then on the
JSON and the page are exports and must never be hand-edited:

```bash
python3 scripts/export_catalog.py && python3 scripts/render_page.py
```

Service lines derive from AHCA's own 59G rule decomposition in `docs/ahca-manifests/ahca_BH_sources.csv`. Codes and modifiers are read from AHCA fee schedules held in `document_pages`. Fee schedule page footers name the governing rule — that is the deterministic code→line join. Pages citing two rules leave `adjudicated = false`.

## Open

- **Revenue codes and ICD-10-PCS not loaded** — both needed for facility and inpatient claims.
- **Appeals has not answered for any line.** `exception_asks` shows 21 serve lines × 4 payor scopes open. "Nothing differs" is a valid answer and closes the ask.
- **`payor_conformance` is empty.** Until a payor is recorded as conforming or differing, its requirements read as unsourced even where the standard would answer them.
- **ICD block bindings are unadjudicated.** The chapter F blocks bound to inpatient/ED/CSU lines are clinically sound but not yet traced to a payer rule that says *this diagnosis makes this line payable*.
- **Member eligibility** (SMI designation, age bands, CWSP) is on none of the axes and is not yet a declared exclusion.
- Schema needs review from the Platform Architects DB seat.
