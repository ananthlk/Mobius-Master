#!/usr/bin/env python3
"""Discover every human-facing surface across the estate, from the services.

WHY NOT THE DEFINITION. The module list's `surfaces` were hand-written, so they
were both incomplete (fact store, eval, org, rag consoles missing) and wrong in
places (three declared paths 404). Anything hand-maintained drifts; the services
already know their own routes.

METHOD, and its limits stated because the number is going on a page:
  1. /openapi.json per service -> every GET route with no path parameter.
     Routes WITH parameters are skipped: /org/{slug} is not a surface you can
     link to without inventing a slug, and inventing one is how a page starts
     lying.
  2. Probe each UNAUTHENTICATED, because that is what a person clicking a link
     gets. Record status AND Content-Type.
  3. Classify by what came back, not by what the path looks like:
       text/html            -> surface (a page)
       json / other 2xx     -> api
       401/403              -> auth-required (a surface may still be there)
       404/5xx              -> dead
  4. Services with no openapi are probed on a small fixed path list, and that
     is recorded as the weaker method it is -- absence there is not evidence.
"""
from __future__ import annotations
import json, subprocess, urllib.request, urllib.error, datetime, pathlib, sys
import concurrent.futures as cf

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "surfaces.json"
REGION = "us-central1"
NO_OPENAPI_PROBES = [
    "/", "/docs", "/redoc", "/index.html", "/health", "/healthz", "/ready",
    "/admin", "/ui", "/app", "/dashboard", "/console", "/home", "/static/index.html",
]
TIMEOUT = 25


def services() -> list[dict]:
    out = subprocess.run(
        ["gcloud", "run", "services", "list", "--region", REGION,
         "--format=value(metadata.name,status.url)"],
        capture_output=True, text=True, timeout=180)
    return [{"service": p[0], "url": p[1]}
            for p in (l.split() for l in out.stdout.splitlines()) if len(p) >= 2]


def idtoken() -> str:
    return subprocess.run(["gcloud", "auth", "print-identity-token"],
                          capture_output=True, text=True).stdout.strip()


SYNTH = "__mobius_probe__"


def fill_params(path: str) -> str:
    """Replace {param} with a synthetic value.

    This asks "does this route serve pages?", NOT "here is a link". A page route
    answers text/html even for a row that does not exist; an API answers JSON.
    The result is recorded with linkable=False so nobody mistakes the probe URL
    for a destination.
    """
    out, depth, buf = [], 0, []
    for ch in path:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            out.append(SYNTH)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def openapi_paths(url: str, tok: str) -> list[str] | None:
    try:
        r = urllib.request.Request(url + "/openapi.json",
                                   headers={"Authorization": f"Bearer {tok}"})
        with urllib.request.urlopen(r, timeout=TIMEOUT) as f:
            d = json.load(f)
    except Exception:
        return None
    return sorted(p for p, ops in d.get("paths", {}).items() if "get" in ops)


