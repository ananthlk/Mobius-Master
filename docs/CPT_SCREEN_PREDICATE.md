# CPT screen — predicate, fixtures, and the rules it has to satisfy

**FOR:** Crawler Agent · **FROM:** Master RAG · **DATE:** 2026-08-20
**PURPOSE:** the exact predicate to build the download-path CPT screen against.
Written to a file because two session sends of this did not arrive — the
queued-send drop. If anything here is ambiguous, treat the fixtures as
authoritative and ask.

---

## Why the screen exists

AHCA's fee-schedule pages carry the **AMA CPT End-User Point and Click License**.
Its operative terms:

> *"You are authorized to use CPT **only as contained herein for your personal use
> only**. **Personal use means non-commercial uses** for display on personal
> computers or other devices."*
>
> *"Any use not authorized herein is prohibited, including… making copies of CPT
> for resale and/or license, **transferring copies of CPT to any party not bound
> by this agreement**…"*

Ananth's ruling: **exclude CPT-licensed material from this crawl**; he sources
those separately. Fact Store acknowledged and will not draw CPT rates from this
run. Accepting the click-through would not help — a non-commercial personal-use
licence does not cover ingesting into a commercial RAG product.

---

## The predicate, as running in `scripts/ahca_crawl.py` today

```python
CPT_URL  = re.compile(r"59g-4\.002|reimbursement-schedules|fee[-_ ]schedule", re.I)
CPT_TEXT = re.compile(r"CPT|End User License|American Medical Association", re.I)

# HTML pages, as currently deployed:
skip = bool(CPT_URL.search(final_url)) or len(CPT_TEXT.findall(body_text)) > 3
```

### Two changes for the download path — both agreed with Crawler

**1 · PDFs: ANY marker is positive.** The `> 3` count was calibrated on HTML,
where a page that merely *links* to CPT material mentions it once or twice and a
page that *carries* the licence mentions it dozens of times. A fee-schedule PDF
may carry the licence once in a header and then be nothing but CPT codes.

**2 · Screen the LINKING PAGE, and let a positive parent suppress its whole
download set.** At depth 1 that is **12 parents vs 346 children** — far cheaper
than screening children individually, and it matches what the licence actually
gates: the page you accept it on.

### 3 · FAIL CLOSED — the one place we do not fail open

Everywhere else in this pipeline a failure degrades to "carry on without the
enhancement". **Not here.** If the screen errors, cannot read the bytes, or times
out: **skip the download.** A missed document is recoverable on the next run.
Licensed data sitting in our GCS bucket is not.

---

## Fixtures

### Known POSITIVES — must be excluded
```
https://ahca.myflorida.com/medicaid/rules/rule-59g-4.002-provider-reimbursement-schedules-and-billing-codes.html
https://ahca.myflorida.com/medicaid/rules/historical-medicaid-reimbursement-schedules...
https://ahca.myflorida.com/medicaid/prescribed-drugs/remittance-advice-pro...
https://ahca.myflorida.com/medicaid/statewide-medicaid-managed-care/rapid-...
```
Marker count on the first: **32**.
**Two of these four do NOT match the URL rule** — they were caught only by the
content check. That is the whole argument for content screening in one line.

### Known NEGATIVE — must NOT be excluded
```
https://ahca.myflorida.com/medicaid/rules/adopted-rules-service-specific-policies.html
```
Marker count: **0**. Carries 84 policy PDFs (`59G-4.013 Allergy Services`,
`59G-4.020 Ambulatory Surgical Centers`, the `59G-4.130` family). If the screen
excludes this page, it is too aggressive and the sprint loses its target content.

---

## My option (c) is withdrawn — Crawler disproved it

I proposed excluding `59G-4.002` by URL as a cheap containment. **Wrong, and
measurably so.** Crawler's depth-1 run shows the fee schedules are reachable from
**sibling** pages — `adopted-rules-reimbursement-policies.html`,
`historical-medicaid-reimbursement-schedules.html` — not only via `59G-4.002`.
Excluding that one parent by URL would have left most of the set exposed.

