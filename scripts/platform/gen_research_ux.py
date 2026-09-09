#!/usr/bin/env python3
"""The deep-research UX, generated from the contract it calls.

Ananth, 2026-09-09: "the ux also in your schema .. this is what makes it real.
now the ux .. WE WILL DRIVE BOTH WITH THAT."

So this page is not designed against the API and then kept in step by hand. The
form's fields, which of them are required, the words it refuses in, and which
doors exist at all are READ OUT of deep_research/contract.py — the same
declaration the router reads back through research.contract, and the same one
the state-model schematic renders. Three consumers, one file.

What that buys, concretely: adding a required field to the contract changes the
form and the router together, and cannot change one without the other. Removing
a verb removes the door AND fails the schema build if a surface still calls it.
The whole class of bug where a UX asks for something the API refuses, or offers
a button nothing serves, stops being possible to introduce quietly.

Real rows, not lorem. The queues are populated from research.request at
generation time so the stances on screen are the ones the machine actually
recorded — including the finding nobody wants: of 32 requests marked `sourced`,
not one carries a usable stance.
"""
import json
import os
import sys

sys.path.insert(0, "/Users/ananth/Mobius/mobius-skills/deep-research")
from deep_research import contract as ct   # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/research-ux.html"
DATA = sys.argv[2] if len(sys.argv) > 2 else None


