# Payor inheritance — handoff to Payor Fact Store

**Ananth's ruling, 2026-09-13: every registered payor inherits, and Payor Fact Store
sets it up.** This page is the mechanical picture so that work lands correctly the
first time. Everything below is measured, not recalled.

**My side is already done and deployed-pending: the read path no longer caps who can
inherit.** What remains is population, which is yours.

---

## 1 · What you are populating (it is not the table you would expect)

`payor_inherited_authority` is **a VIEW**. Nothing can be inserted into it:

```sql
SELECT ... FROM (
    SELECT DISTINCT payor, state, program FROM payor_readiness_asset
    WHERE state='FL' AND program='Medicaid' AND payor <> 'AHCA'
  ) m
  CROSS JOIN payor_readiness_asset a
 WHERE a.payor='AHCA' AND a.corpus_present
   AND a.authority_level='contract_source_of_truth';
```

Its 8 rows are 2 payors × 4 AHCA assets. **The real table is `payor_readiness_asset`,
and both sides of the cross join come from it.**

## 2 · Why it is 8 rows, in the two places it is capped

**Left side — who inherits.** Only Aetna and Sunshine Health have `state='FL' AND
program='Medicaid'` rows:

```
Aetna                FL Medicaid   24
Sunshine Health      FL Medicaid   23
AHCA                 FL Medicaid   21   (excluded by design — it is the source)
BBHC, CFBHN, CFCHS, LSF, NWF, SEFBHN, SFBHN   FL SAMH   10 each
```

The seven behavioural-health networks are `program='SAMH'`, so the view's
`program='Medicaid'` filter excludes them. **UnitedHealthcare, Humana, Molina, Simply,
WellCare and Amerigroup have no rows at all** — they exist in the lexicon
(`payor.unitedhealthcare` et al., 23 `payor.*` codes) but not in the registry.

**Right side — what is inherited.** AHCA has 21 asset rows; only 4 qualify:

```
medicaid_policy_rule   corpus_present ✓  contract_source_of_truth ✓  document ✓
medical_policies       corpus_present ✓  contract_source_of_truth ✓  document ✓
state_contract         corpus_present ✓  contract_source_of_truth ✓  document ✓
um_policies            corpus_present ✓  contract_source_of_truth ✓  document ✓
provider_manual                          contract_source_of_truth    no document
fee_schedule           corpus_present ✓  payer_policy  ← filtered out by authority_level
formulary                                payer_policy      no document
+ 14 rows that are phone numbers, portal URLs, EDI ids — not documents at all
```

## 3 · The thing to decide before populating — the grain does not hold 9,541 documents

We hold **9,541 documents from `ahca.myflorida.com`**. `payor_readiness_asset`'s grain
is **one row per asset TYPE**, each carrying a single representative `document_id`.
21 AHCA rows cannot enumerate 9,541 documents, and adding 9,541 rows × N payors would
turn a readiness checklist into a cross-product with six figures of rows.

So "every registered payor inherits every AHCA document" is not expressible as more
rows in this table. Three shapes, and the choice is yours as owner:

1. **Rule, not enumeration** — inheritance derived at query time from document
   provenance (`source_metadata->>'source_url'` host = `ahca.myflorida.com`) crossed
   with registered FL Medicaid payors. Scales to the whole AHCA corpus, no row
   explosion, and new AHCA documents inherit the moment they are ingested. My
   recommendation, and I can build the query side.
2. **Widen the view's filters** — drop `authority_level='contract_source_of_truth'`
   and/or relax `program='Medicaid'`. Cheapest, but still capped at AHCA's 21 asset
   types, so it buys a handful of documents, not the corpus.
3. **A real inheritance table** at document grain, populated by you. Most explicit,
   most rows to maintain, and it needs a writer that keeps pace with ingest.

If you take (1), the view is retired rather than extended — worth saying out loud,
because it currently reads as the mechanism.

## 4 · What I fixed so your work is not invisible

`corpus_search.py` hardcoded the payor→j-tag mapping:

```python
_INHERITED_PAYOR_TO_JTAG = {"Aetna": "payor.aetna",
                            "Sunshine Health": "payor.sunshine_health"}
```

**Every payor you registered would have been selected by the query and then dropped by
a dict lookup returning None** — your population landing, changing nothing, and
raising no error. A hardcoded map in front of a table someone else owns is a consumer
that quietly refuses most of its producer's output.

It now derives from `payor_readiness_asset.j_tag`, which you already populate for every
payor (`j:payor.sunshine_health`; the `j:` prefix is stripped on read). Verified parity
on the live 8 rows. **A payor you register from now on inherits with no change to my
code.** Committed `c9a68e5`; ships on the next RAG deploy.

## 5 · What I need from you, concretely

- **Register the missing FL Medicaid MCOs** in `payor_readiness_asset` with
  `state='FL'`, `program='Medicaid'`, and a populated `j_tag` — UnitedHealthcare,
  Humana, Molina, Simply, WellCare, Amerigroup at minimum. The `j_tag` is the field my
  read path keys on; a row without it inherits nothing.
- **Decide §3's shape** and tell me. If it is (1) I build the provenance rule; if it is
  (2) or (3) the work is yours and I consume whatever the view or table emits.
- **Confirm the SAMH networks' intent.** Seven payors sit at `program='SAMH'` and are
  excluded by the view. If AHCA authority binds them too, that filter is wrong; if it
  does not, it is correct and should be commented as deliberate rather than read as an
  oversight.

One thing I will not do: assert which AHCA documents bind which payor. That is a
payer-policy determination and it is yours. I am the scribe on this field, the same way
I am on `product_line`.
