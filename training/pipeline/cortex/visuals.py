from __future__ import annotations

import html
import json
from typing import Any


def render_mri(manifest: dict[str, Any], evaluation: dict[str, Any]) -> str:
    data = {
        "title": f"{manifest['display_name']} · Cortex MRI",
        "checkpoint": evaluation["certificate"]["candidate_checkpoint"],
        "candidate": evaluation["candidate"]["scan"]["activation_health"],
        "parent": evaluation["parent"]["scan"]["activation_health"],
    }
    return _page(
        data,
        data["title"],
        """
<div class="app mri-app">
  <aside class="rail">
    <div class="brand">NINEREEDS · MRI</div>
    <div class="muted" id="checkpoint"></div>
    <h2>LAYERS</h2><div id="layers"></div>
  </aside>
  <main class="stage">
    <div class="toolbar"><strong id="title"></strong><span class="pill">candidate vs parent</span></div>
    <div class="mri-summary" id="summary"></div>
    <div class="layer-grid" id="grid"></div>
  </main>
  <aside class="inspector">
    <div class="brand">INSPECTOR</div>
    <div id="inspect"></div>
    <h2>TOP NEURONS</h2><div id="neurons" class="panel"></div>
  </aside>
</div>
""",
        """
const DATA=__DATA__;
const candidate=DATA.candidate, parent=DATA.parent;
let selected=0;
const fmt=(v,n=4)=>Number(v??0).toFixed(n);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
document.getElementById('title').textContent=DATA.title;
document.getElementById('checkpoint').textContent=DATA.checkpoint;
const summary=document.getElementById('summary');
summary.innerHTML=[
 ['hidden mean |x|',candidate.hidden_mean_abs,parent.hidden_mean_abs],
 ['hidden std',candidate.hidden_std,parent.hidden_std],
 ['dead layers',candidate.dead_layers.length,parent.dead_layers.length],
 ['saturated',candidate.saturated_layers.length,parent.saturated_layers.length]
].map(x=>`<div class="metric"><span>${x[0]}</span><b>${fmt(x[1],6)}</b><small>parent ${fmt(x[2],6)}</small></div>`).join('');
function layerRows(){
 document.getElementById('layers').innerHTML=candidate.layers.map((l,i)=>`<button class="layer-button ${i===selected?'active':''}" data-i="${i}"><span>L${l.layer}</span><small>${(l.xy_sparse_density*100).toFixed(1)}%</small></button>`).join('');
 document.querySelectorAll('.layer-button').forEach(b=>b.onclick=()=>{selected=Number(b.dataset.i);render()});
}
function bar(label,value,parentValue,max,color){
 const width=Math.min(100,Math.max(1,value/max*100));
 const marker=Math.min(100,Math.max(0,parentValue/max*100));
 return `<div class="signal"><div class="signal-head"><span>${label}</span><b>${fmt(value)}</b></div><div class="track"><i style="width:${width}%;background:${color}"></i><em style="left:${marker}%"></em></div><small>parent ${fmt(parentValue)}</small></div>`;
}
function render(){
 layerRows();
 const l=candidate.layers[selected], p=parent.layers.find(x=>x.layer===l.layer&&x.tick===l.tick)||l;
 document.getElementById('grid').innerHTML=`
  <section class="scan-card"><h3>SPARSE DENSITY</h3>
   ${bar('x sparse',l.x_sparse_density,p.x_sparse_density,.75,'#62d7ff')}
   ${bar('y sparse',l.y_sparse_density,p.y_sparse_density,.75,'#b48cff')}
   ${bar('xy co-fire',l.xy_sparse_density,p.xy_sparse_density,.75,'#70f59a')}
  </section>
  <section class="scan-card"><h3>ACTIVATION MAGNITUDE · LOG SCALE</h3>
   ${bar('x mean |a|',Math.log1p(l.x_sparse_mean_abs),Math.log1p(p.x_sparse_mean_abs),8,'#62d7ff')}
   ${bar('y mean |a|',Math.log1p(l.y_sparse_mean_abs),Math.log1p(p.y_sparse_mean_abs),8,'#b48cff')}
   ${bar('xy mean |a|',Math.log1p(l.xy_sparse_mean_abs),Math.log1p(p.xy_sparse_mean_abs),8,'#70f59a')}
  </section>`;
 document.getElementById('inspect').innerHTML=`<div class="panel">
  <div class="kv"><span>layer</span><b>L${l.layer}</b></div><div class="kv"><span>compute tick</span><b>${l.tick}</b></div>
  <div class="kv"><span>co-fire density</span><b>${fmt(l.xy_sparse_density,6)}</b></div>
  <div class="kv"><span>parent delta</span><b>${fmt(l.xy_sparse_density-p.xy_sparse_density,6)}</b></div>
  <div class="kv"><span>health</span><b class="${l.xy_sparse_density<1e-6||l.xy_sparse_density>.75?'warn':'good'}">${l.xy_sparse_density<1e-6?'dead':l.xy_sparse_density>.75?'saturated':'healthy'}</b></div></div>`;
 const neurons=l.top_neurons||[];
 document.getElementById('neurons').innerHTML=neurons.length?neurons.map(n=>`<div class="neuron"><b>${esc(n.label||`L${l.layer}H${n.head}N${n.neuron}`)}</b><span>fire ${fmt(n.fire_rate,3)} · |a| ${fmt(n.mean_abs,3)}</span></div>`).join(''):`<p class="muted">Per-neuron evidence was not captured by this scan. Layer-level activity above is genuine; a future scan must not invent neuron identities.</p>`;
}
render();
""",
        extra_css="""
.mri-app{grid-template-columns:230px minmax(480px,1fr) 300px}
.mri-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:14px 18px}
.metric,.scan-card{background:#081713;border:1px solid #1e4636;border-radius:7px;padding:14px}
.metric span,.metric small{display:block;color:#78988a;font-size:10px}.metric b{display:block;color:#c9f7da;font-size:18px;margin:8px 0 4px}
.layer-button{width:100%;display:flex;justify-content:space-between;background:transparent;color:#9bb9aa;border:0;border-left:2px solid transparent;padding:7px 10px;cursor:pointer}
.layer-button.active{background:#102b20;border-color:#70f59a;color:#e2ffec}.layer-button small{color:#5e8974}
.layer-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:8px 18px 18px}.scan-card h3{font-size:10px;letter-spacing:2px;color:#69a984;margin:0 0 18px}
.signal{margin:15px 0}.signal-head{display:flex;justify-content:space-between;font-size:11px}.signal small{color:#587767}
.track{height:12px;background:#030907;margin:5px 0;position:relative;border:1px solid #183629}.track i{display:block;height:100%}.track em{position:absolute;top:-3px;height:16px;border-left:2px solid #fff}
""",
    )


