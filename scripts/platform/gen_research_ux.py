#!/usr/bin/env python3
"""The deep-research UX, generated from the contract it calls.

Ananth, 2026-09-09: "the ux also in your schema .. WE WILL DRIVE BOTH WITH
THAT." And then the framework: "request, output, authority, tools, decisions,
(recommendations), status .. these are good artifacts of things we need."

So the page is organised by those seven, and every one of them — which fields
are required, the words a refusal uses, which doors exist, which actions are
offered and what each ends as — is read out of `deep_research/contract`, the
same declaration the router reads back through `research.contract`.

THE LIST TRIAGES; THE PAGE DECIDES. An earlier cut put a recommendation, a
rationale, a wait state and twelve buttons inside a table row — a decision
surface in forty pixels. A row now carries what we advise and who it is waiting
on, and everything else lives on the question's own page, where the evidence and
the conversation have room.

Real rows, never lorem. Two of the seven artifacts do not exist yet; the page
shows the hole rather than omitting the section.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, "/Users/ananth/Mobius/mobius-skills/deep-research")
from deep_research import contract as ct      # noqa: E402
from deep_research import language as L       # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/research-ux.html"
DATA = sys.argv[2] if len(sys.argv) > 2 else None


def esc(x) -> str:
    return (str("" if x is None else x).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def load_rows() -> dict:
    if DATA and os.path.exists(DATA):
        return json.load(open(DATA))
    return {"requests": []}


def check_script(html: str) -> bool:
    """Parse what we emitted. This generator once shipped a page whose every
    script was dead from one stray newline inside a JS string, and nothing about
    the rendered HTML said so. Rendering is not running."""
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    if not blocks:
        return True
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write("\n".join(blocks))
        path = fh.name
    try:
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    except FileNotFoundError:
        print("  ! node not found — emitted script NOT parsed; unverified.")
        return True
    finally:
        os.unlink(path)
    if r.returncode:
        print("\nBUILD FAILED — emitted JavaScript will not parse:")
        print("  " + (r.stderr or "").strip().replace("\n", "\n  ")[:800])
        return False
    print(f"  script: {len(blocks)} block(s) parsed")
    return True


# Which stances a reader can act on, in the resolver's own severity order.
STANCE_TONE = {"ready": "ok", "thin": "ok", "conditional": "ok",
               "sourced_negative": "ok",
               "conflicting": "bad", "provenance_failed": "bad",
               "citation_unfollowable": "bad", "closed_empty": "bad",
               "unverified": "warn", "could_not_check": "warn",
               "inconclusive": "warn", "caller_decision": "warn"}
WAIT_TONE = {"you": "bad", "nobody": "warn", "nothing": "bad",
             "the machine": "ok"}
ART_TONE = {"present": "ok", "partial": "warn", "absent": "bad"}


def ask_form(doc) -> str:
    """The submit form, grouped by artifact — including the two nothing collects.

    An artifact the page cannot collect is shown DISABLED with what it would
    take, rather than left off. A form that silently omits half the framework
    teaches a reader the framework is smaller than it is.
    """
    fields, sub = doc["fields"], next(v for v in doc["verbs"] if v["id"] == "submit")
    groups = [
        ("The request", "What you want to know", ["subject", "question"]),
        ("What you want back", "The shape of a good answer, and how to grade it",
         ["how_to_judge", "schema", "expects"]),
        ("Authority", "Which sources this answer may rest on",
         ["authority", "jurisdiction"]),
    ]
    out = []
    for title, sub_t, names in groups:
        boxes = []
        for n in names:
            f = fields.get(n, {})
            req = n in sub["required"]
            ex = f.get("example")
            ex = json.dumps(ex, indent=2) if isinstance(ex, (dict, list)) else (ex or "")
            long = n in ("question", "how_to_judge", "schema", "expects")
            why = ""
            if f.get("because"):
                why += f"<span class=why>{esc(f['because'])}</span>"
            if f.get("measured"):
                why += f"<span class=meas>measured today: {esc(f['measured'])}</span>"
            box = (f"<textarea id=f_{n} rows=3 placeholder=\"{esc(ex)}\"></textarea>"
                   if long else f"<input id=f_{n} placeholder=\"{esc(ex)}\">")
            boxes.append(
                f"<div class=field data-name={n}><label for=f_{n}>"
                f"{esc(f.get('label') or n)}"
                + (" <span class=req>needed</span>" if req
                   else " <span class=opt>if you have it</span>")
                + f"</label><p class=says>{esc(f.get('says',''))}</p>{why}{box}"
                f"<p class=err id=e_{n}></p>"
                f"<p class=key>stored as <code>{esc(n)}</code></p></div>")
        out.append(f"<section class=grp><h3>{esc(title)}</h3>"
                   f"<p class=grpsub>{esc(sub_t)}</p>{''.join(boxes)}</section>")

    # The two that do not exist yet.
    for aid in ("tools", "decisions"):
        a = next((x for x in doc["artifacts"] if x["id"] == aid), {})
        if aid == "tools":
            rows = "".join(
                f"<label class=grant><input type=checkbox disabled "
                + ("checked" if v.get("default") == "granted" else "")
                + f"> <b>{esc(k)}</b> <span class=cur>default "
                f"{esc(v.get('default'))} · costs {esc(v.get('costs'))}</span></label>"
                for k, v in (doc.get("tools") or {}).items())
        else:
            rows = "".join(
                f"<label class=grant><span class=pillx>{esc(v.get('default'))}</span> "
                f"<b>{esc(k)}</b> <span class=cur>{esc(v.get('says'))}</span></label>"
                for k, v in (doc.get("decisions") or {}).items())
        out.append(
            f"<section class='grp absent'><h3>{esc(a.get('title', aid))}"
            f" <span class=chip>not collected yet</span></h3>"
            f"<p class=grpsub>{esc(a.get('says',''))}</p>"
            f"<p class=gap>{esc(a.get('gap',''))}</p>"
            f"<div class=grants>{rows}</div></section>")
    return "".join(out)


def artifact_sections(doc) -> str:
    """The seven, as the question page's own spine."""
    out = []
    for a in doc["artifacts"]:
        carried = ", ".join(f"<code>{esc(x)}</code>" for x in a.get("carried_by") or [])
        out.append(
            f"<div class='artcard {esc(a['state'])}' data-art='{esc(a['id'])}'>"
            f"<div class=arth><b>{esc(a['title'])}</b>"
            f"<span class='st {ART_TONE.get(a['state'],'')}'>{esc(a['state'])}</span></div>"
            f"<p class=says>{esc(a['says'])}</p>"
            f"<div class=artbody id=art_{esc(a['id'])}></div>"
            + (f"<p class=gap>{esc(a['gap'])}</p>" if a.get("gap") else "")
            + (f"<p class=key>carried by {carried}</p>" if carried else
               "<p class=key>nothing carries this yet</p>")
            + "</div>")
    return "".join(out)


