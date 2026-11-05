"use strict";
const el=id=>document.getElementById(id),fmt=n=>Number(n).toLocaleString("en-US");
const NS="http://www.w3.org/2000/svg";
const colors=["#7fd8ca","#a89bff","#d9c38d","#8fb6ff","#e0a3ff","#9fd3b0","#ff9ba5"];
let queue=[],page=0,runId=null,evidence=null,chartMode="flow",barMode="fraud",activity=[],latest=null,sessionRuns=[],savedRuns=[];
const pageSize=50;
const digits={
 "0":["01110","11011","11011","11011","11011","11011","01110"],
 "1":["00100","01100","00100","00100","00100","00100","01110"],
 "2":["01110","10001","00001","00110","01000","10000","11111"],
 "3":["11110","00001","00001","01110","00001","00001","11110"],
 "4":["00010","00110","01010","10010","11111","00010","00010"],
 "5":["11111","10000","10000","11110","00001","00001","11110"],
 "6":["01110","10000","10000","11110","10001","10001","01110"],
 "7":["11111","00001","00010","00100","01000","01000","01000"],
 "8":["01110","10001","10001","01110","10001","10001","01110"],
 "9":["01110","10001","10001","01111","00001","00001","01110"],
 ",":["00000","00000","00000","00000","00000","00100","01000"],
 ".":["00000","00000","00000","00000","00000","00000","00100"],
 "—":["00000","00000","00000","11111","00000","00000","00000"],
 "/":["00001","00010","00100","01000","10000","00000","00000"],
 "K":["10001","10010","10100","11000","10100","10010","10001"],
 "M":["10001","11011","10101","10101","10001","10001","10001"],
 "B":["11110","10001","10001","11110","10001","10001","11110"]
};
const compact=n=>{
 const value=Number(n),abs=Math.abs(value);
 if(!Number.isFinite(value))return String(n);
 if(abs>=1e9)return (value/1e9).toFixed(abs>=1e10?0:1).replace(/\.0$/,"")+"B";
 if(abs>=1e6)return (value/1e6).toFixed(abs>=1e7?0:1).replace(/\.0$/,"")+"M";
 if(abs>=1e5)return Math.round(value/1e3)+"K";
 return fmt(value);
};
const clock=value=>{const date=value instanceof Date?value:new Date(value);return Number.isNaN(date.getTime())?"--:--":date.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"})};
function svgNode(tag,attrs={},parent){
 const node=document.createElementNS(NS,tag);for(const [name,item]of Object.entries(attrs))node.setAttribute(name,item);
 if(parent)parent.append(node);return node;
}
function text(parent,x,y,value,attrs={}){
 const node=svgNode("text",{x,y,fill:"#93a19e","font-size":10,"font-family":"Inter,Segoe UI,Arial,sans-serif",...attrs},parent);
 node.textContent=value;return node;
}
const dotCache=new Map(),dotFrames=new Map();
function paintDot(target,str){
 target.replaceChildren();
 if(str==="—"){const dash=document.createElement("span");dash.className="dash-value";dash.textContent="—";target.append(dash);return}
 const svg=svgNode("svg",{viewBox:"0 0 "+(str.length*6*3.5)+" 26",preserveAspectRatio:"xMinYMid meet","aria-hidden":"true"},target);
 [...str].forEach((character,i)=>(digits[character]||digits["—"]).forEach((row,y)=>[...row].forEach((pixel,x)=>{
  if(pixel==="1")svgNode("circle",{cx:(i*6+x)*3.5+1.2,cy:y*3.5+1.2,r:1.4,fill:"currentColor"},svg);
 })));
}
function dotNumber(id,value,accessible=String(value)){
 const target=el(id);if(!target)return;
 const str=String(value),previous=dotCache.get(id);dotCache.set(id,str);
 target.setAttribute("aria-label",accessible);target.title=accessible;
 const from=previous==="—"?0:Number(String(previous).replaceAll(",","")),to=str==="—"?NaN:Number(str.replaceAll(",",""));
 const animate=previous!==undefined&&previous!==str&&Number.isFinite(from)&&Number.isFinite(to)&&!matchMedia("(prefers-reduced-motion: reduce)").matches;
 if(!animate){paintDot(target,str);return}
 cancelAnimationFrame(dotFrames.get(id));
 const decimals=(str.split(".")[1]||"").length,start=performance.now(),duration=620;
 let lastPaint=0;
 const step=now=>{
  const progress=Math.min(1,(now-start)/duration),eased=1-Math.pow(1-progress,3),current=from+(to-from)*eased;
  if(progress===1||now-lastPaint>55){
   paintDot(target,decimals?current.toFixed(decimals):fmt(Math.round(current)));
   lastPaint=now;
  }
  if(progress<1)dotFrames.set(id,requestAnimationFrame(step));else{paintDot(target,str);dotFrames.delete(id)}
 };
 dotFrames.set(id,requestAnimationFrame(step));
}
function icon(name){const svg=svgNode("svg",{"aria-hidden":"true"});svgNode("use",{href:"#"+name},svg);return svg}
function setState(message,state="ready"){
 el("status").textContent=message;el("status").classList.toggle("error",state==="error");
 el("state-badge").replaceChildren(document.createElement("i"),document.createTextNode({ready:"Ready",working:"Working",verified:"Verified",cancelled:"Cancelled",error:"Needs attention"}[state]));
 el("state-badge").classList.toggle("error",state==="error");
 document.body.classList.toggle("busy",state==="working");
}
function logActivity(message){activity.unshift({message,time:new Date().toLocaleTimeString()});activity=activity.slice(0,20)}
function setBadge(id,label,classes){
 const node=el(id);node.textContent=label;node.className="tag "+classes;
}
function changeView(view,options={}){
 const {push=true,scroll=true}=options;
 if(!["overview","queue","evidence"].includes(view))view="overview";
 const previous=el("workspace").dataset.view;
 el("workspace").dataset.view=view;el("evidence-panel").hidden=view!=="evidence";
 document.querySelectorAll("[data-view].nav-tab").forEach(button=>{button.classList.toggle("active",button.dataset.view===view);button.setAttribute("aria-pressed",String(button.dataset.view===view))});
 const copy={overview:["Transaction intelligence","Ranking suspicious transactions with custom sorts and Top-K selection"],
  queue:["Queue workspace","Build and inspect one independently verified Top-K queue"],
  evidence:["Benchmark evidence","Saved five-run medians across input sizes and conditions"]}[view];
 el("workspace-title").textContent=copy[0];el("workspace-subtitle").textContent=copy[1];
 if(previous!==view&&location.hash!=="#"+view){
  if(push)history.pushState({view},"","#"+view);else history.replaceState({view},"","#"+view);
 }
 if(previous!==view&&scroll){
  scrollTo({top:0,behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth"});
  el("workspace-title").focus({preventScroll:true});
 }
}
addEventListener("popstate",()=>changeView(location.hash.slice(1),{push:false}));
function running(on){
 document.querySelectorAll("#settings select,#settings input").forEach(node=>node.disabled=on);
 el("run").disabled=on;el("cancel").disabled=!on;el("queue-panel").setAttribute("aria-busy",String(on));
}
function configurationChanged(){
 dotNumber("capacity",el("k").value||"—");
 el("input-context").textContent=fmt(el("n").value)+" records · "+el("condition").value;
 if(latest&&!runId){
  setState("Settings changed. Build a new queue to measure this selection.");
  el("verification").textContent="Needs rebuild";el("verification").className="tag gold-tag";
  el("verification-kpi").textContent="Needs rebuild";el("verification-kpi").className="tag gold-tag";
  el("run-context").textContent="Settings changed · build to refresh this ordered queue";
 }
}
function resetResult(){
 queue=[];page=0;latest=null;el("queue-search").value="";el("band-filter").value="";
 dotNumber("elapsed","—");dotNumber("comparisons","—");dotNumber("queue-kpi","0");
 el("moves").textContent="—";el("size").textContent="0";
 el("export-queue").disabled=true;
 el("verification").textContent="Not built";el("verification").className="tag";
 el("verification-kpi").textContent="Not built";el("verification-kpi").className="tag";
 el("run-context").textContent="Preparing a fresh input for the selected algorithm";
 barMode="fraud";updateBarControls();renderQueue();drawFlow();drawBars();
}
function filteredQueue(){
 const search=el("queue-search").value.trim().replaceAll(",",""),band=el("band-filter").value;
 return queue.filter(row=>(!search||String(row.txn_id).includes(search))&&(!band||row.band===Number(band)));
}
function renderQueue(){
 const filtered=filteredQueue(),total=Math.ceil(filtered.length/pageSize);
 page=Math.max(0,Math.min(page,total-1));const start=page*pageSize;el("rows").replaceChildren();
 if(!filtered.length){
  const row=el("rows").insertRow(),cell=row.insertCell();cell.colSpan=7;
  const empty=document.createElement("div");empty.className="empty";empty.append(icon(queue.length?"search":"layers"));
  const title=document.createElement("strong");title.textContent=queue.length?"No matching transactions":"Your next queue starts here";
  const note=document.createElement("span");note.textContent=queue.length?"Try another transaction ID or risk band.":"Choose an algorithm and K, then build the queue.";
  empty.append(title,note);cell.append(empty);
 }
 for(const row of filtered.slice(start,start+pageSize)){
  const tr=el("rows").insertRow();
  [fmt(row.rank),fmt(row.txn_id),"",row.amount.toFixed(2),fmt(row.time),row.risk.toFixed(4)].forEach(value=>tr.insertCell().textContent=value);
  const band=document.createElement("span");band.className="band"+(row.band<6?" low":"");band.textContent=row.band;tr.cells[2].append(band);
  const action=document.createElement("button");action.className="icon-button";action.type="button";action.title="Inspect transaction";
  action.setAttribute("aria-label","Inspect transaction "+row.txn_id);action.append(icon("search"));action.onclick=()=>showTransaction(row);
  tr.insertCell().append(action);
  const highlight=on=>document.querySelectorAll("#flow-chart [data-rank]").forEach(path=>{
   if(!on){path.style.opacity="";return}
   path.style.opacity=Number(path.dataset.rank)===row.rank?"1":".12";
  });
  tr.onmouseenter=()=>highlight(true);tr.onmouseleave=()=>highlight(false);
 }
 el("range").textContent=filtered.length?fmt(start+1)+"–"+fmt(Math.min(start+pageSize,filtered.length))+" of "+fmt(filtered.length)+(filtered.length!==queue.length?" matches":" cases"):queue.length?"0 matches":"No queue built";
 el("page").textContent=(total?page+1:0)+" / "+total;
 el("previous").disabled=page===0;el("next").disabled=page+1>=total;
}
function drawLandscape(){
 const root=el("landscape-chart");root.replaceChildren();if(!evidence)return;
 const raw=Array.from({length:10},(_,i)=>Math.log10(1+evidence.profile.band_counts[String(i)]));
 const populated=raw.slice(2),low=Math.min(...populated),high=Math.max(...populated);
 const values=raw.map((value,index)=>index<2?.02:.07+.93*(value-low)/(high-low||1));
 const height=x=>{const p=x*9,j=Math.min(8,Math.floor(p));return values[j]*(1-(p-j))+values[j+1]*(p-j)};
 const point=(x,z)=>[30+x*650+z*78,228-z*98-height(x)*130*Math.exp(-Math.pow((z-.5)*2.3,2))];
 const defs=svgNode("defs",{},root);
 const ridge=svgNode("linearGradient",{id:"ridgeFill",x1:"0",y1:"0",x2:"0",y2:"1"},defs);
 svgNode("stop",{offset:"0","stop-color":"#a89bff","stop-opacity":".28"},ridge);
 svgNode("stop",{offset:"1","stop-color":"#a89bff","stop-opacity":"0"},ridge);
 const glow=svgNode("filter",{id:"ridgeGlow",x:"-20%",y:"-20%",width:"140%",height:"140%"},defs);
 svgNode("feGaussianBlur",{stdDeviation:"2.4"},glow);
 const front=Array.from({length:91},(_,i)=>point(i/90,.5));
 const ridgePath="M"+front.map(p=>p.join(" ")).join(" L");
 svgNode("path",{d:ridgePath+" L758 228 L30 228 Z",fill:"url(#ridgeFill)",stroke:"none"},root);
 svgNode("path",{d:ridgePath,fill:"none",stroke:"#a89bff","stroke-width":3,opacity:.14,filter:"url(#ridgeGlow)"},root);
 svgNode("path",{d:ridgePath,fill:"none",stroke:"#cfc4ff","stroke-width":.9,opacity:.8},root);
 for(let j=0;j<=20;j++){
  const z=j/20,points=Array.from({length:101},(_,i)=>point(i/100,z));
  svgNode("polyline",{points:points.map(p=>p.join(",")).join(" "),fill:"none",stroke:"#a08cff","stroke-width":.75,opacity:.24+.5*(1-z)},root);
 }
 for(let i=0;i<=46;i++){
  const points=Array.from({length:21},(_,j)=>point(i/46,j/20));
  svgNode("polyline",{points:points.map(p=>p.join(",")).join(" "),fill:"none",stroke:"#a08cff","stroke-width":.62,opacity:.46},root);
 }
 for(let band=2;band<=9;band++){
  const [x,y]=point(band/9,.5);
  svgNode("circle",{cx:x,cy:y,r:2.4,fill:"#c4b9ff",opacity:.95},root);
  text(root,x,246,String(band),{"font-size":8.5,"text-anchor":"middle",fill:"#78868a"});
 }
 text(root,758,18,"risk band →",{"font-size":8.5,"text-anchor":"end",fill:"#78868a"});
 root.setAttribute("aria-label","Wireframe risk landscape. Bands 2 to 9 are populated; band 9 holds 862 records.");
}
function compactChart(){const w=el("flow-chart").clientWidth;return w>0&&w<430}
function drawProfile(root){
 if(!evidence){text(root,310,140,"Saved profile unavailable",{"text-anchor":"middle"});return}
 const profile=evidence.profile,max=Math.max(...Object.values(profile.band_counts));
 const compact=compactChart();
 root.setAttribute("viewBox",compact?"0 0 380 280":"0 0 620 280");
 const x0=compact?30:58,track=compact?250:350;
 const defs=svgNode("defs",{},root);
 const gradient=svgNode("linearGradient",{id:"profileBar",x1:"0",y1:"0",x2:"1",y2:"0"},defs);
 svgNode("stop",{offset:"0","stop-color":"#7a5dc4"},gradient);
 svgNode("stop",{offset:"1","stop-color":"#b8a8ff"},gradient);
 [0,.25,.5,.75,1].forEach(part=>svgNode("line",{x1:x0+track*part,y1:32,x2:x0+track*part,y2:232,stroke:"#222c31","stroke-width":.6,"stroke-dasharray":"2 5"},root));
 for(let band=9;band>=2;band--){
  const y=44+(9-band)*25,count=profile.band_counts[String(band)],width=Math.log10(1+count)/Math.log10(1+max)*track;
  text(root,compact?12:26,y+4,String(band),{"font-size":compact?10:10,fill:"#c9d4d1"});
  svgNode("rect",{x:x0,y:y-5,width:track,height:10,fill:"#131a1c",rx:2},root);
  svgNode("rect",{x:x0,y:y-5,width:Math.max(2,width),height:10,fill:"url(#profileBar)",rx:2,opacity:.9},root);
  text(root,Math.min(compact?346:548,x0+width+9),y+4,fmt(count),{"font-size":compact?10:9.5,fill:"#b7c3c0"});
 }
 text(root,compact?20:24,16,"Band",{"font-size":9});
 text(root,compact?20:24,252,compact?"Transaction count · log length":"Transaction count · logarithmic length",{"font-size":9});
}
function updateFlowControls(){
 const ready=queue.length>0;
 el("flow-mode").disabled=!ready;
 el("flow-mode").classList.toggle("selected",ready&&chartMode==="flow");
 el("profile-mode").classList.toggle("selected",!ready||chartMode==="profile");
 el("flow-mode").setAttribute("aria-pressed",String(ready&&chartMode==="flow"));
 el("profile-mode").setAttribute("aria-pressed",String(!ready||chartMode==="profile"));
 el("flow-mode").title=ready?"Trace the queued records":"Build a queue to trace individual records";
}
function drawFlow(){
 const root=el("flow-chart");root.replaceChildren();updateFlowControls();
 if(!queue.length||chartMode==="profile"){
  drawProfile(root);setBadge("flow-badge",queue.length?"Profile":"Profile","teal-tag");
  el("flow-legend-high").textContent="Band counts";el("flow-legend-low").hidden=true;
  el("flow-description").textContent="Observed band volumes across the full file";
  el("flow-note").textContent=queue.length?"Full-file profile · saved counts":"Build a queue to trace individual records";
  el("callout-label").textContent="Fraud-labelled records";
  el("fraud-total").textContent=evidence?fmt(evidence.profile.fraud_count):"—";
  el("callout-note").textContent="Class is used for evaluation only";
  root.setAttribute("aria-label","Observed full-file risk-band transaction counts");return;
 }
 setBadge("flow-badge","Verified","teal-tag");
 el("flow-legend-high").textContent="Bands 6–9";el("flow-legend-low").hidden=false;
 el("flow-description").textContent="Band → Amount → Queue rank";
 el("flow-note").textContent="First "+Math.min(queue.length,50)+" of "+fmt(queue.length)+" queued records";
 el("callout-label").textContent="Queued records";
 el("fraud-total").textContent=fmt(queue.length);
 el("callout-note").textContent="Reference verified · Class never used";
 root.setAttribute("aria-label","Actual ranking flow for the first fifty queued transactions");
 const defs=svgNode("defs",{},root);
 const high=svgNode("linearGradient",{id:"flowHigh",x1:"0",y1:"0",x2:"1",y2:"0"},defs);
 svgNode("stop",{offset:"0","stop-color":"#5b4a9e","stop-opacity":".15"},high);
 svgNode("stop",{offset:"1","stop-color":"#b3a4ff","stop-opacity":".95"},high);
 const low=svgNode("linearGradient",{id:"flowLow",x1:"0",y1:"0",x2:"1",y2:"0"},defs);
 svgNode("stop",{offset:"0","stop-color":"#2e6f68","stop-opacity":".12"},low);
 svgNode("stop",{offset:"1","stop-color":"#8fe0d3","stop-opacity":".9"},low);
 const compact=compactChart();
 root.setAttribute("viewBox",compact?"0 0 380 280":"0 0 620 280");
 const columns=compact?[[46,"Risk band"],[182,"Amount · log"],[316,"Queue rank"]]:[[70,"Risk band"],[300,"Amount · log"],[520,"Queue rank"]];
 const [cx1,cx2,cx3]=columns.map(column=>column[0]);
 columns.forEach(([x,label])=>{svgNode("line",{x1:x,y1:38,x2:x,y2:242,stroke:"#2a3539","stroke-width":.7,"stroke-dasharray":"3 5",opacity:.75},root);text(root,x,24,label,{"text-anchor":"middle","font-size":compact?8:9,fill:"#84928f"})});
 const sample=queue.slice(0,50),min=Math.min(...sample.map(row=>Math.log1p(row.amount))),max=Math.max(...sample.map(row=>Math.log1p(row.amount)));
 const spanA=cx2-cx1,spanB=cx3-cx2;
 sample.forEach((row,i)=>{
  const y1=232-row.band/9*186,y2=232-(Math.log1p(row.amount)-min)/(max-min||1)*186,y3=42+i/Math.max(1,sample.length-1)*190;
  const color=row.band>=6?"url(#flowHigh)":"url(#flowLow)";
  const path=svgNode("path",{d:"M"+cx1+" "+y1+" C"+(cx1+spanA*.39)+" "+y1+" "+(cx2-spanA*.39)+" "+y2+" "+cx2+" "+y2+" S"+(cx3-spanB*.44)+" "+y3+" "+cx3+" "+y3,fill:"none",stroke:color,"stroke-width":1,opacity:.72,"data-rank":row.rank,pathLength:1},root);
  const title=svgNode("title",{},path);title.textContent="Rank "+row.rank+" · Transaction "+row.txn_id+" · Band "+row.band+" · Amount "+row.amount.toFixed(2);
  svgNode("circle",{cx:cx3,cy:y3,r:1.7,fill:row.band>=6?"#b3a4ff":"#8fe0d3"},root);
  svgNode("rect",{x:cx3+6,y:y3-1.8,width:compact?4+row.band*2.4:6+row.band*4.6,height:3.4,rx:1,fill:row.band>=6?"#8d7ae0":"#4d9d92",opacity:.7},root);
 });
 text(root,cx1-12,250,"0",{"font-size":8.5});text(root,cx1-12,40,"9",{"font-size":8.5});
 text(root,cx3+20,250,"50",{"font-size":8.5});text(root,cx3+20,40,"1",{"font-size":8.5});
}
function drawDonut(){
 const root=el("capture-gauge");root.replaceChildren();
 const fraction=evidence?Math.min(1,evidence.capture.half_threshold/evidence.capture.total_frauds):0;
 const defs=svgNode("defs",{},root);
 const gradient=svgNode("linearGradient",{id:"donutGradient",x1:"0",y1:"0",x2:"1",y2:"1"},defs);
 svgNode("stop",{offset:"0","stop-color":"#6cc6bb"},gradient);
 svgNode("stop",{offset:".62","stop-color":"#9fe4d8"},gradient);
 svgNode("stop",{offset:"1","stop-color":"#b9abff"},gradient);
 for(let tick=0;tick<48;tick++){
  const angle=tick/48*Math.PI*2,inner=tick%6===0?65:68;
  svgNode("line",{x1:85+Math.cos(angle)*inner,y1:85+Math.sin(angle)*inner,x2:85+Math.cos(angle)*73,y2:85+Math.sin(angle)*73,stroke:tick%6===0?"#45575a":"#29383a","stroke-width":.8},root);
 }
 svgNode("circle",{cx:85,cy:85,r:53,fill:"none",stroke:"#1b2527","stroke-width":13},root);
 const circumference=2*Math.PI*53;
 svgNode("circle",{cx:85,cy:85,r:53,fill:"none",stroke:"url(#donutGradient)","stroke-width":13,"stroke-dasharray":(circumference*fraction).toFixed(2)+" "+circumference.toFixed(2),"stroke-linecap":"butt",transform:"rotate(-90 85 85)"},root);
 svgNode("circle",{cx:85,cy:85,r:44.5,fill:"none",stroke:"#263335","stroke-width":.8,opacity:.8},root);
 text(root,85,84,evidence?Math.round(fraction*100)+"%":"—",{"text-anchor":"middle","font-size":26,fill:"#eef4f2","font-family":"Cascadia Mono,Consolas,monospace"});
 text(root,85,101,"captured",{"text-anchor":"middle","font-size":7.5,fill:"#9daca8"});
 root.setAttribute("aria-label",evidence?Math.round(fraction*100)+" percent of fraud labels captured by the half-capture queue":"Fraud capture unavailable");
}
function updateBarControls(){
 if(!queue.length&&barMode==="queue")barMode="fraud";
 const queueAvailable=queue.length>0;
 el("bars-queue").disabled=!queueAvailable;
 el("bars-fraud").classList.toggle("selected",barMode==="fraud");
 el("bars-queue").classList.toggle("selected",barMode==="queue");
 el("bars-fraud").setAttribute("aria-pressed",String(barMode==="fraud"));
 el("bars-queue").setAttribute("aria-pressed",String(barMode==="queue"));
}
function drawBars(){
 const root=el("bars-chart");root.replaceChildren();
 if(!evidence&&!queue.length){text(root,280,145,"Saved profile unavailable",{"text-anchor":"middle"});return}
 const bands=[2,3,4,5,6,7,8,9];
 const queueMode=barMode==="queue"&&queue.length>0;
 let values,total,topValue,topBand;
 if(queueMode){
  values=bands.map(band=>queue.filter(row=>row.band===band).length);
  total=queue.length;
  topValue=Math.max(...values,0);topBand=bands[values.indexOf(topValue)]??"—";
  const high=queue.filter(row=>row.band>=8).length;
  el("bar-half-label").textContent="Bands 8–9";
  el("bar-half").textContent=total?Math.round(high/total*100)+"%":"—";
  el("bar-total-label").textContent="Queue records";
  el("bars-title").textContent="Queue concentration by risk band";
  el("bars-description").textContent="Current verified queue · K = "+fmt(queue.length);
  root.setAttribute("aria-label","Queue records by risk band");
 }else{
  values=bands.map(band=>evidence?evidence.profile.fraud_by_band[String(band)]:0);
  total=evidence?evidence.profile.fraud_count:0;
  topValue=Math.max(...values,0);topBand=bands[values.indexOf(topValue)]??"—";
  el("bar-half-label").textContent="Half-capture K";
  el("bar-half").textContent=evidence?fmt(evidence.capture.k_half):"—";
  el("bar-total-label").textContent="Total labels";
  el("bars-title").textContent="Fraud concentration by risk band";
  el("bars-description").textContent="Where the "+fmt(total)+" fraud labels sit";
  root.setAttribute("aria-label","Fraud labels by risk band");
 }
 el("bar-total").textContent=fmt(total);
 el("bar-top").textContent=topValue?"Band "+topBand+" · "+fmt(topValue):"—";
 const compactView=window.innerWidth<=720;
 const width=compactView?360:560,height=compactView?270:290,left=compactView?31:38,right=compactView?8:10,top=22,baseline=compactView?206:224;
 root.setAttribute("viewBox","0 0 "+width+" "+height);
 const plotW=width-left-right,plotH=baseline-top,slot=plotW/bands.length,barW=Math.max(20,Math.min(38,slot*.56));
 const scaleMax=Math.max(10,Math.ceil(topValue*1.16));
 const y=value=>baseline-value/scaleMax*plotH;
 const defs=svgNode("defs",{},root);
 const barGradient=svgNode("linearGradient",{id:"barGradient",x1:"0",y1:"0",x2:"0",y2:"1"},defs);
 svgNode("stop",{offset:"0","stop-color":queueMode?"#c0b3ff":"#9fe8dc"},barGradient);
 svgNode("stop",{offset:".55","stop-color":queueMode?"#8b77e0":"#64bdb1"},barGradient);
 svgNode("stop",{offset:"1","stop-color":queueMode?"#4b3d8c":"#2f6a63"},barGradient);
 for(let grid=0;grid<=3;grid++){
  const value=scaleMax/3*grid,lineY=y(value);
  svgNode("line",{x1:left,y1:lineY,x2:width-right,y2:lineY,stroke:grid===0?"#334043":"#1c2628","stroke-width":.7,"stroke-dasharray":grid===0?"none":"2 5"},root);
  text(root,left-9,lineY+3,compact(Math.round(value)),{"font-size":8.5,"text-anchor":"end",fill:"#748286"});
 }
 bands.forEach((band,index)=>{
  const value=values[index],barX=left+index*slot+(slot-barW)/2,barY=y(value),barH=Math.max(0,baseline-barY);
  const isTop=value===topValue&&value>0;
  if(value){
   svgNode("rect",{x:barX,y:barY,width:barW,height:barH,fill:"url(#barGradient)",rx:2,opacity:isTop?1:.84},root);
   svgNode("rect",{x:barX,y:barY,width:barW,height:2.5,fill:isTop?(queueMode?"#d7cdff":"#c6f7ef"):(queueMode?"#9d8be9":"#7fd8ca"),rx:1,opacity:.95},root);
  }
  if(value)text(root,barX+barW/2,barY-7,fmt(value),{"text-anchor":"middle","font-size":compactView?9.5:9,fill:isTop?"#eef4f2":"#a9b7b3"});
  text(root,barX+barW/2,baseline+18,String(band),{"text-anchor":"middle","font-size":compactView?10:9.5,fill:isTop?"#eef4f2":"#93a19e"});
  const title=svgNode("title",{},svgNode("rect",{x:barX,y:top,width:barW,height:baseline-top,fill:"transparent"},root));
  title.textContent="Risk band "+band+" · "+fmt(value)+" "+(queueMode?"queued records":"fraud labels");
 });
 text(root,left,baseline+38,queueMode?"Queued records by band":"Fraud labels by band",{"font-size":8.5,fill:"#78868a"});
 text(root,width-right,baseline+38,"Risk band",{"text-anchor":"end","font-size":8.5,fill:"#78868a"});
}
function renderWatch(){
 const list=el("watch-list");list.replaceChildren();
 if(!evidence||!evidence.tournament.length){const note=document.createElement("p");note.className="panel-loading";note.textContent="Saved benchmark evidence is unavailable.";list.append(note);return}
 const preferred=evidence.tournament.filter(row=>row.n===10000&&row.condition==="C2"&&row.seconds!==null);
 let group=preferred;
 if(!group.length){const first=evidence.tournament.find(row=>row.seconds!==null);if(first)group=evidence.tournament.filter(row=>row.n===first.n&&row.condition===first.condition&&row.seconds!==null)}
 group=[...group].sort((a,b)=>a.seconds-b.seconds);
 const top=group.slice(0,3),fastest=top[0]?.seconds||1;
 el("watch-subtitle").textContent="Fastest saved medians · n = "+(top[0]?fmt(top[0].n):"—")+" · "+(top[0]?top[0].condition:"—");
 top.forEach((row,index)=>{
  const card=document.createElement("button");card.type="button";card.className="watch-card";
  card.setAttribute("aria-label","Open evidence for "+row.algorithm+", "+timeLabel(row.seconds));
  const iconWrap=document.createElement("span");iconWrap.className="watch-icon";iconWrap.append(icon(index===0?"activity":"clock"));
  const name=document.createElement("span");name.className="watch-name";name.textContent=row.algorithm;
  const time=document.createElement("span");time.className="watch-time";time.textContent=timeLabel(row.seconds);
  const bar=document.createElement("span");bar.className="watch-bar";
  const fill=document.createElement("i");fill.style.width=Math.max(14,Math.round(fastest/row.seconds*100))+"%";bar.append(fill);
  card.append(iconWrap,name,time,bar);
  card.onclick=()=>{changeView("evidence");el("evidence-n").value=String(row.n);el("evidence-condition").value=row.condition;renderEvidence()};
  list.append(card);
 });
}
function timeLabel(seconds){
 if(seconds===null||seconds===undefined)return "DNF";
 if(seconds<0.0001)return seconds.toExponential(2)+" s";
 if(seconds<0.01)return seconds.toFixed(5)+" s";
 if(seconds<1)return seconds.toFixed(4)+" s";
 return seconds.toFixed(3)+" s";
}
function renderTimeline(){
 const list=el("timeline-list");list.replaceChildren();
 const entries=[...sessionRuns,...savedRuns].slice(0,10);
 if(!entries.length){const empty=document.createElement("li");empty.className="timeline-empty";empty.textContent="No recorded demonstrations yet. Build a queue to start the timeline.";list.append(empty);return}
 entries.forEach((run,index)=>{
  const item=document.createElement("li");item.className="timeline-item "+(index===0?"":"teal");
  const main=document.createElement("div");main.className="timeline-main";
  const row=document.createElement("div");row.className="timeline-row";
  const name=document.createElement("strong");name.textContent=run.algorithm||"Queue build";
  const tag=document.createElement("span");tag.className="tag teal-tag";tag.textContent="Verified";
  row.append(name,tag);
  const context=document.createElement("p");context.textContent=(run.condition||"C1")+" · n = "+fmt(run.n||0)+" · K = "+fmt(run.k||0);
  const detail=document.createElement("small");detail.textContent=timeLabel(run.seconds)+" · "+fmt(run.comparisons||0)+" comparisons";
  main.append(row,context,detail);
  const time=document.createElement("time");time.textContent=clock(run.at||run.timestamp);
  item.append(main,time);list.append(item);
 });
 el("timeline-note").textContent=entries.length+" most recent verified demonstrations. Session runs appear immediately; saved runs come from console.csv.";
}
function renderEvidence(){
 const root=el("benchmark-chart");root.replaceChildren();el("benchmark-rows").replaceChildren();
 if(!evidence)return;
 const rows=evidence.tournament.filter(row=>row.n===Number(el("evidence-n").value)&&row.condition===el("evidence-condition").value);
 const finite=rows.filter(row=>row.seconds!==null),maxLog=finite.length?Math.max(...finite.map(row=>Math.log10(row.seconds))):0,minLog=finite.length?Math.min(...finite.map(row=>Math.log10(row.seconds)))-.15:-3;
 const compactView=window.innerWidth<=720;
 const chartHeight=Math.max(220,74+rows.length*36),barX=compactView?118:205,barMax=compactView?188:500,viewW=compactView?380:900;
 root.setAttribute("viewBox","0 0 "+viewW+" "+chartHeight);
 const defs=svgNode("defs",{},root);
 const gradient=svgNode("linearGradient",{id:"benchGradient",x1:"0",y1:"0",x2:"1",y2:"0"},defs);
 svgNode("stop",{offset:"0","stop-color":"#3c7f78"},gradient);
 svgNode("stop",{offset:"1","stop-color":"#7fd8ca"},gradient);
 const firstDecade=Math.floor(minLog),lastDecade=Math.ceil(maxLog);
 for(let decade=firstDecade;decade<=lastDecade;decade++){
  const x=barX+(decade-minLog)/(maxLog-minLog||1)*barMax;
  svgNode("line",{x1:x,y1:18,x2:x,y2:chartHeight-34,stroke:"#222d2f","stroke-width":.6,"stroke-dasharray":"2 5"},root);
  const seconds=Math.pow(10,decade),label=seconds>=1?seconds+" s":seconds.toFixed(1)+" s";
  text(root,x,chartHeight-20,label,{"text-anchor":"middle","font-size":8.5,fill:"#78868a"});
 }
 const sorted=[...finite].sort((a,b)=>a.seconds-b.seconds).concat(rows.filter(row=>row.seconds===null));
 sorted.forEach((row,index)=>{
  const y=32+index*36,tr=el("benchmark-rows").insertRow();
  [row.algorithm,row.seconds===null?"DNF (>300 s)":row.seconds.toFixed(6)+" s",row.comparisons===null?"—":fmt(row.comparisons),row.moves===null?"—":fmt(row.moves)].forEach(value=>tr.insertCell().textContent=value);
  text(root,0,y+4,row.algorithm,{"font-size":compactView?9.5:10.5,fill:"#d2dcd9"});
  if(row.seconds!==null){
   const width=Math.max(3,(Math.log10(row.seconds)-minLog)/(maxLog-minLog||1)*barMax);
   svgNode("rect",{x:barX,y:y-10,width:barMax,height:14,fill:"#12191a",rx:2},root);
   svgNode("rect",{x:barX,y:y-10,width:width,height:14,fill:"url(#benchGradient)",rx:2,opacity:.9},root);
   text(root,Math.min(viewW-10,barX+width+9),y+2,row.seconds.toFixed(4)+" s",{"font-size":compactView?9:9.5,fill:"#b9c6c2"});
  }else{
   svgNode("rect",{x:barX,y:y-10,width:compactView?60:150,height:14,fill:"#3a2d1c",rx:2,opacity:.5},root);
   text(root,compactView?barX+10:barX+160,y+3,compactView?"DNF":"DNF · no invented time",{fill:"#d9c38d","font-size":compactView?8.5:9.5});
  }
 });
 text(root,barX,chartHeight-6,"Algorithm time (s) · logarithmic bar length",{"font-size":compactView?8:8.5,fill:"#6f7d7a"});
 const fastest=sorted.find(row=>row.seconds!==null);
 el("evidence-fastest").textContent=fastest?fastest.algorithm+" · "+timeLabel(fastest.seconds):"—";
 el("evidence-cells").textContent=fmt(rows.length);
 el("evidence-dnf").textContent=fmt(rows.filter(row=>row.seconds===null).length);
 el("evidence-note").textContent="Saved tournament measurements for "+el("evidence-condition").value+", n="+fmt(el("evidence-n").value)+". "+evidence.provenance+" DNF observations have no measured median. Concurrent tournament timings include host scheduling and cache contention."+(el("evidence-condition").value==="C6"?" C6 compares bands alone; the specification's tie-order conflict is disclosed in the report.":"");
}
function applyEvidence(){
 const populated=Object.values(evidence.profile.band_counts).filter(Boolean).length;
 dotNumber("posture-bands",populated+"/8",populated+" of 8 risk bands populated");
 el("posture-fraud").textContent=fmt(evidence.profile.fraud_count);
 el("fraud-total").textContent=fmt(evidence.profile.fraud_count);
 el("fraud-kpi").textContent=fmt(evidence.profile.fraud_count);
 el("half-capacity").textContent=fmt(evidence.capture.k_half);
 el("capture-insight").textContent=fmt(evidence.capture.half_threshold)+" of "+fmt(evidence.capture.total_frauds)+" fraud labels. Capacity and ranking quality both matter.";
 const recommendation=evidence.recommendations;
 el("batch-choice").textContent="Overnight batch: "+recommendation.batch;
 el("batch-insight").textContent="Lowest full-size worst median across C1–C5: "+recommendation.batch_seconds.toFixed(2)+" s. Already ranked input can reverse this choice.";
 el("heap-insight").textContent="Size-K Heap wins "+(recommendation.wins["Size-K Heap"]||0)+" of "+recommendation.comparison_cells+" measured cells; its worst slowdown is "+recommendation.regrets["Size-K Heap"].toFixed(2)+"×. Scores are assumed immutable.";
 const heap60=evidence.live.find(row=>row.width===3600&&row.strategy==="heap");
 const heap10=evidence.live.find(row=>row.width===600&&row.strategy==="heap");
 const liveLabel=row=>row?.seconds==null?"DNF":row.seconds.toFixed(3)+" s";
 el("live-insight").textContent="Saved full-file medians: "+liveLabel(heap60)+" for 60-minute windows; "+liveLabel(heap10)+" for 10-minute windows. Ordered publication is included.";
 barMode="fraud";updateBarControls();
 drawLandscape();drawFlow();drawDonut();drawBars();renderWatch();renderEvidence();
}
function showDialog(title,content){
 el("dialog-title").textContent=title;el("dialog-content").replaceChildren(content);
 if(!el("detail-dialog").open)el("detail-dialog").showModal();
}
function showTransaction(row){
 const list=document.createElement("dl");list.className="detail-list";
 for(const [label,value]of [["Queue rank",fmt(row.rank)],["Risk band",row.band],["Amount",row.amount.toFixed(2)],["Time from first record",fmt(row.time)+" s"],["Risk score",row.risk.toFixed(6)]]){
  const dt=document.createElement("dt"),dd=document.createElement("dd");dt.textContent=label;dd.textContent=value;list.append(dt,dd);
 }
 const box=document.createElement("div"),note=document.createElement("p");note.textContent="Within each risk band, Amount breaks the next tie. Time and transaction ID complete the order. Class is never part of the ranking.";
 box.append(list,note);showDialog("Transaction "+fmt(row.txn_id),box);
}
function showAbout(){
 const box=document.createElement("div");
 for(const value of ["The Midnight Queue · 23I-2581 · DS-B · Seed 232581.","Risk is the sum of squared population z-scores of V1–V28, computed over the full official file before sampling. The risk band is clipped floor(log₂ risk).","All seven choices use the project's custom algorithms. One comparison is one comparator call; one slot assignment is a move, and an actual swap counts as three.","Interactive results are single verified runs. Initial loading, scoring, construction and verification are outside the timer; producing the ordered output is included. A measured run above 300 seconds is DNF.","This console reuses saved project evidence only. It does not invent locations, channels, or model predictions."]){
  const p=document.createElement("p");p.textContent=value;box.append(p);
 }
 showDialog("About the ranking engine",box);
}
el("settings").onsubmit=async event=>{
 event.preventDefault();if(runId!==null)return;resetResult();runId=crypto.randomUUID();
 running(true);const params={algorithm:el("algorithm").value,n:Number(el("n").value),condition:el("condition").value,k:Number(el("k").value),request_id:runId};
 setState("Building the queue… Preparing the official data and a fresh "+fmt(params.n)+"-record input.","working");
 setBadge("flow-badge","Live","red-tag");
 dispatchEvent(new CustomEvent("mq:sound",{detail:"start"}));
 logActivity("Started "+params.algorithm+" · "+params.condition+" · K="+fmt(params.k));
 try{
  const response=await fetch("/api/run",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(params)});
  const data=await response.json();if(!response.ok)throw Error(data.error);
  latest=data;queue=data.queue.map((row,index)=>({...row,rank:index+1}));page=0;renderQueue();drawFlow();
  dotNumber("elapsed",data.elapsed_s<1?data.elapsed_s.toFixed(4):data.elapsed_s.toFixed(3),data.elapsed_s.toFixed(6)+" seconds");
  dotNumber("comparisons",compact(data.comparisons),fmt(data.comparisons));
  dotNumber("queue-kpi",fmt(data.queue_size),fmt(data.queue_size)+" verified queue records");
  el("moves").textContent=fmt(data.moves);el("size").textContent=fmt(data.queue_size);el("export-queue").disabled=false;
  el("verification").textContent="Reference verified";el("verification").className="tag teal-tag";
  el("verification-kpi").textContent="Verified";el("verification-kpi").className="tag teal-tag";
  el("run-context").textContent=data.algorithm+" · "+data.condition+" · n="+fmt(data.n)+" · K="+fmt(data.k);
  setState("Verified against the reference. "+fmt(data.queue_size)+" cases from "+fmt(data.n)+" records; "+data.condition+", K="+fmt(data.k)+".","verified");
  el("queue-panel").classList.remove("verified-flash");void el("queue-panel").offsetWidth;el("queue-panel").classList.add("verified-flash");
  dispatchEvent(new CustomEvent("mq:sound",{detail:"success"}));
  barMode="queue";updateBarControls();drawBars();
  sessionRuns.unshift({algorithm:data.algorithm,condition:data.condition,n:data.n,k:data.k,seconds:data.elapsed_s,comparisons:data.comparisons,at:new Date()});
  renderTimeline();
  logActivity("Verified "+data.algorithm+" · "+data.elapsed_s.toFixed(6)+" s · "+fmt(data.comparisons)+" comparisons");
 }catch(error){
  const cancelled=error.message.startsWith("Run cancelled");setState(error.message,cancelled?"cancelled":"error");
  el("run-context").textContent=cancelled?"Run cancelled · no timing result recorded":"No verified queue produced";
  dispatchEvent(new CustomEvent("mq:sound",{detail:cancelled?"cancel":"error"}));
  if(!queue.length)drawFlow();
  logActivity(error.message);
 }finally{runId=null;running(false)}
};
el("cancel").onclick=async()=>{
 if(!runId)return;el("cancel").disabled=true;setState("Cancelling the active worker…","working");
 try{const response=await fetch("/api/cancel",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({request_id:runId})});if(!response.ok)throw Error("Cancellation request failed")}
 catch(error){if(runId)el("cancel").disabled=false;setState(error.message,"error")}
};
el("n").onchange=()=>{el("k").max=el("n").value;el("k").value=Math.min(Number(el("k").value),Number(el("n").value));configurationChanged()};
el("k").oninput=configurationChanged;el("algorithm").onchange=configurationChanged;el("condition").onchange=configurationChanged;
el("previous").onclick=()=>{page--;renderQueue()};el("next").onclick=()=>{page++;renderQueue()};
el("queue-search").oninput=()=>{page=0;renderQueue()};el("band-filter").onchange=()=>{page=0;renderQueue()};
document.querySelectorAll(".nav-tab").forEach(button=>button.onclick=()=>changeView(button.dataset.view));
document.querySelector(".brand").onclick=event=>{event.preventDefault();changeView("overview")};
el("configure").onclick=()=>{changeView("queue",{scroll:false});el("queue-panel").scrollIntoView({block:"start",behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth"});el("algorithm").focus({preventScroll:true})};
el("focus-search").onclick=()=>{changeView("queue",{scroll:false});el("queue-search").focus()};
el("open-evidence").onclick=()=>changeView("evidence");
el("open-evidence-watch").onclick=()=>changeView("evidence");
el("evidence-n").onchange=renderEvidence;el("evidence-condition").onchange=renderEvidence;
el("flow-mode").onclick=()=>{chartMode="flow";el("flow-mode").classList.add("selected");el("profile-mode").classList.remove("selected");el("flow-mode").setAttribute("aria-pressed","true");el("profile-mode").setAttribute("aria-pressed","false");drawFlow()};
el("profile-mode").onclick=()=>{chartMode="profile";el("profile-mode").classList.add("selected");el("flow-mode").classList.remove("selected");el("profile-mode").setAttribute("aria-pressed","true");el("flow-mode").setAttribute("aria-pressed","false");drawFlow()};
el("bars-fraud").onclick=()=>{barMode="fraud";updateBarControls();drawBars()};
el("bars-queue").onclick=()=>{if(!queue.length)return;barMode="queue";updateBarControls();drawBars()};
el("about-button").onclick=showAbout;el("dataset-info").onclick=showAbout;el("close-dialog").onclick=()=>el("detail-dialog").close();
el("detail-dialog").addEventListener("click",event=>{if(event.target===el("detail-dialog"))el("detail-dialog").close()});
el("history-button").onclick=()=>{
 const list=document.createElement("ul");list.className="activity-list";
 for(const event of activity){const li=document.createElement("li"),time=document.createElement("time");time.textContent=event.time;li.append(time,document.createTextNode(event.message));list.append(li)}
 if(!activity.length){const li=document.createElement("li");li.textContent="No runs in this browser session. Build a queue to start.";list.append(li)}
 showDialog("Run activity · this session",list);
};
el("export-queue").onclick=()=>{
 if(!queue.length)return;
 const csv=["Rank,Transaction ID,Risk band,Amount,Time (s),Risk score",...queue.map(row=>[row.rank,row.txn_id,row.band,row.amount,row.time,row.risk].join(","))].join("\r\n");
 const url=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"})),link=document.createElement("a");
 link.href=url;link.download="midnight_queue_K"+queue.length+".csv";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 dispatchEvent(new CustomEvent("mq:sound",{detail:"export"}));
 logActivity("Exported "+fmt(queue.length)+" verified queue records");
};
dotNumber("capacity","52");dotNumber("elapsed","—");dotNumber("comparisons","—");dotNumber("queue-kpi","0");dotNumber("posture-bands","8/8");drawDonut();
let resizeTimer;addEventListener("resize",()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{drawLandscape();drawFlow();drawBars()},180)});
const initialView=location.hash.slice(1);if(["overview","queue","evidence"].includes(initialView))changeView(initialView);
(async()=>{
 try{
  const response=await fetch("/api/config");if(!response.ok)throw Error("Console configuration could not load");
  const config=await response.json();for(const name of config.algorithms){const option=document.createElement("option");option.value=option.textContent=name;el("algorithm").append(option)}
  el("algorithm").value="Size-K Heap";el("run").disabled=false;setState("Ready. Choose an algorithm and K to inspect its ordered queue.");
 }catch(error){setState(error.message,"error")}
 try{
  const response=await fetch("/api/evidence");if(!response.ok)throw Error("Saved benchmark evidence is unavailable.");
  evidence=await response.json();applyEvidence();
 }catch(error){
  el("batch-insight").textContent=error.message;
  el("heap-insight").textContent="Interactive queue measurements remain available.";el("evidence-note").textContent=error.message;
  drawFlow();drawBars();
 }
 try{
  const response=await fetch("/api/runs");if(response.ok){const data=await response.json();savedRuns=data.runs||[]}
 }catch(error){savedRuns=[]}
 renderTimeline();
})();
