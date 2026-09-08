#!/usr/bin/env python3
"""Render the dev schema page. Data is inlined, so the page is a single file."""
import json, sys, html

DATA = sys.argv[1]; OUT = sys.argv[2]
d = json.load(open(DATA))

TPL = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chat turn — dev schema</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
:root{--bg:#0f0d18;--panel:#171325;--panel2:#1e1930;--line:rgba(255,255,255,.12);
 --ink:rgba(255,255,255,.92);--ink2:rgba(255,255,255,.62);--dim:rgba(255,255,255,.40);
 --violet:#a78bfa;--green:#4ade80;--amber:#fbbf24;--red:#f87171;--cyan:#7dd3fc;
 --mono:"JetBrains Mono",ui-monospace,Menlo,monospace;--body:"Inter",system-ui,sans-serif;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 var(--body);-webkit-font-smoothing:antialiased}
.wrap{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:24px;max-width:1500px;margin:0 auto;padding:22px}
@media(max-width:1080px){.wrap{grid-template-columns:1fr}.side{order:-1;position:sticky;top:0;max-height:50vh;overflow:auto;background:var(--bg);z-index:5}}
h1{font-size:19px;margin:0 0 3px;font-weight:650}
.lead{color:var(--dim);font-size:12px;margin:0 0 4px}
.devtag{display:inline-block;font:500 10px var(--mono);color:var(--amber);
 border:1px solid rgba(251,191,36,.4);border-radius:99px;padding:2px 8px;margin-bottom:10px}
.band{border:1px dashed var(--line);border-radius:12px;padding:13px;margin-bottom:16px}
.band-t{font:700 9.5px var(--body);letter-spacing:.08em;text-transform:uppercase;color:var(--violet);margin-bottom:9px}
.chain{display:flex;flex-wrap:wrap;align-items:stretch;gap:7px}
.cnode{flex:1 1 150px;background:var(--panel);border:1px solid var(--line);border-radius:9px;
 padding:9px 11px;cursor:pointer;min-width:140px}
.cnode:hover,.cnode:focus-visible{border-color:var(--violet);outline:none}
.cnode.sel{border-color:var(--violet);background:rgba(167,139,250,.14)}
.cnode.gate{border-color:rgba(248,113,113,.5)}
.cn{font:600 12px var(--body)}
.cs{font-size:9.5px;color:var(--dim);margin-top:2px}
.arr{align-self:center;color:var(--dim)}
.schema{display:flex;flex-direction:column;align-items:center}
.n{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:8px 15px;
 text-align:center;min-width:160px;cursor:pointer}
.n:hover,.n:focus-visible{border-color:var(--violet);outline:none}
.n.sel{border-color:var(--violet);background:rgba(167,139,250,.16)}
.nn{font:600 12px var(--body)} .ns{font-size:9.5px;color:var(--dim);margin-top:1px}
.a{color:var(--dim);font-size:14px;line-height:1.5}
.lanes{display:flex;gap:22px;flex-wrap:wrap;justify-content:center;align-items:flex-start}
.lane{border:1px dashed var(--line);border-radius:11px;padding:12px;min-width:250px;
 display:flex;flex-direction:column;align-items:center}
.lt{font:700 9.5px var(--body);letter-spacing:.07em;text-transform:uppercase;color:var(--violet);margin-bottom:8px}
.ph{width:100%;border-left:2px solid rgba(167,139,250,.4);padding:4px 0 4px 9px;margin:3px 0}
.pn{font:700 10px var(--body);color:var(--ink2)}
.pd{font-size:9.5px;color:var(--dim);margin:1px 0 5px;line-height:1.45}
.chips{display:flex;flex-wrap:wrap;gap:5px}
.chip{font:400 10px var(--body);padding:3px 8px;border-radius:5px;cursor:pointer;
 border:1px solid var(--line);background:rgba(255,255,255,.05);color:var(--ink2)}
.chip:hover,.chip:focus-visible{border-color:var(--violet);outline:none}
.chip.sel{border-color:var(--violet);background:rgba(167,139,250,.2)}
.chip .cfg{color:var(--cyan)} .chip .em{color:var(--green)} .chip .no{color:var(--amber)}
.r-green{box-shadow:inset 3px 0 0 var(--green)} .r-amber{box-shadow:inset 3px 0 0 var(--amber)}
.r-red{box-shadow:inset 3px 0 0 var(--red)}
.pill{display:inline-block;font:700 9px var(--body);letter-spacing:.06em;text-transform:uppercase;
 padding:2px 8px;border-radius:99px;margin-left:6px;vertical-align:2px}
