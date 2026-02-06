#!/usr/bin/env python3
"""
Mobius Chat Test Bot: sends curated questions to mobius-chat API, adjudicates responses with an LLM,
submits thumbs up/down from adjudication, validates feedback persistence, and produces a report.
Run from mobius-qa/mobius-chat-qa: python chat_bot.py [--config chat_bot_config.yaml] [--questions chat_bot_questions.yaml] [--report reports/chat-bot-report.md]
Or from Mobius root: PYTHONPATH=mobius-chat python mobius-qa/mobius-chat-qa/chat_bot.py
"""
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# _root = this directory (mobius-chat-qa). Add mobius-chat to path so app and adjudicator's get_llm_provider work.
_root = Path(__file__).resolve().parent
_mobius_chat = _root.parent.parent / "mobius-chat"
if _mobius_chat.exists() and str(_mobius_chat) not in sys.path:
    sys.path.insert(0, str(_mobius_chat))

import httpx
import yaml

from adjudicator import adjudicate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = _root / "chat_bot_config.yaml"
DEFAULT_QUESTIONS_PATH = _root / "chat_bot_questions.yaml"
FEEDBACK_COMMENT_MAX_LENGTH = 500


def load_config(path: Path) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def load_questions(path: Path) -> list[dict]:
    data = load_config(path)
    return data.get("questions") or []


def typing_sleep(message: str, delay_ms: int) -> None:
    if delay_ms <= 0:
        return
    # Simple: fixed delay per question (e.g. 50ms * len(message) or cap)
    duration_sec = min(delay_ms * len(message) / 1000.0, 30.0)
    time.sleep(duration_sec)


