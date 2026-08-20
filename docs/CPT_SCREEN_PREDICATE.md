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