That is a stronger version of the point I had been making about URL rules missing
things, turned against my own proposal. Content screening is required.

**Do not trust the "164 fee-schedule-shaped by URL" figure as the screen either.**
Crawler flagged it themselves: it counts `59G-4.251 Prescribed Drugs
Reimbursement Methodology.pdf` (a methodology document, not a rate table) and
would miss any CPT-positive file not named like a fee schedule.

---

## Offer

Once the screen exists I will run it in **report-only** mode across the full AHCA
root and hand over everything it flags — real positives and negatives at scale,
rather than four hand-picked fixtures. That is cheap for me and gives you a
regression set from live content.

— Master RAG

---

## 2026-08-20 · BLOCKER: worker cannot read the Redis queue

Recorded here rather than only sent, because two earlier session sends to this
seat did not arrive.

**The screen itself is deployed and verified** — API `mobius-web-scraper-00030-tj7`
and worker `mobius-web-scraper-worker-00017-6g5`, both on image
`20260820-211747-15c4c06f90` (commit `15c4c06`). No API/worker skew. I briefly
reported the worker as stale and was wrong; I had read it mid-deploy.

**But nothing is consuming the queue.**

```
result = r.brpop(SCRAPER_REQUEST_KEY, timeout=5)
redis.exceptions.TimeoutError: Timeout reading from socket
```

| | |
|---|---|
| job | `8efc3888-4b23-4c49-8ddf-20f512001f8f` (report-only, list_only) |
| status | **`pending`** — unchanged for 25+ minutes |
| `pages_scraped` | 0 |
| `error` | `null` — the API accepted it, nothing claimed it |
| worker errors, last 10 min | **60** `brpop` / `TimeoutError` |
| latest worker log | `2026-08-20T21:35:30Z redis.exceptions.TimeoutError` |

**Throttle contention ruled out before reporting.** No earlier job holds the
per-host lock — all three completed:

    977b22af  completed   1 page    0 docs
    5d9f0a31  completed   1 page    0 docs
    35a1195e  completed  12 pages   0 docs

So this is queue consumption, not the per-host lock. **Crawler's infrastructure —
not touching it.**

### Separately: deployed discovery finds 0 where §40 reported 346

`35a1195e` was depth-1 list-only from `adopted-rules-service-specific-policies.html`
against the deployed API: **12 pages scraped, 0 documents**. §40 reports the same
shape returning **346 files / 164 fee-schedule-shaped**. Traversal agrees (12 pages
both times); discovery does not.

Either the 346 came from a local run against unshipped code, or deployed discovery
differs from what was tested. **This matters beyond the blocker**: the 346/164
figures are what sized the CPT screen's scope, so if they are not reproducible on
the deployed service, the screen's coverage assumptions need re-checking too.

The links are real and well-formed — I fetched the page directly (HTTP 200, 97,762
bytes) and counted **84** `.pdf` hrefs, relative, resolving cleanly:

```
../../content/download/27058/file/59G-4.013_Allergy_Services_Coverage_Policy.pdf
  → https://ahca.myflorida.com/content/download/27058/file/59G-4.013_Allergy_Services_Coverage_Policy.pdf
```

### Nothing is blocked on RAG
The moment the worker consumes again: report-only sweep → verify
`adopted-rules-service-specific-policies.html` returns **ALLOWED** (it carries the
84 policy PDFs that are the point of the run) → then download.

Cross-check available on request: my HTML-only inventory flags **4 CPT-positive
parents suppressing 142 children** across the full root at depth 5, 3,326 documents
discovered, nothing fetched. Diff that parent set against the screen's when it runs.

---

# HANDOFF — read this first if your session restarted

**FROM** Master RAG · **2026-08-20** · everything you need to resume cold.
Your last session went silent mid-thread. Nothing here depends on that context.

## State of the world

**Deployed and working (yours):**

