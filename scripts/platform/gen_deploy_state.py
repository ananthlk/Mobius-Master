#!/usr/bin/env python3
"""What is actually DEPLOYED, versus merely committed.

WHY. Every "FIXED (chat abc1234)" stamp in the findings log says the code changed. It
says NOTHING about whether that code is running. I conflated the two repeatedly on
2026-09-10 — told Ananth the invented FL Medicaid deadline was still live hours after
it shipped, then told him a deploy had landed when it had not, then reported a badge
green off a coverage file the merge had not re-read. Each time the page had no way to
express the difference, so the difference lived in my head and my head was wrong.

Ananth, 2026-09-10: "before any more changes we make sure we have everything squared
and you update your page to line up with their commit."

So the page now resolves it mechanically:
  - read the DEPLOYED image tag off Cloud Run and pull the commit out of it
  - for every commit referenced in a finding, ask git whether it is an ANCESTOR of the
    deployed commit
  - LIVE means running. FIXED-NOT-DEPLOYED means written and not running. They render
    differently, and a stamp can no longer imply the first while meaning the second.

Reads Cloud Run when gcloud is available; falls back to a cached value and SAYS SO,
because "I could not check" and "it is not deployed" are different answers.
"""
import json, os, re, subprocess, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
CHAT = os.path.join(ROOT, "mobius-chat")
OUT = os.path.join(ROOT, "docs", "chat-deploy-state.json")
SERVICE, REGION = "mobius-chat", "us-central1"
_SHA = re.compile(r"\b([0-9a-f]{7,40})\b")


def _git(*a):
    r = subprocess.run(["git", "-C", CHAT, *a], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def live_revision():
    try:
        rev = subprocess.run(
            ["gcloud", "run", "services", "describe", SERVICE, "--region", REGION,
             "--format", "value(status.traffic[0].revisionName,status.traffic[0].percent)"],
            capture_output=True, text=True, timeout=60)
        img = subprocess.run(
            ["gcloud", "run", "services", "describe", SERVICE, "--region", REGION,
             "--format", "value(spec.template.spec.containers[0].image)"],
            capture_output=True, text=True, timeout=60)
        if rev.returncode or img.returncode:
            return None
        name, _, pct = rev.stdout.strip().partition("\t")
        tag = img.stdout.strip().rsplit(":", 1)[-1]
        sha = tag.rsplit("-", 1)[-1][:9]
        return {"revision": name, "traffic_percent": pct.strip(), "image_tag": tag,
                "commit": sha, "checked": True}
    except Exception:
        return None


def main():
    live = live_revision()
    if not live:
        # Could-not-check is NOT not-deployed. Say which one happened.
        prev = json.load(open(OUT)) if os.path.exists(OUT) else {}
        prev["checked"] = False
        prev["note"] = ("gcloud unavailable — this is the LAST KNOWN deploy state, not a "
                        "current reading. Could-not-check is not the same answer as "
                        "not-deployed.")
        json.dump(prev, open(OUT, "w"), indent=1)
        print("deploy state: COULD NOT CHECK — kept last known and flagged it")
        return

    dep = live["commit"]
    head = _git("rev-parse", "--short=9", "HEAD")
    behind = _git("rev-list", "--count", f"{dep}..HEAD")
    subj = _git("log", "--format=%s", "-1", dep)

    # Which referenced commits are actually running.
    content = open(os.path.join(ROOT, "scripts", "platform",
                                "chat_node_content.py")).read()
    cands = {c for c in _SHA.findall(content) if len(c) in (7, 8, 9)}
    status = {}
    for c in sorted(cands):
        if not _git("cat-file", "-t", c) == "commit":
            continue
        r = subprocess.run(["git", "-C", CHAT, "merge-base", "--is-ancestor", c, dep],
                           capture_output=True)
        status[c] = "live" if r.returncode == 0 else "committed_not_deployed"

    live.update({"head": head, "commits_behind_head": behind,
                 "deployed_commit_subject": subj, "commit_status": status})
    json.dump(live, open(OUT, "w"), indent=1, sort_keys=True)
    n_live = sum(1 for v in status.values() if v == "live")
    print(f"deploy state: {live['revision']} @ {live['traffic_percent']}% traffic · "
          f"commit {dep} · {behind} commits behind HEAD ({head})")
    print(f"  referenced commits: {n_live} live · "
          f"{len(status)-n_live} committed-not-deployed")


if __name__ == "__main__":
    main()
