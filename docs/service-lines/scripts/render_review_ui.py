"""The Service Lines review surface — built for association users, not engineers.

Ananth, 2026-09-07: "way too technical, not adherent with Mobius UX standards
(collapsible left rail with search etc).. this is not minimalist design.. this
will be a surface used by association users .. so we need to make it user
friendly with AI language off."

The previous page was an engineering console. What it broke, from BRANDING.md:

  §5  no 48px topbar, no Mobius mark, sidebar not collapsible, no search,
      9px card radius instead of the 12px token
  §7  internal names on screen everywhere — bh_assessment, line_key,
      binding_role, provenance, caveats, envelope, "parsed/interpreted/asserted"
  §8  invented a local token set (--ground/--surface/--ink) instead of
      importing --mobius-*

This is the structure pass. Every word a user reads is plain English; every
colour, radius and space is a token.

LANGUAGE MAP — the left column never appears on screen:

  parsed          "From the fee schedule"
  interpreted     "Read from the policy"
  asserted        "No source yet"
  human           "Entered by staff"
  unreviewed      "Not checked"
  approve/reject  "Confirm" / "Flag"
  line_key        never shown. The service NAME is the identifier.

Writes docs/product-docs/service-lines-review.html.
"""
import json
import os
import re
from pathlib import Path

ROOT = Path("/Users/ananth/Mobius")
CATALOG = ROOT / "docs/service-lines/fl-medicaid-bh.catalog.json"
TOKENS = ROOT / "mobius-design/tokens.css"
OUT = ROOT / "docs/product-docs/service-lines-review.html"

# Where the Source button posts. A published page cannot reach a laptop, so when this
# is unreachable the panel says what to run instead of failing silently — the surface
# must never imply a run started when nothing did.
API = os.environ.get("MOBIUS_PAYOR_URL", "https://mobius-payor-ortabkknqa-uc.a.run.app")