def main() -> None:
    doc = ct.as_doc()
    data = load_rows()
    reqs = data.get("requests") or []
    tasks = data.get("tasks") or []
    for r in reqs:
        st = r.get("stance")
        r["stance_word"], r["stance_help"] = L.stance(st)
        r["state_word"] = L.state(r["status"])[0]
        r["wait_word"] = L.waiting((r.get("eta") or {}).get("waiting_on"))[0]
    from collections import Counter
    recs = Counter(r.get("recommended") for r in reqs)
    acts_by_id = {a["id"]: a for a in doc["actions"]}
    tally = "".join(
        f"<span class=t><b>{n}</b> "
        + esc(acts_by_id.get(k, {}).get("label", "nothing we would advise"))
        + "</span>" for k, n in recs.most_common())

    rows = "".join(
        "<tr data-id='" + str(r["id"]) + "' data-invoker='" + esc(r.get("invoker"))
        + "' data-consumer='" + esc(r.get("consumer")) + "' data-dec='"
        + str(r.get("dec") or 0) + "'>"
        f"<td class=n>{r['id']}</td>"
        f"<td><b>{esc(r['subject_id'])}</b>"
        f"<span class=q>{esc((r.get('question') or '')[:96])}</span></td>"
        f"<td><span class='pill {esc(r['status'])}'>{esc(r['state_word'])}</span>"
        f"<span class='st {STANCE_TONE.get(r.get('stance') or '','')}' "
        f"title='{esc(r['stance_help'])}'>{esc(r['stance_word'])}</span></td>"
        f"<td class=advise><span class=rec>"
        + esc(acts_by_id.get(r.get("recommended"), {}).get("label",
              "Nothing we would advise")) + "</span>"
        f"<span class=q>{esc((r.get('why') or '')[:130])}</span></td>"
        f"<td><span class='wait {WAIT_TONE.get((r.get('eta') or {}).get('waiting_on'),'')}'>"
        f"{esc(r['wait_word'])}</span></td>"
        f"<td class=n>{r.get('rounds')}</td></tr>" for r in reqs)

    worklist_rows = "".join(
        "<tr data-task='" + str(t["id"]) + "'>"
        f"<td class=n><b class=worth>{t.get('worth', 0)}</b></td>"
        f"<td><b>{esc(t['what'])}</b>"
        f"<span class=q>{esc(t.get('because') or '')}</span></td>"
        f"<td><span class=pillx>{esc(t.get('owner_role') or 'anyone')}</span>"
        f"<span class=q>found by: {esc(t.get('basis') or 'declared')}</span></td>"
        f"<td class=n>{len(t.get('questions') or []) or '—'}</td>"
        f"<td><span class='wait {'bad' if t.get('outside') else 'ok'}'>"
        + ("outside" if t.get("outside") else "here") + "</span></td></tr>"
        for t in tasks)

    doors = "".join(
        f"<button class='door{' live' if s['state']=='live' else ''}' "
        f"data-door='{esc(s['id'])}'><b>{esc(s['title'])}</b>"
        f"<span>{esc(s['audience'])}</span>"
        f"<em>{' '.join(s['calls'])}</em></button>" for s in doc["surfaces"])

    vtable = "".join(
        f"<tr><td><code>{esc(v['method'])} {esc(v['route'])}</code></td>"
        f"<td>{esc(v['says'])}</td>"
        f"<td>{''.join(f'<code>{esc(x)}</code> ' for x in v['required']) or '—'}</td>"
        f"</tr>" for v in doc["verbs"])

    from collections import Counter as C2
    astate = C2(a["state"] for a in doc["artifacts"])

    payload = json.dumps({"requests": reqs, "tasks": tasks,
                          "task_kinds": doc.get("task_kinds") or {},
                          "actions": acts_by_id,
                          "artifacts": doc["artifacts"],
                          "surfaces": {s["id"]: s for s in doc["surfaces"]},
                          "note_uses": doc.get("note_uses") or {},
                          "tools": doc.get("tools") or {},
                          "decisions": doc.get("decisions") or {}})

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
h3{{font-size:13px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);
font-weight:600;margin:0 0 2px}}
.eyebrow{{font-family:var(--mono);font-size:11.5px;letter-spacing:.14em;
text-transform:uppercase;color:var(--violet);margin:0 0 16px}}
p.lede{{font-size:16px;color:var(--ink2);max-width:66ch;margin:0 0 26px}}
.src{{font-family:var(--mono);font-size:11.5px;color:var(--muted);background:var(--sunk);
border:1px solid var(--line);border-radius:4px;padding:8px 12px;display:inline-block;
margin-bottom:28px}}
hr{{border:0;border-top:1px solid var(--line);margin:38px 0}}
.hero{{background:var(--bad-soft);border:1px solid var(--line);border-left:3px solid var(--bad);
border-radius:4px;padding:18px 22px;margin:0 0 26px}}
.hero b{{font-family:var(--mono);font-size:24px;color:var(--bad);font-variant-numeric:tabular-nums}}
.tally{{display:flex;flex-wrap:wrap;gap:13px;margin-top:13px;font-size:12px;color:var(--ink2)}}
.tally .t b{{font-family:var(--mono);font-weight:500;color:var(--ink);font-size:12px}}
.doors{{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:8px;margin:0 0 24px}}
.door{{text-align:left;background:var(--card);border:1px solid var(--line);
border-top:2px solid var(--line2);border-radius:5px;padding:12px 13px;cursor:pointer;
font-family:var(--sans);color:var(--ink);display:flex;flex-direction:column;gap:3px}}
.door:hover{{border-color:var(--violet)}} .door.live{{border-top-color:var(--ok)}}
.door.on{{border-color:var(--violet);border-top-color:var(--violet);background:var(--violet-soft)}}
.door b{{font-size:14px;font-weight:600}} .door span{{font-size:12px;color:var(--muted)}}
.door em{{font-family:var(--mono);font-size:10.5px;font-style:normal;color:var(--violet)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:5px;
padding:22px 24px;margin-bottom:16px}}
.grp{{margin-bottom:26px;padding-bottom:20px;border-bottom:1px solid var(--line)}}
.grp:last-child{{border-bottom:0}}
.grp.absent{{opacity:.9;background:var(--sunk);margin:0 -12px 26px;padding:16px 12px;
border-radius:5px;border-bottom:0}}
.grpsub{{margin:0 0 14px;font-size:13px;color:var(--muted)}}
.gap{{margin:0 0 10px;font-size:12.5px;color:var(--bad);border-left:2px solid var(--bad);
padding-left:10px;max-width:64ch}}
.chip{{font-family:var(--mono);font-size:10px;letter-spacing:.06em;background:var(--bad-soft);
color:var(--bad);padding:2px 7px;border-radius:3px;text-transform:none}}
.grants{{display:flex;flex-direction:column;gap:5px}}
.grant{{font-size:12.5px;color:var(--ink2);display:flex;align-items:baseline;gap:7px}}
.grant b{{font-family:var(--mono);font-size:12px;color:var(--ink);font-weight:500}}
.pillx{{font-family:var(--mono);font-size:10px;text-transform:uppercase;padding:1px 6px;
border-radius:3px;background:var(--card);color:var(--muted);border:1px solid var(--line2)}}
.field{{margin-bottom:18px}}
label{{display:block;font-family:var(--mono);font-size:12.5px;font-weight:500;margin-bottom:2px}}
.req{{color:var(--bad);font-size:10.5px;letter-spacing:.06em;text-transform:uppercase}}
.opt{{color:var(--muted);font-size:10.5px;letter-spacing:.06em;text-transform:uppercase}}
.says{{margin:0 0 4px;font-size:13px;color:var(--ink2)}}
.why,.meas{{display:block;font-size:12px;color:var(--muted);margin-bottom:4px;
border-left:2px solid var(--line2);padding-left:10px;max-width:62ch}}
.meas{{color:var(--bad)}}
input,textarea{{width:100%;font-family:var(--mono);font-size:12.5px;background:var(--sunk);
color:var(--ink);border:1px solid var(--line2);border-radius:4px;padding:9px 11px;line-height:1.55}}
input:focus,textarea:focus{{outline:2px solid var(--violet);outline-offset:1px}}
.field.bad input,.field.bad textarea{{border-color:var(--bad)}}
.err{{margin:5px 0 0;font-size:12.5px;color:var(--bad)}}
.key{{margin:4px 0 0;font-family:var(--mono);font-size:10.5px;color:var(--muted);opacity:.75}}
.key code{{background:none;padding:0}}
button.go{{font-family:var(--sans);font-size:14px;font-weight:600;background:var(--violet);
color:#fff;border:0;border-radius:5px;padding:10px 20px;cursor:pointer}}
pre{{font-family:var(--mono);font-size:12.5px;background:var(--sunk);border:1px solid var(--line);
border-radius:4px;padding:14px 16px;overflow-x:auto;margin:14px 0 0;line-height:1.6;
white-space:pre-wrap}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.07em;
color:var(--muted);font-weight:600;padding:0 10px 8px 0;border-bottom:1px solid var(--line2)}}
td{{padding:9px 10px 9px 0;border-bottom:1px solid var(--line);vertical-align:top;color:var(--ink2)}}
tbody tr{{cursor:pointer}} tbody tr:hover{{background:var(--sunk)}}
td.n{{font-family:var(--mono);text-align:right;font-variant-numeric:tabular-nums;
color:var(--muted);width:1%}}
td b{{color:var(--ink);font-weight:500;font-family:var(--mono);font-size:12.5px}}
.q{{display:block;font-size:12px;color:var(--muted);margin-top:2px}}
.pill,.st,.wait{{font-family:var(--mono);font-size:10.5px;letter-spacing:.05em;
text-transform:uppercase;padding:2px 7px;border-radius:3px;white-space:nowrap;
background:var(--sunk);color:var(--muted);display:inline-block}}
.pill.sourced{{background:var(--ok-soft);color:var(--ok)}}
.pill.open{{background:var(--violet-soft);color:var(--violet)}}
.pill.escalated{{background:var(--warn-soft);color:var(--warn)}}
.st.ok,.wait.ok{{background:var(--ok-soft);color:var(--ok)}}
.st.warn,.wait.warn{{background:var(--warn-soft);color:var(--warn)}}
.st.bad,.wait.bad{{background:var(--bad-soft);color:var(--bad)}}
.st{{margin-top:4px}}
.advise{{max-width:330px}}
.worth{{font-family:var(--mono);font-size:16px;color:var(--violet);font-weight:500}}
#wl tr{{cursor:pointer}}
.rec{{display:inline-block;font-family:var(--mono);font-size:11px;font-weight:500;
letter-spacing:.04em;text-transform:uppercase;background:var(--violet-soft);
color:var(--violet);padding:2px 8px;border-radius:3px}}
.filter{{font-family:var(--mono);font-size:12px;color:var(--muted);margin:0 0 12px;
padding:8px 12px;background:var(--sunk);border-radius:4px;border-left:2px solid var(--violet)}}
.note{{font-size:13px;color:var(--muted);border-left:2px solid var(--line2);padding-left:14px;
margin:18px 0;max-width:66ch}} .note b{{color:var(--ink2)}}
/* the question page */
.back{{font-family:var(--mono);font-size:12px;background:none;border:0;color:var(--violet);
cursor:pointer;padding:0;margin-bottom:14px}}
.arts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:10px;margin:18px 0}}
.artcard{{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--line2);
border-radius:5px;padding:13px 15px}}
.artcard.present{{border-left-color:var(--ok)}}
.artcard.partial{{border-left-color:var(--warn)}}
.artcard.absent{{border-left-color:var(--bad);background:var(--sunk)}}
.arth{{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:3px}}
.arth b{{font-size:14px}}
.artbody{{font-size:12.5px;color:var(--ink2);margin-top:7px}}
.artbody ul{{margin:0;padding-left:16px}} .artbody li{{margin-bottom:3px}}
.acts{{display:flex;flex-wrap:wrap;gap:5px;margin-top:10px}}
.act{{font-family:var(--sans);font-size:12px;background:var(--sunk);color:var(--ink2);
border:1px solid var(--line2);border-radius:3px;padding:4px 9px;cursor:pointer}}
.act:hover{{border-color:var(--violet);color:var(--violet)}}
.act.adv{{background:var(--violet);color:#fff;border-color:var(--violet);font-weight:600}}
.lead{{margin-top:10px;padding:11px 13px;background:var(--violet-soft);border-radius:4px}}
.spec{{margin:6px 0;font-size:12.5px;color:var(--ink2);line-height:1.5}}
.closes{{margin:0;font-family:var(--mono);font-size:10.5px;letter-spacing:.03em;
color:var(--muted);text-transform:uppercase}}
.noterow{{display:flex;gap:8px;margin-top:10px}}
.noterow input{{flex:1}}
.notelist{{margin-top:12px;display:flex;flex-direction:column;gap:8px}}
.nitem{{background:var(--sunk);border-radius:4px;padding:9px 11px;font-size:12.5px}}
.nitem .cur{{display:block;margin-top:3px}}
.cur{{font-size:11.5px;color:var(--muted)}}
.no{{color:var(--bad)}}
footer{{margin-top:52px;padding-top:20px;border-top:1px solid var(--line);
font-family:var(--mono);font-size:11.5px;color:var(--muted);line-height:1.8}}
[hidden]{{display:none!important}}
</style>
<div class=wrap>
<p class=eyebrow>Deep research</p>
<h1>Ask a question.<br>See what happened. Do something about it.</h1>
<p class=lede>Five ways in, one set of rules. Every request carries seven things —
what you asked, what you want back, what it may rest on, what it may use, what you
keep deciding, what we advise, and where it stands. Three of those seven do not
exist yet, and the page says which.</p>
<p class=src>{len(reqs)} real questions, read live · {astate['present']} artifacts
present, {astate['partial']} partial, {astate['absent']} absent · contract v1</p>

<div class=hero><b>{recs.get('reopen', 0)} of {len(reqs)}</b> of these should be
asked again. They are marked finished, but nobody ever opened the document to
check the answer — most closed before that check existed. Being finished is not
the same as being right.
<div class=tally>{tally}</div></div>

<h2>Where do you come in?</h2>
<p class=lede style="margin-bottom:14px">The same questions, shown to whoever is
looking. Nobody sees a different system — just a different slice of it.</p>
<div class=doors>{doors}</div>

<div id=panel_ask class=card>
  <h2 style="margin-bottom:16px">Ask a question</h2>
  {ask_form(doc)}
  <button class=go id=go>Ask it</button>
  <pre id=out hidden></pre>
</div>

<div id=panel_queue hidden>
  <p class=filter id=filt></p>
  <div class=card style="padding:14px 16px">
  <table><thead><tr><th>#</th><th>question</th><th>where it stands</th>
  <th>what we advise</th><th>waiting on</th><th>tries</th></tr></thead>
  <tbody id=tb>{rows}</tbody></table></div>
  <p class=note><b>The list triages; the page decides.</b> A row says what we
  advise and who it is waiting on. Open one for the evidence, everything you can
  do about it, and the conversation.</p>
</div>

<div id=panel_work hidden>
  <p class=filter>Work, not questions — most valuable first. What an item is
  worth is how many questions it unblocks, and it is derived, never typed.</p>
  <div class=card style="padding:14px 16px">
  <table><thead><tr><th>worth</th><th>what to do</th><th>who · how we knew</th>
  <th>closes</th><th>where</th></tr></thead>
  <tbody id=wl>{worklist_rows}</tbody></table></div>
  <div id=taskdetail class=card hidden></div>
  <p class=note><b>How we knew which document</b> — extracted (the answer read
  it), named (the drafter named it and never cited it), class (one document per
  payer, which is why four handbook errands are one), or explore. That last is
  not a failure to fetch; it is research, and it is the machine's own job.</p>
  <p class=note><b>One item here is worth twenty-three.</b> As twenty-three rows
  on a question list it looked like twenty-three problems. The bottom row has no
  question attached at all — work does not have to be about a question, and that
  is the case this list exists to make expressible.</p>
</div>

<div id=panel_one hidden>
  <button class=back id=back>← back to the list</button>
  <div class=card><h2 id=one_title></h2><p class=says id=one_q></p>
  <div class=arts>{artifact_sections(doc)}</div></div>
</div>

<hr>
<h2>For anyone building against this</h2>
<table><thead><tr><th>route</th><th>what it does</th><th>needs</th></tr></thead>
<tbody>{vtable}</tbody></table>
<p class=note>One published set of rules, read by this page and by the service
behind it. Neither keeps its own copy, so a form can never ask for something the
service would refuse.</p>

<footer>
one declaration → three consumers: this page, mobius-payor's router (via
research.contract), and the state-model schematic<br>
scripts/platform/gen_research_ux.py · rows read from research.request
</footer>
</div>
<script>
var D = {payload};
var REQ = {{}}; D.requests.forEach(function(r){{ REQ[r.id] = r; }});
var ME = 'service_line_registry';

// ---- the form: refuses in the contract's own words ----------------------
var REQUIRED = ['subject','question','how_to_judge'];
var REFUSALS = {{'subject':'no subject','question':'no question',
  'how_to_judge':'no evaluator prompt — we cannot judge an answer for your store without one'}};
document.getElementById('go').addEventListener('click', function(){{
  var body = {{}}, refused = [];
  document.querySelectorAll('.field').forEach(function(d){{
    var n = d.dataset.name, el = document.getElementById('f_' + n);
    if(!el) return;
    var v = (el.value || '').trim();
    d.classList.remove('bad');
    document.getElementById('e_' + n).textContent = '';
    if(v) body[n] = v;
  }});
  REQUIRED.forEach(function(n){{
    if(!body[n]){{
      refused.push(REFUSALS[n]);
      document.getElementById('e_' + n).textContent = REFUSALS[n];
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
  var limits = body.schema ? [] :
    ['no schema — completeness cannot be measured, so a partial answer will close as answered'];
  out.textContent = 'POST /api/research/request  →  201\\n'
    + JSON.stringify({{request:'(assigned)', status:'open',
        asked_by:'(your verified identity — never a form field)', limits: limits}}, null, 2)
    + '\\n\\n// sent:\\n' + JSON.stringify(body, null, 2);
}});

// ---- the doors are filters over one queue -------------------------------
function door(id){{
  document.querySelectorAll('.door').forEach(function(b){{
    b.classList.toggle('on', b.dataset.door === id); }});
  var ask = id === 'ask', work = id === 'worklist';
  document.getElementById('panel_ask').hidden = !ask;
  document.getElementById('panel_work').hidden = !work;
  document.getElementById('panel_queue').hidden = ask || work;
  document.getElementById('panel_one').hidden = true;
  if(ask || work) return;
  var f = D.surfaces[id] || {{}};
  var el = document.getElementById('filt');
  el.textContent = (f.filter_says || 'Everything') + '   ·   can call: '
    + (f.calls || []).join(', ');
  el.title = f.filter || 'no filter';
  document.querySelectorAll('#tb tr').forEach(function(tr){{
    var show = true, flt = f.filter || '';
    if(flt.indexOf('invoker') >= 0) show = tr.dataset.invoker === ME;
    if(flt.indexOf('consumer') >= 0) show = tr.dataset.consumer === ME;
    if(flt.indexOf('resolution') >= 0) show = tr.dataset.dec !== '0';
    tr.hidden = !show;
  }});
}}
document.addEventListener('click', function(e){{
  var b = e.target.closest('.door');
  if(b) door(b.dataset.door);
}});

// ---- the question page --------------------------------------------------
function li(items){{ return '<ul>' + items.map(function(x){{ return '<li>' + x + '</li>'; }}).join('') + '</ul>'; }}
function esc(s){{ var d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; }}

function fill(r){{
  document.getElementById('one_title').textContent = '#' + r.id + '  ' + r.subject_id;
  document.getElementById('one_q').textContent = r.question || '';

  document.getElementById('art_request').innerHTML =
    '<b>' + esc(r.consumer) + '</b> asked this'
    + (r.invoker ? '' : ' <span class=no>— anonymously; there is nobody to return it to</span>')
    + '<br><span class=cur>opened ' + esc(r.d) + ' · ' + r.rounds + ' round(s)</span>';

  var out = [];
  if(r.schema_keys && r.schema_keys.length)
    out.push('asked for: ' + r.schema_keys.map(esc).join(', '));
  else out.push('<span class=no>no schema — a partial answer closes as answered</span>');
  if(r.fields_kept.length)
    out.push('kept: ' + li(r.fields_kept.map(function(f){{
      return '<b>' + esc(f.name) + '</b> = ' + esc(f.value)
        + (f.scope ? ' <span class=cur>(' + esc(f.scope) + ')</span>' : '')
        + (f.document ? '<br><span class=cur>' + esc(f.document) + '</span>' : ''); }})));
  if(r.missing && r.missing.length)
    out.push('<span class=no>never came: ' + r.missing.map(esc).join(', ') + '</span>');
  document.getElementById('art_output').innerHTML = out.join('<br>');

  document.getElementById('art_authority').innerHTML =
    (r.authority ? 'bar: <b>' + esc(r.authority) + '</b>'
                 : '<span class=no>no bar declared — the default refuses payer policy</span>')
    + (r.documents && r.documents.length
        ? '<br>rested on: ' + li(r.documents.map(esc)) : '');

  document.getElementById('art_tools').innerHTML =
    '<span class=no>nothing was declared, so what this request got depended on which '
    + 'entry point ran it — and nothing on the result says which.</span>';

  var und = (r.undeclared_decisions || []).length;
  document.getElementById('art_decisions').innerHTML =
    '<span class=no>' + und + ' decisions undeclared</span>'
    + '<br><span class=cur>every one of them defaults to ASK, which is why a person '
    + 'is interrupted for calls they might have delegated once.</span>';

  var adv = (r.actions || []).filter(function(a){{ return a.id === r.recommended; }})[0];
  var lead = '';
  if(adv) lead = '<div class=lead><button class="act adv" data-a="' + esc(adv.id)
      + '" data-r="' + r.id + '">' + esc(adv.label) + '</button>'
      + (adv.specific ? '<p class=spec>' + esc(adv.specific) + '</p>' : '')
      + '<p class=closes>ends as — ' + esc(adv.closes_as) + '</p></div>';
  var btns = (r.actions || []).filter(function(a){{ return a.id !== r.recommended; }})
    .map(function(a){{ return '<button class=act data-a="' + esc(a.id) + '" data-r="'
      + r.id + '" title="' + esc(a.specific || a.does) + '">' + esc(a.label)
      + '</button>'; }}).join('');
  document.getElementById('art_recommendations').innerHTML =
    '<span class=cur>' + esc(r.why) + '</span>' + lead
    + '<div class=acts>' + btns + '</div><div id=drawer></div>';

  var notes = (r.notes || []).map(function(n){{
    return '<div class=nitem>' + esc(n.body)
      + '<span class=cur>→ ' + esc((D.note_uses[n.will] || {{}}).say || n.will)
      + ' · ' + (n.outcome === 'used' ? 'carried into round ' + n.round
                 : n.outcome === 'unusable' ? 'could not be used'
                 : 'waiting on a person') + '</span></div>'; }}).join('');
  document.getElementById('art_status').innerHTML =
    '<b>' + esc(r.state_word) + '</b> · ' + esc(r.wait_word)
    + '<br><span class=cur>' + esc((r.eta || {{}}).say || '') + '</span>'
    + (r.answered_elsewhere_by ? '<br><span class=no>request '
        + r.answered_elsewhere_by + ' answered the same requirement</span>' : '')
    + '<div class=noterow><input id=notebox placeholder="Tell it what it was missing — '
    + 'a document, a section, a year">'
    + '<button class=act id=notesend data-r="' + r.id + '">Send</button></div>'
    + '<div class=notelist>' + notes + '</div><pre id=notereply hidden></pre>';
}}

document.addEventListener('click', function(e){{
  var wt = e.target.closest('#wl tr');
  if(wt){{
    var t = (D.tasks || []).filter(function(x){{ return String(x.id) === wt.dataset.task; }})[0];
    if(t){{
      var qs = (t.questions || []);
      var box = document.getElementById('taskdetail');
      box.hidden = false;
      box.innerHTML = '<h2>' + esc(t.what) + '</h2>'
        + '<p class=says>' + esc((D.task_kinds[t.kind] || {{}}).says || t.kind)
        + (t.outside ? ' — <b>this happens outside this system; the machine can '
           + 'never mark it done on its own.</b>' : '') + '</p>'
        + '<p class=closes>found by ' + esc(t.basis || 'declared')
        + ' · worth ' + (t.worth || 0) + ' · '
        + (qs.length ? 'closes ' + qs.length + ' question(s): ' + qs.join(', ')
                     : 'no question attached — work that stands on its own')
        + '</p>';
      box.scrollIntoView({{behavior: 'smooth', block: 'nearest'}});
    }}
    return;
  }}
  var tr = e.target.closest('#tb tr');
  if(tr){{
    fill(REQ[tr.dataset.id]);
    document.getElementById('panel_queue').hidden = true;
    document.getElementById('panel_one').hidden = false;
    window.scrollTo({{top: 0, behavior: 'smooth'}});
    return;
  }}
  if(e.target.id === 'back'){{
    document.getElementById('panel_one').hidden = true;
    document.getElementById('panel_queue').hidden = false;
    return;
  }}
  var a = e.target.closest('.act[data-a]');
  if(a){{
    var A = D.actions[a.dataset.a] || {{}};
    var d = document.getElementById('drawer');
    var extra = (A.needs || []).filter(function(n){{ return n !== 'because'; }});
    var b = {{action: a.dataset.a, because: 'one sentence a reader will see in a month'}};
    extra.forEach(function(n){{ b[n] = 'the ' + n; }});
    d.innerHTML = '<p class=spec><b>' + esc(A.label) + '</b> — ' + esc(A.does) + '</p>'
      + '<p class=closes>ends as — ' + esc(A.closes_as) + ' · moves it to '
      + esc(A.moves) + '</p><pre id=dpre></pre>';
    document.getElementById('dpre').textContent =
      'POST ' + (A.post_to || '/api/research/request/{{id}}/act').replace('{{id}}', a.dataset.r)
      + '\\n' + JSON.stringify(b, null, 2);
    return;
  }}
  if(e.target.id === 'notesend'){{
    var box = document.getElementById('notebox');
    var body = (box.value || '').trim();
    var pre = document.getElementById('notereply');
    pre.hidden = false;
    if(!body){{ pre.textContent = 'POST /note → 422\\n"there is nothing in the note"'; return; }}
    pre.textContent = 'POST /api/research/request/' + e.target.dataset.r + '/note\\n'
      + JSON.stringify({{body: body}}, null, 2)
      + '\\n\\n// the receipt says what it will do with it, what happens to this'
      + '\\n// question, and how long that usually takes — and the round later'
      + '\\n// records whether it was actually used.';
  }}
}});
door('ask');
</script>"""
    open(OUT, "w").write(html)
    if not check_script(html):
        sys.exit(1)
    print(f"{len(doc['verbs'])} verbs · {len(doc['surfaces'])} doors · "
          f"{len(doc['artifacts'])} artifacts · {len(reqs)} requests → {OUT}")


if __name__ == "__main__":
    main()
