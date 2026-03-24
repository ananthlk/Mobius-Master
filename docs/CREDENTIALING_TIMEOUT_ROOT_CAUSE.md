# Credentialing “Step 1 timed out” — root cause

## What broke

From chat, the credentialing flow often shows **“✓ Step 1 done. (timed out)”** then **“✓ Step 2 done. Failed. Stopping.”** and all later steps skipped.

## Cause (traced in git)

1. **1bfb676** (Mar 12, 2026) — *Report: retry draft on validation BLOCK*
   - Introduced `roster_credentialing_orchestrator.py` with:
     - `_run_step_0_ensure_benchmarks()` calling `POST /ensure-benchmarks` with **timeout=120**.
     - The orchestrator was **not** invoked from the chat UI in this commit.

2. **acce0e1** (Mar 14, 2026) — *Planner routing, emit ordering, and Layer 4 safety fixes*
   - **This is the change that caused timeouts to appear.**
   - Wired `tool_agent.py` to the orchestrator: added `run_orchestrator`, roster triggers, and credentialing report flow from chat.
   - From this commit on, any “credentialing report for X” from chat runs the full plan, including ensure_benchmarks, with the **same 120s** HTTP timeout.

So the 120s timeout existed from day one in the orchestrator; it only started affecting users when the chat path began calling it in **acce0e1**. Before that, “so many reports” were likely produced via:

- Direct runs of `run_roster_api_flow.py` (no chat worker timeout), or
- A different integration that did not go through this orchestrator.

No change was made to the BigQuery query or the skill’s `/ensure-benchmarks` handler in that window; the query (DOGE + NPPES join) often takes **2–5 minutes**. So once the chat path ran it, 120s was too short.

## Fix (on our end)

- **mobius-chat** (uncommitted): increase ensure_benchmarks HTTP timeout from **120 → 300** seconds in `roster_credentialing_orchestrator.py`.
- Add a single **retry** for the next step (identify_org) when the previous step times out or has connection errors, so a busy skill can recover.
- Commit these changes so deployed chat uses the longer timeout and retry.

## Google / environment

- BigQuery job duration can vary (cache, slots, NPPES table size). No code change on our side made the query heavier; the skill’s `utilization_benchmarks.py` even added `entity_type_code = '1'` (individuals only), which reduces work.
- If 300s is still insufficient in some runs, consider skipping repopulation when the benchmarks table was written in the last N minutes (cache) or making ensure_benchmarks asynchronous (return 202 + poll).
