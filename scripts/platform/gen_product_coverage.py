#!/usr/bin/env python3
"""Product-domain coverage export for the tool-selection catalogue.

Answers one question per feature: can we ANSWER about it, or only NAME it?

Two inputs, both artefacts rather than opinion:
  * product-awareness/corpus/registry.json -- what is documented (17 docs)
  * deployed Cloud Run services            -- what is shipped

The mapping between them is declared here, not inferred, because doc `module`
names and service names disagree ("credentialing" vs
"mobius-provider-roster-credentialing"). A feature whose mapping is unknown is
emitted as `unknown`, never guessed -- an unverified row in a coverage export
is worse than a missing one, since the consumer cannot tell them apart.

Statuses follow the Payor Fact Store contract: covered / template / asserts /
absent / not_applicable, plus `unknown` for what this exporter cannot decide.
`asserts` is NOT emitted: distinguishing "documents shipped behaviour" from
"documents an intention" requires reading each page against the product, which
is a judgement this script cannot make. Emitting `covered` for those would
overstate; the field is left for a human pass and flagged in `note`.
"""
from __future__ import annotations
import json, subprocess, datetime, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
REG = ROOT / "product-awareness" / "corpus" / "registry.json"
OUT = ROOT / "docs" / "coverage" / "product_docs.json"

# doc module -> the shipped thing it documents. Declared, hand-checked.
MODULE_TO_FEATURE = {
    "chat": "Chat", "rag": "RAG", "auth": "Auth", "os": "Extension",
    "credentialing": "Credentialing", "lexicon": "Lexicon", "eval": "Eval",
    "hipaa": "HIPAA", "skills": "Skills", "infra": "Infra",
    "releases": "Releases", "document-viewer": "Document Viewer",
    "response-cards": "Response Cards", "architecture": "Architecture",
    "architecture-drilldown": "Architecture", "about": "About",
    "strategy": "Strategy",
}

# Shipped features the product surfaces to a user, and the service or code that
# backs each. Only entries a user could plausibly ask "where is X" about.
FEATURES = {
    "Chat": "mobius-chat", "RAG": "mobius-rag", "Appeals": "mobius-appeals-prototype",
    "Payor": "mobius-payor", "Credentialing": "mobius-provider-roster-credentialing",
    "Extension": "mobius-os-backend", "Feedback": "mobius-feedback",
    "Task Manager": "mobius-task-manager", "Interact": "mobius-interact",
    "Story UI": "mobius-story-ui", "Specs": "mobius-specs",
    "Org Intelligence": "mobius-org-intelligence", "PHI Classifier": "mobius-phi-classifier",
    "Vibe": "mobius-vibe", "Answer Cache": "mobius-answer-cache",
    "Doc Reader": "mobius-doc-reader", "Web Scraper": "mobius-web-scraper",
    "Lexicon": "mobius-lexicon-maintenance", "User": "mobius-user",
    "Product Awareness": "mobius-product-awareness",
    # Named in the UI, no service of its own -- backed by chat FE + an
    # undeployed repo. Deliberately present so the gap is visible.
    "Vault": None,
}


def deployed() -> set[str]:
    try:
        out = subprocess.run(
            ["gcloud", "run", "services", "list", "--region", "us-central1",
             "--format=value(metadata.name)"],
            capture_output=True, text=True, timeout=120)
        return {l.strip() for l in out.stdout.splitlines() if l.strip()}
    except Exception:
        return set()


def main() -> int:
    reg = json.loads(REG.read_text())
    documented: dict[str, int] = {}
    for d in reg["docs"]:
        feat = MODULE_TO_FEATURE.get(d.get("module"))
        if feat:
            documented[feat] = documented.get(feat, 0) + 1

    live = deployed()
    rows = []
    # Union, not FEATURES alone. An earlier version of this script iterated
    # FEATURES only, which silently dropped 11 DOCUMENTED features that had no
    # service mapping (Auth, Eval, HIPAA, Skills, Infra, Releases, Document
    # Viewer, Response Cards, Architecture, About, Strategy) -- the export
    # looked complete at 21 rows while omitting the best-covered half of the
    # corpus. Enumerate the full set, then classify.
    universe = dict(FEATURES)
    for feat in documented:
        universe.setdefault(feat, None)
    for feat, svc in sorted(universe.items()):
        n = documented.get(feat, 0)
        is_live = bool(svc) and svc in live
        if n and is_live:
            status, note = "covered", "documented and deployed; asserts-vs-covered needs a human read"
        elif n and not is_live:
            status, note = "unknown", f"documented but no deployed service resolved (mapped: {svc!r})"
        elif is_live:
            status, note = "absent", "deployed, zero docs in the corpus -- nameable, not answerable"
        elif n:
            status, note = "unknown", "documented; no service mapping declared -- may be a doc topic, not a feature"
        else:
            status, note = "unknown", "no doc and no deployed service resolved; needs an owner ruling"
        rows.append({"axis": "feature", "value": feat, "status": status,
                     "rows_present": n, "rows_sourced": n, "note": note})

    # Modules documented that no feature claims -- the other direction.
    claimed = set(MODULE_TO_FEATURE.values())
    for d in reg["docs"]:
        m = d.get("module")
        if m and m not in MODULE_TO_FEATURE:
            rows.append({"axis": "feature", "value": m, "status": "unknown",
                         "rows_present": 1, "rows_sourced": 1,
                         "note": "doc module with no declared feature mapping"})

    payload = {
        "source_key": "product_docs",
        "exported_by": "mobius-c2 (platform seat) on behalf of product-awareness",
        "exported_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "exporter_rev": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                       capture_output=True, text=True).stdout.strip(),
        "caveats": [
            "asserts is never emitted -- it needs a page-by-page read against shipped behaviour",
            "registry.json updated_at 2026-09-07; corpus freshness is not verified here",
            "not the PA seat's own export; supersede when that seat produces one",
        ],
        "rows": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"-> {OUT.relative_to(ROOT)}  {len(rows)} rows  {counts}")
    for r in rows:
        if r["status"] == "absent":
            print(f"   absent: {r['value']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
