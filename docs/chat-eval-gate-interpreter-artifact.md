# The gate's "12 baseline failures now PASS" is an interpreter artifact

**Author:** Payor Policy Agent · **Date:** 2026-09-10
**Status:** 🔴 Do not shrink the baseline. Nothing was fixed.

## What the gate reported

Running `scripts/platform/gen_eval_report.py` at `70082ce`:

```
tests 2637/2644 passed, 2 failed, 0 errors, 5 skipped (1169.4s)
regressions 0 · newly passing 12 · known-failing baseline 14
```

and in `docs/chat-eval-report.md`:

> **12 baseline failure(s) now PASS** — shrink the baseline:

All 12 are in two files: `test_logging_config.py` and `test_tracing_config.py`.

## What actually happened

**I invoked the gate with `mobius-chat/.venv/bin/python`. The baseline of 14 was
frozen 2026-09-08 under system `python3`.** Twelve of those fourteen were
`ModuleNotFoundError`, not assertion failures:

| Interpreter | `pythonjsonlogger` | `opentelemetry` | Those two files |
|---|---|---|---|
| system `python3` | absent | absent | **12 failed**, 26 passed |
| `.venv/bin/python` | present | present | **38 passed** |

Twelve failures, twelve "newly passing", same twelve tests. Demonstrated directly
rather than inferred — both runs are reproducible in one command each:

```bash
cd mobius-chat && python3 -m pytest tests/test_logging_config.py tests/test_tracing_config.py -q
cd mobius-chat && .venv/bin/python -m pytest tests/test_logging_config.py tests/test_tracing_config.py -q
```

**No code changed. No one fixed these.** The interpreter changed.

## Why this matters more than it looks

1. **Shrinking the baseline would manufacture 12 phantom regressions.** The list
   "may shrink, never grow." Shrink it to 2 on this evidence and the next person
   who runs the gate the documented way — `python3 scripts/platform/gen_eval_report.py`
   — gets 12 regressions and goes looking for a bug that was never introduced.
2. **`regressions 0` was measured against a baseline frozen on a different
   interpreter.** For a docs-and-tests change like mine that is harmless. It is not
   generally safe: a real regression in a module that only imports under the venv
   is invisible to a `python3` baseline, and vice versa.
3. **This is the same defect class the program has been cataloguing all week** — a
   measurement that reports a property of the harness as a property of the system.
   Same shape as the "29 MCP tools emitted zero times" premise: both are true
   readings that answer a different question than the one being asked of them.
4. It lands during a push for green nodes. A gate that appears to have improved by
   12 tests overnight, with no commit claiming the fix, is the most tempting
   possible moment to bank the win.

## What should happen

**Not a unilateral edit to the shared gate — it is what everyone is scored on, and
chat changes are on hold.** Proposal, for whoever owns the eval seat:

- `gen_eval_report.py` should **refuse to run**, rather than report, when the
  interpreter is missing test dependencies — an ImportError-only failure is not a
  test result and should not be scored as one.
- Or the frozen baseline should record the interpreter it was frozen under and
  refuse comparison across a mismatch.
- Either way the baseline stays at **14** until it is re-frozen deliberately.

The other 2 failures are real and interpreter-independent — both LOC ratchets:
`main.py` 3279 vs a 2200 ceiling, `react_loop.py` 6451 vs a 2560 ceiling. Those
are the honest content of the known-failing set. Note that this program's own work
has been adding to `react_loop.py`, so that ratchet is drifting further from its
ceiling, not closer.
