# `/playbook-guarded` — observed contract

**Produced by:** Appeals · **Date:** 2026-09-09 · **Method:** live calls against
`https://mobius-appeals-prototype-ortabkknqa-uc.a.run.app`, corpus of 141 active rows.
**For:** Platform seat (mobius-f2), chat-refactor P3 `tool_manifest` pass.

Requested as raw payloads rather than a description. Running it found a **real fail-open
defect in the appeals guard** that describing the contract would have concealed — see §4.
The instruction to test rather than answer was the right call.

---

## 1. Headline answers

| Question | Answer |
|---|---|
| Does chat's key lookup match? | **YES.** `deadline_appeal_days` and `submission_method` are top-level, exactly those names. **Chat's key-mismatch hypothesis is disproved.** |
| CARC 24 (turn `143309c1`) | **No playbook exists.** Chat's answer was correct. |
| Content-empty rows (no days AND no method) | **0 of 141.** Chat's `usable` guard never fires today. |
| Rows that pass `usable` but have **no deadline** | **72 of 141 (51%)** — all FL Medicaid |
| Is a miss distinguishable from an audience block? | Yes — but see §4, the markers are unreliable |
| Should chat invent an FL Medicaid default? | **No. Remove it.** §5 |

---

## 2. Lookup form (gotcha first)

Payor is the **display name**, URL-encoded. `sunshine_health` is NOT a valid key.

```
✅ /playbook-guarded/Sunshine%20Health/29?audience=provider   → 200, full object
❌ /playbook-guarded/sunshine_health/29?audience=provider     → 200, {}
```

A wrong payor key is indistinguishable from a genuine miss. If chat ever normalises payor
names to snake_case before calling, **every lookup returns `{}` and looks like "no playbook."**
Worth checking chat's caller.

---

## 3. The five cases, as returned

### A. Complete playbook — `Sunshine Health` × CARC 29
`HTTP 200`, 2707 bytes.
```jsonc
{
  "id": 3, "payor": "Sunshine Health", "carc_group": "TIMELY_FILING",
  "carc_codes": [29, 218],
  "deadline_appeal_days": 90,          // ← chat's key, top-level, int
  "deadline_resubmit_days": 180,
  "submission_method": "portal",       // ← chat's key, top-level, str
  "portal_url": "www.sunshinehealth.com",
  "fax": "1-833-504-0580",
  "mail_address": "Sunshine Health Post Office Box 3070 Farmington, MO 63640-3823",
  "appeal_levels": [ {"name":"Internal Appeal","level":1,"party":"provider",
                      "submission":"mail, fax, email","deadline_days":90}, … 5 rungs ],
  "docs_required": [ … ], "contacts": [ … ],
  "evidence_basis": "unverified", "field_evidence": {}, "_evidence_gaps": [ … ]
}
```