.p-green{background:rgba(74,222,128,.16);color:var(--green)}
.p-amber{background:rgba(251,191,36,.16);color:var(--amber)}
.p-red{background:rgba(248,113,113,.18);color:var(--red)}
.find{margin:5px 0 0;padding-left:15px;font-size:11px;line-height:1.55}
.find li{margin-bottom:5px}
.f-bad::marker{content:"▲ ";color:var(--red)}
.f-watch::marker{content:"▸ ";color:var(--amber)}
.f-good::marker{content:"✓ ";color:var(--green)}
.sigs{display:flex;flex-wrap:wrap;gap:3px 10px;font:400 10px var(--mono);color:var(--dim)}
.sigs b{color:var(--ink2);font-weight:500}
.depth{font:400 9.5px var(--mono);color:var(--dim)}
.side{position:sticky;top:14px;align-self:start;max-height:calc(100vh - 28px);overflow-y:auto}
.card{border:1px solid rgba(167,139,250,.35);border-radius:12px;padding:15px 17px;background:rgba(167,139,250,.07)}
.card h3{margin:0 0 2px;font-size:15px}
.card .mod{font:400 10px var(--mono);color:var(--dim)}
.card .desc{font-size:12px;color:var(--ink2);margin:8px 0 12px;white-space:pre-wrap;max-height:230px;overflow:auto}
.f{margin-top:11px}
.f b{display:block;font:700 9.5px var(--body);letter-spacing:.07em;text-transform:uppercase;color:var(--violet);margin-bottom:3px}
.f div{font-size:11px;color:var(--ink2);line-height:1.55;overflow-wrap:anywhere}
.f .m{font-family:var(--mono);font-size:10.5px;color:var(--dim)}
.none{color:var(--amber)}
.legend{font-size:10px;color:var(--dim);text-align:center;margin-top:10px}
</style></head><body><div class="wrap"><div>
<h1>How a chat turn actually runs</h1>
<span class="devtag">DEV BUILD — local only, nothing deployed</span>
<p class="lead" id="lead"></p>
<div class="band"><div class="band-t">Before the pipeline — the part the shipped diagram omits</div>
<div class="chain" id="chain"></div></div>
<div class="band"><div class="band-t">Inside run_pipeline</div><div class="schema" id="schema"></div>
<p class="legend">● emits its own signals&nbsp; ◦ observable only through its caller&nbsp; ⚙ has env-var config<br>left edge: <span style="color:var(--green)">green</span> ready · <span style="color:var(--amber)">amber</span> named weakness · <span style="color:var(--red)">red</span> failure here is invisible or unbounded</p></div>
<div class="band"><div class="band-t">Cross-cutting — under every step, not a step</div>
<div class="chain" id="cross"></div></div>
</div><div class="side"><div id="detail"></div>
<p class="legend" style="text-align:left;margin-top:9px">Click anything. This panel follows you down the page.</p>
</div></div>
<script>
var D = __DATA__;
var SUB={}, SEL=null;
D.submodules.forEach(function(m){ SUB[m.module.split('.').pop()]=m; });
D.cross_cutting.forEach(function(c){ SUB[c.id]=c; });
D.chain.forEach(function(c){ SUB['chain:'+c.step]=c; });
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
document.getElementById('lead').textContent =
  D.submodules.length+' sub-modules, '+D.chain.length+' hops before the pipeline, '+
  D.cross_cutting.length+' cross-cutting. Generated by '+D.generated_by+'.';

function marks(m){
  var s='';
  if(m.telemetry && m.telemetry.length) s+=' <span class="em">●</span>'; else if(m.module) s+=' <span class="no">◦</span>';
  if(m.config && m.config.length) s+=' <span class="cfg">⚙</span>';
  return s;
}
function rc(m){ return m && m.rating ? ' r-'+m.rating : ''; }
function chip(name){ var m=SUB[name]||{};
  return '<span class="chip'+rc(m)+'" data-k="'+esc(name)+'" tabindex="0" role="button">'+esc(name)+marks(m)+'</span>'; }