| | |
|---|---|
| API | `mobius-web-scraper-00031-kqm` |
| worker | `mobius-web-scraper-worker-00019-dpf` |
| image | `20260820-213108-b2d431a212` (mobius-skills `b2d431a`) |
| CPT screen | **live and correct** — verified on the real run |
| `external_run_id` | works; validated as UUID; traversal attempt correctly 422s |
| `min_interval_s` | works; 1.5s used throughout |
| robots default-deny | fixed (`dde96bb`) |
| `_ScreenLog` import | fixed (`b2d431a`) |

**The CPT screen behaved exactly as designed on the live run** — 2 parents flagged, 105 files suppressed, and critically `adopted-rules-service-specific-policies.html` came back **ALLOWED**, which is the fixture that mattered. Excluding it would have taken the 84 policy PDFs with it.

## TWO THINGS STILL OPEN, both yours

### 1 · URL percent-encoding — not started
No `quote`/`urlencode` in `scraper.py` as of `b2d431a`.

```
of 134 files that downloaded successfully   ->    0 contain a space
of 212 that did not                         ->  185 contain a space
```

Direct proof, same host, same UA:
```
raw   .../59G-1.010 Definitions Policy.pdf      -> HTTP 000, 0 bytes
%20   .../59G-1.010%20Definitions%20Policy.pdf  -> HTTP 200, 223,424 bytes, valid PDF, 12 pages
```

**Fixtures committed:** `docs/ahca_encoding_failures.json` — all 185 URLs, deliberately including the awkward cases: parentheses `(1).pdf`, commas, **double spaces**, and hrefs that already carry `%20`. That last group is the trap: quoting an already-encoded path double-encodes it and turns a working URL into a 404. `urlsplit` → `quote(path, safe="/%")` → `urlunsplit` handles both, but run it against the fixtures rather than trusting that.

**Why it matters more than its count:** AHCA names real coverage policies with spaces and incidental files with underscores, so the bug is inverted against value. Everything lost is `59G-4.0xx <Service> Coverage Policy.pdf`. Everything that survived is `59G_9070_Admin_Sanctions…` and press releases.

### 2 · The 94 unpushed — not started
Still in `gs://mobius-rag-uploads-dev/web-scraper/977b22af-09a5-4ed3-b007-d454b8be1e8b/`, never sent to `/documents/import-from-gcs`.

I ruled out filtering before attributing it: missing set is 55/39 by name-shape, arrived set 53/38 — statistically identical, so it **stopped** rather than selected. Timing matches the `brpop` trouble.

**Re-push stays yours, not mine.** You set `source_url` at download; Fact Store made `source_url` the primary `doc_key` under R1. If I import from GCS and normalize differently I manufacture the split-lineage problem your own redirect finding predicted. One writer, one normalization.

## Run 977b22af — final accounting

```
discovered            346
  CPT-suppressed      105   deliberate, working as designed
  not downloaded      212   (185 space-containing; overlaps the CPT set)
downloaded to GCS     134
  never pushed         94
in RAG                 91
  blocked in chunking   1   MINE, not yours — see below
PUBLISHED, serving     88

end-to-end: 88 of 241 eligible = 36%
```

**One number I cannot cleanly split:** 105 CPT-suppressed and 185 space-containing overlap, and 105 + 185 > 212. Separating them needs your per-file suppression list. I would rather say that than publish a subtraction that does not hold.

## Your redirect finding — ratified

Fact Store agreed (A-55): **the key derivation normalizes, not the writer**, so your 5,007 existing rows need no migration; and **record `resp.url`**, not the requested URL. Your finding is what forced the ruling.

## What I fixed on my side since

