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
import re
from pathlib import Path

ROOT = Path("/Users/ananth/Mobius")
CATALOG = ROOT / "docs/service-lines/fl-medicaid-bh.catalog.json"
TOKENS = ROOT / "mobius-design/tokens.css"
OUT = ROOT / "docs/product-docs/service-lines-review.html"

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
        common = []
        for r in l.get("review", []):
            item = {
                "what": human(r.get("value") or "")[:220],
                "verbatim": (r.get("value") or "")[:400],
                "origin": r.get("origin"), "source": r.get("source"),
                "state": r.get("state"),
                "kind": (r.get("kind") or "").replace("_", " "),
            }
            k = key(r.get("code"), r.get("modifier"))
            if r.get("code") and k in codes:
                codes[k]["items"].append(item)
            else:
                common.append(item)

        lines.append({
            "id": l["key"],                       # DOM handle only, never displayed
            "name": l["name"],
            "rule": l.get("rule"),
            "ready": bool(codes or bc.get("covered")),
            "codes": list(codes.values()),
            "common": common,
            "covered": bc.get("covered", 0),
            "sources": sorted({r["source"] for r in l.get("review", []) if r.get("source")}),
            "grain": l.get("grain"), "authority": l.get("authority"),
            "toCheck": rc.get("unreviewed", 0),
            "checked": (rc.get("total", 0) - rc.get("unreviewed", 0)),
        })

    data = json.dumps({"lines": lines}, separators=(",", ":"))
    OUT.write_text(PAGE.replace("__TOKENS__", tokens).replace("__LOGO__", LOGO)
                       .replace("__DATA__", data))
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

function drawNav(){
  var q = filter.toLowerCase();
  var hit = LINES.filter(function(l){return !q || l.name.toLowerCase().indexOf(q)>=0;});
  var ready = hit.filter(function(l){return l.ready;});
  var wait  = hit.filter(function(l){return !l.ready;});
  function grp(title, arr){
    if(!arr.length) return "";
    return '<div class="grp">'+title+' · '+arr.length+'</div>' + arr.map(function(l){
      return '<button data-id="'+l.id+'" aria-current="'+(l.id===cur)+'">'+
        '<span class="dot'+(l.ready?"":" wait")+'"></span><b>'+esc(l.name)+'</b>'+
        (l.toCheck?'<i>'+l.toCheck+'</i>':'')+'</button>';
    }).join("");
  }
  var html = grp("Ready", ready) + grp("Awaiting sources", wait);
  document.getElementById("nav").innerHTML = html ||
    '<div class="empty"><span>No services match “'+esc(filter)+'”</span></div>';
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
  return '<div class="item"><div class="itop">'+
    '<span class="itxt">'+esc(it.what)+'</span>'+
    '<span class="chip '+src[1]+'">'+src[0]+'</span>'+
    '<span class="chip '+st[1]+'">'+st[0]+'</span>'+
    '<span class="acts"><button class="btn pri" disabled>Confirm</button>'+
    '<button class="btn" disabled>Flag</button>'+
    '<button class="btn" disabled>Edit</button></span></div>'+
    evidence(it)+'</div>';
}

function draw(){
  var l = LINES.filter(function(x){return x.id===cur;})[0];
  if(!l) return;
  var h = '<div><h1>'+esc(l.name)+'</h1><p class="sub">'+
    (l.ready
      ? 'Florida Medicaid behavioral health'+(l.rule?' · Rule '+esc(l.rule):'')
      : 'We have not gathered the fee schedule or coverage documents for this service yet.')+
    '</p></div>';

  h += '<div class="kpis">'+
    '<div class="kpi"><span>Billable codes</span><b>'+l.codes.length+'</b></div>'+
    '<div class="kpi"><span>Covered</span><b>'+l.covered+'</b></div>'+
    '<div class="kpi"><span>To check</span><b>'+l.toCheck+'</b></div></div>';

  /* Applies to the whole service, before any individual code. */
  if(l.common.length){
    h += card("Applies to the whole service", l.common.length+" items",
      '<div class="pad items">'+l.common.map(itemRow).join("")+'</div>');
  }

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

  if(!l.ready){
    h += '<section class="card"><div class="empty">'+
      '<svg viewBox="0 0 100 100" width="24" height="24" fill="none" stroke="currentColor" '+
      'stroke-width="4.5"><path d="M 50 50 C 50 22 22 22 22 50 C 22 78 50 78 50 50 '+
      'C 50 78 78 78 78 50 C 78 22 50 22 50 50" stroke-linecap="round"/></svg>'+
      '<span>Nothing to review until the documents for this service are gathered.</span>'+
      '</div></section>';
  }

  var tech = '<div class="pad"><dl class="tech">'+
    '<dt>Governing rule</dt><dd>'+(l.rule?esc(l.rule):"none recorded")+'</dd>'+
    '<dt>Authority</dt><dd>'+esc(l.authority||"—")+'</dd>'+
    '<dt>How it is paid</dt><dd>'+esc((l.grain||"—").replace(/_/g," "))+'</dd>'+
    '<dt>Documents behind this</dt><dd>'+
      (l.sources.length? l.sources.map(esc).join("<br>") : "none held")+'</dd>'+
    '<dt>Items on file</dt><dd>'+(l.checked+l.toCheck)+' — '+l.checked+' checked, '+
      l.toCheck+' still to check</dd>'+
    '</dl></div>';
  h += card("Technical details", "", tech, true);

  document.getElementById("main").innerHTML = h;
}

document.getElementById("main").addEventListener("click", function(e){
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
document.getElementById("expand").addEventListener("click", function(){
  var first = LINES.filter(function(l){return l.toCheck;})[0];
  if(first){ cur = first.id; drawNav(); draw(); }
});
drawNav(); draw();
</script>
"""

if __name__ == "__main__":
    build()
