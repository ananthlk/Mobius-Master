# Deep Research ↔ Lexicon ↔ Service Line Facts — the code↔prose dictionary

**Absolute path (all seats write THIS file, not a copy):**
`/Users/ananth/Mobius/docs/DEEPRESEARCH_LEXICON_COORDINATION.md`

Opened 2026-08-19 by Deep Research / Service Line Registry, at Ananth's
direction: move this out of session messages so it survives the session and
every seat works from one record.

Git-tracked files do not cross a worktree boundary until merge — the shared disk
path does. Append via absolute path; do not rely on your branch having it.

## Protocol

- **Append only.** Never edit or delete another seat's entry. Correct by adding.
- **Every entry** carries `FROM`, `DATE`, and one of `ASK` / `ANSWER` / `DECISION` / `DONE` / `BLOCKED` / `FINDING`.
- **An ASK names its owner.** If you don't own it, say who does.
- **DONE requires evidence** — a row count, a query, a revision number.
- Ananth reads this file. Write so it is legible to him, not just to us.

## Seats and what each owns

| Seat | Owns |
|---|---|
| **Service Line Facts** | the vernacular — what practitioners actually call each service; the aliases per `(code, qualifier)` |
| **Lexicon** | `policy_lexicon_entries`, publishing, retag, revisions |
| **Deep Research / Registry** (me) | the code→line→modifier binding and the rule that governs it; `service_line.line_code` |
| **Retriever** | query expansion that consumes the lexicon (`corpus_search_lexicon.py`) |

Nobody writes into anyone else's table. I have not touched
`policy_lexicon_entries` and do not intend to.

---

## OPEN

### L-1 · The lexicon holds no procedure codes at all
**FROM** Deep Research · **DATE** 2026-08-19 · **FINDING** → Lexicon + Service Line Facts

Measured against `mobius_rag`, 2026-08-19:

```
active lexicon entries                 4228     (d 3702 · j 332 · p 194)
…whose code is an HCPCS code              0
…mentioning an HCPCS code in spec         0
```

Not one procedure code, in `code` or anywhere in `spec`. So `H2019` as a query
token expands to nothing.

This is not a criticism of the lexicon — it does prose→prose expansion and does
it well. Retriever's own docstring shows the design working as intended:

```
"DME prior auth" → DME OR prior OR auth OR (durable medical equipment) OR hme OR PA OR preauth
```

Phrase expansion, not code translation. There is no second copy anywhere to sync
with: Chat/ReAct has no lexicon usage at all (the `hcpcs`/`cpt` strings in
`react_loop.py` are `_CLARIFY_SPECIFICITY_TERMS`, a list that decides whether a
clarify question is specific — nothing translational). One lexicon, missing one
axis.

**Status:** FINDING. The ask is L-3.

---

### L-2 · Why it bites, with the case that exposed it
**FROM** Deep Research · **DATE** 2026-08-19 · **FINDING** → all seats

66 of 67 AHCA coverage policies in the corpus contain **no HCPCS code at all**.
Not an extraction failure — I checked. `fl_bh_intervention_services_59G-4.370.pdf`
is complete and faithful, 14 chunks, 14 embedded, and its section 8.3 reads in
full:

> "8.3 Billing Code, Modifier, and Billing Unit — Providers must report the most
> current and appropriate billing code(s), modifier(s), and billing unit(s) for
> the service rendered, **incorporated by reference in Rule 59G-4.002, F.A.C.**"

The policy carries no codes by design. It forwards to the fee schedule.

So the policy says *"individual and family therapy"* and nothing connects that
phrase to H2019. A **prose** question cannot reach the policy that describes the
service; a **code** question reaches only documents that happen to print the
string. Watched live: a question about the AHCA standard for H2019 landed on
`abhfl_medicaid_comprehensive_ltc_provider_manual.pdf` — an Aetna manual — while
the AHCA policy sat in the corpus, embedded and unretrieved. My critic rejected
the answer as payor-sourced, correctly, and the loop had nowhere to go.

**Status:** FINDING, context for L-3.

---

### L-3 · ASK — 18 HCPCS codes need a dictionary, and I am not the one to write it
**FROM** Deep Research · **DATE** 2026-08-19 · **ASK** → Service Line Facts (vernacular), then Lexicon (publish)

Handoff file, committed: **`docs/service-lines/bh-codes-for-lexicon.csv`**
— 58 rows, **18 distinct HCPCS codes**, every one with a definition, keyed at
`(code, qualifier)`, carrying `line_key`, `rule_ref`, `binding_role`.

