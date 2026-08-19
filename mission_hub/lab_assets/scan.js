const root=document.querySelector("#scanRoot");
const params=new URLSearchParams(location.search);
const artifact=params.get("artifact"),view=params.get("view");
const palette=["#63e6a2","#65b9ff","#ffcf70","#ca94ff","#ff7e99","#55ddd2","#f39d64"];
const esc=(value)=>String(value??"").replace(/[&<>"']/g,(c)=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const fmt=(value,digits=4)=>Number(value??0).toFixed(digits);

async function load(){
  if(!artifact||!["mri","atlas","map"].includes(view))throw new Error("This Observatory link is incomplete.");
  const response=await fetch(`/lab/api/observatory/evaluations/${encodeURIComponent(artifact)}`,{headers:{Accept:"application/json"}});
  if(response.status===401){location.replace("/login");return}
  const data=await response.json().catch(()=>({}));
  if(!response.ok)throw new Error(data.message||data.error||`Evidence request failed (${response.status})`);
  const evaluation=data.evaluation;
  const branch=data.manifest.branch_id||evaluation.evaluation_context?.branch_id||evaluation.campaign_id;
  document.title=`${branch} · ${view==='map'?'3D map':view.toUpperCase()}`;
  if(view==="mri")renderMRI(evaluation,branch);
  if(view==="atlas")renderAtlas(evaluation,branch);
  if(view==="map")renderMap(evaluation,branch);
}

function shell(brand,branch,checkpoint,stage,inspector=""){
  root.innerHTML=`<div class="scan-shell"><aside class="rail"><div class="brand">NINEREEDS · ${esc(brand)}</div><div class="checkpoint muted">${esc(checkpoint)}</div><div id="railContent"></div></aside><main class="stage"><div class="toolbar"><strong>${esc(branch)}</strong><span class="pill">immutable evaluation evidence</span></div><div id="stageContent">${stage}</div></main><aside class="inspector"><div class="brand">INSPECTOR</div><div id="inspectorContent">${inspector}</div></aside></div>`;
}

function renderMRI(evaluation,branch){
  const candidate=evaluation.candidate.scan.activation_health,parent=evaluation.parent.scan.activation_health;
  shell("MRI",branch,evaluation.candidate.checkpoint,"<div id=summary class=summary-grid></div><div id=layerGrid class=layer-grid></div>","<div id=inspect></div><div class=section-label>TOP CO-FIRING DIMENSIONS</div><div id=neurons class=panel></div>");
  document.querySelector("#railContent").innerHTML="<div class=section-label>LAYERS</div><div id=layers></div>";
  document.querySelector("#summary").innerHTML=[
    ["hidden mean |x|",candidate.hidden_mean_abs,parent.hidden_mean_abs],["hidden std",candidate.hidden_std,parent.hidden_std],
    ["dead layers",candidate.dead_layers.length,parent.dead_layers.length],["saturated",candidate.saturated_layers.length,parent.saturated_layers.length],
  ].map(([label,value,prior])=>`<div class=metric><span>${label}</span><b>${fmt(value,6)}</b><small>parent ${fmt(prior,6)}</small></div>`).join("");
  let selected=0;
  const bar=(label,value,prior,max,color)=>`<div class=signal><div class=signal-head><span>${label}</span><b>${fmt(value)}</b></div><div class=track><i style="width:${Math.min(100,Math.max(1,value/max*100))}%;background:${color}"></i><em style="left:${Math.min(100,Math.max(0,prior/max*100))}%"></em></div><small class=muted>parent ${fmt(prior)}</small></div>`;
  const draw=()=>{
    document.querySelector("#layers").innerHTML=candidate.layers.map((layer,index)=>`<button class="choice ${index===selected?'active':''}" data-layer=${index}><span>L${layer.layer}</span><small>${(layer.xy_sparse_density*100).toFixed(1)}%</small></button>`).join("");
    document.querySelectorAll("[data-layer]").forEach((button)=>button.onclick=()=>{selected=Number(button.dataset.layer);draw()});
    const layer=candidate.layers[selected],prior=parent.layers.find((item)=>item.layer===layer.layer&&item.tick===layer.tick)||layer;
    document.querySelector("#layerGrid").innerHTML=`<section class=scan-card><h2>SPARSE DENSITY</h2>${bar("x sparse",layer.x_sparse_density,prior.x_sparse_density,.75,"#62d7ff")}${bar("y sparse",layer.y_sparse_density,prior.y_sparse_density,.75,"#b48cff")}${bar("xy co-fire",layer.xy_sparse_density,prior.xy_sparse_density,.75,"#70f59a")}</section><section class=scan-card><h2>ACTIVATION MAGNITUDE · LOG SCALE</h2>${bar("x mean |a|",Math.log1p(layer.x_sparse_mean_abs),Math.log1p(prior.x_sparse_mean_abs),20,"#62d7ff")}${bar("y mean |a|",Math.log1p(layer.y_sparse_mean_abs),Math.log1p(prior.y_sparse_mean_abs),20,"#b48cff")}${bar("xy mean |a|",Math.log1p(layer.xy_sparse_mean_abs),Math.log1p(prior.xy_sparse_mean_abs),20,"#70f59a")}</section>`;
    const health=layer.xy_sparse_density<1e-6?"dead":layer.xy_sparse_density>.75?"saturated":"within observed range";
    document.querySelector("#inspect").innerHTML=`<div class=panel><div class=kv><span>layer</span><b>L${layer.layer}</b></div><div class=kv><span>compute tick</span><b>${layer.tick}</b></div><div class=kv><span>co-fire density</span><b>${fmt(layer.xy_sparse_density,6)}</b></div><div class=kv><span>parent delta</span><b>${fmt(layer.xy_sparse_density-prior.xy_sparse_density,6)}</b></div><div class=kv><span>diagnostic</span><b class="${health==='within observed range'?'good':'warn'}">${health}</b></div></div>`;
    const neurons=layer.top_neurons||[];
    document.querySelector("#neurons").innerHTML=neurons.length?neurons.map((n)=>`<div class=neuron><b>${esc(n.label||`L${layer.layer}H${n.head}N${n.neuron}`)}</b><span>fire ${fmt(n.fire_rate,3)} · |a| ${fmt(n.mean_abs,2)}</span></div>`).join(""):"<p class=muted>No per-dimension evidence was captured. Nothing is inferred.</p>";
  };draw();
}

function renderAtlas(evaluation,branch){
  const candidate=evaluation.candidate,concepts=[...new Set(candidate.cases.map((row)=>row.concept))],stages=["ingress","core","intentions"];
  shell("ATLAS",branch,candidate.checkpoint,"<svg id=atlas class=atlas-svg></svg>","<div id=atlasInspect></div><div class=section-label>PROBES</div><div id=probes></div><div class=section-label>CO-FIRING EVIDENCE</div><div id=conceptNeurons class=panel></div>");
  document.querySelector("#railContent").innerHTML="<div class=section-label>STAGE</div><div id=stages></div><div class=section-label>CONCEPTS</div><div id=concepts></div>";
  let stage="core",selected=concepts[0];const color=(concept)=>palette[concepts.indexOf(concept)%palette.length];
  const draw=()=>{
    document.querySelector("#stages").innerHTML=stages.map((name)=>`<button class="choice ${name===stage?'active':''}" data-stage=${name}>${name}</button>`).join("");
    document.querySelectorAll("[data-stage]").forEach((button)=>button.onclick=()=>{stage=button.dataset.stage;draw()});
    document.querySelector("#concepts").innerHTML=concepts.map((concept)=>`<button class="concept ${concept===selected?'active':''}" data-concept="${esc(concept)}"><i style="background:${color(concept)}"></i><span>${esc(concept)}</span><small>${candidate.cases.filter((row)=>row.concept===concept).length}</small></button>`).join("");
    document.querySelectorAll("[data-concept]").forEach((button)=>button.onclick=()=>{selected=button.dataset.concept;draw()});
    const svg=document.querySelector("#atlas"),rect=svg.getBoundingClientRect(),width=rect.width||900,height=rect.height||700,groups={};
    candidate.scan.points[stage].forEach((point)=>(groups[point.concept]??=[]).push(point));
    const points=concepts.map((concept)=>{const rows=groups[concept]||[];return{concept,count:rows.length,x:rows.reduce((sum,row)=>sum+row.x,0)/Math.max(1,rows.length),y:rows.reduce((sum,row)=>sum+row.y,0)/Math.max(1,rows.length),z:rows.reduce((sum,row)=>sum+row.z,0)/Math.max(1,rows.length)}});
    const xs=points.map((p)=>p.x),ys=points.map((p)=>p.y),sx=(x)=>80+(x-Math.min(...xs))/(Math.max(...xs)-Math.min(...xs)||1)*(width-160),sy=(y)=>80+(y-Math.min(...ys))/(Math.max(...ys)-Math.min(...ys)||1)*(height-160);
    const edges=[];points.forEach((a,index)=>points.map((b,j)=>({j,d:(a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2})).filter((row)=>row.j!==index).sort((a,b)=>a.d-b.d).slice(0,2).forEach((row)=>{if(index<row.j)edges.push([a,points[row.j],row.d])}));
    svg.innerHTML=edges.map(([a,b,d])=>`<line class=edge x1=${sx(a.x)} y1=${sy(a.y)} x2=${sx(b.x)} y2=${sy(b.y)} stroke-opacity=${Math.max(.12,.7-d)}></line>`).join("")+points.map((p)=>`<g class="node ${p.concept===selected?'selected':''}" data-node="${esc(p.concept)}"><circle cx=${sx(p.x)} cy=${sy(p.y)} r=${10+p.count*2} fill=${color(p.concept)}></circle><text x=${sx(p.x)+15} y=${sy(p.y)+4}>${esc(p.concept)}</text></g>`).join("");
    document.querySelectorAll("[data-node]").forEach((node)=>node.onclick=()=>{selected=node.dataset.node;draw()});
    const cases=candidate.cases.filter((row)=>row.concept===selected),health=candidate.scan.representation_health[stage];
    document.querySelector("#atlasInspect").innerHTML=`<div class=panel><div style="color:${color(selected)};font-weight:800">${esc(selected)}</div><div class=kv><span>probes</span><b>${cases.length}</b></div><div class=kv><span>within cosine</span><b>${fmt(health.within_concept_cosine,6)}</b></div><div class=kv><span>between cosine</span><b>${fmt(health.between_concept_cosine,6)}</b></div><div class=kv><span>separation</span><b class=${health.concept_separation>0?'good':'warn'}>${fmt(health.concept_separation,6)}</b></div></div>`;
    document.querySelector("#probes").innerHTML=cases.map((row)=>`<details class=probe><summary>${esc(row.case_id)} · ${esc(row.language)}</summary><p>${esc(row.prompt)}</p><small class=muted>response</small><p>${esc(row.response)}</p></details>`).join("");
    const neurons=candidate.scan.activation_health.concept_neurons?.[selected]||[];
    document.querySelector("#conceptNeurons").innerHTML=neurons.length?neurons.map((n)=>`<div class=neuron><b>${esc(n.label)}</b><span>fire ${fmt(n.fire_rate,3)}</span></div>`).join(""):"<p class=muted>No concept-level co-firing evidence was captured.</p>";
  };draw();window.onresize=draw;
}

function renderMap(evaluation,branch){
  const candidate=evaluation.candidate,cases=Object.fromEntries(candidate.cases.map((row)=>[row.case_id,row])),points=candidate.scan.points.core.map((point)=>({...point,...cases[point.case_id]}));
  root.innerHTML=`<div class=map-shell><canvas id=space></canvas><aside class=map-side><div class=brand>NINEREEDS · 3D MAP</div><p class="muted checkpoint">${esc(branch)}<br>${esc(candidate.checkpoint)}</p><div class=section-label>NODE INFO</div><div id=mapNode class="panel map-node"><p>Hover or click a node.</p></div><div class=section-label>CONCEPTS</div><div id=mapConcepts></div><div class=section-label>CONTROLS</div><p class=muted>drag — rotate<br>scroll — zoom<br>click — lock inspector<br>double-click — reset</p></aside></div>`;
  const canvas=document.querySelector("#space"),context=canvas.getContext("2d"),concepts=[...new Set(points.map((p)=>p.concept))],visible=Object.fromEntries(concepts.map((c)=>[c,true]));
  const color=(concept)=>palette[concepts.indexOf(concept)%palette.length];let ax=-.18,ay=.55,zoom=1,drag=false,lastX=0,lastY=0,locked=null,projected=[];
  document.querySelector("#mapConcepts").innerHTML=concepts.map((concept)=>`<button class=concept data-map-concept="${esc(concept)}"><i style="background:${color(concept)}"></i><span>${esc(concept)}</span><small>${points.filter((p)=>p.concept===concept).length}</small></button>`).join("");
  document.querySelectorAll("[data-map-concept]").forEach((button)=>button.onclick=()=>{visible[button.dataset.mapConcept]=!visible[button.dataset.mapConcept];button.classList.toggle("active",visible[button.dataset.mapConcept]);draw()});
  const rotate=(p)=>{let{x,y,z}=p,c=Math.cos(ay),s=Math.sin(ay);[x,z]=[x*c-z*s,x*s+z*c];c=Math.cos(ax);s=Math.sin(ax);[y,z]=[y*c-z*s,y*s+z*c];return{x,y,z}};
  const draw=()=>{const width=innerWidth-310,height=innerHeight,d=devicePixelRatio||1;canvas.width=width*d;canvas.height=height*d;canvas.style.width=`${width}px`;canvas.style.height=`${height}px`;context.setTransform(d,0,0,d,0,0);context.fillStyle="#020805";context.fillRect(0,0,width,height);const scale=Math.min(width,height)*.34*zoom;projected=points.filter((p)=>visible[p.concept]).map((p)=>({...p,...rotate(p)})).map((p)=>({...p,sx:width/2+p.x*scale,sy:height/2-p.y*scale}));projected.forEach((a,index)=>projected.map((b,j)=>({j,d:(a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2})).filter((row)=>row.j!==index).sort((a,b)=>a.d-b.d).slice(0,2).forEach((row)=>{if(index>=row.j)return;const b=projected[row.j];context.strokeStyle=`rgba(72,160,105,${Math.max(.07,.3-row.d/8)})`;context.beginPath();context.moveTo(a.sx,a.sy);context.lineTo(b.sx,b.sy);context.stroke()}));projected.sort((a,b)=>a.z-b.z).forEach((p)=>{context.fillStyle=color(p.concept);context.strokeStyle=p.case_id===locked?"#fff":"#06100a";context.lineWidth=p.case_id===locked?3:1.5;context.beginPath();context.arc(p.sx,p.sy,6,0,Math.PI*2);context.fill();context.stroke();context.fillStyle="#bdd8c7";context.fillText(p.case_id,p.sx+10,p.sy+4)})};
  const nearest=(event)=>projected.map((p)=>({p,d:(p.sx-event.clientX)**2+(p.sy-event.clientY)**2})).sort((a,b)=>a.d-b.d)[0];
  const inspect=(p)=>{if(!p)return;document.querySelector("#mapNode").innerHTML=`<h2>${esc(p.case_id)}</h2><div class=kv><span>concept</span><b style="color:${color(p.concept)}">${esc(p.concept)}</b></div><div class=kv><span>language</span><b>${esc(p.language)}</b></div><p>${esc(p.prompt)}</p><div class=section-label>RESPONSE</div><p>${esc(p.response)}</p>`};
  canvas.onmousedown=(e)=>{drag=true;lastX=e.clientX;lastY=e.clientY};window.onmouseup=()=>drag=false;canvas.onmousemove=(e)=>{if(drag){ay+=(e.clientX-lastX)/180;ax+=(e.clientY-lastY)/180;lastX=e.clientX;lastY=e.clientY;draw()}else if(!locked){const n=nearest(e);if(n&&n.d<500)inspect(n.p)}};canvas.onclick=(e)=>{const n=nearest(e);if(n&&n.d<500){locked=n.p.case_id;inspect(n.p);draw()}};canvas.onwheel=(e)=>{e.preventDefault();zoom=Math.max(.35,Math.min(4,zoom*Math.exp(-e.deltaY*.001)));draw()};canvas.ondblclick=()=>{ax=-.18;ay=.55;zoom=1;locked=null;draw()};window.onresize=draw;draw();
}

load().catch((error)=>{root.innerHTML=`<div class=error>${esc(error.message)}</div>`});