LOGO = (
    '<svg viewBox="0 0 100 100" width="24" height="24" aria-hidden="true">'
    '<defs><linearGradient id="mg" x1="0%" y1="50%" x2="100%" y2="50%">'
    '<stop offset="0%" stop-color="var(--mobius-logo-stroke-start)"/>'
    '<stop offset="22%" stop-color="#6e6e6e"/>'
    '<stop offset="50%" stop-color="#b8b8b8"/>'
    '<stop offset="78%" stop-color="#6e6e6e"/>'
    '<stop offset="100%" stop-color="var(--mobius-logo-stroke-end)"/></linearGradient></defs>'
    '<path d="M 50 50 C 50 22 22 22 22 50 C 22 78 50 78 50 50 C 50 78 78 78 78 50 '
    'C 78 22 50 22 50 50" stroke="url(#mg)" stroke-width="4.5" fill="none" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def build():
    cat = json.loads(CATALOG.read_text())
    tokens = TOKENS.read_text()

    # Only what the surface needs, in the shape it renders. Keys stay out of the
    # payload where they are not needed so they cannot leak into the DOM.
    def human(t):
        """Enum and extraction artefacts are not English. The verbatim form is
        kept for the evidence panel; this is what a person reads."""
        t = (t or "").replace("state_fiscal_year", "state fiscal year")
        t = t.replace("_", " ")
        # The fee schedule's unit column bled into our extraction, so statements
        # begin "rate Medicaid reimburses" / "event Medicaid reimburses".
        return re.sub(r"^(rate|event|quarter hour|quarter|assessment|evaluation|review)\s+"
                      r"(?=Medicaid|There)", "", t).strip()

    def say_limit(x):
        """Say the cap in English, using the code card above for context.

        Concatenating the stored phrase gave "1 evaluations (one in-depth
        assessment) per state_fiscal_year per recipient" — a plural on 1, a
        redundant gloss and a raw enum. Naive pluralisation is not the fix
        either: three of the fourteen unit definitions break it ("one
        psychiatric review of records" -> "recordss").

        limit_type is already a regular plural, so it singularises safely, and
        the specific thing being counted is named by the code card directly
        above. The exact unit definition stays in the evidence panel.
        """
        if x.get("unlimited"):
            return "No limit stated in the source."
        n = x.get("amount")
        n = int(n) if n is not None and float(n).is_integer() else n
        noun = x.get("limit_type") or "units"
        if n == 1 and noun.endswith("s"):
            noun = noun[:-1]
        unit = (x.get("unit_definition") or "")
        head = f"{n:,} {noun}" if isinstance(n, int) else f"{n} {noun}"
        if "minute" in unit.lower():          # a timed increment needs its length
            head += " of 15 minutes"
        bits = [head]
        if x.get("period"):
            bits.append("per " + str(x["period"]).replace("_", " "))
        tail = " ".join(bits)
        if x.get("per_whom"):
            tail += ", per " + str(x["per_whom"]).replace("_", " ")
        return tail

    lines = []
    for l in cat["service_lines"]:
        rc = l.get("review_counts") or {}
        bc = l.get("benefit_counts") or {}

        # ── one entry per billable code, carrying everything about that code ──
        # The old page split a single code across three tables — its definition
        # in one, its cap in another, its review row in a third. Nobody reads a
        # code that way.
        def key(c, m):
            return (c or "") + "|" + (m or "")

        codes = {}
        for c in l.get("codes", []):
            codes[key(c["code"], c.get("modifier"))] = {
                "code": c["code"], "mod": c.get("modifier") or "",
                "what": c.get("definition") or "",
                "rate": c.get("standard_rate"),
                "unit": (c.get("standard_rate_unit") or "").replace("per ", ""),
                "tele": bool(c.get("telemedicine")),
                "limits": [], "items": [],
            }
        for x in l.get("benefit_limits", []):
            k = key(x["code"], x.get("modifier"))
            if k in codes:
                codes[k]["limits"].append(say_limit(x))

        # DEFECT 1 — the same sentence rendered three times on one code, because
        # the coverage answer and the limit were sourced from one fee-schedule
        # sentence and the code definition sat beside them unlabelled. One row
        # per distinct wording now, carrying every fact it establishes.
        LABEL = {"benefit": "Covered", "benefit_limit": "Limit",
                 "line_code": "What the code means",
                 "standard_requirement": "Requirement"}

        def fold(rows):
            out, seen = [], {}
            for r in rows:
                t = r["what"]
                if t in seen:
                    if r["label"] not in seen[t]["labels"]:
                        seen[t]["labels"].append(r["label"])
                    if r["state"] == "unreviewed":
                        seen[t]["state"] = "unreviewed"
                    continue
                r["labels"] = [r["label"]]
                seen[t] = r
                out.append(r)
            return out

        common, groupings = [], []
        for r in l.get("review", []):
            item = {
                "what": human(r.get("value") or "")[:220],
                "verbatim": (r.get("value") or "")[:400],
                "origin": r.get("origin"), "source": r.get("source"),
                "state": r.get("state"),
                "label": LABEL.get(r.get("kind"), r.get("kind") or ""),
                # DEFECT 3 — four APR-DRG severities rendered as four identical
                # rows. Severity is the only thing telling them apart.
                "sev": r.get("modifier") if r.get("role") == "grouped_to" else "",
            }
            role = r.get("role")
            k = key(r.get("code"), r.get("modifier"))
            if role == "rendered_as" and k in codes:
                codes[k]["items"].append(item)
            elif role in ("classified_by", "grouped_to"):
                # DEFECT 2 — these are diagnosis and DRG bindings. They answer
                # "what places this encounter", not "what may I bill", and 285
                # of them were drowning the service-wide section.
                item["what"] = (item["what"] + (" · severity " + item["sev"]
                                                if item["sev"] else ""))
                item["label"] = ("Diagnosis" if role == "classified_by"
                                 else "Hospital grouping")
                groupings.append(item)
            else:
                common.append(item)

        for c in codes.values():
            c["items"] = fold(c["items"])
        common = fold(common)
        groupings = fold(groupings)

        lines.append({
            "id": l["key"],                       # DOM handle only, never displayed
            "name": l["name"],
            "rule": l.get("rule"),
            "ready": bool(codes or bc.get("covered")),
            "codes": list(codes.values()),
            "common": common,
            "search": " ".join([l["name"]] + [c["code"] for c in l.get("codes", [])]).lower(),
            "covered": bc.get("covered", 0),
            "sources": sorted({r["source"] for r in l.get("review", []) if r.get("source")}),
            "grain": l.get("grain"), "authority": l.get("authority"),
            "modules": [{"name": m["name"], "state": (l.get("status") or {}).get(m["key"], ["todo",""])[0],
                         "why": (l.get("status") or {}).get(m["key"], ["todo",""])[1]}
                        for m in cat["modules"]],
            "attempts": l.get("sourcing_attempts", []),
            "machine": l.get("state_machine", []),
            "runs": l.get("runs", []),
            "terms": (l.get("lexicon_d_counts") or {}),
            "chunks": (l.get("j_service_line") or {}).get("retrievable_chunks", 0),
            "groupings": groupings,
            "toCheck": sum(1 for x in ([i for c in codes.values() for i in c["items"]]
                                       + common + groupings)
                           if x["state"] == "unreviewed" and x["origin"] != "asserted"),
            "toSource": sum(1 for x in ([i for c in codes.values() for i in c["items"]]
                                        + common + groupings)
                            if x["origin"] == "asserted"),
            "checked": (rc.get("total", 0) - rc.get("unreviewed", 0)),
        })

    data = json.dumps({"lines": lines}, separators=(",", ":"))
    OUT.write_text(PAGE.replace("__TOKENS__", tokens).replace("__LOGO__", LOGO)
                       .replace("__DATA__", data).replace("__API__", API))
    ready = sum(1 for x in lines if x["ready"])
    print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")
    print(f"  {len(lines)} services · {ready} ready · {len(lines)-ready} awaiting sources")
    print(f"  {sum(x['toCheck'] for x in lines)} items to check")


PAGE = r"""<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Service Lines</title>
<style>
__TOKENS__

*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--mobius-bg-primary);color:var(--mobius-text-primary);
  font-family:var(--mobius-font-sans);font-size:var(--mobius-text-sm);line-height:1.55;
  -webkit-font-smoothing:antialiased}
button{font:inherit;color:inherit}

/* ── frame: 48px topbar, 260px sidebar collapsing to 48px (BRANDING §5) ── */
.app{display:grid;grid-template-rows:48px 1fr;height:100vh}
.top{display:flex;align-items:center;gap:var(--mobius-space-base);
  padding:0 var(--mobius-space-md);background:var(--mobius-bg-card);
  border-bottom:1px solid var(--mobius-border)}
.mark{display:flex;align-items:center;gap:var(--mobius-space-sm);font-weight:500}
.mark{font-weight:600;letter-spacing:0}
.top .spacer{flex:1}

.body{display:grid;grid-template-columns:260px 1fr;min-height:0;
  transition:grid-template-columns 180ms ease-out}
.body.rail{grid-template-columns:48px 1fr}
@media (prefers-reduced-motion:reduce){.body{transition:none}}

.side{background:var(--mobius-bg-card);border-right:1px solid var(--mobius-border);
  display:flex;flex-direction:column;min-height:0;overflow:hidden}
.sidehead{display:flex;align-items:center;gap:var(--mobius-space-sm);
  padding:var(--mobius-space-base);border-bottom:1px solid var(--mobius-border)}
.srch{flex:1;height:32px;border:1px solid var(--mobius-border);
  border-radius:var(--mobius-radius-base);padding:0 var(--mobius-space-base);
  font:inherit;background:var(--mobius-bg-primary);color:var(--mobius-text-primary);min-width:0}
.srch:focus{outline:2px solid var(--mobius-accent);outline-offset:-1px;border-color:transparent}
.srch::placeholder{color:var(--mobius-text-muted)}
/* Chat's control, not a hamburger: a circular button straddling the sidebar's
   right edge, chevron pointing the way it will move. */
.side{position:relative}
.chev{position:absolute;right:0;top:14px;transform:translateX(50%);width:28px;height:28px;
  display:grid;place-items:center;border:1px solid var(--mobius-border);border-radius:50%;
  background:var(--mobius-bg-card);color:var(--mobius-text-muted);cursor:pointer;
  box-shadow:var(--mobius-shadow-sm);z-index:60;
  transition:background 150ms ease-out,color 150ms ease-out}
.chev:hover{background:var(--mobius-bg-hover);color:var(--mobius-text-primary)}
.chev:focus-visible{outline:2px solid var(--mobius-accent);outline-offset:2px}
.chev svg{width:14px;height:14px;transition:transform 200ms ease-out}
.rail .chev svg{transform:rotate(180deg)}
.rail .srch,.rail .grp,.rail .nav b,.rail .nav i{display:none}
.rail .sidehead{padding:var(--mobius-space-sm)}
.rail .nav button{justify-content:center;padding:7px 0}

.nav{overflow-y:auto;padding:var(--mobius-space-sm);display:flex;flex-direction:column;
  gap:2px;min-height:0}
.grp{padding:var(--mobius-space-base) var(--mobius-space-sm) var(--mobius-space-xs);
  font-size:var(--mobius-text-xs);letter-spacing:.04em;text-transform:uppercase;
  color:var(--mobius-text-muted)}
.nav button{display:flex;align-items:center;gap:var(--mobius-space-sm);width:100%;
  text-align:left;background:none;border:0;padding:7px var(--mobius-space-sm);
  border-radius:var(--mobius-radius-base);cursor:pointer;color:var(--mobius-text-secondary)}
.nav button:hover{background:var(--mobius-bg-hover)}
.nav button[aria-current=true]{background:color-mix(in srgb,var(--mobius-accent) 10%,transparent);
  color:var(--mobius-accent);font-weight:500}
.nav b{font-weight:inherit;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.nav i{font-style:normal;font-size:var(--mobius-text-xs);color:var(--mobius-text-muted)}
.nav button[aria-current=true] i{color:var(--mobius-accent)}
.dot{width:6px;height:6px;border-radius:var(--mobius-radius-full);flex:none;
  background:var(--mobius-success)}
.dot.wait{background:var(--mobius-border-medium)}
/* Collapsed, the dot becomes the service's initials — nine identical dots told
   a reader nothing. */
.rail .dot{width:24px;height:24px;border-radius:var(--mobius-radius-sm);
  background:var(--mobius-bg-tertiary);display:grid;place-items:center;
  font-size:10px;font-weight:600;color:var(--mobius-text-muted)}
.rail .dot::after{content:attr(data-ini)}
.rail .dot.wait{background:var(--mobius-bg-secondary);
  color:var(--mobius-border-medium)}
.nav i.src{color:var(--mobius-warning)}
.nav i.non{color:var(--mobius-border-medium)}
.lbl{display:inline-block;font-size:var(--mobius-text-xs);font-weight:500;
  color:var(--mobius-text-muted);background:var(--mobius-bg-tertiary);
  border-radius:var(--mobius-radius-sm);padding:1px 6px;margin-right:6px;
  vertical-align:1px}
.item.needs{border-left:2px solid var(--mobius-warning);border-radius:0
  var(--mobius-radius-base) var(--mobius-radius-base) 0}

.main{overflow-y:auto;padding:var(--mobius-space-xl);display:flex;flex-direction:column;
  gap:var(--mobius-space-md);min-width:0}
/* Flex children shrink by default. In a scrolling column that means every card
   is squeezed to fit the viewport instead of overflowing it — which clipped the
   collapsed card titles in half against .card{overflow:hidden}. Cards keep
   their natural height and the column scrolls. */
.main>*{flex:0 0 auto}
h1{margin:0;font-size:var(--mobius-text-xl);font-weight:600;letter-spacing:-.01em}
.sub{color:var(--mobius-text-muted);margin:var(--mobius-space-xs) 0 0}

.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:var(--mobius-space-md)}
.kpi{background:var(--mobius-bg-card);border:1px solid var(--mobius-border);
  border-radius:var(--mobius-radius-md);box-shadow:var(--mobius-shadow-sm);
  padding:var(--mobius-space-md)}
.kpi span{display:block;font-size:var(--mobius-text-xs);text-transform:uppercase;
  letter-spacing:.04em;color:var(--mobius-text-muted)}
.kpi b{display:block;font-size:var(--mobius-text-2xl);font-weight:600;line-height:1.2;
  margin-top:var(--mobius-space-xs)}

.card{background:var(--mobius-bg-card);border:1px solid var(--mobius-border);
  border-radius:var(--mobius-radius-md);box-shadow:var(--mobius-shadow-sm);overflow:hidden}
.card>h2{margin:0;padding:var(--mobius-space-base) var(--mobius-space-md);
  font-size:var(--mobius-text-sm);font-weight:600;
  border-bottom:1px solid var(--mobius-border);display:flex;align-items:center;
  gap:var(--mobius-space-sm);cursor:pointer;user-select:none;width:100%;
  background:none;border-left:0;border-right:0;border-top:0;text-align:left}
.card>h2:hover{background:var(--mobius-bg-hover)}
.card>h2 .ci{width:14px;height:14px;flex:none;color:var(--mobius-text-muted);
  transition:transform 200ms ease-out}
.card.shut>h2{border-bottom:0}
.card.shut>h2 .ci{transform:rotate(-90deg)}
.card.shut>.scroll,.card.shut>.pad,.card.shut>.note,.card.shut>.empty{display:none}
.card>h2 em{margin-left:auto;font-style:normal;font-weight:400;
  color:var(--mobius-text-muted);font-size:var(--mobius-text-xs)}
.pad{padding:var(--mobius-space-md)}
.scroll{overflow-x:auto}
/* A squashed table is unreadable; let it keep its width and scroll inside the
   card instead. The card never forces the page to scroll sideways. */
.scroll table{min-width:520px}
@media (max-width:820px){
  .body{grid-template-columns:48px 1fr}
  .main{padding:var(--mobius-space-md)}
  .kpis{grid-template-columns:repeat(2,1fr)}
}
table{border-collapse:collapse;width:100%;font-size:var(--mobius-text-sm)}
th,td{text-align:left;padding:10px var(--mobius-space-md);
  border-bottom:1px solid var(--mobius-border);vertical-align:top}
th{font-size:var(--mobius-text-xs);text-transform:uppercase;letter-spacing:.04em;
  color:var(--mobius-text-muted);font-weight:500;white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.cd{white-space:nowrap;font-weight:500}
td.cd small{display:block;font-weight:400;color:var(--mobius-text-muted)}

.chip{display:inline-flex;align-items:center;gap:5px;border-radius:var(--mobius-radius-full);
  font-size:var(--mobius-text-xs);font-weight:500;padding:2px var(--mobius-space-sm);
  white-space:nowrap}
.c-ok{background:color-mix(in srgb,var(--mobius-success) 15%,transparent);color:var(--mobius-success)}
.c-warn{background:color-mix(in srgb,var(--mobius-warning) 15%,transparent);color:#8a5a00}
.c-need{background:color-mix(in srgb,var(--mobius-error) 15%,transparent);color:var(--mobius-error)}
.c-mute{background:var(--mobius-bg-tertiary);color:var(--mobius-text-muted)}

.acts{display:flex;gap:var(--mobius-space-xs);white-space:nowrap}
.btn{height:28px;padding:0 var(--mobius-space-base);border-radius:var(--mobius-radius-base);
  border:1px solid var(--mobius-border);background:var(--mobius-bg-card);
  color:var(--mobius-text-secondary);cursor:pointer;font-size:var(--mobius-text-xs)}
.btn:hover{background:var(--mobius-bg-hover)}
.btn.pri{background:var(--mobius-accent);border-color:var(--mobius-accent);
  color:var(--mobius-accent-text)}
.btn.pri:hover{background:var(--mobius-accent-hover)}
.btn:disabled{opacity:.5;cursor:not-allowed}

.empty{display:flex;flex-direction:column;align-items:center;gap:var(--mobius-space-sm);
  padding:var(--mobius-space-xl);text-align:center;color:var(--mobius-text-muted)}
.empty svg{opacity:.3}
.tech{display:grid;grid-template-columns:minmax(120px,180px) 1fr;gap:var(--mobius-space-sm)
  var(--mobius-space-md);margin:0;font-size:var(--mobius-text-sm)}
.tech dt{color:var(--mobius-text-muted)}
.tech dd{margin:0;word-break:break-word}
@media (max-width:640px){.tech{grid-template-columns:1fr;gap:var(--mobius-space-xs)}
  .tech dd{margin-bottom:var(--mobius-space-sm)}}
.th{margin:0 0 var(--mobius-space-sm);font-size:var(--mobius-text-xs);
  text-transform:uppercase;letter-spacing:.04em;color:var(--mobius-text-muted);font-weight:500}
.hint2{color:var(--mobius-text-muted);font-size:var(--mobius-text-xs);margin-top:2px}
.lead{margin:0 0 var(--mobius-space-md);font-size:var(--mobius-text-md);
  color:var(--mobius-text-primary)}
.items{display:flex;flex-direction:column;gap:var(--mobius-space-sm);
  margin-top:var(--mobius-space-md)}
.item{border:1px solid var(--mobius-border);border-radius:var(--mobius-radius-base);
  padding:var(--mobius-space-base)}
.itop{display:flex;align-items:center;gap:var(--mobius-space-sm);flex-wrap:wrap}
.itxt{flex:1;min-width:220px}
.acts{display:flex;gap:var(--mobius-space-xs);margin-left:auto}
.ev{margin-top:var(--mobius-space-sm)}
.ev summary{cursor:pointer;color:var(--mobius-text-muted);font-size:var(--mobius-text-xs);
  list-style:none;display:inline-flex;align-items:center;gap:var(--mobius-space-xs)}
.ev summary::-webkit-details-marker{display:none}
.ev summary::before{content:"›";display:inline-block;transition:transform 150ms ease-out}
.ev[open] summary::before{transform:rotate(90deg)}
.ev summary:hover{color:var(--mobius-text-primary)}
.ev .tech{margin-top:var(--mobius-space-sm);padding:var(--mobius-space-base);
  background:var(--mobius-bg-secondary);border-radius:var(--mobius-radius-base)}
.vb{font-family:var(--mobius-font-mono);font-size:var(--mobius-text-xs);
  color:var(--mobius-text-secondary)}
.note{padding:var(--mobius-space-base) var(--mobius-space-md);
  border-top:1px solid var(--mobius-border);color:var(--mobius-text-muted);
  font-size:var(--mobius-text-xs)}

  /* A run and its steps. Deliberately quiet: this lives inside Technical details,
     which a reviewer opens only when they want to know how an answer was reached. */
  .throw{display:flex;align-items:center;justify-content:space-between;gap:8px}
  .btn-src{font:inherit;font-size:12px;padding:5px 11px;border-radius:8px;
    border:1px solid var(--mobius-border);background:var(--mobius-surface);
    color:var(--mobius-text);cursor:pointer}
  .btn-src:hover{border-color:var(--mobius-violet);color:var(--mobius-violet)}
  .run{margin-top:12px;padding-top:12px;border-top:1px dashed var(--mobius-border)}
  .run:first-of-type{border-top:0}
  .steps{list-style:none;margin:8px 0 0;padding:0;font-size:12px}
  .steps li{display:flex;gap:8px;padding:3px 0;align-items:baseline}
  .ts{color:var(--mobius-text-muted);font-variant-numeric:tabular-nums;flex:0 0 auto}
  .sk{flex:0 0 auto;min-width:150px}
  .sx{color:var(--mobius-text-muted);overflow:hidden;text-overflow:ellipsis;
    white-space:nowrap;min-width:0}
  .quote{margin-top:4px;padding-left:9px;border-left:2px solid var(--mobius-border);
    color:var(--mobius-text-muted);font-size:12px}
</style>

<div class="app">
  <header class="top">
    <span class="mark">__LOGO__ Mobius Service Lines</span>
    <span class="spacer"></span>
    <button class="btn" id="expand">Show everything to check</button>
  </header>
  <div class="body" id="body">
    <nav class="side">
      <button class="chev" id="toggle" aria-label="Collapse sidebar" title="Collapse sidebar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
      </button>
      <div class="sidehead">
        <input class="srch" id="q" type="search" placeholder="Search services" autocomplete="off">
      </div>
      <div class="nav" id="nav"></div>
    </nav>
    <main class="main" id="main"></main>
  </div>
</div>

<script>
var DATA = __DATA__;
var LINES = DATA.lines, cur = LINES[0].id, filter = "";

function esc(s){return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;");}
var CHEV='<svg class="ci" viewBox="0 0 24 24" fill="none" stroke="currentColor" '+
  'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>';
function card(title, meta, inner, shut){
  return '<section class="card'+(shut?' shut':'')+'"><h2 role="button" tabindex="0" '+
    'aria-expanded="'+(shut?'false':'true')+'">'+CHEV+esc(title)+
    (meta?'<em>'+esc(meta)+'</em>':'')+'</h2>'+inner+'</section>';
}
function money(n){return n==null?"—":"$"+Number(n).toFixed(2);}

/* Plain English. The internal words never reach the screen. */
function sourceLabel(o){
  return o==="parsed"      ? ["From the fee schedule","c-ok"]
       : o==="interpreted" ? ["Read from the policy","c-warn"]
       : o==="human"       ? ["Entered by staff","c-mute"]
       :                     ["No source yet","c-need"];
}
function checkLabel(s){
  return s==="approve" ? ["Confirmed","c-ok"]
       : s==="reject"  ? ["Flagged","c-need"]
       : s==="correct" ? ["Edited","c-warn"]
       :                 ["Not checked","c-mute"];
}

/* DEFECT 7 — six of seven ready services begin "Behavioral Health", so
   truncation removed exactly the distinguishing part. Drop the shared prefix in
   the rail; the full name stays in the tooltip and the heading. */
function shortName(n){
  return n.replace(/^Behavioral Health\s+/, "")
          .replace(/^Targeted Case Management for\s+/, "TCM · ");
}
/* DEFECT 6 — at 48px every service was an identical dot. */
function initials(n){
  var w = n.replace(/[^A-Za-z ]/g," ").split(/\s+/).filter(Boolean);
  return ((w[0]||"?")[0] + (w[1]||"")[0||0] || "").toUpperCase().slice(0,2);
}

function drawNav(){
  var q = filter.toLowerCase();
  /* DEFECT 9 — a billing user arrives with the code on the claim, not the
     service name. */
  var hit = LINES.filter(function(l){return !q || l.search.indexOf(q)>=0;});
  var ready = hit.filter(function(l){return l.ready;});
  var wait  = hit.filter(function(l){return !l.ready;});
  function grp(title, arr){
    if(!arr.length) return "";
    return '<div class="grp">'+title+' · '+arr.length+'</div>' + arr.map(function(l){
      /* DEFECT 5 — four services hold nothing at all and the rail gave no hint
         that opening them was pointless. */
      var n = l.toCheck || l.toSource;
      var tag = l.toCheck ? '<i>'+l.toCheck+'</i>'
              : l.toSource ? '<i class="src">'+l.toSource+'</i>'
              : '<i class="non">—</i>';
      return '<button data-id="'+l.id+'" aria-current="'+(l.id===cur)+'" '+
        'title="'+esc(l.name)+(n?"":" — nothing recorded yet")+'">'+
        '<span class="dot'+(l.ready?"":" wait")+'" data-ini="'+esc(initials(l.name))+'"></span>'+
        '<b>'+esc(shortName(l.name))+'</b>'+tag+'</button>';
    }).join("");
  }
  var html = grp("Ready", ready) + grp("Awaiting sources", wait);
  document.getElementById("nav").innerHTML = html ||
    '<div class="empty"><span>Nothing matches \u201c'+esc(filter)+'\u201d</span></div>';
}

function evidence(it){
  /* Why this is here and what it rests on. Shut by default — a reviewer opens
     it when they doubt something, and it must never set the tone of the page. */
  return '<details class="ev"><summary>Why this is here</summary>'+
    '<dl class="tech">'+
    '<dt>Recorded as</dt><dd>'+esc(it.kind||"—")+'</dd>'+
    '<dt>How we got it</dt><dd>'+sourceWhy(it.origin)+'</dd>'+
    '<dt>Document</dt><dd>'+(it.source?esc(it.source):
       '<span style="color:var(--mobius-error)">none — this still needs a source</span>')+'</dd>'+
    '<dt>Exact wording</dt><dd class="vb">'+esc(it.verbatim)+'</dd>'+
    '</dl></details>';
}
/* Even an operator panel obeys §7. These are our pipeline's words, not English. */
var OUTCOME={extracted:"Found and recorded",
  ungrounded:"Answer could not be traced back to a document",
  not_answered:"Nothing in our documents answered it",
  no_retrieval:"No documents came back",
  error:"The run failed"};
var MSTATE={sourced:"Found",escalated:"Handed to a person",
  open:"Waiting",in_progress:"Running"};
function sourceWhy(o){
  return o==="parsed"      ? "Read straight out of the published fee schedule."
       : o==="interpreted" ? "Taken from the wording of the policy and written into a "+
                             "form that can be checked against a claim."
       : o==="human"       ? "Entered by a member of staff."
       : "No document has been found for this yet. It is a placeholder in our own words, "+
         "not the policy's.";
}

function itemRow(it){
  var src = sourceLabel(it.origin), st = checkLabel(it.state);
  /* Nothing sits behind this yet, so confirming it would only approve our own
     wording. The action is to find a source, not to agree. */
  var noDoc = it.origin === "asserted";
  var acts = noDoc
    ? '<button class="btn pri" disabled>Find a source</button>'+
      '<button class="btn" disabled>Edit</button>'
    : '<button class="btn pri" disabled>Confirm</button>'+
      '<button class="btn" disabled>Flag</button>'+
      '<button class="btn" disabled>Edit</button>';
  return '<div class="item'+(noDoc?" needs":"")+'"><div class="itop">'+
    '<span class="itxt">'+(it.labels||[it.label]).map(function(x){
      return '<span class="lbl">'+esc(x)+'</span>';}).join("")+
    esc(it.what)+'</span>'+
    '<span class="chip '+src[1]+'">'+src[0]+'</span>'+
    (noDoc?'':'<span class="chip '+st[1]+'">'+st[0]+'</span>')+
    '<span class="acts">'+acts+'</span></div>'+
    evidence(it)+'</div>';
}

function draw(){
  var l = LINES.filter(function(x){return x.id===cur;})[0];
  if(!l) return drawQueue();
  var h = '<div><h1>'+esc(l.name)+'</h1><p class="sub">'+
    (l.ready
      ? 'Florida Medicaid behavioral health'+(l.rule?' · Rule '+esc(l.rule):'')
      : 'We have not gathered the fee schedule or coverage documents for this service yet.')+
    '</p></div>';

  var behindN = l.modules.filter(function(m){
    return m.state!=="done" && m.state!=="complete" && m.state!=="na" &&
           m.state!=="not_applicable";}).length;
  h += '<div class="kpis">'+
    '<div class="kpi"><span>Billable codes</span><b>'+l.codes.length+'</b></div>'+
    '<div class="kpi"><span>To check</span><b>'+l.toCheck+'</b></div>'+
    '<div class="kpi"><span>Needs a source</span><b>'+l.toSource+'</b></div>'+
    '<div class="kpi"><span>Modules behind</span><b>'+behindN+'</b></div></div>';

  /* Where the service comes from. NOT technical — a reviewer needs the rule and
     the documents in front of them, which is why they moved out of the folded
     panel and up here, open. */
  h += card("About this service", l.rule ? "Rule "+l.rule : "no rule recorded",
    '<div class="pad"><dl class="tech">'+
    '<dt>Governing rule</dt><dd>'+(l.rule?esc(l.rule):
      '<span style="color:var(--mobius-warning)">none recorded yet</span>')+'</dd>'+
    '<dt>Set by</dt><dd>'+esc(l.authority||"—")+'</dd>'+
    '<dt>How it is paid</dt><dd>'+esc((l.grain||"—").replace(/_/g," "))+'</dd>'+
    '<dt>Documents behind this</dt><dd>'+
      (l.sources.length? l.sources.map(esc).join("<br>")
        : '<span style="color:var(--mobius-error)">none held yet</span>')+'</dd>'+
    '</dl></div>'+
    (l.common.length?'<div class="pad items" style="border-top:1px solid var(--mobius-border)">'+
      '<p class="lead" style="font-size:var(--mobius-text-sm);color:var(--mobius-text-muted)">'+
      'Applies to every code below.</p>'+l.common.map(itemRow).join("")+'</div>':''));

  /* One card per code. Everything about that code is inside it — what it is,
     what it pays, its caps, and each thing waiting to be checked. */
  l.codes.forEach(function(c){
    var title = c.code + (c.mod ? " with " + c.mod : "");
    var pending = c.items.filter(function(i){return i.state==="unreviewed";}).length;
    var inner = '<div class="pad">'+
      '<p class="lead">'+esc(c.what)+'</p>'+
      '<dl class="tech">'+
      '<dt>Rate</dt><dd>'+money(c.rate)+(c.unit?' per '+esc(c.unit):'')+'</dd>'+
      (c.limits.length?'<dt>Limit</dt><dd>'+c.limits.map(esc).join('<br>')+'</dd>':'')+
      (c.tele?'<dt>Telehealth</dt><dd>Allowed</dd>':'')+
      '</dl>'+
      (c.items.length?'<div class="items">'+c.items.map(itemRow).join("")+'</div>':'')+
      '</div>';
    h += card(title, pending? pending+" to check" : "checked", inner, true);
  });

  if(l.groupings.length){
    h += card("Diagnosis and hospital grouping codes", l.groupings.length+" codes",
      '<div class="pad"><p class="lead" style="font-size:var(--mobius-text-sm);'+
      'color:var(--mobius-text-muted)">These place an encounter for hospital billing. '+
      'They are not codes you bill directly.</p>'+
      '<div class="items">'+l.groupings.map(itemRow).join("")+'</div></div>', true);
  }

  if(!l.ready){
    h += '<section class="card"><div class="empty">'+
      '<svg viewBox="0 0 100 100" width="24" height="24" fill="none" stroke="currentColor" '+
      'stroke-width="4.5"><path d="M 50 50 C 50 22 22 22 22 50 C 22 78 50 78 50 50 '+
      'C 50 78 78 78 78 50 C 78 22 50 22 50 50" stroke-linecap="round"/></svg>'+
      '<span>Nothing to review until the documents for this service are gathered.</span>'+
      '</div></section>';
  }

  /* System state, not domain fact. How this service was sourced, whether the
     machinery is still working on it, and whether the other modules have caught
     up — the questions an operator asks, never a reviewer. */
  var MOD={done:["In sync","c-ok"],complete:["In sync","c-ok"],
           doing:["Working","c-warn"],in_progress:["Working","c-warn"],
           na:["Not needed","c-mute"],not_applicable:["Not needed","c-mute"]};
  var behind = l.modules.filter(function(m){return (MOD[m.state]||["Not started"])[0]==="Not started";}).length;
  var tech =
    '<div class="pad"><h3 class="th">Other modules</h3><dl class="tech">'+
      l.modules.map(function(m){
        var v = MOD[m.state] || ["Not started","c-need"];
        return '<dt>'+esc(m.name)+'</dt><dd><span class="chip '+v[1]+'">'+v[0]+'</span>'+
          (m.why?'<div class="hint2">'+esc(m.why)+'</div>':'')+'</dd>';
      }).join("")+'</dl></div>'+
    '<div class="pad" style="border-top:1px solid var(--mobius-border)">'+
      '<div class="throw"><h3 class="th">Sourcing</h3>'+
        '<button class="btn-src" data-src="'+esc(l.id)+'">Source this service</button></div>'+
      '<div id="srcnote" class="hint2"></div>'+
      (l.runs.length ? l.runs.map(runBlock).join("")
        : '<p class="hint2">This service has not been sourced yet. '+
          'Starting a run asks the policy documents for each missing answer, '+
          'and every step is recorded below.</p>')+
    '</div>'+
    '<div class="pad" style="border-top:1px solid var(--mobius-border)">'+
      '<h3 class="th">Search terms</h3><dl class="tech">'+
      '<dt>Agreed terms</dt><dd>'+(l.terms.confirmed||0)+' of '+(l.terms.mapped||0)+'</dd>'+
      '<dt>Passages reachable</dt><dd>'+l.chunks+'</dd>'+
      '</dl></div>';
  h += card("Technical details", behind? behind+" modules behind" : "", tech, true);


/* One run, rendered the same way whether it is happening now or happened last week.
   Contract §7: live is a tail of the stream, replay is the same rows read again, and
   they must render identically — otherwise the audit log is not evidence of what the
   viewer saw. */
var API = "__API__";
var FIND = {stated:["Answered","c-ok"], none_applies:["No requirement","c-ok"],
            silent:["Document is silent","c-ok"], unresolved:["Could not answer","c-need"],
            unknown_class:["Unrecognised result","c-need"]};
var STEP = {run_started:"Run started", governing_resolved:"Governing document checked",
            request_opened:"Question sent", turn_running:"Searching",
            turn_complete:"Search finished", attempt:"Answer assessed",
            diagnosis:"Result classified", request_settled:"Question settled",
            repair_filed:"Handed to another team", run_finished:"Run finished",
            error:"Failed", stream_closed:"Stream closed"};
var RSTAT = {running:["Running","c-warn"], finished:["Finished","c-ok"],
             failed:["Failed","c-need"], cancelled:["Cancelled","c-mute"]};
/* Whether a person can actually follow the citation to the sentence. Checked against
   our own corpus, not taken from the answer. A quote a reviewer cannot check is not
   evidence, and confirming against one manufactures confidence rather than earning it. */
var CITE = {verbatim:["In the document","c-ok"],
            composed:["Summarised from the document","c-warn"],
            misdirected:["Not found in that document","c-need"],
            unresolvable:["That document is not on file","c-need"],
            unverified:["Not checkable","c-mute"], uncited:["No source given","c-need"]};

function runBlock(r){
  var st = RSTAT[r.status] || [r.status,"c-mute"];
  var items = (r.items||[]).map(function(t){
    var f = FIND[t.finding] || (t.finding? [t.finding,"c-mute"] : ["Not settled","c-mute"]);
    return '<dt>'+esc(t.about)+(t.code? " "+esc(t.code):"")+'</dt><dd>'+
      '<span class="chip '+f[1]+'">'+f[0]+'</span>'+
      (t.owner? '<div class="hint2">Waiting on '+esc(t.owner.replace(/_/g," "))+'</div>':'')+
      (t.quote? '<div class="quote">'+esc(t.quote)+'</div>':'')+
      (t.document? '<div class="hint2">'+esc(t.document)+
        (CITE[t.citation]? ' &middot; <span class="chip '+CITE[t.citation][1]+'">'+
          CITE[t.citation][0]+'</span>' : '')+'</div>':'')+'</dd>';
  }).join("");
  var steps = (r.events||[]).map(function(e){
    return '<li><span class="ts">'+esc(e.at||"")+'</span>'+
      '<span class="sk">'+esc(STEP[e.kind]||e.kind.replace(/_/g," "))+'</span>'+
      (e.text? '<span class="sx">'+esc(e.text)+'</span>':'')+'</li>';
  }).join("");
  return '<div class="run" id="run-'+esc(r.id)+'">'+
    '<div class="throw"><strong>'+esc(r.started)+'</strong>'+
      '<span class="chip '+st[1]+'">'+st[0]+'</span></div>'+
    '<div class="hint2">'+r.tasks+' question'+(r.tasks===1?"":"s")+
      ' &middot; started by '+esc(r.by)+(r.note? ' &middot; '+esc(r.note):'')+'</div>'+
    (items? '<dl class="tech">'+items+'</dl>':'')+
    '<ol class="steps">'+steps+'</ol></div>';
}

function startRun(lineId){
  var note = document.getElementById("srcnote");
  note.textContent = "Starting…";
  fetch(API+"/api/service-line/runs?line="+encodeURIComponent(lineId))
    .then(function(r){ if(!r.ok) throw new Error("HTTP "+r.status); return r.json(); })
    .then(function(d){
      /* Reading works; starting does not. Registry exposes the run and its stream, but
         a run is driven by the sourcing script, not by this service — so say exactly
         that rather than pretending a click did something. */
      note.innerHTML = 'Runs are started from the sourcing script, not from this page yet. '+
        'Run <code>python3 docs/service-lines/scripts/run_sourcing.py '+esc(lineId)+'</code> '+
        'and this panel will show every step.';
    })
    .catch(function(e){
      note.textContent = "The registry service is not reachable from here ("+e.message+
        "). The steps below are the last recorded run.";
    });
}

  document.getElementById("main").innerHTML = h;
}

document.getElementById("main").addEventListener("click", function(e){
  var sb = e.target.closest && e.target.closest("[data-src]");
  if (sb) { startRun(sb.getAttribute("data-src")); return; }
  var hd = e.target.closest(".card > h2");
  if(!hd) return;
  var c = hd.parentElement, shut = c.classList.toggle("shut");
  hd.setAttribute("aria-expanded", String(!shut));
});
document.getElementById("main").addEventListener("keydown", function(e){
  if(e.key !== "Enter" && e.key !== " ") return;
  var hd = e.target.closest(".card > h2");
  if(!hd) return;
  e.preventDefault(); hd.click();
});
document.getElementById("nav").addEventListener("click", function(e){
  var b = e.target.closest("button[data-id]");
  if(b){ cur = b.dataset.id; drawNav(); draw(); document.getElementById("main").scrollTop = 0; }
});
document.getElementById("q").addEventListener("input", function(e){
  filter = e.target.value; drawNav();
});
document.getElementById("toggle").addEventListener("click", function(){
  var railed = document.getElementById("body").classList.toggle("rail");
  var b = document.getElementById("toggle");
  b.setAttribute("aria-label", railed ? "Expand sidebar" : "Collapse sidebar");
  b.setAttribute("title", railed ? "Expand sidebar" : "Collapse sidebar");
});
/* DEFECT 10 — the button said "show everything to check" and jumped to one
   service. A reviewer wants one queue across all of them. */
function drawQueue(){
  var rows = [];
  LINES.forEach(function(l){
    var items = [].concat(l.common, l.groupings);
    l.codes.forEach(function(c){ items = items.concat(c.items); });
    items.filter(function(i){return i.state==="unreviewed" && i.origin!=="asserted";})
         .forEach(function(i){ rows.push({svc:l.name, id:l.id, it:i}); });
  });
  var by = {};
  rows.forEach(function(r){ (by[r.svc]=by[r.svc]||[]).push(r); });
  var h = '<div><h1>Everything to check</h1><p class="sub">'+rows.length+
    ' items across '+Object.keys(by).length+' services, oldest sources first.</p></div>';
  Object.keys(by).forEach(function(svc){
    h += card(svc, by[svc].length+" items",
      '<div class="pad items">'+by[svc].map(function(r){return itemRow(r.it);}).join("")+
      '</div>', true);
  });
  if(!rows.length) h = '<div class="empty"><span>Nothing is waiting to be checked.</span></div>';
  document.getElementById("main").innerHTML = h;
}
document.getElementById("expand").addEventListener("click", function(){
  cur = null; drawNav(); drawQueue();
});
drawNav(); draw();
</script>
"""

if __name__ == "__main__":
    build()