def post_chat(api_base: str, message: str, auth_token: str | None, client: httpx.Client) -> tuple[str, str | None]:
    """POST /chat; returns (correlation_id, thread_id)."""
    url = f"{api_base.rstrip('/')}/chat"
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    body = {"message": message}
    resp = client.post(url, json=body, headers=headers, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    return (data.get("correlation_id", ""), data.get("thread_id"))


def wait_poll(
    api_base: str,
    correlation_id: str,
    auth_token: str | None,
    client: httpx.Client,
    poll_interval_sec: float,
    max_wait_sec: float,
) -> tuple[dict | None, float, float]:
    """Poll GET /chat/response/{id} until status completed. Returns (response, time_to_first_progress, time_to_completion)."""
    url = f"{api_base.rstrip('/')}/chat/response/{correlation_id}"
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    start = time.monotonic()
    first_progress_at: float | None = None
    while (time.monotonic() - start) < max_wait_sec:
        resp = client.get(url, headers=headers, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        if first_progress_at is None and (data.get("thinking_log") or data.get("message")):
            first_progress_at = time.monotonic() - start
        if data.get("status") == "completed":
            t_first = first_progress_at if first_progress_at is not None else (time.monotonic() - start)
            return (data, t_first, time.monotonic() - start)
        time.sleep(poll_interval_sec)
    return (None, 0.0, time.monotonic() - start)


def wait_sse(
    api_base: str,
    correlation_id: str,
    auth_token: str | None,
    client: httpx.Client,
    max_wait_sec: float,
) -> tuple[dict | None, float, float]:
    """GET /chat/stream/{id}, read SSE until 'completed'. Returns (response, time_to_first_progress, time_to_completion)."""
    url = f"{api_base.rstrip('/')}/chat/stream/{correlation_id}"
    headers = {"Accept": "text/event-stream"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    start = time.monotonic()
    first_progress_at: float | None = None
    completed_data: dict | None = None
    with client.stream("GET", url, headers=headers, timeout=max_wait_sec) as resp:
        resp.raise_for_status()
        buffer = ""
        for chunk in resp.iter_bytes():
            if (time.monotonic() - start) > max_wait_sec:
                break
            buffer += chunk.decode("utf-8", errors="replace")
            while "\n\n" in buffer:
                event_block, _, buffer = buffer.partition("\n\n")
                for line in event_block.split("\n"):
                    line = line.strip()
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:].strip())
                            event = ev.get("event")
                            if event == "thinking" and first_progress_at is None:
                                first_progress_at = time.monotonic() - start
                            if event == "completed":
                                completed_data = ev.get("data") or {}
                                t_first = first_progress_at if first_progress_at is not None else (time.monotonic() - start)
                                return (completed_data, t_first, time.monotonic() - start)
                        except json.JSONDecodeError:
                            pass
    t_total = time.monotonic() - start
    t_first = first_progress_at if first_progress_at is not None else 0.0
    return (completed_data, t_first, t_total)


def post_feedback(
    api_base: str,
    correlation_id: str,
    rating: str,
    comment: str | None,
    auth_token: str | None,
    client: httpx.Client,
) -> None:
    """POST /chat/feedback."""
    if comment and len(comment) > FEEDBACK_COMMENT_MAX_LENGTH:
        comment = comment[:FEEDBACK_COMMENT_MAX_LENGTH]
    url = f"{api_base.rstrip('/')}/chat/feedback"
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    body = {"correlation_id": correlation_id, "rating": rating, "comment": comment}
    resp = client.post(url, json=body, headers=headers, timeout=10.0)
    resp.raise_for_status()


def get_feedback(api_base: str, correlation_id: str, auth_token: str | None, client: httpx.Client) -> dict | None:
    """GET /chat/feedback/{correlation_id}. Returns { rating, comment } or None if 404."""
    url = f"{api_base.rstrip('/')}/chat/feedback/{correlation_id}"
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    resp = client.get(url, headers=headers, timeout=10.0)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def run_one(
    q: dict,
    config: dict,
    client: httpx.Client,
) -> dict:
    """Run one question: send, wait, adjudicate, feedback, validate. Returns result row for report."""
    api_base = (config.get("api_base") or "http://localhost:8000").rstrip("/")
    auth_token = config.get("auth_token") or os.environ.get("CHAT_BOT_AUTH_TOKEN")
    typing_delay_ms = config.get("typing_delay_ms") or 0
    use_sse = config.get("use_sse", True)
    poll_interval_sec = config.get("poll_interval_sec") or 0.4
    max_wait_sec = config.get("max_wait_sec") or 300
    use_chat_llm = config.get("use_chat_llm", True)

    question = (q.get("question") or "").strip()
    category = (q.get("category") or "in_manual").strip()
    expected_answer = (q.get("expected_answer") or "").strip() or None
    should_refrain = bool(q.get("should_refrain", False))
    expected_refrain_phrases = q.get("expected_refrain_phrases")
    if expected_refrain_phrases is None and should_refrain:
        expected_refrain_phrases = []

    result = {
        "question": question,
        "category": category,
        "correlation_id": "",
        "expected_answer": expected_answer,
        "should_refrain": should_refrain,
        "actual_message_snippet": "",
        "adjudication_match": False,
        "adjudication_reason": "",
        "rating_submitted": "",
        "feedback_validated": False,
        "time_to_first_progress_sec": 0.0,
        "time_to_completion_sec": 0.0,
        "error": "",
        "status": "pending",
    }

    # Typing simulation
    typing_sleep(question, typing_delay_ms)

    # POST /chat
    try:
        correlation_id, _ = post_chat(api_base, question, auth_token, client)
        result["correlation_id"] = correlation_id
    except Exception as e:
        result["error"] = str(e)
        result["status"] = "error"
        return result

    # Wait for completion
    if use_sse:
        response_data, t_first, t_total = wait_sse(api_base, correlation_id, auth_token, client, max_wait_sec)
    else:
        response_data, t_first, t_total = wait_poll(
            api_base, correlation_id, auth_token, client, poll_interval_sec, max_wait_sec
        )
    result["time_to_first_progress_sec"] = round(t_first, 2)
    result["time_to_completion_sec"] = round(t_total, 2)

    if response_data is None:
        result["error"] = "Timeout or no completed response"
        result["status"] = "timeout"
        return result

    actual_message = (response_data.get("message") or "").strip()
    result["actual_message_snippet"] = (actual_message[:500] + "…") if len(actual_message) > 500 else actual_message

    # Adjudicate
    try:
        match, reason = adjudicate(
            question=question,
            category=category,
            expected_answer=expected_answer,
            should_refrain=should_refrain,
            expected_refrain_phrases=expected_refrain_phrases,
            actual_message=actual_message,
            use_chat_llm=use_chat_llm,
        )
        result["adjudication_match"] = match
        result["adjudication_reason"] = (reason or "")[:500]
    except Exception as e:
        result["adjudication_match"] = False
        result["adjudication_reason"] = f"Adjudicator error: {e}"
        logger.exception("Adjudicator failed for %s", correlation_id[:8])

    # Submit feedback
    rating = "up" if result["adjudication_match"] else "down"
    result["rating_submitted"] = rating
    comment = result["adjudication_reason"] if not result["adjudication_match"] else None
    try:
        post_feedback(api_base, correlation_id, rating, comment, auth_token, client)
    except Exception as e:
        result["error"] = (result.get("error") or "") + f"; post_feedback: {e}"
        result["status"] = "feedback_error"
        return result

    # Validate feedback persisted
    try:
        stored = get_feedback(api_base, correlation_id, auth_token, client)
        result["feedback_validated"] = stored is not None and stored.get("rating") == rating
    except Exception as e:
        result["error"] = (result.get("error") or "") + f"; get_feedback: {e}"
    result["status"] = "completed"
    return result


def write_report(results: list[dict], report_path: Path, config: dict) -> None:
    """Write Markdown report: summary, accuracy by category, per-run table, latency stats, failures."""
    total = len(results)
    completed = sum(1 for r in results if r.get("status") == "completed")
    matches = sum(1 for r in results if r.get("adjudication_match"))
    by_cat: dict[str, list[dict]] = {}
    for r in results:
        c = r.get("category") or "unknown"
        by_cat.setdefault(c, []).append(r)
    in_manual = by_cat.get("in_manual", [])
    out_manual = by_cat.get("out_of_manual", [])
    off_topic = by_cat.get("off_topic", [])
    in_manual_match = sum(1 for r in in_manual if r.get("adjudication_match"))
    refrain_match = sum(1 for r in out_manual + off_topic if r.get("adjudication_match"))
    refrain_total = len(out_manual) + len(off_topic)

    latencies = [r["time_to_completion_sec"] for r in results if r.get("status") == "completed" and r.get("time_to_completion_sec") > 0]
    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    min_lat = min(latencies) if latencies else 0
    max_lat = max(latencies) if latencies else 0

    failures = [r for r in results if r.get("status") != "completed" or not r.get("adjudication_match")]

    lines = [
        "# Mobius Chat Test Bot Report",
        "",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"- **Total runs:** {total}",
        f"- **Completed (API + response):** {completed}",
        f"- **Adjudication match (thumbs up):** {matches}",
        f"- **Match rate:** {100 * matches / total:.1f}%" if total else "-",
        "",
        "## Content Accuracy",
        "",
        f"- **Match rate (overall):** {100 * matches / total:.1f}%" if total else "-",
        f"- **In-manual accuracy:** {100 * in_manual_match / len(in_manual):.1f}% ({in_manual_match}/{len(in_manual)})" if in_manual else "-",
        f"- **Refrain accuracy (out_of_manual + off_topic):** {100 * refrain_match / refrain_total:.1f}% ({refrain_match}/{refrain_total})" if refrain_total else "-",
        "",
        "## Latency (time to completion)",
        "",
        f"- **Min:** {min_lat:.2f}s | **Max:** {max_lat:.2f}s | **Avg:** {avg_lat:.2f}s | **P95:** {p95:.2f}s",
        "",
        "## Per-run",
        "",
        "| # | Question (snippet) | Category | correlation_id | Match | Reason (snippet) | Rating | Feedback OK | Time (s) |",
        "|---|-------------------|----------|----------------|-------|-----------------|--------|-------------|----------|",
    ]
    def _cell(s: str) -> str:
        return (s or "").replace("|", "-").replace("\n", " ").strip()

    for i, r in enumerate(results, 1):
        q_full = r.get("question") or ""
        q_snip = _cell(q_full[:50]) + ("…" if len(q_full) > 50 else "")
        cat = _cell(r.get("category") or "")
        cid = _cell((r.get("correlation_id") or "")[:8])
        match = "yes" if r.get("adjudication_match") else "no"
        reason_full = r.get("adjudication_reason") or ""
        reason = _cell(reason_full[:40]) + ("…" if len(reason_full) > 40 else "")
        rating = _cell(r.get("rating_submitted") or "")
        fb_ok = "yes" if r.get("feedback_validated") else "no"
        t = r.get("time_to_completion_sec") or 0
        lines.append(f"| {i} | {q_snip} | {cat} | {cid} | {match} | {reason} | {rating} | {fb_ok} | {t:.1f} |")

    lines.extend([
        "",
        "## Failures and mismatches",
        "",
    ])
    for r in failures:
        lines.append(f"- **{r.get('correlation_id', '')[:8]}** {r.get('category', '')} | {r.get('question', '')[:60]}…")
        lines.append(f"  - Status: {r.get('status')} | Error: {r.get('error', '')[:200]}")
        if not r.get("adjudication_match") and r.get("adjudication_reason"):
            lines.append(f"  - Reason: {r.get('adjudication_reason', '')[:200]}")
        lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Report written to %s", report_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Mobius Chat Test Bot")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Config YAML path")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS_PATH, help="Questions YAML path")
    parser.add_argument("--report", type=Path, default=None, help="Report output path (default: report_dir/chat-bot-report-<timestamp>.md)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of questions (0 = all)")
    args = parser.parse_args()

    config_path = args.config if args.config.is_absolute() else _root / args.config
    questions_path = args.questions if args.questions.is_absolute() else _root / args.questions
    if not config_path.exists():
        logger.error("Config not found: %s", config_path)
        return 1
    if not questions_path.exists():
        logger.error("Questions not found: %s", questions_path)
        return 1

    config = load_config(config_path)
    questions = load_questions(questions_path)
    if args.limit > 0:
        questions = questions[: args.limit]
    if not questions:
        logger.error("No questions loaded")
        return 1

    if args.report is not None:
        report_path = args.report if args.report.is_absolute() else _root / args.report
    else:
        report_dir = config.get("report_dir") or "reports"
        prefix = config.get("report_filename_prefix") or "chat-bot-report"
        report_path = _root / report_dir / f"{prefix}-{int(time.time())}.md"

    results: list[dict] = []
    with httpx.Client(timeout=60.0) as client:
        for i, q in enumerate(questions):
            logger.info("Running question %d/%d: %s", i + 1, len(questions), (q.get("question") or "")[:60])
            result = run_one(q, config, client)
            results.append(result)
            if result.get("status") != "completed":
                logger.warning("Run %d status: %s %s", i + 1, result.get("status"), result.get("error", "")[:100])

    write_report(results, report_path, config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
