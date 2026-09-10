# Chat's own tools — source of truth for the manifest

**Written by the Tool Manifest seat, 2026-09-10, from the implementations.**
**These sixteen tools have no owning seat.** Ananth asked for them to be written
properly rather than compiled from manifest prose, so every claim below traces
to a line in `mobius-chat/app/skills/builtin/` or `app/pipeline/`.

**What that does and does not buy.** Arguments, sequencing, failure modes, limits
and cost are recoverable from source and are stated with their evidence.
**Coverage is not.** Where a tool's real coverage is unknown to me I say so
rather than leaving a confident gap — that is the dimension that has changed
selection most, and inventing it would be worse than admitting it.

---

## ⚠️ One finding that spans almost all of them

**`signal="no_sources"` collapses distinct causes across the builtins too**, not
only on the MCP path. `corpus_search.py:550-553` documents three different
outcomes returning the same signal:

- no `RAG_API_URL` configured → `no_sources`
- HTTP 4xx/5xx from the RAG service → `no_sources`
- empty chunks / non-ok contract status → `no_sources`

The first is a **deployment fault**, the second an **outage**, the third a
genuine **content gap**. A caller reading `signal` cannot tell "we are
misconfigured" from "the corpus does not contain this", and the second is the
only one where retrying helps.

**Two builtins do better and are worth copying.** `transform_previous.py:205`
returns `system_context` on success, so it *is* discriminating. And
`document_uploads.py:60` returns the best failure text in the catalogue:

> *"I couldn't read this conversation's uploaded-file list just now (a storage
> read failed). **That is not the same as having no uploads** — please try again
> in a moment."*

That sentence is the standard the other fourteen should be held to.

---

# 1. `rag`

## FINDING

**1. Real phrasings:** what does the policy say about X · does this payer require prior auth ·
what's the timely filing limit · how do I submit a claim to them · what are the credentialing
requirements · is this service covered · what documentation do they want · what's the process for
X · does Medicaid pay for this · what are the eligibility rules · how long do I have · what does
the manual say · is there a policy on this

**2. The decision being made:** *What is the rule?* Someone needs the written position before
acting — the answer exists as a sentence in a document, and they need it and its citation.

**3. Entity vocabulary:** policy, provider manual, coverage policy, billing guide, handbook,
prior authorization, prior auth, PA, precertification, timely filing, filing limit, claims
submission, credentialing, enrollment, appeals process, medical necessity, criteria, guidelines,
requirement, rule, regulation, statute, AHCA, Medicaid, Medicare, managed care, MCO, health plan,
payer, payor, covered service, non-covered, exclusion, limitation, documentation, fee schedule,
rate, reimbursement.

**4. What the user has in hand:** a question and usually a payer or state. They do not have a
document identifier and are not asking for a file.

**5. What this does NOT answer (own boundary):** anything requiring a computation across many
records — a count, a ranking, a percentage, market share, a trend, a comparison between
organisations. Those answers exist in no document as a sentence. Nor live status for a named
provider or organisation. The test is whether the honest answer is a **statement from a document**
or a **computed result**; the presence of an organisation's name in the question is not itself the
signal.

**6. Coverage:** ⚠️ **UNKNOWN TO ME AND NEEDS AN OWNER.** The corpus behind this tool is the whole
RAG index; its real coverage by payer, state and document type is a question for the corpus owner,
not something recoverable from `corpus_search.py`. Elsewhere in this catalogue asking that question
found one real payor behind 141 rows. **Nobody has asked it here.**

## EXECUTING

**7. Arguments:** `query` — the user question as asked. Payer and state names help.

**8. Sequencing:** none. This is the general retrieval entry point.

**9. Return shape:** numbered passages `[1]…[N]` with page citations and confidence.

**10. Failure modes** — `corpus_search.py:550-553`:

| condition | returns | what the loop should do |
|---|---|---|
| `RAG_API_URL` unset | `no_sources` + explanatory text | **deployment fault.** Retrying cannot help |
| HTTP 4xx/5xx | `no_sources` + redacted error | **transient.** Retry is reasonable |
| empty chunks / non-ok status | `no_sources` | **genuine gap.** Do not retry the same query |

🔴 **All three look identical on `signal`.** The distinguishing information is in the text, not
the field a caller is told to branch on. And a source gap (the document exists but is not indexed)
is indistinguishable from a content gap (the fact is documented nowhere) in this output alone.

**11. Cost:** the full retrieval pipeline. **120-second HTTP timeout** (`:134`) — by an order of
magnitude the most expensive read in the catalogue.

