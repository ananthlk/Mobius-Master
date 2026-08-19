# Mobius Discovery — ingest contract

**For:** any agent that acquires documents the corpus does not yet have.
**From:** Master RAG Coordinator. **Status:** contract, 2026-08-19.

Discovery is not "upload with a different label". It is the loop by which the
system notices what it is missing and goes and gets it. That makes two things
different from an operator upload: the request must carry **why** the document
was fetched, and the system must be able to tell you **it already had it** without
that being a failure.

---

## 0. Before you fetch anything: ask what is missing

Discovery driven by "here is a site, crawl it" produces volume. Discovery driven
by a measured gap produces value. The gaps are queryable — use them as your work
list rather than inventing one:

| Gap | Where to read it | What to fetch |
|---|---|---|
| pairs that cannot be ordered | `GET /corpus/duplicates?actionable=false` → 195 groups | a dated edition of either document |
| documents with no text layer | Corpus Health → Stopped → `needs_ocr` (276) | a text-bearing version of the same document |
| payer/program with thin coverage | `GET /corpus/health?payer=X` → `documents_total` | the payer's manual, fee schedule, policy index |
| questions retrieval answers badly | `rag_query_decisions` (low-confidence answers) | the document that would have answered it |

**A fetch with no gap behind it is not discovery.** Put the gap in the request
(`discovery_reason`) so the system can later tell whether acquiring it helped.

---

## 1. How to submit — and how NOT to create duplicates

`POST /upload` (multipart) or `POST /documents/import-from-gcs` (already staged).

**The duplicate question is already answered for you, three times over. Do not
build your own check.**

1. **Byte-identical → 409, and that is a SUCCESS.** `documents.file_hash` is
   sha256 of the bytes, unique, checked before insert. If you re-fetch a page
   that has not changed, you get a 409 with the existing `document_id`. Record it
   as `already_present`, not as an error, and do not retry. This is the cheapest
   correct outcome in the system: no chunk, no embedding, no vector.
2. **Same URL, changed bytes → submit it.** That is a new edition and the
   versioning gate wants it. Send `source_url` so the gate can find the prior.
3. **Different URL, same text → submit it and let the gate decide.** Do not
   suppress it yourself. It may be a duplicate, or a product variant, or the same
   form for a different year — three outcomes that look identical to a fetcher and
   are separated by rules you do not have. Suppressing here loses documents that
   are legitimately distinct. We nearly deleted this year's attestation forms in
   favour of last year's by conflating exactly these.

**Never dedup by filename.** `CMS-Panretin.pdf` and `Panretin.pdf` are different
products; `GME_Attestation_SFY2025-26` and `SFY2024-25` are different years. Both
score ~1.00 on text similarity and both must be kept.

---

## 2. What to send

```
POST /upload?payer=AHCA&state=FL&program=Medicaid
  file=@doc.pdf
  source_url=https://...            # REQUIRED for discovery. It is the identity
                                    # that makes a re-fetch recognisable later.
  discovery_reason=<the gap>        # e.g. "ordering_unknown pair 0035e109 needs a dated edition"
  discovered_by=<your agent name>
```

**Dates — send only what the DOCUMENT says.**

- `effective_date` — only if printed in the document ("Effective January 1, 2024").
- `termination_date` — only if the document states an end of coverage.
- **Never send a computed or default termination date.** `/upload` used to invent
  `today + 182 days`; it produced 9,871 rows that read as real end-of-coverage
  dates and were a refresh cadence. A constraint now rejects an unsourced
  termination date, and ingest was down for a day because of it. NULL means
  "open-ended", which is almost always the truth.

If you can read a date off page 1 that we cannot, that is the single most
valuable field you can send: 195 pairs are unresolvable today for want of one.

---

## 3. How I answer you

Every submission gets one of four outcomes. Treat them as data, not as
success/failure:

| Outcome | Meaning | What you do |
|---|---|---|
| `201 created` | new document, pipeline started | record `document_id`, move on |
| `409 duplicate` | byte-identical to `document_id` | record `already_present`; do NOT retry |
| `4xx rejected` | malformed, unreadable, or PHI-blocked | read the detail; it says which |
| `5xx` | our fault | retry with backoff; if it persists, write to the coordination file |

**Where to watch what happened next**, since ingest is asynchronous:

- `GET /corpus/health` — your document moves through extracted → chunked →
  embedded → published. If it stops, the stage tells you why and who owns it.
- `GET /corpus/duplicates` — if it paired with something, it appears here with
  the rule that fired and the evidence.
- Corpus Health → **Stopped** — if it landed in `needs_ocr`, no OCR step exists
  yet; that is a known gap, not a transient failure.

**I do not push notifications.** Poll the health endpoint, or read the
coordination file. If something you submitted is stuck in a way the dashboard
does not explain, write it to `docs/RAG_FACTSTORE_COORDINATION.md`-style channel
with the document_id and I will answer there.

---

## 4. The self-learning loop, closed

A discovery run is only worth repeating if it changed something. After a batch:

1. Re-read the gap you cited in `discovery_reason`. Did the number move?
2. If you fetched to resolve `ordering_unknown` pairs, check
   `GET /corpus/duplicates?actionable=false` — the count should drop as dates land.
3. If it did not move, say so. A discovery run that fetched 40 documents and
   moved no gap is a finding about the gap, not a success to be repeated.

**Report per batch**: submitted, created, already_present (409), rejected, and the
gap metric before and after. Volume alone is not a result.

---

## 5. The rules that will bite you if ignored

- **A 409 is not an error.** Retrying it wastes a fetch and pollutes your logs.
- **Do not invent dates.** See §2. This one took the whole ingest path down.
- **Do not filter out near-identical documents.** Send them; the gate separates
  duplicate from product variant from period series, and it needs both copies to
  do it.
- **`source_url` is not optional for discovery.** Without it a re-fetch cannot be
  recognised as the same page, and every crawl creates new lineage-less documents.
- **Fetch what a gap names.** The corpus does not need more volume; it has 9,876
  documents and 276 of them cannot be read at all.
