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

> **STATUS 2026-09-07 — READ §5.1 FIRST.** The v1 doc-side described below was
> **erased** by nightly rebuilds and is being rebuilt on a durable design (dedicated
> column, not `j_tags`). **Query-side is restored** (32 entries now in QA *and* RAG).
> **Doc-side column is pending** DB-seat DDL + Retriever read-side. Treat the
> "verified it live / 32 entries applied" statements in this section as **history of
> v1**, not current state. §5.1 is authoritative.

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

## 5.1 Change 2026-09-07 — `j:service_line` axis erased by rebuilds (Lexicon)

Registry flagged (verified independently by Lexicon against the live DB) that the
axis recorded live in §3.4 is **gone**, while its doc-side tags partly remain —
the contract had stopped matching the world. State at 2026-09-07:

| | §3.4 (2026-08-20) | now |
|---|---|---|
| `policy_lexicon_entries` `service_line*` (RAG, any state) | 32 | **0** (deleted) |
| same in QA | (never added) | **0** |
| `policy_paragraphs` with a `service_line` j_tag | 592 | **39** |
| `document_tags` with a `service_line` j_tag | 15 | **3** |
| `rag_published_embeddings` chunk `service_line` tags | 591 | **562** (inert — no vocabulary reaches them) |
| lexicon revision | 2442 | 3213 |

**Root cause — two mechanisms, both Lexicon's error, not a deliberate removal:**