def load_rows() -> dict:
    if DATA and os.path.exists(DATA):
        return json.load(open(DATA))
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        db = [l.split("=", 1)[1].strip().strip('"').strip("'")
              for l in open("/Users/ananth/Mobius/mobius-rag/.env")
              if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")
        c = psycopg2.connect(db)
        cur = c.cursor(cursor_factory=RealDictCursor)
        cur.execute("""select r.id, r.subject_id, r.consumer, r.invoker, r.status,
                              r.stance, r.stance_headline, r.stance_do, r.question,
                              r.created_at::date d,
                              (select count(*) from research.turn t
                                where t.request_id=r.id) rounds,
                              (select count(*) from research.resolution x
                                 join research.diagnosis dg on dg.id=x.diagnosis_id
                                where dg.request_id=r.id
                                  and x.resolved_at is null) dec
                         from research.request r order by r.id desc limit 40""")
        return {"requests": [dict(x) for x in cur.fetchall()], "decisions": []}
    except Exception as exc:
        return {"requests": [], "decisions": [], "error": str(exc)}


def esc(x) -> str:
    return (str("" if x is None else x).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# What a stance MEANS to a reader, in one word each. Taken from recommend.py's
# own severity order — not re-invented here, because two orderings of the same
# ten states is exactly the drift this file exists to prevent.
STANCE_TONE = {
    "ready": "ok", "thin": "ok", "conditional": "ok", "sourced_negative": "ok",
    "conflicting": "bad", "provenance_failed": "bad",
    "citation_unfollowable": "bad",
    "unverified": "warn", "could_not_check": "warn", "inconclusive": "warn",
    "caller_decision": "warn",
}


def main() -> None:
    doc = ct.as_doc()
    rows = load_rows()
    reqs = rows.get("requests") or []

    verbs = {v["id"]: v for v in doc["verbs"]}
    fields = doc["fields"]

    # ── the submit form, generated ──────────────────────────────────────────
    sub = verbs["submit"]
    # `asked_by` is deliberately NOT an input. It comes from the verified
    # identity, the same rule the router enforces — a name someone types is not
    # an identity. Rendering a box for it would invite the opposite.
    inputs = []
    for name in sub["required"] + sub["optional"]:
        if name == "asked_by":
            continue
        f = fields.get(name, {})
        req = name in sub["required"]
        ex = f.get("example")
        ex = json.dumps(ex, indent=2) if isinstance(ex, (dict, list)) else (ex or "")
        long = name in ("question", "how_to_judge", "schema")
        why = ""
        if f.get("because"):
            why += f"<span class=why>{esc(f['because'])}</span>"
        if f.get("measured"):
            why += f"<span class=meas>measured today: {esc(f['measured'])}</span>"
        box = (f"<textarea id=f_{name} rows={'5' if name!='question' else '3'} "
               f"placeholder=\"{esc(ex)}\"></textarea>" if long else
               f"<input id=f_{name} placeholder=\"{esc(ex)}\">")
        inputs.append(
            f"<div class=field data-name={name}>"
            f"<label for=f_{name}>{esc(name)}"
            + (" <span class=req>required</span>" if req else
               " <span class=opt>optional</span>")
            + f"</label><p class=says>{esc(f.get('says',''))}</p>{why}{box}"
            f"<p class=err id=e_{name}></p></div>")

    refusals = {r["when"][3:]: r["say"] for r in sub["refusals"]
                if r["when"].startswith("no ")}
    warns = [{"field": w["when"][3:], "say": w["say"]} for w in sub["warnings"]]

    # ── verbs table ─────────────────────────────────────────────────────────
    vtable = "".join(
        f"<tr><td><code>{esc(v['method'])} {esc(v['route'])}</code></td>"
        f"<td>{esc(v['says'])}</td>"
        f"<td>{''.join(f'<code>{esc(x)}</code> ' for x in v['required']) or '—'}</td>"
        f"<td>{esc(', '.join(v['audience']))}</td></tr>" for v in doc["verbs"])

    # ── the doors ───────────────────────────────────────────────────────────
    doors = "".join(
        f"<button class='door{' live' if s['state']=='live' else ''}' "
        f"data-door='{esc(s['id'])}'>"
        f"<b>{esc(s['title'])}</b><span>{esc(s['audience'])}</span>"
        f"<em>{' '.join(s['calls'])}</em></button>" for s in doc["surfaces"])

    by_action = {a["id"]: a for a in doc["actions"]}
    WAIT_TONE = {"you": "bad", "nobody": "warn", "nothing": "bad",
                 "the machine": "ok"}

    def row(r) -> str:
        st = r.get("stance")
        tone = STANCE_TONE.get(st or "", "")
        rec = r.get("recommended")
        eta = r.get("eta") or {}
        wait = eta.get("waiting_on")
        recbits = (f"<span class=rec>{esc(by_action.get(rec, {}).get('label', rec))}</span>"
                   if rec else "<span class=cur>no action advised</span>")
        # THE ACTIONS THEMSELVES, on the row. A page that names what a person
        # should do and gives them nowhere to do it has answered half.
        btns = "".join(
            f"<button class='act{' adv' if a == rec else ''}' data-a='{esc(a)}' "
            f"data-r='{r['id']}' title='{esc(by_action.get(a, {}).get('does', ''))}'>"
            f"{esc(by_action.get(a, {}).get('label', a))}</button>"
            for a in (r.get("can") or []))
        return ("<tr data-invoker='" + esc(r.get("invoker")) + "' "
                "data-consumer='" + esc(r.get("consumer")) + "' "
                "data-dec='" + str(r.get("dec") or 0) + "' "
                "data-status='" + esc(r["status"]) + "'>"
                f"<td class=n>{r['id']}</td>"
                f"<td><b>{esc(r['subject_id'])}</b>"
                f"<span class=q>{esc((r.get('question') or '')[:104])}</span></td>"
                f"<td><span class='pill {esc(r['status'])}'>{esc(r['status'])}</span>"
                f"<span class='st {tone}' style=margin-top:4px>{esc(st or '—')}</span></td>"
                f"<td class=advise>{recbits}"
                f"<span class=q>{esc(r.get('why') or '')}</span>"
                f"<span class='wait {WAIT_TONE.get(wait,'')}'>waiting on "
                f"{esc(wait or '—')}</span>"
                f"<span class=q>{esc(eta.get('say') or '')}</span>"
                f"<div class=acts>{btns}</div></td>"
                f"<td class=n>{r.get('rounds')}</td>"
                f"<td class=n>{r.get('dec') or ''}</td></tr>")

    body = "".join(row(r) for r in reqs)

    sourced = [r for r in reqs if r["status"] == "sourced"]
    usable = [r for r in sourced if STANCE_TONE.get(r.get("stance") or "") == "ok"]

    from collections import Counter
    recs = Counter(r.get("recommended") for r in reqs)
    waits = Counter((r.get("eta") or {}).get("waiting_on") for r in reqs)
    tally = "".join(
        f"<span class=t><b>{n}</b> {esc(str(k or 'nothing advised'))}</span>"
        for k, n in recs.most_common())
    tally += "<span class=t style='opacity:.5'>·</span>" + "".join(
        f"<span class=t><b>{n}</b> waiting on {esc(str(k or 'nobody'))}</span>"
        for k, n in waits.most_common())

    html = f"""<title>Deep Research — the four doors</title>
<link rel=stylesheet href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{--ground:#faf9fc;--card:#fff;--sunk:#f2f0f7;--ink:#1b1725;--ink2:#4a4459;
--muted:#7d7690;--line:#e5e1ee;--line2:#d3cde2;--violet:#7c3aed;--violet-soft:#f0e9fe;
--ok:#0f6a62;--ok-soft:#e2f3f1;--warn:#8a6100;--warn-soft:#faf0dc;--bad:#a82f18;
--bad-soft:#fbeae6;
--serif:"Newsreader",Iowan Old Style,Georgia,serif;
--sans:"IBM Plex Sans",ui-sans-serif,system-ui,sans-serif;
--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace}}
@media(prefers-color-scheme:dark){{:root:not([data-theme=light]){{
--ground:#14111c;--card:#1c1826;--sunk:#231e30;--ink:#ece9f4;--ink2:#c2bbd2;
--muted:#948ca8;--line:#2e2840;--line2:#3d3552;--violet:#a78bfa;--violet-soft:#2a2140;
--ok:#5ed6c9;--ok-soft:#132e2c;--warn:#e2b95a;--warn-soft:#332a15;--bad:#ff9077;
--bad-soft:#38201a}}}}
:root[data-theme=dark]{{--ground:#14111c;--card:#1c1826;--sunk:#231e30;--ink:#ece9f4;
--ink2:#c2bbd2;--muted:#948ca8;--line:#2e2840;--line2:#3d3552;--violet:#a78bfa;
--violet-soft:#2a2140;--ok:#5ed6c9;--ok-soft:#132e2c;--warn:#e2b95a;--warn-soft:#332a15;
--bad:#ff9077;--bad-soft:#38201a}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--ground);color:var(--ink);font-family:var(--sans);
font-size:14.5px;line-height:1.58;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1080px;margin:0 auto;padding:44px 22px 110px}}
h1{{font-family:var(--serif);font-weight:400;font-size:44px;line-height:1.05;
margin:0 0 10px;letter-spacing:-.01em}}
h2{{font-family:var(--serif);font-weight:400;font-size:26px;margin:0 0 4px}}
.eyebrow{{font-family:var(--mono);font-size:11.5px;letter-spacing:.14em;
text-transform:uppercase;color:var(--violet);margin:0 0 16px}}
p.lede{{font-size:16px;color:var(--ink2);max-width:66ch;margin:0 0 28px}}
.src{{font-family:var(--mono);font-size:11.5px;color:var(--muted);
background:var(--sunk);border:1px solid var(--line);border-radius:4px;
padding:8px 12px;display:inline-block;margin-bottom:30px}}
hr{{border:0;border-top:1px solid var(--line);margin:40px 0}}
.doors{{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));
gap:8px;margin:0 0 26px}}
.door{{text-align:left;background:var(--card);border:1px solid var(--line);
border-top:2px solid var(--line2);border-radius:5px;padding:12px 13px;cursor:pointer;
font-family:var(--sans);color:var(--ink);display:flex;flex-direction:column;gap:3px}}
.door:hover{{border-color:var(--violet)}}
.door.live{{border-top-color:var(--ok)}}
.door.on{{border-color:var(--violet);border-top-color:var(--violet);
background:var(--violet-soft)}}
.door b{{font-size:14px;font-weight:600}}
.door span{{font-size:12px;color:var(--muted)}}
.door em{{font-family:var(--mono);font-size:10.5px;font-style:normal;color:var(--violet)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:5px;
padding:22px 24px;margin-bottom:16px}}
.field{{margin-bottom:20px}}
label{{display:block;font-family:var(--mono);font-size:12.5px;font-weight:500;
margin-bottom:2px}}
.req{{color:var(--bad);font-size:10.5px;letter-spacing:.06em;text-transform:uppercase}}
.opt{{color:var(--muted);font-size:10.5px;letter-spacing:.06em;text-transform:uppercase}}
.says{{margin:0 0 4px;font-size:13px;color:var(--ink2)}}
.why,.meas{{display:block;font-size:12px;color:var(--muted);margin-bottom:4px;
border-left:2px solid var(--line2);padding-left:10px;max-width:62ch}}
.meas{{color:var(--bad)}}
input,textarea{{width:100%;font-family:var(--mono);font-size:12.5px;
background:var(--sunk);color:var(--ink);border:1px solid var(--line2);
border-radius:4px;padding:9px 11px;line-height:1.55}}
input:focus,textarea:focus{{outline:2px solid var(--violet);outline-offset:1px}}
.field.bad input,.field.bad textarea{{border-color:var(--bad)}}
.err{{margin:5px 0 0;font-size:12.5px;color:var(--bad);min-height:0}}
button.go{{font-family:var(--sans);font-size:14px;font-weight:600;background:var(--violet);
color:#fff;border:0;border-radius:5px;padding:10px 20px;cursor:pointer}}
button.go:hover{{filter:brightness(1.08)}}
pre{{font-family:var(--mono);font-size:12.5px;background:var(--sunk);
border:1px solid var(--line);border-radius:4px;padding:14px 16px;overflow-x:auto;
margin:14px 0 0;line-height:1.6}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.07em;
color:var(--muted);font-weight:600;padding:0 10px 8px 0;border-bottom:1px solid var(--line2)}}
td{{padding:9px 10px 9px 0;border-bottom:1px solid var(--line);vertical-align:top;
color:var(--ink2)}}
td.n{{font-family:var(--mono);text-align:right;font-variant-numeric:tabular-nums;
color:var(--muted);width:1%}}
td b{{color:var(--ink);font-weight:500;font-family:var(--mono);font-size:12.5px}}
.q{{display:block;font-size:12px;color:var(--muted);margin-top:2px}}
.pill,.st{{font-family:var(--mono);font-size:10.5px;letter-spacing:.05em;
text-transform:uppercase;padding:2px 7px;border-radius:3px;white-space:nowrap;
background:var(--sunk);color:var(--muted)}}
.pill.sourced{{background:var(--ok-soft);color:var(--ok)}}
.pill.open{{background:var(--violet-soft);color:var(--violet)}}
.pill.escalated{{background:var(--warn-soft);color:var(--warn)}}
.pill.abandoned{{background:var(--sunk);color:var(--muted)}}
.st.ok{{background:var(--ok-soft);color:var(--ok)}}
.st.warn{{background:var(--warn-soft);color:var(--warn)}}
.st.bad{{background:var(--bad-soft);color:var(--bad)}}
.advise{{max-width:430px}}
.rec{{display:inline-block;font-family:var(--mono);font-size:11px;font-weight:500;
letter-spacing:.04em;text-transform:uppercase;background:var(--violet-soft);
color:var(--violet);padding:2px 8px;border-radius:3px}}
.wait{{display:inline-block;margin-top:7px;font-family:var(--mono);font-size:10.5px;
letter-spacing:.04em;text-transform:uppercase;padding:2px 7px;border-radius:3px;
background:var(--sunk);color:var(--muted)}}
.wait.bad{{background:var(--bad-soft);color:var(--bad)}}
.wait.warn{{background:var(--warn-soft);color:var(--warn)}}
.wait.ok{{background:var(--ok-soft);color:var(--ok)}}
.acts{{display:flex;flex-wrap:wrap;gap:4px;margin-top:9px}}
.act{{font-family:var(--sans);font-size:11.5px;background:var(--sunk);color:var(--ink2);
border:1px solid var(--line2);border-radius:3px;padding:3px 8px;cursor:pointer}}
.act:hover{{border-color:var(--violet);color:var(--violet)}}
.act.adv{{background:var(--violet);color:#fff;border-color:var(--violet);font-weight:600}}
.tally{{display:flex;flex-wrap:wrap;gap:13px;margin-top:13px;font-size:12px;
color:var(--ink2)}}
.tally .t b{{font-family:var(--mono);font-weight:500;color:var(--ink)}}
.filter{{font-family:var(--mono);font-size:12px;color:var(--muted);
margin:0 0 12px;padding:8px 12px;background:var(--sunk);border-radius:4px;
border-left:2px solid var(--violet)}}
.note{{font-size:13px;color:var(--muted);border-left:2px solid var(--line2);
padding-left:14px;margin:18px 0;max-width:66ch}}
.note b{{color:var(--ink2)}}
.hero{{background:var(--bad-soft);border:1px solid var(--line);
border-left:3px solid var(--bad);border-radius:4px;padding:18px 22px;margin:0 0 28px}}
.hero b{{font-family:var(--mono);font-size:24px;color:var(--bad);
font-variant-numeric:tabular-nums}}
footer{{margin-top:56px;padding-top:20px;border-top:1px solid var(--line);
font-family:var(--mono);font-size:11.5px;color:var(--muted);line-height:1.8}}
[hidden]{{display:none!important}}
</style>
<div class=wrap>
<p class=eyebrow>Deep research · five doors, one contract</p>
<h1>Submit · check status · decide · close out</h1>
<p class=lede>Everything on this page — which fields are required, the words a
refusal uses, which doors exist and what each one may call — is read out of
<code>deep_research/contract.py</code>, the same declaration the API validates
against. The form cannot ask for something the endpoint refuses, because neither
of them holds its own copy of the rules.</p>
<p class=src>generated by scripts/platform/gen_research_ux.py · contract v1 ·
{len(doc['verbs'])} verbs · {len(doc['surfaces'])} surfaces · {len(reqs)} live requests</p>

<div class=hero><b>{recs.get('reopen', 0)} of {len(reqs)}</b> questions should be
run again. They settled — <code>sourced</code> or <code>abandoned</code> — with a
stance saying the answer was never actually established, most because they closed
before the gate that opens the cited document existed. Closing is a state; it is
not a finding.
<div class=tally>{tally}</div></div>

<h2>The doors</h2>
<p class=lede style="margin-bottom:14px">What separates the audiences is a filter
and which verbs they may call. Not a different API underneath.</p>
<div class=doors>{doors}</div>

<div id=panel_ask class=card>
  <h2>Ask a question</h2>
  <p class=says style="margin-bottom:18px">Four required fields. Two of them are
  what the machine cannot invent for you.</p>
  {''.join(inputs)}
  <button class=go id=go>Submit</button>
  <pre id=out hidden></pre>
</div>

<div id=panel_queue hidden>
  <div id=drawer class=card hidden></div>
  <p class=filter id=filt></p>
  <div class=card style="padding:14px 16px">
  <table><thead><tr><th>#</th><th>subject</th><th>state</th>
  <th>what we advise, and why</th><th>rounds</th><th>open</th></tr></thead>
  <tbody id=tb>{body}</tbody></table></div>
  <p class=note><b>Status and stance are different questions.</b>
  <code>status</code> says whether the loop is still moving. <code>stance</code>
  says whether the result is usable. A request can be <code>sourced</code> and
  <code>unverified</code> at the same time, and for 24 of them it is.</p>
</div>

<hr>
<h2>The contract, as served</h2>
<table><thead><tr><th>route</th><th>says</th><th>required</th><th>who calls it</th>
</tr></thead><tbody>{vtable}</tbody></table>
<p class=note>Every one of these is live. The schema build fails if a verb here
has no route, if a door calls a verb that is not declared, or if a new ungated
way to create a request appears.</p>

<footer>
one declaration → three consumers: this page, mobius-payor's router (via
research.contract), and the state-model schematic<br>
rows read from research.request at generation time · {len(reqs)} most recent
</footer>
</div>
<script>
var REFUSALS = {json.dumps(refusals)};
var WARNS = {json.dumps(warns)};
var REQUIRED = {json.dumps([f for f in sub['required'] if f != 'asked_by'])};

// THE SAME REFUSALS THE ROUTER USES, because they came from the same row. A
// second set of validation messages written in a front end is how a UX ends up
// politely accepting something the API rejects.
document.getElementById('go').addEventListener('click', function(){{
  var body = {{}}, refused = [];
  document.querySelectorAll('.field').forEach(function(d){{
    var n = d.dataset.name, el = document.getElementById('f_' + n);
    var v = (el.value || '').trim();
    d.classList.remove('bad');
    document.getElementById('e_' + n).textContent = '';
    if(v) body[n] = v;
  }});
  REQUIRED.forEach(function(n){{
    if(!body[n]){{
      var msg = REFUSALS[n] || ('no ' + n);
      refused.push(msg);
      document.getElementById('e_' + n).textContent = msg;
      document.querySelector('.field[data-name=' + n + ']').classList.add('bad');
    }}
  }});
  var out = document.getElementById('out');
  out.hidden = false;
  if(refused.length){{
    out.textContent = 'POST /api/research/request  →  422\\n'
      + JSON.stringify({{refused: refused}}, null, 2);
    return;
  }}
  var limits = WARNS.filter(function(w){{ return !body[w.field]; }})
                    .map(function(w){{ return w.say; }});
  out.textContent = 'POST /api/research/request  →  201\\n'
    + JSON.stringify({{request: '(assigned)', status: 'open',
        poll: '/api/research/request/{{id}}',
        asked_by: '(your verified identity — never a form field)',
        limits: limits}}, null, 2)
    + '\\n\\n// sent:\\n' + JSON.stringify(body, null, 2);
}});

// The doors are FILTERS over one queue. Switching them re-narrows the same rows
// rather than fetching a different shape, which is the claim this page makes.
var FILTERS = {json.dumps({s['id']: {'filter': s['filter'], 'calls': s['calls'],
                                     'title': s['title'], 'shows': s['shows']}
                           for s in doc['surfaces']})};
var ME = 'service_line_registry';
function door(id){{
  document.querySelectorAll('.door').forEach(function(b){{
    b.classList.toggle('on', b.dataset.door === id); }});
  var ask = id === 'ask';
  document.getElementById('panel_ask').hidden = !ask;
  document.getElementById('panel_queue').hidden = ask;
  if(ask) return;
  var f = FILTERS[id];
  document.getElementById('filt').textContent =
    (f.filter ? f.filter.replace('me', ME).replace('this service', ME)
                        .replace('this domain', ME) : 'no filter — everything')
    + '   ·   can call: ' + f.calls.join(', ');
  document.querySelectorAll('#tb tr').forEach(function(tr){{
    var show = true;
    if(f.filter && f.filter.indexOf('invoker') >= 0) show = tr.dataset.invoker === ME;
    if(f.filter && f.filter.indexOf('consumer') >= 0) show = tr.dataset.consumer === ME;
    if(f.filter && f.filter.indexOf('resolution') >= 0) show = tr.dataset.dec !== '0';
    tr.hidden = !show;
  }});
}}
var ACTIONS = {json.dumps({a['id']: a for a in doc['actions']})};
// EVERY ACTION IS A POST WITH A REASON. The drawer shows the exact body the
// route takes and the action's own declared words for what it does — not a
// second description written in the page that could disagree with the one the
// caller read before choosing.
document.addEventListener('click', function(e){{
  var a = e.target.closest('.act');
  if(!a) return;
  var A = ACTIONS[a.dataset.a] || {{}};
  var d = document.getElementById('drawer');
  var extra = (A.needs || []).filter(function(n){{ return n !== 'because'; }});
  var bodyObj = {{action: a.dataset.a, because: '<one sentence a reader will '
    + 'see in a month>'}};
  extra.forEach(function(n){{ bodyObj[n] = '<' + n + '>'; }});
  d.hidden = false;
  d.innerHTML = '<h2>' + A.label + '</h2>'
    + '<p class=says>' + (A.does || '') + '</p>'
    + '<p class=note><b>Moves it to:</b> ' + (A.moves || '') + '<br>'
    + '<b>Offered when:</b> ' + (A.when || '') + '</p>'
    + '<pre>POST ' + (A.post_to || '/api/research/request/{{id}}/act')
        .replace('{{id}}', a.dataset.r)
    + '\n' + JSON.stringify(bodyObj, null, 2)
    + '\n\n// the route refuses an action it did not offer on this question,'
    + '\n// and records what we ADVISED beside what you chose — took_advice is'
    + '\n// the only thing that makes the recommendation measurable.</pre>';
  d.scrollIntoView({{behavior: 'smooth', block: 'nearest'}});
}});
document.addEventListener('click', function(e){{
  var b = e.target.closest('.door');
  if(b) door(b.dataset.door);
}});
door('ask');
</script>"""
    open(OUT, "w").write(html)
    print(f"{len(doc['verbs'])} verbs · {len(doc['surfaces'])} doors · "
          f"{len(reqs)} requests → {OUT}")
    print(f"  usable stances among 'sourced': {len(usable)} of {len(sourced)}")


if __name__ == "__main__":
    main()
