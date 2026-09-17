#!/usr/bin/env python3
"""Sweep the live estate and write the endpoint map into platform-definition.json.

WHY. The definition was hand-maintained and carried `service` names but no URLs,
so "where is X actually served?" had no answer on the page. It had also drifted:
written 2026-09-07, it was missing five services that are deployed and live.
Hand-maintenance is why; this is a generator so the next drift is one command.

WHAT IS MEASURED vs DECLARED, because the distinction is the whole point:
  measured  — service list, URL, ready revision, HTTP reachability (gcloud + curl)
  declared  — which module a service belongs to, owner, tier (from the definition)
A service with no module keeps `module: null` rather than being guessed into one.

SURFACES are separate from services. A service is a deployment; a surface is a
page a person opens. mobius-chat serves ten of them and one service URL tells you
none of them, which is exactly what "I lost track of the endpoints" means.
"""
from __future__ import annotations
import json, subprocess, pathlib, datetime, re, sys, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEF = ROOT / "docs" / "platform-definition.json"
CHAT_MAIN = ROOT / "mobius-chat" / "app" / "main.py"
REGION = "us-central1"


def sweep_services() -> list[dict]:
    out = subprocess.run(
        ["gcloud", "run", "services", "list", "--region", REGION,
         "--format=value(metadata.name,status.url,status.latestReadyRevisionName)"],
        capture_output=True, text=True, timeout=180)
    rows = []
    for line in out.stdout.splitlines():
        p = line.split()
        if len(p) >= 2:
            rows.append({"service": p[0], "url": p[1],
                         "ready_revision": p[2] if len(p) > 2 else None})
    return sorted(rows, key=lambda r: r["service"])


def sweep_chat_surfaces() -> list[dict]:
    """Page routes in mobius-chat, with their admin gate read per-route.

    Each route's body is bounded by the NEXT @app.get rather than a fixed line
    window: a 22-line window bled across the /platform -> /ab boundary and
    reported /platform as admin-gated, which it is not.
    """
    if not CHAT_MAIN.exists():
        return []
    L = CHAT_MAIN.read_text(encoding="utf-8").split("\n")
    starts = [(i, m.group(1)) for i, l in enumerate(L)
              if (m := re.search(r'@app\.get\("([^"]+)"', l))]
    surfaces = []
    for n, (i, path) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(L)
        body = "\n".join(L[i:end])
        if "FileResponse" not in body:
            continue
        html = re.search(r'_frontend\s*/\s*"([^"]+)"', body)
        surfaces.append({
            "path": path,
            "file": html.group(1) if html else None,
            "admin_gated_in_code": "_admin_enabled()" in body,
        })
    return sorted(surfaces, key=lambda s: s["path"])


def probe(url: str, timeout: int = 20) -> int | None:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def main() -> int:
    d = json.loads(DEF.read_text())
    live = {s["service"]: s for s in sweep_services()}
    by_service = {m["service"]: m for m in d["modules"] if m.get("service")}
    # A module may be deployed more than once (an older or parallel service of the
    # same app). Those are declared on the module as `also_deployed_as`; without
    # this they resurface as orphans every run, and a gap report that cries wolf
    # gets ignored on the day it is right.
    secondary = {a["service"]: m for m in d["modules"] for a in m.get("also_deployed_as", [])}

    # 1 — merge deployment facts onto the modules that name a service
    for svc, m in by_service.items():
        s = live.get(svc)
        m["deployment"] = ({"url": s["url"], "ready_revision": s["ready_revision"],
                            "state": "live"} if s else
                           {"url": None, "ready_revision": None, "state": "declared_not_deployed"})

    # 2 — services with no module: recorded, never invented into one
    orphan = [s for k, s in live.items() if k not in by_service and k not in secondary]

    # 3 — surfaces, probed live
    chat = live.get("mobius-chat")
    surfaces = []
    for s in sweep_chat_surfaces():
        url = (chat["url"] + s["path"]) if chat else None
        surfaces.append({**s, "service": "mobius-chat", "url": url,
                         "http": probe(url) if url else None})
    # Deep Research is served from mobius-payor, not from its own service --
    # the kind of thing a service list alone will never tell you.
    payor = live.get("mobius-payor")
    if payor:
        for p, label in (("/research/ask", "Deep Research — the user screen"),
                         ("/research/console", "Deep Research — the technical view")):
            u = payor["url"] + p
            surfaces.append({"path": p, "file": None, "admin_gated_in_code": None,
                             "service": "mobius-payor", "label": label,
                             "url": u, "http": probe(u)})

    d["endpoints"] = {
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "generated_by": "scripts/platform/gen_platform_endpoints.py",
        "region": REGION,
        "provenance": "measured: gcloud run services list + live HTTP probe",
        "caveats": [
            "http is a single unauthenticated GET at generation time; a 200 here is "
            "reachability, not a working page, and a scale-to-zero service may answer "
            "slowly on the first call",
            "admin_gated_in_code reads _admin_enabled() in the route body; a gated route "
            "can still answer 200 when admin is enabled in that environment",
            "services_without_module are recorded, not assigned -- guessing an owner from "
            "a name is how a registry acquires a wrong one",
        ],
        "services": list(live.values()),
        "services_without_module": [s["service"] for s in orphan],
        "secondary_deployments": [{"service": k, "module": m["id"]} for k, m in secondary.items()],
        "surfaces": surfaces,
    }
    d["last_updated"] = datetime.datetime.now(datetime.UTC).isoformat()
    d["updated_by"] = "gen_platform_endpoints.py (platform / product-awareness seat)"
    DEF.write_text(json.dumps(d, indent=2) + "\n")

    print(f"-> {DEF.relative_to(ROOT)}")
    print(f"   services live {len(live)} · modules {len(d['modules'])} · "
          f"surfaces {len(surfaces)}")
    if orphan:
        print(f"   NOT IN ANY MODULE ({len(orphan)}): " + ", ".join(s['service'] for s in orphan))
    nd = [m["id"] for m in d["modules"]
          if m.get("deployment", {}).get("state") == "declared_not_deployed"]
    if nd:
        print(f"   DECLARED BUT NOT DEPLOYED ({len(nd)}): " + ", ".join(nd))
    return 0


if __name__ == "__main__":
    sys.exit(main())
