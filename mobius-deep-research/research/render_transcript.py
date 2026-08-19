"""Render the actual conversation — what was asked, what came back, what the
evaluator made of it, and what it asked next.

Not a dashboard. The exchange itself, in order, with the evaluator's judgment
sitting against the answer it judged so you can disagree with it.
"""
import json
import re

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = "/Users/ananth/Mobius/"
OUT = ROOT + "docs/product-docs/deep-research-transcript.html"
DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open(ROOT + "mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")


def esc(s):
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;")


def chat_envelope(raw: str):
    """Deployed chat answers with a structured envelope, not prose. Show the
    answer as prose and keep mode / unfinished-reason as what they are —
    metadata about how the turn went, which is exactly what a caller needs."""
    try:
        d = json.loads(raw)
    except Exception:
        return raw, {}
    if not isinstance(d, dict):
        return raw, {}
    body = d.get("direct_answer") or d.get("answer") or d.get("message") or raw
    meta = {k: v for k, v in d.items()
            if k in ("mode", "unfinished_reason", "confidence", "citable")
            and v not in (None, "")}
    # some builds inline the unfinished markers in the answer text
    m = re.search(r"Unfinished Reason:\s*(\w+)", body)
    if m:
        meta.setdefault("unfinished_reason", m.group(1))
        body = body[:m.start()].rstrip()
    return body, meta


def md(s):
    """Just enough markdown for chat's answers: headings, bold, code, lists."""
    import re
    s = esc(s)
    s = re.sub(r"^### (.+)$", r"<h4>\1</h4>", s, flags=re.M)
    s = re.sub(r"^## (.+)$", r"<h4>\1</h4>", s, flags=re.M)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"^\s*[-•]\s+(.+)$", r"<li>\1</li>", s, flags=re.M)
    s = re.sub(r"(<li>.*</li>\n?)+", lambda m: f"<ul>{m.group(0)}</ul>", s)
    return "".join(f"<p>{b.strip()}</p>" if not b.strip().startswith(("<h4", "<ul"))
                   else b for b in s.split("\n\n") if b.strip())