function node(name,sub,key){ var m=SUB[key||name]||{};
  return '<div class="n'+rc(m)+'" data-k="'+esc(key||name)+'" tabindex="0" role="button"><div class="nn">'+
    esc(name)+'</div>'+(sub?'<div class="ns">'+esc(sub)+'</div>':'')+'</div>'; }
var A='<div class="a">↓</div>';

document.getElementById('chain').innerHTML = D.chain.map(function(c,i){
  return '<div class="cnode '+(c.kind==='gate'?'gate':'')+rc(SUB['chain:'+c.step])+'" data-k="chain:'+esc(c.step)+'" tabindex="0" role="button">'+
    '<div class="cn">'+esc(c.step)+(c.config.length?' <span class="cfg">⚙</span>':'')+'</div>'+
    '<div class="cs">'+esc(c.path)+(c.line?':'+c.line:'')+'</div></div>'+
    (i<D.chain.length-1?'<span class="arr">→</span>':''); }).join('');

document.getElementById('cross').innerHTML = D.cross_cutting.map(function(c){
  return '<div class="cnode'+rc(c)+'" data-k="'+esc(c.id)+'" tabindex="0" role="button">'+
    '<div class="cn">'+esc(c.id)+(c.config.length?' <span class="cfg">⚙</span>':'')+'</div>'+
    '<div class="cs">'+esc(c.path)+' · called by '+c.fan_in+'</div></div>'; }).join('');

var f=D.flow, strip=function(x){return x.replace(/^run_/,'');};
var h='<div class="schema">';
(f.shared_pre||[]).forEach(function(x){ h+=node(strip(x),'always runs')+A; });
h+='<div class="n" style="cursor:default;border-style:dashed"><div class="nn">'+f.branch_on+' ?</div>'+
   '<div class="ns">orchestrator.py:'+f.branch_line+'</div></div>'+A+'<div class="lanes">';
h+='<div class="lane"><div class="lt">ReAct path</div>'+node('react_loop','replaces plan + resolve');
(f.react_phases||[]).forEach(function(p){
  h+='<div class="ph"><div class="pn">'+esc(p.phase)+'</div><div class="pd">'+esc(p.note)+
     (p.cite?' <span style="opacity:.6">react_loop.py:'+p.cite+'</span>':'')+'</div>'+
     '<div class="chips">'+(p.modules||[]).map(chip).join('')+'</div></div>'; });
h+='</div><div class="lane"><div class="lt">Classic path</div>';
(f.classic_path||[]).forEach(function(x,i){ h+=node(strip(x))+(i<f.classic_path.length-1?A:''); });
h+='</div></div>';
(f.shared_post||[]).forEach(function(x){ h+=A+node(strip(x),'both paths');
  if(strip(x)==='integrate' && D.integrate_passes){
    h+='<div class="ph" style="max-width:420px;margin-top:6px"><div class="pn">three LLM calls, not one step</div>'+
       D.integrate_passes.map(function(p){
         return '<div class="pd"><b style="color:var(--ink2)">'+esc(p.id)+'</b> · '+esc(p.label)+' — '+esc(p.what)+
                (p.skippable?' <span style="color:var(--amber)">'+esc(p.skippable)+'</span>':'')+'</div>'; }).join('')+
       '<div class="pd" style="color:var(--cyan)">'+esc(D.integrate_modes.mode)+'</div>'+
       '<div class="pd" style="color:var(--cyan)">'+esc(D.integrate_modes.dynamic_enrichment)+'</div></div>';
  }
});
if(f.shared_post_guard) h+='<div class="pd" style="max-width:340px;text-align:center;color:var(--amber)">'+esc(f.shared_post_guard)+'</div>';
h+=A+'<div class="n" style="cursor:default"><div class="nn">publish</div></div></div>';
document.getElementById('schema').innerHTML=h;

var placed={}; (f.shared_pre||[]).concat(f.classic_path||[],f.shared_post||[]).forEach(function(x){placed[strip(x)]=1;});
(f.react_phases||[]).forEach(function(p){(p.modules||[]).forEach(function(m){placed[m]=1;});}); placed['react_loop']=1;
var rest=Object.keys(SUB).filter(function(k){return SUB[k].module && !placed[k];});
if(rest.length) document.getElementById('schema').insertAdjacentHTML('beforeend',
  '<div class="ph" style="max-width:720px;margin-top:14px"><div class="pn">Carried everywhere</div>'+
  '<div class="pd">Read or written by many stages rather than called at one point.</div>'+
  '<div class="chips">'+rest.map(chip).join('')+'</div></div>');