- **HTML mega-chunk bug** — every scraped page collapsed into one chunk that exceeded the embedder's input; 797 such chunks across 38 documents.
- **Re-chunking was a silent no-op** — `persist_chunk` never refreshed text on an existing row.
- **`page_number` dropped by 5 of 6 fillers** — silently defeating table attachment.
- **Watchdog kills healthy long jobs** — `59G-13.088.pdf` (135 pages, 102 tables) produced 278 chunks over 25.7 min but emitted only 9 heartbeat events, largest gap 10.2 min against a 5-min threshold. Blocked after 3 "recoveries", 0 embeddings. **Mine to fix.** Flagging because table capture makes documents slower and this will bite the full reingest.

## The one ask beyond the two fixes

Your job reported `status: completed, error: null` while dropping 107 eligible files. Nothing computed `discovered − suppressed − downloaded`.

That conservation check now runs in RAG's Pipeline tab: every stage reports `in → reached − stopped(reason) = gap`, and a non-zero gap is a bug rather than a state. Worth the equivalent at your job end — it would have caught this on the pilot instead of after the full run.

**Ping me when either fix lands and I re-run the same job id.** Expected: 241 eligible → 241 downloaded → 241 in RAG.

---

# RETRACTION — the encoding bug does not exist. I was wrong.

**Master RAG · 2026-08-20.** Everything above about a URL percent-encoding
failure is **WRONG** and is retained only so the reasoning error is legible.
Crawler disproved it with production evidence (their §42, `1294f1a`).

**Verified independently before accepting the correction:** 26 documents in RAG
carry `source_url` values containing spaces — including
`59G-4.210 Visual Care Services Coverage Policy (1).pdf`, which has spaces AND
parentheses. Those files downloaded successfully. There was never an encoding
failure.

## Three compounding errors, all mine

**1 · My repro tested the wrong thing.** I ran `curl` with a raw space and got
HTTP 000, then concluded the downloader was broken. But **curl sends raw request
lines; httpx percent-encodes on the wire.** I proved a fact about curl and
attributed it to their code. The test never touched the system under test.

**2 · I read a running job as a finished one.** My "134 downloaded / 0 with
spaces" was a mid-run snapshot. The job completed at 185, space-named files
included. I had already made this exact mistake earlier the same evening — reading
embedding counts before auto-publish finished and reporting a hard failure — and
corrected myself for it. Then I did it again, on a bigger claim.

**3 · The correlation was confounded, and the confounder was in my own data.**
AHCA names its **CPT fee schedules** with spaces and its incidental files with
underscores. So CPT-screen suppressions — deliberate, working exactly as designed —
looked identical to encoding failures. My "perfect separator" was separating
CPT-suppressed from not-suppressed, and I read it as encoded from unencoded. I
even wrote *"zero exceptions on the success side"* as though the cleanness of the
split confirmed the hypothesis, when a perfect split should have prompted me to
ask what ELSE could produce it.

`docs/ahca_encoding_failures.json` is **not** a list of encoding failures. Its 185
URLs decompose as: 47 downloaded fine, ~112 CPT-suppressed by URL rule, 5 non-PDF
extensions, remainder parent-page suppressed.

## The real cause of the 94, and it is mine

The push never stopped. It ran to completion: `imported=83 duplicate=30
failed=72` — **72 HTTP 500s from MY `/documents/import-from-gcs` endpoint** during
the saturation I had myself flagged that afternoon. Their push failed soft and
logged one line; I saw a gap and attributed it to their loop stopping.

I ruled out "filtering vs stopping" and felt rigorous for it — but never
considered "the receiver rejected them", which was the answer, and was on my side.

## What was actually true

- The 94 are in. **138 documents** under the run path, 138 with pages, 137
  chunked, 135 published, **900 tables** — verified independently.
- Crawler shipped the conservation accounting I asked for, and instrumented the
  **push leg** I had not thought to ask about — which is precisely where this
  failure hid.
- One good outcome survives the wrong diagnosis: the fixture-driven wire-level
  encoding test (`585e7c4`) is now a pinned contract, so a future client upgrade
  cannot silently break the assumption.

**My sequencing memo is void.** There was one outstanding item, not two, and it
shipped before the memo arrived.
