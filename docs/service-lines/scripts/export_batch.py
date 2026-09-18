"""Emit the whole outstanding sourcing backlog as one deep-research batch.

Deep Research asked for the playbook as a batch rather than a question at a time
(Ananth: "not one question from service line or payor facts, but their entire
playbook that we source"). The four fields open_many() requires already exist in
run_sourcing.py and are used for every request this seat has ever opened, so this
REUSES them rather than authoring a second set:

    subject_id         line_key/requirement_type[/code][/qualifier]#id
    question           ASK[rtype], jurisdiction and governing rule folded in
    evaluator_prompt   EVAL — this store's standard, not a generic one
    extraction_schema  SLOTS[rtype] — the typed slots completeness is measured on

Authoring a fresh evaluator for the batch would have made the 64 judged by a
different standard than the 89 already sourced, and "2 of 3 complete" would not
be comparable across them.
"""
import json
import sys

sys.path.insert(0, "/Users/ananth/Mobius/docs/service-lines/scripts")
from run_sourcing import ASK, EVAL, JURISDICTION, SLOTS, db, governing, targets  # noqa: E402


def build(only_unsourced=True):
    conn, cur = db()
    cur.execute("select key, name from service_line.line order by key")
    lines = {r["key"]: r["name"] for r in cur.fetchall()}
    specs, skipped = [], []
    for line_key, name in lines.items():
        reqs = targets(cur, line_key, only_unsourced=only_unsourced)
        if not reqs:
            continue
        gov = governing(cur, line_key)
        for r in reqs:
            rtype = r["requirement_type"]
            # A line whose governing rule we cannot resolve is NOT sent. The whole
            # point of emitting governing_resolved before asking (contract 6.2) is
            # that `silent` is only decidable when we know the document is held and
            # readable. Batched, that check would otherwise be skipped 64 times.
            if not gov["resolvable"]:
                skipped.append({"subject_id": f"{line_key}/{rtype}#{r['id']}",
                                "why": f"governing rule unresolvable: {gov['why']}"})
                continue
            subject = name + (f" (code {r['code']})" if r["code"] else "")
            specs.append({
                "subject_id": (f"{line_key}/{rtype}"
                               + (f"/{r['code']}" if r["code"] else "")
                               + (f"/{r['qualifier']}" if r["qualifier"] else "")
                               + f"#{r['id']}"),
                "question": (f"For {JURISDICTION}: " + ASK[rtype].format(subject=subject)
                             + (f" The governing rule is {gov['rule_ref']}."
                                if gov["rule_ref"] else "")
                             + " Quote the governing policy text and name the source document."),
                "evaluator_prompt": EVAL,
                "extraction_schema": SLOTS[rtype],
                "expects": list(SLOTS[rtype]),
                "jurisdiction": JURISDICTION,
                "authority": "standard",
                "rule_ref": gov["rule_ref"],
                "governing_document_id": gov.get("document_id"),
                "governing_chunks": gov.get("chunks"),
            })
    return specs, skipped


if __name__ == "__main__":
    specs, skipped = build()
    out = "/Users/ananth/Mobius/docs/service-lines/sourcing-batch.json"
    json.dump(specs, open(out, "w"), indent=1)
    from collections import Counter
    print(f"{len(specs)} specs -> {out}")
    # split("/")[1] still carries the "#id" suffix — the id is appended to the LAST
    # segment, so a naive split reports 51 distinct "types". Strip it.
    rtype = lambda sid: sid.split("/")[1].split("#")[0]
    for k, v in sorted(Counter(rtype(s["subject_id"]) for s in specs).items()):
        print(f"   {k:<24} {v}")
    print(f"\nSKIPPED — governing rule unresolvable: {len(skipped)}")
    for k, v in sorted(Counter(s["subject_id"].split("/")[0] for s in skipped).items()):
        print(f"   {k:<24} {v}")
