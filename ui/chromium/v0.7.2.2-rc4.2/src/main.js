/* AURA P0.4.1.5 STAGE MONOTONICITY FIX */
/* AURA P0.4.1 TRUE NEURAL CONSTRUCTION BOOT */
/* AURA P0.3.4 STATE PCM FUSION */
/* AURA P0.3.3 VOICE DYNAMICS */
/* AURA P0.3.2 ORB MULTILAYER REACTION */
/* AURA P0.3.1 NEURAL VOICE ENVELOPE SHAPER */
import * as THREE from 'three';
import './style.css';

const qs = new URLSearchParams(location.search);
const token = qs.get('token') || '';
const ids=['stateText','routeText','coreChip','voiceChip','coreState','coreSub','bootCard','bootPercent','bootFill','bootPhase','displayGpu','computeGpu','voiceState','voiceSub','providerState','providerSub','eventLink','eventCount','pcmValue','wave','toast','conversation','messages','emptyConversation','conversationStatus','messageInput','composerHint','sendBtn','micBtn','talkBtn','homeBtn','closeTalk'];
const ui=Object.fromEntries(ids.map(id=>[id,document.getElementById(id)]));
let eventCounter=0, pcm=0, targetPcm=0, boot=0, currentState='BOOTSTRAP', stateTarget='STARTUP';
let interactionReady=false, micHeld=false, voiceWarmStarted=performance.now();
const waveHistory = new Array(96).fill(0);

function toast(msg){ui.toast.textContent=msg;ui.toast.classList.add('show');clearTimeout(toast.t);toast.t=setTimeout(()=>ui.toast.classList.remove('show'),2400)}
function cleanState(v){const s=String(v||'IDLE').toUpperCase();const m=s.match(/(IDLE|LISTENING|TRANSCRIBING|THINKING|SEARCHING|ANALYZING|ACTING|WAITING_CONFIRMATION|SPEAKING|PAUSED|OFFLINE|ERROR|STARTUP)/);return m?m[1]:'IDLE'}
function setState(v){currentState=cleanState(v);document.body.dataset.state=currentState;ui.stateText.textContent=currentState;ui.coreState.textContent=currentState==='STARTUP'?'INITIALIZING':currentState;stateTarget=currentState;}
function setBoot(p,phase){boot=Math.max(0,Math.min(100,Number(p)||0));ui.bootPercent.textContent=String(Math.round(boot)).padStart(2,'0')+'%';ui.bootFill.style.width=boot+'%';if(phase)ui.bootPhase.textContent=String(phase).toUpperCase().slice(0,62);if(boot>=100)setTimeout(()=>ui.bootCard.classList.add('hidden'),1100)}
function setConstruction(p,phase){const next=Math.max(0,Math.min(100,Number(p)||0));if(next<=boot)return;ui.bootCard.classList.remove('hidden');setBoot(next,phase)}
function mapStartupConstruction(raw,phase){const p=Math.max(0,Math.min(100,Number(raw)||0));const mapped=Math.min(40,12+p*.30);const stage=p<78?'01 ÉMERGENCE':'02 AGRÉGATION';setConstruction(mapped,`${stage} · ${String(phase||'Initialisation des services').toUpperCase()}`)}
function finalizeConstructionSnapshot(d={}){if((d.voice_ready||String(d.voice_state)==='ready')&&interactionReady&&boot>=82&&boot<100)setConstruction(100,'05 STABILISATION · NOYAU OPÉRATIONNEL')}
function mapOperation(name){const n=String(name||'').toLowerCase();if(/web|search|internet|news/.test(n))return'SEARCHING';if(/document|pdf|vision|image|analy/.test(n))return'ANALYZING';return'ACTING'}
function setInteractionReady(on){interactionReady=!!on;ui.messageInput.disabled=!on;ui.sendBtn.disabled=!on;ui.micBtn.disabled=!on;ui.messageInput.placeholder=on?'Écris à AURA…':'AURA démarre…';ui.composerHint.textContent=on?'Entrée pour envoyer · maintenir le micro pour parler':'Interaction activée lorsque le Runtime est prêt.';if(on)ui.conversationStatus.textContent='Conversation locale active';}
const deferredVoiceResults=new Set(['ram-available','ram-hard-percent','vram-percent','display-gpu-guard','vram-unmeasured','ollama-resident','dual-probe-required']);
function setVoiceReady(sub='Camilla · XTTS resident'){ui.voiceState.textContent='READY';ui.voiceSub.textContent=sub;ui.voiceChip.textContent='CAMILLA · READY';}
function setVoiceWarming(){if(ui.voiceState.textContent!=='WARMING')voiceWarmStarted=performance.now();ui.voiceState.textContent='WARMING';ui.voiceSub.textContent='Camilla se charge en arriere-plan';ui.voiceChip.textContent='CAMILLA - CHARGEMENT';}
function setVoiceStandby(result='on-demand'){ui.voiceState.textContent='STANDBY';ui.voiceSub.textContent=deferredVoiceResults.has(String(result))?'Camilla · chargement à la demande':String(result||'Voice runtime disponible');ui.voiceChip.textContent='CAMILLA · STANDBY';}
function applyVoiceSnapshot(d={}){if(d.voice_ready||String(d.voice_state)==='ready')setVoiceReady();else if(d.voice_warming||String(d.voice_state)==='warming')setVoiceWarming();else if(String(d.voice_state)==='standby'&&ui.voiceState.textContent!=='READY')setVoiceStandby(d.voice_result);finalizeConstructionSnapshot(d);}