---

# 2. `recall_evidence`

## FINDING

**1. Phrasings:** that chunk from earlier · the one you set aside · go back to what you found
before · pull that passage back · show me all of that result

**2. Decision:** *A passage I skipped earlier turns out to matter.* Recovery, not search.

**3. Vocabulary:** earlier, before, previous, set aside, that chunk, that passage, the one you
found, go back, full text, in full.

**4. In hand:** a reference from an earlier result in the same turn, shaped `call.chunk` (e.g.
`2.4` = tool call 2, chunk 4).

**5. Does NOT answer:** anything not already retrieved **in this turn**. It performs no search and
cannot reach prior turns.

**6. Coverage:** complete for what it covers — it recalls from in-turn state, so there is no data
gap to declare.

## EXECUTING

**7.** `refs` — list of `"call.chunk"` strings.
**8. Sequencing:** requires a prior retrieval **in the same turn**. Nothing to recall on round 0.
**9. Returns:** the original untruncated chunk text.
**10. Failure:** an unknown ref returns nothing for that ref. It is not a search failure.
**11. Cost:** local, instant, no retrieval budget consumed.

---

# 3. `fetch_document`

## FINDING

**1. Phrasings:** send me the manual · download that policy · get me the file · open the document ·
show me the whole thing · read this document and summarise it · what does page 20 say · I want the
actual PDF · can you attach it · the source document itself

**2. Decision:** *I need the document, not an answer about it.* Either to read in full, or to hold.

**3. Vocabulary:** document, file, PDF, manual, handbook, policy document, attach, attachment,
download, link, copy, source, original, page, pages, section, chapter, appendix, exhibit, full
text, whole document.

**4. In hand:** a document name, filename, policy ID, or an identifier already held. Not a topic.

**5. Does NOT answer:** a broad question answered from passages spread across many documents. It
is for when a single real source is the point.

**6. Coverage:** the ingested corpus, **plus** payer and agency sites known but not yet ingested.
⚠️ **The second half is unquantified** — which sites, and how reliably they fetch, is not
recoverable from source.

## EXECUTING

**7. Arguments:** `query` (name/filename/policy ID, matched by text) · `document_id` (**only** when
the exact UUID is already held — never guess one) · `pages` (e.g. `"20-24"`, `"20,80"`).

**8. Sequencing:** several text matches return a short pick-list; call again with the chosen
`document_id` to pin and attach.

**9. Returns:** document content — the native file when small, parsed text when large — a download
link for the user, and `page_count`.

**10. Failure modes** (`fetch_document.py:98-173`):

| condition | behaviour |
|---|---|
| file over **8 MB** (`_ATTACHMENT_MAX_BYTES`) | not attached natively; falls back to parsed text |
| fetch exceeds **12 s** (`_ATTACHMENT_FETCH_TIMEOUT_S`, raised from 6 s on 2026-08-17) | falls back |
| 404 / network error | falls back |

🔴 **A truncated read is not an absent section.** A large document returns as much text as fits
plus `page_count` — request pages explicitly rather than concluding the content is missing.

**11. Cost:** a fetch plus a parse; 12 s per URL attachment attempt.

---

# 4. `ingest_url`

## FINDING

**1. Phrasings:** index this URL · add this PDF to the corpus · pull in this page · can you ingest
this · make this searchable · add this provider manual · save this policy so we can search it

**2. Decision:** *Make this specific source permanently searchable.*

**3. Vocabulary:** ingest, index, add, import, load, fetch and save, make searchable, add to
corpus, URL, link, PDF, page.

**4. In hand:** a specific canonical URL they have decided they want.

**5. Does NOT answer:** anything. It is a write, not a read — it changes what is searchable and
returns a status.

**6. Coverage:** PDF and HTML both work; the inlet auto-detects. **A page that is blocked or
requires authentication will not fetch cleanly** and needs a manual upload instead.

## EXECUTING

**7.** `url` — the canonical URL.
**8. Sequencing:** after it returns ok, **re-run the original question against retrieval** — the
document is only available then.
**9. Returns:** `{document_id, status, sections}`.
**10. Failure:** a blocked or auth-walled page fails to fetch cleanly; ask for a manual upload.
**11. Cost:** fetch + chunk + embed + publish. **Minutes, not seconds**, and it consumes Vertex
tokens and storage.

🔴 **Requires explicit user approval for the specific URL.** One per call; for a list, call
repeatedly with confirmation each time.

