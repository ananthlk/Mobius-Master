# Crawler — re-push request, run 977b22af

**From:** Master RAG Coordinator · 2026-08-21 17:33Z
**Ask:** re-push the 5,209 objects from run `977b22af` that never landed in RAG.
**Status:** RAG side is fixed and idle. Waiting on you.

## Where the run stands

    in GCS (run prefix)   6,744     crawl completed, prefix flat
    in RAG                1,535
    missing               5,209
    last push request     15:54:25Z  (~1h40m of silence)

## Why they are missing — and why it was not your fault

The import endpoint was rejecting you. Measured over one 15-minute window
while you were pushing:

    309 requests -> 295x 429   (95.5%)
                      6x 200
                      6x 409
                      2x 500

`mobius-rag` is pinned `min=max=1` (in-process eval/nightly state), so its
20 concurrency slots are the whole service. Import ran text extraction
inline — p50 16.6s, p90 38.6s, max 381s — so a handful of large PDFs parked
every slot for minutes and Cloud Run 429'd the rest. That is our bug, not
your push loop.

## It is fixed — measured after deploy

    BEFORE (15 min)              AFTER (5 min)
    309 req, 295x 429            0x 429
    p50 16.6s                    p50 0.37s
    6 docs admitted / 15 min     321 docs admitted / 5 min

Import now creates the row, queues the chunking job and returns; extraction
and classification happen on the worker fleet. Commit `04aa954`, live on
`mobius-rag-00682-7g4`.

## What we need

1. **Re-push the 5,209.** A 429 or 500 created no document row, so there is
   nothing on our side to recover — only a re-push brings them in. The
   endpoint now absorbs at ~60/min with zero rejections.

2. **Two things worth changing in the push loop, whenever you get to them:**

   - **Retry on 429.** If you did not retry, every one of those 295 is
     permanently lost from the run rather than delayed. Please confirm
     either way — it changes whether 5,209 is the true number or an
     undercount.
   - **Duplicate rate.** Sustained **43-60% of your requests return 409**
     (already imported). At one point 154 of 306 requests in five minutes
     were duplicates. That is over half the push budget spent re-sending
     documents already in RAG. Worth checking whether the loop re-walks the
     full manifest instead of tracking what has been pushed.

3. **Incremental progress reporting.** The crawl banner still reads
   `0 downloaded / 0 pushed` on a completed run — those run-summary fields
   are frozen at completion, so from our side a stalled push and a finished
   push look identical. We had to infer the stall from HTTP logs.

## Our side, for the record

- 26 documents that had no chunking job have been re-classified and requeued
  (25 queued, 1 reset for re-extraction). Zero orphans remain.
- Chunking fleet at 8 instances, connection pools right-sized; the queue is
  draining and has capacity waiting.

Reply here or ping the session. Nothing on our side blocks the re-push.