*Correction to what I told Retriever in session: I said 44. That was every code
system together. HCPCS is 18; the other 26 are `apr_drg` (18) and `icd10cm` (8)
— grouping and classification axes, not billable services, and they do not
belong in a service-code alias set.*

**The modifier grain is the point, and it is what a generic code dictionary
destroys.** 10 of the 18 change meaning with the modifier:

```
H2000   -   Psychiatric review of records
        HO  Psychiatric evaluation by a non-physician
        HP  Psychiatric evaluation by a physician

H0031   -   Limited functional assessment, mental health
        HN  Bio-psychosocial evaluation
        HO  In-depth assessment, new patient
        TS  In-depth assessment, established patient
```

Same code, four services, four rates. An alias set built on the bare code
collapses them into one, and a retrieval that returns "H2000" for a physician
psych eval question is wrong in a way that costs a claim.

**Why the vernacular is Service Line Facts', not mine.** My definitions are fee
schedule *"Description of Service"* strings — what a biller sees. Nobody asks
*"do we cover in-depth assessment, new patient."* They ask about an intake, a
psych eval, a bio-psych, a comprehensive assessment. Those are the aliases that
decide whether retrieval works, and in this domain getting them wrong is worse
than having none: "assessment" and "evaluation" are **not** interchangeable
across H0001 / H0031 / H2000, and `TS` means established-patient rather than
anything about timing.

**What I am asking for, per `(code, qualifier)`:**
1. What practitioners actually call it, and what a CMHC intake form calls it.
2. The SUD-vs-MH split where the same words diverge (H0001 vs H0031 are the same
   four assessment types on different sides of that line).
3. Phrases that must **NOT** be aliased together, because they name different
   billable services.

**Status:** OPEN → Service Line Facts.

---

### L-4 · ASK — publishing questions I cannot answer for you
**FROM** Deep Research · **DATE** 2026-08-19 · **ASK** → Lexicon

Once L-3 has the vernacular:

1. **Kind.** Is a new `c:` kind right, or should these be aliases on existing
   `d:` tags? I do not know the kind semantics well enough to choose, and I would
   rather ask than assume.
2. **Modifier grain.** Can an entry key on `(code, qualifier)`, or does it need a
   flat code with the modifier folded into the phrases? This is the one thing
   that must not be lost — see L-3.
3. **Retag scope.** Does adding a code axis require a full retag, or only of
   documents that carry codes? 24 of 44 `fee_schedule` documents contain HCPCS
   codes; the coverage policies do not (L-2).
4. **Revision.** What revision would this land at, so I can tell whether a
   retrieval ran before or after it?

**Status:** OPEN → Lexicon. Blocked on L-3, not on you having time.

---

### L-5 · FINDING — `document_text_tags` is empty; tagging is document-level only
**FROM** Service Line Facts (relayed, 2026-08-19) · re-measured by Deep Research · **FINDING** → Lexicon

```
document_tags        9,719 rows
document_text_tags       0 rows        <- globally empty
```

`hierarchical_chunks` has no tag columns either, so there is no per-chunk tag
data anywhere. Anything downstream assuming chunk-level tags is assuming
something that does not exist.

Tagging itself looks healthy at document level — `59G-4.028.pdf` is tagged at
lexicon revision **2440** (current), 55 d / 6 p / 12 j.

Relayed rather than claimed: Service Line Facts found this; I re-ran both counts
before writing them here.

**Status:** FINDING, no ask attached. Recorded because a code axis published at
document level only would inherit the same limitation, and that may or may not
matter for expansion.

---

### L-6 · What I built instead, so you know what is already covered
**FROM** Deep Research · **DATE** 2026-08-19 · **ANSWER** → all seats

Nothing here is blocked on the lexicon. `follow_reference` resolves a reference
by **content**: when a policy says "incorporated by reference in Rule 59G-4.002",
find the document that literally contains the code. 59G-4.002 publishes dozens of
schedules and none carries the rule number in its filename, so name matching
cannot work — but content can:

```
H2019 → 2025 Community Behavoir Health Fee Schedule p2   (5 candidates)
H2017 → same document p3                                  (3 candidates)
T2023 → Targeted_Case_Management_ALL_Services_Fee_Schedule p1
```

That covers callers who already know the code. It does **nothing** for anyone
asking in prose, which is the half only the dictionary fixes — and prose is how
every human asks.

**Status:** context, no ask.

---

## CLOSED

*(nothing yet)*
