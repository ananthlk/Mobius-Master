"""Live demo of mobius-skills-core against the real microservices.

Usage:
    cd /Users/ananth/Mobius/mobius-skills-core
    .venv/bin/python scripts/demo.py

Needs:
    * google-search microservice running (e.g. port 8004)
    * web-scraper microservice running (e.g. port 8002)

Shows:
    1. How to call a skill (one function call, no plumbing)
    2. Every emit event the skill fires (with task-promotion suggestions)
    3. The SkillResult it returns (what a consumer gets back)
"""
from __future__ import annotations

import os

# Point skills at the running microservices (your mstart already has them up)
os.environ["GOOGLE_SEARCH_URL"] = "http://localhost:8004/search?"
os.environ["WEB_SCRAPER_URL"] = "http://localhost:8002/scrape/review"

from mobius_skills_core import SkillEvent
from mobius_skills_core.skills.google_search import run_google_search
from mobius_skills_core.skills.web_scrape import run_web_scrape


# ── An "emitter" is just a function that gets called with events ─────
#
# Any consumer (chat, MCP, a demo script) can plug its own callback in.
# Here we just collect them so we can print them.
class EmitCollector:
    def __init__(self):
        self.events: list[SkillEvent] = []

    def __call__(self, event: SkillEvent) -> None:
        self.events.append(event)


def _hr(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _print_events(events: list[SkillEvent]) -> None:
    print(f"\n📡  {len(events)} emit event(s):")
    for i, e in enumerate(events, 1):
        ts = f"t+{(e.ts_ms - events[0].ts_ms):4d}ms"
        task_hint = ""
        if e.task_type:
            task_hint = f" [→ task-manager: {e.task_type}/{e.task_severity}]"
        print(f"  {i}. {ts}  {e.signal:<16}  step={e.step_id}")
        print(f"       note: {e.note}")
        if e.data:
            short_data = {k: v for k, v in e.data.items() if k not in ("body_preview",)}
            print(f"       data: {short_data}")
        if task_hint:
            print(f"       {task_hint.strip()}")


def _print_result(r) -> None:
    print(f"\n📦  SkillResult:")
    print(f"    signal:      {r.signal}")
    print(f"    text:        {(r.text or '')[:140]}{'…' if len(r.text) > 140 else ''}")
    print(f"    sources:     {len(r.sources)} item(s)")
    for i, s in enumerate(r.sources[:3], 1):
        print(f"       [{i}] {s.document_name}  url={s.url}")
    if r.extra:
        print(f"    extra keys:  {list(r.extra.keys())}")


# ──────────────────────────────────────────────────────────────────────
# DEMO 1 — Happy path: a real google search, emits collected
# ──────────────────────────────────────────────────────────────────────

_hr("DEMO 1 — google_search (happy path)")

collector = EmitCollector()
result = run_google_search(
    query="Sunshine Health medical necessity H0036",
    max_results=3,
    emitter=collector,              # ← the consumer wires itself in here
)
_print_events(collector.events)
_print_result(result)


# ──────────────────────────────────────────────────────────────────────
# DEMO 2 — Empty query: skill rejects before any HTTP call
# ──────────────────────────────────────────────────────────────────────

_hr("DEMO 2 — empty query (error BEFORE tool_invoked)")

collector = EmitCollector()
result = run_google_search(query="", emitter=collector)
_print_events(collector.events)
print(f"\n(Notice: only ONE emit — tool_error. tool_invoked was NEVER fired")
print(f" because validation short-circuits before the HTTP call.)")


# ──────────────────────────────────────────────────────────────────────
# DEMO 3 — Missing config: "blocker/high" severity suggestion
# ──────────────────────────────────────────────────────────────────────

_hr("DEMO 3 — missing config (escalates to BLOCKER severity)")

# Temporarily blank out the env var
saved = os.environ.pop("GOOGLE_SEARCH_URL", None)
os.environ.pop("CHAT_SKILLS_GOOGLE_SEARCH_URL", None)

collector = EmitCollector()
result = run_google_search(query="anything", emitter=collector)
_print_events(collector.events)
print(f"\n(Notice: task_type=blocker, task_severity=high — a consumer that")
print(f" promotes to task-manager should turn this into a loud alert.)")

# Restore
if saved:
    os.environ["GOOGLE_SEARCH_URL"] = saved


# ──────────────────────────────────────────────────────────────────────
# DEMO 4 — web_scrape with mode-specific emit
# ──────────────────────────────────────────────────────────────────────

_hr("DEMO 4 — web_scrape quick mode")

collector = EmitCollector()
result = run_web_scrape(
    url="https://www.sunshinehealth.com/providers.html",
    scrape_mode="quick",
    emitter=collector,
)
_print_events(collector.events)
_print_result(result)


# ──────────────────────────────────────────────────────────────────────
# DEMO 5 — No emitter: everything still works
# ──────────────────────────────────────────────────────────────────────

_hr("DEMO 5 — no emitter (consumer doesn't care about events)")

result = run_google_search(query="Florida Medicaid provider enrollment", max_results=2)
_print_result(result)
print(f"\n(Notice: zero emits collected because we didn't pass one. Skills")
print(f" work fine without event instrumentation.)")


print("\n" + "=" * 72)
print("DEMOS COMPLETE")
print("=" * 72)
print()
print("Takeaway:")
print("  - 1 function call gets you the skill.")
print("  - Emits are opt-in — pass an emitter if you want them.")
print("  - Consumers pick what to DO with events (display, log, promote to")
print("    task-manager) — the skill just reports what it's doing.")
