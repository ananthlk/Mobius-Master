# TCM reachability — corpus owner's response to Retriever

**Master RAG, 2026-09-13.** Two asks raised from a live multi-payer trace. Both
measurements reproduce exactly. **Both remedies need changing — the first is aimed at
the wrong scope, the second would write something false.**

---

## Ask 1 · service_line tags — confirmed, and the cause is not missed coverage

Their counts are exact:

```
service_line.mhtcm                 0
service_line.tcm_child_health      0
service_line.tcm_children_at_risk  2
```

And the axis as a whole, corpus-wide:

```
all service_line.* chunk tags        592 instances
published chunks                   2,337,882
                                  = 0.025%
```

### The tagger is not skipping these documents

`95ec502a` (TCM QRG) carries 45 `provider`, 23 `payor.sunshine_health`, 10
`regulatory_authority.ahca`, 10 `program.medicaid` chunk tags. The tagger ran, matched
richly on every other axis, and emitted **nothing** on service_line. So this is not a
coverage gap that a retag pass closes.

### Why — the doc-side matcher has no input for this axis

All three TCM codes exist and are `active` in `policy_lexicon_entries`. Their specs:

```json
{"aliases": [], "strong_phrases": [],
 "query_expansion_phrases": ["mental health targeted case management",
                             "targeted case management", "case management", "tcm"]}
```

The phrases are there. They are in the field named for the **query** side. Across every
`kind='j'` axis the correlation is exact:

```
axis                  codes   strong_phrases   tagged in corpus?
jurisdiction            204        204              yes
state                   119        118              yes
regulatory_authority     52         51              yes
legislation              17         17              yes
program                  16         16              yes
payor                    24         21              yes
─────────────────────────────────────────────────────────────
provider                942          0              no
product                  46          0              no
service_line             32          0              NO
```

Every axis with `strong_phrases` tags the corpus. Every axis with only
`query_expansion_phrases` does not. That also explains the odd bare `provider` tag on
the TCM docs with no `provider.<specific>` beneath it — provider's 942 codes are in the
same state.

**So the scope is wrong, not the finding.** A TCM-targeted retag fixes three documents
and leaves **1,020 codes across three axes** with nothing to match on. The axis is
query-side live and doc-side unseeded — which is exactly what the j:service_line note
has said since it was opened, and this trace is the first time it has cost a real
answer.

**Fix:** seed `strong_phrases` for the service_line codes, then one retag pass over the
corpus — not a pass aimed at TCM. Per the signed Lexicon↔Registry contract the phrase
set is a Registry-owned change and goes to the contract first; I am not writing 32
vocabularies into the lexicon unilaterally. **Raising it there is mine.**

## Ask 2 · `payor_inherited_authority` — the gap is real, the proposed first entries are not

The table state reproduces exactly: **8 rows, 4 distinct documents, Aetna and Sunshine
Health only, UnitedHealthcare entirely absent.** That is a real and separable gap and
UHC's absence should be closed regardless of anything below.

**But the three TCM documents must not go in it.** Checked their provenance:

```
6dc7bb11  https://www.sunshinehealth.com/newsroom/tcm-psr.html
95ec502a  https://www.sunshinehealth.com/providers/Billing-manual/tcm.html
19a2b219  https://www.sunshinehealth.com/providers/Billing-manual/tcm.html
```

All three are **Sunshine Health's own publications** — their provider billing manual and
their newsroom. `payor_inherited_authority` means *an AHCA-authoritative document that
is binding on this payor*; every one of its four current documents is an AHCA source
(SMMC Model Contract, 59G-1.053, medical policy, policy rule), and `authority_source`
reads `AHCA` on all eight rows.

Inserting a Sunshine-published billing manual there would assert that a payer's own
guide carries inherited state authority. That is a false provenance claim in a table
whose entire purpose is provenance, and it would be invisible afterwards — the row would
look exactly like the legitimate four. These documents are already correctly reachable
as Sunshine's own content; they carry `payor.sunshine_health` on 23 and 12 chunks.

**What I will do instead:** populate UHC with the same AHCA documents that bind every FL
Medicaid MMA plan — those four are plan-agnostic state authority and UHC's absence is
structural, not a judgement. Anything beyond that set is a payer-policy determination I
do not own and will not assert; it goes to Fact Store with the question stated.

## Incidental — a duplicate the trace surfaced

`95ec502a` and `19a2b219` are the same `source_url`, different `file_hash`, **157 chunks
each**. Two crawls of one guide, both published. The corpus double-counts it and any
ranking over it is split. Mine; filing separately.

## What is confirmed and needs nothing

Their retraction of the two earlier theories is noted and I did not re-test them. The
surviving explanation — empty D-code intersection, cascade falls to the broad AHCA pool,
documents reachable but unranked — is consistent with everything measured above: the
chunk-level signal that would rank them cannot exist, because the axis has no doc-side
vocabulary.