---

# 5. `web_scrape`

## FINDING

**1. Phrasings:** what does this page say · check this site · read this URL · what's on that page
now · look at this link · is it still listed there

**2. Decision:** *What does this page say right now?* Currency is the point.

**3. Vocabulary:** page, site, website, URL, link, read, check, look at, current, live, now,
today, still.

**4. In hand:** a URL.

**5. Does NOT answer:** anything from the indexed corpus, and it does not add what it reads to it.

**6. Coverage:** the open web, minus whatever blocks automated fetching. ⚠️ **Unquantified.**

## EXECUTING

**7.** `url` · `scrape_mode` (optional fetch strategy).
**8. Sequencing:** none.
**9. Returns:** the page's readable content. Does **not** index it.
**10. Failure:** many origins block automated fetching. **A refusal is the site's, not evidence
the page is empty** — do not report the content as absent.
**11. Cost:** one live fetch against a third-party origin.

---

# 6. `document_upload_skill`

**1. Phrasings:** how do I upload · how do I attach a roster · can I send you a file · what
formats do you take · how does upload work · is there an API for it · how do I send my provider list

**2. Decision:** *How do I get my file to you?*
**3. Vocabulary:** upload, attach, send, file, document, roster, spreadsheet, CSV, PDF, paperclip,
API, endpoint, format, supported.
**4. In hand:** a file they want to send.
**5. Does NOT answer:** it does not move any bytes. It answers *how*, never *do it*.
**6. Coverage:** complete — it is static instructional content.

**7.** no arguments. **8.** none. **9.** Markdown: purposes, the UI path (paperclip in the
composer), the HTTP endpoint (`POST /chat/roster-upload`), and the relation to roster
reconciliation. **10.** none meaningful. **11.** trivial, static (`document_uploads.py:20`).

---

# 7. `list_thread_document_uploads`

**1. Phrasings:** what did I upload · what's on file · what documents have I sent · did my upload
go through · which files are attached · what was in that roster

**2. Decision:** *What have I already given you?*
**3. Vocabulary:** uploaded, attached, on file, sent, my documents, my files, roster, earlier.
**4. In hand:** a memory of having uploaded something.
**5. Does NOT answer:** what is *inside* any of them.
**6. Coverage:** complete for the current conversation.

**7.** `thread_id` — defaults to the current conversation, filled server-side.
**8.** none. **9.** Markdown table of uploads plus reconciliation defaults if set.

**10. Failure — and this one is the model for the whole catalogue** (`document_uploads.py:60`):
a storage read failure returns *"I couldn't read this conversation's uploaded-file list just now
(a storage read failed). **That is not the same as having no uploads** — please try again in a
moment."* An empty list and an unreadable list are **different**, and this tool is the only one
here that says so in its own text.

**11.** one read.

---

# 8. `search_uploaded_document`

## FINDING

**1. Phrasings:** what does my uploaded doc say about X · summarise the PDF I just sent · find the
prior-auth rules in this manual · what's in the file I attached · look in my document for that ·
search the roster I uploaded

**2. Decision:** *Answer from the file I gave you, not from the corpus.*
**3. Vocabulary:** my document, my file, my upload, the PDF I sent, attached, uploaded, this
manual, in the file, inside the document.
**4. In hand:** a file already attached to this conversation.
**5. Does NOT answer:** anything about the general corpus, and it cannot see a document attached to
another tool's result.
**6. Coverage:** only instant-RAG thread uploads on the current conversation.

## EXECUTING

**7.** `query` — **a content query, not a command.** It is a semantic vector search: for a summary,
use the document's topic or filename ("provider billing manual overview"), **not** the word
"summarize". `upload_id` — omit when exactly one upload exists and the server resolves it.

**8. Sequencing:** requires at least one instant-RAG upload on the thread.

**9. Returns:** matching passages from the uploaded file.

**10. Failure — 🔴 the scope trap:** a document attached to **another tool's result** is a native
attachment, **not** a thread upload, and this tool cannot see it. It fails with *"No uploads on
this thread."* **If a document has already been attached to a tool result, that IS the document —
read it from the result rather than calling this.**

**11.** one vector search over the uploaded file.

---

# 9. `healthcare_query`

## FINDING

**1. Phrasings:** what does F32.1 mean · what is Z00.00 · what does this CPT code cover · is this
covered by Medicare · what does this HCPCS code describe · what's the definition of this code ·
NCD for this procedure · is there an LCD

