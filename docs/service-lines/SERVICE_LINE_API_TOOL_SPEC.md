# Service Line Registry API → chat tools

**From:** Service Line Registry · **For:** Chat Master / ReAct / Chat FE
**Service:** `mobius-payor` · **Base:** `PAYOR_API_URL` · **Prefix:** `/api/service-line`
**Status:** LIVE — `mobius-payor-00175-nc4`. All GET. 31 endpoint tests green.

---

## 1. What this is for

The registry holds the FL Medicaid behavioural-health master contract: which
services we serve, what codes bill them, what the published standard covers, how
much may be billed, and on whose authority. Chat previously answered these from
retrieval over fee-schedule PDFs — which is how you get a confident number off a
table slab that is mostly about other codes.

These endpoints answer from certified rows, and every answer cites its document.

## 2. One envelope, every endpoint

```json
{
  "status":    "found | known_absent | unknown",
  "answer":    "one sentence, directly quotable — the headline",
  "caveats":   [{"code": "...", "kind": "blocking|material|context",
                 "text": "...", "choices": [{"id","title","subtitle"}]}],
  "citations": [{"document": "...", "page": 2, "sourced": true}],
  "data":      { ...endpoint-specific payload... },
  "query":     { ...echo of what was asked... },
  "meta":      {"endpoint","count","jurisdiction","registry","generated"}
}
```

### 2.1 `status` — three states that must never collapse

| | Meaning | What the caller must do |
|---|---|---|
| `found` | We hold a sourced answer | Answer, and cite |
| `known_absent` | We looked. The governing document **is held** and is **silent**. | Say the source does not state it. Do **not** infer, and do not fall back to retrieval and present that as equivalent. |
| `unknown` | We hold nothing | Say we do not have it. **Not a denial.** |

The failure this prevents: *"is H0032 covered?"* → nothing found → chat answers
"no". A code nobody sourced and a code genuinely not covered are different facts.
**24 of 31 lines currently return `unknown`**, so the honest-decline path is the
common one, not the rare one.

### 2.2 `caveats` — conditional, coded, and typed by what to DO

A caveat appears **only when it applies**, so its presence is information. Branch
on `code`; never pattern-match `text`.

| `kind` | Meaning | Treatment |
|---|---|---|
| `blocking` | The answer cannot honestly be given until this is resolved | **Stop and ask.** Carries `choices`. |
| `material` | The answer stands, but drop this and it becomes wrong | Inline, next to the answer, never collapsed |
| `context` | Standing scope note, true of every answer here | Footer |

`blocking` caveats carry `choices` as `{id, title, subtitle}` — pass `id` back as
the `modifier` (or line key) on the re-query and the loop closes.

```
modifier_ambiguous     blocking   several billable services under one code
limits_differ_by_modifier blocking the caps are not the same across modifiers
bad_filter             blocking   the line key does not exist (suggests near keys)
caps_not_additive      material   rows repeat per line; quote distinct_readings
multiple_caps_apply    material   a daily AND an annual cap both bind
unit_undefined         material   an amount with no definition of a unit
no_numeric_cap         material   "as medically necessary" — a stated absence
single_modifier_only   material   everything held carries one specific modifier
unsourced_placeholders material   some rows are our wording, not policy
absence_is_not_denial  material   we hold nothing; that is not a finding
decline_well           material   FL Medicaid covers it, Mobius does not serve it
evidence_basis_varies  material   quoted_rule vs published_rate are not equal
fuzzy_match            material   approximate spelling hit — confirm it
standard_not_payor     context    AHCA/CMS standard; a plan may differ
registry_scope_is_narrow context  FL Medicaid BH only
modifier_meaning_is_per_code context a modifier's meaning changes per code
```

### 2.3 `citations`

`{document, page, sourced}`. **`sourced: false` must render differently** — it
pairs with `unsourced_placeholders`, and presenting one as a citation launders a
placeholder into a source. Document names are AHCA's, including the misspelling
in `2025 Community Behavoir Health Fee Schedule.pdf` — render verbatim; it is the
join key back to the document.

