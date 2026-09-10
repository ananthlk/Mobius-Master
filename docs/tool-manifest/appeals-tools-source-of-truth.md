# Appeals tools — source of truth for the manifest

**Owner:** Appeals · **For:** Tool Manifest seat · **Date:** 2026-09-10
**Status:** content, not shape. Compile `find_text` / `exec_text` from this; this page stays canonical.

Rules honoured: **no tool names another tool**; **no cross-tool priority language**. Boundaries below
are stated as each tool's own limits.

---

## ⚠️ Read this before compiling anything

Three things I found while writing this page. Two are defects in my module; one corrects your diagnosis.

### (a) Your "got nothing twice" premise doesn't reproduce today

`appeals_lookup_rules` depends on **two** endpoints. Both answer for CARC 197 right now:

```
GET /rules/197        → 200, rules_found: 5   (PRECERT.R001 …)
GET /carc-config/197  → 200, title + root_causes
```

So the tool had data for the exact query that failed. Your ranking finding may still be entirely
correct — the right tool went 4→1 when you tightened the text — but **"it was called and returned
nothing" is not something I can confirm from the service side.** Candidates: a bad argument
(`carc=0`, or the payor string), an older revision, or a transport error rendering as an empty
result. Worth pinning before anything is built on it. **Note the tool returns errors as a bare
string** (`"[appeals_lookup_rules] Error fetching rules for CARC 197: …"`), not JSON — a loop
expecting JSON may well read that as "nothing."

### (b) 🔴 The fabricated FL Medicaid default is MINE, in `mcp_server.py`

```python
not_found_msg = _j({"found": False, …, "message": (
    f"No playbook found for {payor}. "
    "Use standard FL Medicaid appeal process: 42 CFR §438.408. "
    "Default deadline: 60 days from denial notice date. "
    "Submit via certified mail to payor appeals department.")})
```

I ruled against exactly this text yesterday and told another team to fix it on their side. **It is
emitted by my own tool.** An invented filing deadline with a real-looking regulatory citation
attached is the worst version of the failure class this project exists to remove. **Being removed.**
Until it is, the manifest must not describe this tool as returning a usable answer on a miss.

### (c) 🔴 The MCP tool reads the UNGUARDED playbook endpoint

`mcp_server.py` calls `/playbook/{payor}/{lookup}`. Chat's loop was moved to
`/playbook-guarded/…?audience=provider`; **the MCP path never was.** So the party filter that keeps
member-party remedies out of a provider ladder is bypassed here. **Being fixed.**

---

## Coverage, blunt — dimension 6, and it is thinner than the tool text implies

**There is exactly ONE real payor with data: Sunshine Health.**

| | |
|---|---|
| playbook rows | 141 |
| distinct payor names | 2 — `Sunshine Health` (69), `FL Medicaid` (72) |
| **real payors** | **1** |
| CARC codes with a playbook | 72 |
| filing-critical values | 339 |
| **sourced / citable** | **0 — 0.0%** |

**`FL Medicaid` is not a payor. It is a template.** All 72 rows share one identical
`appeal_levels` signature; every payor-specific scalar is blank (`deadline=None`, `portal_url=''`,
`fax=''`, `mail_address=''`); and its own ladder escalates *to* AHCA at level 5 — which the state
agency cannot do to itself. It is a generic managed-care ladder stored under a payor-shaped name.

**What this means for ranking, plainly:** for any payor that is not Sunshine Health, the playbook
tool has nothing real to return. Rank it accordingly per-payor if your selector can carry that.

**CARC catalog is separate and wider.** `/carc-config/{carc}` covers the built archetypes
(197, 22, 29, 50 confirmed). **CARC 24 is absent** — `404 "CARC 24 not in library"` — which is why a
recent CARC 24 turn correctly reported having no instructions.

**Nothing is sourced.** Every value is `basis: unverified`, `citable: false`. The first citable
value in the system's history was produced yesterday and is not yet integrated.

---

# 1. `appeals_get_playbook`

## FINDING

