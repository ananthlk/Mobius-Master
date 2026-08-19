"""Render the service line registry page from the master catalog."""
import json

ROOT = "/Users/ananth/Mobius/"
CAT = json.load(open(ROOT + "docs/service-lines/fl-medicaid-bh.catalog.json"))
OUT = ROOT + "docs/product-docs/service-line-registry-mockup.html"

HEAD = """<title>Mobius Service Line Registry — FL Medicaid Behavioral Health</title>
<style>
:root{
  --ground:#fbfbfd; --surface:#ffffff; --surface-2:#f4f4f8; --surface-3:#eceaf2;
  --line:#e3e3ec; --line-strong:#cfcfdc;
  --ink:#16161d; --ink-2:#54546a; --ink-3:#8b8b9e;
  --accent:#6d28d9; --accent-soft:#ede9fe; --accent-line:#c4b5fd;
  --ok:#0f7a52; --ok-bg:#d8f0e4; --ok-line:#8fd3b6;
  --warn:#8a5600; --warn-bg:#fbeed2; --warn-line:#e6c68a;
  --crit:#a1213a; --crit-bg:#fbe2e8; --crit-line:#eda9b9;
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
  --shadow:0 1px 2px rgba(0,0,0,.4),0 4px 16px rgba(0,0,0,.3);
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--sans);
     font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
code,.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
h1,h2,h3{margin:0;text-wrap:balance}
.shell{display:grid;grid-template-columns:262px minmax(0,1fr);min-height:100vh}
@media (max-width:900px){.shell{grid-template-columns:1fr}}
.rail{border-right:1px solid var(--line);background:var(--surface);padding:20px 0;
      display:flex;flex-direction:column;gap:16px}
@media (max-width:900px){.rail{border-right:0;border-bottom:1px solid var(--line)}}
.brand{padding:0 18px;display:flex;flex-direction:column;gap:2px}
.brand .mk{font-family:var(--mono);font-size:10.5px;letter-spacing:.16em;
           text-transform:uppercase;color:var(--accent)}
.brand .nm{font-size:15px;font-weight:640;letter-spacing:-.01em}
.brand .sb{font-size:11.5px;color:var(--ink-3)}
.railhead{padding:0 18px;font-family:var(--mono);font-size:10px;letter-spacing:.14em;
          text-transform:uppercase;color:var(--ink-3)}
.lines{display:flex;flex-direction:column;gap:1px;padding:0 8px}
.lines button{all:unset;cursor:pointer;padding:7px 10px;border-radius:6px;display:grid;
              grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:8px}
.lines button:hover{background:var(--surface-2)}
.lines button:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.lines button[aria-current="true"]{background:var(--accent-soft)}
.lines .t{font-size:12.5px;color:var(--ink-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lines button[aria-current="true"] .t{color:var(--accent);font-weight:620}
.lines .s{font-family:var(--mono);font-size:10.5px;color:var(--ink-3)}
.lines button[aria-current="true"] .s{color:var(--accent)}
.lines .all{border-bottom:1px solid var(--line);border-radius:6px 6px 0 0;margin-bottom:5px;padding-bottom:11px}
.main{min-width:0;padding:26px 28px 60px;display:flex;flex-direction:column;gap:22px}
.ph{display:flex;flex-direction:column;gap:6px;max-width:78ch}
.eyebrow{font-family:var(--mono);font-size:10.5px;letter-spacing:.15em;text-transform:uppercase;color:var(--ink-3)}
.ph h2{font-size:22px;font-weight:650;letter-spacing:-.02em}
.ph p{margin:0;color:var(--ink-2);font-size:13px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:9px;
      box-shadow:var(--shadow);overflow:hidden}
.ch{padding:11px 16px;border-bottom:1px solid var(--line);background:var(--surface-2);
    display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.ch h3{font-size:12px;font-weight:620}
.ch .hint{margin-left:auto;font-size:11.5px;color:var(--ink-3)}
.cb{padding:16px}
.field{display:grid;grid-template-columns:136px minmax(0,1fr);gap:14px;align-items:baseline;margin-bottom:12px}
.field:last-child{margin-bottom:0}
@media (max-width:640px){.field{grid-template-columns:1fr;gap:4px}}
.field .l{font-family:var(--mono);font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.field .v{font-size:13px;line-height:1.55}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
thead th{font-family:var(--mono);font-size:10px;letter-spacing:.09em;text-transform:uppercase;
         color:var(--ink-3);font-weight:500;background:var(--surface-2);
         border-bottom:1px solid var(--line-strong);white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:var(--surface-2)}
td.num{text-align:right;font-family:var(--mono);white-space:nowrap}
td.c{font-family:var(--mono);white-space:nowrap}
.mod{display:inline-block;font-family:var(--mono);font-size:10.5px;padding:1px 5px;border-radius:3px;
     background:var(--accent-soft);border:1px solid var(--accent-line);color:var(--accent)}
.mod.none{background:var(--surface-2);border-color:var(--line);color:var(--ink-3)}
.excl{display:block;margin-top:3px;font-size:11px;color:var(--crit)}
.lim{display:block;margin-top:2px;font-size:11px;color:var(--ink-3)}
.flag{display:inline-block;font-family:var(--mono);font-size:9.5px;letter-spacing:.06em;
      text-transform:uppercase;padding:1px 5px;border-radius:3px;background:var(--warn-bg);
      color:var(--warn);border:1px solid var(--warn-line);margin-left:5px}
.mods{display:flex;flex-direction:column}
.m{display:grid;grid-template-columns:150px minmax(0,1fr) 116px;gap:18px;padding:14px 0;
   border-bottom:1px solid var(--line);align-items:start}
.m:last-child{border-bottom:0}
@media (max-width:820px){.m{grid-template-columns:1fr;gap:7px}}
.m .w b{display:block;font-size:12.5px;font-weight:620}
.m .w span{font-size:11px;color:var(--ink-3)}
.owes{font-size:12.5px;line-height:1.55}
.owes .said{color:var(--ink-2);margin-top:5px;display:block;padding-left:11px;border-left:2px solid var(--line-strong)}
.owes .said em{font-style:normal;font-family:var(--mono);font-size:10px;letter-spacing:.1em;
               text-transform:uppercase;color:var(--ink-3);display:block;margin-bottom:1px}
.pill{display:inline-flex;align-items:center;gap:5px;font-family:var(--mono);font-size:10px;
      letter-spacing:.07em;text-transform:uppercase;padding:2px 8px;border-radius:99px;
      border:1px solid transparent;white-space:nowrap}
.pill .d{width:5px;height:5px;border-radius:50%}
.p-done{background:var(--ok-bg);color:var(--ok);border-color:var(--ok-line)}.p-done .d{background:var(--ok)}
.p-doing{background:var(--warn-bg);color:var(--warn);border-color:var(--warn-line)}.p-doing .d{background:var(--warn)}
.p-todo{background:var(--crit-bg);color:var(--crit);border-color:var(--crit-line)}.p-todo .d{background:var(--crit)}
.p-na{background:var(--surface-2);color:var(--ink-3);border-color:var(--line)}.p-na .d{background:var(--ink-3)}
.k-na{background:var(--surface-2);border-color:var(--line)}
.scope{display:inline-flex;align-items:center;gap:5px;font-family:var(--mono);font-size:10px;
       letter-spacing:.07em;text-transform:uppercase;padding:2px 8px;border-radius:4px}
.sc-serve{background:var(--accent-soft);color:var(--accent);border:1px solid var(--accent-line)}
.sc-decline{background:var(--surface-2);color:var(--ink-3);border:1px solid var(--line-strong)}
.railgrp{padding:10px 18px 3px;font-family:var(--mono);font-size:9.5px;letter-spacing:.13em;
         text-transform:uppercase;color:var(--ink-3)}
.roll{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.roll .big{font-size:30px;font-weight:650;letter-spacing:-.025em;font-variant-numeric:tabular-nums}
.roll .of{font-size:13px;color:var(--ink-3)}
.track{height:7px;border-radius:99px;background:var(--surface-3);overflow:hidden;flex:1;min-width:130px;display:flex}
.track i{display:block;height:100%}
.f-done{background:var(--ok)}.f-doing{background:var(--warn)}
.mk{display:inline-block;width:13px;height:13px;border-radius:3px;border:1px solid transparent}
.k-done{background:var(--ok-bg);border-color:var(--ok-line);box-shadow:inset 0 0 0 3px var(--ok)}
.k-doing{background:var(--warn-bg);border-color:var(--warn-line)}
.k-todo{background:var(--crit-bg);border-color:var(--crit-line)}
td.g{text-align:center}
.legend{display:flex;flex-wrap:wrap;gap:7px 20px;padding:11px 16px;border-top:1px solid var(--line);background:var(--surface-2)}
.legend span{display:flex;align-items:center;gap:7px;font-size:11.5px;color:var(--ink-2)}
.note{font-size:12.5px;color:var(--ink-2);border-left:2px solid var(--accent-line);
      padding:2px 0 2px 12px;max-width:78ch}
.note b{color:var(--ink);font-weight:620}
.lk{all:unset;cursor:pointer;color:var(--accent);text-decoration:underline;text-underline-offset:2px}
tbody td:first-child{min-width:236px}
.lk:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.src{font-family:var(--mono);font-size:10.5px;color:var(--ink-3)}
</style>
"""

