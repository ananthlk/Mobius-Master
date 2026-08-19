"""Render the Deep Research console from research.* — no hand-authored data."""
import json
from datetime import date

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = "/Users/ananth/Mobius/"
OUT = ROOT + "docs/product-docs/deep-research-console.html"
DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open(ROOT + "mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")


def gather():
    c = psycopg2.connect(DB)
    cur = c.cursor(cursor_factory=RealDictCursor)
    d = {}

    cur.execute("""select r.id, r.consumer, r.subject_id, r.question, r.expects,
                          r.status, r.created_at
                     from research.request r order by r.id""")
    d["requests"] = [dict(x) for x in cur.fetchall()]

    cur.execute("""select a.request_id, a.round, a.asked, a.answered_by, a.sources_seen,
                          a.top_documents, a.outcome, a.reason, a.statement, a.quote,
                          a.source_document
                     from research.attempt a order by a.request_id, a.round""")
    d["attempts"] = [dict(x) for x in cur.fetchall()]

    cur.execute("""select g.id, g.request_id, g.gap_class, g.evidence,
                          g.candidate_document, g.candidate_url,
                          g.candidate_document_id is not null as held
                     from research.gap g order by g.id""")
    d["gaps"] = [dict(x) for x in cur.fetchall()]

    cur.execute("""select rp.gap_id, rp.action, rp.state, rp.detail, rp.error
                     from research.repair rp order by rp.id""")
    d["repairs"] = [dict(x) for x in cur.fetchall()]

    cur.execute("""select e.request_id, e.reason, e.asked, e.what_we_checked, e.state
                     from research.escalation e order by e.id""")
    d["escalations"] = [dict(x) for x in cur.fetchall()]

    cur.execute("""select dr.id, dr.url, dr.filename, dr.discovery_reason,
                          dr.document_stated_date, dr.outcome, dr.detail
                     from research.discovery_request dr order by dr.id""")
    d["discovery"] = [dict(x) for x in cur.fetchall()]

    cur.execute("""select discovery_reason, metric, value_before, value_after, verdict,
                          submitted, documents_created, already_had, rejected
                     from research.discovery_effect order by discovery_reason""")
    d["effect"] = [dict(x) for x in cur.fetchall()]

    cur.execute("""select gap_class, count(*) n from research.gap group by 1""")
    d["gap_profile"] = {x["gap_class"]: x["n"] for x in cur.fetchall()}

    # The consumer's own backlog, so the console shows what the loop is for.
    cur.execute("""select count(*) filter (where sourced) s,
                          count(*) filter (where not sourced) u
                     from service_line.standard_requirement""")
    r = cur.fetchone()
    d["consumer_backlog"] = {"sourced": r["s"], "unsourced": r["u"]}
    c.close()
    return d


def jdefault(o):
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


