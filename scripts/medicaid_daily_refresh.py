#!/usr/bin/env python3
"""FL Medicaid daily refresh — PML + PPL.

Called daily by launchd (com.mobiusos.medicaid-refresh).
Also safe to run manually: python scripts/medicaid_daily_refresh.py

Strategy:
  1. Hit GET /medicaid/freshness on the running service.
     If PML and PPL are both current → exit 0 (nothing to do).
  2. If stale (or service unreachable), fall back to running
     run_fl_medicaid_daily_load.sh directly.
  3. Log every step with timestamps to logs/medicaid_refresh.log.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
MOBIUS_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = MOBIUS_ROOT / "mobius-dbt" / "scripts"
LOG_FILE    = MOBIUS_ROOT / "logs" / "medicaid_refresh.log"
VENV_PYTHON = MOBIUS_ROOT / ".venv" / "bin" / "python3"
SHELL_SCRIPT = SCRIPTS_DIR / "run_fl_medicaid_daily_load.sh"
DBT_PROJECT_DIR = MOBIUS_ROOT / "mobius-dbt"
UV_BIN = Path(os.environ.get("HOME", "/Users/ananth")) / ".local" / "bin" / "uv"

# ── Service config ─────────────────────────────────────────────────────────────
SERVICE_PORT = int(os.environ.get("CREDENTIALING_PORT", "8011"))
FRESHNESS_URL = f"http://localhost:{SERVICE_PORT}/medicaid/freshness"
REFRESH_URL   = f"http://localhost:{SERVICE_PORT}/medicaid/refresh/stream"
TIMEOUT_SECONDS = 3600  # SSE stream can take a while; full refresh is typically 10–20 min


# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("medicaid_refresh")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _env_for_subprocess() -> dict[str, str]:
    """Build env dict for subprocess calls, pulling BQ vars from .env files."""
    env = dict(os.environ)
    for env_path in (
        MOBIUS_ROOT / "mobius-config" / ".env",
        MOBIUS_ROOT / ".env",
    ):
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k = k.strip()
                    if k and k not in env:  # don't override real env
                        env[k] = v.strip().strip('"').strip("'")
    return env


def check_freshness() -> dict | None:
    """GET /medicaid/freshness. Returns parsed JSON or None if service is down."""
    try:
        import urllib.request
        with urllib.request.urlopen(FRESHNESS_URL, timeout=10) as r:
            return json.loads(r.read())
    except Exception as exc:
        log.warning("Freshness check failed (service may be down): %s", exc)
        return None


def refresh_via_api() -> bool:
    """POST /medicaid/refresh/stream — consume SSE until complete/error."""
    import urllib.request

    log.info("Triggering refresh via API: POST %s", REFRESH_URL)
    try:
        req = urllib.request.Request(REFRESH_URL, method="POST",
                                     headers={"Content-Type": "application/json"},
                                     data=b"{}")
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            buf = b""
            start = time.monotonic()
            for chunk in iter(lambda: resp.read(1024), b""):
                buf += chunk
                # Parse any complete SSE lines we've accumulated
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line or line == b":":
                        continue
                    if line.startswith(b"data: "):
                        try:
                            event = json.loads(line[6:])
                            evt_type = event.get("event", "progress")
                            if evt_type == "progress":
                                log.info("  [%s] %s — %s",
                                         event.get("table", "?"),
                                         event.get("step", "?"),
                                         event.get("message", ""))
                            elif evt_type == "complete":
                                result = event.get("result", {})
                                pml_rows = (result.get("pml") or {}).get("rows_loaded", "?")
                                ppl_rows = (result.get("ppl") or {}).get("rows_loaded", "?")
                                elapsed = round(time.monotonic() - start)
                                log.info("✓ Refresh complete in %ds — PML: %s rows, PPL: %s rows",
                                         elapsed, pml_rows, ppl_rows)
                                return True
                            elif evt_type == "error":
                                log.error("✗ Refresh error from API: %s", event.get("message"))
                                return False
                        except json.JSONDecodeError:
                            pass
        log.warning("SSE stream ended without complete event")
        return False
    except Exception as exc:
        log.error("API refresh failed: %s", exc)
        return False


def refresh_via_shell() -> bool:
    """Fall back: run run_fl_medicaid_daily_load.sh directly."""
    if not SHELL_SCRIPT.exists():
        log.error("Shell script not found: %s", SHELL_SCRIPT)
        return False

    log.info("Triggering refresh via shell script: %s", SHELL_SCRIPT)
    env = _env_for_subprocess()
    try:
        proc = subprocess.run(
            ["bash", str(SHELL_SCRIPT)],
            cwd=str(SCRIPTS_DIR.parent),
            env=env,
            capture_output=False,  # let output flow to our logger via stdout handler
            timeout=TIMEOUT_SECONDS,
        )
        if proc.returncode == 0:
            log.info("✓ Shell script completed successfully")
            return True
        else:
            log.error("✗ Shell script exited %d", proc.returncode)
            return False
    except subprocess.TimeoutExpired:
        log.error("✗ Shell script timed out after %ds", TIMEOUT_SECONDS)
        return False
    except Exception as exc:
        log.error("✗ Shell script failed: %s", exc)
        return False


def run_dbt() -> bool:
    """Run dbt for marts.medicaid_npi after a successful PML/PPL load."""
    log.info("Running dbt marts.medicaid_npi to rebuild stale mart tables...")
    env = _env_for_subprocess()
    uv = str(UV_BIN) if UV_BIN.exists() else "uv"
    try:
        proc = subprocess.run(
            [uv, "run", "dbt", "run", "--select", "marts.medicaid_npi"],
            cwd=str(DBT_PROJECT_DIR),
            env=env,
            timeout=TIMEOUT_SECONDS,
            capture_output=False,
        )
        if proc.returncode == 0:
            log.info("✓ dbt run complete — mart tables rebuilt")
            return True
        else:
            log.error("✗ dbt run exited %d — mart tables may be stale", proc.returncode)
            return False
    except subprocess.TimeoutExpired:
        log.error("✗ dbt timed out after %ds", TIMEOUT_SECONDS)
        return False
    except Exception as exc:
        log.error("✗ dbt failed: %s", exc)
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    log.info("=== FL Medicaid refresh check started ===")

    # Step 1: freshness check
    freshness = check_freshness()
    if freshness:
        pml_current = (freshness.get("pml") or {}).get("is_current", False)
        ppl_current = (freshness.get("ppl") or {}).get("is_current", False)
        pml_date    = (freshness.get("pml") or {}).get("last_loaded", "unknown")
        ppl_date    = (freshness.get("ppl") or {}).get("last_loaded", "unknown")
        today       = freshness.get("today", "unknown")

        log.info("Freshness: today=%s | PML=%s (%s) | PPL=%s (%s)",
                 today,
                 "current" if pml_current else "STALE", pml_date,
                 "current" if ppl_current else "STALE", ppl_date)

        if pml_current and ppl_current:
            log.info("PML and PPL are current — skipping PML/PPL load, running dbt anyway to ensure marts are fresh...")
            run_dbt()
            log.info("=== Done ===")
            return 0

        log.info("One or more tables stale — triggering refresh via API...")
        success = refresh_via_api()
    else:
        # Service unreachable — go straight to shell script
        log.warning("Service at port %d unreachable — falling back to shell script", SERVICE_PORT)
        success = refresh_via_shell()

    if success:
        # PML/PPL loaded — now rebuild dbt marts so the report runs against fresh data
        run_dbt()
        log.info("=== FL Medicaid refresh complete ===")
        return 0
    else:
        log.error("=== FL Medicaid refresh FAILED — check logs above ===")
        return 1


if __name__ == "__main__":
    sys.exit(main())