def render_graph(manifest: dict[str, Any], evaluation: dict[str, Any]) -> str:
    cases = {row["case_id"]: row for row in evaluation["candidate"]["cases"]}
    points = []
    for point in evaluation["candidate"]["scan"]["points"]["core"]:
        row = cases.get(point["case_id"], {})
        points.append({**point, "prompt": row.get("prompt"), "response": row.get("response")})
    data = {
        "title": f"{manifest['display_name']} · Core representation map",
        "checkpoint": evaluation["certificate"]["candidate_checkpoint"],
        "points": points,
    }
    return _page(
        data,
        data["title"],
        """
<div class="graph-shell">
 <canvas id="space"></canvas>
 <aside class="graph-side">
  <div class="brand">NINEREEDS · 3D MAP</div>
  <div id="stats" class="muted"></div>
  <h2>NODE INFO</h2><div id="node" class="panel"><p class="muted">Hover or click a node.</p></div>
  <h2>CONCEPTS</h2><div id="concepts"></div>
  <h2>CONTROLS</h2><div class="muted control-copy">drag — rotate<br>scroll — zoom<br>click — lock inspector<br>double-click — reset</div>
 </aside>
</div>
""",
        """
const DATA=__DATA__, canvas=document.getElementById('space'),ctx=canvas.getContext('2d');
const palette=['#58b7ff','#72f1a6','#ffcf66','#c397ff','#ff7f9f','#55ddd2','#f59b5b'];
const concepts=[...new Set(DATA.points.map(p=>p.concept))], visible=Object.fromEntries(concepts.map(x=>[x,true]));
let ax=-.18,ay=.55,zoom=1,drag=false,lastX=0,lastY=0,locked=null,projected=[];
const color=c=>palette[concepts.indexOf(c)%palette.length];
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function resize(){const d=devicePixelRatio||1;canvas.width=innerWidth*d;canvas.height=innerHeight*d;canvas.style.width=innerWidth+'px';canvas.style.height=innerHeight+'px';ctx.setTransform(d,0,0,d,0,0);draw()}
function rotate(p){let x=p.x,y=p.y,z=p.z;let c=Math.cos(ay),s=Math.sin(ay);[x,z]=[x*c-z*s,x*s+z*c];c=Math.cos(ax);s=Math.sin(ax);[y,z]=[y*c-z*s,y*s+z*c];return{x,y,z}}
function edges(points){const out=[];points.forEach((a,i)=>{points.map((b,j)=>({j,d:(a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2})).filter(x=>x.j!==i).sort((u,v)=>u.d-v.d).slice(0,2).forEach(x=>{if(i<x.j)out.push([i,x.j,x.d])})});return out}
function draw(){const w=innerWidth-310,h=innerHeight;ctx.clearRect(0,0,w,h);ctx.fillStyle='#020713';ctx.fillRect(0,0,w,h);const pts=DATA.points.filter(p=>visible[p.concept]).map(p=>({...p,...rotate(p)}));const scale=Math.min(w,h)*.34*zoom;projected=pts.map(p=>({...p,sx:w/2+p.x*scale,sy:h/2-p.y*scale}));edges(projected).forEach(([a,b,d])=>{const u=projected[a],v=projected[b];ctx.strokeStyle=`rgba(65,130,180,${Math.max(.08,.3-d/8)})`;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(u.sx,u.sy);ctx.lineTo(v.sx,v.sy);ctx.stroke()});projected.sort((a,b)=>a.z-b.z).forEach(p=>{const r=p.group==='protected'?7:6;ctx.fillStyle=color(p.concept);ctx.strokeStyle=p.case_id===locked?'#fff':'#06101c';ctx.lineWidth=p.case_id===locked?3:1.5;ctx.beginPath();if(p.group==='protected')ctx.rect(p.sx-r,p.sy-r,r*2,r*2);else ctx.arc(p.sx,p.sy,r,0,Math.PI*2);ctx.fill();ctx.stroke();ctx.fillStyle='#b8d7e9';ctx.font='11px ui-monospace';ctx.fillText(p.case_id,p.sx+10,p.sy+4)})}
function nearest(e){const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;return projected.map(p=>({p,d:(p.sx-x)**2+(p.sy-y)**2})).sort((a,b)=>a.d-b.d)[0]}
function inspect(p){if(!p)return;document.getElementById('node').innerHTML=`<div class="node-title">${esc(p.case_id)}</div><div class="kv"><span>concept</span><b style="color:${color(p.concept)}">${esc(p.concept)}</b></div><div class="kv"><span>language</span><b>${esc(p.language)}</b></div><div class="kv"><span>group</span><b>${esc(p.group)}</b></div><div class="coords">x ${p.x.toFixed(4)} · y ${p.y.toFixed(4)} · z ${p.z.toFixed(4)}</div><h3>PROMPT</h3><p>${esc(p.prompt)}</p><h3>RESPONSE</h3><p>${esc(p.response)}</p>`}
document.getElementById('stats').textContent=`${DATA.points.length} probes · ${concepts.length} concepts · orthographic PCA`;
document.getElementById('concepts').innerHTML=concepts.map(c=>`<button class="concept-row" data-c="${esc(c)}"><i style="background:${color(c)}"></i><span>${esc(c)}</span><small>${DATA.points.filter(p=>p.concept===c).length}</small></button>`).join('');
document.querySelectorAll('.concept-row').forEach(b=>b.onclick=()=>{visible[b.dataset.c]=!visible[b.dataset.c];b.classList.toggle('off',!visible[b.dataset.c]);draw()});
canvas.onmousedown=e=>{drag=true;lastX=e.clientX;lastY=e.clientY};onmouseup=()=>drag=false;canvas.onmousemove=e=>{if(drag){ay+=(e.clientX-lastX)/180;ax+=(e.clientY-lastY)/180;lastX=e.clientX;lastY=e.clientY;draw()}else if(!locked){const n=nearest(e);if(n&&n.d<500)inspect(n.p)}};canvas.onclick=e=>{const n=nearest(e);if(n&&n.d<500){locked=n.p.case_id;inspect(n.p);draw()}};canvas.onwheel=e=>{e.preventDefault();zoom=Math.max(.35,Math.min(4,zoom*Math.exp(-e.deltaY*.001)));draw()};canvas.ondblclick=()=>{ax=-.18;ay=.55;zoom=1;locked=null;draw()};onresize=resize;resize();
""",
        extra_css="""
.graph-shell{position:fixed;inset:0;background:#020713}.graph-side{position:fixed;right:0;top:0;bottom:0;width:310px;padding:16px;background:rgba(4,10,24,.97);border-left:1px solid #173552;overflow:auto}#space{position:fixed;inset:0 310px 0 0}
.concept-row{width:100%;display:flex;align-items:center;gap:8px;border:0;background:transparent;color:#a9c7d9;padding:5px;cursor:pointer}.concept-row:hover{background:#0c2235}.concept-row.off{opacity:.25}.concept-row i{width:9px;height:9px;border-radius:50%}.concept-row small{margin-left:auto;color:#52758c}.node-title{color:#75d8ff;font-weight:700;word-break:break-word}.coords{font-size:10px;color:#62859a;margin:8px 0}.control-copy{line-height:1.9}
""",
        tone="blue",
    )


