#!/usr/bin/env python3
"""fleetpower — Cloud Run fleet power manager for Mobius.

Manages PINNED CAPACITY (min/max instances) against a desired-state manifest
(fleet.yaml) and audits spend, because that's where the money goes: a service
at min=0 with no traffic costs ~$0, while one pinned instance of 4vCPU/8Gi
with always-allocated CPU costs ~$230/mo.

Commands:
  status              manifest vs live scaling config + live instance counts
  apply [--dry-run]   enforce the manifest (service-level --min/--max updates)
  audit [--days N]    billable hours vs requests per service; est. cost; waste flags
  boost SVC --min N   temporary service-level floor (sprint); prints the revert

Reads BOTH scaling layers — the serving revision's template annotations AND the
service-level run.googleapis.com/minScale|maxScale annotations. The service
level one is the trap: `gcloud run services update --min=8` sets it, deploys
never clear it, and it silently pins instances forever (cost audit, Sep 2026).
"""
import argparse
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

MANIFEST_DEFAULT = Path(__file__).parent / "fleet.yaml"

# us-central1 tier-1 $/hour. Instance-based (always-allocated CPU) vs
# request-based rates; request-based idle min instances actually bill less
# than this, so audit estimates are an upper bound for throttled services.
RATE = {
    "always": {"cpu": 0.0648, "mem": 0.0072},
    "request": {"cpu": 0.0864, "mem": 0.0090},
}

ANN_SVC_MIN = "run.googleapis.com/minScale"
ANN_SVC_MAX = "run.googleapis.com/maxScale"
ANN_REV_MIN = "autoscaling.knative.dev/minScale"
ANN_REV_MAX = "autoscaling.knative.dev/maxScale"
ANN_THROTTLE = "run.googleapis.com/cpu-throttling"


