# `/upload` is failing for everything — handoff to the RAG agent

**From:** Service Line Registry / Deep Research
**Date:** 2026-08-19
**Why you care:** every document ingest through `POST /upload` currently 500s. Found while building an automated acquire→ingest→retry loop; not specific to that loop.

---

## 1. The defect — `/upload` writes a termination date without its provenance

```
asyncpg.exceptions.CheckViolationError:
new row for relation "documents" violates check constraint
"ck_documents_term_date_provenance"
```

The constraint:

```sql
CHECK (termination_date IS NULL OR termination_date_source IS NOT NULL)
```

The upload path sets the date and never sets the source:

```python
termination_date_obj = date.fromisoformat(default_termination_date())
```

Three call sites, all with the same shape — so this is not just the UI upload:

| Site | Endpoint |
|---|---|
| [`main.py:7252`](../mobius-rag/app/main.py) | `POST /upload` |
| [`main.py:7724`](../mobius-rag/app/main.py) | `POST /documents/import-from-gcs` |
| [`main.py:7990`](../mobius-rag/app/main.py) | `POST /documents/import-from-html` |

The `Document(...)` constructor at `main.py:7253` passes `termination_date=termination_date_obj` and no `termination_date_source`.

**Reproduce** (any PDF, no special params):

```bash
curl -sS -X POST "http://127.0.0.1:8001/upload?payer=AHCA&state=FL&program=Medicaid" \
  -F "file=@some.pdf"
```

**Two candidate fixes, and the choice is yours because they differ in retention behaviour:**

1. Stamp the provenance alongside the default — `termination_date_source='upload_default_ttl'` (or whatever vocabulary the column already uses elsewhere) at all three sites. Smallest change, preserves current behaviour.
2. Stop defaulting a termination date on upload — leave it `NULL` and let whoever knows the real termination set it. Arguably more correct: a default TTL invented at upload time is not provenance-bearing, which is presumably why the constraint exists.

Whichever you pick, the other two sites need it too.

**Likely blast radius:** nothing has landed in `documents` in this database in 24h (newest row `2026-08-18 01:09`). Ananth reported ingesting a document that never appeared — consistent with this.

---

## 2. Environmental — the RAG on :8000 is running two-week-old code

Not your bug, but it changes the error you see, so worth knowing before you debug:

| | |
|---|---|
| Process on `:8000` (PID 98161) | started **Mon Aug 3 21:43** |
| `mobius-rag/app/models.py` | modified **Aug 17 11:22** |

`models.py:22-23` now declares `effective_date` / `termination_date` as `Column(Date)` ("Synced with DB migration 020"). The Aug-3 process still binds them as `VARCHAR`, so against **that** server every upload fails earlier with a different error:

```
column "effective_date" is of type date but expression is of type character varying
```

So the same broken call produces two different errors depending on which server you hit. On stale `:8000` you get the datatype mismatch; on current code you get the check-constraint violation, which is the real one.

I did **not** restart `:8000` — other agents may be using it. I started a fresh instance on `:8001` from `.claude/launch.json` (`mobius-rag-backend`) and confirmed the constraint error there against current code.

---

## 3. Two other things I tripped over, offered as context, not asks

- **`document_text_tags` is empty — 0 rows globally**, while `document_tags` has 9,718. So lexicon tagging is document-level only; there is no per-chunk tag data. If anything downstream assumes chunk-level tags exist, it is reading an empty table. (`hierarchical_chunks` has no tag columns at all.)
- **Tagging itself looks healthy.** Spot-checked `59G-4.028.pdf`: tagged `2026-08-17` at lexicon revision **2440**, which is current — 55 `d`, 6 `p`, 12 `j` tags, including the `place_of_service.*` ones. So whatever else is stale, the tagger is not.

---

## 4. What I need, and what I don't

**Need:** the fix decision in §1 (stamp provenance vs. stop defaulting). Once `/upload` accepts documents again I can re-run my loop unattended — the four PDFs are already downloaded and staged, so there is nothing to re-fetch.

**Don't need:** any change on your side for my loop's benefit specifically. This is a general ingest outage that happens to be blocking me.

Four AHCA fee schedules waiting to ingest, all confirmed absent from the corpus first:
`2026 BA Fee Schedule.pdf` · `2026 BHOS Fee Schedule.pdf` · `2026 SIPP Billing Codes.pdf` · `Specialized Therapeutic Services - July 8, 2025.pdf`

Every attempt is recorded in `research.repair` (action `acquire`) with the exact error, if you want the raw trail.
