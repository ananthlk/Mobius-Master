# Ingest admission control — every RAG ingestion path

**Owner:** Master RAG Coordinator · **Date:** 2026-09-07
**Mandate:** Ananth, 2026-09-06 — *"you control every rag ingestion path"*
**Status:** PROPOSED — needs Crawler ack on §3, then build

## Why this exists

The CPT/licensing screen lives inside the web-scraper. It protects crawled
content and nothing else. Deep Research's acquire arm reached AMA-licensed
material through `/upload` — a door the screen does not watch — and nobody had
done anything wrong: the constraint was never expressed at the endpoint.

Measured exposure at the time of writing:

    published rows containing AMA/CPT copyright text     625
    across distinct documents                            369
      policy / prose that REFERENCES CPT      609 rows, 363 docs
      fee schedule / rate table                16 rows,   6 docs

The 6 fee-schedule-shaped documents are the category Ananth excluded in August
("exclude the fee schedules... we will get the license later"). They include
Rule 59G-4.002 (74 published rows).

## 1. The perimeter is one place, which makes this small

Audited every module. **`Document` rows are created in exactly six endpoints,
all in `mobius-rag`:**

    /upload                          classifier: yes
    /documents/import-from-gcs       classifier: in the chunking worker
    /documents/import-from-html      classifier: yes
    /documents/import-from-drive     classifier: yes
    /drive/import-folder             classifier: yes
    /documents/import-scraped-pages  classifier: yes

`mobius-chat` contains no `Document(` constructor and no separate corpus
(`mobius_chat_rag` does not exist as a database) — its instant-RAG and thread
uploads call these endpoints. Crawler, Deep Research and the Drive importer
likewise.

**So "control every ingestion path" does not require reaching into other
modules' code.** One gate at the six endpoints and every caller inherits it.
That is the whole design, and it is far smaller than the mandate sounds.

## 2. What the gate does

A single `admit()` called by all six endpoints before a `Document` row is
created. It returns a verdict, and the endpoint refuses on `reject`.

    admit(source_type, filename, source_url, source_page_url, text_sample)
      -> {decision: admit|hold|reject, reason, rule_key, rule_version}

Three properties, each of which is a defect we hit this year:

  * **Fails closed.** The crawler's screen already does; the boundary must too.
  * **Names its rule.** `rule_key` is stable and machine-matchable, so a caller
    records something reconcilable instead of a prose string (Service Line
    Registry's `defect_key` argument — 4 documents lost 18 days to an
    unmatchable stack trace).
  * **`hold` is not `reject`.** Today `review_status` is a LABEL, not a gate —
    it appears three times in `main.py`, all sync statements, never in a WHERE
    clause on the retrieval path. A held document is fully retrievable. That is
    fixed separately (§4) and must not be conflated with admission.

## 3. ONE implementation of the licensing rule — NEEDS CRAWLER ACK

`mobius-skills/web-scraper/app/services/cpt_screen.py` is 166 lines of pure
functions with no I/O — `screen_html`, `screen_pdf_text`, `screen_file_url`,
all failing closed. It is good and it should not be copied.

**Proposal: move it to `mobius-contracts` and have both sides import it.**

Copying is the defect we have hit repeatedly: Fact Store and I nearly both
wrote `product_line` until they took the mapping and I became the scribe;
Crawler and I each held half a provenance contract. Two copies of a licensing
predicate would drift, and the drift would be invisible until something was
admitted that should not have been.

Crawler keeps authorship of the rule. I call it at the boundary. If Crawler
would rather keep it in the scraper and expose it, that works too — what must
not happen is a second regex.

## 4. Separate, and not optional: make `review_status` a gate

Publishing currently ignores `review_status`. A document marked for human
review is retrievable. Either the label means something at the retrieval
boundary or it should be deleted — a label that reads like a gate is worse
than no label, because everyone assumes it is one. I assumed it, and told
Ananth "nothing has leaked" on the strength of it.

## 5. Explicitly NOT in scope

Rewriting chat's or anyone else's ingestion code. The mandate is control of the
path, and the path converges on six endpoints I already own. Callers should
need no change beyond handling a `reject`.

## Open

  * Crawler ack on §3 (shared module vs exposed service)
  * Ananth's ruling on the 369 already-published documents — he ruled on a
    picture of one unpublished document; the real number is materially different
  * Backfill: nothing is removed until that ruling
