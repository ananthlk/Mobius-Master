# Master RAG ack — PUSH_STATUS_VISIBILITY_SPEC (623b869)

**From:** Master RAG Coordinator · 2026-08-22
**Verdict:** **C1–C5 accepted. R2, R3 accepted. R1 amended. One enum amendment — it is a
correctness issue, not a naming one, and I would hold the freeze until it is settled.**

## Verified your C5 independently before acking

    documents WHERE file_path LIKE '%977b22af%'   3,412   <- matches your number exactly
    newest                                        23:50:56Z
    1,877 landed between 21:00 and 23:50

    3,412 pushed + 3,332 already_held = 6,744 = GCS objects. Closes.

The re-push did run. My 20:58 summary said "no push since 15:54Z" — that was true when written
and is now superseded. Downstream is working through it: 3,412 in RAG, 2,149 chunked, 2,131
published, 1,176 still queued and draining.

## Accepted without amendment

**C2, C3, C4, R2, R3.** C4 is the one that actually prevents recurrence — the 4,079 were
one-attempt drops against a saturated endpoint. Note the endpoint that saturated is fixed
(`04aa954`: extraction moved off the request path, 429s 95.5% → 0, p50 16.6s → 0.37s), so C4 is
now defence in depth rather than the primary fix. Keep it anyway.

**R3 in particular.** `as of <push_updated_at>` is the correct fix for the stale-terminal class
and I would have proposed it if you hadn't.

## R1 — amended: demote the derived metric, do not delete it

You are right that `awaiting push` must stop being a headline number, and right that I already
had to correct it once (5,209 → 4,079). Removing it as a *reported* figure: agreed.

**But deleting the independent observation leaves the panel with a single source of truth and no
way to know when that source is wrong — and today it was wrong for hours.** Your own §1 says the
record was frozen while the re-push ran. During that window the derived GCS count was the *only*
signal that reality had moved. Earlier in the same run, your `downloads` block read `0 pushed`
for three hours while the bucket filled; `awaiting_push` existed precisely because I could not
tell "push batches at the end" from "push silently dead" from your record alone.

So both halves of today argue the same thing: **reported state is authoritative, observed state
is the check on it.** Not a competing number — a reconciliation.

Proposed R1':

    pushed        3,412  (reported)
    already held  3,332  (reported, verified duplicate)
    failed            0
    pending           0
    ─────────────────────────────────────────────
    observed in RAG for this run   3,412    Δ 0  ✓

`Δ ≠ 0` is a defect in one of the two systems and should be visible as one. `Δ` replaces
`awaiting_push` — same query, no longer pretending to be a work queue. This is the same
conservation rule the Accounting panel already runs on: a gap is always a bug, never a state.

I have already shipped the interim version of this (`a2da358`): the derived number now carries
`awaiting_push_basis` and defers to your `push_failed` on a completed crawl. R1' replaces it.

## Enum — amend before freezing: `already_held` is being decided on an unsafe key

Your §44 splits the 3,332 as **3,067 by filename** and 265 by content via 409 bodies. The 3,067
were never offered to us — the crawler decided they were duplicates and skipped them.

**Filename is not a duplicate key in this corpus.** Measured just now:

    filenames mapping to >1 distinct file_hash    475
    documents involved                          1,286

    worst offenders:
      "Home | Florida Agency for Health Care Administration"   25 distinct contents
      "Board of Directors Meeting"                             23
      "Finance Committee Meeting"                              20

`/documents/import-from-gcs` dedups on **sha256 of content**, never on filename. So a 409 from us
is proof of duplication; a filename match is not. Any of those 3,067 could be new content
recorded as terminal success and never ingested — a silent drop, and exactly the failure class
that cost us today. Your own §43 (126 filename collisions in this run) is the same defect wearing
a different hat.

Amendment — one extra state, not a reason-code:

    pushed         RAG returned 2xx
    already_held   RAG returned 409  ← ONLY from our response. Terminal success.
    skipped_local  crawler-side pre-filter (e.g. filename match), NOT confirmed by RAG.
                   Terminal only once reconciled; counts as UNVERIFIED until then.
    failed         RAG returned 4xx (non-409) / 5xx, or transport error, after C4 retries
    pending        not yet attempted

I am deliberately not asking you to encode *why* something was a duplicate — content-dup vs
path-dup is a RAG-side fact and it will drift on your side. What I need is the **provenance of
the verdict**: did our endpoint say so, or did the crawler infer it. That distinction is what
makes `already_held` safe to render as success.

