#!/usr/bin/env python3
"""Split the product feature list into entity-resolvable surfaces and doc topics.

WHY THIS EXISTS. `gen_product_coverage.py` emits 32 "features", and the Lexicon
seat seeded a j:product entity axis from them. Several are ordinary English or
core RCM vocabulary, so they fire as exact entities on queries that have nothing
to do with the page: "which payor covers H0031" hits the Payor page, "what is the
auth requirement" hits the Auth page when the user means prior-AUTHORIZATION.

The root cause is mine and it is upstream of the lexicon: the coverage export is
keyed on DOC MODULES, and I labelled the column "feature". A doc module is a
thing we wrote a page about; a product surface is a thing a user would name in a
question. Those sets overlap but are not the same, and About / Architecture /
Infra / Releases are only ever the former.

THE TEST, applied per row rather than by heuristic:
  Does the bare token also carry meaning in (a) ordinary English as used in a
  question, or (b) the product's own RCM/healthcare domain vocabulary?
    yes -> it must not be a bare entity. Either it is not a surface at all
           (DROP), or it is a real surface whose bare word collides (ALIAS).
    no  -> KEEP as an entity.

A length or dictionary heuristic is explicitly rejected: it would silently
capture a future one-word feature that SHOULD resolve ("Vault" is one word and
belongs in KEEP). The decision is enumerated so it is reviewable and reversible.
"""
from __future__ import annotations
import json, pathlib, datetime, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
COV = ROOT / "docs" / "coverage" / "product_docs.json"
OUT = ROOT / "docs" / "coverage" / "product_taxonomy.json"

# KEEP -- a user would name this, and the token is not ordinary English or RCM
# vocabulary. These stay entity-resolvable in j:product.
KEEP = {
    "Vault": "distinctive in this product; the query that started this thread",
    "RAG": "acronym, no ordinary-English sense in a user question",
    "Story UI": "multi-word, product-specific",
    "Task Manager": "multi-word, names a surface a user opens",
    "Org Intelligence": "multi-word, product-specific",
    "PHI Classifier": "multi-word; PHI is domain vocabulary but the pair is not",
    "Answer Cache": "multi-word, product-specific",
    "Doc Reader": "multi-word, names a surface",
    "Web Scraper": "multi-word, names a surface",
    "Document Viewer": "multi-word, names a surface",
    "Response Cards": "multi-word, names a surface",
    "Product Awareness": "multi-word; internal-leaning but unambiguous",
    "Lexicon": "single word, but no RCM sense and no ordinary-question sense",
}

# ALIAS -- a real product surface whose bare token collides. Resolvable only by
# the multi-word alias; the bare word must never fire.
ALIAS = {
    "Payor": ("payor module", "'payor' is core RCM vocabulary -- 'which payor covers H0031' must NOT hit a help page"),
    "Appeals": ("appeals module", "'appeal' is the central workflow verb; 'how do I appeal CARC 22' wants tools, not docs"),
    "Credentialing": ("credentialing module", "'credentialing status' is a domain query the credentialing TOOLS answer"),
    "Extension": ("browser extension", "'extension' is RCM vocabulary -- a filing-deadline extension"),
    "Chat": ("chat module", "'in this chat' / 'chat history' are ordinary phrasings; high collision rate"),
    "Feedback": ("feedback widget", "'feedback from the payor' is an ordinary domain phrase"),
    "Interact": ("interact module", "ordinary English verb"),
    "Vibe": ("vibe module", "ordinary English noun"),
    "HIPAA": ("hipaa page", "users ask about HIPAA the regulation far more often than the page"),
}

# DROP -- doc or meta topics, not product surfaces. They remain doc pages and
# keep their coverage rows; they simply stop being entity-resolvable.
DROP = {
    "About": "doc-meta page; 'about' appears in a large share of all questions",
    "Architecture": "internal doc topic",
    "Infra": "internal doc topic",
    "Releases": "internal doc topic",
    "Strategy": "internal doc topic; also ordinary English",
    "Specs": "internal doc topic; also ordinary English",
    "Eval": "internal doc topic; 'evaluation' is domain vocabulary",
    "Skills": "internal concept; ordinary English",
    "Auth": "MOST DANGEROUS collision -- 'auth' means prior-authorization throughout RCM",
    "User": "internal service name; 'user' appears in ordinary phrasing constantly",
}


def main() -> int:
    cov = json.loads(COV.read_text())
    values = [r["value"] for r in cov["rows"]]
    decided = set(KEEP) | set(ALIAS) | set(DROP)
    missing = [v for v in values if v not in decided]
    extra = [v for v in decided if v not in values]
    if missing or extra:
        # Fail loudly rather than emit a partial taxonomy: an unclassified
        # feature would silently inherit whatever the lexicon already has.
        print(f"REFUSING: unclassified={missing} not-in-coverage={extra}", file=sys.stderr)
        return 1

    rows = []
    for v in sorted(values):
        if v in KEEP:
            rows.append({"value": v, "decision": "keep", "entity_resolvable": True,
                         "slug": v.lower().replace(" ", "_"), "why": KEEP[v]})
        elif v in ALIAS:
            alias, why = ALIAS[v]
            rows.append({"value": v, "decision": "alias", "entity_resolvable": True,
                         "slug": alias.replace(" ", "_"), "alias": alias,
                         "bare_token_must_not_fire": v.lower(), "why": why})
        else:
            rows.append({"value": v, "decision": "drop", "entity_resolvable": False,
                         "why": DROP[v]})

    payload = {
        "source_key": "product_taxonomy",
        "decided_by": "mobius-c2 (platform / product-awareness seat)",
        "decided_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "rev": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True).stdout.strip(),
        "test_applied": ("does the bare token also carry meaning in ordinary English as used in a "
                         "question, or in RCM/healthcare domain vocabulary? yes -> drop or alias"),
        "caveats": [
            "the coverage export is keyed on DOC MODULES; 'feature' was my mislabel and is the root cause",
            "10 of 32 are dropped as doc topics -- the export is not a user-facing feature vocabulary",
            "supersede when the PA seat produces its own taxonomy",
        ],
        "rows": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    counts = {}
    for r in rows:
        counts[r["decision"]] = counts.get(r["decision"], 0) + 1
    print(f"-> {OUT.relative_to(ROOT)}  {len(rows)} rows  {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