HEAD = """<title>Mobius Deep Research — console</title>
<style>
:root{
  --ground:#fbfbfd; --surface:#fff; --surface-2:#f4f4f8; --surface-3:#eceaf2;
  --line:#e3e3ec; --line-strong:#cfcfdc;
  --ink:#16161d; --ink-2:#54546a; --ink-3:#8b8b9e;
  --accent:#6d28d9; --accent-soft:#ede9fe; --accent-line:#c4b5fd;
  --ok:#0f7a52; --ok-bg:#d8f0e4; --ok-line:#8fd3b6;
  --warn:#8a5600; --warn-bg:#fbeed2; --warn-line:#e6c68a;
  --crit:#a1213a; --crit-bg:#fbe2e8; --crit-line:#eda9b9;
  --info:#1d4e89; --info-bg:#dbe9f8; --info-line:#9dc0e5;
  --shadow:0 1px 2px rgba(20,20,40,.05),0 4px 16px rgba(20,20,40,.05);
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --ground:#0e0e14; --surface:#15151e; --surface-2:#1c1c28; --surface-3:#242433;
  --line:#2b2b3a; --line-strong:#3a3a4d;
  --ink:#ecebf4; --ink-2:#a6a4bb; --ink-3:#74728a;
  --accent:#a78bfa; --accent-soft:#291f42; --accent-line:#5b4a8f;
  --ok:#5ed39b; --ok-bg:#123227; --ok-line:#2c6b50;
  --warn:#e0aa54; --warn-bg:#33270f; --warn-line:#6d5427;
  --crit:#f08099; --crit-bg:#361620; --crit-line:#78313f;
  --info:#7fb3ea; --info-bg:#12243a; --info-line:#2f5580;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 4px 16px rgba(0,0,0,.3);
}}
:root[data-theme="dark"]{
  --ground:#0e0e14; --surface:#15151e; --surface-2:#1c1c28; --surface-3:#242433;
  --line:#2b2b3a; --line-strong:#3a3a4d;
  --ink:#ecebf4; --ink-2:#a6a4bb; --ink-3:#74728a;
  --accent:#a78bfa; --accent-soft:#291f42; --accent-line:#5b4a8f;
  --ok:#5ed39b; --ok-bg:#123227; --ok-line:#2c6b50;
  --warn:#e0aa54; --warn-bg:#33270f; --warn-line:#6d5427;
  --crit:#f08099; --crit-bg:#361620; --crit-line:#78313f;
  --info:#7fb3ea; --info-bg:#12243a; --info-line:#2f5580;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 4px 16px rgba(0,0,0,.3);
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--sans);
     font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
code,.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
h1,h2,h3{margin:0;text-wrap:balance}
.wrap{max-width:1180px;margin:0 auto;padding:30px 26px 70px;display:flex;flex-direction:column;gap:26px}
header{display:flex;flex-direction:column;gap:7px;max-width:80ch}
.mk{font-family:var(--mono);font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}
header h1{font-size:23px;font-weight:650;letter-spacing:-.02em}
header p{margin:0;color:var(--ink-2);font-size:13.5px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:9px;box-shadow:var(--shadow);overflow:hidden}
.ch{padding:11px 16px;border-bottom:1px solid var(--line);background:var(--surface-2);
    display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.ch h3{font-size:12.5px;font-weight:620}
.ch .hint{margin-left:auto;font-size:11.5px;color:var(--ink-3)}
.cb{padding:16px}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th,td{text-align:left;padding:8px 11px;border-bottom:1px solid var(--line);vertical-align:top}
thead th{font-family:var(--mono);font-size:10px;letter-spacing:.09em;text-transform:uppercase;
         color:var(--ink-3);font-weight:500;background:var(--surface-2);
         border-bottom:1px solid var(--line-strong);white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:var(--surface-2)}
td.num{text-align:right;font-family:var(--mono);white-space:nowrap}
.pill{display:inline-flex;align-items:center;gap:5px;font-family:var(--mono);font-size:10px;
      letter-spacing:.07em;text-transform:uppercase;padding:2px 8px;border-radius:99px;
      border:1px solid transparent;white-space:nowrap}
.pill .d{width:5px;height:5px;border-radius:50%}
.p-ok{background:var(--ok-bg);color:var(--ok);border-color:var(--ok-line)}.p-ok .d{background:var(--ok)}
.p-warn{background:var(--warn-bg);color:var(--warn);border-color:var(--warn-line)}.p-warn .d{background:var(--warn)}
.p-crit{background:var(--crit-bg);color:var(--crit);border-color:var(--crit-line)}.p-crit .d{background:var(--crit)}
.p-info{background:var(--info-bg);color:var(--info);border-color:var(--info-line)}.p-info .d{background:var(--info)}
.p-mute{background:var(--surface-2);color:var(--ink-3);border-color:var(--line)}.p-mute .d{background:var(--ink-3)}
/* the loop */
.loop{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:1px;background:var(--line)}
.step{background:var(--surface);padding:14px 15px;display:flex;flex-direction:column;gap:4px;position:relative}
.step .k{font-family:var(--mono);font-size:9.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--ink-3)}
.step .v{font-size:24px;font-weight:650;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.step .n{font-size:11.5px;color:var(--ink-3);line-height:1.4}
.step.term .v{color:var(--crit)}
.step.good .v{color:var(--ok)}
/* gap classes */
.classes{display:grid;grid-template-columns:repeat(auto-fit,minmax(238px,1fr));gap:14px}
.gclass{border:1px solid var(--line);border-radius:8px;padding:13px 15px;display:flex;flex-direction:column;gap:6px;background:var(--surface)}
.gclass .top{display:flex;align-items:baseline;gap:9px}
.gclass .nm{font-family:var(--mono);font-size:11.5px;font-weight:620}
.gclass .ct{margin-left:auto;font-size:20px;font-weight:650;font-variant-numeric:tabular-nums}
.gclass .fix{font-size:12px;color:var(--ink-2)}
.gclass .fix b{color:var(--ink);font-weight:620}
.gclass.zero{opacity:.55}
.note{font-size:12.5px;color:var(--ink-2);border-left:2px solid var(--accent-line);padding:2px 0 2px 12px;max-width:80ch}
.note b{color:var(--ink);font-weight:620}
.note.warn{border-left-color:var(--warn-line)}
.ev{font-size:12px;color:var(--ink-2);line-height:1.6}
.rule{display:flex;gap:10px;padding:9px 0;border-bottom:1px dashed var(--line);font-size:12.5px}
.rule:last-child{border-bottom:0}
.rule .n{font-family:var(--mono);font-size:10.5px;color:var(--ink-3);flex:none;width:16px}
.rule .t b{color:var(--ink)}
.rule .t{color:var(--ink-2)}
.kv{font-family:var(--mono);font-size:11px;color:var(--ink-3)}
</style>
"""


