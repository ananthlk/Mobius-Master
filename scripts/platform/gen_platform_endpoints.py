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
import json, subprocess, pathlib, datetime, re, sys, urllib.request, urllib.error, os

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


def probe(url: str, timeout: int = 20, retries: int = 1) -> int | None:
    """None means NO RESPONSE, which is not the same as 404 and must not be shown
    as one. Retry once: these are scale-to-zero services and the first hit after
    idle can exceed the timeout."""
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return probe(url, timeout=timeout + 20, retries=retries - 1) if retries > 0 else None


def sweep_tool_surface() -> dict:
    """The tools ReAct can actually be offered, counted from the live servers.

    Measured here: MCP tools per server (a real handshake + tools/list), and the
    builtin skills in chat's own registry. NOT measured here: the Tool Selection
    registry's own numbers (declarations, refusals, owners) -- that runs on its
    own database with no read API, so those belong to that seat and are recorded
    as reported, with a date, or not at all.
    """
    servers = {}
    chat_env = {
        "primary": os.environ.get("CHAT_SKILLS_MCP_URL")
                   or "https://mobius-provider-roster-credentialing-ortabkknqa-uc.a.run.app/mcp",
        "extra": os.environ.get("EXTRA_MCP_URLS")
                 or "https://mobius-appeals-prototype-ortabkknqa-uc.a.run.app",
    }
    for label, url in chat_env.items():
        if not url:
            continue
        u = url if url.rstrip("/").endswith("/mcp") else url.rstrip("/") + "/mcp"
        try:
            import asyncio
            from mcp.client.session import ClientSession
            from mcp.client.streamable_http import streamable_http_client
            import httpx

            async def _list(target: str):
                async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=10),
                                             follow_redirects=True) as h:
                    async with streamable_http_client(target, http_client=h) as st:
                        async with ClientSession(st[0], st[1]) as sess:
                            await sess.initialize()
                            return sorted(t.name for t in (await sess.list_tools()).tools)

            # Retry once. A single failed handshake against a scale-to-zero
            # service is not an outage, and reporting count:None for a server
            # that is actually serving five tools is a false alarm on the page.
            last = None
            for attempt in (1, 2):
                try:
                    names = asyncio.run(asyncio.wait_for(_list(u), 90))
                    break
                except Exception as exc:          # noqa: PERF203 - two tries
                    last = exc
                    names = None
            if names is None:
                raise last
            servers[u] = {"role": label, "count": len(names), "tools": names,
                          "attempts": attempt}
        except Exception as exc:
            servers[u] = {"role": label, "count": None,
                          "error": f"{type(exc).__name__}: {str(exc)[:80]}",
                          "note": "two handshakes failed; treat as unknown, not as zero tools"}
    builtin = sorted({m.group(1) for m in re.finditer(
        r'name="([a-z_]+)"',
        "\n".join((ROOT / "mobius-chat" / "app" / "skills" / "builtin" / f).read_text(errors="ignore")
                   for f in os.listdir(ROOT / "mobius-chat" / "app" / "skills" / "builtin")
                   if f.endswith(".py")))})
    total = sum(v["count"] or 0 for v in servers.values())
    return {"mcp_servers": servers, "mcp_tool_total": total,
            "builtin_skill_names": builtin, "builtin_count": len(builtin),
            "note": ("every MCP tool reaches ReAct through chat's registry; the Tool Selection "
                     "registry (mobius-tool-manifest) decides which are OFFERED and runs on its "
                     "own database, so its declaration/refusal counts are not swept here")}


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

    # 3 — surfaces. Discovered from the services by discover_surfaces.py, not
    # hand-listed: the hand-written list had 12 and missed the eval consoles,
    # the research console, org intelligence, the appeals admin pages and the
    # curator. Curated NAMES are kept where a module already named a path --
    # "Research Console" reads better than "/research/console" -- but the SET
    # comes from discovery, so a new page appears without anyone remembering.
    disc_path = ROOT / "docs" / "surfaces.json"
    discovered = {}
    if disc_path.exists():
        dj = json.loads(disc_path.read_text())
        for r in dj.get("surfaces", []):
            discovered.setdefault(r["service"], []).append(r)
    curated_name = {}
    for mod in d["modules"]:
        for sf in mod.get("surfaces") or []:
            if isinstance(sf, dict) and sf.get("path"):
                curated_name[((sf.get("service") or mod.get("service")), sf["path"])] = sf.get("name")

    # Attach the discovered set to each module, so the Product cards show every
    # page that module actually serves.
    # ATTRIBUTION IS NOT DERIVABLE FROM THE SERVICE. mobius-payor hosts payor,
    # service-line-registry AND Deep Research's two pages; mobius-rag hosts the
    # eval consoles and the fact store. An earlier version attached every
    # discovered page to every module on that service, which made fact-store
    # claim /eval and service-line-registry claim /research/ask. Wrong
    # information, confidently presented -- the failure this page exists to fix.
    #
    # So: a module keeps the surfaces a HUMAN attributed to it, refreshed with
    # the measured url/http from discovery. Discovery's full set lives in the
    # endpoints block grouped by SERVICE, which is a fact, and anything
    # discovered but attributed to no module is reported as a gap for a person
    # to assign.
    attributed: set[tuple[str, str]] = set()
    retired: list[dict] = []
    for mod in d["modules"]:
        fresh = []
        for sf in mod.get("surfaces") or []:
            if not isinstance(sf, dict) or not sf.get("path"):
                continue
            svc = sf.get("service") or mod.get("service")
            allr = (dj.get("all_routes", []) if disc_path.exists() else [])
            as_api = next((r for r in allr
                           if r["service"] == svc and r["path"] == sf["path"]
                           and r["kind"].startswith("api")), None)
            if as_api:
                retired.append({"module": mod["id"], "service": svc, "path": sf["path"],
                                "http": as_api["http"],
                                "why": f"declared a surface but serves {as_api['content_type']} — it is an API"})
                continue
            hit = next((r for r in discovered.get(svc, []) if r["path"] == sf["path"]), None)
            if hit:
                sf["url"], sf["http"] = hit["url"], hit["http"]
                sf["behind_login"] = hit["kind"] == "surface-authed"
                attributed.add((svc, sf["path"]))
            else:
                # Declared by a human, not found by discovery. Probe it, then
                # RETIRE it if the probe agrees it is not a page -- either the
                # route is gone (404, absent from the service's own table) or it
                # was never a page (an API mis-declared as a surface). Retiring
                # is recorded, never silent: a hand-written entry disappearing
                # without a trace is how the next person re-adds it.
                path = sf["path"]
                base = live.get(svc, {}).get("url")
                if base and path.startswith("/") and " " not in path:
                    u = base.rstrip("/") + ("" if path == "/" else path)
                    sf["url"], sf["http"] = u, probe(u)
                else:
                    sf["url"], sf["http"] = None, None
                in_table = any(r["path"] == sf["path"]
                               for r in (dj.get("all_routes", []) if disc_path.exists() else [])
                               if r["service"] == svc)
                if "{" not in sf["path"] and sf.get("http") not in (200, None):
                    retired.append({"module": mod["id"], "service": svc, "path": sf["path"],
                                    "http": sf.get("http"),
                                    "why": ("route is absent from the service's own table and 404s"
                                            if not in_table else "declared as a surface but does not answer")})
                    continue
            fresh.append(sf)
        if fresh:
            mod["surfaces"] = fresh

    # ATTRIBUTION, where it is derivable and only there. A service that backs
    # exactly ONE module attributes unambiguously -- that is 32 of 34 services.
    # The two shared ones (mobius-payor: payor + service-line-registry + Deep
    # Research's pages; mobius-rag: rag + fact-store) cannot be settled by any
    # rule available here, so their unclaimed pages are left for a person WITH
    # the candidate modules named, rather than assigned to whichever module the
    # dict happened to hold.
    mods_on: dict[str, list] = {}
    for m in d["modules"]:
        if m.get("service"):
            mods_on.setdefault(m["service"], []).append(m)
        for a in m.get("also_deployed_as", []):
            mods_on.setdefault(a["service"], []).append(m)

    # Where a service backs several modules the rule cannot decide, so these are
    # decided from EVIDENCE — each page's own <title>, fetched 2026-09-18 — and
    # enumerated so they are reviewable and reversible. A title is what the page
    # says it is; it beats both the service name and the path shape.
    BY_EVIDENCE = {
        ("mobius-payor", "/"):                         ("payor", 'title "Mobius Payor"'),
        ("mobius-payor", "/preview/sources-structure"): ("payor", 'title "Mobius Payor"'),
        ("mobius-payor", "/dashboard/{payor}"):        ("payor", "per-payor dashboard; path names the payor"),
        ("mobius-payor", "/research"):                 ("deep-research", 'title "Mobius Research — Ask"'),
        ("mobius-payor", "/research-console"):         ("deep-research", "research console; sibling of /research/console"),
        ("mobius-rag", "/eval"):                       ("eval", 'Eval Console'),
        ("mobius-rag", "/eval/bank"):                  ("eval", 'title "Eval Console · Run the bank"'),
        ("mobius-rag", "/eval/query"):                 ("eval", 'title "Mobius Eval · Query"'),
        ("mobius-rag", "/eval/runs"):                  ("eval", 'title "Eval Console · Runs"'),
        ("mobius-rag", "/curator"):                    ("rag", 'title "Source Registry — Curator"'),
        ("mobius-rag", "/trace-explorer"):             ("rag", 'title "Payor Policy — Trace Explorer"'),
        ("mobius-rag", "/drive/popup-success"):        ("rag", 'title "Drive connected" — OAuth callback, not a product page'),
    }
    by_id = {m["id"]: m for m in d["modules"]}

    auto, needs_human = [], []
    for svc, items in discovered.items():
        owners = mods_on.get(svc, [])
        for r in items:
            if (svc, r["path"]) in attributed:
                continue
            ev = BY_EVIDENCE.get((svc, r["path"]))
            if ev and ev[0] in by_id:
                m = by_id[ev[0]]
                m.setdefault("surfaces", []).append({
                    "name": r["path"], "path": r["path"], "service": svc,
                    "url": r["url"], "http": r["http"],
                    "behind_login": r["kind"] == "surface-authed",
                    "attributed_by": f"evidence: {ev[1]}",
                })
                auto.append({"module": ev[0], "service": svc, "path": r["path"],
                             "how": "evidence"})
            elif len(owners) == 1:
                m = owners[0]
                m.setdefault("surfaces", []).append({
                    "name": r["path"], "path": r["path"], "service": svc,
                    "url": r["url"], "http": r["http"],
                    "behind_login": r["kind"] == "surface-authed",
                    "attributed_by": "sole module on this service",
                })
                auto.append({"module": m["id"], "service": svc, "path": r["path"]})
            else:
                needs_human.append({
                    "service": svc, "path": r["path"], "url": r["url"],
                    "candidates": [m["id"] for m in owners] or ["(no module on this service)"],
                })
    unattributed = needs_human

    # 3b — chat/payor page probe (kept: it reads chat's ROUTE TABLE, which tells
    # us the admin gate, something a probe cannot see)
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

    # Probe the surfaces the MODULES declare, not just chat's routes. Two were
    # dead at the first sweep (chat /pipeline, payor /service-lines/review) and
    # the page was about to offer them as links. A chip that looks clickable and
    # 404s is worse than one that was honest about being a label, so the result
    # is written onto the surface and the page decides from it.
    for mod in d["modules"]:
        for sf in mod.get("surfaces") or []:
            if not isinstance(sf, dict):
                continue            # malformed entry: leave it, don't guess a shape
            path = sf.get("path") or ""
            if not path.startswith("/") or " " in path:
                sf["url"], sf["http"] = None, None    # a repo path or a label
                continue
            base_svc = sf.get("service") or mod.get("service")
            base = live.get(base_svc, {}).get("url")
            if not base:
                sf["url"], sf["http"] = None, None
                continue
            u = base.rstrip("/") + ("" if path == "/" else path)
            sf["url"], sf["http"] = u, probe(u)

    # A parameterised path is probed with a synthetic value, so its 404 is
    # expected and says nothing about the route. Excluded from the dead list.
    dead = [(m["id"], sf["path"], sf["http"])
            for m in d["modules"] for sf in (m.get("surfaces") or [])
            if isinstance(sf, dict) and sf.get("url") and sf.get("http") != 200
            and "{" not in sf["path"]]

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
        "discovered_surfaces": sorted(
            [r for items in discovered.values() for r in items],
            key=lambda r: (r["service"], r["path"])),
        "retired_declared_surfaces": retired,
        "attributed_automatically": sorted(auto, key=lambda r: (r["service"], r["path"])),
        "discovered_unattributed": sorted(unattributed, key=lambda r: (r["service"], r["path"])),
        "attribution_rule": ("a service backing exactly one module attributes unambiguously; "
                             "shared services are left for a person with candidates named"),
        "dead_declared_surfaces": [
            {"module": a, "path": b, "http": c} for a, b, c in dead
        ],
        "tool_surface": sweep_tool_surface(),
    }
    d["last_updated"] = datetime.datetime.now(datetime.UTC).isoformat()
    d["updated_by"] = "gen_platform_endpoints.py (platform / product-awareness seat)"
    DEF.write_text(json.dumps(d, indent=2) + "\n")

    print(f"-> {DEF.relative_to(ROOT)}")
    print(f"   services live {len(live)} · modules {len(d['modules'])} · "
          f"surfaces {len(surfaces)} · mcp tools "
          f"{d['endpoints']['tool_surface']['mcp_tool_total']} · builtins "
          f"{d['endpoints']['tool_surface']['builtin_count']}")
    if retired:
        print(f"   RETIRED (declared but not a live page): {len(retired)}")
        for r in retired:
            print(f"      {r['module']:22} {r['path']:28} {r['why']}")
    if auto:
        print(f"   attributed automatically (sole module on service): {len(auto)}")
    if unattributed:
        print(f"   NEEDS A HUMAN ({len(unattributed)}) -- shared service, candidates named:")
        for r in unattributed:
            print(f"      {r['service']}{r['path']}  -> {' | '.join(r['candidates'])}")
    if dead:
        print(f"   DECLARED SURFACE NOT ANSWERING ({len(dead)}): "
              + ", ".join(f"{a}{b} [{c}]" for a, b, c in dead))
    if orphan:
        print(f"   NOT IN ANY MODULE ({len(orphan)}): " + ", ".join(s['service'] for s in orphan))
    nd = [m["id"] for m in d["modules"]
          if m.get("deployment", {}).get("state") == "declared_not_deployed"]
    if nd:
        print(f"   DECLARED BUT NOT DEPLOYED ({len(nd)}): " + ", ".join(nd))
    return 0


if __name__ == "__main__":
    sys.exit(main())
