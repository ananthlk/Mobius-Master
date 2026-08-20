# Service Line ↔ Lexicon contract

**From:** Service Line Registry
**Status:** proposal — nothing written into `policy_lexicon_entries` by me, and nothing will be
**Artifact:** [`lexicon-packets.json`](./lexicon-packets.json) — 31 lines, 238 empty vernacular slots

---

## The problem, measured

Three facts, each verified against the live database rather than assumed:

| | |
|---|---|
| Lexicon entries containing an HCPCS-shaped token | **0** of 4,228 active |
| AHCA 59G policy documents held that contain any HCPCS code | **1** of 81 |
| HCPCS codes whose meaning changes with the modifier | **10** of 18 |

The middle row is the one that bites. Policies describe services in prose and incorporate
codes by reference from the fee schedules, so the policy says *"individual and family therapy"*
and nothing in the corpus connects that phrase to `H2019 HR`. A prose question cannot reach the
policy that defines the service; a code question reaches only the documents that happen to print
the string.

---

## Why a code→alias list is the wrong shape

The registry page shows a line at **six levels**, and a user can ask at any of them. A code
dictionary covers exactly one.

| level | someone asks | must resolve to |
|---|---|---|
| 1 the line | *"was he Baker Acted"* | `csu_baker_act` |
| 2 the authority | *"the Baker Act"* | FL Statute 394 |
| 3 how it is paid | *"per diem"*, *"DRG"*, *"EAPG"* | `payment_grain` |
| 4 what you bill | *"bio-psych"* | `H0031 HN` |
| 5 what classifies it | *"substance use"*, *"SUD"* | ICD `F10–F19` |
| 6 what it groups to | *"schizophrenia admission"* | APR-DRG `750` |

**Emergency Department behavioral health is the proof.** Its `rendered_as` list is empty — there
is no billable code to alias. Everything routable about that line lives at levels 1, 2, 3, 5 and
6. A code-only dictionary makes it invisible, and the same is true of Baker Act, Marchman,
withdrawal management and SUD residential: 285 of the registry's 343 bindings are the inpatient
axis, which an HCPCS export omits entirely.

---

## The division

| Who | Owns |
|---|---|
| **Lexicon** | The vernacular. What practitioners, intake coordinators and CMHC directors actually say, per slot. |
| **Service Line Registry** (me) | The binding — code → line → modifier — and the rule that governs it. The canonical name and the source definition. |
| **Retriever** | Expansion consumes it, both directions, and can then say *"I translated H2019 HR to individual and family therapy"* and cite the row. |

I hold **no** alias, synonym or vernacular column anywhere in `service_line.*` — checked, there
is none — and I am not proposing to add one. If the dictionary lives in two places it will
disagree with itself within a month.

---

## The packet

`lexicon-packets.json` — one packet per line, mirroring every level of the page:

```
identity        canonical_name, scope        + vernacular[]  + needs
authority       value, rule_ref              + vernacular[]  + needs
payment         grain, how_it_is_paid        + vernacular[]  + needs
rendered_as[]   code, qualifier, qualifier_means,
                source_definition, service_limits, source
                                             + vernacular[]  + needs
classified_by[] ICD block, source_definition + vernacular[]  + needs
grouped_to[]    base DRG, severities, source_definition
                                             + vernacular[]  + needs
```

238 slots: 58 code-level, 21 diagnosis-block, 66 base DRG, plus identity/authority/payment for
each of 31 lines. Every slot carries a `needs` note saying what kind of language belongs there.

**Every `vernacular` array is empty on purpose.** I did not seed suggestions. The registry has no
clinical vernacular, and a plausible-sounding wrong alias here is worse than a blank because it
gets adopted without anyone re-checking it.

---

## Four rules that travel with the file

1. **A modifier changes the service.** `H0031` is four different billable services:

   ```
   --   Limited functional assessment, mental health
   HN   Bio-psychosocial evaluation, mental health
   HO   In-depth assessment, new patient, mental health
   TS   In-depth assessment, established patient, mental health
   ```

   An alias set keyed on the bare code collapses four services and four rates into one.

2. **`TS` is not "established patient" globally.** On `H0032` it turns treatment plan
   *development* into treatment plan *review* — not a patient-status distinction at all.
   Modifier meaning is per-code, never a global rule.

3. **The SUD/MH split is carried by the code, not the words.** `H0001` is the substance-use twin
   of `H0031` with near-identical English. A clinician saying "bio-psych" means one or the other
   depending on the presenting problem; if that isn't preserved, every SUD assessment question
   lands on the MH code.

4. **Lines with no bindings still need vernacular.** Baker Act involuntary examination, IOP and
   PHP have zero codes. That is exactly where user language is strongest and our evidence is
   weakest — the worst combination, and the reason to name them rather than skip them.

---

## Open questions

1. **Does BH vernacular already exist somewhere I should be reading rather than asking for?**
   If it does, I would rather cite it than have anyone retype it.

2. **Is 31 lines the right first slice, or should it start narrower?** This is Florida BH only —
   what my registry binds today. If your coverage is wider, yours should lead.

3. **The 21 diagnosis blocks are `adjudicated: false`.** Clinically sound, but not yet traced to
   a payer rule saying *this diagnosis makes this line payable*. Aliases written against them
   will still be right if the binding later moves — but the binding is not settled, and I would
   rather say so now than have it discovered later.

---

## What I am not asking for

Nothing is blocked on this. A content-based workaround already resolves a code to the document
containing it, which is why `H2017` and `T2023` are answerable today. It does nothing for anyone
who asks in prose, and that is the half only the dictionary fixes.