**1. Real phrasings (8–15, including sloppy):**
- how do i appeal a carc 197 denial for sunshine health
- how do I appeal this
- what's the appeal process for sunshine
- how long do i have to appeal
- deadline to appeal sunshine health
- where do i send the appeal
- sunshine health appeal fax number
- appeal address for sunshine
- do i mail or use the portal
- what forms do i need to appeal
- can i still appeal, denial was 2 months ago
- sunshine denied us, what now
- appeal levels sunshine health
- who do i escalate to if the appeal is denied
- 197 denial sunshine how to appeal

**2. The decision being made:** *Can I still file, and exactly how do I file it?* This is the
operational step after deciding to appeal — a person about to physically send something.

**3. Entity vocabulary (literal retrieval signal):**
appeal, appeals, how to appeal, file an appeal, filing, refile, deadline, due date, timely, days,
calendar days, business days, window, submit, submission, send, mail, certified mail, fax, fax
number, portal, provider portal, upload, address, PO box, attn, forms, form, required documents,
attachments, medical records, claim adjustment request, appeal levels, first level, second level,
internal appeal, external appeal, peer to peer, p2p, reconsideration, redetermination, dispute,
provider claim dispute, grievance, escalate, AHCA, CMS, denial, denied, EOP, remit, remittance,
835, CARC, CARC code, reason code, denial code, payor, payer, plan, health plan, MCO, managed care,
Medicaid, Sunshine, Sunshine Health, Centene, and bare integers 1–283.

**4. What the user has in hand:** a denial in front of them, a payor name, and usually a CARC
number or archetype. They already know *that* they were denied — they are past diagnosis.

**5. What this tool does NOT answer (own boundary):** it does not tell you *whether* you should
appeal, whether you have grounds, or what argument to make. It does not evaluate a claim, produce a
recommendation, or write anything. It does not interpret what a denial code means — it takes the
code as given. It does not identify a code from a description.

**6. Coverage:** Sunshine Health only, as above. 72 CARC codes. **Zero sourced values today** —
returns operational facts that have not been verified against a payor document. `FL Medicaid` rows
return a blank template.

## EXECUTING

**7. Arguments**
| arg | required | meaning | how to obtain if missing |
|---|---|---|---|
| `payor` | **yes** | payor display name — `"Sunshine Health"` | from the remit/EOP header, or ask the user. **Must be the display name; a snake_case slug returns empty.** |
| `carc` | one of | CARC integer, e.g. `197` | from the 835/EOP line, or identify it from a description first |
| `carc_group` | one of | archetype slug, e.g. `"auth_required"` | leave blank if you have the integer |

Pass **either** `carc` or `carc_group`. Both blank returns not-found without querying.

**8. Sequencing:** none required — callable directly when payor and code are known. If only a
plain-English denial description exists, the code must be established first.

**9. Return shape:** `found`, `payor`, `carc_group`, `carc_codes[]`, `deadline_appeal_days` (int|null),
`deadline_resubmit_days`, `submission_method` (`portal|fax|mail|certified_mail`), `portal_url`,
`fax`, `mail_address`, `docs_required[{doc, required, url, notes}]`,
`appeal_levels[{level, name, path, party, submission, deadline_days, notes}]`, `contacts[]`, `notes`.

**A present key is not a populated key.** `deadline_appeal_days: null` with a populated
`submission_method` is common (51% of rows) and means *we have no verified deadline*, not *no
deadline exists*.

**10. Failure modes**
| condition | returns | what the loop should do |
|---|---|---|
| no playbook for payor×CARC | `found: false` + **a fabricated default (defect b, being removed)** | say plainly that no payor-specific instructions are on file. **Do not repeat the default deadline to the user.** |
| wrong payor key format | same as not-found | retry once with the display name |
| deadline null, method present | `found: true`, `deadline_appeal_days: null` | render the channel; say the deadline is not on file. **Never substitute a typical value.** |
| service error | bare error **string**, not JSON | treat as unavailable, not as "no playbook" |

**11. Cost/latency:** one HTTP read, sub-second. Cheap to call, cheap to retry.

---

# 2. `appeals_lookup_rules`

## FINDING

**1. Real phrasings:**
- what does carc 22 mean
- what is a 197 denial
- why was this denied
- carc 29 explanation
- what does denial code 50 mean
- got a 16 denial what's missing
- is a 197 appealable
- do i have a case for carc 22
- what are my options on a timely filing denial
- reasons for carc 197
- what causes a 50 denial
- rules for carc 29
- what do i need to prove for 197
- carc 22 sunshine health