1. **Query-side entries wiped by the nightly.** The 32 entries were written to the
   **RAG** lexicon only, never synced to **QA**. The nightly rebuilds RAG-lexicon
   *from QA*, so the first rebuild dropped them. (The thin-pool *phrases* were
   synced to QA; the `service_line` *entries* were not — the §2.4 "incorporate to
   QA" rule, half-applied.)
2. **Source tags wiped by `retag-in-place`.** That pipeline regenerates
   `policy_paragraphs`/`document_tags` tags from lexicon *phrase-matching*.
   `j:service_line` is an **explicit** assignment with empty `strong_phrases`, so
   every retag recomputes those tables without it. An explicit doc→line assignment
   never survives a phrase-derived regeneration.

**The design lesson:** `j:service_line` should never have lived in the
phrase-derived tag store. `j:doc_type` got this right with a dedicated
`document_doc_type` **column** the retag/rebuild pipelines do not touch. The
durable fix is the same shape for service lines, plus persisting the query-side
entries in QA. **Pending Ananth's sign-off on the schema change** (it needs
Retriever's read-side to read the new column). Until then the 562 chunks are inert
but harmless; Registry's chat-API path (certified rows, 6/6 live) does not depend
on the axis.

Interim: neither restored nor stripped yet — awaiting the architecture decision so
the fix is done once, durably, rather than re-applied into the same erasure.

---

## 5.2 Change 2026-09-13 — which phrase field is authoritative for which direction (Lexicon, with Master RAG + Tool Manifest + Service Line Registry)

The §5.1 erasure was one instance of a larger, silent class: **the field a
code's vocabulary lives in silently decides which direction can read it, and
nothing enforced that the two matched.** Traced from a live retrieval failure
(a three-payor "care management activities" question returning nothing, while
the TCM codes T1017/H0049/H0050 sat untagged in the corpus).

**Verified firsthand (Lexicon read `policy_path_b._build_phrase_map`, lines
175-228):** the doc-side tagger reads `phrases`, `strong_phrases`, `aliases`
(score 1.0), falls back to `description`, and reads `weak_keywords.any_of`
(score 0.6). It does **not** read `query_expansion_phrases`. The query side
(Gate `_extract_phrases`, `expand_query_via_lexicon`, tool selection) reads all
fields unioned, `query_expansion_phrases` included.

Measured consequence: three whole axes held their vocabulary **only** in
`query_expansion_phrases` and were therefore doc-side blind —
`provider` (942), `product` (46), `service_line` (32) — **1,020 codes
query-side live, doc-side invisible.** Every axis that used `strong_phrases`
tagged the corpus; every axis that did not, tagged nothing.

**Rule (now binding for both parties):**

| Field | Doc-side (tagging) | Query-side | Use for |
|---|---|---|---|
| `strong_phrases` / `aliases` / `phrases` | **yes, @1.0** | **yes** (query bag) | **Identity-grade only** — a multi-word name or a real proper name. A term here tags every document containing it at full weight AND resolves it on the query side, so generic English must never live here. |
| `weak_keywords.any_of` | **yes, @0.6** | **NO** | Collision-prone / generic / acronym surfaces — doc-side recall without query-side mis-resolution. Doc-only is the whole point: it lets a generic surface tag a doc weakly without letting a generic query word resolve the code. |
| `query_expansion_phrases` | **no** | **yes** (query bag) | Query-side expansion only. **Must never be a code's sole vocabulary** — that is doc-side blindness. |

> **Correction 2026-09-13 (Master RAG AST-checked; Lexicon verified):** an
> earlier draft of this table marked `weak_keywords` query-side "yes" — wrong.
> The query bag (`corpus_search_lexicon.expand_query_via_lexicon`, line 306-307)
> reads exactly `strong_phrases, aliases, phrases, query_expansion_phrases` —
> NOT `weak_keywords`, which appears there only in a docstring (a comment
> asserting a dataflow the module does not implement — the week's recurring
> trap, this time in my own contract). Consequence: to fix a **query-side**
> mis-resolution a surface must be **dropped from the query bag fields**;
> demoting it to `weak_keywords` changes only doc-side tagging, and a seeder that
> only ADDS never removes the offending surface from `query_expansion_phrases`.

**Every code must carry a doc-side vocabulary field** (`strong_phrases`,
`aliases`, or `phrases`). Absence is a defect visible at write time, not to be
inferred from zero tags months later.

**Acronym rule (Service Line Registry, replacing Lexicon's length proxy):**
demote an acronym to `weak_keywords` when it has a **non-service-line meaning
attested in this corpus**; **refute** it (`refuted_words`) when that meaning is
mechanically identifiable. Length is a proxy for collision and wrong both ways
(`fqhc` is 4 chars and unambiguous; `detox` is 5 and generic; `mrt` collides
with *Mediator Release Test*, which no length or context filter finds — only
corpus attestation does).

**Axis rulings under this rule:**
- `service_line` (32) — Master RAG re-filed each code's own
  `query_expansion_phrases` into `strong_phrases` (unique, ≥8 char, identity) +
  `weak_keywords.any_of` (shared/acronym) + `refuted_words`. Nothing invented;
  re-filing the Registry's own words under the doc-side key is inside rule 4,
  not across it. **Mirrored to QA by Lexicon 2026-09-13** (31 specs, verified
  QA==RAG) so the nightly publish cannot clobber it — the §5.1 trap, avoided
  this time before it fired. **Query-side residual (2026-09-13):** the 6 surfaces
  demoted to `weak_keywords` (`fact`, `mrt`, `detox`, `tcm`, `case management`,
  `targeted case management`) are STILL in `query_expansion_phrases` (the seeder
  only adds), so they still resolve query-side — demotion fixed doc-side only.
  Lexicon tested each in Gate: **drop `fact`** ("fact requirements" → j:service_
  line.fact) **and `mrt`** ("mrt test results" → mobile_response; the Mediator-
  Release-Test collision) from `query_expansion_phrases`; **keep the other four** —
  `detox`→withdrawal_management, `tcm`/`case management`/`targeted case
  management`→TCM lines are correct, desired query-side resolutions. Rule: a
  query surface is dropped when generic/collision, kept when a real synonym —
  decided by running Gate, not by shape.
- `product` (46) — **stays query-side-only. Not seeded doc-side.** The axis is
  Mobius's own module names; doc-side seeding would tag payer documents with
  internal product vocabulary.
- `provider` (941) — **measured 2026-09-13: seedable doc-side, low risk.** Of
  1,763 surfaces, **1,724 (97.8%) are distinctive** multi-word org names — safe
  as `strong_phrases` because the tagger matches the full phrase, not tokens
  (measured corpus-match rate on representative distinctive names ≤0.04% of
  paragraphs, those matches legitimate org mentions). **31 all-generic multi-word
  surfaces** ("mental health care", "community health centers", "family mental
  health", …) → `weak_keywords`/`refuted`: as full strong phrases they would tag
  every doc about the concept as the org ("Mental Health Care Inc"). Attestation
  reasoning, sound.
  - **Correction (Master RAG, same day):** the 8 short acronyms were first
    excluded by `≤4 chars` — the exact length proxy this §5.2 replaced, re-applied
    within hours by the seat that ratified the replacement. Redone by attestation
    (reading `policy_lines`): **barc** ("BARC Housing, Inc."), **laar** ("Laar
    Corp."), **cmet** ("CMET, LLC") appear AS THE ORG → they BELONG in
    `strong_phrases`; the length rule wrongly excluded them. **ahn** collides with
    a person surname ("Ahn, Byung-Joon MD"; citation author "Ahn C") → demote/
    refute. **ajnd, cftc** have 0 corpus presence and **dlc (3 lines), syx (2)**
    are negligible → placement immaterial. So the acronym exclusion is **ahn only
    (+dlc/syx if one insists), not 8** — three of the "risky" acronyms are
    legitimate identity.
  - **Class note:** a new rule does not delete the old heuristic — it sits next to
    it, and the old one is the one your hands already know. Length re-surfaced here,
    in the entry that deprecated it. Also: "excluded by shape because the rate
    *would* be high" is a prediction doing a measurement's job — right for the 31
    generic multi-word (self-flagged), but the shape this week keeps catching, so
    it is caveated, not trusted.
  - **Tail scan run (2026-09-13, 5% corpus sample, all 1,763 surfaces).** The
    caveat paid off: it flagged **2 generics the shape rule missed** — `steps`
    (0.43%; a provider org whose token is a common English word — "complete the
    steps"; already visible as gate018's mis-resolution to "steps llc") and
    `childrens hospital` (0.11%; a generic suffix across Nemours/Norton/DiMaggio)
    → both to `weak_keywords`. Two more flags were attested as **legitimate
    high-frequency orgs, kept in strong**: `circles of care`, `orlando health`.
  - **Action model (corrected once the field semantics were checked):**
    `weak_keywords` is QUERY-VISIBLE (does not fix a query-side mis-resolution);
    `refuted_words` is DOC-SIDE ONLY (verified: read only in
    `policy_path_b`, never in the query resolver). So the exclusion is three
    actions, not one: **(1) drop the bare generic where a fuller sibling exists**
    (12 codes — e.g. `provider.steps_llc` keeps "STEPS, LLC", drops bare "STEPS";
    fixes both query mis-resolution and doc over-tag); **(2) `weak_keywords`** for
    a generic that is the code's only surface (12); **(3) `refuted_words`** for a
    doc-side name collision (`ahn`). `gate018` ("Steps for verifying eligibility"
    → `j:provider.steps_llc`) is the live proof this must be a drop, not a demote.
    Sets in `docs/coverage/provider-seed-exclusions.json`; applied with Master
    RAG's sequenced provider seed, RAG+QA in one transaction.
- `d:*.general` (18) — carry a mix of identity and generic/acronym/OCR in
  `strong_phrases`; Lexicon to move generic+collision to `weak_keywords`, delete
  OCR junk, keep single- and multi-word identity in `strong_phrases`. Queued
  behind the live service_line retag. (Same class as §3.1 stems.)

---

## 6. Sign-off

| Party | Position |
|---|---|
| **Lexicon** | Reconciled mapping delivered; supersedes the registry's fuzzy first pass. Asked to be verified rather than trusted. |
| **Service Line Registry** | Verified all six drops independently — all correct. Applied the reconciliation. Returns two findings (§3.1 stems, §3.3 collapsed pairs) and accepts §3.2 with a distinction. |

Signed on the evidence above, not on summary.