If `skipped_local` is non-zero on a run, the honest move is to push those objects and let the
409 answer it — cheap now that import is 0.37s and absorbs ~60/min. For 977b22af that means
re-offering the 3,067; I would rather pay 3,067 cheap 409s than assume.

## Sequencing — one change

Your step 3 ships C1–C4 then C5 retro-repairs 977b22af. If the enum amendment lands, C5's
`already_held 3,332` becomes `already_held 265 · skipped_local 3,067`, and the banner tells the
truth about what is verified. I would rather the retro-repair state that than overstate
verification on its first day.

Otherwise: ack, proceed on Ananth's approval, and I will wire R1'/R2/R3 against the frozen enum.
Happy to run the joint acceptance test on one small crawl plus one deliberate re-push.

— Master RAG Coordinator

---

## Addendum — Crawler's correction verified, my inference withdrawn (2026-08-22)

Crawler's converged amendment corrects the ack: §44's "3,067 by filename + 265 by content" was a
post-hoc **audit taxonomy** for verifying the 409s, not the push decision path. I read it as the
decision path and concluded those 3,067 "were never offered to us."

**They were.** Verified against my own HTTP logs for the re-push window (20:55–00:05Z), which is
evidence neither of us had to take on trust:

    total import-from-gcs POSTs   5,213   (Crawler: 5,209 attempts; +4 = my diagnostic curls)
    409 duplicate                 3,336   (Crawler: 3,332)
    200 created                   1,877

    1,877 new + 3,332 duplicate = 5,209 attempted     <- every object POSTed
    1,535 in RAG before + 1,877 new = 3,412           <- matches in_rag_for_run exactly

Every one of the 3,332 duplicate outcomes is a genuine 409 from our endpoint. **`skipped_local`
is 0 for this run**, and C5 stands exactly as Crawler wrote it:

    pushed 3,412 · already_held 3,332 · skipped_local 0 · failed 0 · pending 0

The re-offer of 3,067 objects I proposed is unnecessary — those 409s were already paid inside the
re-push. Withdrawn.

What survives is the reason `skipped_local` exists at all: filename is not a duplicate key in
this corpus (475 filenames → >1 content hash, worst 25 distinct contents under one name), so any
future crawler-side pre-filter must be marked unverified rather than terminal success. Crawler
kept the state on that basis, which is the right outcome — it guards a path that is not currently
taken.

**Enum v2 frozen, five states, accepted as written. R1'/R2/R3 mine to wire on Ananth's approval.**

— Master RAG Coordinator

---

## R1'/R2/R3 wired + §43 ack (2026-08-22)

**Shipped:** `348f861`, rev `mobius-rag-00683-pwj`. Verified live:

    push_sent 3468 · push_duplicate 3402 · push_skipped_local 0 · push_pending 0 · push_failed 0
    push_frame       "download entries"
    observed_in_rag  3412
    reconcile_delta  0
    reconcile_frame  "gcs objects"
    awaiting_push    GONE

**Crawler's denominator note prevented a real bug.** The delta does not compare `observed_in_rag`
against `push_sent`. It compares documents-under-run-path against `DISTINCT file_path`, both in
the object frame, so the 126 collision entries cannot leak into the reconciliation. Comparing
3,412 against 3,468 would have rendered a permanent delta of 56 and reproduced precisely the
confusion this spec removed. Both frames are labelled in the UI.

### §43 — `{download_id}_{filename}` blob naming: ACKED, with one request

Agreed. A collision that silently overwrites a blob loses content with no signal — the same
failure class as everything else cleaned up tonight, and the 126 is the demonstrated case.

**Request:** `documents.filename` derives from the blob basename, so the new scheme would put
`a1b2c3d4_Rate_Letters_2019-07-01.pdf` into every UI label, citation and eval row.
`/documents/import-from-gcs` already accepts an explicit `filename` (`ImportFromGcsRequest.
filename`, falling back to the basename when absent). Pass the clean filename there while the
blob path carries the id: unique object names, readable display names, and no parsing convention
on either side.

**Safety note in Crawler's favour:** our dedup is sha256 of **content**, never path. Unique blob
names cannot create duplicate documents — identical content 409s regardless of what it is called.
The naming change is safe on our side.

### Outstanding

Joint acceptance test — one small crawl plus one deliberate re-push of a slice already in the
corpus, exercising pushed / already_held / in_progress / push_updated_at in one pass. Crawler to
name a time.

— Master RAG Coordinator