def render_atlas(manifest: dict[str, Any], evaluation: dict[str, Any]) -> str:
    data = {
        "title": f"{manifest['display_name']} · Cortex atlas",
        "checkpoint": evaluation["certificate"]["candidate_checkpoint"],
        "cases": evaluation["candidate"]["cases"],
        "points": evaluation["candidate"]["scan"]["points"],
        "health": evaluation["candidate"]["scan"]["representation_health"],
        "activation": evaluation["candidate"]["scan"]["activation_health"],
    }
    return _page(
        data,
        data["title"],
        """
<div class="app atlas-app">
 <aside class="rail"><div class="brand">NINEREEDS · ATLAS</div><div id="summary" class="muted"></div><h2>STAGE</h2><div id="stages"></div><h2>CONCEPTS</h2><div id="concepts"></div></aside>
 <main class="stage"><div class="toolbar"><strong id="title"></strong><span class="pill" id="stageName"></span></div><svg id="atlas"></svg></main>
 <aside class="inspector"><div class="brand">INSPECTOR</div><div id="inspect"></div><h2>PROBES</h2><div id="probes"></div><h2>NEURON EVIDENCE</h2><div id="neurons" class="panel"></div></aside>
</div>
""",
        """
const DATA=__DATA__, svg=document.getElementById('atlas');
const palette=['#63e6a2','#65b9ff','#ffcf70','#ca94ff','#ff7e99','#55ddd2','#f39d64'];
const concepts=[...new Set(DATA.cases.map(c=>c.concept))], stages=['ingress','core','intentions'];let stage='core',selected=concepts[0];
const color=c=>palette[concepts.indexOf(c)%palette.length],esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
document.getElementById('title').textContent=DATA.title;document.getElementById('summary').innerHTML=`${concepts.length} concepts · ${DATA.cases.length} probes<br>${esc(DATA.checkpoint)}`;
document.getElementById('stages').innerHTML=stages.map(s=>`<button class="layer-button" data-s="${s}">${s}</button>`).join('');
document.querySelectorAll('[data-s]').forEach(b=>b.onclick=()=>{stage=b.dataset.s;render()});
function conceptPoints(){const pts=DATA.points[stage],groups={};pts.forEach(p=>(groups[p.concept]??=[]).push(p));return concepts.map(c=>{const a=groups[c]||[];return{id:c,count:a.length,x:a.reduce((s,p)=>s+p.x,0)/Math.max(1,a.length),y:a.reduce((s,p)=>s+p.y,0)/Math.max(1,a.length),z:a.reduce((s,p)=>s+p.z,0)/Math.max(1,a.length)}})}
function render(){
 document.querySelectorAll('[data-s]').forEach(b=>b.classList.toggle('active',b.dataset.s===stage));document.getElementById('stageName').textContent=stage;
 document.getElementById('concepts').innerHTML=concepts.map(c=>`<button class="concept-row ${c===selected?'active':''}" data-c="${esc(c)}"><i style="background:${color(c)}"></i><span>${esc(c)}</span><small>${DATA.cases.filter(x=>x.concept===c).length}</small></button>`).join('');document.querySelectorAll('[data-c]').forEach(b=>b.onclick=()=>{selected=b.dataset.c;render()});
 const w=svg.clientWidth||900,h=svg.clientHeight||700,pts=conceptPoints();const minX=Math.min(...pts.map(p=>p.x)),maxX=Math.max(...pts.map(p=>p.x)),minY=Math.min(...pts.map(p=>p.y)),maxY=Math.max(...pts.map(p=>p.y));const sx=x=>90+(x-minX)/(maxX-minX||1)*(w-180),sy=y=>90+(y-minY)/(maxY-minY||1)*(h-180);const edges=[];pts.forEach((a,i)=>pts.map((b,j)=>({j,d:(a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2})).filter(x=>x.j!==i).sort((u,v)=>u.d-v.d).slice(0,2).forEach(x=>{if(i<x.j)edges.push([a,pts[x.j],x.d])}));svg.innerHTML='';edges.forEach(([a,b,d])=>{const e=document.createElementNS('http://www.w3.org/2000/svg','line');e.setAttribute('x1',sx(a.x));e.setAttribute('y1',sy(a.y));e.setAttribute('x2',sx(b.x));e.setAttribute('y2',sy(b.y));e.setAttribute('class','atlas-edge');e.setAttribute('stroke-opacity',Math.max(.12,.7-d));svg.appendChild(e)});pts.forEach(p=>{const g=document.createElementNS('http://www.w3.org/2000/svg','g');g.setAttribute('class','atlas-node');g.innerHTML=`<circle cx="${sx(p.x)}" cy="${sy(p.y)}" r="${10+p.count*2}" fill="${color(p.id)}" class="${p.id===selected?'selected':''}"></circle><text x="${sx(p.x)+15}" y="${sy(p.y)+4}">${esc(p.id)}</text>`;g.onclick=()=>{selected=p.id;render()};svg.appendChild(g)});
 const cases=DATA.cases.filter(c=>c.concept===selected),health=DATA.health[stage];document.getElementById('inspect').innerHTML=`<div class="panel"><div class="node-title" style="color:${color(selected)}">${esc(selected)}</div><div class="kv"><span>probes</span><b>${cases.length}</b></div><div class="kv"><span>within cosine</span><b>${health.within_concept_cosine.toFixed(6)}</b></div><div class="kv"><span>between cosine</span><b>${health.between_concept_cosine.toFixed(6)}</b></div><div class="kv"><span>separation</span><b class="${health.concept_separation>0?'good':'warn'}">${health.concept_separation.toFixed(6)}</b></div></div>`;
 document.getElementById('probes').innerHTML=cases.map(c=>`<details class="probe"><summary>${esc(c.case_id)} · ${esc(c.language)}</summary><p>${esc(c.prompt)}</p><small>response</small><p>${esc(c.response)}</p></details>`).join('');
 const neurons=(DATA.activation.concept_neurons||{})[selected]||[];document.getElementById('neurons').innerHTML=neurons.length?neurons.map(n=>`<div class="neuron"><b>${esc(n.label)}</b><span>fire ${Number(n.fire_rate).toFixed(3)}</span></div>`).join(''):`<p class="muted">This evaluation contains representation geometry and layer health, but predates concept-level neuron capture. No campaign 16 neurons are substituted.</p>`;
}
onresize=render;render();
""",
        extra_css="""
.atlas-app{grid-template-columns:240px minmax(520px,1fr) 330px}.atlas-edge{stroke:#5c9471;stroke-width:1.4}.atlas-node{cursor:pointer}.atlas-node text{fill:#cce4d4;font:11px ui-monospace}.atlas-node circle{stroke:#07140e;stroke-width:2}.atlas-node circle.selected{stroke:#fff;stroke-width:3}.probe{border-bottom:1px solid #173326;padding:7px 2px;font-size:10px}.probe summary{cursor:pointer;color:#a9c9b6}.probe p{color:#7fa08d;line-height:1.45}.probe small{color:#4f7e65}
""",
    )