HEAD = """<title>Deep Research — the conversation</title>
<style>
:root{
  --ground:#fbfbfd; --surface:#fff; --surface-2:#f4f4f8;
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
  --ground:#0e0e14; --surface:#15151e; --surface-2:#1c1c28;
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
  --ground:#0e0e14; --surface:#15151e; --surface-2:#1c1c28;
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
     font-size:14px;line-height:1.55;-webkit-font-smoothing:antialiased}
code{font-family:var(--mono);font-size:.92em;background:var(--surface-2);
     padding:1px 4px;border-radius:3px;border:1px solid var(--line)}
h1,h4{margin:0;text-wrap:balance}
.wrap{max-width:880px;margin:0 auto;padding:30px 24px 80px;display:flex;flex-direction:column;gap:20px}
header{display:flex;flex-direction:column;gap:6px}
.mk{font-family:var(--mono);font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}
header h1{font-size:22px;font-weight:650;letter-spacing:-.02em}
header p{margin:0;color:var(--ink-2);font-size:13.5px;max-width:74ch}
.subject{display:flex;gap:9px;flex-wrap:wrap;align-items:center;padding:11px 14px;
   background:var(--surface);border:1px solid var(--line);border-radius:8px;font-size:12.5px}
.subject .k{font-family:var(--mono);font-size:10px;letter-spacing:.12em;
   text-transform:uppercase;color:var(--ink-3)}
.turnhead{display:flex;align-items:center;gap:10px;margin-top:14px}
.turnhead .n{font-family:var(--mono);font-size:10.5px;letter-spacing:.13em;
   text-transform:uppercase;color:var(--ink-3)}
.turnhead .bar{flex:1;height:1px;background:var(--line)}
/* messages */
.msg{display:flex;flex-direction:column;gap:6px}
.who{display:flex;align-items:center;gap:8px;font-family:var(--mono);font-size:10px;
   letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.who .dot{width:7px;height:7px;border-radius:50%}
.bubble{border:1px solid var(--line);border-radius:10px;padding:13px 15px;background:var(--surface);
   box-shadow:var(--shadow)}
.bubble p{margin:0 0 9px}
.bubble p:last-child{margin-bottom:0}
.bubble h4{font-size:13px;font-weight:650;margin:10px 0 5px}
.bubble ul{margin:6px 0;padding-left:19px}
.bubble li{margin:2px 0}
.ask .bubble{background:var(--accent-soft);border-color:var(--accent-line)}
.ask .dot{background:var(--accent)}
.answer .dot{background:var(--info)}
.answer .bubble{max-height:420px;overflow-y:auto}
.evalr .dot{background:var(--warn)}
.evalr .bubble{background:var(--surface-2)}
.repair .dot{background:var(--ok)}
.repair .bubble{background:var(--ok-bg);border-color:var(--ok-line)}
.sources{display:flex;flex-wrap:wrap;gap:5px;margin-top:9px;padding-top:9px;border-top:1px solid var(--line)}
.src{font-family:var(--mono);font-size:10.5px;padding:2px 7px;border-radius:4px;
   background:var(--surface-2);border:1px solid var(--line);color:var(--ink-2)}
.verdict{display:flex;gap:10px;align-items:flex-start;margin-bottom:9px}
.pill{display:inline-flex;align-items:center;gap:5px;font-family:var(--mono);font-size:10px;
   letter-spacing:.07em;text-transform:uppercase;padding:2px 8px;border-radius:99px;
   border:1px solid transparent;white-space:nowrap;flex:none}
.pill .d{width:5px;height:5px;border-radius:50%}
.p-ok{background:var(--ok-bg);color:var(--ok);border-color:var(--ok-line)}.p-ok .d{background:var(--ok)}
.p-warn{background:var(--warn-bg);color:var(--warn);border-color:var(--warn-line)}.p-warn .d{background:var(--warn)}
.p-crit{background:var(--crit-bg);color:var(--crit);border-color:var(--crit-line)}.p-crit .d{background:var(--crit)}
.p-info{background:var(--info-bg);color:var(--info);border-color:var(--info-line)}.p-info .d{background:var(--info)}
.p-mute{background:var(--surface-2);color:var(--ink-3);border-color:var(--line)}.p-mute .d{background:var(--ink-3)}
.field{display:grid;grid-template-columns:104px minmax(0,1fr);gap:11px;font-size:12.5px;margin-top:7px}
.field .k{font-family:var(--mono);font-size:10px;letter-spacing:.11em;text-transform:uppercase;color:var(--ink-3)}
blockquote{margin:0;padding-left:11px;border-left:2px solid var(--line-strong);color:var(--ink-2);font-size:12.5px}
.waiting{display:flex;align-items:center;gap:10px;padding:11px 14px;border:1px dashed var(--line-strong);
   border-radius:8px;color:var(--ink-2);font-size:12.5px;background:var(--surface)}
.note{font-size:12.5px;color:var(--ink-2);border-left:2px solid var(--accent-line);
   padding:2px 0 2px 12px;max-width:76ch}
.note b{color:var(--ink);font-weight:620}
</style>
"""


