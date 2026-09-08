#!/usr/bin/env python3
"""Build the joint sign-off page for the chat pipeline's sub-modules.

Every field comes from docs/chat-submodules.json, which is itself generated
from the source. The only hand-written content is the plain-English line per
module — the thing the two seats are actually signing off — and that is kept
here, next to the data, so a module added to the pipeline shows up with a
visibly missing description instead of silently vanishing.

Organised by where each module sits in the loop, because that is how someone
reads it: entry, the branch, the two paths, and the parts carried everywhere.
"""
import json, os, html, sys

ROOT = "/Users/ananth/Mobius"
CAT = os.path.join(ROOT, "docs/chat-submodules.json")
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/submodule-signoff.html"

PLAIN = {
 "orchestrator": "The front door. Runs the stages in order, handles the early exits when we have to stop and ask, and publishes the response.",
 "state_load": "Loads the conversation's memory before anything else runs. Applies what the user just said to what was already known, and hands on a single pack of context.",
 "classify": "Decides whether this message is a new question, or the user filling in a blank we asked about.",
 "plan": "Turns the message into a plan — what is really being asked, and the sub-questions that would answer it.",
 "clarify": "Catches what we cannot answer yet: a missing state or jurisdiction, or two routes that conflict. Asks instead of guessing.",
 "resolve": "Sends each sub-question to whichever agent can answer it, and walks down a fallback cascade when the first one cannot.",
 "integrate": "Assembles the answer the user actually sees — formats it and builds the response payload. The ReAct path replaces this entirely.",
 "continuity": "Knows when to stop trying alone: when to ask the user for help, when they have dropped the thread, and when we have hit the attempt ceiling.",
 "react_loop": "The engine of the ReAct path. Reason about what to do, call a tool, look at what came back, go again. Replaces plan, resolve and integrate in one loop.",
 "round0": "A shortcut. When the caller already did the work and handed us verified data, answer straight from it rather than entering the tool loop at all. Also handles a Continue after a mid-turn truncation.",
 "prompts": "Writes what the reasoning model actually reads each round — the system prompt, and the per-round context telling it where the turn has got to.",
 "tool_manifest": "The menu of tools the planner is shown. If a tool is not described here, the planner cannot choose it. Half the entries now come from the skill registry rather than this file.",
 "capabilities": "What each path can actually answer. Fed to the planner so it only splits a question into pieces something is able to handle.",
 "parsing": "Pulls a clean decision out of the model's messy reply — code fences, trailing commas, unescaped characters and all.",
 "react_retry_guard": "Stops the loop burning calls re-running a tool that already failed on the same inputs. Written against a pathology seen in production.",
 "curator_tools": "Two tools that let the assistant find authoritative source URLs for a payer and topic, and pull one into the corpus mid-conversation.",
 "critic": "Audits the draft answer against the sources it claims to rest on, before the user sees it. Shape checks only look at structure; this one checks whether the claims are actually grounded.",
 "governor": "The round policy — how many rounds this turn gets and what it is told to do next, driven by a contract rather than scattered hardcoded rules. Off by default.",
 "feedback_signal": "Decides whether this is the turn where we ask the user for feedback, based on their own cadence rather than a fixed interval.",
 "context": "The shared clipboard every stage reads and writes. Stages change it in place; state moves only through explicit transitions.",
 "message_resolver": "Works out what “it” means. Resolves pronouns against the previous turn, and notices when the answer is already sitting in a report we produced earlier.",
 "personalization": "Splices the user's own preferences into the prompt and honours their autonomy setting. A no-op for anyone who has not onboarded.",
 "active_context": "Remembers which tool the conversation is currently inside, so a follow-up lands in the right place instead of starting over.",
 "credentialing_envelope": "Routing helpers for credentialing conversations — works out when a message is really about roster reconciliation.",
 "stages": "The list of stage names. Twelve lines, but it is what every emit event and the whole trace are keyed on.",
}

def main():
    cat = json.load(open(CAT))
    flow = cat["flow"]
    by = {m["module"].split(".")[-1]: m for m in cat["submodules"]}

    strip = lambda fn: fn.replace("run_", "")
    order = []
    order.append(("Entry", "The single way in. Runs before the branch, for every turn.",
                  ["orchestrator"] + [strip(f) for f in flow["shared_pre"]]))
    for p in flow["react_phases"]:
        order.append((f"ReAct — {p['phase']}",
                      p["note"] + f"  (react_loop.py:{p['cite']})",
                      (["react_loop"] if p["phase"] == "Round 0" else []) + p["modules"]))
    order.append(("Classic path",
                  "Taken when use_react is off. run_integrate lives inside this branch only — the "
                  "ReAct path replaces it.",
                  [strip(f) for f in flow["classic_path"]]))
    placed = {n for _, _, ns in order for n in ns}
    order.append(("Carried everywhere",
                  "Not a step in the loop. Read or written by many stages rather than called at one point.",
                  sorted(n for n in by if n not in placed)))

    data = []
    for title, note, names in order:
        rows = []
        for n in names:
            m = by.get(n)
            if not m:
                continue
            rows.append({
                "id": n, "module": m["module"], "path": m["path"], "loc": m["loc"],
                "plain": PLAIN.get(n, ""),
                "doc": m.get("role_full") or m.get("role") or "",
                "api": m.get("api") or [],
                "callers": m.get("callers") or [],
                "fan_in": m.get("fan_in", 0),
                "signals": [t["signal"] for t in (m.get("telemetry") or [])],
                "tiers": sorted({t["tier"] for t in (m.get("telemetry") or [])}),
                "surfaces": m.get("surfaces") or [],
                "obs": m.get("observability"), "obs_note": m.get("observability_note", ""),
            })
        if rows:
            data.append({"title": title, "note": note, "rows": rows})

    seen = {r["id"] for g in data for r in g["rows"]}
    missing = sorted(set(by) - seen)
    undescribed = sorted(r["id"] for g in data for r in g["rows"] if not r["plain"])

    tpl = open(os.path.join(ROOT, "scripts/platform/signoff_template.html"),
               encoding="utf-8").read()
    out = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
    out = out.replace("/*__META__*/null", json.dumps({
        "generated_by": "scripts/platform/gen_signoff_page.py",
        "source": "docs/chat-submodules.json",
        "count": len(seen),
        "telemetry_sink": cat["telemetry_sink"],
        "branch_line": flow["branch_line"],
        "unplaced": missing,
        "undescribed": undescribed,
    }, ensure_ascii=False))
    open(OUT, "w", encoding="utf-8").write(out)
    print(f"{len(seen)} sub-modules · {len(data)} groups · unplaced {missing or 'none'} "
          f"· undescribed {undescribed or 'none'} -> {OUT}")

if __name__ == "__main__":
    main()