def _page(
    data: dict[str, Any],
    title: str,
    body: str,
    script: str,
    *,
    extra_css: str = "",
    tone: str = "green",
) -> str:
    colors = (
        ("#58b7ff", "#173552", "#07111f")
        if tone == "blue"
        else ("#70f59a", "#1e4636", "#06110c")
    )
    safe_title = html.escape(title)
    payload = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{safe_title}</title><style>
*{{box-sizing:border-box}}html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:#020905;color:#d5ebdd;font:12px ui-monospace,SFMono-Regular,Consolas,monospace}}
.app{{display:grid;height:100vh}}.rail,.inspector{{padding:16px;background:{colors[2]};overflow:auto}}.rail{{border-right:1px solid {colors[1]}}}.inspector{{border-left:1px solid {colors[1]}}}.stage{{position:relative;overflow:hidden;background:radial-gradient(circle at 50% 40%,rgba(45,120,80,.16),transparent 45%),#030b08}}
.brand{{color:{colors[0]};font-size:11px;letter-spacing:2.5px;padding-bottom:10px;border-bottom:1px solid {colors[1]}}}h2{{font-size:9px;color:#678b78;letter-spacing:2px;margin:18px 0 8px;border-bottom:1px solid {colors[1]};padding-bottom:5px}}h3{{font-size:9px;color:#6d9b82;letter-spacing:1px;margin-top:12px}}.muted{{color:#668477;font-size:10px;line-height:1.5;word-break:break-word}}.toolbar{{height:48px;display:flex;align-items:center;justify-content:space-between;padding:0 18px;border-bottom:1px solid {colors[1]};color:#b9dec9}}.pill{{font-size:9px;color:#739987;border:1px solid {colors[1]};border-radius:999px;padding:4px 8px}}.panel{{background:#081713;border:1px solid {colors[1]};border-radius:6px;padding:11px;margin:9px 0}}.kv{{display:flex;justify-content:space-between;gap:12px;margin:6px 0;font-size:10px}}.kv span{{color:#6d8b7b}}.kv b{{color:#cce9d8;text-align:right}}.good{{color:#70f59a!important}}.warn{{color:#ffc86b!important}}.neuron{{display:flex;justify-content:space-between;gap:8px;border-bottom:1px solid #173326;padding:5px 0;font-size:9px}}.neuron b{{color:#b8dec8}}.neuron span{{color:#6e9980}}svg{{width:100%;height:calc(100% - 48px)}}{extra_css}
</style></head><body>{body}<script>{script.replace("__DATA__", payload)}</script></body></html>"""
