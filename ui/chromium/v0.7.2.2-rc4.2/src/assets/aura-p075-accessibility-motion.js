/* AURA P0.7.5 — ACCESSIBILITY & MOTION
   Global accessibility layer for the Unified Workspace.
   - Respects OS reduced-motion preference by default.
   - Manual motion, contrast and text-scale overrides are local-only.
   - Adds visible keyboard focus, skip navigation and live announcements.
   - Does not read or transmit user content, health data, files or prompts.
*/
(()=>{
  'use strict';
  if(window.__AURA_P075_ACCESSIBILITY__)return;
  window.__AURA_P075_ACCESSIBILITY__=true;

  const VERSION='P0.7.5';
  const STORAGE='aura.accessibility.p075';
  const VALID_MOTION=new Set(['system','full','reduced','off']);
  const VALID_CONTRAST=new Set(['standard','high']);
  const VALID_SCALE=new Set(['100','115','130']);
  const STATE={panel:null,button:null,live:null,skip:null,settings:null,registered:false};
  const q=(s,r=document)=>r.querySelector(s);
  const qa=(s,r=document)=>[...r.querySelectorAll(s)];
  const safe=(v,n=120)=>String(v??'').replace(/\s+/g,' ').trim().slice(0,n);
  const mm=window.matchMedia?.('(prefers-reduced-motion: reduce)');

  function defaults(){return {motion:'system',contrast:'standard',scale:'100'}}
  function load(){
    const d=defaults();
    try{
      const raw=JSON.parse(localStorage.getItem(STORAGE)||'{}');
      if(VALID_MOTION.has(raw.motion))d.motion=raw.motion;
      if(VALID_CONTRAST.has(raw.contrast))d.contrast=raw.contrast;
      if(VALID_SCALE.has(String(raw.scale)))d.scale=String(raw.scale);
    }catch(_e){}
    return d;
  }
  function persist(){try{localStorage.setItem(STORAGE,JSON.stringify(STATE.settings))}catch(_e){}}
  function resolvedMotion(){const m=STATE.settings?.motion||'system';return m==='system'?(mm?.matches?'reduced':'full'):m}
  function emit(name,detail){window.dispatchEvent(new CustomEvent(name,{detail:Object.assign({version:VERSION},detail||{})}))}
  function announce(text){
    if(!STATE.live)return;
    const v=safe(text,240);if(!v)return;
    STATE.live.textContent='';setTimeout(()=>{if(STATE.live)STATE.live.textContent=v},20);
  }
  function apply({save=true,notify=true}={}){
    const s=STATE.settings||defaults(),motion=resolvedMotion();
    const root=document.documentElement,body=document.body;
    root.dataset.auraMotion=motion;root.dataset.auraMotionPreference=s.motion;
    root.dataset.auraContrast=s.contrast;root.dataset.auraTextScale=s.scale;
    body?.classList.toggle('aura-p075-reduced-motion',motion==='reduced'||motion==='off');
    body?.classList.toggle('aura-p075-motion-off',motion==='off');
    body?.classList.toggle('aura-p075-high-contrast',s.contrast==='high');
    window.__AURA_REDUCED_MOTION__=motion==='reduced'||motion==='off';
    window.__AURA_MOTION_OFF__=motion==='off';
    if(save)persist();
    refreshPanel();
    if(notify){
      emit('aura:accessibility-changed',{settings:{...s},resolvedMotion:motion,reduced:window.__AURA_REDUCED_MOTION__});
      emit('aura:motion-profile-changed',{preference:s.motion,resolved:motion,reduced:window.__AURA_REDUCED_MOTION__,off:window.__AURA_MOTION_OFF__});
    }
  }
  function setSetting(key,val){
    if(key==='motion'&&VALID_MOTION.has(val))STATE.settings.motion=val;
    else if(key==='contrast'&&VALID_CONTRAST.has(val))STATE.settings.contrast=val;
    else if(key==='scale'&&VALID_SCALE.has(String(val)))STATE.settings.scale=String(val);
    else return false;
    apply();announce(labelForCurrent());return true;
  }
  function labelForCurrent(){
    const s=STATE.settings,m=resolvedMotion();
    const ml={system:'système',full:'complet',reduced:'réduit',off:'désactivé'}[s.motion]||s.motion;
    const rl=m==='reduced'?'mouvement réduit':m==='off'?'animations désactivées':'mouvement complet';
    const cl=s.contrast==='high'?'contraste renforcé':'contraste standard';
    return `Accessibilité : profil ${ml}, ${rl}, ${cl}, texte ${s.scale} pour cent.`;
  }

  function ensureInfra(){
    if(!STATE.live){
      let live=q('#aura-p075-live');
      if(!live){live=document.createElement('div');live.id='aura-p075-live';live.className='aura-p075-sr-only';live.setAttribute('role','status');live.setAttribute('aria-live','polite');live.setAttribute('aria-atomic','true');document.body.appendChild(live)}
      STATE.live=live;
    }
    if(!STATE.skip){
      let skip=q('#aura-p075-skip');
      if(!skip){skip=document.createElement('button');skip.id='aura-p075-skip';skip.type='button';skip.className='aura-p075-skip';skip.textContent='Aller au contenu principal';skip.addEventListener('click',focusPrimary);document.body.prepend(skip)}
      STATE.skip=skip;
    }
  }
  function focusPrimary(){
    const current=safe(window.AuraWorkspace?.current?.()||document.body.dataset.auraWorkspace||'',32).toLowerCase();
    const selectors={
      talk:'.aura-p0712-conversation-drawer.open #messageInput, .aura-p0711-conversation-drawer.open #messageInput, #messageInput',
      weather:'.aura-p073-weather-workspace.open button, .aura-p073-weather-workspace.open input',
      vitals:'.aura-p074-vitals-workspace.open button, .aura-p074-vitals-workspace.open input',
      maps:'.aura-maps-workspace.open button, .aura-maps-workspace.open input',
      plan:'[data-aura-workspace="plan"] button, [data-aura-workspace="plan"] input'
    };
    const target=q(selectors[current]||'main button, main input, #messageInput, [data-rail-target="home"]');
    if(target){target.focus({preventScroll:false});target.scrollIntoView?.({block:'nearest',inline:'nearest'});announce('Contenu principal atteint.')}
    return !!target;
  }

  function ensureButton(){
    const grid=q('.aura-p0702-module-grid');if(!grid)return false;
    let b=q('[data-module="accessibility"]',grid);
    if(!b){
      b=document.createElement('button');b.type='button';b.dataset.module='accessibility';b.className='aura-p075-accessibility-entry';
      b.innerHTML='<span aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="12" cy="4.7" r="2.1"/><path d="M5 8.4c4.8 1.5 9.2 1.5 14 0M12 7.4v12M8.1 20l3.9-6 3.9 6M8.4 10.6 5.9 16M15.6 10.6l2.5 5.4"/></svg></span><div><b>ACCESSIBILITÉ</b><small>Contraste · texte · mouvement</small></div>';
      grid.appendChild(b);
    }
    b.setAttribute('aria-haspopup','dialog');b.setAttribute('aria-controls','aura-p075-panel');STATE.button=b;return true;
  }

  function optionGroup(title,key,items){
    return `<fieldset class="aura-p075-field"><legend>${title}</legend><div class="aura-p075-options" role="radiogroup">${items.map(([v,l,d])=>`<button type="button" role="radio" aria-checked="false" data-a11y-key="${key}" data-a11y-value="${v}"><b>${l}</b><small>${d}</small></button>`).join('')}</div></fieldset>`;
  }
  function ensurePanel(){
    if(STATE.panel?.isConnected)return STATE.panel;
    const p=document.createElement('section');p.id='aura-p075-panel';p.className='aura-p075-panel';p.hidden=true;p.setAttribute('role','dialog');p.setAttribute('aria-modal','false');p.setAttribute('aria-labelledby','aura-p075-title');
    p.innerHTML=`<header><div><small>AURA · ACCESSIBILITY</small><b id="aura-p075-title">ACCESSIBILITÉ & MOUVEMENT</b><em>Réglages locaux à cette interface</em></div><button type="button" data-a11y-action="close" aria-label="Fermer le panneau Accessibilité">×</button></header><div class="aura-p075-content">
      ${optionGroup('MOUVEMENT','motion',[['system','SYSTÈME','Suit la préférence Windows / navigateur'],['full','COMPLET','Animations et transitions normales'],['reduced','RÉDUIT','Transitions courtes, effets atténués'],['off','DÉSACTIVÉ','Animations décoratives neutralisées']])}
      ${optionGroup('CONTRASTE','contrast',[['standard','STANDARD','Palette AURA normale'],['high','RENFORCÉ','Bordures, texte et focus plus lisibles']])}
      ${optionGroup('TAILLE DU TEXTE','scale',[['100','100 %','Échelle normale'],['115','115 %','Texte agrandi'],['130','130 %','Texte fortement agrandi']])}
      <div class="aura-p075-help"><b>CLAVIER</b><span><kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>A</kbd> ouvre ce panneau.</span><span><kbd>Tab</kbd> affiche un focus renforcé. <kbd>Échap</kbd> ferme ce panneau.</span></div>
    </div><footer><button type="button" data-a11y-action="reset">RÉINITIALISER</button><span data-a11y-summary></span></footer>`;
    document.body.appendChild(p);STATE.panel=p;
    p.addEventListener('click',e=>{
      const b=e.target.closest('[data-a11y-key],[data-a11y-action]');if(!b)return;
      if(b.dataset.a11yKey){setSetting(b.dataset.a11yKey,b.dataset.a11yValue);return}
      if(b.dataset.a11yAction==='close')closePanel();
      if(b.dataset.a11yAction==='reset'){STATE.settings=defaults();apply();announce('Réglages d’accessibilité réinitialisés.')}
    });
    return p;
  }
  function refreshPanel(){
    const p=STATE.panel;if(!p)return;
    qa('[data-a11y-key]',p).forEach(b=>{const active=String(STATE.settings?.[b.dataset.a11yKey])===b.dataset.a11yValue;b.classList.toggle('active',active);b.setAttribute('aria-checked',String(active))});
    const s=q('[data-a11y-summary]',p);if(s)s.textContent=`Mouvement : ${resolvedMotion()} · Contraste : ${STATE.settings.contrast} · Texte : ${STATE.settings.scale}%`;
  }
  function openPanel(){
    ensureInfra();ensurePanel();
    STATE.panel.hidden=false;STATE.panel.classList.add('open');STATE.button?.setAttribute('aria-expanded','true');refreshPanel();
    setTimeout(()=>q('[data-a11y-key]',STATE.panel)?.focus({preventScroll:true}),20);announce('Panneau Accessibilité ouvert.');return true;
  }
  function closePanel(){
    if(!STATE.panel)return false;STATE.panel.classList.remove('open');STATE.panel.hidden=true;STATE.button?.setAttribute('aria-expanded','false');STATE.button?.focus({preventScroll:true});announce('Panneau Accessibilité fermé.');return true;
  }
  function togglePanel(){return STATE.panel&&!STATE.panel.hidden?closePanel():openPanel()}

  function improveSemantics(){
    qa('button:not([type])').forEach(b=>b.setAttribute('type','button'));
    const input=q('#messageInput');if(input&&!input.getAttribute('aria-label'))input.setAttribute('aria-label','Message à AURA');
    const send=q('#sendBtn');if(send&&!send.getAttribute('aria-label'))send.setAttribute('aria-label','Envoyer le message');
    qa('.aura-p0702-nav-btn').forEach(b=>{if(!b.getAttribute('aria-label')){const t=safe(b.textContent,60);if(t)b.setAttribute('aria-label',t)}});
  }
  function announceWorkspace(e){
    const id=safe(e?.detail?.workspace||window.AuraWorkspace?.current?.()||'',32);if(!id)return;
    const labels={home:'Accueil',talk:'Conversation',weather:'Météo',vitals:'Signes vitaux',maps:'Cartes',plan:'Tâches et agenda',system:'Diagnostics',memory:'Mémoire'};
    announce(`${labels[id]||id} ouvert.`);
  }
  function onKey(e){
    if(e.ctrlKey&&e.altKey&&!e.shiftKey&&e.key.toLowerCase()==='a'){e.preventDefault();togglePanel();return}
    if(e.key==='Escape'&&STATE.panel&&!STATE.panel.hidden){e.preventDefault();closePanel();return}
    if(e.key==='F6'&&!e.ctrlKey&&!e.altKey&&!e.metaKey){e.preventDefault();focusPrimary()}
  }

  function register(){
    ensureInfra();ensureButton();ensurePanel();improveSemantics();
    if(STATE.registered)return;
    STATE.registered=true;
    document.addEventListener('click',e=>{const b=e.target.closest?.('[data-module="accessibility"]');if(!b)return;e.preventDefault();e.stopImmediatePropagation();const pop=q('.aura-p0702-modules-popover');if(pop){pop.classList.remove('open');pop.hidden=true}openPanel()},true);
    document.addEventListener('keydown',onKey,true);
    window.addEventListener('aura:workspace-changed',announceWorkspace);
    window.addEventListener('aura:workspace-manager-ready',()=>{improveSemantics();ensureButton()});
    window.addEventListener('aura:conversation-drawer-opened',()=>announce('Conversation ouverte.'));
    window.addEventListener('aura:conversation-drawer-closed',()=>announce('Conversation fermée.'));
    mm?.addEventListener?.('change',()=>{if(STATE.settings.motion==='system')apply({save:false})});
    const mo=new MutationObserver(()=>{ensureButton();improveSemantics()});mo.observe(document.documentElement,{subtree:true,childList:true});
  }

  STATE.settings=load();register();apply({save:false,notify:false});
  window.AuraAccessibility=Object.freeze({
    version:VERSION,open:openPanel,close:closePanel,toggle:togglePanel,focusPrimary,
    get:()=>({...STATE.settings,resolvedMotion:resolvedMotion()}),
    set:(key,value)=>setSetting(safe(key,20),safe(value,20)),
    reset:()=>{STATE.settings=defaults();apply();return {...STATE.settings}},
    announce
  });
  emit('aura:accessibility-ready',{settings:{...STATE.settings},resolvedMotion:resolvedMotion(),features:['keyboard-focus','skip-navigation','reduced-motion','motion-off','high-contrast','text-scale','live-region']});
})();
