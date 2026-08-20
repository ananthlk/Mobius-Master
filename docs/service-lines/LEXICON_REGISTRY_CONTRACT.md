# Service Line ↔ Lexicon contract — SIGNED

**Ruling:** Ananth, 2026-08-19 — hybrid ownership
**Parties:** Service Line Registry · Lexicon (`2a - Lexicon`)
**Artifacts:** [`lexicon-packets.json`](./lexicon-packets.json) (registry) ·
[`lexicon-line-mapping.reconciled.json`](./lexicon-line-mapping.reconciled.json) (Lexicon)
**Status:** in force. Any change by either party is written here first.

---

## 1. Ownership

A service line is describable at six levels. Ownership splits at level 4.

| Level | | Authored by |
|---|---|---|
| 1 | identity — the line name and how people say it | **Registry** |
| 2 | authority — the statute or rule as people name it | **Registry** |
| 3 | payment — the billing shape as billing staff say it | **Registry** |
| 4 | `rendered_as` — clinical concept per (code, modifier) | **Lexicon** |
| 5 | `classified_by` — diagnosis vernacular | **Lexicon** |
| 6 | `grouped_to` — DRG admission vernacular | **Deep Research** |

**93 registry slots · 145 Lexicon slots**, of which Lexicon has authored 52
(66% of levels 4–5). The 66 `grouped_to` slots are Deep Research's because DRG
admission language is not a clinical concept.

Lexicon may pass a courtesy `d:` suggestion into a registry slot; the registry
still authors it. The registry may propose into a Lexicon slot; Lexicon still
decides.

---

## 2. Standing rules

1. **Keyed at (code, modifier), never the bare code.** `H0031` is four
   different billable services. An alias set on the bare code collapses four
   services and four rates.
2. **`TS` is not "established patient" globally.** On `H0032` and `T1007` it
   turns treatment plan *development* into *review*. Modifier meaning is
   per-code.
3. **The SUD/MH split is carried by the code, not the words.** `H0001` is the
   substance-use twin of `H0031` with near-identical English.
4. **Neither party writes into the other's store.** Nothing here has been
   written to `policy_lexicon_entries`. Lexicon does not write
   `service_line.*`.
5. **Registry proposals are evidence, not mappings.** A lexical match is
   labelled as such and carries no confidence score.

---

## 3. What was exchanged, and what verification found

The registry verified every one of Lexicon's six drops against its own data
rather than accepting them. **All six were correct.** 23 line-pairings rejected,
32 Lexicon-authored mappings adopted; lines with no `d` code fell from 2 to 1.

### 3.1 Root cause of the registry's noise — a two-sided defect

| Side | Defect |
|---|---|
| **Registry** | Matched *inside* words, and used the d-code leaf as a match term. `"denti"` matched inside resi**denti**al; `"rehab"` (leaf of `provider.healthsouth.rehab`) inside psychosocial re**hab**ilitation; `"proc"` inside **proc**edures; `"behav"` inside **behav**ioral. |
| **Lexicon** | Carries truncated stems as `strong_phrases`. `health_care_services.dental` literally lists `"denti"`; `billing_codes.procedure_code` lists `"proc"`. **857 active `d` codes carry a strong_phrase of ≤5 characters with no space** — including `"em"`, `"ba"`, `"bh"`, `"ct"`, `"xr"`, `"np"`, `"fs"`. |

The registry has fixed its side. The stem finding is Lexicon's to judge — it
affects `corpus_search_lexicon` expansion generally, not just this mapping.

### 3.2 One drop the registry accepts but distinguishes

`billing_codes.evaluation_and_management` on the `evaluation_management` line
matched on the **full phrase** "evaluation and management" — the pairing was
correct, not noise. Dropped because `billing_codes.*` is structural rather than
a clinical concept, which follows from §1. Recorded so it is not re-proposed as
a bug fix later.

### 3.3 One finding returned to Lexicon

Rule 2 was breached in exactly the place it warned about. Of codes carrying more
than one modifier in a line, **12 pairs correctly differ and 3 collapsed** to
identical vernacular:

