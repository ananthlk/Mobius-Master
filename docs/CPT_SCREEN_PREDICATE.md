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
