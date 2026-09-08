#!/usr/bin/env python3
"""cut_product_release.py <version> — build a product release lockfile from git.

Every field is read from the repositories themselves. Nothing here is
hand-entered, because a hand-typed SHA in a release manifest is a lie that
nobody catches until a rollback goes to the wrong commit.

    scripts/release/cut_product_release.py 1.0.0
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEMVER = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

# The release set. Modules that actually ship carry a tag; everything else is
# recorded honestly rather than being dressed up with a version it hasn't earned.
SHIPPING = [
    "mobius-chat", "mobius-rag", "mobius-payor", "mobius-skills",
    "mobius-skills-mcp", "mobius-os", "mobius-story-ui", "mobius-qa",
    "mobius-interact", "mobius-dbt", "mobius-auth", "mobius-answer-cache",
    "mobius-vault", "product-awareness",
    # Added in product-v1.0.1. Each deploys a live Cloud Run service, so
    # product-v1.0.0 pinned a manifest that was not the whole running system.
    # mobius-feedback and specs-platform were carved out of the superproject
    # for this release; mobius-db-agent was miscarried as pre-release while
    # already serving traffic.
    "Mobius-user", "mobius-feedback", "mobius-db-agent", "specs-platform",
]
PRE_RELEASE = [
    "mobius-config", "mobius-contracts", "mobius-design",
    "mobius-document-viewer", "mobius-migrations", "mobius-qa-modules",
    "mobius-rag-api",
]
DEPRECATED = {"mobius-retriever": "superseded by the RAG module's own retrieval path"}


def git(module: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT / module), *args],
        capture_output=True, text=True, check=False,
    ).stdout.strip()


def newest_semver_tag(module: str) -> str | None:
    """Highest semver tag in the module, ignoring legacy junk like 'alpha' or 'v1'."""
    tags = [t for t in git(module, "tag", "--list").splitlines() if SEMVER.match(t)]
    if not tags:
        return None
    return max(tags, key=lambda t: tuple(int(g) for g in SEMVER.match(t).groups()))


def describe(module: str) -> dict:
    version = newest_semver_tag(module)
    entry = {
        "module": module,
        "version": version,
        "branch": git(module, "rev-parse", "--abbrev-ref", "HEAD") or None,
        "commit": git(module, "rev-parse", "HEAD") or None,
        "commit_short": git(module, "rev-parse", "--short", "HEAD") or None,
        "commits_total": int(git(module, "rev-list", "--count", "HEAD") or 0),
        # Uncommitted files are NOT in the release — a tag points at a commit.
        # Recorded so the manifest says what it excluded rather than implying
        # the tag captured the developer's whole working tree.
        "uncommitted_files_excluded": len(
            [l for l in git(module, "status", "--porcelain").splitlines() if l]
        ),
    }
    entry["dirty"] = entry["uncommitted_files_excluded"] > 0
    if version:
        # A tag can point at an older commit than HEAD. Say so rather than
        # implying the manifest pins current HEAD.
        tagged = git(module, "rev-list", "-n", "1", version)
        entry["tagged_commit"] = tagged or None
        entry["tag_is_head"] = tagged == entry["commit"]
        entry["notes"] = f"docs/releases/modules/{module}/{version}.md"
    return entry


def main() -> int:
    if len(sys.argv) != 2 or not re.match(r"^\d+\.\d+\.\d+$", sys.argv[1]):
        print("usage: cut_product_release.py <MAJOR.MINOR.PATCH>", file=sys.stderr)
        return 1
    version = sys.argv[1]

    manifest = {
        "product_version": f"product-v{version}",
        "cut_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "story": f"docs/releases/product-v{version}.md",
        "modules": [describe(m) for m in SHIPPING],
        "pre_release": [describe(m) for m in PRE_RELEASE],
        "deprecated": [{"module": m, "reason": r} for m, r in DEPRECATED.items()],
    }

    untagged = [m["module"] for m in manifest["modules"] if not m["version"]]
    dirty = [m["module"] for m in manifest["modules"] if m["dirty"]]
    stale = [m["module"] for m in manifest["modules"] if m.get("tag_is_head") is False]

    out = ROOT / "docs" / "releases" / f"product-v{version}.lock.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"✓ {out.relative_to(ROOT)}")
    print(f"  {len(manifest['modules']) - len(untagged)}/{len(SHIPPING)} shipping modules tagged")
    for label, items in (("UNTAGGED", untagged), ("DIRTY TREE", dirty), ("TAG BEHIND HEAD", stale)):
        if items:
            print(f"  ⚠ {label}: {', '.join(items)}")
    return 1 if untagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
