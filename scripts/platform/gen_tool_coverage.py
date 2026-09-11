#!/usr/bin/env python3
"""Tool-coverage export for the ONE product-domain tool this seat owns.

Tool Selection blocked four tools on owner-declared coverage and addressed all
four here. Only one is ours. `product_feedback` forwards to mobius-feedback
(docs/feedback-agent-spec.md), `vibe` forwards to mobius-skills/vibe, and
`document_upload_skill` delegates to mobius_skills_core -- they sit in the
manifest's `product` DOMAIN, which is a taxonomy bucket, not an ownership
assignment. Declaring their coverage would be certifying a store we do not own,
which the adapter's own docstring rules out. They are named, with owners, in
`unowned_tools_referred` so the refusal is legible rather than a silence.

Coverage is derived from product_docs.json, so it moves when the corpus moves.
provenance is `declared:` not `measured:` -- a row says a page is INDEXED, not
that a retrieval against it succeeded. Those differ and only the second is a
promise about answers.
"""
from __future__ import annotations
import json, pathlib, datetime, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
COV = ROOT / "docs" / "coverage" / "product_docs.json"
OUT = ROOT / "docs" / "coverage" / "tool_coverage_product.json"

# Axes product_help_search has no business answering. One exclusion with a
# reason beats a hundred `absent` rows, and it is the fix for the tool ranking
# #2 on "what is the auth requirement for bh therapy".
# kind: not_applicable = this axis does not govern our predicate, do NOT demote.
#       not_implemented  = the axis IS material to our predicate and we hold
#                          nothing, so DO demote.
# All four are not_applicable. The predicate is "how a documented Mobius product
# surface works"; none of these axes governs that, so a question mentioning one
# is not a question we are wrongly failing to answer -- it is somebody else's
# question. See the payor note for the one case that argues otherwise and why it
# is a COVERAGE gap rather than an axis claim.
DOES_NOT_SERVE = [
    ("payor", "not_applicable",
     "product docs describe Mobius surfaces; they say nothing about payer policy, coverage "
     "rules or prior authorisation. 'auth' in a user question means prior-authorisation far "
     "more often than the Auth doc page. ONE CASE ARGUES THE OTHER WAY and is deliberately "
     "NOT handled here: 'does Mobius support Sunshine Health?' is a product-capability "
     "question keyed on a payor, a user WOULD reasonably expect us to answer it, and we hold "
     "nothing. That is a missing PAGE, not a claim about the payor axis -- it belongs as an "
     "absent coverage row under `feature`, and marking the whole axis not_implemented to "
     "capture it would demote us on every payer-policy question, which is the over-gating "
     "this field was split to stop."),
    ("service_line", "not_applicable",
     "no clinical or billing service-line facts in the product corpus; a service-line "
     "question is not a question about how a Mobius surface works"),
    ("carc", "not_applicable",
     "denial codes are the appeals tools' question, not the docs'"),
    ("provider", "not_applicable",
     "no roster, NPI or credentialing facts in the product corpus"),
]

UNOWNED = [
    ("product_feedback", "feedback agent (mobius-feedback)", "app/skills/builtin/product_feedback.py:1-12"),
    ("vibe", "skills seat (mobius-skills/vibe)", "app/skills/builtin/vibe.py:1-10"),
    ("document_upload_skill", "skills-core / chat", "app/skills/builtin/document_uploads.py:1-10"),
]


def main() -> int:
    cov = json.loads(COV.read_text())
    rows = []
    for r in cov["rows"]:
        n = r.get("rows_present", 0)
        if r["status"] == "covered":
            rows.append({"axis": "feature", "value": r["value"], "status": "covered",
                         "rows_present": n, "rows_sourced": n})
        elif r["status"] == "absent":
            rows.append({"axis": "feature", "value": r["value"], "status": "absent",
                         "rows_present": 0, "rows_sourced": 0,
                         "note": "shipped surface with zero pages in the corpus -- "
                                 "nameable, not answerable"})
        else:
            rows.append({"axis": "feature", "value": r["value"], "status": "absent",
                         "rows_present": n, "rows_sourced": n,
                         "note": "documented but no deployed service resolved; "
                                 "treat as unverified rather than served"})

    payload = {
        "source_key": "product_docs",
        "exported_by": "product-awareness (written by mobius-c2, platform seat)",
        "exported_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "exporter_rev": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                       capture_output=True, text=True).stdout.strip(),
        "provenance": "declared: derived from corpus/registry.json crossed with deployed services",
        "contract_version": "v1",
        "axis_semantics": ("the `feature` axis carries DOC MODULES crossed with deployed "
                           "services, not a user-facing feature vocabulary -- see taxonomy_ref "
                           "for which values may be entity-resolved"),
        "taxonomy_ref": "docs/coverage/product_taxonomy.json",
        "caveats": [
            "covered means a page EXISTS and is indexed -- not that a retrieval against it "
            "answers well. asserts-vs-covered still needs a page-by-page read.",
            "15 of 32 shipped surfaces have zero pages; `absent` is the honest majority here",
            "not the PA seat's own export; supersede when that seat produces one",
        ],
        "reading_notes": {
            "unowned_tools_referred": (
                "Tool Selection addressed four product-domain tools here; only "
                "product_help_search is ours. The others sit in the `product` DOMAIN, which "
                "is a taxonomy bucket rather than an ownership assignment, and declaring "
                "their coverage would certify a store this seat does not own. Owners: " +
                "; ".join(f"{t} -> {o} ({e})" for t, o, e in UNOWNED)
            ),
        },
        "tools": [{
            "tool": "product_help_search",
            "predicate": "how a documented Mobius product surface works",
            "values": rows,
            "axes_served": ["feature"],
            "axes_not_served": [{"axis": a, "kind": k, "why": w} for a, k, w in DOES_NOT_SERVE],
        }],
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    c = {}
    for r in rows:
        c[r["status"]] = c.get(r["status"], 0) + 1
    print(f"-> {OUT.relative_to(ROOT)}  1 tool  {len(rows)} coverage rows  {c}  "
          f"{len(DOES_NOT_SERVE)} exclusions  {len(UNOWNED)} referred elsewhere")
    return 0


if __name__ == "__main__":
    sys.exit(main())