**2. Decision:** *What is this code, or what does Medicare say about it?*
**3. Vocabulary:** ICD-10, ICD-10-CM, diagnosis code, CPT, HCPCS, procedure code, code definition,
what does it mean, NCD, LCD, national coverage determination, local coverage determination,
Medicare coverage, Medicaid coverage.
**4. In hand:** a code, or a general coverage question.
**5. Does NOT answer:** provider enrollment or provider-list status, and it cannot find an
organisation's NPI from its name.

**6. Coverage — 🔴 a VERIFIED known-bad slice:** for **Florida Medicaid behavioural-health HCPCS
(H-codes, T-codes)** this tool **generates** a definition rather than looking one up, and has been
observed returning **different wrong definitions on repeated calls for the same code**. Treat any
FL Medicaid BH code answer from here as unsourced. Coverage elsewhere is otherwise unquantified
and needs an owner.

## EXECUTING

**7.** `question`. **8.** none. **9.** code meaning, coverage summary, or NPI registry facts.
**10.** error shape is graceful fallback text with `signal="no_sources"` (`healthcare.py:25`) —
**identical to its success signal at `:96`**, so `signal` does not discriminate here either.
**11.** one external lookup.

---

# 10. `healthcare_npi_lookup`

**1. Phrasings:** who is NPI 1234567890 · what's the taxonomy for this NPI · what address is on
file · is this NPI an org or a person · look up this NPI

**2. Decision:** *Whose number is this?*
**3. Vocabulary:** NPI, national provider identifier, 10-digit, registry, NPPES, taxonomy,
specialty, practice address, registered name.
**4. In hand:** a 10-digit NPI.
**5. Does NOT answer:** the reverse direction. **Number in, identity out** — it cannot find an NPI
from a name. A diagnosis, procedure or billing code is not an NPI even though it contains digits.
**6. Coverage:** the NPPES national registry — a **third-party API**, complete for US providers,
and only as current as NPPES itself.

**7.** `question` (must contain the NPI). **8.** none. **9.** registered name, taxonomy, address.
**10.** graceful fallback text, `signal="no_sources"` — indistinguishable from success on that
field. **11.** one third-party registry call.

---

# 11. `payor_readiness`

**1. Phrasings:** what do we have on this payor · how complete is our coverage of them · what
documents are we missing · are we ready for this payor · what's our readiness score

**2. Decision:** *How good is OUR data on this payer?* An internal question, not a billing one.
**3. Vocabulary:** readiness, coverage, ingested, documents held, gaps, missing, complete,
scorecard, grounded, integrity.
**4. In hand:** a payor name, or none for a roster-wide view.
**5. Does NOT answer:** any of the payor's actual rules. It reports on the state of our corpus.
**6. Coverage:** whatever payors the readiness registry holds. ⚠️ **Unquantified here.**

**7.** `payor` (optional). **8.** none. **9.** ingested counts, known coverage, grounded fact count,
gaps. **10.** unreachable service returns `signal="no_sources"` with the error under
`extra.error` (`payor.py:47,64`) — **the error detail is present but not in the signal.**
**11.** one read, **30-second timeout** (`payor.py:26`).

---

# 12. `product_help_search`

**1. Phrasings:** how do I do this in Mobius · where is that screen · what is the Public Library ·
what is the Vault · what does Strategy do · what is the Roster · what is the Pipeline · how does
chat work · where did that button go · how do I set up a lexicon

**2. Decision:** *How does this product work?*
**3. Vocabulary:** Mobius, the app, the product, feature, tile, screen, page, button, menu,
sidebar, navigate, where is, how do I, setup, configure, Vault, Roster, Strategy, Pipeline,
Public Library, lexicon, skills.
**4. In hand:** a question about the product, often using a feature name that sounds generic.
**5. Does NOT answer:** healthcare policy, payer rules or claims questions — documentation about
the industry rather than about this product.
**6. Coverage:** the product documentation. **When something is undocumented it says so and logs
the gap** (`product_help_search.py:51`) — an answer, not an error.

**7.** `query` · `k` · `module` (chat, rag, lexicon, skills, strategy) · `audience`.
**8.** none. **9.** documentation passages. **10.** empty envelope with `signal="no_sources"` at
`:126` and `:141` — two different conditions, one signal. **11.** one search, **10-second timeout**.

---

# 13. `product_feedback`

**1. Phrasings:** I love this · this is confusing · I wish it could do X · you never have Ohio
Medicaid · the sidebar is broken · I want to report a bug · where is the feedback form · how do I
give feedback · this feature is great