| Line | Code | Slots sharing identical aliases |
|---|---|---|
| `bh_assessment` | `H0001` | `HO` (new patient) · `TS` (established patient) |
| `bh_medication_mgmt` | `H0032` | `TS` (plan **review**) · none (plan **development**) |
| `bh_medication_mgmt` | `T1007` | `TS` (plan **review**) · none (plan **development**) |

The structural grain survived — they are separate slots — but the aliases do
not distinguish them, so a query can reach the pair and not tell which service
is meant. `H0032` is the exact case rule 2 names.

---

## 3.4 `j:service_line` — line-precise routing (agreed 2026-08-19)

Concept tags alone cannot serve by line. Verified: the three lines sharing
`substance_use_disorders` — `sud_residential`, `withdrawal_management`,
`marchman_act` — carry **zero** `rendered_as` codes between them, so
code+modifier cannot disambiguate exactly where the ambiguity is. More broadly
**24 of 31 lines have no HCPCS code at all**, and **80 of 81 held AHCA policy
documents contain no code**, so a code filter reaches the fee schedule that
prints a code, never the policy that defines the service.

Lexicon therefore built a `j:service_line` axis. Registry verified it live:
**32 entries** (`service_line` container + 31 children), all 31 line keys
present, none missing, none extra, `strong_phrases`/`aliases` empty so the
corpus is untouched until doc-side assignment.

| Side | Owner |
|---|---|
| The axis, query expansion, doc-side application | **Lexicon** |
| The doc→line assignment seed | **Registry** |
| Identity vernacular feeding query phrases | **Registry** (§1 level 1) |

Two constraints, both written into Lexicon's spec:

1. **Provenance in, not concept in.** An assignment must come from the
   document's own provenance, never inferred from a concept tag — inference
   would re-import the ambiguity the axis exists to remove.
2. **Multi-valued.** A document may carry several line tags. The CBH fee
   schedule is the cited source for **six** lines.

Seed: [`service-line-doc-assignment.seed.json`](./service-line-doc-assignment.seed.json)
— **20 assignments, 15 documents, 9 of 31 lines**, from two provenance bases:
`rule_ref` (the document is the governing policy) and `cited_source` (the
document is where the line's bindings were read from).

## 4. Open gaps

| Gap | Owner | Note |
|---|---|---|
| `specialized_therapeutic` — no `d` entry | Lexicon | Concept not covered |
| "Marchman Act" as a literal term | Deep Research | Concept maps to `substance_use_disorders`; the term itself is missing |
| 66 `grouped_to` / DRG slots | Deep Research | DRG admission vernacular |
| 3 collapsed modifier pairs (§3.3) | Lexicon | Rule 2 |
| 857 short strong_phrases | Lexicon | §3.1 |
| 22 of 31 lines have no assigned document | Deep Research | Route by phrase, retrieve nothing line-specific until the governing doc is held |

**Structural finding, unresolved:** the `d` axis is condition-shaped, not
service-shaped. Of 57 codes under `health_care_services.behavioral_health`, most
name conditions — PTSD, OCD, agitation, serotonin, stigma. **Zero case-management
`d` codes exist** across all 3,702, while the registry binds three
case-management lines. Service-line questions will keep missing while that holds.

---

## 5. Change protocol

Either party changing the mapping writes the change **here first**, then to
their own store. Registry state lives in `service_line.line_lexicon_d`:

| `state` | Meaning |
|---|---|
| `proposed` | Registry lexical candidate — evidence only, never adopt on its own |
| `confirmed` | Lexicon authored or agreed it |
| `rejected` | Lexicon dropped it; kept so it is not re-proposed |
| `requested` | A concept the registry binds that the vocabulary cannot express |

Current: **32 confirmed · 42 proposed · 23 rejected · 2 requested**.

---

## 6. Sign-off

| Party | Position |
|---|---|
| **Lexicon** | Reconciled mapping delivered; supersedes the registry's fuzzy first pass. Asked to be verified rather than trusted. |
| **Service Line Registry** | Verified all six drops independently — all correct. Applied the reconciliation. Returns two findings (§3.1 stems, §3.3 collapsed pairs) and accepts §3.2 with a distinction. |

Signed on the evidence above, not on summary.