**2. The decision being made:** *What is this denial actually saying, and do I have grounds?* This
is diagnosis — earlier than filing mechanics.

**3. Entity vocabulary:** CARC, RARC, denial code, reason code, adjustment code, group code, CO,
PR, OA, 835, EOP, remit, remittance advice, denial reason, root cause, why denied, what does it
mean, explanation, definition, grounds, appealable, can I appeal, do I have a case, options,
argument, rule, rules, criteria, requirements, evidence, proof, documentation, action items, plus
the archetype words: timely filing, COB, coordination of benefits, other insurance, prior
authorization, precertification, precert, auth, medical necessity, non-covered, missing
information, bundling, NCCI, modifier, place of service, provider type, credentialing, eligibility,
benefit maximum, duplicate — and bare integers 1–283.

**4. What the user has in hand:** a CARC number, and often nothing else. They may not know the
payor and do not need to.

**5. What this tool does NOT answer (own boundary):** it does not give you a deadline, a fax
number, a portal, an address, or a required-document list. It does not know any payor's filing
mechanics. It does not produce a recommendation for a specific claim, and it does not write
anything. It requires the numeric code — it cannot start from a plain-English description.

**6. Coverage:** the built archetype library — 197, 22, 29, 50, 16 and the wider catalog; **CARC 24
is absent** (`404 "not in library"`). `payor` is accepted but does not currently narrow results, so
coverage does not vary by payor for this tool.

## EXECUTING

**7. Arguments**
| arg | required | meaning | how to obtain |
|---|---|---|---|
| `carc` | **yes** | integer code | from the 835/EOP; if the user only has a description, identify it first |
| `payor` | no | payor slug | leave blank if unknown — blank is fine and common |
| `inv_signals` | no | JSON string of known facts (`primary_ins`, `timely_filing_date`, `auth_number`) | pass `"{}"` when nothing is known |

**8. Sequencing:** none. Callable as the first appeals call in a turn.

**9. Return shape:** `carc`, `carc_title`, `rules_found`, `rules[{rule_id, rule_name, rule_statement,
scoring}]`, `action_items[{rule_id, text}]`.

**10. Failure modes**
| condition | returns | what the loop should do |
|---|---|---|
| CARC not in library | error string naming the code | say the code is not in the library; do not retry the same code |
| either dependency down | **bare error string, not JSON** | treat as unavailable — **not** as "no rules exist" |
| `rules_found: 0` | JSON with empty list | genuinely no rules; a retry will not help |

**The bare-string-on-error behaviour is the highest-value thing to encode.** A JSON-expecting loop
reads it as empty, retries, gets the same string, and concludes there is no data — which matches
the reported 197 turn better than the ranking explanation does.

**11. Cost/latency:** two HTTP reads, sub-second.

---

# 3. `appeals_find_carc`

**1. Phrasings:** they said we needed prior auth · denied for no authorization · says not medically
necessary · patient wasn't eligible · they said we filed too late · claim says duplicate · denied
because of the modifier · says another insurance is primary · we got denied but I don't have the
code · what code is this denial · denial says "not covered" · they want more information

**2. Decision:** *Which denial am I actually looking at?* Identification, before anything else.

**3. Vocabulary:** all the plain-English denial language above, plus: denial letter, EOB, EOP,
remit, denial reason, they said, says, rejected, not paid, zero paid, no payment, write-off,
description, plain English, don't know the code, what code.

**4. In hand:** a description in words. **Specifically no code** — that is the distinguishing
condition.

**5. Does NOT answer (own boundary):** it does not give filing mechanics, deadlines, or channels,
and it does not write anything. Its answer is a best-effort identification from wording, not a
determination of what the payor actually sent — the authoritative code is on the 835/EOP.

**6. Coverage:** matches against the built catalog only; a denial whose true code is outside the
library cannot be identified, and confidence is lower on short or generic descriptions.

**7–9.** `denial_description` (**required**, free text — pass the user's own words, not a
paraphrase; paraphrasing removes the matching signal), `payor` (optional). Returns ranked CARC
candidates with titles, archetypes, and rules.