function detail(k){
  var m=SUB[k]; if(!m) return;
  SEL=k;
  document.querySelectorAll('[data-k]').forEach(function(e){ e.classList.toggle('sel', e.dataset.k===k); });
  var isChain = k.indexOf('chain:')===0;
  var fields='';
  function F(label,val,cls){ return '<div class="f"><b>'+esc(label)+'</b><div class="'+(cls||'')+'">'+val+'</div></div>'; }
  var rate = m.rating ? '<span class="pill p-'+m.rating+'">'+m.rating+'</span>' : '';
  var sg = m.signals||{};
  var sigline = sg.loc ? '<div class="sigs">'+
      '<span><b>'+sg.loc+'</b> loc</span>'+
      '<span><b>'+(sg.except_handlers||0)+'</b> except</span>'+
      '<span><b>'+(sg.swallow||0)+'</b> log-and-continue</span>'+
      '<span><b>'+(sg.fan_in||0)+'</b> callers</span>'+
      '<span><b>'+(sg.emits||0)+'</b> signals</span>'+
      '<span><b>'+((sg.tests||[]).length)+'</b> test files</span></div>' : '';
  var findings = (m.findings||[]).length ? '<ul class="find">'+m.findings.map(function(f){
      return '<li class="f-'+f[0]+'">'+esc(f[1])+'</li>'; }).join('')+'</ul>' : '';
  var ready = m.rating ? '<div class="f"><b>Production readiness '+rate+
      ' <span class="depth">read: '+esc(m.depth||'')+'</span></b>'+sigline+findings+'</div>' : '';
  var howf = m.how ? F('How it works', esc(m.how)) : '';
  var uxf = m.ux ? F('UX — where you see or manage it', esc(m.ux)) : '';

  if(isChain){
    fields = howf + uxf + ready + F('What happens here', esc(m.what)) +
      F('Where it lives','<span class="m">'+esc(m.path)+(m.line?':'+m.line:'')+'</span>') +
      F('Configuration', m.config.length? '<span class="m">'+esc(m.config.join(', '))+'</span>'
        : '<span class="none">nothing configurable</span>');
  } else {
    fields = howf + uxf + ready + F('What the code says about itself', esc(m.role_full||m.role)) +
      F('Where it lives','<span class="m">'+esc(m.path)+' · '+m.loc+' lines</span>') +
      F('Configuration — env vars it reads', (m.config&&m.config.length)
          ? '<span class="m">'+esc(m.config.join('\\n')).replace(/\\n/g,'<br>')+'</span>'
          : '<span class="none">nothing configurable</span>') +
      F('Where to see the output', (m.telemetry&&m.telemetry.length)
          ? esc(m.telemetry.map(function(t){return t.signal;}).join(', '))+
            '<br><span class="m">'+esc((m.surfaces||[]).join(' · '))+'</span>'
          : ((m.writes&&m.writes.length)
              ? 'No signal. Writes via <span class="m">'+esc(m.writes.join(', '))+'</span>'
              : '<span class="none">'+esc(m.observability_note||'Nothing of its own.')+'</span>')) +
      F('Used by ('+(m.fan_in||0)+')', (m.callers&&m.callers.length)
          ? '<span class="m">'+esc(m.callers.join(', '))+'</span>'
          : '<span class="none">nothing imports it</span>') +
      (m.api&&m.api.length? F('Public API','<span class="m">'+esc(m.api.join(', '))+'</span>'):'');
  }
  document.getElementById('detail').innerHTML='<div class="card"><h3>'+esc(m.id||m.step)+rate+'</h3>'+
    '<span class="mod">'+esc(m.module||m.path||'')+'</span>'+fields+'</div>';
}
document.addEventListener('click',function(e){ var t=e.target.closest('[data-k]'); if(t) detail(t.dataset.k); });
document.addEventListener('keydown',function(e){ if(e.key!=='Enter'&&e.key!==' ')return;
  var t=e.target.closest&&e.target.closest('[data-k]'); if(t){e.preventDefault();detail(t.dataset.k);} });
detail('chain:PHI gate');
</script></body></html>
"""
open(OUT, "w", encoding="utf-8").write(TPL.replace("__DATA__", json.dumps(d)))
print(f"wrote {OUT} ({len(open(OUT).read())} bytes)")