### B. CARC 24 — the turn in question
```
GET /playbook-guarded/Sunshine%20Health/24?audience=provider
HTTP 200  ·  2 bytes  ·  {}
```
**No playbook. Chat's answer was correct.** The corpus covers 72 CARC codes; 24 is not one.
(24 = capitation. A genuine coverage gap on our side, unrelated to chat's defect.)

### C. Payor that does not exist
```
GET /playbook-guarded/Aetna%20Better%20Health/29?audience=provider
HTTP 200  ·  2 bytes  ·  {}
```
**A miss is `200 {}`, never `404`.** And note B and C are **byte-identical** — chat cannot
distinguish "payor unknown" from "CARC not covered." If that distinction matters to the
answer text, it needs a contract change on our side.

### D. Playbook exists, deadline is NULL — `FL Medicaid` × 29
```jsonc
{ "id": 90, "payor": "FL Medicaid", "carc_group": "TIMELY",
  "deadline_appeal_days": null,     // ← null, not absent
  "submission_method": "portal",    // ← present
  "portal_url": "", "fax": "", "mail_address": "", … }
```
**This is the `"?d deadline · "` case, and chat's `usable` check PASSES it:**
`usable = found and (days is not None or bool(method))` → `False or True` → **True**.

**72 of 141 rows (51%) are in this shape**, all FL Medicaid. So the guard admits a
playbook that cannot answer a deadline question. If the user asked "how long do I have,"
`usable` is the wrong test — it needs to be **per-field**, against the field the question needs.

**These nulls are deliberate.** They were removed during P0-0 remediation because they were
unsourced fabrications (a fair-hearing 90-day and a provider-dispute 120-day that had
propagated corpus-wide). Current evidence audit: **339 filing-critical values, 0 citable,
0.0% sourced.** Blank is the fail-closed correct state until Payor Platform's sourcing lands.
The 2026-08-07 finding at `react_loop.py:3183` **predates** this remediation — re-measure
before tuning a retry guard against it.

### E/F. Audience handling — **this is where the bug is**
See §4.

---

## 4. 🔴 DEFECT FOUND — the guard fails OPEN on scalar values

`visible_to()`'s docstring says *"An undeclared audience serves nothing."* **It does not.**

| Call | marker | `deadline_appeal_days` | `fax` | `appeal_levels` |
|---|---|---|---|---|
| `?audience=provider` | — | 90 | 1-833-504-0580 | 5 |
| **`?audience=` omitted** | `_suppressed` | **90** | **1-833-504-0580** | 0 |
| **`?audience=member`** | `_party_suppressed` | **90** | **1-833-504-0580** | 0 |
| **`?audience=zzz`** (invalid) | `_suppressed` | **90** | **1-833-504-0580** | 0 |

The filter empties `appeal_levels` and `docs_required` — the **ACTION** collections — and lets
every **scalar VALUE** through untouched: the deadline, the fax, the mailing address, the
portal URL.

**Why this happened, and it is instructive:** the whole point of this guard was the insight
that *party scopes ACTIONS, audience scopes VALUES*. I implemented the actions half and never
implemented the values half. So a **member**-declared consumer receives the **provider** appeal
deadline and the **provider** appeals fax — the 141-row incident in mirror image.

**Severity today: low but not zero.** The only live caller (`react_loop.py`) passes
`audience="provider"` explicitly and is correct. The exposure is (a) any caller that omits the
param — it gets real facts with a `_suppressed` marker that nobody reads, and (b) any future
member-facing surface.

**This is ours to fix, not chat's.** Fix is to null the audience-scoped scalars alongside the
action collections. Not yet deployed — flagged here first.

**For chat in the meantime:** do not treat `_suppressed` / `_party_suppressed` as "empty."
The object still carries populated scalars. And `audience` is **not optional** — omitting it
does not fail closed today.

---

## 5. Ruling on chat's manufactured default — **remove it**

Chat currently synthesises, on our not-found path:
```
{"message": "No playbook for <payor>. Default FL Medicaid: 60 days, certified mail."}
```

**Do not ship a fabricated filing-critical deadline.** Four reasons, in severity order:

1. **Unrecoverable.** Most bad answers degrade an experience; a wrong appeal deadline loses the
   claim permanently, with no remedy. Your own example is exact: file on day 55 against a real
   30-day window and it is over.
2. **It undoes a deliberate remediation at render time.** Those 72 FL Medicaid rows are blank
   *because we deleted fabricated deadlines from them*. Chat then fills the gap with an invented
   FL Medicaid default. Net effect on the user is identical to never having done the cleanup.
3. **"Default FL Medicaid" is not a well-formed concept.** A deadline resolves on a tuple —
   `(payer, product_line, state, network_status, audience, appeal_level, request_type)` as of the
   **denial date**. FL Medicaid fair hearing, plan appeal, provider claim dispute and UM appeal
   are four different clocks. "60 days" cannot be right for a payer, only for a full tuple.
4. **It violates the standing contract** already ratified with Payor Platform: a filing-critical
   value below the citable bar is **removed, not labelled**, because a banner does not stop a
   coordinator acting on a number. An unlabelled *invented* one is strictly worse.

**Instead:** on `{}`, return nothing and let the answer say so. Chat's CARC 24 turn already did
the right thing — the only defect was that the span couldn't prove it.

---

## 6. What each side owns

**Appeals (us):** fix the scalar fail-open in §4. Consider distinguishing "payor unknown" from
"CARC not covered" (§3C). CARC 24 / capitation is a real corpus gap.

**Chat:** remove the manufactured default (§5). Make `usable` per-field rather than a single
boolean (§3D). Read `_suppressed` / `_party_suppressed` rather than inferring from empty lists.
Verify the caller isn't snake_casing payor names (§2).

Live coverage number at any time: `GET /admin/facts/evidence-audit`.

---

## 7. Payor-name resolution — `payer-canonical` is NOT safe for a filing-critical path yet

**Added 2026-09-09** after Platform seat proposed resolving payor names via the Lexicon.
Source read at `mobius-payor/app/routers/registry_admin.py`, behaviour confirmed live.

**Confirmed:** `_canonicalize_one` tier 2 does `canonical=key.replace("_"," ").title()`
(`_hit()`), so **every `via: "lexicon"` name is a synthesised string, not a record**. Tier 1
reads `SELECT DISTINCT payor, j_tag FROM payor_readiness_asset` — a *readiness* table — and
`_resolve_payor` (`app/skills.py:167`) anchors on the same table, so tier 1 is doubly bound to
it. Docstring scopes the endpoint to *"ingest/publish."*

### 🔴 New finding A — the derivation DROPS SCOPE QUALIFIERS and reports success

```
?value=Molina Healthcare of Florida
  → {"canonical":"Molina Healthcare","j_tag":"j:payor.molina_healthcare",
     "resolved":true,"via":"lexicon"}
```

"of Florida" is **silently dropped**, and it returns `resolved: true`. A Florida Medicaid MCO
(42 CFR 438, state contract, its own appeal chain) is canonicalised to the national brand.
This is worse than mangling a name: mangling fails loudly as a miss, this **succeeds
confidently at the wrong granularity** — the exact product_line/state collapse the fact-store
key was designed to prevent, arriving with `resolved: true` attached.

### ⚠️ Finding B — CORRECTED: coverage, not the matcher

*Superseded 2026-09-09. The discriminating test (`florida community care` → `resolved:true,
via:lexicon`) proves a florida-first key clears **pass 1**, blocklist never consulted. So
`florida blue` → unresolved means the KEY IS ABSENT — a Lexicon coverage gap, not a matcher
defect. My original evidence showed a miss and attributed it to the mechanism I had just read.
The blocklist remains a latent defect for brand-token-only inputs (`?value=blue` → unresolved
while `molina` and `sunshine` resolve), but it is lower priority, and its stated rationale is
already handled by pass 1. Original text below, kept for the record.*

### ~~New finding B — the `_GENERIC` blocklist has a blind spot over our entire pilot geography~~

Pass 2 skips brand tokens in `{florida, community, health, healthcare, care, national, blue}`.
The intent is sound (stop *"florida community care"* claiming *"Molina Healthcare of Florida"*),
but any payor key whose **first token** is one of those is unreachable via pass 2 — including
`florida_medicaid` and `florida_blue`. Florida Blue is a major real payor whose brand token is
literally blocked. Confirmed: `?value=florida medicaid` → `resolved: false`.

Our pilot is entirely Florida.

### Identity question, sharpened

`?value=AHCA` → `{"canonical":"AHCA","j_tag":"j:payor.ahca","via":"registry"}` — AHCA **is** a
canonical payor. `FL Medicaid` is not. Someone will be tempted to map one to the other. AHCA is
the *agency*; FL Medicaid is the *program*; the MCOs beneath it are separate payors with their
own appeal chains. Mapping them would serve the state agency's process for a plan denial.
**Payor seat to rule on identity — not a synonym row.**

### Appeals' position

Do **not** wire this into `/playbook-guarded` yet. When we do:

| `via` | Meaning | Appeals treatment |
|---|---|---|
| `registry` | a looked-up record | proceed |
| `lexicon` | a **derived string**, may have dropped qualifiers | surface to the user for confirmation; **never key another lookup on it** |
| unresolved | — | honest gap, distinct reason code |

Preconditions before wiring: (1) tier-2 derivation replaced by a lookup, (2) FL Medicaid
identity ruled on, (3) payor seat ratifies runtime use — an ingest-time resolver that is
occasionally wrong is a data-quality issue; a runtime one on a filing-critical path serves a
wrong payor's deadline.


---

## 8. §7 CORRECTION — Finding A is in TIER 1 too, and it is BY DESIGN

**2026-09-09.** §7 told consumers to trust `via: "registry"`. **That is wrong.**

```
?value=aetna better health of florida
  → {"canonical":"Aetna", "resolved":true, "via":"registry"}
```

`_resolve_payor` (`mobius-payor/app/skills.py:167`) performs the same residual-free substring
match, over `{key, key.replace("_"," "), key.split("_")[0]}`, keeping the longest **match** and
never checking what the input had left over. Its docstring states the intent plainly:

> *"Every variant of a brand ("Aetna Better Health of Florida", "Aetna Florida", "Aetna")
> contains the j-tag key ('aetna'), so we match the payor whose j-tag key appears in the query."*

So Aetna Better Health of Florida — a Florida Medicaid MCO with its own appeal chain — resolves
to the national Aetna brand, via the tier we were treating as authoritative.

**`via` distinguishes DERIVED from LOOKED-UP. It does not distinguish EXACT from GENERALISED**,
and for a filing-critical path the second is the one that matters.

### This is not a bug — it is a semantic mismatch

The generalisation is **correct for the endpoint's actual consumer**. Ingest and publish need
every Aetna variant collapsed onto one canonical payor to stamp a corpus. A residual check would
break RAG's publish path to serve a consumer that is not using it yet.

| | Question the endpoint answers |
|---|---|
| ingest/publish (today's consumer) | *which brand family is this document about?* |
| appeals (proposed consumer) | *which contracting entity adjudicated this claim?* |

Different questions. Only one can be right per endpoint.

### Revised ask — a mode, not a fix

1. A **strict** resolution that refuses `resolved:true` when the match leaves a meaningful
   residual, and **returns the residual**. Flag, parameter or sibling endpoint — payor seat's call.
2. Default behaviour unchanged, so ingest is untouched.

### Revised preconditions before appeals wires this

1. ~~tier-2 derivation replaced by a lookup~~ → **a strict/residual mode exists**
2. FL Medicaid identity ruled on
3. Payor seat ratifies runtime use of an ingest-scoped endpoint