**2. Decision:** *I want to tell you something about the product.*
**3. Vocabulary:** feedback, suggestion, complaint, bug, broken, confusing, wish, love, hate,
great, terrible, report, form, survey, rating, score, NPS, CSAT.
**4. In hand:** an opinion. **This tool IS the feedback path** — a request to find the feedback
form is served by using it, not by pointing at one.
**5. Does NOT answer:** a pure data or policy question carrying no opinion. **Never rates clinical
content.** Applies even when the same message also asks a real question.
**6. Coverage:** complete — it is a write path.

**7.** `trigger` (`on_demand` when they asked to give feedback) · `verbatim` · `category` ·
`context_excerpt` · `kind` (`survey`) · `survey_type` · `score` · `update` · `add_detail` ·
`feedback_id`.
**8. Sequencing:** 🔴 when the user corrects or extends feedback just given, call again with
`update=true`. **Without it you create a duplicate rather than editing the item.**
**9.** a playback receipt inviting edits.
**10.** an unfindable `feedback_id` returns *"I couldn't find that feedback to update — mind
restating it?"* (`:206`). **11.** one write, **10-second timeout**.

---

# 14. `transform_previous_answer`

**1. Phrasings:** turn this into an appeal letter · write that as an email · make it shorter ·
bullet this · summarise the above · put it in plain English · draft a memo from this · give me the
counter-argument · rewrite that · shorter version

**2. Decision:** *Reshape what you just told me.*
**3. Vocabulary:** this, that, the above, your last answer, convert, rewrite, shorten, lengthen,
bulletize, summarise, format as, draft from this, turn into, make it, plain English, email, memo,
letter, counter-argument.
**4. In hand:** a previous assistant answer in this thread.
**5. Does NOT answer:** a fresh substantive question, even a topically related one — that needs
retrieval.
**6. Coverage:** complete; the prior turn is the entire source.

**7.** `transformation` (optional).
**8. Sequencing:** 🔴 **requires a previous assistant answer. There is none on the first turn.**
**9.** the reshaped artifact; sources cite the prior turn.
**10.** no prior answer returns `no_sources` (`:157`); **on success it returns
`signal=system_context` (`:205`) — one of the few builtins where `signal` is meaningful.**
**11.** generation only, no retrieval.

---

# 15. `vibe`

**1. Phrasings:** (not a question) long day · finally done · ugh · thank god that's over · that
was painful · we did it · say something nice
**2. Decision:** *Acknowledge the moment.*
**3. Vocabulary:** tired, exhausted, long day, finally, done, ugh, thanks, celebrate, rough,
painful, brutal, made it.
**4. In hand:** nothing. A mood.
**5. Does NOT answer:** any real question, data request or documentation need. **Never about
patients, clinical topics or politics.**
**6. Coverage:** n/a.

**7.** `trigger` · `mode_hint` · `excerpt` · `position`. **8.** none.
**9.** one sentence, ≤15 words, **or empty**.
**10.** 🔴 **an empty return is a correct outcome, not a failure** (`vibe.py:55,59`) — do not retry it.
**11.** trivial, **10-second timeout**.

---

# 16. `refuse`

**1. Phrasings:** is member 12345 eligible · what should this patient be prescribed · is John Smith
covered · what treatment do you recommend for this patient
**2. Decision:** none — it declines.
**3. Vocabulary:** member ID, patient name, this patient, member number, subscriber, recommend
treatment, should they take, diagnose.
**4. In hand:** a question that identifies a specific individual, or asks for clinical judgement.
**5. Does NOT answer:** anything. A question about **rules, eligibility criteria, policy or
coverage in general is not protected health information and is not this.**
**6. Coverage:** n/a.

**7.** `reason` — PHI, or clinical recommendation. **8.** terminal. **9.** nothing.
**10.** 🔴 **this is a gate, not a retrieval: it fails CLOSED by design.** **11.** trivial.

---

## What is still missing, and who could close it

**Coverage for `rag`, `fetch_document`, `web_scrape` and `payor_readiness`.** Four tools whose real
coverage I could not recover from source and have marked unknown rather than guessed. `rag` is the
most consequential — it is the default retrieval path for the whole product, and its corpus
coverage by payer and state is exactly the question that, asked of the appeals family, found 141
rows behind one real payor.

**An owner.** These sixteen are chat's own code and no seat has claimed their semantics. This page
is the best I can do from the implementations; it is not a substitute for someone who knows what
the tools are *for*.