**10. Failure modes:** no confident match → returns low-confidence candidates; treat as a prompt to
ask the user for the code off the remit rather than proceeding on a guess. **A wrong CARC
identification propagates silently through everything downstream.**

**11.** One read plus matching, sub-second.

---

# 4. `appeals_validate_claim`

**1. Phrasings:** should i appeal this · is it worth appealing · do i have a case · what should i do
with this denial · appeal or rebill · is this worth the time · should we write this off · what's my
best move · will this appeal win · recommend what to do

**2. Decision:** *Is appealing the right action at all* — versus correcting and resubmitting,
versus writing it off. This is the go/no-go.

**3. Vocabulary:** should I, worth it, recommend, recommendation, advice, best move, chances, odds,
likely to win, success rate, appeal or resubmit, rebill, corrected claim, write off, adjustment,
give up, action, next step, decision, ROI, amount, balance, dollars, date of service, DOS.

**4. In hand:** the code, usually the payor, often the dollar amount and date of service, and
sometimes answers about the claim's circumstances.

**5. Does NOT answer (own boundary):** it does not tell you the deadline, the channel, or the forms,
and it does not produce the appeal itself. Its output is a recommendation, **not a legal or clinical
determination**, and it is only as good as the signals supplied — thin signals produce a thin
recommendation, and it will not say so loudly.

**6. Coverage:** depends on the same archetype library; strongest where rules exist, weakest on
codes outside it. **Recommendations are not currently calibrated against real appeal outcomes** —
no won/lost feedback flows back, so treat confidence as heuristic, not measured.

**7–9.** `carc` (**required**), `payor`, `amount`, `dos`, `inv_signals` (JSON string of known facts —
**this is what actually drives quality**). Returns an action (`appeal | resubmit | do_not_appeal |
unresolved`), a rationale, and supporting rules.

**10. Failure modes:** unknown CARC → error string. Sparse `inv_signals` → an `unresolved` or
low-confidence action, which should be read as *ask the user more*, not as *no case*.

**11.** Model-backed; seconds, not sub-second.

---

# 5. `appeals_assemble_letter`

**1. Phrasings:** write the appeal letter · draft my appeal · generate the appeal · make me a letter
· write an appeal for carc 197 · draft a reconsideration request · put together the appeal packet ·
write it up for sunshine · i need the letter to send

**2. Decision:** *Produce the document I am going to send.* The decision to appeal is already made.

**3. Vocabulary:** letter, appeal letter, draft, write, generate, compose, produce, packet, cover
letter, reconsideration request, submission, template, document, attachments, exhibits, argument,
citation, sign, send.

**4. In hand:** a settled decision to appeal, the code, the payor, and ideally amount, DOS, denial
date, and completed action items.

**5. Does NOT answer (own boundary):** it does not decide whether to appeal, does not verify that
grounds exist, and does not file anything — output is a draft for human review and signature. It
does not confirm the deadline it writes against, and any date or citation in the draft must be
checked against a sourced fact before sending.

**6. Coverage:** written against FL Medicaid conventions. Output for other states or product lines
will be structurally reasonable and **jurisdictionally unverified**.

**7–9.** `carc` (**required**), `payor`, `amount`, `dos`, `denial_date`, `carc_group`,
`action_items` (JSON array), `inv_signals` (JSON), `action_path` (default `"appeal"`),
`session_id`. Returns the assembled letter plus its components.

**10. Failure modes:** missing `action_items`/`inv_signals` → a generic letter that reads complete
and is weak — **the most dangerous failure of the five, because it fails plausibly.** Pipeline error
→ error string.

**11. 🔴 Cost/latency: a five-agent pipeline, 30–90 seconds, synchronous.** By far the most
expensive tool here. Should not be reached speculatively, mid-diagnosis, or without the decision to
appeal already made.

---

## Answering your dimension-6 ask directly

You said you would rather know now than infer it from `no_sources` rates. So: **the coverage is
much thinner than the tool descriptions imply.** One real payor. Zero sourced values. A 72-row
template masquerading as a second payor. If the selector can weight per-payor, everything except
Sunshine Health should rank the playbook tool low — and the honest answer for those payors is that
we have nothing, which is a better user outcome than a confident empty result.
