(() => {
"use strict";
window.__AURA_MUSIC_UI4_R4__=true;
const BRIDGE="/api/music-premium";
const state={items:[],selected:0,playing:false,paused:false,fullList:false,volume:80,dragId:"",poll:null,lifecycleTimer:null,timeline:{pos:0,dur:0,pct:0,lastAt:0,valid:false},timelineTimer:null,repeatMode:(localStorage.getItem("aura.music.repeatMode")||"off"),shuffle:(localStorage.getItem("aura.music.shuffle")||"0")==="1",autoAdvancing:false,lastEndedId:"",libraryState:{favorites:[],history:[],last_selected_id:"",last_played_id:""},libraryQuery:"",libraryFavoriteOnly:false,libraryHistoryOpen:false,libraryRestored:false,libraryPersistedSelection:""};

function toast(msg){let t=document.getElementById("aura-music-toast-v180");if(!t){t=document.createElement("div");t.id="aura-music-toast-v180";t.className="aura-music-toast";document.body.appendChild(t)}t.textContent=msg;t.classList.add("show");clearTimeout(t.__timer);t.__timer=setTimeout(()=>t.classList.remove("show"),2700)}
function fmt(v){const s=Math.max(0,Math.floor(Number(v)||0));return `${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}`}
function auraMusicToken(){const q=new URLSearchParams(location.search);return q.get("token")||q.get("auth")||""}
async function api(path,method="GET",body=null){const tk=auraMusicToken();if(!tk)throw new Error("token runtime absent");const opt={method,cache:"no-store",headers:{"Content-Type":"application/json"}};if(body!==null)opt.body=JSON.stringify(body);const sep=String(path).includes("?")?"&":"?";const url=BRIDGE+path+sep+"token="+encodeURIComponent(tk);const r=await fetch(url,opt);let d={};try{d=await r.json()}catch(_e){}if(!r.ok||d.ok===false)throw new Error(d.error||`HTTP ${r.status}`);return d}
function runtime(mode,text){const root=document.getElementById("aura-music-player-v180"),label=document.getElementById("aura-music-runtime-text-v180");if(root)root.dataset.runtime=mode||"";if(label)label.textContent=text||""}
async function probe(){try{await api("/health");runtime("ok","VLC BRIDGE • CONNECTÉ");return true}catch(e){runtime("error","VLC BRIDGE • HORS LIGNE");toast("Pont audio AURA indisponible. Relance le correctif R4.");return false}}
function current(){return state.items[state.selected]||null}
async function loadPlaylist(){
 try{
  const [d,l]=await Promise.all([api("/playlist"),api("/library/state").catch(()=>({library:{}}))]);
  state.items=Array.isArray(d.playlist?.items)?d.playlist.items:[];
  const lib=l&&l.library&&typeof l.library==="object"?l.library:{};
  state.libraryState={
   favorites:Array.isArray(lib.favorites)?lib.favorites.map(String):[],
   history:Array.isArray(lib.history)?lib.history:[],
   last_selected_id:String(lib.last_selected_id||""),
   last_played_id:String(lib.last_played_id||"")
  };
  if(!state.libraryRestored){
   const restoreId=state.libraryState.last_selected_id||state.libraryState.last_played_id;
   const idx=restoreId?state.items.findIndex(x=>String(x.id)===restoreId):-1;
   if(idx>=0)state.selected=idx;
   state.libraryRestored=true
  }
  if(state.selected>=state.items.length)state.selected=Math.max(0,state.items.length-1);
  render()
 }catch(e){
  console.error(e);
  runtime("error","VLC BRIDGE • ERREUR")
 }
}
/* AURA_M180_UI5_R2_METADATA_RENDER */
function auraRenderMediaMetadata(cur){
 const cover=document.getElementById("aura-music-cover-v180");
 const badge=document.getElementById("aura-music-cover-badge-v180");
 const title=document.getElementById("aura-music-current-title-v180");
 const artist=document.getElementById("aura-music-current-artist-v180");
 const chips=document.getElementById("aura-music-chips-v180");
 if(title)title.textContent=cur?.title||"Aucun média";
 if(artist){
  if(!cur)artist.textContent="Bibliothèque locale";
  else{
   const a=[cur.artist,cur.album].map(x=>String(x||"").trim()).filter(Boolean);
   artist.textContent=a.length?a.join(" • "):"PC LOCAL"
  }
 }
 const art=String(cur?.cover_data_uri||"");
 if(cover){
  cover.classList.toggle("has-art",!!art);
  cover.classList.toggle("no-art",!art);
  cover.style.backgroundImage=art?`url("${art}")`:""
 }
 if(badge)badge.textContent=art?"POCHETTE":String(cur?.media_type||"MEDIA").toUpperCase();
 if(chips){
  if(!cur){chips.innerHTML="";return}
  const values=[
   String(cur.extension||"").replace(".","").toUpperCase(),
   cur.track?`PISTE ${String(cur.track).split("/")[0]}`:"",
   cur.year?String(cur.year).slice(0,4):"",
   cur.metadata_source?String(cur.metadata_source).toUpperCase():""
  ].filter(Boolean);
  chips.innerHTML=values.map((x,i)=>`<span class="aura-music-chip ${i===values.length-1?"aura-music-meta-source":""}">${x}</span>`).join("")
 }
}

function render(){
 const cur=current();
 auraRenderMediaMetadata(cur);
 const count=document.getElementById("aura-music-count-v180");if(count)count.textContent=`${state.items.length} morceau${state.items.length>1?"x":""}`;
 const list=document.getElementById("aura-music-list-v180");if(!list)return;
 if(!state.items.length){list.innerHTML='<div class="aura-music-empty">Ajoute des morceaux avec <b>TITRE PC</b>, importe une <b>PLAYLISTE</b> ou choisis un <b>DOSSIER</b>.</div>';return}
 const rows=state.fullList?state.items:state.items.slice(0,8);
 list.innerHTML=rows.map((row,i)=>`<div class="aura-music-row ${i===state.selected?"active":""}" draggable="true" data-id="${row.id}" data-index="${i}"><div class="aura-music-drag" title="Glisser pour réorganiser">⋮⋮</div><div class="aura-music-num">${String(i+1).padStart(2,"0")}</div><div class="aura-music-row-main"><div class="aura-music-row-title">${row.title||"Media"}</div><div class="aura-music-row-sub">${row.artist||row.album||"PC LOCAL"}</div></div><div class="aura-music-row-right"><div class="aura-music-row-kind">${String(row.extension||row.media_type||"MEDIA").replace(".","").toUpperCase()}</div></div><div class="aura-music-row-actions"><button data-act="up" title="Monter">↑</button><button data-act="down" title="Descendre">↓</button><button data-act="remove" title="Retirer">×</button></div></div>`).join("");
 list.querySelectorAll(".aura-music-row").forEach(el=>{
  el.onclick=e=>{if(e.target.closest("button"))return;state.selected=Number(el.dataset.index||0);render()};
  el.ondblclick=e=>{if(!e.target.closest("button"))playSelected()};
  el.ondragstart=e=>{state.dragId=el.dataset.id;e.dataTransfer.effectAllowed="move"};
  el.ondragover=e=>{e.preventDefault();e.dataTransfer.dropEffect="move"};
  el.ondrop=e=>{e.preventDefault();dropReorder(state.dragId,el.dataset.id)};
  el.querySelector('[data-act="remove"]').onclick=()=>removeItem(el.dataset.id);
  el.querySelector('[data-act="up"]').onclick=()=>moveItem(el.dataset.id,-1);
  el.querySelector('[data-act="down"]').onclick=()=>moveItem(el.dataset.id,1)
 });
 const full=document.getElementById("aura-music-full-v180");if(full)full.textContent=state.fullList?"RÉDUIRE LA PLAYLISTE":"VOIR PLAYLISTE COMPLÈTE"
}
async function persistOrder(){await api("/playlist/reorder","POST",{ids:state.items.map(x=>x.id)});await loadPlaylist()}
async function moveItem(id,delta){const i=state.items.findIndex(x=>x.id===id);if(i<0)return;const j=i+delta;if(j<0||j>=state.items.length)return;[state.items[i],state.items[j]]=[state.items[j],state.items[i]];state.selected=j;render();try{await persistOrder()}catch(e){toast(`Réorganisation impossible • ${e.message}`)}}
async function dropReorder(fromId,toId){if(!fromId||!toId||fromId===toId)return;const from=state.items.findIndex(x=>x.id===fromId),to=state.items.findIndex(x=>x.id===toId);if(from<0||to<0)return;const [item]=state.items.splice(from,1);state.items.splice(to,0,item);state.selected=to;render();try{await persistOrder()}catch(e){toast(`Réorganisation impossible • ${e.message}`)}}
async function removeItem(id){try{await api("/playlist/remove","POST",{id});toast("Morceau retiré");await loadPlaylist()}catch(e){toast(`Suppression impossible • ${e.message}`)}}
async function clearPlaylist(){if(!state.items.length)return;try{await api("/playlist/clear","POST",{});state.selected=0;toast("Playlist vidée");await loadPlaylist()}catch(e){toast(`Impossible de vider • ${e.message}`)}}
async function pick(kind){const labels={track:"AJOUT TITRE",playlist:"IMPORT PLAYLISTE",folder:"IMPORT DOSSIER"};runtime("busy",`${labels[kind]} • WINDOWS`);try{const d=await api("/pick","POST",{kind});if(d.cancelled){runtime("ok","VLC BRIDGE • CONNECTÉ");return}state.selected=0;toast(kind==="track"?"Titres ajoutés":"Playlist chargée");await loadPlaylist();runtime("ok","VLC BRIDGE • CONNECTÉ")}catch(e){runtime("error","VLC BRIDGE • ERREUR");toast(`Sélection impossible • ${e.message}`)}}
async function playSelected(){const cur=current();if(!cur)return toast("Aucun morceau sélectionné.");state.lastEndedId="";auraResetTimelineClock(0,0);renderProjectedTimeline();runtime("busy","VLC • LANCEMENT");try{await api("/play","POST",{id:cur.id});runtime("ok","VLC • LECTURE");startPoll()}catch(e){runtime("error","VLC • ÉCHEC");toast(`Lecture impossible • ${e.message}`)}}
async function togglePlay(){try{const s=await api("/status");if(s.current_id===current()?.id&&s.paused)await api("/control","POST",{action:"resume"});else if(s.current_id===current()?.id&&s.playing)await api("/control","POST",{action:"pause"});else await playSelected();await pollStatus()}catch(e){toast(`Commande lecture impossible • ${e.message}`)}}
async function stop(){try{await api("/control","POST",{action:"stop"});await pollStatus()}catch(e){toast(`Stop impossible • ${e.message}`)}}
async function next(){if(!state.items.length)return;state.selected=(state.selected+1)%state.items.length;render();await playSelected()}
async function previous(){if(!state.items.length)return;state.selected=(state.selected-1+state.items.length)%state.items.length;render();await playSelected()}
/* AURA_M180_UI4_R4_R6_VLC_CLOCK_SYNC */
function auraTimelinePerf(){return performance.now()}
function auraProjectedVlcPosition(at=auraTimelinePerf()){
 const t=state.timeline;
 if(!t.clockValid)return Number(t.pos)||0;
 let p=Number(t.basePos)||0;
 if(state.playing&&Number.isFinite(t.basePerf)){
   p+=(at-t.basePerf)/1000
 }
 if(Number.isFinite(t.rawSecond)){
   p=Math.max(p,t.rawSecond);
   if(state.playing)p=Math.min(p,t.rawSecond+.995)
 }
 if(Number(t.dur)>0)p=Math.min(p,Number(t.dur));
 return Math.max(0,p)
}
function auraResetTimelineClock(pos=0,dur=0){
 const t=state.timeline;
 t.clockValid=false;
 t.rawSecond=null;
 t.lastSamplePerf=null;
 t.basePos=Math.max(0,Number(pos)||0);
 t.basePerf=auraTimelinePerf();
 t.pos=t.basePos;
 if(Number(dur)>0)t.dur=Number(dur);
 t.pct=t.dur>0?t.basePos*100/t.dur:0;
 t.valid=true
}
function auraIngestVlcClockSample(rawPos,dur,playing,paused,valid){
 const t=state.timeline;
 const now=auraTimelinePerf();
 if(Number.isFinite(dur)&&dur>0)t.dur=dur;
 if(!valid||!Number.isFinite(rawPos)||rawPos<0){
   return
 }

 const raw=Math.max(0,Math.floor(rawPos));
 const before=t.clockValid?auraProjectedVlcPosition(now):raw;

 if(!t.clockValid){
   t.clockValid=true;
   t.rawSecond=raw;
   t.lastSamplePerf=now;
   // get_time is floor seconds. +0.35 s is only the initial estimate;
   // the first integer transition below calibrates the real phase.
   t.basePos=playing?raw+.35:raw;
   t.basePerf=now;
 }else{
   const previousRaw=Number(t.rawSecond);
   const previousSample=Number(t.lastSamplePerf);
   if(raw!==previousRaw){
     const sequential=raw===previousRaw+1&&playing&&Number.isFinite(previousSample);
     if(sequential){
       // The true integer boundary happened between the previous and current
       // VLC samples. Midpoint estimation gives <= half-poll timing error.
       const boundaryPerf=previousSample+(now-previousSample)/2;
       t.basePos=raw;
       t.basePerf=boundaryPerf
     }else{
       // Seek, track change or non-sequential jump: trust VLC immediately.
       t.basePos=raw;
       t.basePerf=now
     }
     t.rawSecond=raw
   }else{
     // Keep the smooth clock monotonic, but never run into the next VLC
     // integer second until VLC itself reports that boundary.
     const held=Math.min(Math.max(before,raw),raw+.995);
     t.basePos=held;
     t.basePerf=now
   }
   t.lastSamplePerf=now
 }

 if(!playing){
   const frozen=Math.min(Math.max(auraProjectedVlcPosition(now),raw),raw+.995);
   t.basePos=frozen;
   t.basePerf=now
 }
 t.pos=auraProjectedVlcPosition(now);
 t.pct=t.dur>0?t.pos*100/t.dur:0;
 t.valid=true
}
function renderProjectedTimeline(){
 const t=state.timeline;
 if(!t.valid)return;
 const pos=auraProjectedVlcPosition();
 const pct=t.dur>0?Math.max(0,Math.min(100,pos*100/t.dur)):Number(t.pct)||0;
 const progress=document.getElementById("aura-music-progress-v180");
 const now=document.getElementById("aura-music-current-time-v180");
 const total=document.getElementById("aura-music-total-v180");
 if(progress&&!progress.matches(":active"))progress.value=String(pct);
 if(now)now.textContent=fmt(pos);
 if(total&&t.dur>0)total.textContent=fmt(t.dur)
}
async function auraBindVisualizerToStatus(s){
 /* AURA_M180_UI6_R1_R5_R5_CURRENT_TRACK_ANALYSIS_BINDING_FIX */
 /* AURA_M180_UI6_R1_R5_R8_R1_BINDING_MARKER_POSTCHECK_FIX */
 const active=!!s?.playing||!!s?.paused;
 const activeId=String(s?.current_id||"");
 if(!active||!activeId){
  if(!active)state.__vizBackendCurrentId="";
  return
 }
 state.__vizBackendCurrentId=activeId;

 const pos=Math.max(0,Number(s?.position_seconds||0));
 const a=state.realAudioAnalysis;
 const loadedId=String(a?.id||"");
 const w0=Number(a?.window_start_seconds);
 const w1=Number(a?.window_end_seconds);
 const hasWindow=loadedId===activeId&&a?.available&&Array.isArray(a?.frames)&&a.frames.length&&Number.isFinite(w0)&&Number.isFinite(w1);
 const safelyCovered=hasWindow&&pos>=w0+.15&&pos<=w1-2.25;

 if(safelyCovered)return;

 if(state.__analysisLoadingId===activeId){
  const age=Date.now()-Number(state.__analysisLoadingAt||0);
  if(age>0&&age<5000)return;
  state.__analysisLoadingId="";
  state.__analysisLoadingAt=0
 }
 if(Date.now()<Number(state.__analysisRetryAt||0))return;

 await auraLoadRealAudioAnalysis(activeId,pos)
}

async function pollStatus(){
 if(state.__vlcClockPollBusy)return;
 state.__vlcClockPollBusy=true;
 try{
  const s=await api("/status");
  const dur=Number(s.duration_seconds);
  const pos=Number(s.position_seconds);
  const valid=s.status_valid!==false;

  if(valid){
    state.playing=!!s.playing;
    state.paused=!!s.paused
  }
  auraIngestVlcClockSample(pos,dur,state.playing,state.paused,valid);
  await auraBindVisualizerToStatus(s);
 await auraHandleNaturalEnd(s);

  const root=document.getElementById("aura-music-player-v180");
  const play=document.getElementById("aura-music-play-v180");
  if(root)root.dataset.playing=state.playing?"true":"false";
  if(play)play.textContent=state.playing?"Ⅱ":"▶";

  runtime(
    valid?"ok":"busy",
    state.playing?"VLC • LECTURE":state.paused?"VLC • PAUSE":valid?"VLC BRIDGE • CONNECTÉ":"VLC • SYNCHRONISATION"
  );

  if(Number.isFinite(Number(s.volume_percent))){
    state.volume=Number(s.volume_percent);
    const vol=document.getElementById("aura-music-volume-v180");
    const lab=document.getElementById("aura-music-volume-label-v180");
    if(vol&&!vol.matches(":active"))vol.value=String(state.volume);
    if(lab)lab.textContent=`${state.volume}%`
  }
  renderProjectedTimeline()
 }catch(_e){
  runtime("busy","VLC • SYNCHRONISATION");
  renderProjectedTimeline()
 }finally{
  state.__vlcClockPollBusy=false
 }
}

function startPoll(){if(state.poll)clearInterval(state.poll);if(state.timelineTimer)clearInterval(state.timelineTimer);pollStatus();state.poll=setInterval(pollStatus,250);state.timelineTimer=setInterval(renderProjectedTimeline,50)}
/* AURA_M180_UI5_R1_QUEUE_MODES */
function auraPersistQueueModes(){
 try{
  localStorage.setItem("aura.music.repeatMode",state.repeatMode);
  localStorage.setItem("aura.music.shuffle",state.shuffle?"1":"0")
 }catch(_e){}
}
function auraQueueModeLabel(){
 const repeat=state.repeatMode==="one"?"RÉPÉTER 1":state.repeatMode==="all"?"RÉPÉTER TOUT":"RÉPÉTER OFF";
 return `${repeat} • ALÉATOIRE ${state.shuffle?"ON":"OFF"}`
}
function auraRenderQueueModes(){
 const repeat=document.getElementById("aura-music-repeat-v180");
 const shuffle=document.getElementById("aura-music-shuffle-v180");
 const indicator=document.getElementById("aura-music-queue-indicator-v180");
 if(repeat){
  repeat.textContent=state.repeatMode==="one"?"↻ 1":state.repeatMode==="all"?"↻ ALL":"↻ OFF";
  repeat.classList.toggle("active",state.repeatMode!=="off");
  repeat.classList.toggle("repeat-one",state.repeatMode==="one")
 }
 if(shuffle){
  shuffle.textContent=state.shuffle?"⇄ ON":"⇄ OFF";
  shuffle.classList.toggle("active",state.shuffle)
 }
 if(indicator)indicator.textContent=auraQueueModeLabel()
}
function auraEnsureQueueModeControls(){
 if(document.getElementById("aura-music-mode-strip-v180"))return;
 const controls=document.querySelector("#aura-music-player-v180 .aura-music-controls");
 if(!controls)return;
 const strip=document.createElement("div");
 strip.id="aura-music-mode-strip-v180";
 strip.className="aura-music-mode-strip";
 strip.innerHTML='<button class="aura-music-mode-btn" id="aura-music-repeat-v180">↻ OFF</button><button class="aura-music-mode-btn" id="aura-music-shuffle-v180">⇄ OFF</button>';
 const indicator=document.createElement("div");
 indicator.id="aura-music-queue-indicator-v180";
 indicator.className="aura-music-queue-indicator";
 controls.parentElement.insertBefore(strip,controls.nextSibling);
 strip.parentElement.insertBefore(indicator,strip.nextSibling);
 document.getElementById("aura-music-repeat-v180").onclick=()=>{
  state.repeatMode=state.repeatMode==="off"?"all":state.repeatMode==="all"?"one":"off";
  auraPersistQueueModes();auraRenderQueueModes()
 };
 document.getElementById("aura-music-shuffle-v180").onclick=()=>{
  state.shuffle=!state.shuffle;auraPersistQueueModes();auraRenderQueueModes()
 };
 auraRenderQueueModes()
}
/* AURA_M180_UI5_R6_UP_NEXT_QUEUE_CORRECTNESS */
function auraChooseNextIndex(anchorId=""){
 const n=state.items.length;
 if(!n)return -1;
 const requestedAnchor=String(anchorId||"");
 let anchorIndex=requestedAnchor?state.items.findIndex(x=>String(x.id)===requestedAnchor):-1;
 if(anchorIndex<0)anchorIndex=Math.max(0,Math.min(state.selected,n-1));
 if(state.repeatMode==="one")return anchorIndex;
 const queuedId=String(state.queueNextId||"");
 if(queuedId){
  const qi=state.items.findIndex(x=>String(x.id)===queuedId);
  state.queueNextId="";
  if(qi>=0&&qi!==anchorIndex)return qi
 }
 if(state.shuffle&&n>1){
  let j=anchorIndex;
  for(let tries=0;tries<12&&j===anchorIndex;tries++)j=Math.floor(Math.random()*n);
  if(j===anchorIndex)j=(anchorIndex+1)%n;
  return j
 }
 const j=anchorIndex+1;
 if(j<n)return j;
 return state.repeatMode==="all"?0:-1
}
async function auraHandleNaturalEnd(s){
 if(!s||!s.ended||state.autoAdvancing)return;
 const endedId=String(s.current_id||"");
 auraClearResume(endedId);
 if(endedId&&endedId===state.lastEndedId)return;
 state.lastEndedId=endedId;
 state.autoAdvancing=true;
 try{
  const nextIndex=auraChooseNextIndex(endedId);
  if(nextIndex<0){
   state.playing=false;state.paused=false;
   const root=document.getElementById("aura-music-player-v180");
   if(root)root.dataset.playing="false";
   runtime("ok","VLC • FIN DE PLAYLISTE");
   return
  }
  state.selected=nextIndex;
  render();
  await playSelected()
 }finally{
  setTimeout(()=>{state.autoAdvancing=false},250)
 }
}

/* AURA_M180_UI5_R3_PREMIUM_LIBRARY */
function auraLibraryFavoriteSet(){return new Set((state.libraryState?.favorites||[]).map(String))}
function auraLibraryDate(v){
 try{
  const d=new Date(v);
  if(Number.isNaN(d.getTime()))return "";
  return d.toLocaleString("fr-FR",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"})
 }catch(_e){return ""}
}
function auraEnsureLibraryToolbar(){
 const aside=document.querySelector("#aura-music-player-v180 .aura-music-playlist");
 const head=aside?.querySelector(".aura-music-playlist-head");
 if(!aside||!head)return;
 if(!document.getElementById("aura-music-library-tools-v180")){
  const tools=document.createElement("div");
  tools.id="aura-music-library-tools-v180";
  tools.className="aura-music-library-tools";
  tools.innerHTML='<label class="aura-music-library-search"><input id="aura-music-library-search-v180" type="search" autocomplete="off" placeholder="Rechercher titre, artiste, album..."><span>⌕</span></label><button id="aura-music-library-favs-v180" class="aura-music-library-btn">☆ FAVORIS</button><button id="aura-music-library-history-btn-v180" class="aura-music-library-btn">◷ HIST.</button>';
  head.insertAdjacentElement("afterend",tools);
  const history=document.createElement("div");
  history.id="aura-music-library-history-v180";
  history.className="aura-music-library-history";
  tools.insertAdjacentElement("afterend",history);

  const search=document.getElementById("aura-music-library-search-v180");
  search.value=state.libraryQuery||"";
  search.oninput=()=>{
   state.libraryQuery=search.value||"";
   if(state.libraryQuery.trim())state.fullList=true;
   auraApplyLibraryFilters()
  };
  document.getElementById("aura-music-library-favs-v180").onclick=()=>{
   state.libraryFavoriteOnly=!state.libraryFavoriteOnly;
   if(state.libraryFavoriteOnly)state.fullList=true;
   auraApplyLibraryFilters();
   auraRenderLibraryButtons()
  };
  document.getElementById("aura-music-library-history-btn-v180").onclick=()=>{
   state.libraryHistoryOpen=!state.libraryHistoryOpen;
   if(state.libraryHistoryOpen)state.libraryCollectionsOpen=false;
   auraRenderHistory();
   auraRenderLibraryButtons()
  }
 }
 auraRenderLibraryButtons()
}
function auraRenderLibraryButtons(){
 const fav=document.getElementById("aura-music-library-favs-v180");
 const hist=document.getElementById("aura-music-library-history-btn-v180");
 if(fav){
  fav.classList.toggle("active",!!state.libraryFavoriteOnly);
  fav.textContent=state.libraryFavoriteOnly?"★ FAVORIS":"☆ FAVORIS"
 }
 if(hist)hist.classList.toggle("active",!!state.libraryHistoryOpen)
}
function auraDecorateFavoriteButtons(){
 const favs=auraLibraryFavoriteSet();
 document.querySelectorAll("#aura-music-list-v180 .aura-music-row").forEach(row=>{
  const id=String(row.dataset.id||"");
  const actions=row.querySelector(".aura-music-row-actions");
  if(!actions||actions.querySelector(".aura-music-fav-btn"))return;
  const b=document.createElement("button");
  b.type="button";
  b.className="aura-music-fav-btn"+(favs.has(id)?" active":"");
  b.title=favs.has(id)?"Retirer des favoris":"Ajouter aux favoris";
  b.textContent=favs.has(id)?"★":"☆";
  b.onclick=async e=>{
   e.preventDefault();e.stopPropagation();
   const enabled=!auraLibraryFavoriteSet().has(id);
   try{
    const d=await api("/library/favorite","POST",{id,enabled});
    if(d.library)state.libraryState=d.library;
    auraDecorateLibrary();
    toast(enabled?"Ajouté aux favoris":"Retiré des favoris")
   }catch(err){toast(`Favori impossible • ${err.message}`)}
  };
  actions.insertBefore(b,actions.firstChild)
 })
}
function auraApplyLibraryFilters(){
 const list=document.getElementById("aura-music-list-v180");
 if(!list)return;
 const q=String(state.libraryQuery||"").trim().toLocaleLowerCase("fr-FR");
 const favs=auraLibraryFavoriteSet();
 let visible=0;
 list.querySelectorAll(".aura-music-row").forEach(row=>{
  const id=String(row.dataset.id||"");
  const item=state.items.find(x=>String(x.id)===id)||{};
  const hay=[item.title,item.artist,item.album,item.year,item.extension].map(x=>String(x||"")).join(" ").toLocaleLowerCase("fr-FR");
  const okQuery=!q||hay.includes(q);
  const okFav=!state.libraryFavoriteOnly||favs.has(id);
  const show=okQuery&&okFav;
  row.style.display=show?"":"none";
  if(show)visible++
 });
 let empty=document.getElementById("aura-music-empty-filter-v180");
 if((q||state.libraryFavoriteOnly)&&visible===0){
  if(!empty){
   empty=document.createElement("div");
   empty.id="aura-music-empty-filter-v180";
   empty.className="aura-music-empty-filter";
   list.appendChild(empty)
  }
  empty.textContent=state.libraryFavoriteOnly?"Aucun favori ne correspond à la recherche.":"Aucun morceau ne correspond à la recherche."
 }else if(empty)empty.remove();
 const count=document.getElementById("aura-music-count-v180");
 if(count&&(q||state.libraryFavoriteOnly))count.textContent=`${visible} / ${state.items.length} morceau${state.items.length>1?"x":""}`
}
function auraRenderHistory(){
 const panel=document.getElementById("aura-music-library-history-v180");
 const list=document.getElementById("aura-music-list-v180");
 if(!panel)return;
 panel.classList.toggle("open",!!state.libraryHistoryOpen);
 if(list)list.style.display=state.libraryHistoryOpen?"none":"";
 if(!state.libraryHistoryOpen)return;
 const history=Array.isArray(state.libraryState?.history)?state.libraryState.history:[];
 panel.innerHTML='<div class="aura-music-history-head"><span>HISTORIQUE DE LECTURE</span><button class="aura-music-history-clear" id="aura-music-history-clear-v180">EFFACER</button></div>'+
  (history.length?history.map((h,i)=>{
   const idx=state.items.findIndex(x=>String(x.id)===String(h.id||""));
   const missing=idx<0;
   const sub=[h.artist,h.album].map(x=>String(x||"").trim()).filter(Boolean).join(" • ")||(missing?"Morceau absent de la playlist":"PC LOCAL");
   return `<div class="aura-music-history-item ${missing?"missing":""}" data-history-index="${i}" data-track-index="${idx}"><div class="aura-music-history-icon">▶</div><div class="aura-music-history-main"><div class="aura-music-history-title">${String(h.title||"Media")}</div><div class="aura-music-history-sub">${sub}</div></div><div class="aura-music-history-time">${auraLibraryDate(h.played_at)}</div></div>`
  }).join(""):'<div class="aura-music-empty-filter">Aucun morceau écouté pour le moment.</div>');
 const clear=document.getElementById("aura-music-history-clear-v180");
 if(clear)clear.onclick=async()=>{
  try{
   const d=await api("/library/clear-history","POST",{});
   if(d.library)state.libraryState=d.library;
   auraRenderHistory();
   toast("Historique effacé")
  }catch(e){toast(`Historique impossible • ${e.message}`)}
 };
 panel.querySelectorAll(".aura-music-history-item:not(.missing)").forEach(el=>{
  el.onclick=async()=>{
   const idx=Number(el.dataset.trackIndex);
   if(!Number.isFinite(idx)||idx<0)return;
   state.selected=idx;
   state.libraryHistoryOpen=false;
   render();
   await playSelected()
  }
 })
}
function auraPersistLibrarySelection(){
 const cur=current();
 const id=String(cur?.id||"");
 if(!id||id===state.libraryPersistedSelection)return;
 state.libraryPersistedSelection=id;
 api("/library/select","POST",{id}).then(d=>{
  if(d.library)state.libraryState={...state.libraryState,...d.library}
 }).catch(()=>{})
}

/* AURA_M180_UI7_R1_R1_ANCHOR_SAFE_PREMIUM_LIBRARY */
function auraUI7Norm(v){return String(v??"").trim()}
function auraUI7Get(k){try{return localStorage.getItem(k)||""}catch(_e){return ""}}
function auraUI7Set(k,v){try{v?localStorage.setItem(k,String(v)):localStorage.removeItem(k)}catch(_e){}}
function auraUI7Facets(){
 if(state.ui7Artist===undefined)state.ui7Artist=auraUI7Get("aura.music.ui7.artist");
 if(state.ui7Album===undefined)state.ui7Album=auraUI7Get("aura.music.ui7.album");
 if(state.ui7Year===undefined)state.ui7Year=auraUI7Get("aura.music.ui7.year");
 return {artist:auraUI7Norm(state.ui7Artist),album:auraUI7Norm(state.ui7Album),year:auraUI7Norm(state.ui7Year)}
}
function auraUI7SetFacet(k,v){
 v=auraUI7Norm(v);
 if(k==="artist"){state.ui7Artist=v;auraUI7Set("aura.music.ui7.artist",v)}
 if(k==="album"){state.ui7Album=v;auraUI7Set("aura.music.ui7.album",v)}
 if(k==="year"){state.ui7Year=v;auraUI7Set("aura.music.ui7.year",v)}
 auraApplyLibraryFilters()
}
function auraUI7Reset(){
 state.ui7Artist=state.ui7Album=state.ui7Year="";
 ["artist","album","year"].forEach(k=>auraUI7Set(`aura.music.ui7.${k}`,""));
 auraApplyLibraryFilters()
}
function auraUI7Stats(){
 const items=Array.isArray(state.items)?state.items:[];
 const favs=auraLibraryFavoriteSet(), artists=new Set(), albums=new Set(), years=new Set();
 items.forEach(x=>{
  const a=auraUI7Norm(x?.artist),b=auraUI7Norm(x?.album),y=auraUI7Norm(x?.year);
  if(a)artists.add(a); if(b)albums.add(b); if(y)years.add(y)
 });
 return {items,favs,artists,albums,years}
}
function auraUI7Fill(id,label,values,current){
 const e=document.getElementById(id); if(!e)return;
 const arr=[...values].sort((a,b)=>String(a).localeCompare(String(b),"fr-FR",{numeric:true,sensitivity:"base"}));
 e.replaceChildren();
 const first=document.createElement("option"); first.value=""; first.textContent=label; e.appendChild(first);
 arr.forEach(v=>{const o=document.createElement("option");o.value=String(v);o.textContent=String(v);e.appendChild(o)});
 e.value=values.has(String(current||""))?String(current||""):""
}
function auraEnsureUI7Library(){
 const tools=document.getElementById("aura-music-library-tools-v180"); if(!tools)return null;
 let p=document.getElementById("aura-music-ui7-library-v180"); if(p)return p;
 p=document.createElement("section"); p.id="aura-music-ui7-library-v180"; p.className="aura-music-ui7-library";
 p.innerHTML=`<div class="aura-music-ui7-head"><div><span>PREMIUM LIBRARY</span><strong>Bibliothèque</strong><small id="aura-music-ui7-summary-v180"></small></div><button id="aura-music-ui7-reset-v180" type="button">RÉINITIALISER</button></div>
 <div class="aura-music-ui7-stats">
  <div><span>MORCEAUX</span><strong id="aura-music-ui7-stat-tracks-v180">0</strong></div>
  <div><span>ARTISTES</span><strong id="aura-music-ui7-stat-artists-v180">0</strong></div>
  <div><span>ALBUMS</span><strong id="aura-music-ui7-stat-albums-v180">0</strong></div>
  <div><span>FAVORIS</span><strong id="aura-music-ui7-stat-favs-v180">0</strong></div>
 </div>
 <div class="aura-music-ui7-facets">
  <label><span>ARTISTE</span><select id="aura-music-ui7-artist-v180"></select></label>
  <label><span>ALBUM</span><select id="aura-music-ui7-album-v180"></select></label>
  <label><span>ANNÉE</span><select id="aura-music-ui7-year-v180"></select></label>
 </div>`;
 const smart=document.getElementById("aura-music-smart-strip-v180");
 (smart||tools).insertAdjacentElement("afterend",p);
 document.getElementById("aura-music-ui7-artist-v180").onchange=e=>auraUI7SetFacet("artist",e.target.value);
 document.getElementById("aura-music-ui7-album-v180").onchange=e=>auraUI7SetFacet("album",e.target.value);
 document.getElementById("aura-music-ui7-year-v180").onchange=e=>auraUI7SetFacet("year",e.target.value);
 document.getElementById("aura-music-ui7-reset-v180").onclick=auraUI7Reset;
 return p
}
function auraRefreshUI7Library(){
 if(!auraEnsureUI7Library())return;
 const m=auraUI7Stats(); let f=auraUI7Facets();
 if(f.artist&&!m.artists.has(f.artist)){state.ui7Artist="";auraUI7Set("aura.music.ui7.artist","")}
 if(f.album&&!m.albums.has(f.album)){state.ui7Album="";auraUI7Set("aura.music.ui7.album","")}
 if(f.year&&!m.years.has(f.year)){state.ui7Year="";auraUI7Set("aura.music.ui7.year","")}
 f=auraUI7Facets();
 auraUI7Fill("aura-music-ui7-artist-v180","Tous les artistes",m.artists,f.artist);
 auraUI7Fill("aura-music-ui7-album-v180","Tous les albums",m.albums,f.album);
 auraUI7Fill("aura-music-ui7-year-v180","Toutes les années",m.years,f.year);
 [["tracks",m.items.length],["artists",m.artists.size],["albums",m.albums.size],["favs",m.favs.size]].forEach(([k,v])=>{
  const e=document.getElementById(`aura-music-ui7-stat-${k}-v180`); if(e)e.textContent=String(v)
 });
 const s=document.getElementById("aura-music-ui7-summary-v180");
 if(s)s.textContent=`${m.items.length} morceaux · ${m.artists.size} artistes · ${m.albums.size} albums`;
 const r=document.getElementById("aura-music-ui7-reset-v180"); const active=!!(f.artist||f.album||f.year);
 if(r){r.disabled=!active;r.classList.toggle("active",active)}
}
function auraApplyUI7Facets(){
 const list=document.getElementById("aura-music-list-v180"); if(!list)return;
 const f=auraUI7Facets(); let visible=0;
 list.querySelectorAll(".aura-music-row").forEach(row=>{
  if(row.style.display==="none")return;
  const id=String(row.dataset.id||"");
  const x=(state.items||[]).find(v=>String(v?.id||"")===id)||{};
  const ok=(!f.artist||auraUI7Norm(x.artist)===f.artist)&&(!f.album||auraUI7Norm(x.album)===f.album)&&(!f.year||auraUI7Norm(x.year)===f.year);
  if(!ok)row.style.display="none"; else visible++
 });
 if(f.artist||f.album||f.year){
  const c=document.getElementById("aura-music-count-v180"); if(c)c.textContent=`${visible} / ${(state.items||[]).length} morceaux`;
  const s=document.getElementById("aura-music-ui7-summary-v180"); if(s)s.textContent=`${visible} morceaux visibles · filtres premium actifs`
 }
}
const auraUI7BaseFilter=auraApplyLibraryFilters;
auraApplyLibraryFilters=function(){auraUI7BaseFilter();auraApplyUI7Facets();auraRefreshUI7Library()};
const auraUI7BaseDecorate=auraDecorateLibrary;
auraDecorateLibrary=function(){auraUI7BaseDecorate();auraEnsureUI7Library();auraRefreshUI7Library()};

function auraDecorateLibrary(){
 auraEnsureLibraryToolbar();
 auraDecorateFavoriteButtons();
 auraApplyLibraryFilters();
 auraRenderHistory();
 auraRenderLibraryButtons();
 auraPersistLibrarySelection()
}
async function auraReloadLibraryState(){
 try{
  const d=await api("/library/state");
  if(d.library)state.libraryState=d.library;
  auraDecorateLibrary()
 }catch(_e){}
}
const auraBaseRenderUi5R3=render;
render=function(){
 auraBaseRenderUi5R3();
 auraDecorateLibrary()
};
const auraBasePlaySelectedUi5R3=playSelected;
playSelected=async function(){
 const result=await auraBasePlaySelectedUi5R3();
 setTimeout(auraReloadLibraryState,120);
 return result
};

/* AURA_M180_UI5_R4_SAVED_COLLECTIONS */
async function auraLoadCollections(){
 try{
  const d=await api("/collections");
  state.collections=Array.isArray(d.collections?.items)?d.collections.items:[];
  auraRenderCollections()
 }catch(_e){
  state.collections=Array.isArray(state.collections)?state.collections:[]
 }
}
function auraEnsureCollectionsUi(){
 const tools=document.getElementById("aura-music-library-tools-v180");
 if(!tools)return;
 if(!document.getElementById("aura-music-library-collections-v180")){
  const b=document.createElement("button");
  b.id="aura-music-library-collections-v180";
  b.className="aura-music-library-btn";
  b.textContent="▤ LISTES";
  b.onclick=()=>{
   state.libraryCollectionsOpen=!state.libraryCollectionsOpen;
   if(state.libraryCollectionsOpen)state.libraryHistoryOpen=false;
   auraRenderCollections();
   auraRenderHistory();
   auraRenderLibraryButtons();
   if(state.libraryCollectionsOpen)auraLoadCollections()
  };
  tools.appendChild(b)
 }
 let panel=document.getElementById("aura-music-collections-panel-v180");
 if(!panel){
  panel=document.createElement("div");
  panel.id="aura-music-collections-panel-v180";
  panel.className="aura-music-collections-panel";
  const hist=document.getElementById("aura-music-library-history-v180");
  if(hist)hist.insertAdjacentElement("afterend",panel);
  else tools.insertAdjacentElement("afterend",panel)
 }
}
function auraRenderCollectionButton(){
 const b=document.getElementById("aura-music-library-collections-v180");
 if(!b)return;
 b.classList.toggle("active",!!state.libraryCollectionsOpen);
 b.textContent=state.libraryCollectionsOpen?"▤ LISTES":"▤ LISTES"
}
function auraRenderCollections(){
 auraEnsureCollectionsUi();
 const panel=document.getElementById("aura-music-collections-panel-v180");
 const list=document.getElementById("aura-music-list-v180");
 if(!panel)return;
 panel.classList.toggle("open",!!state.libraryCollectionsOpen);
 if(list)list.style.display=(state.libraryHistoryOpen||state.libraryCollectionsOpen)?"none":"";
 auraRenderCollectionButton();
 if(!state.libraryCollectionsOpen)return;
 const rows=Array.isArray(state.collections)?state.collections:[];
 panel.innerHTML='<div class="aura-music-collections-head"><span class="aura-music-collections-title">PLAYLISTS ENREGISTRÉES</span><button id="aura-music-collections-save-v180" class="aura-music-collections-save">+ ENREGISTRER</button></div>'+
  (rows.length?rows.map(r=>`<div class="aura-music-collection-row" data-id="${String(r.id||"")}"><div class="aura-music-collection-icon">▤</div><div class="aura-music-collection-main" data-act="load"><div class="aura-music-collection-name">${String(r.name||"Playlist")}</div><div class="aura-music-collection-sub">${Array.isArray(r.paths)?r.paths.length:0} morceau${Array.isArray(r.paths)&&r.paths.length>1?"x":""}</div></div><div class="aura-music-collection-actions"><button data-act="rename" title="Renommer">✎</button><button data-act="delete" title="Supprimer">×</button></div></div>`).join(""):'<div class="aura-music-empty-filter">Aucune playlist enregistrée.</div>');
 const save=document.getElementById("aura-music-collections-save-v180");
 if(save)save.onclick=async()=>{
  if(!state.items.length)return toast("La playlist actuelle est vide.");
  const suggested=`Playlist ${new Date().toLocaleDateString("fr-FR")}`;
  const name=window.prompt("Nom de la playlist à enregistrer :",suggested);
  if(!name||!name.trim())return;
  try{
   const d=await api("/collections/save","POST",{name:name.trim()});
   state.collections=Array.isArray(d.collections?.items)?d.collections.items:[];
   auraRenderCollections();
   toast("Playlist enregistrée")
  }catch(e){toast(`Enregistrement impossible • ${e.message}`)}
 };
 panel.querySelectorAll(".aura-music-collection-row").forEach(row=>{
  const id=String(row.dataset.id||"");
  row.querySelector('[data-act="load"]')?.addEventListener("click",async()=>{
   try{
    runtime("busy","PLAYLIST • CHARGEMENT");
    const d=await api("/collections/load","POST",{id});
    state.items=Array.isArray(d.playlist?.items)?d.playlist.items:[];
    state.selected=0;
    state.libraryCollectionsOpen=false;
    state.libraryHistoryOpen=false;
    state.libraryQuery="";
    state.libraryFavoriteOnly=false;
    state.libraryRestored=true;
    render();
    runtime("ok","PLAYLIST • CHARGÉE");
    const missing=Number(d.missing||0);
    toast(missing?`Playlist chargée • ${missing} fichier(s) absent(s)`:"Playlist chargée")
   }catch(e){runtime("error","PLAYLIST • ÉCHEC");toast(`Chargement impossible • ${e.message}`)}
  });
  row.querySelector('[data-act="rename"]')?.addEventListener("click",async e=>{
   e.stopPropagation();
   const old=row.querySelector(".aura-music-collection-name")?.textContent||"Playlist";
   const name=window.prompt("Nouveau nom :",old);
   if(!name||!name.trim()||name.trim()===old)return;
   try{
    const d=await api("/collections/rename","POST",{id,name:name.trim()});
    state.collections=Array.isArray(d.collections?.items)?d.collections.items:[];
    auraRenderCollections()
   }catch(err){toast(`Renommage impossible • ${err.message}`)}
  });
  row.querySelector('[data-act="delete"]')?.addEventListener("click",async e=>{
   e.stopPropagation();
   const name=row.querySelector(".aura-music-collection-name")?.textContent||"cette playlist";
   if(!window.confirm(`Supprimer « ${name} » des playlists enregistrées ?`))return;
   try{
    const d=await api("/collections/delete","POST",{id});
    state.collections=Array.isArray(d.collections?.items)?d.collections.items:[];
    auraRenderCollections();
    toast("Playlist enregistrée supprimée")
   }catch(err){toast(`Suppression impossible • ${err.message}`)}
  })
 })
}
const auraBaseDecorateLibraryUi5R4=auraDecorateLibrary;
auraDecorateLibrary=function(){
 auraBaseDecorateLibraryUi5R4();
 auraEnsureCollectionsUi();
 auraRenderCollectionButton();
 if(state.libraryCollectionsOpen)auraRenderCollections()
};
const auraBaseRenderHistoryUi5R4=auraRenderHistory;
auraRenderHistory=function(){
 auraBaseRenderHistoryUi5R4();
 const list=document.getElementById("aura-music-list-v180");
 if(list)list.style.display=(state.libraryHistoryOpen||state.libraryCollectionsOpen)?"none":"";
 auraRenderCollectionButton()
};
setTimeout(auraLoadCollections,350);

/* AURA_M180_UI5_R5_SMART_LIBRARY */
function auraSmartNormalize(v){
 return String(v||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase("fr-FR").replace(/[^a-z0-9]+/g," ").trim()
}
function auraSmartDuplicateKey(item){
 const title=auraSmartNormalize(item?.title);
 const artist=auraSmartNormalize(item?.artist);
 if(title&&artist)return `${artist}|${title}`;
 return ""
}
function auraSmartDuplicateSet(){
 const buckets=new Map();
 state.items.forEach(item=>{
  const key=auraSmartDuplicateKey(item);
  if(!key)return;
  if(!buckets.has(key))buckets.set(key,[]);
  buckets.get(key).push(String(item.id||""))
 });
 const out=new Set();
 buckets.forEach(ids=>{if(ids.length>1)ids.forEach(id=>out.add(id))});
 return out
}
function auraSmartRecentMap(){
 const out=new Map();
 const h=Array.isArray(state.libraryState?.history)?state.libraryState.history:[];
 h.forEach((row,i)=>{
  const id=String(row?.id||"");
  if(id&&!out.has(id)){
   const t=Date.parse(row?.played_at||"");
   out.set(id,Number.isFinite(t)?t:(h.length-i))
  }
 });
 return out
}
function auraEnsureSmartLibraryUi(){
 const tools=document.getElementById("aura-music-library-tools-v180");
 if(!tools)return;
 if(document.getElementById("aura-music-smart-strip-v180"))return;
 const strip=document.createElement("div");
 strip.id="aura-music-smart-strip-v180";
 strip.className="aura-music-smart-strip";
 strip.innerHTML='<label class="aura-music-smart-select-wrap"><select id="aura-music-smart-sort-v180" class="aura-music-smart-select"><option value="playlist">ORDRE PLAYLIST</option><option value="title">TITRE A → Z</option><option value="artist">ARTISTE A → Z</option><option value="album">ALBUM A → Z</option><option value="year">ANNÉE RÉCENTE</option><option value="recent">ÉCOUTÉS RÉCEMMENT</option></select></label><button id="aura-music-smart-dup-v180" class="aura-music-smart-btn">DUPLICATA</button><span id="aura-music-smart-count-v180" class="aura-music-smart-count"></span>';
 tools.insertAdjacentElement("afterend",strip);

 const select=document.getElementById("aura-music-smart-sort-v180");
 state.smartSort=state.smartSort||localStorage.getItem("aura.music.smartSort")||"playlist";
 state.smartDuplicates=typeof state.smartDuplicates==="boolean"?state.smartDuplicates:(localStorage.getItem("aura.music.smartDuplicates")==="1");
 select.value=state.smartSort;
 select.onchange=()=>{
  state.smartSort=select.value||"playlist";
  try{localStorage.setItem("aura.music.smartSort",state.smartSort)}catch(_e){}
  auraApplySmartLibrary()
 };
 const dup=document.getElementById("aura-music-smart-dup-v180");
 dup.onclick=()=>{
  state.smartDuplicates=!state.smartDuplicates;
  try{localStorage.setItem("aura.music.smartDuplicates",state.smartDuplicates?"1":"0")}catch(_e){}
  auraApplySmartLibrary()
 }
}
function auraSmartSortRows(rows){
 const byId=new Map(state.items.map((x,i)=>[String(x.id||""),{item:x,index:i}]));
 const recent=auraSmartRecentMap();
 const mode=state.smartSort||"playlist";
 const key=(row)=>{
  const id=String(row.dataset.id||"");
  const rec=byId.get(id)||{item:{},index:999999};
  const item=rec.item||{};
  if(mode==="title")return [auraSmartNormalize(item.title),rec.index];
  if(mode==="artist")return [auraSmartNormalize(item.artist),auraSmartNormalize(item.title),rec.index];
  if(mode==="album")return [auraSmartNormalize(item.album),auraSmartNormalize(item.track),auraSmartNormalize(item.title),rec.index];
  if(mode==="year"){
   const y=parseInt(String(item.year||"").slice(0,4),10);
   return [Number.isFinite(y)?-y:999999,auraSmartNormalize(item.artist),auraSmartNormalize(item.title),rec.index]
  }
  if(mode==="recent")return [-(recent.get(id)||0),rec.index];
  return [rec.index]
 };
 const cmp=(a,b)=>{
  const ka=key(a),kb=key(b),n=Math.max(ka.length,kb.length);
  for(let i=0;i<n;i++){
   const av=ka[i],bv=kb[i];
   if(av===bv)continue;
   if(typeof av==="number"&&typeof bv==="number")return av-bv;
   return String(av??"").localeCompare(String(bv??""),"fr",{sensitivity:"base",numeric:true})
  }
  return 0
 };
 return rows.slice().sort(cmp)
}
function auraApplySmartLibrary(){
 auraEnsureSmartLibraryUi();
 const list=document.getElementById("aura-music-list-v180");
 if(!list)return;
 const dupSet=auraSmartDuplicateSet();
 const rows=Array.from(list.querySelectorAll(".aura-music-row"));
 rows.forEach(row=>{
  const id=String(row.dataset.id||"");
  const duplicate=dupSet.has(id);
  row.classList.toggle("aura-music-duplicate-row",duplicate);
  if(state.smartDuplicates&&!duplicate)row.style.display="none"
 });
 auraSmartSortRows(rows).forEach(row=>list.appendChild(row));

 const visible=rows.filter(row=>row.style.display!=="none").length;
 const dup=document.getElementById("aura-music-smart-dup-v180");
 const count=document.getElementById("aura-music-smart-count-v180");
 const select=document.getElementById("aura-music-smart-sort-v180");
 if(select&&select.value!==(state.smartSort||"playlist"))select.value=state.smartSort||"playlist";
 if(dup){
  dup.classList.toggle("active",!!state.smartDuplicates);
  dup.textContent=state.smartDuplicates?"DUPLICATA ON":"DUPLICATA"
 }
 if(count){
  const d=dupSet.size;
  count.textContent=state.smartDuplicates?`${visible} affiché${visible>1?"s":""}`:`${d} doublon${d>1?"s":""}`
 }
}
const auraBaseApplyLibraryFiltersUi5R5=auraApplyLibraryFilters;
auraApplyLibraryFilters=function(){
 auraBaseApplyLibraryFiltersUi5R5();
 auraApplySmartLibrary()
};
const auraBaseDecorateLibraryUi5R5=auraDecorateLibrary;
auraDecorateLibrary=function(){
 auraBaseDecorateLibraryUi5R5();
 auraEnsureSmartLibraryUi();
 auraApplySmartLibrary()
};

function auraDecorateUpNext(){
 const queued=String(state.queueNextId||"");
 document.querySelectorAll("#aura-music-list-v180 .aura-music-row").forEach(row=>{
  const id=String(row.dataset.id||"");
  row.classList.toggle("aura-music-upnext-row",!!queued&&id===queued);
  const actions=row.querySelector(".aura-music-row-actions");
  if(!actions)return;
  let btn=actions.querySelector(".aura-music-play-next-btn");
  if(!btn){
   btn=document.createElement("button");
   btn.type="button";
   btn.className="aura-music-play-next-btn";
   btn.title="Lire ensuite";
   btn.textContent="↪";
   btn.onclick=async e=>{
    e.preventDefault();e.stopPropagation();
    await auraQueuePlayNext(id)
   };
   actions.insertBefore(btn,actions.firstChild)
  }
  btn.classList.toggle("active",!!queued&&id===queued);
  btn.title=queued&&id===queued?"Programmé ensuite":"Lire ensuite"
 })
}
async function auraQueuePlayNext(targetId){
 targetId=String(targetId||"");
 if(!targetId)return;
 try{
  const selectedId=String(current()?.id||"");
  const s=await api("/status").catch(()=>({}));
  let anchorId=String(s?.current_id||selectedId||"");
  if(!anchorId||!state.items.some(x=>String(x.id)===anchorId))anchorId=selectedId;
  if(!anchorId)return toast("Sélectionne ou lance d’abord un morceau.");
  if(targetId===anchorId)return toast("Ce morceau est déjà en cours.");
  const target=state.items.find(x=>String(x.id)===targetId);
  if(!target)return;
  const reordered=state.items.filter(x=>String(x.id)!==targetId);
  const anchorIndex=reordered.findIndex(x=>String(x.id)===anchorId);
  if(anchorIndex<0)return toast("Morceau courant introuvable dans la playlist.");
  reordered.splice(anchorIndex+1,0,target);
  state.items=reordered;
  const keepIndex=selectedId?state.items.findIndex(x=>String(x.id)===selectedId):-1;
  if(keepIndex>=0)state.selected=keepIndex;
  state.queueNextId=targetId;
  render();
  const d=await api("/playlist/reorder","POST",{ids:state.items.map(x=>x.id)});
  if(Array.isArray(d.playlist?.items)){
   const selectedAfter=String(current()?.id||selectedId);
   state.items=d.playlist.items;
   const k=state.items.findIndex(x=>String(x.id)===selectedAfter);
   if(k>=0)state.selected=k
  }
  render();
  toast(state.shuffle?"Programmé ensuite • priorité unique sur ALÉATOIRE":"Programmé pour être lu ensuite")
 }catch(e){
  toast(`Lire ensuite impossible • ${e.message}`);
  try{await loadPlaylist()}catch(_e){}
 }
}
const auraBaseDecorateLibraryUi5R6=auraDecorateLibrary;
auraDecorateLibrary=function(){
 auraBaseDecorateLibraryUi5R6();
 auraDecorateUpNext()
};

/* AURA_M180_UI5_R7_M3U8_IMPORT_EXPORT */
function auraEnsureM3uButtons(){
 const panel=document.getElementById("aura-music-collections-panel-v180");
 if(!panel)return;
 const head=panel.querySelector(".aura-music-collections-head");
 if(!head)return;
 let actions=head.querySelector(".aura-music-collections-head-actions");
 if(!actions){
  actions=document.createElement("div");
  actions.className="aura-music-collections-head-actions";
  const save=document.getElementById("aura-music-collections-save-v180");
  if(save){save.insertAdjacentElement("beforebegin",actions);actions.appendChild(save)}
  else head.appendChild(actions)
 }
 if(!document.getElementById("aura-music-m3u-import-v180")){
  const b=document.createElement("button");
  b.id="aura-music-m3u-import-v180";b.className="aura-music-collections-io";b.textContent="IMPORT M3U";
  b.onclick=async()=>{
   if(state.items.length&&!window.confirm("Importer une playlist M3U/M3U8 remplacera la file actuelle. Continuer ?"))return;
   runtime("busy","PLAYLIST • IMPORT");
   try{
    const d=await api("/playlist/import-m3u8","POST",{});
    if(d.cancelled){runtime("ok","PLAYLIST • ANNULÉ");return}
    state.items=Array.isArray(d.playlist?.items)?d.playlist.items:[];
    state.selected=0;state.queueNextId="";state.libraryQuery="";state.libraryFavoriteOnly=false;
    state.libraryCollectionsOpen=false;state.libraryHistoryOpen=false;
    render();runtime("ok","PLAYLIST • IMPORTÉE");
    const missing=Number(d.missing||0);
    toast(missing?`${d.imported||state.items.length} morceaux importés • ${missing} ignoré(s)`:`${d.imported||state.items.length} morceaux importés`)
   }catch(e){runtime("error","PLAYLIST • IMPORT ÉCHEC");toast(`Import M3U impossible • ${e.message}`)}
  };
  actions.insertBefore(b,actions.firstChild)
 }
 if(!document.getElementById("aura-music-m3u-export-v180")){
  const b=document.createElement("button");
  b.id="aura-music-m3u-export-v180";b.className="aura-music-collections-io";b.textContent="EXPORT M3U";
  b.onclick=async()=>{
   if(!state.items.length)return toast("La playlist actuelle est vide.");
   runtime("busy","PLAYLIST • EXPORT");
   try{
    const d=await api("/playlist/export-m3u8","POST",{});
    if(d.cancelled){runtime("ok","PLAYLIST • ANNULÉ");return}
    runtime("ok","PLAYLIST • EXPORTÉE");toast(`${d.count||state.items.length} morceaux exportés en M3U8`)
   }catch(e){runtime("error","PLAYLIST • EXPORT ÉCHEC");toast(`Export M3U impossible • ${e.message}`)}
  };
  const save=document.getElementById("aura-music-collections-save-v180");
  if(save)actions.insertBefore(b,save);else actions.appendChild(b)
 }
}
const auraBaseRenderCollectionsUi5R7=auraRenderCollections;
auraRenderCollections=function(){
 auraBaseRenderCollectionsUi5R7();
 auraEnsureM3uButtons()
};

/* AURA_M180_UI5_R8_RESUME_CHECKPOINT */
function auraFmtResume(sec){
 sec=Math.max(0,Math.floor(Number(sec)||0));
 const m=Math.floor(sec/60),s=sec%60;
 return `${m}:${String(s).padStart(2,"0")}`
}
function auraEnsureResumeUi(){
 if(document.getElementById("aura-music-resume-card-v180"))return;
 const controls=document.querySelector("#aura-music-player-v180 .aura-music-controls");
 if(!controls)return;
 const card=document.createElement("div");
 card.id="aura-music-resume-card-v180";
 card.className="aura-music-resume-card";
 card.innerHTML='<div class="aura-music-resume-copy"><div class="aura-music-resume-label">REPRENDRE LA LECTURE</div><div id="aura-music-resume-title-v180" class="aura-music-resume-title"></div><div id="aura-music-resume-sub-v180" class="aura-music-resume-sub"></div></div><div class="aura-music-resume-actions"><button id="aura-music-resume-go-v180" class="aura-music-resume-btn">REPRENDRE</button><button id="aura-music-resume-dismiss-v180" class="aura-music-resume-dismiss" title="Oublier">×</button></div>';
 const indicator=document.getElementById("aura-music-queue-indicator-v180");
 (indicator||controls).insertAdjacentElement("afterend",card);
 document.getElementById("aura-music-resume-go-v180").onclick=auraResumePlayback;
 document.getElementById("aura-music-resume-dismiss-v180").onclick=()=>auraClearResume(String(state.resumeState?.item_id||""))
}
function auraResumeEligible(r){
 const id=String(r?.item_id||"");
 const pos=Number(r?.position_seconds||0);
 const dur=Number(r?.duration_seconds||0);
 return !!id&&pos>=10&&dur>20&&(dur-pos)>=10&&state.items.some(x=>String(x.id)===id)
}
function auraRenderResume(){
 auraEnsureResumeUi();
 const card=document.getElementById("aura-music-resume-card-v180");
 if(!card)return;
 const r=state.resumeState||{};
 /* AURA_M180_UI6_R1_R2_RESUME_CARD_ACTIVE_PLAYBACK_FIX */
 const playbackActive=!!state.playing||!!state.paused;
 const ok=auraResumeEligible(r)&&!playbackActive;
 card.classList.toggle("open",ok);
 if(!ok)return;
 const item=state.items.find(x=>String(x.id)===String(r.item_id||""))||{};
 const title=String(item.title||r.title||"Morceau");
 const artist=String(item.artist||r.artist||"");
 document.getElementById("aura-music-resume-title-v180").textContent=title;
 document.getElementById("aura-music-resume-sub-v180").textContent=`${artist?artist+" • ":""}${auraFmtResume(r.position_seconds)} / ${auraFmtResume(r.duration_seconds)}`;
 document.getElementById("aura-music-resume-go-v180").textContent=`REPRENDRE ${auraFmtResume(r.position_seconds)}`
}
async function auraLoadResume(){
 try{
  const d=await api("/resume");
  state.resumeState=d.resume||{};
  auraRenderResume()
 }catch(_e){}
}
async function auraClearResume(id=""){
 try{
  const d=await api("/resume/clear","POST",{id:String(id||"")});
  state.resumeState=d.resume||{};
  auraRenderResume()
 }catch(_e){}
}
async function auraPersistResumeCheckpoint(){
 if(state.__resumeWriteBusy)return;
 state.__resumeWriteBusy=true;
 try{
  const s=await api("/status");
  if(!s||!s.status_valid)return;
  const id=String(s.current_id||"");
  const pos=Number(s.position_seconds||0);
  const dur=Number(s.duration_seconds||0);
  if(!id||dur<=20)return;
  if(s.ended||pos>=dur-5){
   await auraClearResume(id);
   return
  }
  if(!s.playing||s.paused||pos<10||dur-pos<10)return;
  const d=await api("/resume/update","POST",{id,position:pos,duration:dur});
  state.resumeState=d.resume||state.resumeState||{};
  auraRenderResume()
 }catch(_e){}finally{
  state.__resumeWriteBusy=false
 }
}
async function auraResumePlayback(){
 const r=state.resumeState||{};
 if(!auraResumeEligible(r))return;
 const idx=state.items.findIndex(x=>String(x.id)===String(r.item_id||""));
 if(idx<0)return;
 state.selected=idx;
 render();
 try{
  await playSelected();
  const dur=Number(r.duration_seconds||0),pos=Number(r.position_seconds||0);
  const pct=dur>0?Math.max(0,Math.min(100,(pos/dur)*100)):0;
  await new Promise(resolve=>setTimeout(resolve,180));
  await api("/control","POST",{action:"seek_percent",value:pct});
  auraResetTimelineClock(pos,dur);
  renderProjectedTimeline();
  runtime("ok","VLC • REPRISE");
  toast(`Lecture reprise à ${auraFmtResume(pos)}`)
 }catch(e){
  toast(`Reprise impossible • ${e.message}`)
 }
}
const auraBaseDecorateLibraryUi5R8=auraDecorateLibrary;
auraDecorateLibrary=function(){
 auraBaseDecorateLibraryUi5R8();
 auraRenderResume()
};
setTimeout(auraLoadResume,450);
if(!state.resumeTimer)state.resumeTimer=setInterval(auraPersistResumeCheckpoint,3000);

/* AURA_M180_UI6_R1_REAL_AUDIO_REACTIVE_VISUALIZER */
function auraVisualizerRoot(){
 return document.querySelector("#aura-music-player-v180 .aura-music-premium-visualizer")
}
function auraVisualizerBars(){
 const root=auraVisualizerRoot();
 return root?Array.from(root.children).filter(x=>x instanceof HTMLElement):[]
}
function auraSetVisualizerMode(mode){
 const root=auraVisualizerRoot();
 if(!root)return;
 root.classList.add("audio-reactive");
 root.classList.toggle("is-analyzing",mode==="analyzing");
 root.classList.toggle("is-unavailable",mode==="unavailable")
}
function auraVisualizerIdle(){
 const bars=auraVisualizerBars();
 bars.forEach((bar,i)=>{
  const base=.18+.055*Math.sin(i*.72);
  bar.style.transform=`scaleY(${Math.max(.1,base).toFixed(3)})`;
  bar.style.opacity=".48"
 })
}
/* AURA_M180_UI6_R1_R3_SMOOTH_VISUALIZER_INTERPOLATION */
/* AURA_M180_UI6_R1_R5_CANVAS_SPECTRUM_PLL */
function auraEnsureSpectrumCanvas(){
 const root=auraVisualizerRoot();
 if(!root)return null;
 root.classList.add("audio-reactive");
 let canvas=root.querySelector(".aura-music-spectrum-canvas");
 if(!canvas){
  canvas=document.createElement("canvas");
  canvas.className="aura-music-spectrum-canvas";
  root.appendChild(canvas)
 }
 return canvas
}
function auraSpectrumContext(){
 const canvas=auraEnsureSpectrumCanvas();
 if(!canvas)return null;
 const rect=canvas.getBoundingClientRect();
 const width=Math.max(1,rect.width);
 const height=Math.max(1,rect.height);
 const dpr=Math.max(1,Math.min(1.5,window.devicePixelRatio||1));
 const pw=Math.max(1,Math.round(width*dpr));
 const ph=Math.max(1,Math.round(height*dpr));
 if(canvas.width!==pw||canvas.height!==ph){
  canvas.width=pw;canvas.height=ph;
  canvas.__auraGradient=null
 }
 const ctx=canvas.getContext("2d",{alpha:true,desynchronized:true});
 if(!ctx)return null;
 ctx.setTransform(dpr,0,0,dpr,0,0);
 if(!canvas.__auraGradient){
  const g=ctx.createLinearGradient(0,height,0,0);
  g.addColorStop(0,"#8b5cf6");
  g.addColorStop(.48,"#6d7df8");
  g.addColorStop(1,"#58e7ff");
  canvas.__auraGradient=g
 }
 return {canvas,ctx,width,height}
}
function auraVisualizerClockPosition(now){
 let auth=0;
 try{auth=auraProjectedVlcPosition(now)}catch(_e){auth=Number(state.timeline?.pos||0)}
 auth=Math.max(0,Number(auth||0));

 const track=String(state.realAudioAnalysis?.id||current()?.id||"");
 let c=state.__vizClock;
 if(!c||c.track!==track||!Number.isFinite(c.pos)||!Number.isFinite(c.now)){
  c={track,pos:auth,now};
  state.__vizClock=c;
  return auth
 }

 const dt=Math.max(0,Math.min(.05,(now-c.now)/1000));
 let predicted=c.pos;
 if(state.playing&&!state.paused)predicted+=dt;

 const error=auth-predicted;
 if(Math.abs(error)>.35){
  predicted=auth
 }else{
  const maxCorrection=Math.max(.0005,dt*.10);
  const correction=Math.max(-maxCorrection,Math.min(maxCorrection,error*.055));
  predicted+=correction
 }

 if(state.playing&&!state.paused&&predicted<c.pos)predicted=c.pos;

 c.pos=Math.max(0,predicted);
 c.now=now;
 c.track=track;
 return c.pos
}
function auraSpectrumInterpolatedFrame(a,pos){
 const frames=a?.frames;
 if(!Array.isArray(frames)||!frames.length)return null;
 const step=Math.max(.01,Number(a.step_seconds||1/60));
 const windowStart=Math.max(0,Number(a.window_start_seconds||0));
 const exact=Math.max(0,(pos-windowStart)/step);
 const base=Math.floor(exact);
 const t=Math.max(0,Math.min(1,exact-base));
 const at=(n)=>frames[Math.max(0,Math.min(frames.length-1,n))]||[];
 const f0=at(base),f1=at(base+1);
 const out=new Float32Array(42);
 for(let i=0;i<42;i++){
  const u=Number(f0[i]||0),v=Number(f1[i]||u);
  out[i]=(u+(v-u)*t)/255
 }
 return out
}
function auraDrawSpectrumFrame(now=performance.now()){
 const box=auraSpectrumContext();
 if(!box)return;
 const {ctx,width,height}=box;
 ctx.clearRect(0,0,width,height);

 const a=state.realAudioAnalysis;
 const count=38;
 const backendId=String(state.__vizBackendCurrentId||"");
 const analysisId=String(a?.id||"");
 const analysisMatches=!backendId||analysisId===backendId;
 if(!a||!a.available||!analysisMatches||!Array.isArray(a.frames)||!a.frames.length){
  const gap=2;
  const bw=Math.max(1,(width-gap*(count-1))/count);
  ctx.fillStyle="rgba(103,126,238,.46)";
  for(let i=0;i<count;i++){
   const h=height*(.18+.025*Math.sin(i*.71));
   ctx.fillRect(Math.round(i*(bw+gap)),height-h,Math.ceil(bw),h)
  }
  return
 }

 const pos=auraVisualizerClockPosition(now);
 const f=auraSpectrumInterpolatedFrame(a,pos);
 if(!f)return;

 if(!state.__vizCanvasSmooth||state.__vizCanvasSmooth.length!==count){
  state.__vizCanvasSmooth=new Float32Array(count);
  state.__vizCanvasSmooth.fill(.12)
 }
 const previousNow=Number(state.__vizCanvasNow||now);
 const dt=Math.max(1,Math.min(34,now-previousNow));
 state.__vizCanvasNow=now;

 /* AURA_M180_UI6_R1_R5_R4_AGC_FLOOR_VERTICAL_EXPANSION */
 const rms=Math.max(0,Math.min(1,f[0]||0));

 const frameBands=new Float32Array(count);
 let framePeak=0;
 for(let i=0;i<count;i++){
  const v=Math.max(0,Math.min(1,f[4+i]||0));
  frameBands[i]=v;
  if(v>framePeak)framePeak=v
 }

 const sorted=Array.from(frameBands).sort((a,b)=>a-b);
 const p75=sorted[Math.max(0,Math.min(sorted.length-1,Math.floor((sorted.length-1)*.75)))]||0;
 const p90=sorted[Math.max(0,Math.min(sorted.length-1,Math.floor((sorted.length-1)*.90)))]||0;

 // Never disable AGC on quiet/sparse frames.
 // A floor only prevents division by zero; low signal now produces MORE gain, not less.
 const reference=Math.max(.0015,p75*.78,p90*.48,framePeak*.24);
 const desiredGain=Math.max(.9,Math.min(24,.70/reference));

 const priorGain=Number(state.__vizAdaptiveGain||1);
 const gainTau=desiredGain>priorGain?240:760;
 const gainAlpha=1-Math.exp(-dt/gainTau);
 const adaptiveGain=priorGain+(desiredGain-priorGain)*gainAlpha;
 state.__vizAdaptiveGain=adaptiveGain;

 const targets=new Float32Array(count);
 for(let i=0;i<count;i++){
  const raw=Math.max(0,Math.min(1,frameBands[i]*adaptiveGain));
  const shaped=Math.pow(raw,.54);
  // Keep a small floor, then spend almost the full 44px on actual spectrum dynamics.
  const level=.035+shaped*(.90+.06*rms);
  targets[i]=Math.max(.045,Math.min(.995,level))
 }
 const spatial=new Float32Array(count);
 for(let i=0;i<count;i++){
  const left=targets[Math.max(0,i-1)];
  const center=targets[i];
  const right=targets[Math.min(count-1,i+1)];
  spatial[i]=left*.12+center*.76+right*.12
 }

 const smooth=state.__vizCanvasSmooth;
 for(let i=0;i<count;i++){
  const prev=smooth[i];
  const target=spatial[i];
  const tau=target>prev?26:72;
  const alpha=1-Math.exp(-dt/tau);
  smooth[i]=prev+(target-prev)*alpha
 }

 const gap=Math.max(1.5,Math.min(2.5,width/260));
 const bw=Math.max(1,(width-gap*(count-1))/count);
 ctx.fillStyle=box.canvas.__auraGradient;

 for(let i=0;i<count;i++){
  const barH=Math.max(2,Math.min(height-1,smooth[i]*(height-1)));
  const x=Math.round((i*(bw+gap))*2)/2;
  const y=Math.round((height-barH)*2)/2;
  const w=Math.max(1,Math.floor(bw*2)/2);
  ctx.fillRect(x,y,w,barH)
 }
}
function auraVisualizerFrame(now=performance.now()){
 auraDrawSpectrumFrame(now)
}

/* AURA_M180_UI6_R1_R5_R8_WINDOWED_FFT_TRANSPORT */
async function auraLoadRealAudioAnalysis(id,position=null){
 id=String(id||"");
 if(!id)return;

 const now=Date.now();
 if(state.__analysisLoadingId===id){
  const age=now-Number(state.__analysisLoadingAt||0);
  if(age>0&&age<5000)return;
  state.__analysisLoadingId="";
  state.__analysisLoadingAt=0
 }

 let pos=Number(position);
 if(!Number.isFinite(pos)){
  try{pos=auraProjectedVlcPosition(performance.now())}
  catch(_e){pos=Number(state.timeline?.pos||0)}
 }
 pos=Math.max(0,Number(pos||0));

 state.__analysisLoadingId=id;
 state.__analysisLoadingAt=now;
 const token=(state.__analysisToken||0)+1;
 state.__analysisToken=token;
 auraSetVisualizerMode("analyzing");

 try{
  const d=await api("/analysis/window","POST",{id,position:pos,before:1.5,after:8.5});
  if(token!==state.__analysisToken)return;
  const a=d?.analysis||{};

  if(a.available&&Array.isArray(a.frames)&&a.frames.length&&Number(a.spectrum_bands||0)===38){
   state.realAudioAnalysis=a;
   state.__analysisLoadedId=id;
   state.__analysisLoadingId="";
   state.__analysisLoadingAt=0;
   state.__analysisRetryAt=0;
   state.__analysisLastError="";
   state.__vizClock=null;
   state.__vizCanvasSmooth=null;
   state.__vizCanvasNow=0;
   state.__vizAdaptiveGain=1;
   auraSetVisualizerMode("ready")
  }else{
   state.realAudioAnalysis=null;
   state.__analysisLoadingId="";
   state.__analysisLoadingAt=0;
   state.__analysisRetryAt=Date.now()+700;
   state.__analysisLastError=String(a?.reason||"window_unavailable");
   auraSetVisualizerMode("unavailable")
  }
 }catch(_e){
  if(token!==state.__analysisToken)return;
  state.realAudioAnalysis=null;
  state.__analysisLoadingId="";
  state.__analysisLoadingAt=0;
  state.__analysisRetryAt=Date.now()+700;
  state.__analysisLastError=String(_e?.message||_e||"window_fetch_error");
  auraSetVisualizerMode("unavailable")
 }
}

const auraBasePlaySelectedUi6R1=playSelected;
playSelected=async function(){
 const id=String(current()?.id||"");
 const result=await auraBasePlaySelectedUi6R1();
 if(id)setTimeout(()=>auraLoadRealAudioAnalysis(id),60);
 return result
};
const auraBaseDecorateLibraryUi6R1=auraDecorateLibrary;
auraDecorateLibrary=function(){
 auraBaseDecorateLibraryUi6R1();
 auraSetVisualizerMode(state.realAudioAnalysis?.available?"ready":"analyzing")
};
if(state.realVisualizerTimer){
 clearInterval(state.realVisualizerTimer);
 state.realVisualizerTimer=null
}
if(!state.realVisualizerRaf){
 const auraVisualizerLoop=(now)=>{
  auraVisualizerFrame(now);
  state.realVisualizerRaf=requestAnimationFrame(auraVisualizerLoop)
 };
 state.realVisualizerRaf=requestAnimationFrame(auraVisualizerLoop)
}
setTimeout(()=>{
 const s=state.libraryState?.last_played_id||"";
 if(s&&state.playing)auraLoadRealAudioAnalysis(s)
},600);

/* AURA_M180_UI6_R2_GLOBAL_MINIPLAYER */
function auraMiniFmt(sec){
 sec=Math.max(0,Math.floor(Number(sec)||0));
 const m=Math.floor(sec/60),s=sec%60;
 return `${m}:${String(s).padStart(2,"0")}`
}
function auraEnsureGlobalMiniPlayer(){
 let mini=document.getElementById("aura-global-mini-player-v180");
 if(mini)return mini;

 mini=document.createElement("div");
 mini.id="aura-global-mini-player-v180";
 mini.innerHTML=`
  <div id="aura-global-mini-cover-v180"></div>
  <div class="aura-global-mini-copy">
   <div id="aura-global-mini-title-v180">AURA Music</div>
   <div id="aura-global-mini-meta-v180">Lecteur local</div>
   <div id="aura-global-mini-state-v180">VLC</div>
  </div>
  <div class="aura-global-mini-actions">
   <button class="aura-global-mini-btn" id="aura-global-mini-prev-v180" title="Précédent">◀</button>
   <button class="aura-global-mini-btn" id="aura-global-mini-toggle-v180" title="Lecture / Pause">▶</button>
   <button class="aura-global-mini-btn" id="aura-global-mini-next-v180" title="Suivant">▶</button>
  </div>
  <div id="aura-global-mini-progress-v180"><div id="aura-global-mini-progress-fill-v180"></div></div>`;

 document.body.appendChild(mini);

 const command=async(action)=>{
  try{
   await api("/media/command","POST",{action});
   setTimeout(auraRefreshGlobalMiniPlayer,120)
  }catch(e){
   toast(`Commande média impossible • ${e.message}`)
  }
 };
 document.getElementById("aura-global-mini-prev-v180").onclick=()=>command("previous");
 document.getElementById("aura-global-mini-toggle-v180").onclick=()=>command("play_pause");
 document.getElementById("aura-global-mini-next-v180").onclick=()=>command("next");
 return mini
}
function auraMiniCurrentItem(id){
 id=String(id||"");
 if(!id)return null;
 return (state.items||[]).find(x=>String(x.id||"")===id)||null
}
async function auraRefreshGlobalMiniPlayer(){
 const mini=auraEnsureGlobalMiniPlayer();
 if(!mini)return;

 try{
  const s=await api("/status");
  state.__miniStatus=s||{};

  const id=String(s?.current_id||"");
  const active=!!s?.playing||!!s?.paused;
  const hasMedia=!!id&&Number(s?.duration_seconds||0)>0;

  const main=document.getElementById("aura-music-player-v180");
  const mainVisible=!!(main&&main.offsetParent!==null&&getComputedStyle(main).display!=="none");
  mini.classList.toggle("main-open",mainVisible);
  mini.classList.toggle("show",hasMedia);

  if(!hasMedia)return;

  let item=auraMiniCurrentItem(id);
  if(!item&&String(state.libraryState?.last_played_id||"")===id){
   item=(state.items||[]).find(x=>String(x.id||"")===id)||null
  }

  const title=String(item?.title||s?.current_title||"Morceau");
  const artist=String(item?.artist||"");
  const album=String(item?.album||"");
  const pos=Math.max(0,Number(s?.position_seconds||0));
  const dur=Math.max(0,Number(s?.duration_seconds||0));
  const pct=dur>0?Math.max(0,Math.min(100,pos/dur*100)):0;

  document.getElementById("aura-global-mini-title-v180").textContent=title;
  document.getElementById("aura-global-mini-meta-v180").textContent=[artist,album].filter(Boolean).join(" • ")||"AURA Music";
  document.getElementById("aura-global-mini-state-v180").textContent=
   `${s?.paused?"PAUSE":active?"LECTURE":"PRÊT"} • ${auraMiniFmt(pos)} / ${auraMiniFmt(dur)}`;
  document.getElementById("aura-global-mini-toggle-v180").textContent=
   (s?.playing&&!s?.paused)?"Ⅱ":"▶";
  document.getElementById("aura-global-mini-progress-fill-v180").style.width=`${pct.toFixed(2)}%`;
  const miniProgress=document.getElementById("aura-global-mini-progress-v180");
  if(miniProgress){
   miniProgress.style.setProperty("--aura-mini-progress",`${pct.toFixed(2)}%`);
   miniProgress.setAttribute("aria-valuemax",String(Math.round(dur)));
   miniProgress.setAttribute("aria-valuenow",String(Math.round(pos)));
   miniProgress.setAttribute("aria-valuetext",`${auraMiniFmt(pos)} sur ${auraMiniFmt(dur)}`);
   miniProgress.title=`${auraMiniFmt(pos)} / ${auraMiniFmt(dur)} • glisser pour déplacer`;
  }

  const cover=document.getElementById("aura-global-mini-cover-v180");
  if(item?.cover_data_uri){
   cover.style.backgroundImage=`url("${String(item.cover_data_uri).replace(/"/g,"%22")}")`
  }else{
   cover.style.backgroundImage=""
  }
 }catch(_e){}
}

/* AURA_M180_UI6_R5_GLOBAL_MINIPLAYER_INTERACTIVE_SCRUB */
function auraMiniSeekRatioFromEvent(ev,bar){
 const r=bar.getBoundingClientRect();
 if(!r.width)return 0;
 return Math.max(0,Math.min(1,(Number(ev.clientX)-r.left)/r.width))
}
function auraMiniSeekSecondsFromRatio(ratio){
 const s=state.__miniStatus||{};
 const dur=Math.max(0,Number(s.duration_seconds||0));
 return dur>0?ratio*dur:0
}
function auraMiniRenderSeekPreview(bar,seconds){
 const s=state.__miniStatus||{};
 const dur=Math.max(0,Number(s.duration_seconds||0));
 if(dur<=0)return;
 const pct=Math.max(0,Math.min(100,seconds/dur*100));
 const fill=document.getElementById("aura-global-mini-progress-fill-v180");
 if(fill)fill.style.width=`${pct.toFixed(2)}%`;
 bar.dataset.preview=auraMiniFmt(seconds);
 bar.classList.add("scrub-preview")
}
function auraMiniClearSeekPreview(bar){
 bar.classList.remove("scrub-preview");
 delete bar.dataset.preview
}
async function auraMiniCommitSeek(seconds){
 const s=state.__miniStatus||{};
 const dur=Math.max(0,Number(s.duration_seconds||0));
 if(dur<=0)return;
 const target=Math.max(0,Math.min(dur,Number(seconds)||0));
 try{
  await api("/media/seek","POST",{position:target});
  if(state.__miniStatus)state.__miniStatus.position_seconds=target;
  setTimeout(auraRefreshGlobalMiniPlayer,90)
 }catch(e){
  toast(`Déplacement impossible • ${e.message}`)
 }
}
function auraInstallMiniScrub(){
 const bar=document.getElementById("aura-global-mini-progress-v180");
 if(!bar||bar.dataset.scrubReady==="1")return;
 bar.dataset.scrubReady="1";
 bar.tabIndex=0;
 bar.setAttribute("role","slider");
 bar.setAttribute("aria-label","Position de lecture");
 bar.setAttribute("aria-valuemin","0");

 let dragging=false;

 bar.addEventListener("pointerdown",ev=>{
  const s=state.__miniStatus||{};
  if(Number(s.duration_seconds||0)<=0)return;
  dragging=true;
  try{bar.setPointerCapture(ev.pointerId)}catch(_e){}
  const sec=auraMiniSeekSecondsFromRatio(auraMiniSeekRatioFromEvent(ev,bar));
  auraMiniRenderSeekPreview(bar,sec);
  ev.preventDefault()
 });

 bar.addEventListener("pointermove",ev=>{
  if(!dragging && ev.pointerType!=="mouse")return;
  const s=state.__miniStatus||{};
  if(Number(s.duration_seconds||0)<=0)return;
  const sec=auraMiniSeekSecondsFromRatio(auraMiniSeekRatioFromEvent(ev,bar));
  if(dragging||ev.pointerType==="mouse")auraMiniRenderSeekPreview(bar,sec)
 });

 const commit=ev=>{
  if(!dragging)return;
  dragging=false;
  const sec=auraMiniSeekSecondsFromRatio(auraMiniSeekRatioFromEvent(ev,bar));
  auraMiniRenderSeekPreview(bar,sec);
  auraMiniCommitSeek(sec);
  setTimeout(()=>auraMiniClearSeekPreview(bar),500);
  try{bar.releasePointerCapture(ev.pointerId)}catch(_e){}
 };

 bar.addEventListener("pointerup",commit);
 bar.addEventListener("pointercancel",ev=>{
  dragging=false;
  auraMiniClearSeekPreview(bar);
  try{bar.releasePointerCapture(ev.pointerId)}catch(_e){}
  auraRefreshGlobalMiniPlayer()
 });
 bar.addEventListener("pointerleave",()=>{
  if(!dragging)auraMiniClearSeekPreview(bar)
 });

 bar.addEventListener("keydown",ev=>{
  const s=state.__miniStatus||{};
  const dur=Math.max(0,Number(s.duration_seconds||0));
  const pos=Math.max(0,Number(s.position_seconds||0));
  if(dur<=0)return;
  let target=null;
  if(ev.key==="ArrowLeft")target=Math.max(0,pos-5);
  else if(ev.key==="ArrowRight")target=Math.min(dur,pos+5);
  else if(ev.key==="Home")target=0;
  else if(ev.key==="End")target=dur;
  if(target===null)return;
  ev.preventDefault();
  auraMiniRenderSeekPreview(bar,target);
  auraMiniCommitSeek(target);
  setTimeout(()=>auraMiniClearSeekPreview(bar),500)
 })
}


/* AURA_M180_UI6_R6_EXPANDED_MINIPLAYER_QUEUE_FAVORITES */
function auraMiniR6FavoriteIds(){
 const lib=state.libraryState||{};
 const ids=new Set();
 const add=v=>{
  if(v===null||v===undefined)return;
  if(typeof v==="string"||typeof v==="number"){ids.add(String(v));return}
  if(typeof v==="object"){
   const id=v.id??v.item_id??v.track_id;
   if(id!==undefined&&id!==null)ids.add(String(id))
  }
 };

 const candidates=[
  lib.favorite_ids,lib.favourite_ids,lib.favorites,lib.favourites,
  lib.starred_ids,lib.starred
 ];
 for(const c of candidates){
  if(Array.isArray(c)){for(const v of c)add(v)}
  else if(c&&typeof c==="object"){
   for(const [k,v] of Object.entries(c)){
    if(v===true||v===1||v==="1"||v==="true")ids.add(String(k));
    else add(v)
   }
  }
 }
 for(const item of (state.items||[])){
  if(item?.favorite===true||item?.favourite===true||item?.is_favorite===true||
     item?.is_favourite===true||item?.starred===true){
   add(item)
  }
 }
 return ids
}
function auraMiniR6CurrentIndex(){
 const id=String(state.__miniStatus?.current_id||"");
 return (state.items||[]).findIndex(x=>String(x?.id||"")===id)
}
function auraMiniR6QueueItems(){
 const items=state.items||[];
 if(!items.length)return [];
 const idx=auraMiniR6CurrentIndex();
 if(idx<0)return items.slice(0,8);
 const out=[];
 for(let off=0;off<Math.min(8,items.length);off++){
  out.push(items[(idx+off)%items.length])
 }
 return out
}
function auraMiniR6FavoriteItems(){
 const ids=auraMiniR6FavoriteIds();
 return (state.items||[]).filter(x=>ids.has(String(x?.id||""))).slice(0,12)
}
function auraMiniR6Esc(v){
 return String(v??"")
  .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
  .replace(/"/g,"&quot;").replace(/'/g,"&#39;")
}
function auraMiniR6Row(item,isCurrent=false){
 const id=auraMiniR6Esc(item?.id||"");
 const title=auraMiniR6Esc(item?.title||"Morceau");
 const artist=auraMiniR6Esc(item?.artist||"");
 return `<button class="aura-mini-r6-row${isCurrent?" current":""}" data-mini-play-id="${id}" type="button">
   <span class="aura-mini-r6-row-dot">${isCurrent?"▶":"•"}</span>
   <span class="aura-mini-r6-row-copy">
    <strong>${title}</strong>
    <small>${artist||"AURA Music"}</small>
   </span>
  </button>`
}
function auraMiniR6Render(){
 const mini=document.getElementById("aura-global-mini-player-v180");
 const drawer=document.getElementById("aura-mini-r6-drawer");
 if(!mini||!drawer)return;

 const tab=drawer.dataset.tab||"queue";
 const currentId=String(state.__miniStatus?.current_id||"");
 const list=tab==="favorites"?auraMiniR6FavoriteItems():auraMiniR6QueueItems();

 const queueBtn=document.getElementById("aura-mini-r6-tab-queue");
 const favBtn=document.getElementById("aura-mini-r6-tab-favorites");
 if(queueBtn)queueBtn.classList.toggle("active",tab==="queue");
 if(favBtn)favBtn.classList.toggle("active",tab==="favorites");

 const body=document.getElementById("aura-mini-r6-list");
 if(!body)return;

 if(!list.length){
  body.innerHTML=`<div class="aura-mini-r6-empty">${
   tab==="favorites"?"Aucun favori détecté dans la bibliothèque.":"File d’attente vide."
  }</div>`;
 }else{
  body.innerHTML=list.map(x=>auraMiniR6Row(x,String(x?.id||"")===currentId)).join("")
 }

 for(const row of body.querySelectorAll("[data-mini-play-id]")){
  row.onclick=async()=>{
   const id=String(row.dataset.miniPlayId||"");
   if(!id)return;
   try{
    const res=await api("/media/play-id","POST",{id});
    if(!res?.ok)throw new Error(res?.reason||"play_id_failed");
    setTimeout(auraRefreshGlobalMiniPlayer,110);
    setTimeout(auraMiniR6Render,160)
   }catch(e){
    toast(`Lecture impossible • ${e.message}`)
   }
  }
 }
}
function auraMiniR6SetExpanded(expanded){
 const mini=document.getElementById("aura-global-mini-player-v180");
 const drawer=document.getElementById("aura-mini-r6-drawer");
 const btn=document.getElementById("aura-mini-r6-expand");
 if(!mini||!drawer||!btn)return;
 mini.classList.toggle("r6-expanded",!!expanded);
 drawer.hidden=!expanded;
 btn.textContent=expanded?"⌄":"⌃";
 btn.title=expanded?"Réduire le mini-player":"Développer le mini-player";
 try{localStorage.setItem("aura_mini_r6_expanded",expanded?"1":"0")}catch(_e){}
 if(expanded)auraMiniR6Render()
}
function auraInstallMiniR6(){
 const mini=auraEnsureGlobalMiniPlayer();
 if(!mini||mini.dataset.r6Ready==="1")return;
 mini.dataset.r6Ready="1";

 const actions=mini.querySelector(".aura-global-mini-actions");
 if(actions&&!document.getElementById("aura-mini-r6-expand")){
  const expand=document.createElement("button");
  expand.className="aura-global-mini-btn aura-mini-r6-expand";
  expand.id="aura-mini-r6-expand";
  expand.type="button";
  expand.textContent="⌃";
  expand.title="Développer le mini-player";
  actions.appendChild(expand);
  expand.onclick=()=>auraMiniR6SetExpanded(!mini.classList.contains("r6-expanded"))
 }

 if(!document.getElementById("aura-mini-r6-drawer")){
  const drawer=document.createElement("div");
  drawer.id="aura-mini-r6-drawer";
  drawer.className="aura-mini-r6-drawer";
  drawer.dataset.tab="queue";
  drawer.hidden=true;
  drawer.innerHTML=`
   <div class="aura-mini-r6-tabs">
    <button id="aura-mini-r6-tab-queue" class="aura-mini-r6-tab active" type="button">À suivre</button>
    <button id="aura-mini-r6-tab-favorites" class="aura-mini-r6-tab" type="button">Favoris</button>
   </div>
   <div id="aura-mini-r6-list" class="aura-mini-r6-list"></div>`;
  mini.appendChild(drawer);

  document.getElementById("aura-mini-r6-tab-queue").onclick=()=>{
   drawer.dataset.tab="queue";auraMiniR6Render()
  };
  document.getElementById("aura-mini-r6-tab-favorites").onclick=()=>{
   drawer.dataset.tab="favorites";auraMiniR6Render()
  }
 }

 let expanded=false;
 try{expanded=localStorage.getItem("aura_mini_r6_expanded")==="1"}catch(_e){}
 auraMiniR6SetExpanded(expanded);

 state.__miniR6Timer=setInterval(()=>{
  if(mini.classList.contains("r6-expanded"))auraMiniR6Render()
 },1400)
}
setTimeout(auraInstallMiniR6,850);


/* AURA_M180_UI6_R7_DRAGGABLE_GLOBAL_MINIPLAYER */
function auraMiniR7ViewportClamp(x,y,mini){
 const margin=8;
 const r=mini.getBoundingClientRect();
 const w=Math.max(220,r.width||mini.offsetWidth||340);
 const h=Math.max(70,r.height||mini.offsetHeight||72);
 const maxX=Math.max(margin,window.innerWidth-w-margin);
 const maxY=Math.max(margin,window.innerHeight-h-margin);
 return {
  x:Math.max(margin,Math.min(maxX,Number(x)||margin)),
  y:Math.max(margin,Math.min(maxY,Number(y)||margin))
 }
}
function auraMiniR7ApplyPosition(x,y,save=true){
 const mini=document.getElementById("aura-global-mini-player-v180");
 if(!mini)return;
 const p=auraMiniR7ViewportClamp(x,y,mini);
 mini.style.left=`${Math.round(p.x)}px`;
 mini.style.top=`${Math.round(p.y)}px`;
 mini.style.right="auto";
 mini.style.bottom="auto";
 mini.dataset.dragged="1";
 if(save){
  try{
   localStorage.setItem("aura_mini_r7_position",JSON.stringify({
    x:Math.round(p.x),y:Math.round(p.y)
   }))
  }catch(_e){}
 }
}
function auraMiniR7ResetPosition(){
 const mini=document.getElementById("aura-global-mini-player-v180");
 if(!mini)return;
 mini.style.left="";
 mini.style.top="";
 mini.style.right="";
 mini.style.bottom="";
 delete mini.dataset.dragged;
 try{localStorage.removeItem("aura_mini_r7_position")}catch(_e){}
}
function auraMiniR7RestorePosition(){
 const mini=document.getElementById("aura-global-mini-player-v180");
 if(!mini)return;
 let saved=null;
 try{
  const raw=localStorage.getItem("aura_mini_r7_position");
  if(raw)saved=JSON.parse(raw)
 }catch(_e){}
 if(saved&&Number.isFinite(Number(saved.x))&&Number.isFinite(Number(saved.y))){
  requestAnimationFrame(()=>auraMiniR7ApplyPosition(saved.x,saved.y,false))
 }
}
function auraMiniR7InteractiveTarget(target){
 if(!target)return false;
 return !!target.closest(
  "button,input,select,textarea,a,[role='slider'],"+
  "#aura-global-mini-progress-v180,#aura-mini-r6-drawer,"+
  "[data-mini-play-id]"
 )
}
function auraInstallMiniR7Drag(){
 const mini=auraEnsureGlobalMiniPlayer();
 if(!mini||mini.dataset.r7DragReady==="1")return;
 mini.dataset.r7DragReady="1";

 let dragging=false;
 let pointerId=null;
 let startX=0,startY=0,startLeft=0,startTop=0;

 const begin=ev=>{
  if(ev.button!==undefined&&ev.button!==0)return;
  if(auraMiniR7InteractiveTarget(ev.target))return;

  const r=mini.getBoundingClientRect();
  dragging=true;
  pointerId=ev.pointerId;
  startX=ev.clientX;
  startY=ev.clientY;
  startLeft=r.left;
  startTop=r.top;
  mini.classList.add("r7-dragging");

  try{mini.setPointerCapture(pointerId)}catch(_e){}
  ev.preventDefault()
 };

 const move=ev=>{
  if(!dragging||ev.pointerId!==pointerId)return;
  const x=startLeft+(ev.clientX-startX);
  const y=startTop+(ev.clientY-startY);
  auraMiniR7ApplyPosition(x,y,false);
  ev.preventDefault()
 };

 const end=ev=>{
  if(!dragging||ev.pointerId!==pointerId)return;
  dragging=false;
  const r=mini.getBoundingClientRect();
  auraMiniR7ApplyPosition(r.left,r.top,true);
  if(typeof auraMiniR8SnapAfterDrag==="function"){
   setTimeout(()=>auraMiniR8SnapAfterDrag(mini),0)
  }
  mini.classList.remove("r7-dragging");
  try{mini.releasePointerCapture(pointerId)}catch(_e){}
  pointerId=null;
  ev.preventDefault()
 };

 mini.addEventListener("pointerdown",begin);
 mini.addEventListener("pointermove",move);
 mini.addEventListener("pointerup",end);
 mini.addEventListener("pointercancel",end);

 mini.addEventListener("dblclick",ev=>{
  if(auraMiniR7InteractiveTarget(ev.target))return;
  auraMiniR7ResetPosition()
 });

 window.addEventListener("resize",()=>{
  if(mini.dataset.dragged!=="1")return;
  const r=mini.getBoundingClientRect();
  auraMiniR7ApplyPosition(r.left,r.top,true)
 });

 auraMiniR7RestorePosition()
}
setTimeout(auraInstallMiniR7Drag,950);


/* AURA_M180_UI6_R8_INTELLIGENT_SNAP_ANCHOR_MINIPLAYER */
const AURA_MINI_R8_MARGIN=8;
const AURA_MINI_R8_SNAP_THRESHOLD=72;

function auraMiniR8ReadAnchor(){
 try{
  const raw=localStorage.getItem("aura_mini_r8_anchor");
  return raw?JSON.parse(raw):null
 }catch(_e){return null}
}
function auraMiniR8WriteAnchor(data){
 try{
  if(data)localStorage.setItem("aura_mini_r8_anchor",JSON.stringify(data));
  else localStorage.removeItem("aura_mini_r8_anchor")
 }catch(_e){}
}
function auraMiniR8Geometry(mini){
 const r=mini.getBoundingClientRect();
 const margin=AURA_MINI_R8_MARGIN;
 const availX=Math.max(0,window.innerWidth-r.width-margin*2);
 const availY=Math.max(0,window.innerHeight-r.height-margin*2);
 return {r,margin,availX,availY}
}
function auraMiniR8DetectAnchor(mini){
 const {r,margin}=auraMiniR8Geometry(mini);
 const d={
  left:Math.abs(r.left-margin),
  right:Math.abs((window.innerWidth-margin)-r.right),
  top:Math.abs(r.top-margin),
  bottom:Math.abs((window.innerHeight-margin)-r.bottom)
 };
 const h=d.left<=d.right?"left":"right";
 const v=d.top<=d.bottom?"top":"bottom";
 const nearH=d[h]<=AURA_MINI_R8_SNAP_THRESHOLD;
 const nearV=d[v]<=AURA_MINI_R8_SNAP_THRESHOLD;

 if(nearH&&nearV)return `${v}-${h}`;
 if(nearH)return h;
 if(nearV)return v;
 return ""
}
function auraMiniR8AnchorPayload(anchor,mini){
 const {r,margin,availX,availY}=auraMiniR8Geometry(mini);
 let cross=0;
 if(anchor==="left"||anchor==="right"){
  cross=availY>0?(r.top-margin)/availY:0;
 }else if(anchor==="top"||anchor==="bottom"){
  cross=availX>0?(r.left-margin)/availX:0;
 }
 return {
  anchor,
  cross:Math.max(0,Math.min(1,Number(cross)||0))
 }
}
function auraMiniR8Target(anchorData,mini){
 const {r,margin,availX,availY}=auraMiniR8Geometry(mini);
 const a=String(anchorData?.anchor||"");
 const cross=Math.max(0,Math.min(1,Number(anchorData?.cross)||0));
 let x=r.left,y=r.top;

 if(a.includes("left"))x=margin;
 else if(a.includes("right"))x=window.innerWidth-r.width-margin;
 else if(a==="top"||a==="bottom")x=margin+(availX*cross);

 if(a.includes("top"))y=margin;
 else if(a.includes("bottom"))y=window.innerHeight-r.height-margin;
 else if(a==="left"||a==="right")y=margin+(availY*cross);

 return auraMiniR7ViewportClamp(x,y,mini)
}
function auraMiniR8ApplyAnchor(anchorData,animate=true){
 const mini=document.getElementById("aura-global-mini-player-v180");
 if(!mini||!anchorData?.anchor)return;
 const p=auraMiniR8Target(anchorData,mini);
 if(animate)mini.classList.add("r8-snapping");
 auraMiniR7ApplyPosition(p.x,p.y,true);
 if(animate)setTimeout(()=>mini.classList.remove("r8-snapping"),190)
}
function auraMiniR8SnapAfterDrag(mini){
 if(!mini)return;
 const anchor=auraMiniR8DetectAnchor(mini);
 if(!anchor){
  auraMiniR8WriteAnchor(null);
  mini.classList.remove("r8-anchored");
  delete mini.dataset.r8Anchor;
  return
 }
 const data=auraMiniR8AnchorPayload(anchor,mini);
 auraMiniR8WriteAnchor(data);
 mini.dataset.r8Anchor=anchor;
 mini.classList.add("r8-anchored");
 auraMiniR8ApplyAnchor(data,true)
}
function auraMiniR8RestoreAnchor(){
 const mini=document.getElementById("aura-global-mini-player-v180");
 if(!mini)return;
 const data=auraMiniR8ReadAnchor();
 if(!data?.anchor)return;
 mini.dataset.r8Anchor=String(data.anchor);
 mini.classList.add("r8-anchored");
 requestAnimationFrame(()=>auraMiniR8ApplyAnchor(data,false))
}
function auraMiniR8ResetBottomRight(){
 const mini=document.getElementById("aura-global-mini-player-v180");
 if(!mini)return;
 const data={anchor:"bottom-right",cross:1};
 auraMiniR8WriteAnchor(data);
 mini.dataset.r8Anchor=data.anchor;
 mini.classList.add("r8-anchored");
 auraMiniR8ApplyAnchor(data,true)
}
function auraInstallMiniR8Snap(){
 const mini=auraEnsureGlobalMiniPlayer();
 if(!mini||mini.dataset.r8SnapReady==="1")return;
 mini.dataset.r8SnapReady="1";

 auraMiniR8RestoreAnchor();

 let resizeRaf=0;
 const reflow=()=>{
  if(mini.classList.contains("r7-dragging"))return;
  const data=auraMiniR8ReadAnchor();
  if(!data?.anchor)return;
  cancelAnimationFrame(resizeRaf);
  resizeRaf=requestAnimationFrame(()=>auraMiniR8ApplyAnchor(data,false))
 };

 window.addEventListener("resize",reflow);

 if(typeof ResizeObserver==="function"){
  const ro=new ResizeObserver(()=>reflow());
  ro.observe(mini);
  state.__miniR8ResizeObserver=ro
 }

 mini.addEventListener("dblclick",ev=>{
  if(auraMiniR7InteractiveTarget(ev.target))return;
  setTimeout(auraMiniR8ResetBottomRight,0)
 })
}
setTimeout(auraInstallMiniR8Snap,1100);


/* AURA_M180_UI6_R9_PINNED_AUTOHIDE_MINIPLAYER */
const AURA_MINI_R9_IDLE_MS=3600;

function auraMiniR9ReadBool(key,def){
 try{
  const v=localStorage.getItem(key);
  if(v===null)return !!def;
  return v==="1"
 }catch(_e){return !!def}
}
function auraMiniR9WriteBool(key,v){
 try{localStorage.setItem(key,v?"1":"0")}catch(_e){}
}
function auraMiniR9AnchorSide(){
 const mini=document.getElementById("aura-global-mini-player-v180");
 if(!mini)return "";
 const a=String(mini.dataset.r8Anchor||auraMiniR8ReadAnchor()?.anchor||"");
 if(!a)return "";
 if(a.includes("left"))return "left";
 if(a.includes("right"))return "right";
 if(a==="top")return "top";
 if(a==="bottom")return "bottom";
 return ""
}
function auraMiniR9ClearHide(){
 const mini=document.getElementById("aura-global-mini-player-v180");
 if(!mini)return;
 mini.classList.remove("r9-hide-left","r9-hide-right","r9-hide-top","r9-hide-bottom","r9-autohidden")
}
function auraMiniR9CanHide(){
 const mini=document.getElementById("aura-global-mini-player-v180");
 if(!mini)return false;
 if(!auraMiniR9ReadBool("aura_mini_r9_autohide",false))return false;
 if(!auraMiniR9AnchorSide())return false;
 if(mini.matches(":hover")||mini.matches(":focus-within"))return false;
 if(mini.classList.contains("r7-dragging"))return false;
 if(mini.classList.contains("r6-expanded"))return false;
 if(document.getElementById("aura-global-mini-progress-v180")?.classList.contains("scrub-preview"))return false;
 const s=state.__miniStatus||{};
 if(!s.playing)return false;
 return true
}
function auraMiniR9ApplyHide(){
 const mini=document.getElementById("aura-global-mini-player-v180");
 if(!mini||!auraMiniR9CanHide())return;
 const side=auraMiniR9AnchorSide();
 auraMiniR9ClearHide();
 if(!side)return;
 mini.classList.add(`r9-hide-${side}`,"r9-autohidden")
}
function auraMiniR9Touch(show=true){
 state.__miniR9LastInteraction=Date.now();
 if(show)auraMiniR9ClearHide()
}
function auraMiniR9SetPinned(v){
 const mini=document.getElementById("aura-global-mini-player-v180");
 const btn=document.getElementById("aura-mini-r9-pin");
 if(!mini)return;
 const on=!!v;
 mini.classList.toggle("r9-pinned",on);
 auraMiniR9WriteBool("aura_mini_r9_pinned",on);
 if(btn){
  btn.classList.toggle("active",on);
  btn.textContent=on?"◆":"◇";
  btn.title=on?"Mini-player prioritaire dans AURA":"Épingler le mini-player au-dessus de l’interface";
  btn.setAttribute("aria-pressed",on?"true":"false")
 }
}
function auraMiniR9SetAutoHide(v){
 const btn=document.getElementById("aura-mini-r9-autohide");
 const on=!!v;
 auraMiniR9WriteBool("aura_mini_r9_autohide",on);
 if(btn){
  btn.classList.toggle("active",on);
  btn.textContent=on?"◐":"○";
  btn.title=on?"Masquage intelligent activé":"Activer le masquage intelligent";
  btn.setAttribute("aria-pressed",on?"true":"false")
 }
 auraMiniR9Touch(true)
}
function auraMiniR9InstallButtons(mini){
 const actions=mini.querySelector(".aura-global-mini-actions");
 if(!actions)return;

 if(!document.getElementById("aura-mini-r9-pin")){
  const pin=document.createElement("button");
  pin.id="aura-mini-r9-pin";
  pin.className="aura-global-mini-btn aura-mini-r9-btn";
  pin.type="button";
  pin.setAttribute("aria-label","Épingler le mini-player");
  actions.appendChild(pin);
  pin.onclick=ev=>{
   ev.stopPropagation();
   auraMiniR9SetPinned(!mini.classList.contains("r9-pinned"));
   auraMiniR9Touch(true)
  }
 }

 if(!document.getElementById("aura-mini-r9-autohide")){
  const hide=document.createElement("button");
  hide.id="aura-mini-r9-autohide";
  hide.className="aura-global-mini-btn aura-mini-r9-btn";
  hide.type="button";
  hide.setAttribute("aria-label","Masquage intelligent");
  actions.appendChild(hide);
  hide.onclick=ev=>{
   ev.stopPropagation();
   auraMiniR9SetAutoHide(!auraMiniR9ReadBool("aura_mini_r9_autohide",false))
  }
 }

 auraMiniR9SetPinned(auraMiniR9ReadBool("aura_mini_r9_pinned",true));
 auraMiniR9SetAutoHide(auraMiniR9ReadBool("aura_mini_r9_autohide",false))
}
function auraInstallMiniR9(){
 const mini=auraEnsureGlobalMiniPlayer();
 if(!mini||mini.dataset.r9Ready==="1")return;
 mini.dataset.r9Ready="1";
 auraMiniR9InstallButtons(mini);
 auraMiniR9Touch(true);

 const reveal=()=>auraMiniR9Touch(true);
 mini.addEventListener("pointerenter",reveal);
 mini.addEventListener("pointerdown",reveal);
 mini.addEventListener("focusin",reveal);
 mini.addEventListener("wheel",reveal,{passive:true});

 mini.addEventListener("pointerleave",()=>{
  state.__miniR9LastInteraction=Date.now()
 });

 let lastId=String(state.__miniStatus?.current_id||"");
 state.__miniR9Timer=setInterval(()=>{
  const id=String(state.__miniStatus?.current_id||"");
  if(id!==lastId){
   lastId=id;
   auraMiniR9Touch(true)
  }

  if(!auraMiniR9ReadBool("aura_mini_r9_autohide",false)){
   auraMiniR9ClearHide();
   return
  }

  const idle=Date.now()-Number(state.__miniR9LastInteraction||Date.now());
  if(idle>=AURA_MINI_R9_IDLE_MS)auraMiniR9ApplyHide();
  else auraMiniR9ClearHide()
 },320)
}
setTimeout(auraInstallMiniR9,1250);

function auraInstallGlobalMiniPlayer(){
 if(state.__globalMiniInstalled)return;
 state.__globalMiniInstalled=true;
 auraEnsureGlobalMiniPlayer();
  auraInstallMiniScrub();
 auraRefreshGlobalMiniPlayer();
 state.__globalMiniTimer=setInterval(auraRefreshGlobalMiniPlayer,700)
}
setTimeout(auraInstallGlobalMiniPlayer,650);

function install(){
 const root=document.getElementById("aura-music-player-v180");
 auraEnsureQueueModeControls();
 document.getElementById("aura-music-close-v180").onclick=()=>root.classList.remove("open");
 document.getElementById("aura-music-refresh-v180").onclick=async()=>{runtime("busy","MÉTADONNÉES • ANALYSE");try{const d=await api("/metadata/refresh","POST",{});state.items=Array.isArray(d.playlist?.items)?d.playlist.items:state.items;render();runtime("ok","MÉTADONNÉES • ACTUALISÉES");toast("Métadonnées et pochettes actualisées")}catch(e){runtime("error","MÉTADONNÉES • ÉCHEC");toast(`Actualisation impossible • ${e.message}`)}};
 document.getElementById("aura-music-play-v180").onclick=togglePlay;
 document.getElementById("aura-music-stop-v180").onclick=stop;
 document.getElementById("aura-music-next-v180").onclick=next;
 document.getElementById("aura-music-prev-v180").onclick=previous;
 document.getElementById("aura-music-pick-track-v180").onclick=()=>pick("track");
 document.getElementById("aura-music-pick-playlist-v180").onclick=()=>pick("playlist");
 document.getElementById("aura-music-pick-folder-v180").onclick=()=>pick("folder");
 document.getElementById("aura-music-clear-v180").onclick=clearPlaylist;
 document.getElementById("aura-music-full-v180").onclick=()=>{state.fullList=!state.fullList;render()};
 document.getElementById("aura-music-mute-v180").onclick=async()=>{try{if(state.volume>0){state.__beforeMute=state.volume;await api("/control","POST",{action:"volume_percent",value:0})}else await api("/control","POST",{action:"volume_percent",value:state.__beforeMute||80});await pollStatus()}catch(e){toast(`Mute impossible • ${e.message}`)}};
 const volume=document.getElementById("aura-music-volume-v180");volume.oninput=()=>{state.volume=Number(volume.value);document.getElementById("aura-music-volume-label-v180").textContent=`${state.volume}%`};volume.onchange=()=>api("/control","POST",{action:"volume_percent",value:state.volume}).catch(e=>toast(`Volume impossible • ${e.message}`));
 const progress=document.getElementById("aura-music-progress-v180");progress.oninput=()=>{const pct=Number(progress.value)||0;const dur=Number(state.timeline.dur)||0;if(dur>0){const target=dur*pct/100;const now=document.getElementById("aura-music-current-time-v180");if(now)now.textContent=fmt(target)}};progress.onchange=async()=>{const pct=Number(progress.value)||0;const dur=Number(state.timeline.dur)||0;const target=dur>0?dur*pct/100:0;auraResetTimelineClock(target,dur);renderProjectedTimeline();try{await api("/control","POST",{action:"seek_percent",value:pct});setTimeout(pollStatus,80)}catch(e){toast(`Déplacement impossible • ${e.message}`)}};
 root.addEventListener("click",e=>{if(e.target===root)root.classList.remove("open")});
 document.addEventListener("keydown",e=>{if(!root.classList.contains("open"))return;if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="f"){e.preventDefault();document.getElementById("aura-music-library-search-v180")?.focus();return;}if(e.key==="Escape")root.classList.remove("open");if(e.code==="Space"&&!["INPUT","TEXTAREA"].includes(document.activeElement?.tagName)){e.preventDefault();togglePlay()}if(e.key==="ArrowRight"&&e.altKey)next();if(e.key==="ArrowLeft"&&e.altKey)previous()})
}
function replaceUi(){
 let root=document.getElementById("aura-music-player-v180");if(root)root.remove();root=document.createElement("div");root.id="aura-music-player-v180";
 const bars='<div class="aura-music-premium-visualizer">'+Array.from({length:38},()=>'<span></span>').join("")+'</div>';
 root.innerHTML=`<div class="aura-music-shell"><header class="aura-music-head"><div class="aura-music-brand"><div class="aura-music-logo">A</div><div><div class="aura-music-title">AURA - MUSIQUE</div><div class="aura-music-subtitle">PREMIUM LOCAL PLAYER</div></div></div><div class="aura-music-head-right"><div class="aura-music-status"><i></i>LOCAL • VLC BRIDGE</div><button class="aura-music-icon-btn" id="aura-music-close-v180">×</button></div></header><div class="aura-music-body"><section class="aura-music-main"><div class="aura-music-cover no-art" id="aura-music-cover-v180"><div class="aura-music-cover-badge" id="aura-music-cover-badge-v180">MEDIA</div>${bars}</div><div class="aura-music-meta"><div><div class="aura-music-track" id="aura-music-current-title-v180">Aucun média</div><div class="aura-music-artist" id="aura-music-current-artist-v180">Bibliothèque locale</div><div class="aura-music-runtime-line"><span class="aura-music-runtime-dot"></span><span id="aura-music-runtime-text-v180">VLC BRIDGE • CONNEXION</span></div><div class="aura-music-chips" id="aura-music-chips-v180"></div></div><button class="aura-music-icon-btn" id="aura-music-refresh-v180">↻</button></div><div class="aura-music-progress"><input id="aura-music-progress-v180" type="range" min="0" max="100" step="0.1" value="0"><div class="aura-music-time"><span id="aura-music-current-time-v180">0:00</span><span id="aura-music-total-v180">--:--</span></div></div><div><div class="aura-music-controls"><button class="aura-music-control" id="aura-music-stop-v180">■</button><button class="aura-music-control" id="aura-music-prev-v180">◀</button><button class="aura-music-play" id="aura-music-play-v180">▶</button><button class="aura-music-control" id="aura-music-next-v180">▶</button><button class="aura-music-control" id="aura-music-mute-v180">◌</button></div><div class="aura-music-volume"><span>VOL</span><input id="aura-music-volume-v180" type="range" min="0" max="100" step="1" value="80"><span id="aura-music-volume-label-v180">80%</span></div></div></section><aside class="aura-music-playlist"><div class="aura-music-playlist-head"><div><div class="aura-music-playlist-title">PLAYLISTE</div><div class="aura-music-playlist-count" id="aura-music-count-v180">0 morceau</div></div><button class="aura-music-clear-btn" id="aura-music-clear-v180">VIDER</button></div><div id="aura-music-list-v180"></div><div class="aura-music-pc-actions"><button class="aura-music-pc-btn" id="aura-music-pick-track-v180"><strong>+</strong>TITRE PC</button><button class="aura-music-pc-btn" id="aura-music-pick-playlist-v180"><strong>≡</strong>PLAYLISTE</button><button class="aura-music-pc-btn" id="aura-music-pick-folder-v180"><strong>DIR</strong>DOSSIER</button></div><button class="aura-music-footer-btn" id="aura-music-full-v180">VOIR PLAYLISTE COMPLÈTE</button></aside></div></div>`;
 document.body.appendChild(root);install();probe();loadPlaylist();startPoll()
}
function openMusic(){const root=document.getElementById("aura-music-player-v180");if(root){root.classList.add("open");probe();loadPlaylist();startPoll()}}
/* AURA R15 - DIRECT MUSIC API */
window.__AURA_R15_MUSIC_API__ = true;
window.AuraMusicPlayerV180 = {
  open: () => {
    const root = document.getElementById("aura-music-player-v180");
    if (!root) return false;
    openMusic();
    root.hidden = false;
    root.classList.add("open");
    root.style.setProperty("z-index","2147483000","important");
    root.style.setProperty("visibility","visible","important");
    root.style.setProperty("opacity","1","important");
    root.style.setProperty("pointer-events","auto","important");
    return true;
  },
  close: () => {
    const root = document.getElementById("aura-music-player-v180");
    if (!root) return false;
    root.classList.remove("open");
    return true;
  }
};
function ensureMusicNav(){let btn=document.getElementById("aura-music-nav-v180");if(btn){btn.onclick=openMusic;return btn}btn=document.createElement("button");btn.id="aura-music-nav-v180";btn.type="button";btn.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8"><path d="M9 18V5l10-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="16" cy="16" r="3"></circle></svg><span>MUSIQUE</span>';btn.onclick=openMusic;const els=[...document.querySelectorAll("body *")],auraLive=els.find(el=>(el.textContent||"").trim().toUpperCase()==="AURA LIVE"),modules=els.find(el=>(el.textContent||"").trim().toUpperCase()==="MODULES"),anchor=auraLive||modules;let container=anchor?.parentElement;for(let i=0;i<5&&container;i++){const r=container.getBoundingClientRect(),txt=(container.textContent||"").toUpperCase();if(r.width>120&&r.width<320&&txt.includes("CONVERSATION")&&txt.includes("PARAM"))break;container=container.parentElement}if(container&&anchor){let ref=anchor;while(ref.parentElement&&ref.parentElement!==container)ref=ref.parentElement;if(auraLive)container.insertBefore(btn,ref);else if(ref.nextSibling)container.insertBefore(btn,ref.nextSibling);else container.appendChild(btn);return btn}document.body.appendChild(btn);return btn}
function boot(){replaceUi();ensureMusicNav();startAuraLifecycleHeartbeat();let timer=null;new MutationObserver(()=>{clearTimeout(timer);timer=setTimeout(ensureMusicNav,120)}).observe(document.body,{childList:true,subtree:true})}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot,{once:true});else boot()
})();

/* AURA_MUSIC_R17_EXPRESSIVE_PLAYER
   Original AURA implementation inspired by modern expressive player UX.
   No PixelPlayer source code or assets are copied.
*/
(() => {
  "use strict";
  if (window.__AURA_MUSIC_R17_EXPRESSIVE_PLAYER__) return;
  window.__AURA_MUSIC_R17_EXPRESSIVE_PLAYER__ = true;

  const ROOT_ID = "aura-music-player-v180";
  const MINI_ID = "aura-music-mini-r17";
  const q = (s, p = document) => p.querySelector(s);
  const qa = (s, p = document) => [...p.querySelectorAll(s)];
  const root = () => document.getElementById(ROOT_ID);

  function currentThemeIsLight() {
    const toggler = qa("button").find(b => /MODE\s+(SOMBRE|CLAIR)/i.test((b.textContent || "").trim()));
    if (toggler) return /MODE\s+SOMBRE/i.test((toggler.textContent || "").trim());
    const html = document.documentElement;
    const body = document.body;
    return html.dataset.theme === "light" ||
      html.classList.contains("light") ||
      body?.classList.contains("light") ||
      body?.dataset.theme === "light";
  }

  function setTheme() {
    const light = currentThemeIsLight();
    const r = root();
    const m = document.getElementById(MINI_ID);
    if (r) r.classList.toggle("r17-light", light);
    if (m) m.classList.toggle("r17-light", light);
  }

  function setAccent(rgb) {
    const [r, g, b] = rgb;
    const value = `${r},${g},${b}`;
    const player = root();
    const mini = document.getElementById(MINI_ID);
    if (player) player.style.setProperty("--r17-accent-rgb", value);
    if (mini) mini.style.setProperty("--r17-accent-rgb", value);
  }

  let lastArtwork = "";
  function updateArtworkAndAccent() {
    const player = root();
    const cover = document.getElementById("aura-music-cover-v180");
    if (!player || !cover) return;

    const bg = cover.style.backgroundImage || getComputedStyle(cover).backgroundImage || "";
    if (bg && bg !== "none") player.style.setProperty("--r17-art", bg);
    else player.style.setProperty("--r17-art", "none");

    if (!bg || bg === "none" || bg === lastArtwork) return;
    lastArtwork = bg;

    const match = bg.match(/^url\((['"]?)(.*?)\1\)$/);
    const src = match?.[2] || "";
    if (!src) {
      setAccent([76, 215, 235]);
      return;
    }

    const img = new Image();
    img.onload = () => {
      try {
        const c = document.createElement("canvas");
        c.width = c.height = 28;
        const ctx = c.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(img, 0, 0, 28, 28);
        const data = ctx.getImageData(0, 0, 28, 28).data;
        let rr = 0, gg = 0, bb = 0, count = 0;
        for (let i = 0; i < data.length; i += 16) {
          const a = data[i + 3];
          if (a < 180) continue;
          const r = data[i], g = data[i + 1], b = data[i + 2];
          const lum = (r + g + b) / 3;
          if (lum < 28 || lum > 232) continue;
          rr += r; gg += g; bb += b; count++;
        }
        if (!count) return setAccent([76, 215, 235]);
        let r = Math.round(rr / count), g = Math.round(gg / count), b = Math.round(bb / count);
        const max = Math.max(r, g, b), min = Math.min(r, g, b);
        if (max - min < 34) {
          const boost = Math.max(0, 56 - (max - min));
          b = Math.min(255, b + boost);
          g = Math.min(255, g + Math.round(boost * .55));
        }
        const high = Math.max(r, g, b);
        if (high < 150) {
          const k = 150 / Math.max(1, high);
          r = Math.min(235, Math.round(r * k));
          g = Math.min(235, Math.round(g * k));
          b = Math.min(235, Math.round(b * k));
        }
        setAccent([r, g, b]);
      } catch (_e) {
        setAccent([76, 215, 235]);
      }
    };
    img.onerror = () => setAccent([76, 215, 235]);
    img.src = src;
  }

  function closeAuxPanels(keep) {
    const history = document.getElementById("aura-music-library-history-btn-v180");
    const collections = document.getElementById("aura-music-library-collections-v180");
    if (keep !== "history" && history?.classList.contains("active")) history.click();
    if (keep !== "collections" && collections?.classList.contains("active")) collections.click();
  }

  function playlistTitle(text) {
    const title = q(".aura-music-playlist-title", root());
    if (title) title.textContent = text;
  }

  function selectTab(tab) {
    const player = root();
    if (!player) return;
    player.dataset.r17tab = tab;
    qa(".aura-music-r17-tab", player).forEach(b => {
      b.classList.toggle("active", b.dataset.tab === tab);
      b.setAttribute("aria-selected", b.dataset.tab === tab ? "true" : "false");
    });

    if (tab === "player") {
      closeAuxPanels("");
      playlistTitle("À SUIVRE");
    } else if (tab === "library") {
      closeAuxPanels("");
      playlistTitle("BIBLIOTHÈQUE");
    } else if (tab === "queue") {
      closeAuxPanels("");
      playlistTitle("FILE D’ATTENTE");
    } else if (tab === "playlists") {
      closeAuxPanels("collections");
      playlistTitle("PLAYLISTES");
      setTimeout(() => {
        const b = document.getElementById("aura-music-library-collections-v180");
        if (b && !b.classList.contains("active")) b.click();
      }, 80);
    }
  }

  function ensureTabs() {
    const player = root();
    const head = q(".aura-music-head", player);
    if (!player || !head) return false;
    if (q(".aura-music-r17-tabs", head)) return true;

    const tabs = document.createElement("nav");
    tabs.className = "aura-music-r17-tabs";
    tabs.setAttribute("aria-label", "Navigation AURA Music");
    tabs.innerHTML = `
      <button type="button" class="aura-music-r17-tab active" data-tab="player">LECTURE</button>
      <button type="button" class="aura-music-r17-tab" data-tab="library">BIBLIOTHÈQUE</button>
      <button type="button" class="aura-music-r17-tab" data-tab="playlists">PLAYLISTES</button>
      <button type="button" class="aura-music-r17-tab" data-tab="queue">FILE</button>`;
    const right = q(".aura-music-head-right", head);
    head.insertBefore(tabs, right || null);
    tabs.addEventListener("click", e => {
      const b = e.target.closest(".aura-music-r17-tab");
      if (b) selectTab(b.dataset.tab || "player");
    });
    player.dataset.r17tab = player.dataset.r17tab || "player";
    playlistTitle("À SUIVRE");
    return true;
  }

  function openFullPlayer() {
    const nav = document.getElementById("aura-music-nav-v180");
    if (nav) {
      nav.click();
    } else {
      const player = root();
      if (player) player.classList.add("open");
    }
    setTimeout(() => selectTab("player"), 40);
  }

  function coreClick(id) {
    const b = document.getElementById(id);
    if (b) b.click();
  }

  function ensureMiniPlayer() {
    let mini = document.getElementById(MINI_ID);
    if (mini) return mini;
    mini = document.createElement("section");
    mini.id = MINI_ID;
    mini.setAttribute("aria-label", "Mini lecteur AURA Music");
    mini.innerHTML = `
      <div class="r17-mini-cover" title="Ouvrir AURA Music"></div>
      <div class="r17-mini-info" title="Ouvrir AURA Music">
        <div class="r17-mini-title">Aucun média</div>
        <div class="r17-mini-artist">Bibliothèque locale</div>
      </div>
      <div class="r17-mini-progress"><i></i></div>
      <div class="r17-mini-controls">
        <button type="button" class="r17-mini-btn prev" title="Précédent">◀</button>
        <button type="button" class="r17-mini-btn play" title="Lecture / pause">▶</button>
        <button type="button" class="r17-mini-btn next" title="Suivant">▶</button>
        <button type="button" class="r17-mini-open" title="Ouvrir le lecteur">OUVRIR</button>
      </div>`;
    document.body.appendChild(mini);

    q(".r17-mini-cover", mini).onclick = openFullPlayer;
    q(".r17-mini-info", mini).onclick = openFullPlayer;
    q(".r17-mini-open", mini).onclick = openFullPlayer;
    q(".r17-mini-btn.prev", mini).onclick = e => { e.stopPropagation(); coreClick("aura-music-prev-v180"); };
    q(".r17-mini-btn.play", mini).onclick = e => { e.stopPropagation(); coreClick("aura-music-play-v180"); };
    q(".r17-mini-btn.next", mini).onclick = e => { e.stopPropagation(); coreClick("aura-music-next-v180"); };
    return mini;
  }

  function syncMiniPlayer() {
    const player = root();
    if (!player) return;
    const mini = ensureMiniPlayer();
    const title = document.getElementById("aura-music-current-title-v180")?.textContent?.trim() || "";
    const artist = document.getElementById("aura-music-current-artist-v180")?.textContent?.trim() || "";
    const cover = document.getElementById("aura-music-cover-v180");
    const progress = document.getElementById("aura-music-progress-v180");
    const hasTrack = !!title && !/^Aucun média$/i.test(title);
    const fullOpen = player.classList.contains("open");

    mini.classList.toggle("show", hasTrack && !fullOpen);
    q(".r17-mini-title", mini).textContent = title || "Aucun média";
    q(".r17-mini-artist", mini).textContent = artist || "Bibliothèque locale";

    const bg = cover ? (cover.style.backgroundImage || getComputedStyle(cover).backgroundImage || "") : "";
    const miniCover = q(".r17-mini-cover", mini);
    miniCover.style.backgroundImage = bg && bg !== "none"
      ? bg
      : "linear-gradient(145deg,rgba(var(--r17-accent-rgb),.28),rgba(126,87,226,.22))";

    const pct = Math.max(0, Math.min(100, Number(progress?.value || 0)));
    q(".r17-mini-progress>i", mini).style.width = `${pct}%`;
    const playing = player.dataset.playing === "true";
    q(".r17-mini-btn.play", mini).textContent = playing ? "Ⅱ" : "▶";
  }

  function improveLabels() {
    const player = root();
    if (!player) return;
    const count = document.getElementById("aura-music-count-v180");
    if (count && player.dataset.r17tab === "player" && !count.dataset.r17Original) {
      count.dataset.r17Original = count.textContent || "";
    }
  }

  let booted = false;
  function refresh() {
    const player = root();
    if (!player) return;
    ensureTabs();
    ensureMiniPlayer();
    setTheme();
    updateArtworkAndAccent();
    syncMiniPlayer();
    improveLabels();
    if (!booted) {
      booted = true;
      player.dataset.r17tab = "player";
      selectTab("player");
    }
  }

  const observer = new MutationObserver(() => {
    clearTimeout(observer.__r17Timer);
    observer.__r17Timer = setTimeout(refresh, 35);
  });

  function boot() {
    refresh();
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["class", "style", "data-playing", "data-runtime"]
    });
    setInterval(() => {
      setTheme();
      updateArtworkAndAccent();
      syncMiniPlayer();
    }, 420);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();