def probe(url: str, timeout: int = TIMEOUT) -> tuple[int | None, str]:
    """Unauthenticated GET: what a person following the link actually gets."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout) as r:
            return r.status, (r.headers.get("Content-Type") or "").split(";")[0].strip()
    except urllib.error.HTTPError as e:
        return e.code, (e.headers.get("Content-Type") or "").split(";")[0].strip()
    except Exception:
        return None, ""


def classify(status: int | None, ctype: str) -> str:
    if status is None:
        return "unreachable"
    if status in (401, 403):
        return "auth-required"
    if status >= 400:
        return "dead"
    if ctype.startswith("text/html"):
        return "surface"
    return "api"


def main() -> int:
    tok = idtoken()
    svcs = services()
    rows: list[dict] = []
    jobs: list[tuple[str, str, str, str]] = []   # service, base, path, method

    for s in svcs:
        paths = openapi_paths(s["url"], tok)
        if paths is None:
            for p in NO_OPENAPI_PROBES:
                jobs.append((s["service"], s["url"], p, "fixed-path-probe"))
        else:
            for p in paths:
                jobs.append((s["service"], s["url"], p,
                             "openapi" if "{" not in p else "openapi-synthetic-param"))

    def run(j):
        svc, base, path, how = j
        concrete = fill_params(path) if "{" in path else path
        u = base.rstrip("/") + ("" if concrete == "/" else concrete)
        st, ct = probe(u)
        row = {"service": svc, "path": path, "url": u, "http": st,
               "content_type": ct, "kind": classify(st, ct), "discovered_by": how,
               "linkable": "{" not in path}
        if "{" in path:
            row["probe_url"] = u
            row["url"] = None          # the probe URL is not a destination
            # A page route serves HTML even for a missing row; 404-with-HTML is
            # still a page. Only JSON/other says "this is an API".
            if row["kind"] == "dead" and ct.startswith("text/html"):
                row["kind"] = "surface-parameterised"
        return row

    with cf.ThreadPoolExecutor(16) as ex:
        rows = list(ex.map(run, jobs))

    # SECOND PASS. Two states from pass 1 are "I could not tell", not answers:
    #   auth-required -- a page behind a login is still a surface; unauthenticated
    #                    401 says nothing about what is there.
    #   unreachable   -- a timeout is not evidence. Retry once; a scale-to-zero
    #                    service is slow on the first hit.
    def probe_auth(url: str):
        try:
            r = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
            with urllib.request.urlopen(r, timeout=TIMEOUT) as f:
                return f.status, (f.headers.get("Content-Type") or "").split(";")[0].strip()
        except urllib.error.HTTPError as e:
            return e.code, (e.headers.get("Content-Type") or "").split(";")[0].strip()
        except Exception:
            return None, ""

    def second(r):
        if r["kind"] == "auth-required":
            st, ct = probe_auth(r["url"])
            k = classify(st, ct)
            r["authed_http"], r["authed_content_type"] = st, ct
            # Behind auth it is still a surface, but say so -- a link a reader
            # cannot open without signing in is a different promise.
            if k == "surface":
                r["kind"] = "surface-authed"
            elif k == "api":
                r["kind"] = "api-authed"
            elif r.get("content_type", "").startswith("application/json"):
                # urlopen follows redirects, so a PAGE behind a login would have
                # ended on an HTML login screen. A JSON error body instead means
                # the auth layer is answering an API caller.
                r["kind"] = "api-401-json"
            
        elif r["kind"] == "unreachable":
            st, ct = probe(r.get("url") or r.get("probe_url") or "", timeout=70)
            if st is not None:
                r["http"], r["content_type"] = st, ct
                r["kind"] = classify(st, ct)
                r["retried"] = True
            else:
                r["retried"] = True
        return r

    with cf.ThreadPoolExecutor(12) as ex:
        rows = list(ex.map(second, rows))

    surfaces = [r for r in rows
                if r["kind"] in ("surface", "surface-authed", "surface-parameterised")]
    by_kind: dict[str, int] = {}
    for r in rows:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1

    payload = {
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "generated_by": "scripts/platform/discover_surfaces.py",
        "provenance": ("measured: openapi route discovery + unauthenticated GET per route; "
                       "classified by response Content-Type, not by path shape"),
        "method_limits": [
            "GET routes WITH path parameters are not probed -- /org/{slug} is not linkable "
            "without inventing a value, and inventing one is how a page starts lying",
            "services with no /openapi.json are probed on a fixed path list only; absence "
            "there is weak evidence, not proof there is no surface",
            "probes are unauthenticated, which is what a person clicking gets; auth-required "
            "is reported as its own state rather than folded into dead",
            "routes WITH a path parameter are probed with a synthetic value to learn "
            "whether the route serves PAGES; they are marked linkable=false and their "
            "probe URL is not offered as a destination",
            "a 401 whose body is application/json is treated as an API: probes follow "
            "redirects, so a page behind a login would have landed on an HTML login screen",
            "a single probe at one moment -- a scale-to-zero service can be slow on the first hit",
        ],
        "counts": by_kind,
        "services_scanned": len(svcs),
        "routes_probed": len(rows),
        "surface_kinds": "surface = open; surface-authed = a page, but behind a login",
        "surfaces": sorted(surfaces, key=lambda r: (r["service"], r["path"])),
        "all_routes": sorted(rows, key=lambda r: (r["service"], r["path"])),
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"-> {OUT.relative_to(ROOT)}")
    print(f"   {len(svcs)} services · {len(rows)} routes probed · counts {by_kind}")
    print(f"   SURFACES FOUND: {len(surfaces)}")
    cur = None
    for r in payload["surfaces"]:
        if r["service"] != cur:
            cur = r["service"]; print(f"     {cur}")
        print(f"        {r['path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
