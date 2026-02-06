# Mobius Chat QA

Automated test bot that sends curated questions to the mobius-chat API, adjudicates responses with an LLM (match/mismatch), submits thumbs up/down from adjudication, validates feedback persistence, and produces a report (accuracy + latency).

## Prerequisites

- Python 3.10+ with mobius-chat dependencies installed: `pip install -r requirements.txt` (from mobius-chat root).
- Mobius-chat API running (e.g. `uvicorn app.main:app --reload`) and worker running if using a queue.
- For adjudication: same LLM env as chat (Vertex/Ollama) so the adjudicator can call `app.services.llm_provider.get_llm_provider()`.

**Using Redis queue:** The bot talks to the API over HTTP only; it does not choose the queue. To use Redis:
- On the **mobius-chat server**: set `QUEUE_TYPE=redis` and `REDIS_URL=redis://localhost:6379/0` (or your Redis URL). Run the worker in a separate process: `python -m app.worker`.
- For SSE streaming with Redis, set `CHAT_LIVE_STREAM=1` on the API process so it subscribes to Redis for progress. The bot's `use_sse: true` (default) will then receive live events.

## Config

- **`chat_bot_config.yaml`** – API base URL, optional auth token, typing delay, SSE vs poll, adjudicator (use_chat_llm), report path.
- **`chat_bot_questions.yaml`** – Curated 50–60 questions: `in_manual` (expected answer), `out_of_manual` / `off_topic` (should_refrain). Each entry has `question`, `category`, `expected_answer` or `should_refrain`, optional `expected_refrain_phrases`.

## Run

From **mobius-qa/mobius-chat-qa** (script adds mobius-chat to path so no PYTHONPATH needed when run from here):

```bash
python chat_bot.py
```

From **Mobius repo root**:

```bash
PYTHONPATH=mobius-chat python mobius-qa/mobius-chat-qa/chat_bot.py
```

Or from **mobius-chat** (if launcher is present):

```bash
python scripts/chat_bot.py
```

With explicit paths:

```bash
python chat_bot.py --config chat_bot_config.yaml --questions chat_bot_questions.yaml --report reports/chat-bot-report.md
```

- **`--limit N`** – Run only the first N questions (e.g. `--limit 3` for a quick smoke test).

## Report

Report is written to `reports/chat-bot-report-<timestamp>.md` (or `--report` path). It includes:

- Summary (total runs, completed, match rate).
- Content accuracy: match rate overall, in-manual accuracy, refrain accuracy (out_of_manual + off_topic).
- Latency: min/max/avg/P95 time to completion.
- Per-run table: question snippet, category, correlation_id, match, reason, rating submitted, feedback validated, time (s).
- Failures and mismatches: status, error, adjudication reason.

## Flow

1. Load config and question set.
2. For each question: optional typing delay → POST /chat → wait (SSE or poll) until status completed → LLM adjudicate (expected vs actual) → POST /chat/feedback (thumbs up if match, thumbs down if mismatch) → GET /chat/feedback to validate.
3. Write report.

Thumbs up/down are driven by content accuracy (adjudication), not at random.