def render(rows, req):
    out = []
    for t in rows:
        a = t.get("attempt") or {}
        ev = a.get("evaluator_verdict") or {}
        out.append(f'<div class="turnhead"><span class="n">Turn {t["n"]}</span>'
                   f'<span class="bar"></span></div>')

        out.append(
            '<div class="msg ask"><div class="who"><span class="dot"></span>'
            'Deep Research → chat &nbsp;·&nbsp; new thread</div>'
            f'<div class="bubble"><p>{esc(t["query"])}</p></div></div>')

        if not a:
            out.append('<div class="waiting"><span class="pill p-mute">'
                       '<span class="d"></span>waiting</span> asked; no answer stored yet</div>')
            continue

        srcs = "".join(f'<span class="src">{esc(s)}</span>'
                       for s in (a.get("top_documents") or []))
        body, meta = chat_envelope(a.get("answer_text") or "(no answer text stored)")
        chips = "".join(
            f'<span class="pill {"p-warn" if k == "unfinished_reason" else "p-mute"}">'
            f'<span class="d"></span>{esc(k.replace("_", " "))}: {esc(v)}</span>'
            for k, v in meta.items())
        out.append(
            '<div class="msg answer"><div class="who"><span class="dot"></span>'
            f'chat &nbsp;·&nbsp; ReAct &nbsp;·&nbsp; {len(a.get("top_documents") or [])} documents cited</div>'
            f'<div class="bubble">{md(body)}'
            + (f'<div class="sources" style="gap:6px">{chips}</div>' if chips else "")
            + (f'<div class="sources">{srcs}</div>' if srcs else "") +
            '</div></div>')

        got = bool(ev.get("extracted"))
        gap = ev.get("gap_class") or "none"
        pill = ("p-ok" if got else
                "p-crit" if gap in ("not_in_corpus", "absent_from_source") else "p-warn")
        body = (f'<div class="verdict"><span class="pill {pill}"><span class="d"></span>'
                f'{"extracted" if got else "rejected"}</span>'
                f'<div>{esc(ev.get("verdict_reason") or a.get("reason") or "")}</div></div>')
        if got:
            body += (f'<div class="field"><span class="k">statement</span>'
                     f'<span>{esc(ev.get("statement"))}</span></div>'
                     f'<div class="field"><span class="k">grounded on</span>'
                     f'<span><blockquote>{esc(ev.get("quote"))}</blockquote>'
                     f'<div style="margin-top:5px"><span class="src">{esc(ev.get("document"))}</span></div>'
                     f'</span></div>')
        else:
            body += (f'<div class="field"><span class="k">gap class</span>'
                     f'<span><code>{esc(gap)}</code></span></div>')
        if ev.get("next_query"):
            body += (f'<div class="field"><span class="k">asks next</span>'
                     f'<span>{esc(ev["next_query"])}</span></div>')
        out.append(
            '<div class="msg evalr"><div class="who"><span class="dot"></span>'
            f'evaluator &nbsp;·&nbsp; invoker\'s prompt &nbsp;·&nbsp; {esc(a.get("model") or "via LLMManager")}'
            f'</div><div class="bubble">{body}</div></div>')

        if t.get("feedback_kind"):
            fb = t["feedback_ref"] or {}
            st = t["feedback_state"]
            out.append(
                '<div class="msg repair"><div class="who"><span class="dot"></span>'
                f'feedback → {esc(t["feedback_kind"])}</div><div class="bubble">'
                f'<div class="verdict"><span class="pill '
                f'{"p-ok" if st == "settled" else "p-info"}"><span class="d"></span>{st}</span>'
                f'<div>{esc(json.dumps(fb))}</div></div>'
                '<div style="font-size:12.5px;color:var(--ink-2);margin-top:7px">'
                'The next turn does not start until this settles — ingest lands in minutes, '
                'a person in days.</div></div></div>')

        if t["status"] in ("running", "waiting") and not got:
            out.append('<div class="waiting"><span class="pill p-info">'
                       '<span class="d"></span>gate</span> waiting for both tracks before turn '
                       f'{t["n"] + 1}</div>')

    return HEAD + f"""
<div class="wrap">
  <header>
    <div class="mk">Mobius · deep research</div>
    <h1>The conversation</h1>
    <p>What was actually asked, what chat actually answered, and what the invoker's
       evaluator made of it. The evaluator sits against the answer it judged, so you can
       disagree with it.</p>
  </header>

  <div class="subject">
    <span class="k">invoker</span><span>{esc(req.get("consumer"))}</span>
    <span class="k">subject</span><code>{esc(req.get("subject_id"))}</code>
    <span class="k">status</span><span>{esc(req.get("status"))}</span>
  </div>

  <div class="note"><b>The evaluator prompt comes from the invoker, not from here.</b>
    Deep Research does not know what a good answer looks like for someone else's fact
    store — a generic evaluator is how you get confidently wrong extractions written to a
    certified store. This one was told: <em>{esc((req.get("evaluator_prompt") or "")[:240])}</em></div>

  {"".join(out)}
</div>
"""


if __name__ == "__main__":
    c = psycopg2.connect(DB)
    cur = c.cursor(cursor_factory=RealDictCursor)
    cur.execute("""select id, consumer, subject_id, status, evaluator_prompt
                     from research.request
                    where evaluator_prompt is not null order by id desc limit 1""")
    req = cur.fetchone()
    cur.execute("""select t.id, t.n, t.query, t.status, t.feedback_kind, t.feedback_state,
                          t.feedback_ref
                     from research.turn t where t.request_id=%s order by t.n""",
                (req["id"],))
    turns = [dict(x) for x in cur.fetchall()]
    for t in turns:
        cur.execute("""select answer_text, top_documents, evaluator_verdict, reason, model
                         from research.attempt where turn_id=%s order by id desc limit 1""",
                    (t["id"],))
        t["attempt"] = dict(cur.fetchone() or {}) or None
    open(OUT, "w").write(render(turns, dict(req)))
    print(f"wrote {OUT} — request {req['id']}, {len(turns)} turns, "
          f"{sum(1 for t in turns if t['attempt'])} with a stored answer")
