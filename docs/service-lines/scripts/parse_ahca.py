"""Parse AHCA fee schedules from the RAG corpus into service-line rows.

Grain: (procedure_code, modifier) — proven by H2000/HP vs H2000/HO carrying
different fees and different rendering practitioners in the same document.
"""
import json
import re
import sys

import psycopg2

DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open("mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")

CODE = re.compile(r"^([A-Z]\d{4})\s*$")
MOD = re.compile(r"^(H[A-Z]|T[A-Z]|U\d|[A-Z]{2})\s*$")
FEE = re.compile(r"^\$\s?([\d,]+\.\d{2})\s*(.*)$")
RULE = re.compile(r"^(59G-[\d.]+):\s*(.+?)\s*$")


def fetch_pages(cur, like):
    cur.execute("select id, filename from documents where filename ilike %s", (like,))
    hit = cur.fetchone()
    if not hit:
        return None, None, []
    cur.execute(
        "select page_number, coalesce(text_markdown, text) from document_pages "
        "where document_id=%s order by page_number", (hit[0],))
    return hit[0], hit[1], cur.fetchall()


def parse(pages, source):
    """Walk each page top-down. A code line opens a row; the description is the
    text above it, the fee/limits the text below, until the next code line."""
    rows = []
    for pno, text in pages:
        lines = [l.rstrip() for l in (text or "").split("\n")]
        page_rules = [RULE.match(l).groups() for l in lines if RULE.match(l)]

        lines = [l for l in lines if l.strip()]
        idx = [i for i, l in enumerate(lines) if CODE.match(l.strip())]
        for n, i in enumerate(idx):
            code = CODE.match(lines[i].strip()).group(1)

            # description sits directly above the code as a wrapped noun phrase.
            # Limit sentences end in '.', descriptions do not — walk back while
            # the line still looks like a fragment.
            head = []
            for k in range(i - 1, max(idx[n - 1] if n else -1, -1), -1):
                t = lines[k].strip()
                if t.endswith(".") or t.startswith("$") or t in ("Y",) or MOD.match(t):
                    break
                if t in ("Reimbursement and Service Limitations", "Maximum Fee", "medicine *",
                         "Tele-", "Mod", "Code", "Procedure", "Description of Service"):
                    break
                head.insert(0, t)
                if len(head) == 3:
                    break
            desc = re.sub(r"\s+", " ", " ".join(head)).strip(" .")

            end = idx[n + 1] if n + 1 < len(idx) else len(lines)
            tail = [x.strip() for x in lines[i + 1:end] if x.strip()]

            mod, tele, fee, unit = None, False, None, None
            limits = []
            for j, t in enumerate(tail):
                if fee is None and MOD.match(t) and mod is None and j < 3:
                    mod = t
                    continue
                if fee is None and t == "Y" and j < 4:
                    tele = True
                    continue
                m = FEE.match(t)
                if m and fee is None:
                    fee = float(m.group(1).replace(",", ""))
                    # the unit wraps: "$250.63 per" / "evaluation"
                    unit = m.group(2).strip()
                    nxt = tail[j + 1].strip() if j + 1 < len(tail) else ""
                    if unit.endswith("per") and nxt and not nxt.endswith("."):
                        unit = f"{unit} {nxt}"
                    unit = re.split(r"\s+(?=Medicaid|There is)", unit)[0]
                    unit = re.sub(r"\s+", " ", unit).strip()
                    continue
                if fee is not None:
                    if RULE.match(t) or t.startswith("*") or t.startswith("Page "):
                        continue
                    limits.append(t)
                elif unit is None and re.match(r"^per\b|^quarter|^weekly|^daily", t, re.I):
                    unit = t

            if fee is None:
                continue

            blob = " ".join(limits)
            blob = re.sub(r"\s+", " ", blob).strip()
            excl = [s.strip() for s in re.split(r"(?<=\.)\s+", blob)
                    if "not reimbursable" in s.lower() or "will not reimburse" in s.lower()]
            lim = [s.strip() for s in re.split(r"(?<=\.)\s+", blob)
                   if "maximum" in s.lower() or "reimburses" in s.lower()]

            rows.append({
                "code": code,
                "modifier": mod,
                "description": desc,
                "max_fee": fee,
                "fee_unit": unit,
                "telemedicine": tele,
                "limits": lim,
                "exclusions": excl,
                "page": pno,
                "page_cites_rules": [{"rule": r, "title": t} for r, t in page_rules],
                "source": source,
            })
    return rows


def main():
    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    out = {}
    for key, like in [("cbh_2025", "%Community Behavoir Health%"),
                      ("tcm_children_2022", "%TCM_for_Children_At-Risk%")]:
        did, fn, pages = fetch_pages(cur, like)
        if not did:
            print(f"  {key}: NOT IN CORPUS", file=sys.stderr)
            continue
        rows = parse(pages, fn)
        out[key] = {"document_id": did, "filename": fn, "pages": len(pages), "rows": rows}
        print(f"  {key}: {len(rows)} rows from {len(pages)} pages — {fn}", file=sys.stderr)

    dest = ("/private/tmp/claude-502/-Users-ananth-Mobius/"
            "6999871c-ecbf-40d0-b26c-92174f91c392/scratchpad/ahca/parsed.json")
    json.dump(out, open(dest, "w"), indent=2)
    print(f"\nwrote {dest}", file=sys.stderr)


if __name__ == "__main__":
    main()