BODY = """
<div class="shell">
  <nav class="rail">
    <div class="brand">
      <div class="mk">Mobius · master</div>
      <div class="nm">Service Line Registry</div>
      <div class="sb">FL Medicaid behavioral health</div>
    </div>
    <div class="railhead">Service lines · modules complete</div>
    <div class="lines" id="rail"></div>
  </nav>
  <main class="main" id="main"></main>
</div>
<script>var CATALOG = __CATALOG__;</script>
<script>
(function(){
var C = CATALOG, M = C.modules, L = C.service_lines;
var LAB = {done:'Complete', doing:'In progress', todo:'Not started', na:'N/A'};
function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;');}
function req(l){return M.filter(function(m){return l.status[m.key][0]!=='na';}).length;}
function score(l){return M.filter(function(m){return l.status[m.key][0]==='done';}).length;}
var MODS=C.modifiers;
function modDef(m){return MODS[m]||'not in glossary';}

var rail=document.getElementById('rail'), main=document.getElementById('main');
var total=L.reduce(function(a,l){return a+req(l);},0), allDone=L.reduce(function(a,l){return a+score(l);},0);

function railBtn(l){return '<button data-v="'+l.key+'"><span class="t">'+esc(l.name)+
  '</span><span class="s">'+score(l)+'/'+req(l)+'</span></button>';}
var served=L.filter(function(l){return l.scope==='serve';});
var declined=L.filter(function(l){return l.scope!=='serve';});
rail.innerHTML='<button class="all" data-v="all"><span class="t">All service lines</span>'+
  '<span class="s">'+allDone+'/'+total+'</span></button>'+
  '<div class="railgrp">Serving · '+served.length+'</div>'+served.map(railBtn).join('')+
  '<div class="railgrp">Named, not served · '+declined.length+'</div>'+declined.map(railBtn).join('');

function codeTable(l){
  if(!l.codes.length) return '<div class="cb"><p style="margin:0;color:var(--ink-3);font-size:12.5px">'+
    'No codes loaded. '+esc(l.status.facts[1])+'</p></div>';
  return '<div class="scroll"><table><thead><tr>'+
    '<th>Code</th><th>Modifier</th><th>Modifier means</th><th>Service definition</th>'+
    '<th>Tele</th><th>Billing relations</th></tr></thead><tbody>'+
    l.codes.map(function(c){
      return '<tr><td class="c">'+c.code+'</td>'+
        '<td>'+(c.modifier?'<span class="mod">'+c.modifier+'</span>':'<span class="mod none">none</span>')+'</td>'+
        '<td style="font-size:11.5px;color:var(--ink-3)">'+(c.modifier?esc(modDef(c.modifier)):'—')+'</td>'+
        '<td>'+esc(c.definition)+(c.adjudicated?'':'<span class="flag" title="page cites '+
          c.rule_candidates.join(' and ')+'">unadjudicated</span>')+'</td>'+
        '<td class="c">'+(c.telemedicine?'Y':'')+'</td>'+
        '<td>'+((c.relations||[]).length?(c.relations||[]).map(function(x){return '<span class="excl">'+esc(x)+'</span>';}).join('')
                :'<span style="color:var(--ink-3)">—</span>')+'</td>'+
      '</tr>';
    }).join('')+'</tbody></table></div>';
}

function evidenceTable(l){
  if(!l.evidence_sources || !l.evidence_sources.length)
    return '<div class="cb"><p style="margin:0;color:var(--ink-3);font-size:12.5px">'+
      'No corpus evidence gathered for this line yet.</p></div>';
  return '<div class="scroll"><table><thead><tr><th>What we hold</th><th>Publisher</th>'+
    '<th>Authority level</th><th style="text-align:right">Pages</th></tr></thead><tbody>'+
    l.evidence_sources.map(function(e){
      return '<tr><td>'+esc(e.doc)+'</td><td>'+esc(e.payer||'—')+'</td>'+
        '<td style="font-size:11.5px;color:var(--ink-3)">'+esc(e.authority||'unclassified')+'</td>'+
        '<td class="num">'+e.pages+'</td></tr>';
    }).join('')+'</tbody></table></div>';
}

function exceptionCard(l){
  var A=l.exception_asks||[]; if(!A.length) return '';
  var by={}; A.forEach(function(a){ (by[a.domain]=by[a.domain]||[]).push(a); });
  return Object.keys(by).map(function(dom){
    var rows=by[dom], store=rows[0].other_store, q=rows[0].question;
    var open_=rows.filter(function(r){return !r.answer;}).length;
    return '<div class="card"><div class="ch"><h3>'+esc(dom)+' — exceptions only</h3>'+
      '<span class="pill '+(open_?'p-todo':'p-done')+'"><span class="d"></span>'+
      (open_? open_+' unanswered' : 'all answered')+'</span>'+
      '<span class="hint">'+esc(store)+' holds the standard · we hold only what differs</span></div>'+
      '<div class="cb" style="border-bottom:1px solid var(--line);padding-bottom:12px">'+
      '<div style="font-size:12.5px;color:var(--ink-2)"><em style="font-style:normal;'+
      'font-family:var(--mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;'+
      'color:var(--ink-3);display:block;margin-bottom:3px">What we ask them</em>'+esc(q)+'</div></div>'+
      '<div class="scroll"><table><thead><tr><th>Payor</th><th>Answer</th>'+
      '<th>If different, what</th></tr></thead><tbody>'+
      rows.map(function(r){
        return '<tr><td class="c">'+esc(r.payer==='*'?'all payors':(r.payer||'').split('|')[0])+'</td>'+
          '<td>'+(r.answer==='follows_standard'
              ? '<span class="pill p-done"><span class="d"></span>follows standard</span>'
              : r.answer==='has_exception'
                ? '<span class="pill p-doing"><span class="d"></span>special process</span>'
                : '<span class="pill p-todo"><span class="d"></span>not answered</span>')+'</td>'+
          '<td style="font-size:11.5px;color:var(--ink-2)">'+
            (r.statement? esc(r.statement)
             : (r.answer==='follows_standard'? '<span style="color:var(--ink-3)">nothing — '+
                 esc(store)+' has it</span>' : '<span style="color:var(--crit)">awaiting answer</span>'))+
          '</td></tr>';
      }).join('')+'</tbody></table></div></div>';
  }).join('');
}

function requirementCard(l){
  var R=l.payor_requirements||[]; if(!R.length) return '';
  var c=l.requirement_counts||{};
  return '<div class="card"><div class="ch"><h3>Payor requirements</h3>'+
    '<span class="pill '+(c.answered===c.applies?'p-done':(c.answered?'p-doing':'p-todo'))+'">'+
    '<span class="d"></span>'+c.answered+' of '+c.applies+' answered</span>'+
    '<span class="hint">registry holds the AHCA/CMS standard · Fact Store holds payor deltas</span></div>'+
    '<div class="scroll"><table><thead><tr><th>Requirement</th><th>Predicate</th>'+
    '<th>On file</th><th>Held by</th><th>Answer</th></tr></thead><tbody>'+
    R.map(function(r){
      var a=r.answers||[];
      return '<tr><td>'+esc(r.label||r.predicate)+
        (r.filing_critical?'<span class="flag">filing critical</span>':'')+
        (r.regulatory_authority?'<span class="cite" style="margin-left:5px">'+
          esc(r.regulatory_authority)+'</span>':'')+'</td>'+
        '<td class="c" style="font-size:10.5px;color:var(--ink-3)">'+esc(r.predicate)+'</td>'+
        '<td>'+(a.length? a.map(function(x){
            return '<span class="chip'+(x.resolves_from==='standard'?' on':'')+'" title="'+
              esc(x.owner||'')+'">'+esc((x.payer||'').split('|')[0])+'</span>';}).join(' ')
          : '<span class="pill p-todo"><span class="d"></span>none</span>')+'</td>'+
        '<td>'+(r.has_standard?'<span class="pill p-done"><span class="d"></span>ours</span>'
                 :(r.deltas.length?'<span class="pill p-doing"><span class="d"></span>Fact Store</span>'
                   :'<span class="pill p-todo"><span class="d"></span>nobody</span>'))+'</td>'+
        '<td style="font-size:11.5px;color:var(--ink-2)">'+
          (a.length? esc((a[0].answer||'').toString().slice(0,140))
           : '<span style="color:var(--crit)">Not sourced</span>')+'</td></tr>';
    }).join('')+'</tbody></table></div></div>';
}

function bindingCard(l){
  var roles=[['classified_by','Classified by','ICD-10-CM diagnoses that place an encounter in this line'],
             ['grouped_to','Grouped to','the APR-DRG the encounter resolves to — grain is (DRG, severity)']];
  var out='';
  roles.forEach(function(r){
    var rows=(l.bindings&&l.bindings[r[0]])||[];
    if(!rows.length) return;
    var base={}; rows.forEach(function(x){ (base[x.code]=base[x.code]||[]).push(x); });
    out+='<div class="card"><div class="ch"><h3>'+r[1]+'</h3>'+
      '<span class="hint">'+r[2]+'</span></div><div class="scroll"><table><thead><tr>'+
      '<th>Code</th><th>'+(r[0]==='grouped_to'?'Severity':'Block')+'</th><th>Definition</th>'+
      '<th>Source</th></tr></thead><tbody>'+
      Object.keys(base).sort().map(function(k){
        var g=base[k], q=g.map(function(x){return x.modifier;}).filter(Boolean).sort();
        return '<tr><td class="c">'+esc(k)+'</td>'+
          '<td class="c" style="font-size:11px">'+(q.length?q.join(' '):'—')+'</td>'+
          '<td>'+esc(g[0].definition||'')+'</td>'+
          '<td style="font-size:11px;color:var(--ink-3)">'+esc(g[0].cite.document||'')+'</td></tr>';
      }).join('')+'</tbody></table></div></div>';
  });
  return out;
}

function modifierCard(l){
  if(!l.allowed_modifiers||!l.allowed_modifiers.length) return '';
  return '<div class="card"><div class="ch"><h3>Allowed modifiers</h3>'+
    '<span class="hint">HCPCS Level II · consistent with observed AHCA usage</span></div>'+
    '<div class="scroll"><table><thead><tr><th>Modifier</th><th>Definition</th>'+
    '<th>Used on</th></tr></thead><tbody>'+
    (l.allowed_modifiers||[]).map(function(m){
      var on=l.codes.filter(function(c){return c.modifier===m;});
      return '<tr><td><span class="mod">'+m+'</span></td><td>'+esc(modDef(m))+'</td>'+
        '<td class="c" style="font-size:11.5px">'+
        Array.from(new Set(on.map(function(c){return c.code;}))).join(', ')+'</td></tr>';
    }).join('')+'</tbody></table></div></div>';
}

function renderLine(l){
  var d=score(l), g=M.filter(function(m){return l.status[m.key][0]==='doing';}).length, rq=req(l);
  var src=l.codes.length?l.codes[0].cite.document:null;
  return '<div class="ph"><div class="eyebrow">Service line · '+
    (l.rule?esc(l.rule):'no rule number')+'</div><h2>'+esc(l.name)+'</h2>'+
    '<p>'+(l.scope==='serve'
      ? 'Defined by AHCA’s own rule decomposition. Codes, allowed modifiers and service '+
        'definitions are read from the AHCA fee schedule, not authored here. Rates and unit '+
        'limits are deliberately not held — those are Fact Store’s.'
      : 'A service CMHCs really run, named here on purpose. Mobius does not support its rules — '+
        'it is governed by '+esc(l.authority)+', outside the AHCA fee schedule. Naming it means '+
        'every module can decline it correctly instead of missing the question in silence.')+
    '</p></div>'+

  (function(){
    var f=[];
    function add(label,val){f.push('<div class="field"><span class="l">'+label+
      '</span><span class="v">'+val+'</span></div>');}

    add('Scope', l.scope==='serve'
      ? '<span class="scope sc-serve">Serving</span>'
      : '<span class="scope sc-decline">Named, not served</span> <span style="color:var(--ink-3)">'+
        '— modules must decline correctly, not stay silent</span>');
    add('Authority', esc(l.authority));
    add('Payment grain', '<code>'+esc(l.grain)+'</code>'+(l.grain==='code_modifier' ? ''
      : ' <span style="color:var(--warn)">— not code grain; cannot be priced or counted like the '+
        'fee-schedule lines</span>'));
    add('Rule', l.rule ? '<code>'+l.rule+'</code> — '+esc(l.name)
      : (l.scope==='serve'
         ? '<span style="color:var(--warn)">No rule number in the AHCA manifest — needs adjudication</span>'
         : '<span style="color:var(--ink-3)">Not an AHCA rule — governed by '+esc(l.authority)+'</span>'));

    if(l.scope==='serve'){
      add('Fee schedule', (l.fee_schedule_family?esc(l.fee_schedule_family):'none identified')+
        (src ? ' · <span class="src">'+esc(src)+'</span>'
             : ' <span style="color:var(--crit)">· not in corpus</span>'));
      add('Modifiers', (l.allowed_modifiers||[]).length
        ? l.allowed_modifiers.map(function(m){
            return '<span class="mod" title="'+esc(modDef(m))+'">'+m+'</span>';}).join(' ')
        : '<span style="color:var(--ink-3)">none</span>');
      add('Codes', l.codes.length
        ? l.distinct_codes+' distinct procedure codes across <b>'+l.code_count+'</b> (code, modifier) pairs'+
          (l.unadjudicated_codes ? ' · <span style="color:var(--warn)">'+l.unadjudicated_codes+
            ' unadjudicated</span>' : '')
        : '<span style="color:var(--crit)">none loaded</span>');
      add('AHCA sources', l.source_documents+
        ' documents in the BH crawl manifest carry this rule number');
    } else {
      add('Corpus evidence', l.evidence_pages
        ? '<b>'+l.evidence_pages+'</b> pages across '+l.evidence_sources.length+
          ' sources mention this service — enough to decline usefully, not enough to support it'
        : '<span style="color:var(--crit)">none gathered</span>');
    }

    return '<div class="card"><div class="ch"><h3>Definition</h3>'+
      '<span class="hint">what every module builds against</span></div>'+
      '<div class="cb">'+f.join('')+'</div>'+
      (l.scope==='serve' ? codeTable(l) : evidenceTable(l))+'</div>';
  })()+ bindingCard(l) + requirementCard(l) + exceptionCard(l) +


  '<div class="card"><div class="ch"><h3>Module completion</h3>'+
    '<span class="hint">each module reports; the registry tracks</span></div>'+
    '<div class="cb" style="border-bottom:1px solid var(--line);padding-bottom:14px">'+
    '<div class="roll"><span class="big">'+d+'</span><span class="of">of '+rq+
    ' modules with an obligation for this line'+(rq<M.length?' ('+(M.length-rq)+' not applicable)':'')+
    '</span><div class="track"><i class="f-done" style="width:'+
    (d/rq*100)+'%"></i><i class="f-doing" style="width:'+(g/rq*100)+'%"></i></div></div></div>'+
    '<div class="cb"><div class="mods">'+
    M.map(function(m){var s=l.status[m.key];
      return '<div class="m"><div class="w"><b>'+esc(m.name)+'</b><span>'+esc(m.role)+'</span></div>'+
        '<div class="owes">'+esc(m.owes)+'<span class="said"><em>Evidence</em>'+esc(s[1])+'</span></div>'+
        '<div><span class="pill p-'+s[0]+'"><span class="d"></span>'+LAB[s[0]]+'</span></div></div>';
    }).join('')+'</div></div></div>';
}

function renderAll(){
  var rows=L.reduce(function(a,l){return a+l.code_count;},0);
  var withCodes=L.filter(function(l){return l.codes.length;}).length;
  return '<div class="ph"><div class="eyebrow">Master · '+esc(C.jurisdiction.state)+' '+
    esc(C.jurisdiction.program)+' · catalog v'+esc(C.catalog_version)+' ('+esc(C.status)+')</div>'+
    '<h2>Is every module complete for what we support?</h2>'+
    '<p>'+L.length+' service lines. The registry defines how Mobius names a service line and which '+
    'codes constitute it — nothing about any payor’s implementation, and nothing about any client. '+
    'A line binds codes three ways: <b>billed</b> (HCPCS you render), <b>Dx</b> (ICD-10-CM that '+
    'classifies the encounter) and <b>DRG</b> (APR-DRG it groups to). No rates, weights or limits — '+
    'those belong to Fact Store.</p></div>'+

  '<div class="card"><div class="cb" style="border-bottom:1px solid var(--line)">'+
    '<div class="roll"><span class="big">'+allDone+'</span><span class="of">of '+total+
    ' module×line obligations complete</span><div class="track"><i class="f-done" style="width:'+
    (allDone/total*100)+'%"></i></div></div></div>'+
    '<div class="scroll"><table><thead><tr><th>Service line</th><th>Rule</th>'+
    M.map(function(m){return '<th style="text-align:center">'+esc(m.name)+'</th>';}).join('')+
    '<th style="text-align:right">Billed</th><th style="text-align:right">Dx</th>'+
    '<th style="text-align:right">DRG</th><th>Grain</th><th>Authority</th></tr></thead><tbody>'+
    L.map(function(l,i){
      var hdr='';
      if(i===0) hdr='<tr><td colspan="'+(M.length+5)+'" style="background:var(--surface-2);'+
        'font-family:var(--mono);font-size:10px;letter-spacing:.13em;text-transform:uppercase;'+
        'color:var(--ink-3)">Serving</td></tr>';
      if(i>0 && L[i-1].scope==='serve' && l.scope!=='serve')
        hdr='<tr><td colspan="'+(M.length+5)+'" style="background:var(--surface-2);'+
        'font-family:var(--mono);font-size:10px;letter-spacing:.13em;text-transform:uppercase;'+
        'color:var(--ink-3)">Named, not served — modules must decline correctly</td></tr>';
      return hdr+'<tr><td><button class="lk" data-go="'+l.key+'">'+esc(l.name)+'</button></td>'+
        '<td class="c" style="font-size:11.5px;color:var(--ink-3)">'+(l.rule||'—')+'</td>'+
        M.map(function(m){var s=l.status[m.key][0];
          return '<td class="g"><span class="mk k-'+s+'" title="'+LAB[s]+'"></span></td>';}).join('')+
        '<td class="num">'+(l.binding_counts.rendered_as||'—')+'</td>'+
        '<td class="num">'+(l.binding_counts.classified_by||'—')+'</td>'+
        '<td class="num">'+(l.binding_counts.grouped_to||'—')+'</td>'+
        '<td class="num" style="font-size:11px">'+((l.requirement_counts&&l.requirement_counts.applies)
          ? l.requirement_counts.answered+'/'+l.requirement_counts.applies : '—')+'</td>'+
        '<td class="c" style="font-size:10.5px;color:'+(l.grain==='code_modifier'?'var(--ink-3)':'var(--warn)')+'">'+
          esc(l.grain)+'</td>'+
        '<td style="font-size:11px;color:var(--ink-3)">'+esc(l.authority)+'</td></tr>';
    }).join('')+'</tbody></table></div>'+
    '<div class="legend"><span><span class="mk k-done"></span>Complete</span>'+
    '<span><span class="mk k-doing"></span>In progress</span>'+
    '<span><span class="mk k-todo"></span>Not started</span></div></div>'+

  '<div class="card"><div class="ch"><h3>What we own vs. what we source</h3>'+
    '<span class="hint">the registry owns the service-code axis; linked stores own the payor axis</span>'+
    '</div><div class="scroll"><table><thead><tr><th>Domain</th><th>Standard</th>'+
    '<th>Registry owns</th><th>Linked store owns</th><th>Question we ask them</th></tr></thead><tbody>'+
    (C.ownership||[]).map(function(o){
      return '<tr><td class="c">'+esc(o.domain)+'</td>'+
        '<td>'+(o.standard_held_by==='registry'
          ? '<span class="pill p-done"><span class="d"></span>ours</span>'
          : '<span class="pill p-doing"><span class="d"></span>'+esc(o.other_store)+'</span>')+'</td>'+
        '<td>'+esc(o.registry_owns||'—')+'</td>'+
        '<td>'+esc(o.other_owns)+'</td>'+
        '<td style="color:var(--ink-3)">'+esc(o.question_asked)+'</td></tr>';
    }).join('')+'</tbody></table></div></div>'+

  '<div class="note"><b>Read the columns.</b> Lexicon is red down the entire column — 4,228 entries and '+
  'not one of these service terms or codes. Analytics is amber down every line with codes: it holds all '+
  'of them, but at bare-code grain, so H2019’s six distinct services collapse into one. Fact Store is the '+
  'only module with anything green, and only where a fee schedule page cites a single rule.</div>'+

  '<div class="note"><b>Provenance.</b> Service lines: '+esc(C.provenance.service_lines)+
  ' · Codes: '+esc(C.provenance.codes)+' · Grain: '+esc(C.provenance.grain)+'.</div>';
}

function show(v){
  rail.querySelectorAll('button').forEach(function(b){b.setAttribute('aria-current',String(b.dataset.v===v));});
  var l=L.filter(function(x){return x.key===v;})[0];
  try {
    main.innerHTML = l?renderLine(l):renderAll();
  } catch (err) {
    main.innerHTML = '<div class="ph"><div class="eyebrow">Render error</div><h2>'+
      (l?esc(l.name):'All service lines')+'</h2><p>This view failed to render: <code>'+
      esc(err.message)+'</code></p></div>';
    throw err;
  }
  window.scrollTo({top:0});
}
rail.addEventListener('click',function(e){var b=e.target.closest('button[data-v]'); if(b) show(b.dataset.v);});
main.addEventListener('click',function(e){var b=e.target.closest('button[data-go]'); if(b) show(b.dataset.go);});
show('all');
})();
</script>
"""


def main():
    html = HEAD + BODY.replace("__CATALOG__", json.dumps(CAT))
    open(OUT, "w").write(html)
    print(f"wrote {OUT}  ({len(html)//1024} KB)")


if __name__ == "__main__":
    main()