## 3. Which tool returns which status — measured, not assumed

| Tool | Endpoint | Can return |
|---|---|---|
| `service_line_code_lookup` | `/codes/{code}` | `found` · `unknown` |
| `service_line_limits` | `/codes/{code}/limits` | `found` · `known_absent` · `unknown` |
| `service_line_coverage` | `/codes/{code}/coverage` | `found` · `unknown` |
| `service_line_search` | `/search?q=` | `found` · `unknown` |
| `service_line_detail` | `/lines/{key}` · list at `/lines` | `found` · `unknown` |
| `service_line_requirements` | `/requirements` | `found` · `unknown` |
| `service_line_gaps` | `/gaps` | `found` only |

**Six of seven vary. Only `gaps` is safe to hardcode a signal for.**
`known_absent` is a *sourced* answer and must not carry a no-sources signal, or
the model may escalate back to retrieval and answer from the fee-schedule table.

Also live: `/modifiers`, `/limits`, `/benefits` (cross-cutting, filterable).

## 4. Routing

| User asks | Tool |
|---|---|
| "what is H2017" / "can I bill H0031 HN" | `code_lookup` |
| "how many units of X" / "is there a daily cap" | `limits` |
| "is X covered" / "who is it covered for" | `coverage` |
| "what can I bill for psychosocial rehab" | `search` → `code_lookup` |
| "what do I need to bill bh_assessment" | `requirements` |
| "do you do partial hospitalisation" | `search` or `detail` — check `scope` |
| "is X *not* covered" | `coverage` first; `gaps` **only if** it returns `unknown` |

`gaps()` is registry-wide, so calling it on every coverage question spends ~650
tokens to learn nothing code-specific. Call it when `coverage()` returns
`unknown`, then check whether that code's line is in `lines_without_coverage`:
present → we hold no coverage document for that line at all; absent → the line
*is* sourced and this code is not in it, which is a much stronger signal.

## 5. Worked example

**"How many units of H2019 with modifier HR can we bill per year?"**

```json
{ "status": "found",
  "answer": "H2019 HR: 4 units of 15 minutes per day; and 104 units of 15 minutes
             per state fiscal year per recipient. All of these apply at once.",
  "caveats": [
    {"code":"multiple_caps_apply","kind":"material", ...},
    {"code":"caps_not_additive","kind":"material", ...},
    {"code":"standard_not_payor","kind":"context", ...}],
  "citations": [{"document":"2025 Community Behavoir Health Fee Schedule.pdf",
                 "page":4,"sourced":true}],
  "data": {"lines":["bh_intervention","fact"], "distinct_readings":[...],
           "limits":[ ...4 rows... ]} }
```

Retrieval alone reliably finds the 104 and misses the daily cap — or sums the
four rows and answers 208 for a 104-unit cap.

## 6. Two traps, both now stated by the API

**A bare code is not one service.** `H0031` is four billable services. Key off
`data.modifier_ambiguous` — **never derive it from `pair_count`**, which counts
rows (line × modifier). Six of eighteen codes sit on two lines with one modifier
between them, so `pair_count > 1` asks the user to choose a modifier that does
not exist, on a third of all codes.

**15 (code, modifier) pairs are bound to more than one line**, so `data.limits`
repeats each cap per line. Quote `data.distinct_readings`.

## 7. Scope

FL Medicaid behavioural health, and the **published standard only**. Not held
here: payor-specific rates or rules (Fact Store), appeals process (Appeals),
provider enrolment (Credentialing), anything outside Florida.

## 8. Changelog

- `00175-nc4` — `choices` on blocking caveats, in Chat FE's candidate shape
- `00174` — `/search` tries exact → spelling variant → trigram. A live chat had
  answered *"partial hospitalisation is not found as a recognized service line"*;
  the line is *Partial Hospitalization Program (PHP)* and one letter hid it
- `00173-vvw` — `kind` on caveats, so a UI places them without reading text
- `00172-gk4` — the single envelope; `answer`, `caveats`, `citations`, `data`
- `00171-www` — first deploy, eleven endpoints
