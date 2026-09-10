#!/usr/bin/env python3
"""Render the dev schema page. Data is inlined, so the page is a single file."""
import json, sys, html

DATA = sys.argv[1]; OUT = sys.argv[2]
d = json.load(open(DATA))

TPL = """<!doctype html><html data-theme="dark"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chat turn — dev schema</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="tokens.css">
<link rel="stylesheet" href="tokens-dark.css">
<style>
/* Mobius design system: never fork or redefine --mobius-*; no font-family
   literals; no raw px sizes. Everything below resolves to a token. The only
   local variables are layout widths, which the token set does not cover. */
:root{ --pane-detail: 25rem; --gap: var(--mobius-space-lg); }
*{box-sizing:border-box}
body{margin:0;background:var(--mobius-bg-primary);color:var(--mobius-text-primary);
 font-family:var(--mobius-font-sans);font-size:var(--mobius-text-sm);line-height:1.55;
 -webkit-font-smoothing:antialiased}

header.top{display:flex;align-items:center;gap:var(--mobius-space-md);
 padding:var(--mobius-space-md) var(--mobius-space-lg);
 border-bottom:1px solid var(--mobius-border);background:var(--mobius-bg-secondary);
 position:sticky;top:0;z-index:20}
header.top img{height:1.5rem;width:auto}
header.top h1{font-size:var(--mobius-text-md);font-weight:600;margin:0}
header.top .lead{font-size:var(--mobius-text-xs);color:var(--mobius-text-muted);margin:0}
.devtag{font-family:var(--mobius-font-mono);font-size:var(--mobius-text-xs);
 color:var(--mobius-warning);border:1px solid var(--mobius-warning);
 border-radius:var(--mobius-radius-full);padding:0.1rem var(--mobius-space-sm)}
.spacer{flex:1}
.pbtn{font-family:var(--mobius-font-sans);font-size:var(--mobius-text-xs);
 padding:0.25rem var(--mobius-space-sm);border-radius:var(--mobius-radius-sm);
 border:1px solid var(--mobius-border-medium);background:var(--mobius-bg-card);
 color:var(--mobius-text-secondary);cursor:pointer;white-space:nowrap}
.pbtn:hover{border-color:var(--mobius-violet);color:var(--mobius-violet)}
.pbtn:focus-visible{outline:2px solid var(--mobius-violet);outline-offset:2px}
.pbtn[aria-pressed="true"]{border-color:var(--mobius-violet);color:var(--mobius-violet);
 background:var(--mobius-bg-tertiary)}

/* Two panels, each independently collapsible, so you can go back and forth:
   schema full-width to see the shape, detail full-width to read a node. */
.wrap{display:grid;grid-template-columns:minmax(0,1fr) var(--pane-detail);
 gap:var(--gap);max-width:96rem;margin:0 auto;padding:var(--gap)}
/* A collapsed panel is display:none, which REMOVES it from the grid — so the
   survivor would fall into column 1. Sizing the collapsed state as a single
   column is what makes the remaining panel actually fill the page. */
.wrap.detail-collapsed,.wrap.schema-collapsed{grid-template-columns:minmax(0,1fr)}
.wrap.detail-collapsed .side{display:none}
.wrap.schema-collapsed .main{display:none}
/* Reading a node full-width: let it flow instead of sticking in a short box. */
.wrap.schema-collapsed .side{position:static;max-height:none;overflow:visible}
.wrap.schema-collapsed .card{max-width:60rem;margin:0 auto}
.wrap.schema-collapsed .card .desc{max-height:none}
@media(max-width:64rem){
 .wrap{grid-template-columns:1fr}
 .side{order:-1;position:sticky;top:3.25rem;max-height:50vh;overflow:auto;
  background:var(--mobius-bg-primary);z-index:5}
 .wrap.detail-collapsed .side,.wrap.schema-collapsed .main{display:none}
}

.band{border:1px dashed var(--mobius-border-medium);border-radius:var(--mobius-radius-lg);
 padding:var(--mobius-space-md);margin-bottom:var(--mobius-space-md)}
.band-t{font-size:var(--mobius-text-xs);letter-spacing:.08em;text-transform:uppercase;
 color:var(--mobius-violet);font-weight:700;margin-bottom:var(--mobius-space-sm)}
.chain{display:flex;flex-wrap:wrap;align-items:stretch;gap:var(--mobius-space-xs)}
.cnode{flex:1 1 9rem;background:var(--mobius-bg-card);border:1px solid var(--mobius-border);
 border-radius:var(--mobius-radius-md);padding:var(--mobius-space-sm);cursor:pointer;min-width:8.5rem}
.cnode:hover,.cnode:focus-visible{border-color:var(--mobius-violet);outline:none}
.cnode.sel{border-color:var(--mobius-violet);background:var(--mobius-bg-tertiary)}
.cnode.gate{border-color:var(--mobius-error)}
.cn{font-size:var(--mobius-text-sm);font-weight:600}
.cs{font-size:var(--mobius-text-xs);color:var(--mobius-text-muted);margin-top:0.1rem}
.arr{align-self:center;color:var(--mobius-text-muted)}
.schema{display:flex;flex-direction:column;align-items:center}
.n{background:var(--mobius-bg-card);border:1px solid var(--mobius-border);
 border-radius:var(--mobius-radius-md);padding:var(--mobius-space-sm) var(--mobius-space-md);
 text-align:center;min-width:10rem;cursor:pointer}
.n:hover,.n:focus-visible{border-color:var(--mobius-violet);outline:none}
.n.sel{border-color:var(--mobius-violet);background:var(--mobius-bg-tertiary)}
.nn{font-size:var(--mobius-text-sm);font-weight:600}
.ns{font-size:var(--mobius-text-xs);color:var(--mobius-text-muted)}
.a{color:var(--mobius-text-muted);line-height:1.4}
.lanes{display:flex;gap:var(--mobius-space-lg);flex-wrap:wrap;justify-content:center;align-items:flex-start}
.lane{border:1px dashed var(--mobius-border-medium);border-radius:var(--mobius-radius-lg);
 padding:var(--mobius-space-md);min-width:15rem;display:flex;flex-direction:column;align-items:center}
.lt{font-size:var(--mobius-text-xs);letter-spacing:.07em;text-transform:uppercase;
 color:var(--mobius-violet);font-weight:700;margin-bottom:var(--mobius-space-sm)}
.ph{width:100%;border-left:2px solid var(--mobius-violet);
 padding:var(--mobius-space-xs) 0 var(--mobius-space-xs) var(--mobius-space-sm);margin:0.15rem 0}
.pn{font-size:var(--mobius-text-xs);font-weight:700;color:var(--mobius-text-secondary)}
.pd{font-size:var(--mobius-text-xs);color:var(--mobius-text-muted);margin:0.1rem 0 0.3rem;line-height:1.45}
.chips{display:flex;flex-wrap:wrap;gap:var(--mobius-space-xs)}
.chip{font-size:var(--mobius-text-xs);padding:0.15rem var(--mobius-space-sm);
 border-radius:var(--mobius-radius-sm);cursor:pointer;border:1px solid var(--mobius-border);
 background:var(--mobius-bg-card);color:var(--mobius-text-secondary)}
.chip:hover,.chip:focus-visible{border-color:var(--mobius-violet);outline:none}
.chip.sel{border-color:var(--mobius-violet);background:var(--mobius-bg-tertiary)}
.chip .cfg{color:var(--mobius-accent)} .chip .em{color:var(--mobius-success)}
.chip .no{color:var(--mobius-warning)}
.r-green{box-shadow:inset 3px 0 0 var(--mobius-success)}
.r-amber{box-shadow:inset 3px 0 0 var(--mobius-warning)}
.r-red{box-shadow:inset 3px 0 0 var(--mobius-error)}
.pill{display:inline-block;font-size:var(--mobius-text-xs);letter-spacing:.06em;
 text-transform:uppercase;font-weight:700;padding:0.1rem var(--mobius-space-sm);
 border-radius:var(--mobius-radius-full);margin-left:var(--mobius-space-xs)}
.p-green{background:var(--mobius-bg-tertiary);color:var(--mobius-success)}
.p-amber{background:var(--mobius-bg-tertiary);color:var(--mobius-warning)}
.p-red{background:var(--mobius-bg-tertiary);color:var(--mobius-error)}
.find{margin:var(--mobius-space-xs) 0 0;padding-left:var(--mobius-space-md);
 font-size:var(--mobius-text-xs);line-height:1.55}
.find li{margin-bottom:0.3rem}
.f-bad::marker{content:"▲ ";color:var(--mobius-error)}
.f-watch::marker{content:"▸ ";color:var(--mobius-warning)}
.f-good::marker{content:"✓ ";color:var(--mobius-success)}
.sigs{display:flex;flex-wrap:wrap;gap:0.15rem var(--mobius-space-md);
 font-family:var(--mobius-font-mono);font-size:var(--mobius-text-xs);color:var(--mobius-text-muted)}
.sigs b{color:var(--mobius-text-secondary);font-weight:500}
.depth{font-family:var(--mobius-font-mono);font-size:var(--mobius-text-xs);color:var(--mobius-text-muted)}
.side{position:sticky;top:calc(3.25rem + var(--gap));align-self:start;
 max-height:calc(100vh - 5rem);overflow-y:auto}
.card{border:1px solid var(--mobius-violet);border-radius:var(--mobius-radius-lg);
 padding:var(--mobius-space-md);background:var(--mobius-bg-card)}
.card h3{margin:0 0 0.1rem;font-size:var(--mobius-text-md)}
.card .mod{font-family:var(--mobius-font-mono);font-size:var(--mobius-text-xs);color:var(--mobius-text-muted)}
.card .desc{font-size:var(--mobius-text-xs);color:var(--mobius-text-secondary);
 margin:var(--mobius-space-sm) 0 var(--mobius-space-md);white-space:pre-wrap;
 max-height:16rem;overflow:auto}
.f{margin-top:var(--mobius-space-sm)}
.f b{display:block;font-size:var(--mobius-text-xs);letter-spacing:.07em;text-transform:uppercase;
 color:var(--mobius-violet);margin-bottom:0.15rem}
.f div{font-size:var(--mobius-text-xs);color:var(--mobius-text-secondary);line-height:1.55;overflow-wrap:anywhere}
.f .m{font-family:var(--mobius-font-mono);font-size:var(--mobius-text-xs);color:var(--mobius-text-muted)}
.none{color:var(--mobius-warning)}
.legend{font-size:var(--mobius-text-xs);color:var(--mobius-text-muted);text-align:center;
 margin-top:var(--mobius-space-sm)}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
.band-dead{opacity:.72}
.n.removed,.cnode.removed{border-left-color:var(--mobius-border-medium)}
.rr{font-size:var(--mobius-text-xs);letter-spacing:.06em;text-transform:uppercase;opacity:.6}
.cnode.dead{border-style:dashed;text-decoration:line-through;text-decoration-thickness:1px}
.cnode.dead .cs{text-decoration:none;opacity:.75}
table.rm{width:100%;border-collapse:collapse;font-size:var(--mobius-font-size-sm)}
table.rm th{text-align:left;font-weight:600;opacity:.7;padding:.5rem .6rem;
 border-bottom:1px solid var(--mobius-border)}
table.rm td{padding:.5rem .6rem;border-bottom:1px solid var(--mobius-border);vertical-align:top}
table.rm tr.rmo td{opacity:.65;font-style:italic}
</style></head><body>
<header class="top">
  <img src="logo.svg" alt="Mobius">
  <div>
    <h1>How a chat turn actually runs</h1>
    <p class="lead" id="lead"></p>
  </div>
  <span class="devtag">DEV \u2014 local only</span>
  <span class="spacer"></span>
  <button class="pbtn" id="tgl-schema" aria-pressed="false">Hide diagram</button>
  <button class="pbtn" id="tgl-detail" aria-pressed="false">Hide detail</button>
</header>
<div class="wrap" id="wrap"><div class="main">
<div class="band"><div class="band-t">Before the pipeline — the part the shipped diagram omits</div>
<div class="chain" id="chain"></div></div>
<div class="band"><div class="band-t">Inside run_pipeline</div><div class="schema" id="schema"></div>
<p class="legend">● emits its own signals&nbsp; ◦ observable only through its caller&nbsp; ⚙ has env-var config<br>
left edge: <span style="color:var(--mobius-success)">green</span> ready ·
<span style="color:var(--mobius-warning)">amber</span> named weakness ·
<span style="color:var(--mobius-error)">red</span> failure here is invisible or unbounded</p></div>
<div class="band"><div class="band-t">Cross-cutting — under every step, not a step</div>
<div class="chain" id="cross"></div></div>
<div class="band"><div class="band-t">Refactor roadmap — every bug on this page is sequenced or explicitly outside</div>
<div id="roadmap"></div>
<p class="legend">Generated by <code>scripts/platform/gen_roadmap.py</code> from these same findings; it
fails when a bug is unassigned, so a new finding cannot escape the roadmap.
Plan and test gate: <code>docs/chat-refactor-program.md</code> · tracker:
<code>docs/chat-refactor-roadmap.md</code>. Nothing starts until the sign-off table is complete.</p></div>
</div><div class="side"><div id="detail"></div>
<p class="legend" style="text-align:left">Click anything. This panel follows you down the page.</p>
</div></div>
<script>
var D = __DATA__;
var SUB={}, SEL=null;
D.submodules.forEach(function(m){ SUB[m.key || m.module.split('.').pop()]=m; });
D.cross_cutting.forEach(function(c){ SUB[c.id]=c; });
D.chain.forEach(function(c){ SUB['chain:'+c.step]=c; });
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
var LIVE_SUB = D.submodules.filter(function(s){return !s.deleted;});
var DEAD_SUB = D.submodules.filter(function(s){return s.deleted;});
document.getElementById('lead').textContent =
  LIVE_SUB.length+' live sub-modules, '+D.chain.length+' hops before the pipeline, '+
  D.cross_cutting.length+' cross-cutting & decision modules'+
  (DEAD_SUB.length? ' · '+DEAD_SUB.length+' removed by the refactor, boxed at the bottom':'')+
  '. Generated by '+D.generated_by+'.';

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

Object.keys(SUB).forEach(function(k){
  var o=SUB[k]; if(!o || !o.deleted) return;
  o.__del=1;
  // The hand-written description was written while the module was live and
  // still reads in the present tense. Rather than rewrite 5 descriptions into
  // the past and lose what they said, stamp the node so a reader cannot mistake
  // a historical description for a current one.
  o.how = '**DELETED BY THE REFACTOR — `'+o.path+'` no longer exists.** The description and '+
          'findings below are kept verbatim as the record of why removing it was safe. '+
          'They describe the module as it WAS.' + String.fromCharCode(10,10) + (o.how||'');
});

document.getElementById('cross').innerHTML = D.cross_cutting.map(function(c){
  return '<div class="cnode'+rc(c)+'" data-k="'+esc(c.id)+'" tabindex="0" role="button">'+
    '<div class="cn">'+esc(c.id)+(c.config.length?' <span class="cfg">⚙</span>':'')+'</div>'+
    '<div class="cs">'+esc(c.path)+' · called by '+c.fan_in+'</div></div>'; }).join('');

// Removed modules live in their OWN box, out of the live flow entirely.
// Keeping them inline made the diagram read as though a deleted stage still
// runs — the schema's job is to show what happens now, and the archive's job
// is to keep the reasoning that justified each removal.
if(DEAD_SUB.length){
 var b=document.createElement('div'); b.className='band band-dead';
 b.innerHTML='<div class="band-t">Removed by the refactor — '+DEAD_SUB.length+
  ' module'+(DEAD_SUB.length>1?'s':'')+', no longer on disk and NOT part of the live flow</div>'+
  '<p class="legend">Kept as an archive, not as pipeline. Click one to read the findings that '+
  'justified removing it — that record is why the deletion was safe, and a diff of this page '+
  'is how anyone sees what each phase took out. Their measured figures (lines, tests, callers) '+
  'read zero because the file is gone; the historical values are preserved under '+
  '<code>was_loc</code> / <code>was_tests</code> in the data.</p>'+
  '<div class="chain">'+DEAD_SUB.map(function(o){
    return '<div class="cnode dead" data-k="'+esc(o.key)+'" tabindex="0" role="button">'+
      '<div class="cn">'+esc(o.key)+'</div>'+
      '<div class="cs">'+esc(o.path)+' · removed'+
      (o.was_loc? ' · was '+o.was_loc+' loc':'')+'</div></div>';}).join('')+'</div>';
 var mainEl=document.querySelector('.main'); if(mainEl) mainEl.appendChild(b);}

var RM=D.roadmap||null;
if(RM){document.getElementById('roadmap').innerHTML=
  '<table class="rm"><thead><tr><th>Phase</th><th>Bugs</th><th>Owner</th><th>Gate metric</th>'+
  '<th>Blocks</th><th>Status</th></tr></thead><tbody>'+
  RM.phases.map(function(p){return '<tr><td><b>'+esc(p.id)+'</b> '+esc(p.name)+'</td>'+
    '<td style="text-align:right">'+p.n+'</td><td>'+esc(p.owner)+'</td><td>'+esc(p.gate)+'</td>'+
    '<td>'+esc(p.blocks||'—')+'</td><td>&#9744; not started</td></tr>';}).join('')+
  '<tr class="rmo"><td>outside the program</td><td style="text-align:right">'+RM.outside+
  '</td><td colspan="4">each carries a stated reason — see the tracker</td></tr>'+
  '</tbody></table>';}

var f=D.flow, strip=function(x){return x.replace(/^run_/,'');};
var h='<div class="schema">';
(f.shared_pre||[]).forEach(function(x){ h+=node(strip(x),'always runs')+A; });
if(f.branch_on){
  h+='<div class="n" style="cursor:default;border-style:dashed"><div class="nn">'+f.branch_on+' ?</div>'+
     '<div class="ns">orchestrator.py:'+f.branch_line+'</div></div>'+A;
}
h+='<div class="lanes">';
h+='<div class="lane">'+(f.branch_on?'<div class="lt">ReAct path</div>':'')+
   node('react_loop',f.branch_on?'replaces plan + resolve':'the only path — the branch was deleted');
(f.react_phases||[]).forEach(function(p){
  h+='<div class="ph"><div class="pn">'+esc(p.phase)+'</div><div class="pd">'+esc(p.note)+
     (p.cite?' <span style="opacity:.6">react_loop.py:'+p.cite+'</span>':'')+'</div>'+
     '<div class="chips">'+(p.modules||[]).map(chip).join('')+'</div></div>'; });
h+='</div>';
if((f.classic_path||[]).length){
  h+='<div class="lane"><div class="lt">Classic path</div>';
  (f.classic_path||[]).forEach(function(x,i){ h+=node(strip(x))+(i<f.classic_path.length-1?A:''); });
  h+='</div>';
}
h+='</div>';
if(f.branch_removed_by){
  h+='<p class="legend" style="margin-top:.6rem">The <code>use_react</code> decision and the '+
     'Classic path lane are gone — removed by '+esc(f.branch_removed_by)+'. Their nodes are kept '+
     'below so the findings that justified the deletion stay readable.</p>';
}
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

// Every DB touch, every UX surface, every parameter — extracted, not listed.
// A field that is empty says so; a field that cannot be extracted says THAT,
// because blank reads as "nothing here" when it may mean "not visible to a
// static read".
function detailBlocks(m){
  var d = m.detail; if(!d) return '';
  if(d._unavailable) return '<div class="f"><b>Detail</b><div class="none">'+esc(d._unavailable)+'</div></div>';
  function list(arr, empty){
    return (arr&&arr.length) ? '<span class="m">'+arr.map(esc).join('<br>')+'</span>'
                             : '<span class="none">'+empty+'</span>'; }
  var db = d.db||{}, ux = d.ux||{}, pa = d.parameters||{};
  var out = '';
  out += '<div class="f"><b>DB — what it touches</b><div>'+
    'SQL: '+list(db.sql,'no literal SQL in this file')+'<br>'+
    'storage fns: '+list(db.storage_fns,'imports nothing from app.storage')+
    (db.redis_keys&&db.redis_keys.length?'<br>redis keys: '+list(db.redis_keys,''):'')+
    '<br><span style="opacity:.55;font-size:10px">'+esc(db.note||'')+'</span></div></div>';
  out += '<div class="f"><b>UX — surfaces</b><div>'+
    'routes: '+list(ux.routes_defined,'defines no routes')+'<br>'+
    'frontend files naming it: '+list(ux.frontend_files,'none — no frontend references it by name')+
    '</div></div>';
  var consts = (pa.module_constants||[]).map(function(c){return c.name+' = '+c.value;});
  var dflts  = (pa.keyword_defaults||[]).map(function(c){return c.fn+'('+c.param+'='+c.default+')';});
  out += '<div class="f"><b>Parameters — constants and defaults</b><div>'+
    'module constants: '+list(consts,'none')+'<br>'+
    'keyword defaults: '+list(dflts,'none')+
    '<br><span style="opacity:.55;font-size:10px">env vars are in Configuration above; these need a code change</span>'+
    '</div></div>';
  return out;
}

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
  var covMap = {'GUARDED':'green','TAGGED-UNVERIFIED':'amber','PERIPHERAL':'amber',
                'IMPORTED-NOT-CALLED':'red','ABSENT':'red','REMOVED':'red'};
  var cov = m.coverage ? '<span class="pill p-'+(covMap[m.coverage]||'watch')+'" '+
      'title="Eval Layer 1 reachability. GUARDED requires an Eval audit of the tag; '+
      'a node cannot mark itself GUARDED.">test: '+esc(m.coverage)+'</span>'+
      ((m.coverage_tags && m.coverage_tags.length)
        ? ' <span class="depth">'+esc(m.coverage_tags.join(', '))+'</span>' : '') : '';
  var ready = m.rating ? '<div class="f"><b>Production readiness '+rate+' '+cov+
      ' <span class="depth">read: '+esc(m.depth||'')+'</span></b>'+sigline+findings+'</div>' : '';
  var howf = m.how ? F('How it works', esc(m.how)) : '';
  // A node whose whole point is "where do I manage this" should hand you the
  // link, not a string to retype.
  var uxf = m.ux ? F('UX — where you see or manage it',
      esc(m.ux).replace(/(https?:\\/\\/[^\\s<]+)/g,
        '<a href="$1" target="_blank" rel="noopener" style="color:var(--mobius-accent)">$1</a>')) : '';

  if(isChain){
    fields = howf + uxf + ready + F('What happens here', esc(m.what)) +
      F('Where it lives','<span class="m">'+esc(m.path)+(m.line?':'+m.line:'')+'</span>') +
      F('Configuration', m.config.length? '<span class="m">'+esc(m.config.join(', '))+'</span>'
        : '<span class="none">nothing configurable</span>') +
      detailBlocks(m);
  } else {
    fields = howf + uxf + ready + F('What the code says about itself', esc(m.role_full||m.role)) +
      F('Where it lives','<span class="m">'+esc(m.path)+' · '+m.loc+' lines</span>') +
      F('Configuration — code default vs LIVE', (m.live_config&&m.live_config.length)
          ? '<span class="m">'+m.live_config.map(function(c){
              var set = c.live.indexOf('(not set')!==0;
              return esc(c.name)+' = '+(set?'<b style="color:var(--cyan)">'+esc(c.live)+'</b>'
                                            :'<span style="color:var(--dim)">'+esc(c.live)+'</span>');
            }).join('<br>')+'</span>'
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
      (m.api&&m.api.length? F('Public API','<span class="m">'+esc(m.api.join(', '))+'</span>'):'') +
      detailBlocks(m);
  }
  document.getElementById('detail').innerHTML='<div class="card"><h3>'+esc(m.id||m.step)+rate+'</h3>'+
    '<span class="mod">'+esc(m.module||m.path||'')+'</span>'+fields+'</div>';
}
document.addEventListener('click',function(e){ var t=e.target.closest('[data-k]'); if(t) detail(t.dataset.k); });
document.addEventListener('keydown',function(e){ if(e.key!=='Enter'&&e.key!==' ')return;
  var t=e.target.closest&&e.target.closest('[data-k]'); if(t){e.preventDefault();detail(t.dataset.k);} });
detail('chain:PHI gate');

// Two panels, each collapsible, so you can go back and forth: diagram alone to
// read the shape, detail alone to read a node. State is remembered per browser
// so the view you were using survives a regenerate-and-reload, which is the
// whole point when the page is rebuilt every few minutes.
(function(){
  var wrap=document.getElementById('wrap');
  function bind(btn, cls, hideLabel, showLabel, other, otherCls){
    var b=document.getElementById(btn);
    function apply(on, save){
      wrap.classList.toggle(cls, on);
      b.setAttribute('aria-pressed', on?'true':'false');
      b.textContent = on ? showLabel : hideLabel;
      if(on){ // never collapse both — the other one comes back
        wrap.classList.remove(otherCls);
        var ob=document.getElementById(other);
        ob.setAttribute('aria-pressed','false');
        ob.textContent = ob.dataset.hide;
        try{ localStorage.removeItem('devschema:'+otherCls); }catch(e){}
      }
      if(save){ try{ on ? localStorage.setItem('devschema:'+cls,'1')
                        : localStorage.removeItem('devschema:'+cls); }catch(e){} }
    }
    b.dataset.hide=hideLabel;
    b.addEventListener('click', function(){ apply(!wrap.classList.contains(cls), true); });
    var stored=false; try{ stored = localStorage.getItem('devschema:'+cls)==='1'; }catch(e){}
    if(stored) apply(true,false);
  }
  bind('tgl-detail','detail-collapsed','Hide detail','Show detail','tgl-schema','schema-collapsed');
  bind('tgl-schema','schema-collapsed','Hide diagram','Show diagram','tgl-detail','detail-collapsed');
})();
</script></body></html>
"""
open(OUT, "w", encoding="utf-8").write(TPL.replace("__DATA__", json.dumps(d)))
print(f"wrote {OUT} ({len(open(OUT).read())} bytes)")