// --- Three.js Neural Core: Intel-balanced, WebGL2 ---
const host=document.getElementById('stage');
const scene=new THREE.Scene();
const camera=new THREE.PerspectiveCamera(42,1,.1,100);camera.position.set(0,0,10.2);
const renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'default'});
renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.setClearColor(0x000000,0);host.appendChild(renderer.domElement);
try{const gl=renderer.getContext(),ext=gl.getExtension('WEBGL_debug_renderer_info');const actual=ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);if(actual){ui.displayGpu.textContent=String(actual).replace(/^ANGLE \(/,'').split(',')[1]?.trim()?.slice(0,28)||String(actual).slice(0,28);if(token)fetch(`/api/client-info?token=${encodeURIComponent(token)}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({webgl_renderer:String(actual).slice(0,220),dpr:devicePixelRatio})}).catch(()=>{})}}catch{}
const group=new THREE.Group();scene.add(group);
const coreMat=new THREE.MeshBasicMaterial({color:0x63dfff,wireframe:true,transparent:true,opacity:.23,blending:THREE.AdditiveBlending});
const core=new THREE.Mesh(new THREE.IcosahedronGeometry(1.18,3),coreMat);group.add(core);
const shellMat=new THREE.MeshBasicMaterial({color:0x846cff,wireframe:true,transparent:true,opacity:.10,blending:THREE.AdditiveBlending});
const shell=new THREE.Mesh(new THREE.IcosahedronGeometry(1.72,2),shellMat);group.add(shell);
const halo=new THREE.Mesh(new THREE.TorusGeometry(2.22,.012,6,160),new THREE.MeshBasicMaterial({color:0x50cfff,transparent:true,opacity:.20,blending:THREE.AdditiveBlending}));halo.rotation.x=1.18;halo.rotation.y=.3;group.add(halo);
const halo2=halo.clone();halo2.material=halo.material.clone();halo2.material.color.setHex(0x8c6dff);halo2.rotation.set(.35,1.05,.7);group.add(halo2);

const PCOUNT=9000;const pos=new Float32Array(PCOUNT*3);
for(let i=0;i<PCOUNT;i++){const r=2.0+Math.pow(Math.random(),1.8)*3.2;const u=Math.random()*2-1;const t=Math.random()*Math.PI*2;const s=Math.sqrt(1-u*u);pos[i*3]=r*s*Math.cos(t);pos[i*3+1]=r*u*.82;pos[i*3+2]=r*s*Math.sin(t)}
const pg=new THREE.BufferGeometry();pg.setAttribute('position',new THREE.BufferAttribute(pos,3));
const pm=new THREE.PointsMaterial({color:0x74e7ff,size:.018,transparent:true,opacity:.52,depthWrite:false,blending:THREE.AdditiveBlending});const points=new THREE.Points(pg,pm);group.add(points);
const SEG=1300;const lp=new Float32Array(SEG*6);for(let i=0;i<SEG;i++){const a=Math.floor(Math.random()*PCOUNT),b=Math.floor(Math.random()*PCOUNT);for(let j=0;j<3;j++){lp[i*6+j]=pos[a*3+j];lp[i*6+3+j]=pos[b*3+j]}}
const lg=new THREE.BufferGeometry();lg.setAttribute('position',new THREE.BufferAttribute(lp,3));const lm=new THREE.LineBasicMaterial({color:0x46bde6,transparent:true,opacity:.045,blending:THREE.AdditiveBlending});const lines=new THREE.LineSegments(lg,lm);group.add(lines);

// Radial texture avoids the opaque square visible in RC3's default SpriteMaterial.
const glowCanvas=document.createElement('canvas');glowCanvas.width=256;glowCanvas.height=256;const gc=glowCanvas.getContext('2d');const gg=gc.createRadialGradient(128,128,0,128,128,124);gg.addColorStop(0,'rgba(105,232,255,.92)');gg.addColorStop(.15,'rgba(84,210,255,.36)');gg.addColorStop(.5,'rgba(60,140,255,.09)');gg.addColorStop(1,'rgba(0,0,0,0)');gc.fillStyle=gg;gc.fillRect(0,0,256,256);
const glowTex=new THREE.CanvasTexture(glowCanvas);const glow=new THREE.Sprite(new THREE.SpriteMaterial({map:glowTex,color:0x5adfff,transparent:true,opacity:.18,blending:THREE.AdditiveBlending,depthWrite:false}));glow.scale.set(4.6,4.6,1);group.add(glow);

const clock=new THREE.Clock();let lastRender=0;const TARGET_FPS=48;
function resize(){const w=host.clientWidth,h=host.clientHeight;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix()}new ResizeObserver(resize).observe(host);resize();
function animate(ts){requestAnimationFrame(animate);const auraVisualFps=window.AuraVisualBudget?.fps('core',TARGET_FPS)||TARGET_FPS;if(ts-lastRender<1000/auraVisualFps)return;lastRender=ts;const dt=Math.min(clock.getDelta(),.05);const envelopeTau=targetPcm>pcm?.040:.220;const envelopeAlpha=1-Math.exp(-dt/envelopeTau);const envelopeBase=pcm+(targetPcm-pcm)*envelopeAlpha;const attackAccent=Math.max(0,targetPcm-envelopeBase)*.16;pcm=Math.min(1,envelopeBase+attackAccent);targetPcm*=Math.exp(-dt/.110);const idle=stateTarget==='IDLE'?1:0;const listen=stateTarget==='LISTENING'?1:0;const speak=stateTarget==='SPEAKING'?1:0;const think=/THINKING|ANALYZING|SEARCHING/.test(stateTarget)?1:0;const act=stateTarget==='ACTING'?1:0;const build=Math.max(0,Math.min(1,boot/100));const emergence=Math.max(0,Math.min(1,(build-.01)/.15));const aggregation=Math.max(0,Math.min(1,(build-.16)/.26));const structuration=Math.max(0,Math.min(1,(build-.40)/.26));const activation=Math.max(0,Math.min(1,(build-.64)/.24));const stabilization=Math.max(0,Math.min(1,(build-.86)/.14));const bootFactor=.01+emergence*.29+aggregation*.24+structuration*.24+activation*.16+stabilization*.06;shell.visible=structuration>.015;halo.visible=activation>.015;halo2.visible=activation>.08;core.visible=activation>.015;glow.visible=activation>.015;shell.scale.setScalar(.72+structuration*.28);halo.scale.setScalar(.62+activation*.38);halo2.scale.setScalar(.58+activation*.42);const voiceEnergy=pcm;const voiceMotion=Math.pow(voiceEnergy,.68);const voiceAccent=Math.min(1,Math.max(0,targetPcm-pcm)*2.4);const voiceSoft=Math.max(0,Math.min(1,(voiceEnergy-.035)/.20))*(1-Math.max(0,Math.min(1,(voiceEnergy-.30)/.22)));const voiceNormal=Math.max(0,Math.min(1,(voiceEnergy-.18)/.34))*(1-Math.max(0,Math.min(1,(voiceEnergy-.67)/.20)));const voiceStrong=Math.max(0,Math.min(1,(voiceEnergy-.52)/.38));const voiceBurst=Math.min(1,voiceAccent*(.55+voiceStrong*.75));const voicePresence=Math.min(1,voiceSoft*.28+voiceNormal*.48+voiceStrong*.72+voiceBurst*.55);const speakingDrive=speak*voicePresence;const idleBreath=idle*(.5+.5*Math.sin(ts*.00135));const listenFocus=listen*(.62+.38*Math.sin(ts*.00215));group.scale.setScalar(bootFactor*(1+idleBreath*.003+listenFocus*.005+think*.006+act*.008+voiceSoft*.018+voiceNormal*.046+voiceStrong*.072+voiceBurst*.028+speakingDrive*.002));group.rotation.y += dt*(.075+listen*.025+think*.18+act*.12+voiceSoft*.012+voiceNormal*.038+voiceStrong*.074);group.rotation.x=Math.sin(ts*.00011)*(.08+listen*.006+think*.008+voiceSoft*.004+voiceStrong*.018);points.rotation.y-=dt*(.025+listen*.025+think*.06+voiceSoft*.035+voiceNormal*.10+voiceStrong*.18);shell.rotation.z+=dt*(.028+listen*.035+think*.075+act*.055+voiceSoft*.035+voiceNormal*.12+voiceStrong*.24+speakingDrive*.006);halo.rotation.z+=dt*(.12+listen*.055+think*.11+act*.08+voiceSoft*.08+voiceNormal*.23+voiceStrong*.42+voiceBurst*.12+speakingDrive*.008);halo2.rotation.z-=dt*(.08+listen*.025+think*.055+act*.04+voiceSoft*.04+voiceNormal*.12+voiceStrong*.23+voiceBurst*.06);core.material.opacity=activation*(.12+idleBreath*.018+listenFocus*.04+think*.025+act*.03+voiceSoft*.18+voiceNormal*.26+voiceStrong*.34+voiceBurst*.10+speakingDrive*.008);pm.opacity=emergence*(.24+idleBreath*.025+listenFocus*.05+think*.10+act*.06+voiceSoft*.15+voiceNormal*.34+voiceStrong*.44);lm.opacity=aggregation*(.014+listenFocus*.035+think*.055+act*.025+voiceSoft*.045+voiceNormal*.10+voiceStrong*.16);glow.material.opacity=activation*(.04+idleBreath*.018+listenFocus*.055+think*.045+act*.05+voiceSoft*.12+voiceNormal*.27+voiceStrong*.39+voiceBurst*.12+speakingDrive*.008);const c=stateTarget==='ERROR'?0xff5777:stateTarget==='SPEAKING'?0xa474ff:stateTarget==='LISTENING'?0x66ffca:stateTarget==='SEARCHING'?0x4da9ff:0x63dfff;core.material.color.lerp(new THREE.Color(c),.06);glow.material.color.lerp(new THREE.Color(c),.04);renderer.render(scene,camera)}requestAnimationFrame(animate);

// --- PCM oscilloscope ---
const ctx=ui.wave.getContext('2d');function drawWave(){const w=ui.wave.width,h=ui.wave.height;ctx.clearRect(0,0,w,h);const grad=ctx.createLinearGradient(0,0,w,0);grad.addColorStop(0,'rgba(73,137,255,.30)');grad.addColorStop(.5,'rgba(104,235,255,.95)');grad.addColorStop(1,'rgba(157,102,255,.38)');ctx.strokeStyle=grad;ctx.lineWidth=1.5;ctx.beginPath();waveHistory.forEach((v,i)=>{const x=i/(waveHistory.length-1)*w;const y=h/2-(v*(h*.39))*Math.sin(i*.92);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke();ctx.strokeStyle='rgba(102,226,255,.08)';ctx.beginPath();ctx.moveTo(0,h/2);ctx.lineTo(w,h/2);ctx.stroke();requestAnimationFrame(drawWave)}drawWave();

function openTalk(){ui.conversation.classList.add('open');ui.talkBtn.classList.add('active');ui.homeBtn.classList.remove('active')}
function closeTalk(){ui.conversation.classList.remove('open');ui.talkBtn.classList.remove('active');ui.homeBtn.classList.add('active')}
function appendMessage(role,text){text=String(text||'').trim();if(!text)return;ui.emptyConversation?.remove();const row=document.createElement('div');row.className=`message ${role}`;const meta=document.createElement('span');meta.textContent=role==='aura'?'AURA':role==='user'?'TOI':'SYSTEM';const body=document.createElement('p');body.textContent=text;row.append(meta,body);ui.messages.appendChild(row);ui.messages.scrollTop=ui.messages.scrollHeight;openTalk()}

async function action(action,payload={}){if(!token)throw new Error('token');const res=await fetch(`/api/action?token=${encodeURIComponent(token)}`,{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...payload})});let data={};try{data=await res.json()}catch{}if(!res.ok)throw new Error(data.error||`HTTP ${res.status}`);return data}
async function sendCurrent(){if(!interactionReady)return;const text=ui.messageInput.value.trim();if(!text)return;ui.sendBtn.disabled=true;try{await action('send_message',{text});ui.messageInput.value='';ui.messageInput.style.height='auto';ui.composerHint.textContent='Message transmis au Core local…'}catch(e){toast(`Message non envoyé · ${e.message}`)}finally{ui.sendBtn.disabled=!interactionReady}}

function handleEvent(ev){eventCounter++;ui.eventCount.textContent=`${eventCounter} events`;ui.eventLink.textContent='CONNECTED';ui.coreChip.textContent='CORE · LINKED';const t=ev.type,d=ev.data||{};
  if(t==='bridge.ready'){setConstruction(Math.max(boot,4),'01 ÉMERGENCE · LIEN LOCAL SÉCURISÉ');ui.coreSub.textContent='Runtime v2 · secure local bridge';if(d.display_gpu)ui.displayGpu.textContent=d.display_gpu;if(d.compute_gpu)ui.computeGpu.textContent=d.compute_gpu;}
  else if(t==='bridge.aura_start'){setState('STARTUP');setConstruction(Math.max(boot,8),'01 ÉMERGENCE · NOYAU PYTHON');}
  else if(t==='startup_progress'){mapStartupConstruction(d.percent,d.phase);}
  else if(t==='startup_ready'){setConstruction(Math.max(boot,42),'02 AGRÉGATION · CORE / CLOUD / TOOLS PRÊTS');setState('IDLE');ui.coreSub.textContent='Runtime v2 online';setInteractionReady(true);toast('AURA est prête · voix en structuration');}
  else if(t==='state'){setState(d.state);}
  else if(t==='provider'){ui.providerState.textContent=String(d.provider||'CLOUD').toUpperCase();ui.providerSub.textContent=String(d.model||'route active').slice(0,36);ui.routeText.textContent=`${String(d.provider||'AI').toUpperCase()} · ${String(d.model||'').toUpperCase()}`.slice(0,34);}
  else if(t==='operation_started'){setState(mapOperation(d.name));ui.routeText.textContent=String(d.name||'LOCAL ACTION').toUpperCase().slice(0,34);}
  else if(t==='operation_finished'){setState('IDLE');}
  else if(t==='voice_warmup_start'){setVoiceWarming();setConstruction(Math.max(boot,56),'03 STRUCTURATION · SYNCHRONISATION VOCALE');}
  else if(t==='voice_warmup_end'){if(d.ok){setVoiceReady(`Camilla · XTTS resident · ${Number(d.elapsed_seconds||0).toFixed(1)}s`);setConstruction(Math.max(boot,86),'04 ACTIVATION · CAMILLA RÉSIDENTE');}else if(deferredVoiceResults.has(String(d.result||''))){setVoiceStandby(d.result);setConstruction(100,'05 STABILISATION · VOIX À LA DEMANDE');}else{ui.voiceState.textContent='LIMITED';ui.voiceSub.textContent=String(d.result||'fallback');ui.voiceChip.textContent='VOICE · LIMITED';setConstruction(100,'05 STABILISATION · MODE VOIX LIMITÉ');}}
  else if(t==='voice_status'){const s=String(d.status||'').toUpperCase();if(s.includes('LISTEN'))setState('LISTENING');else if(s.includes('PROCESS'))setState('TRANSCRIBING');else if(s.includes('SPEAK'))setState('SPEAKING');}
  else if(t==='voice_amplitude'){const rawPcm=Math.max(0,Math.min(1,Number(d.level)||0));const gate=.012;const gated=rawPcm<=gate?0:(rawPcm-gate)/(1-gate);targetPcm=Math.min(1,Math.pow(gated,.72));ui.pcmValue.textContent=rawPcm.toFixed(2);waveHistory.push(targetPcm);waveHistory.shift();if(targetPcm>0.02&&ui.voiceState.textContent==='STANDBY')ui.voiceSub.textContent='Camilla · activité vocale détectée';}
  else if(t==='voice_transcription'){ui.composerHint.textContent='Transcription reçue · traitement en cours';}
  else if(t==='user_message'){appendMessage('user',d.text);ui.composerHint.textContent='AURA traite ton message…';}
  else if(t==='aura_message'){appendMessage('aura',d.text);ui.composerHint.textContent='Prête pour la suite';}
  else if(t==='command_result'&&!d.ok){toast(`Commande ${String(d.action||'').toUpperCase()} refusée`);}
  else if(t==='hardware_display_probe'){if(d.adapter)ui.displayGpu.textContent=String(d.adapter).replace(/\(R\)|\(TM\)/g,'').slice(0,28);}
  else if(t==='hardware_compute_probe'){if(d.adapter)ui.computeGpu.textContent=String(d.adapter).slice(0,28);}
  else if(t==='error'){if(d.text)appendMessage('system',d.text);setState('ERROR');}
  else if(t==='bridge.error'){setState('ERROR');ui.coreSub.textContent='Runtime bridge error';toast('Erreur du Runtime AURA');}
}

if(!token){setState('ERROR');ui.eventLink.textContent='TOKEN MISSING';toast('Session AURA invalide');}
else{
  const es=new EventSource(`/api/events?token=${encodeURIComponent(token)}`);
  es.onopen=()=>{ui.eventLink.textContent='CONNECTED';ui.coreChip.textContent='CORE · CONNECTING';setBoot(Math.max(boot,4),'Lien local securise');};
  es.onmessage=e=>{try{handleEvent(JSON.parse(e.data))}catch{}};
  es.onerror=()=>{ui.eventLink.textContent='RECONNECTING';ui.coreChip.textContent='CORE · WAITING';};
  const auraHeartbeat=()=>fetch(`/api/heartbeat?token=${encodeURIComponent(token)}`,{method:'POST',cache:'no-store'}).then(r=>r.json()).then(applyVoiceSnapshot).catch(()=>{});
  if(window.AuraWorkloadBudget?.repeat)window.AuraWorkloadBudget.repeat(auraHeartbeat,'heartbeat',900);else setInterval(auraHeartbeat,900);
}

ui.talkBtn.addEventListener('click',openTalk);ui.homeBtn.addEventListener('click',closeTalk);ui.closeTalk.addEventListener('click',closeTalk);
ui.messageInput.addEventListener('input',()=>{ui.messageInput.style.height='auto';ui.messageInput.style.height=Math.min(92,ui.messageInput.scrollHeight)+'px'});
ui.messageInput.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendCurrent()}});ui.sendBtn.addEventListener('click',sendCurrent);
ui.micBtn.addEventListener('pointerdown',async e=>{if(!interactionReady||micHeld)return;micHeld=true;ui.micBtn.classList.add('recording');ui.micBtn.setPointerCapture?.(e.pointerId);ui.composerHint.textContent='Écoute… relâche pour envoyer';try{await action('mic_start')}catch(err){micHeld=false;ui.micBtn.classList.remove('recording');toast(`Micro indisponible · ${err.message}`)}});
async function releaseMic(){if(!micHeld)return;micHeld=false;ui.micBtn.classList.remove('recording');ui.composerHint.textContent='Transcription…';try{await action('mic_stop')}catch(err){toast(`Micro · ${err.message}`)}}
ui.micBtn.addEventListener('pointerup',releaseMic);ui.micBtn.addEventListener('pointercancel',releaseMic);

document.getElementById('powerBtn').addEventListener('click',async()=>{if(!token)return window.close();document.getElementById('powerBtn').disabled=true;toast('Arrêt propre d’AURA…');try{await fetch(`/api/shutdown?token=${encodeURIComponent(token)}`,{method:'POST',cache:'no-store'});}catch{}setTimeout(()=>window.close(),450)});
window.addEventListener('pagehide',()=>{if(token)navigator.sendBeacon(`/api/client-close?token=${encodeURIComponent(token)}`,'close')});
setInterval(()=>{if(ui.voiceState.textContent==='WARMING'){const sec=Math.floor((performance.now()-voiceWarmStarted)/1000);ui.voiceSub.textContent=`Camilla se charge en arriere-plan`}},1000);
/* AURA P0.4.1.2 STATUS RECOVERY BRIDGE FIX */
let auraP0412ReadySamples=0;
let auraP0412StatusLinked=false;

async function auraP0412PollRuntimeStatus(){
  try{
    const statusToken=new URLSearchParams(location.search).get('token')||'';
    if(!statusToken)return;

    const res=await fetch(`/api/status?token=${encodeURIComponent(statusToken)}`,{
      cache:'no-store'
    });
    if(!res.ok)throw new Error(`status ${res.status}`);

    const d=await res.json();
    if(!d||!d.ok)return;

    auraP0412StatusLinked=true;

    if(ui.eventLink.textContent!=='CONNECTED'){
      ui.eventLink.textContent='STATUS LINK';
    }
    ui.coreChip.textContent='CORE · LINKED';

    if(boot<4){
      setConstruction(4,'01 ÉMERGENCE · RUNTIME LOCAL JOIGNABLE');
    }

    if(d.interaction_ready){
      if(!interactionReady){
        setInteractionReady(true);
        setState('IDLE');
        ui.coreSub.textContent='Runtime v2 online · status recovery';
      }

      if(boot<42){
        setConstruction(
          42,
          '02 AGRÉGATION · CORE / CLOUD / TOOLS PRÊTS'
        );
      }
    }

    const voiceReady=
      !!d.voice_ready||String(d.voice_state||'')==='ready';

    const voiceWarming=
      !!d.voice_warming||String(d.voice_state||'')==='warming';

    if(voiceWarming){
      setVoiceWarming();
      auraP0412ReadySamples=0;

      if(d.interaction_ready&&boot<56){
        setConstruction(
          56,
          '03 STRUCTURATION · SYNCHRONISATION VOCALE'
        );
      }
    }

    if(voiceReady){
      setVoiceReady('Camilla · XTTS resident · status confirmed');

      if(d.interaction_ready){
        if(boot<86){
          setConstruction(
            86,
            '04 ACTIVATION · CAMILLA RÉSIDENTE'
          );
        }

        auraP0412ReadySamples++;

        if(auraP0412ReadySamples>=2&&boot<100){
          setConstruction(
            100,
            '05 STABILISATION · NOYAU OPÉRATIONNEL'
          );
        }
      }
    }else if(!voiceWarming){
      auraP0412ReadySamples=0;
    }
  }catch(err){
    auraP0412StatusLinked=false;
  }
}

auraP0412PollRuntimeStatus();
if(window.AuraWorkloadBudget?.repeat)window.AuraWorkloadBudget.repeat(auraP0412PollRuntimeStatus,'runtime-status',700);else setInterval(auraP0412PollRuntimeStatus,700);