def esc(s):
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;")


def render(d):
    gp = d["gap_profile"]
    reqs, atts = d["requests"], d["attempts"]
    disc, eff = d["discovery"], d["effect"]
    esc_rows = d["escalations"]
    backlog = d["consumer_backlog"]

    CLASSES = [
        ("not_in_corpus", "the document is not here",
         "<b>acquire</b> — submit to Discovery with the gap cited"),
        ("not_retrievable", "held, but mis-tagged or unindexed",
         "<b>repair</b> — retag or reindex; no fetching"),
        ("vocabulary", "asked with words the source does not use",
         "<b>lexicon alias</b> — then re-ask, still no fetching"),
        ("absent_from_source", "the source is genuinely silent",
         "<b>escalate</b> — a human decides; fetching cannot help"),
    ]
    cls_html = "".join(
        f'<div class="gclass{"" if gp.get(k) else " zero"}"><div class="top">'
        f'<span class="nm">{k}</span><span class="ct">{gp.get(k, 0)}</span></div>'
        f'<div class="ev">{esc(what)}</div><div class="fix">{fix}</div></div>'
        for k, what, fix in CLASSES)

    att_html = "".join(
        f'<tr><td class="mono">{a["request_id"]}.{a["round"]}</td>'
        f'<td>{esc((a["asked"] or "")[:120])}</td>'
        f'<td class="num">{a["sources_seen"]}</td>'
        f'<td><span class="pill p-{"ok" if a["outcome"]=="extracted" else "crit" if a["outcome"] in ("no_retrieval","error") else "warn"}">'
        f'<span class="d"></span>{a["outcome"]}</span></td>'
        f'<td class="ev">{esc((a["reason"] or a["statement"] or "")[:150])}</td></tr>'
        for a in atts) or '<tr><td colspan="5" class="ev">no attempts yet</td></tr>'

    OUT_PILL = {"created": "ok", "duplicate": "ok", "ours": "ok",
                "rejected": "crit", "pending": "mute", "error": "crit"}
    disc_html = "".join(
        f'<tr><td class="mono">#{x["id"]}</td>'
        f'<td>{esc((x["filename"] or x["url"])[:54])}</td>'
        f'<td class="mono" style="font-size:11px">{esc(x["discovery_reason"])}</td>'
        f'<td class="mono" style="font-size:11px">{esc(x["document_stated_date"] or "none stated")}</td>'
        f'<td><span class="pill p-{OUT_PILL.get(x["outcome"], "mute")}"><span class="d"></span>'
        f'{x["outcome"]}</span></td></tr>'
        for x in disc) or '<tr><td colspan="5" class="ev">nothing submitted</td></tr>'

    eff_html = ""
    for e in eff:
        if e["value_after"] is None:
            eff_html += (
                f'<tr><td class="mono">{esc(e["discovery_reason"])}</td>'
                f'<td class="ev">{esc(e["metric"])}</td>'
                f'<td class="num">{e["value_before"]:g}</td><td class="num">—</td>'
                f'<td><span class="pill p-mute"><span class="d"></span>not re-measured</span></td>'
                f'<td class="num">{e["submitted"]}</td></tr>')
        else:
            v = e["verdict"]
            eff_html += (
                f'<tr><td class="mono">{esc(e["discovery_reason"])}</td>'
                f'<td class="ev">{esc(e["metric"])}</td>'
                f'<td class="num">{e["value_before"]:g}</td>'
                f'<td class="num">{e["value_after"]:g}</td>'
                f'<td><span class="pill p-{"ok" if v=="moved" else "crit"}"><span class="d"></span>{v}</span></td>'
                f'<td class="num">{e["submitted"]}</td></tr>')
    eff_html = eff_html or '<tr><td colspan="6" class="ev">no batch measured yet</td></tr>'

    esc_html = "".join(
        f'<tr><td>{esc(x["asked"])}</td><td class="mono">{esc(x["reason"])}</td>'
        f'<td class="ev">{esc(x["what_we_checked"])}</td>'
        f'<td><span class="pill p-warn"><span class="d"></span>{x["state"]}</span></td></tr>'
        for x in esc_rows) or '<tr><td colspan="4" class="ev">nothing escalated</td></tr>'

    return HEAD + f"""
<div class="wrap">
  <header>
    <div class="mk">Mobius · deep research</div>
    <h1>Establish a fact, or say precisely why you can't</h1>
    <p>Generic instrument. Ask the corpus through chat; extract only what is grounded;
       when that fails, diagnose <em>why</em> from evidence before acting — because
       "not answered" has four causes and only one of them is a missing document.
       The service line registry is consumer #1; every fact store gets the same loop.</p>
  </header>

  <div class="card"><div class="ch"><h3>The loop</h3>
    <span class="hint">generated from research.* — nothing here is hand-written</span></div>
    <div class="loop">
      <div class="step"><span class="k">1 · asked</span><span class="v">{len(reqs)}</span>
        <span class="n">questions put to chat's ReAct loop, new thread each</span></div>
      <div class="step good"><span class="k">2 · extracted</span>
        <span class="v">{sum(1 for a in atts if a["outcome"] == "extracted")}</span>
        <span class="n">grounded: quote verbatim in the answer, document actually cited</span></div>
      <div class="step"><span class="k">3 · diagnosed</span><span class="v">{len(d["gaps"])}</span>
        <span class="n">gap classified from evidence, not assumed</span></div>
      <div class="step"><span class="k">4 · repaired</span>
        <span class="v">{sum(1 for r in d["repairs"] if r["state"] == "applied")}</span>
        <span class="n">acquire · retag · lexicon alias</span></div>
      <div class="step term"><span class="k">5 · escalated</span><span class="v">{len(esc_rows)}</span>
        <span class="n">a human decides; the trail comes with it</span></div>
    </div>
  </div>

  <div class="card"><div class="ch"><h3>Why it wasn't answered</h3>
    <span class="hint">four causes, four different repairs</span></div>
    <div class="cb"><div class="classes">{cls_html}</div></div>
  </div>

  <div class="note"><b>This split is the whole point.</b> The first gap this loop
    diagnosed asked for place of service on <code>59G-4.028</code>. The policy was already
    ingested (10 pages, 23 chunks); the lexicon already carried the full
    <code>d/place_of_service</code> tree; the document was already tagged at the current
    revision 2440 and already carried <code>place_of_service.inpatient</code> and
    <code>.outpatient</code>. Downloading it again, adding the term again, or retagging would
    each have changed nothing. The rule simply does not state a place of service —
    <code>absent_from_source</code>, escalated.</div>

  <div class="card"><div class="ch"><h3>Chat attempts</h3>
    <span class="hint">deployed ReAct · a new thread per call, so a long run can't accumulate context</span></div>
    <div class="scroll"><table><thead><tr><th>Req.round</th><th>Asked</th>
      <th style="text-align:right">Sources</th><th>Outcome</th><th>Why</th></tr></thead>
      <tbody>{att_html}</tbody></table></div></div>

  <div class="card"><div class="ch"><h3>Discovery submissions</h3>
    <span class="pill p-mute"><span class="d"></span>ingest stubbed</span>
    <span class="hint">MOBIUS_DISCOVERY_INGEST_CONTRACT.md — RAG owns ingest</span></div>
    <div class="scroll"><table><thead><tr><th>#</th><th>Document</th>
      <th>Gap cited</th><th>Date the document states</th><th>Outcome</th></tr></thead>
      <tbody>{disc_html}</tbody></table></div>
    <div class="cb" style="border-top:1px solid var(--line)">
      <div class="rule"><span class="n">1</span><span class="t"><b>Every request names its gap.</b>
        <code>discovery_reason</code> is NOT NULL and a request without one is refused before
        it is written — that is the site-driven crawling the contract forbids.</span></div>
      <div class="rule"><span class="n">2</span><span class="t"><b>No local dedup.</b>
        Byte-identical → <code>duplicate</code> is a <em>success</em>, recorded and never
        retried. Same URL new bytes → submit, it's an edition. Different URL same text →
        submit anyway. A fetcher cannot tell a duplicate from a product variant from a
        period series; the gate decides.</span></div>
      <div class="rule"><span class="n">3</span><span class="t"><b>Only dates the document states.</b>
        There is no computed-date path in this module and no column to put one in.
        Today's <code>/upload</code> outage is the worked example — a default termination
        date invented at upload time, with no provenance, now failing
        <code>ck_documents_term_date_provenance</code> for every caller.</span></div>
    </div>
  </div>

  <div class="card"><div class="ch"><h3>Did the gap move?</h3>
    <span class="hint">re-read the gap you cited — the closing rule</span></div>
    <div class="scroll"><table><thead><tr><th>Gap cited</th><th>Metric</th>
      <th style="text-align:right">Before</th><th style="text-align:right">After</th>
      <th>Verdict</th><th style="text-align:right">Submitted</th></tr></thead>
      <tbody>{eff_html}</tbody></table></div></div>

  <div class="note warn"><b>A batch that fetched 40 documents and moved no gap is a
    finding about the gap, not a success to repeat.</b> The console says
    <code>unmoved</code> out loud rather than reporting documents acquired, because
    documents acquired is not the outcome anyone wanted.</div>

  <div class="card"><div class="ch"><h3>For a human</h3>
    <span class="hint">escalated with the trail, so nobody repeats the checks</span></div>
    <div class="scroll"><table><thead><tr><th>Question</th><th>Class</th>
      <th>What was already checked</th><th>State</th></tr></thead>
      <tbody>{esc_html}</tbody></table></div></div>

  <div class="note">Consumer #1, the service line registry, currently has
    <b>{backlog["unsourced"]}</b> unsourced standard requirements against
    <b>{backlog["sourced"]}</b> sourced. That backlog is what this loop exists to work
    through — and what it must be measured against, not the number of documents it fetches.</div>
</div>
"""


if __name__ == "__main__":
    data = gather()
    open(OUT, "w").write(render(data))
    print(f"wrote {OUT}")
    print("gap classes:", data["gap_profile"])
    print("discovery:", {x["outcome"] for x in data["discovery"]} or "none")
