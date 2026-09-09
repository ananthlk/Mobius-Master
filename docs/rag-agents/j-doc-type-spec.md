# Spec: `j:doc_type.*` — document type as a doc-level jurisdiction tag

**Owner:** Lexicon (Curation leg) · **Directed by:** Ananth 2026-08-15 · **Status:** implementing

## Idea (Ananth)

A document's TYPE (provider manual, billing manual, …) becomes a **`j:` tag applied at the whole-doc level**, alongside the payer tag. So the *Sunshine Provider Manual* carries **two** j: tags:

- `j:payor.sunshine_health` (which payer)
- `j:doc_type.provider_manual` (which kind of doc)

Both live on the **`j:` = corpus-partition / retrieval-filter axis**. A query like "Sunshine provider manual timely filing" filters `j:payor.sunshine_health` AND `j:doc_type.provider_manual` → exactly the right slice.

## Why `j:` and not `p:` or a `d:` tag

- `j:` is the partition/filter axis (that's why `payor.*`, `state.*`, `regulatory_authority.*` live there). Doc-type is a partition dimension you filter by → fits by function. ("Jurisdiction" is a loose label — same stretch already accepted for payor.)
- **Assigned DOC-LEVEL, not by phrase-matching content.** This is the crux. The earlier "column not tag" ruling was about phrase-matching mis-typing (a billing section inside the provider manual matching "billing"). Here the whole doc gets `j:doc_type.provider_manual` because that is what the doc IS — same mechanism as `document_tags` / `asset_type`. No content phrase-match → no mis-tag.
- Rides the existing `j:` retrieval-filter arm (Gate/Router already filter on `j:` tags) → doc-type filtering comes free, no new plumbing. Replaces the earlier "add `document_asset_type` column to `rag_published_embeddings`" idea — the `j:` tag does that job reusing existing machinery.
- Keeps `p:` (party/process) uncluttered.

## The two faces — kept separate (the guardrail)

| face | source | mechanism |
|---|---|---|
| **doc assignment** (which docs carry the tag) | the role **classifier** (doc-level; shadow-mode, precision-floored) → authoritative `asset_type` | assigned to the whole doc, NOT phrase-matched |
| **query recognition** (query mentions "provider manual" → filter) | `spec.query_expansion_phrases` on the entry | query-side only; read by Gate's `expand_query_via_lexicon` (rev 00558) |

**Entries carry `query_expansion_phrases` ONLY — `strong_phrases` and `aliases` stay EMPTY**, because those two doc-tag by content (`get_phrase_to_tag_map` reads `strong_phrases`/`aliases`) and would reintroduce the mis-tag. Query-phrases for recognition + classifier for assignment = clean on both faces.

## Tie to asset_type

`j:doc_type.<slug>` is the **retrieval projection** of `asset_type`. One source (the classifier), two representations: `asset_type` column (Sources page / entity, authoritative) and `j:doc_type.<slug>` tag (retrieval filter). `doc_type.<slug>` ↔ `asset_type=<slug>` 1:1.

## Shape

`kind='j'`, container `code='doc_type'` (`parent_code=NULL`, sibling to `payor`/`state`/`regulatory_authority`); children `code='doc_type.<slug>'`, `parent_code='doc_type'`. 2-segment cap respected. Seven children (the §3 asset_types):

| code | query_expansion_phrases (draft) |
|---|---|
| `doc_type.member_manual` | member manual, member handbook, member guide, enrollee handbook, member services manual |
| `doc_type.provider_manual` | provider manual, provider handbook, provider guide, provider reference manual |
| `doc_type.billing_manual` | billing manual, billing guide, claims manual, billing and claims manual, reimbursement manual |
| `doc_type.contract` | model contract, medicaid contract, medicare contract, managed care contract, state contract |
| `doc_type.provider_contract` | provider contract, participating provider agreement, provider agreement, participation agreement |
| `doc_type.clinical_policy` | clinical policy, clinical coverage policy, medical policy, clinical criteria, coverage policy |
| `doc_type.um` | um manual, um criteria, medical necessity criteria, level of care criteria, utilization management criteria |

Bare over-generic single tokens deliberately excluded (`contract`, `utilization management`) — they're topic words that would over-route; multiword type-names disambiguate.

## Freeze / bracket safety

Creating these entries is **corpus-neutral**: query-only phrases don't doc-tag, and `strong_phrases`/`aliases` are empty, so no doc gets tagged and retrieval is unchanged until doc-level ASSIGNMENT happens (the chunk/embed/publish run). Safe under the eval-baseline freeze. This is step-1 (incorporate) of Ananth's simulated-nightly bracket: incorporate → baseline eval → assign+publish → post eval.

## Hygiene note

`d:provider.manual` exists (a topic tag carrying "provider manual"). It's orthogonal to `j:doc_type.provider_manual` (topic vs partition) and doesn't conflict at doc-tag level, but it may be a doc-type that leaked onto the `d:` axis — candidate to retire once `j:doc_type` is the home. Not blocking.
