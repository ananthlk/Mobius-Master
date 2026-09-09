"""What every generator on this page needs, in one place.

Ananth, 2026-09-09: "the schema and the ux and the modules now need to align."

`esc` and `check_script` had two copies each, one per generator, and they had
already drifted — one checked the emitted JavaScript and the other did not,
until a page shipped whose every script was dead from a stray newline inside a
string literal. Rendering is not running, and one copy of the check that says so
is worth more than two that might disagree.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile


def esc(x) -> str:
    return (str("" if x is None else x).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def check_script(html: str, label: str = "page") -> bool:
    """Parse the JavaScript the page emits. Fails the build if it will not run.

    A generator once shipped a page that rendered perfectly and did nothing —
    one SyntaxError kills the whole block, and nothing about the HTML says so.
    """
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    if not blocks:
        return True
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write("\n".join(blocks))
        path = fh.name
    try:
        r = subprocess.run(["node", "--check", path], capture_output=True,
                           text=True)
    except FileNotFoundError:
        print(f"  ! node not found — {label} script NOT parsed; unverified.")
        return True
    finally:
        os.unlink(path)
    if r.returncode:
        print(f"\nBUILD FAILED — {label} emits JavaScript that will not parse:")
        print("  " + (r.stderr or "").strip().replace("\n", "\n  ")[:800])
        return False
    print(f"  script: {len(blocks)} block(s) parsed")
    return True