def run(cmd: list[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{res.stderr.strip()}")
    return res.stdout


def load_manifest(path: Path) -> dict:
    m = yaml.safe_load(path.read_text())
    # YAML parses a bare `off` as boolean False; normalize back to the string
    m["modes"] = {("off" if k is False else k): v for k, v in m["modes"].items()}
    for name, entry in m.get("services", {}).items():
        entry = entry or {}
        mode = entry.get("mode", "standby")
        if mode is False:
            mode = entry["mode"] = "off"
        if mode not in m["modes"]:
            sys.exit(f"fleet.yaml: service {name} has unknown mode '{mode}'")
        target = dict(m["modes"][mode])
        target.update({k: entry[k] for k in ("min", "max") if k in entry})
        entry["target"] = target
        m["services"][name] = entry
    return m


def cpu_units(s: str | None) -> float:
    if not s:
        return 1.0
    return float(s[:-1]) / 1000 if s.endswith("m") else float(s)


def mem_gib(s: str | None) -> float:
    if not s:
        return 0.5
    for suf, mul in (("Gi", 1.0), ("Mi", 1 / 1024), ("G", 1.0), ("M", 1 / 1024)):
        if s.endswith(suf):
            return float(s[: -len(suf)]) * mul
    return float(s) / 2**30


def live_services(project: str, region: str) -> dict[str, dict]:
    raw = json.loads(run([
        "gcloud", "run", "services", "list", "--project", project,
        "--region", region, "--format", "json",
    ]))
    out = {}
    for svc in raw:
        name = svc["metadata"]["name"]
        svc_ann = svc["metadata"].get("annotations", {})
        tpl = svc["spec"]["template"]["metadata"].get("annotations", {})
        limits = (svc["spec"]["template"]["spec"]["containers"][0]
                  .get("resources", {}).get("limits", {}))
        svc_min = int(svc_ann[ANN_SVC_MIN]) if ANN_SVC_MIN in svc_ann else None
        svc_max = int(svc_ann[ANN_SVC_MAX]) if ANN_SVC_MAX in svc_ann else None
        rev_min = int(tpl[ANN_REV_MIN]) if ANN_REV_MIN in tpl else None
        rev_max = int(tpl[ANN_REV_MAX]) if ANN_REV_MAX in tpl else None
        out[name] = {
            "svc_min": svc_min, "svc_max": svc_max,
            "rev_min": rev_min, "rev_max": rev_max,
            # effective floor: both layers pin instances independently
            "eff_min": max(svc_min or 0, rev_min or 0),
            "eff_max": svc_max if svc_max is not None else (rev_max or 100),
            "cpu": cpu_units(limits.get("cpu")),
            "mem": mem_gib(limits.get("memory")),
            # cpu-throttling=false ⇒ always-allocated (instance-based) billing
            "always_cpu": tpl.get(ANN_THROTTLE) == "false",
        }
    return out


# ---------- monitoring ----------

def _token() -> str:
    return run(["gcloud", "auth", "print-access-token"]).strip()


def query_metric(project: str, metric: str, days: float, aligner: str) -> dict[str, float]:
    """Per-service sum of a metric over the trailing window."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    period = int((end - start).total_seconds())
    params = {
        "filter": f'metric.type="{metric}"',
        "interval.startTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "interval.endTime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "aggregation.alignmentPeriod": f"{period}s",
        "aggregation.perSeriesAligner": aligner,
        "aggregation.crossSeriesReducer": "REDUCE_SUM",
        "aggregation.groupByFields": "resource.label.service_name",
    }
    url = (f"https://monitoring.googleapis.com/v3/projects/{project}/timeSeries?"
           + urllib.parse.urlencode(params))
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {_token()}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    out: dict[str, float] = {}
    for ts in data.get("timeSeries", []):
        name = ts["resource"]["labels"].get("service_name", "?")
        for p in ts.get("points", []):
            v = p["value"]
            out[name] = out.get(name, 0.0) + float(v.get("doubleValue") or v.get("int64Value") or 0)
    return out


def instance_counts(project: str) -> dict[str, float]:
    """Latest per-service instance count (max over last 10 min)."""
    return query_metric(project, "run.googleapis.com/container/instance_count",
                        days=10 / 1440, aligner="ALIGN_MAX")


def hourly_rate(cfg: dict) -> float:
    r = RATE["always" if cfg["always_cpu"] else "request"]
    return cfg["cpu"] * r["cpu"] + cfg["mem"] * r["mem"]


# ---------- commands ----------

def cmd_status(m: dict, args) -> int:
    live = live_services(m["project"], m["region"])
    try:
        inst = instance_counts(m["project"])
    except Exception as e:
        print(f"(instance counts unavailable: {e})", file=sys.stderr)
        inst = {}
    drift = 0
    print(f"{'SERVICE':<38}{'MODE':<9}{'TARGET':<9}{'LIVE':<9}{'INST':<6}{'CPU':>4}{'MEM':>7}  NOTES")
    for name in sorted(set(live) | set(m["services"])):
        entry = m["services"].get(name)
        cfg = live.get(name)
        if cfg is None:
            print(f"{name:<38}{'?':<9}{'-':<9}{'GONE':<9}{'':<6}{'':>4}{'':>7}  in manifest but not deployed")
            continue
        live_s = f"{cfg['eff_min']}..{cfg['eff_max']}"
        n = f"{inst.get(name, 0):.0f}" if inst else "?"
        res = f"{cfg['cpu']:g}"
        memf = f"{cfg['mem']:g}Gi"
        if entry is None:
            print(f"{name:<38}{'UNMANAGED':<9}{'-':<9}{live_s:<9}{n:<6}{res:>4}{memf:>7}  add to fleet.yaml")
            continue
        t = entry["target"]
        target_s = f"{t['min']}..{t['max']}"
        ok = cfg["eff_min"] == t["min"] and cfg["eff_max"] == t["max"]
        flag = "" if ok else "DRIFT"
        if not ok:
            drift += 1
        notes = " ".join(x for x in (flag, entry.get("note", "")) if x)
        print(f"{name:<38}{entry.get('mode','?'):<9}{target_s:<9}{live_s:<9}{n:<6}{res:>4}{memf:>7}  {notes}")
    print(f"\n{drift} service(s) drifted from manifest." if drift else "\nAll managed services match the manifest.")
    return 1 if drift else 0


def plan_changes(m: dict, live: dict) -> list[dict]:
    changes = []
    for name, entry in m["services"].items():
        cfg = live.get(name)
        if cfg is None:
            continue
        t = entry["target"]
        if cfg["eff_min"] == t["min"] and cfg["eff_max"] == t["max"]:
            continue
        # The revision-level floor can only be lowered by a new revision.
        needs_redeploy = (cfg["rev_min"] or 0) > t["min"]
        flags = []
        if cfg["eff_min"] != t["min"]:
            if needs_redeploy:
                flags += [f"--min-instances={t['min'] if t['min'] else 'default'}"]
            flags += [f"--min={t['min'] if t['min'] else 'default'}"]
        if cfg["eff_max"] != t["max"]:
            flags += [f"--max={t['max']}"]
        changes.append({
            "service": name,
            "from": f"{cfg['eff_min']}..{cfg['eff_max']}",
            "to": f"{t['min']}..{t['max']}",
            "flags": flags,
            "needs_redeploy": needs_redeploy,
        })
    return changes


def cmd_apply(m: dict, args) -> int:
    live = live_services(m["project"], m["region"])
    changes = plan_changes(m, live)
    if not changes:
        print("Nothing to do — live state matches fleet.yaml.")
        return 0
    failures: list[str] = []
    for ch in changes:
        cmd = ["gcloud", "run", "services", "update", ch["service"],
               "--project", m["project"], "--region", m["region"], *ch["flags"]]
        tag = " (creates new revision)" if ch["needs_redeploy"] else ""
        print(f"{ch['service']}: {ch['from']} -> {ch['to']}{tag}")
        if args.dry_run:
            print("  would run:", " ".join(cmd))
            continue
        if ch["needs_redeploy"] and not args.allow_redeploy:
            print("  SKIPPED: lowering a revision-level min needs a new revision; "
                  "re-run with --allow-redeploy")
            continue
        try:
            run(cmd)
        except RuntimeError as e:
            failures.append(ch["service"])
            print(f"  FAILED: {str(e).splitlines()[-1]}")
            continue
        # read back — a write without a reader is how the 8-instance pin survived
        after = live_services(m["project"], m["region"])[ch["service"]]
        got = f"{after['eff_min']}..{after['eff_max']}"
        print(f"  applied, live now {got}" + ("" if got == ch["to"] else "  MISMATCH!"))
    if failures:
        print(f"\n{len(failures)} failed: {', '.join(failures)}")
    return 1 if failures else 0


def cmd_audit(m: dict, args) -> int:
    days = args.days
    live = live_services(m["project"], m["region"])
    hours = query_metric(m["project"], "run.googleapis.com/container/billable_instance_time",
                         days, "ALIGN_SUM")
    reqs = query_metric(m["project"], "run.googleapis.com/request_count", days, "ALIGN_SUM")
    rows = []
    for name, cfg in live.items():
        h = hours.get(name, 0.0) / 3600
        r = int(reqs.get(name, 0))
        est_mo = h * hourly_rate(cfg) * (30 / days)
        pinned_h = cfg["eff_min"] * 24 * days
        flags = []
        if name not in m["services"]:
            flags.append("UNMANAGED")
        # burning instance-hours far beyond both its pin and its traffic
        if h > pinned_h * 1.5 + 1 and r < h * 10:
            flags.append("WASTE?")
        if cfg["eff_min"] > 0 and r < 10 * days:
            flags.append("PINNED-IDLE")
        rows.append((est_mo, name, h, r, cfg, flags))
    rows.sort(reverse=True)
    total = sum(r[0] for r in rows)
    print(f"Trailing {days}d, extrapolated to 30d (upper bound for throttled services):\n")
    print(f"{'SERVICE':<38}{'INST-HRS':>9}{'REQS':>10}{'MIN':>4}{'$EST/MO':>9}  FLAGS")
    for est_mo, name, h, r, cfg, flags in rows:
        if h < 0.01 and not flags:
            continue
        print(f"{name:<38}{h:>9.1f}{r:>10,}{cfg['eff_min']:>4}{est_mo:>9.2f}  {' '.join(flags)}")
    print(f"\n{'TOTAL':<38}{'':>9}{'':>10}{'':>4}{total:>9.2f}")
    return 0


def cmd_report(m: dict, args) -> int:
    """Generate the self-contained HTML dashboard (report_template.html + live data)."""
    days = args.days
    live = live_services(m["project"], m["region"])
    hours = query_metric(m["project"], "run.googleapis.com/container/billable_instance_time",
                         days, "ALIGN_SUM")
    reqs = query_metric(m["project"], "run.googleapis.com/request_count", days, "ALIGN_SUM")
    try:
        inst = instance_counts(m["project"])
    except Exception:
        inst = {}
    services = []
    for name, cfg in live.items():
        entry = m["services"].get(name)
        h = hours.get(name, 0.0) / 3600
        r = int(reqs.get(name, 0))
        est_mo = h * hourly_rate(cfg) * (30 / days)
        pinned_h = cfg["eff_min"] * 24 * days
        flags = []
        if h > pinned_h * 1.5 + 1 and r < h * 10:
            flags.append("WASTE?")
        if cfg["eff_min"] > 0 and r < 10 * days:
            flags.append("PINNED-IDLE")
        t = entry["target"] if entry else None
        services.append({
            "name": name,
            "mode": entry.get("mode", "standby") if entry else None,
            "unmanaged": entry is None,
            "note": (entry or {}).get("note", ""),
            "target_min": t["min"] if t else None,
            "target_max": t["max"] if t else None,
            "eff_min": cfg["eff_min"], "eff_max": cfg["eff_max"],
            "drift": bool(t) and (cfg["eff_min"] != t["min"] or cfg["eff_max"] != t["max"]),
            "instances": int(inst[name]) if name in inst else None,
            "cpu": cfg["cpu"], "mem": round(cfg["mem"], 2),
            "reqs": r, "hours": round(h, 1), "est_mo": round(est_mo, 2),
            "always_cpu": cfg["always_cpu"], "flags": flags,
        })
    services.sort(key=lambda s: (-s["est_mo"], s["name"]))
    data = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "window_days": days,
        "project": m["project"], "region": m["region"],
        "services": services,
    }
    template = (Path(__file__).parent / "report_template.html").read_text()
    html = template.replace("/*__DATA__*/", json.dumps(data).replace("</", "<\\/"))
    out = Path(args.out)
    out.write_text(html)
    total = sum(s["est_mo"] for s in services)
    print(f"Wrote {out} — {len(services)} services, est ${total:,.0f}/mo, "
          f"{sum(1 for s in services if s['drift'])} drifted")
    return 0


def cmd_boost(m: dict, args) -> int:
    entry = m["services"].get(args.service)
    cmd = ["gcloud", "run", "services", "update", args.service,
           "--project", m["project"], "--region", m["region"], f"--min={args.min}"]
    if args.max is not None:
        cmd.append(f"--max={args.max}")
    print(" ".join(cmd))
    run(cmd)
    print(f"Boosted {args.service} to min={args.min}. This is DRIFT by design; "
          f"`fleetpower status` will nag until you revert:")
    if entry:
        print("  fleetpower apply        # restores manifest state")
    else:
        print(f"  gcloud run services update {args.service} --region {m['region']} --min=default")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="fleetpower", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, default=MANIFEST_DEFAULT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("apply")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--allow-redeploy", action="store_true",
                   help="permit changes that create a new revision (revision-level min)")
    p = sub.add_parser("audit")
    p.add_argument("--days", type=float, default=7)
    p = sub.add_parser("boost")
    p.add_argument("service")
    p.add_argument("--min", type=int, required=True)
    p.add_argument("--max", type=int)
    p = sub.add_parser("report")
    p.add_argument("--days", type=float, default=1)
    p.add_argument("-o", "--out", default=str(Path(__file__).parent / "fleet-report.html"))
    args = ap.parse_args()
    m = load_manifest(args.manifest)
    return {"status": cmd_status, "apply": cmd_apply, "audit": cmd_audit,
            "boost": cmd_boost, "report": cmd_report}[args.cmd](m, args)


if __name__ == "__main__":
    sys.exit(main())
