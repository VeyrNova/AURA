/* AURA P0.7.0.2 — LEFT RAIL IA NAVIGATION REFRESH
   Product-facing navigation layer over Workspace Manager v2.
   Legacy rail controls remain mounted but hidden so existing module owners keep their listeners.
*/
(()=>{
  'use strict';
  if(window.__AURA_P0702_LEFT_RAIL__)return;
  window.__AURA_P0702_LEFT_RAIL__=true;

  const VERSION='P0.7.0.2';
  const rail=document.querySelector('.rail');
  if(!rail)return;

  const svg=(name)=>({
    home:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v10h13V10"/><path d="M9.5 20v-6h5v6"/></svg>',
    chat:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 15a4 4 0 0 1-4 4H8l-5 3 1.6-4.3A7.5 7.5 0 0 1 3 13V9a6 6 0 0 1 6-6h7a5 5 0 0 1 5 5z"/><path d="M8 9h8M8 13h5"/></svg>',
    memory:'<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="5" rx="7" ry="3"/><path d="M5 5v6c0 1.7 3.1 3 7 3s7-1.3 7-3V5"/><path d="M5 11v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/><path d="M9 8.5h6"/></svg>',
    tasks:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4M16 3v4M8 12l2 2 5-5M8 17h7"/></svg>',
    calendar:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18M7 14h2M11 14h2M15 14h2M7 17h2M11 17h2"/></svg>',
    modules:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/><rect x="13" y="13" width="8" height="8" rx="1.5"/><path d="M7 6v2M17 6v2M6 17h2M16 17h2"/></svg>',
    diag:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 15V9M12 17V7M16 14v-4"/></svg>',
    settings:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21h-4v-.1A1.7 1.7 0 0 0 8.6 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.4H3v-4h.1A1.7 1.7 0 0 0 4.6 8.6a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V3h4v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9c.18.37.4.7.6 1 .3.28.68.42 1.1.42h.1v4h-.1A1.7 1.7 0 0 0 19.4 15z"/></svg>',
    map:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3z"/><path d="M9 3v15M15 6v15"/></svg>',
    weather:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 18h10a4 4 0 0 0 .6-8A6 6 0 0 0 6.3 8.5 4.5 4.5 0 0 0 7 18z"/><path d="M8 21h8"/></svg>',
    search:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/></svg>',
    file:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/></svg>',
    system:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="14" rx="2"/><path d="M8 21h8M12 18v3M7 9h3M7 13h6"/></svg>',
    user:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
    cube:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 2 8 4.5v9L12 22l-8-6.5v-9z"/><path d="m4 6.5 8 5 8-5M12 11.5V22"/><path d="m8 4.2 8 4.7"/></svg>'
  }[name]||'');

  const legacy=document.createElement('div');
  legacy.className='aura-p0702-legacy-rail-controls';
  const initial=[...rail.children];
  initial.forEach(node=>legacy.appendChild(node));
  rail.appendChild(legacy);

  const nav=document.createElement('nav');
  nav.className='aura-p0702-nav';
  nav.setAttribute('aria-label','Navigation AURA');
  const defs=[
    ['home','ACCUEIL','home'],['conversation','CONVERSATION','chat'],['memory','MÉMOIRE','memory'],
    ['tasks','TÂCHES','tasks'],['agenda','AGENDA','calendar'],['modules','MODULES','modules'],
    ['diagnostics','DIAGNOSTICS','diag'],['settings','PARAMÈTRES','settings']
  ];
  defs.forEach(([id,label,icon])=>{
    const b=document.createElement('button');b.type='button';b.className='aura-p0702-nav-btn';b.dataset.railTarget=id;
    b.innerHTML=`<span class="aura-p0702-icon">${svg(icon)}</span><b>${label}</b><i aria-hidden="true"></i>`;
    b.title=label.charAt(0)+label.slice(1).toLowerCase();nav.appendChild(b);
  });
  rail.appendChild(nav);

  const lower=document.createElement('div');lower.className='aura-p0702-lower';lower.innerHTML=`
    <button type="button" class="aura-p0702-profile" title="Profil AURA actif">
      <span>${svg('user')}</span><div><small>PROFIL</small><b>Standard</b></div><em>◆</em>
    </button>
    <div class="aura-p0702-core-card" role="status" aria-live="polite">
      <span class="aura-p0702-core-icon">${svg('cube')}</span>
      <div><b>AURA CORE</b><small>Noyau central</small><strong data-core-status>Opérationnel</strong></div><i>⌃</i>
    </div>`;
  rail.appendChild(lower);

  const pop=document.createElement('section');pop.className='aura-p0702-popover aura-p0702-modules-popover glass';pop.hidden=true;
  pop.innerHTML=`<header><div><small>AURA WORKSPACE</small><b>MODULES</b></div><button type="button" data-pop-close aria-label="Fermer">×</button></header>
    <div class="aura-p0702-module-grid">
      <button data-module="maps"><span>${svg('map')}</span><div><b>MAPS</b><small>Trajets · POI · Travel Brief</small></div></button>
      <button data-module="weather"><span>${svg('weather')}</span><div><b>MÉTÉO</b><small>Prévisions · carte météo</small></div></button>
      <button data-module="research"><span>${svg('search')}</span><div><b>RECHERCHE</b><small>Recherche IA avec sources</small></div></button>
      <button data-module="documents"><span>${svg('file')}</span><div><b>DOCUMENTS</b><small>Gerer, rechercher ou joindre un fichier</small></div></button><button data-module="notifications"><span>${svg('system')}</span><div><b>NOTIFICATIONS</b><small>Centre d'activite et alertes</small></div></button>
        <!-- AURA_V0922_MODULES_AGENDA_UI_BEGIN -->
        <button data-module="mail"><span>${svg('chat')}</span><div><b>MAIL</b><small>Courriels  recherche  brouillons  envoi</small></div></button>
        
<button data-module="contacts"><span>${svg('calendar')}</span><div><b>CONTACTS</b><small> Recherche & gestion </small></div></button>
        <!-- AURA_V0922_MODULES_AGENDA_UI_END -->
    </div>`;
  document.body.appendChild(pop);
  const mailPop=document.createElement('section');
  mailPop.className='aura-p0702-popover aura-p0702-mail-popover glass';
  mailPop.hidden=true;
  mailPop.innerHTML=`<header><div><small>AURA PERSONAL INTEGRATIONS</small><b>MAIL</b><span>MODE SYNTHETIQUE  backend AURA</span></div><button type="button" data-mail-close aria-label="Fermer">&times;</button></header>
    <div class="aura-p0702-module-grid aura-v0922-mail-actions">
      <button data-mail-action="inbox"><span>${svg('chat')}</span><div><b>BOITE DE RECEPTION</b><small>Afficher les mails de test</small></div></button>
      <button data-mail-action="search"><span>${svg('search')}</span><div><b>RECHERCHER</b><small>Rechercher dans les mails</small></div></button>
      <button data-mail-action="draft"><span>${svg('file')}</span><div><b>BROUILLON</b><small>Preparer un message</small></div></button>
      <button data-mail-action="send"><span>${svg('chat')}</span><div><b>ENVOYER</b><small>Confirmation AURA requise</small></div></button>
    </div>`;
  document.body.appendChild(mailPop);


  const settings=document.createElement('section');settings.className='aura-p0702-popover aura-p0702-settings-popover glass';settings.hidden=true;
  settings.innerHTML=`<header><div><small>AURA WORKSPACE</small><b>PARAMÈTRES</b></div><button type="button" data-pop-close aria-label="Fermer">×</button></header>
    <div class="aura-p0702-settings-body"><b>Configuration locale AURA</b><p>Le rail est prêt pour le workspace Paramètres final. Les réglages techniques existants restent inchangés afin de ne pas modifier le runtime validé.</p><div><span>Profil</span><strong>Standard</strong></div><div><span>Runtime</span><strong>Local + hybride</strong></div><div><span>Workspace</span><strong>P0.7</strong></div></div>`;
  document.body.appendChild(settings);

  let planSubmode='tasks';
  const manager=()=>window.AuraWorkspace;
  const q=s=>document.querySelector(s);
  const setActive=id=>nav.querySelectorAll('.aura-p0702-nav-btn').forEach(b=>b.classList.toggle('active',b.dataset.railTarget===id));
  const popOpen=el=>!!el&&!el.hidden;

  function positionPopover(el,button){
    if(!el||!button)return;
    const r=button.getBoundingClientRect();
    const max=Math.max(100,innerHeight-el.offsetHeight-18);
    el.style.top=`${Math.min(Math.max(96,r.top-8),max)}px`;
  }
  function openPopover(el,id,button){
    if(!el)return false;
    closePopover(pop,'modules',false);closePopover(settings,'settings',false);
    el.hidden=false;el.classList.add('open');positionPopover(el,button);
    manager()?.overlay?.open?.(`rail-${id}`);setActive(id);return true;
  }
  function closePopover(el,id,restore=true){
    if(!el||el.hidden)return false;
    el.classList.remove('open');el.hidden=true;
    manager()?.overlay?.close?.(`rail-${id}`);
    if(restore)syncActive();return true;
  }
  function registerOverlays(){
    const ov=manager()?.overlay;if(!ov?.register)return;
    ov.register({id:'rail-modules',label:'Modules',isOpen:()=>popOpen(pop),open:()=>{pop.hidden=false;pop.classList.add('open');return true},close:()=>{pop.classList.remove('open');pop.hidden=true;syncActive();return true}});
    ov.register({id:'rail-settings',label:'Paramètres',isOpen:()=>popOpen(settings),open:()=>{settings.hidden=false;settings.classList.add('open');return true},close:()=>{settings.classList.remove('open');settings.hidden=true;syncActive();return true}});
  }

  
  function composerInput(){
    return q('#messageInput')
      ||q('.workspace>.composer textarea')
      ||q('.workspace>.composer input[type="text"]')
      ||q('#composer textarea')
      ||q('#composer input[type="text"]');
  }

  function sendButtonFor(input){
    if(!input)return null;
    const root=input.closest('form,.composer,#composer')||document;
    return root.querySelector(
      'button[type="submit"],button.send,.send-button,[data-send],#sendButton'
    );
  }

  function personalCommand(text,autoSend=false){
    closePopover(mailPop,'mail',false);
    manager()?.open?.('talk');
    setTimeout(()=>{
      const input=composerInput();
      if(!input)return;
      input.focus({preventScroll:true});
      input.value=String(text||'');
      input.dispatchEvent(new Event('input',{bubbles:true}));
      input.dispatchEvent(new Event('change',{bubbles:true}));
      if(autoSend){
        const send=sendButtonFor(input);
        if(send&&!send.disabled)send.click();
      }
    },70);
  }

  function openMailModule(){
    closePopover(pop,'modules',false);
    closePopover(settings,'settings',false);
    mailPop.hidden=false;
    mailPop.classList.add('open');
    positionPopover(
      mailPop,
      nav.querySelector('[data-rail-target="modules"]')
    );
    setActive('modules');
  }

  function ensureAgendaCalendarBridge(){
    if(q('.aura-p0623-drawer [data-tab="calendar"]'))return false;
    if(planSubmode!=='agenda')return false;
    const drawer=q('.aura-p0623-drawer');
    if(!drawer)return false;

    let box=drawer.querySelector('[data-aura-calendar-bridge]');
    if(!box){
      box=document.createElement('section');
      box.className='aura-v0922-agenda-calendar-bridge';
      box.setAttribute('data-aura-calendar-bridge','v0.9.2.2');
      box.innerHTML=`<div class="aura-v0922-agenda-calendar-head">
          <div><small>AURA PERSONAL INTEGRATIONS</small><b>CALENDRIER</b><span>CalendarProvider  mode synthetique</span></div>
        </div>
        <div class="aura-v0922-agenda-calendar-actions">
          <button type="button" data-calendar-action="events">RENDEZ-VOUS</button>
          <button type="button" data-calendar-action="freebusy">DISPONIBILITE</button>
          <button type="button" data-calendar-action="create">CREER UN EVENEMENT</button>
        </div>
        <p>Le calendrier reste integre a AGENDA. Les taches restent gerees dans TACHES.</p>`;

      box.addEventListener('click',event=>{
        const button=event.target.closest('[data-calendar-action]');
        if(!button)return;
        const action=button.dataset.calendarAction;
        if(action==='events'){
          personalCommand('quels sont mes prochains rendez-vous',true);
        }else if(action==='freebusy'){
          personalCommand('suis-je libre demain entre 14h et 16h',true);
        }else if(action==='create'){
          personalCommand('cree un rendez-vous demain a 18h intitule Test AURA',false);
        }
      });

      const content=drawer.querySelector('.aura-p0623-content');
      if(content)drawer.insertBefore(box,content);
      else drawer.appendChild(box);
    }

    box.hidden=false;
    return true;
  }

function openPlan(mode){
    planSubmode=mode==='agenda'?'agenda':'tasks';
    manager()?.open?.('plan');
    setTimeout(()=>{
      const sel=planSubmode==='agenda'?'.aura-p0623-drawer [data-tab="calendar"]':'.aura-p0623-drawer [data-tab="tasks"]';
      q(sel)?.click();setActive(planSubmode);if(planSubmode==='agenda')setTimeout(ensureAgendaCalendarBridge,20);
    },35);
  }
  function openResearch(){
    manager()?.open?.('talk');
    setTimeout(()=>{
      const input=q('#messageInput');if(!input)return;
      input.focus({preventScroll:true});
      if(!String(input.value||'').trim())input.placeholder='Recherche : pose ta question à AURA…';
    },45);
  }
  function openDocuments(){
  closePopover(pop,'modules');
  manager()?.open?.('talk');
  setTimeout(()=>{
    const input=composerInput();
    if(!input)return;
    input.focus({preventScroll:true});
    if(!String(input.value||'').trim()){
      input.value='liste mes fichiers';
      input.dispatchEvent(new Event('input',{bubbles:true}));
      input.dispatchEvent(new Event('change',{bubbles:true}));
    }
  },45);
}

  function openNotifications(){
    closePopover(pop,'modules');
    const ew=window.AuraEventWatchers;
    if(ew&&typeof ew.open==='function'){
      try{if(ew.open()!==false)return true}catch(_error){}
    }
    manager()?.open?.('talk');
    setTimeout(()=>{
      const input=composerInput();
      if(!input)return;
      input.focus({preventScroll:true});
      if(!String(input.value||'').trim()){
        input.value='affiche mes notifications';
        input.dispatchEvent(new Event('input',{bubbles:true}));
        input.dispatchEvent(new Event('change',{bubbles:true}));
      }
    },45);
    return false;
  }

  pop.addEventListener('click',(event)=>{
    const button=event.target.closest('button[data-module="notifications"]');
    if(!button||!pop.contains(button))return;
    event.preventDefault();
    event.stopPropagation();
    openNotifications();
  },true);

  nav.addEventListener('click',event=>{
    const b=event.target.closest('.aura-p0702-nav-btn');if(!b)return;
    const id=b.dataset.railTarget;
    if(id==='home'){closePopover(pop,'modules',false);closePopover(settings,'settings',false);manager()?.home?.();return}
    if(id==='conversation'){manager()?.open?.('talk');return}
    if(id==='memory'){manager()?.open?.('memory');return}
    if(id==='tasks'){openPlan('tasks');return}
    if(id==='agenda'){openPlan('agenda');return}
    if(id==='modules'){if(popOpen(pop))closePopover(pop,'modules');else openPopover(pop,'modules',b);return}
    if(id==='diagnostics'){manager()?.open?.('system');return}
    if(id==='settings'){if(popOpen(settings))closePopover(settings,'settings');else openPopover(settings,'settings',b);return}
  });

  pop.addEventListener('click',event=>{
    if(event.target.closest('[data-pop-close]')){closePopover(pop,'modules');return}
    const b=event.target.closest('[data-module]');if(!b)return;
    const id=b.dataset.module;closePopover(pop,'modules',false);
    if(id==='maps')manager()?.open?.('maps');
    else if(id==='weather')manager()?.open?.('weather');
    else if(id==='system')manager()?.open?.('system');
    else if(id==='research')openResearch();
    else if(id==='documents')openDocuments();
    else if(id==='mail')openMailModule();
    else if(id==='agenda')openPlan('agenda');
  });
  
  mailPop.addEventListener('click',event=>{
    if(event.target.closest('[data-mail-close]')){
      closePopover(mailPop,'mail');
      return;
    }
    const button=event.target.closest('[data-mail-action]');
    if(!button)return;
    const action=button.dataset.mailAction;
    if(action==='inbox'){
      personalCommand('affiche mes mails',true);
    }else if(action==='search'){
      personalCommand('cherche mes mails sur ',false);
    }else if(action==='draft'){
      personalCommand('prepare un brouillon de mail a ',false);
    }else if(action==='send'){
      personalCommand('envoie un mail a ',false);
    }
  });
settings.addEventListener('click',e=>{if(e.target.closest('[data-pop-close]'))closePopover(settings,'settings')});

  document.addEventListener('click',event=>{
    const tab=event.target.closest('.aura-p0623-drawer [data-tab]');
    if(tab){if(tab.dataset.tab==='tasks')planSubmode='tasks';if(tab.dataset.tab==='calendar'||tab.dataset.tab==='reminders')planSubmode='agenda';setTimeout(()=>{syncActive();if(planSubmode==='agenda')ensureAgendaCalendarBridge();},0)}
    if(popOpen(pop)&&!event.target.closest('.aura-p0702-modules-popover')&&!event.target.closest('[data-rail-target="modules"]'))closePopover(pop,'modules');
    if(popOpen(settings)&&!event.target.closest('.aura-p0702-settings-popover')&&!event.target.closest('[data-rail-target="settings"]'))closePopover(settings,'settings'); if(popOpen(mailPop)&&!event.target.closest('.aura-p0702-mail-popover')&&!event.target.closest('[data-module="mail"]'))closePopover(mailPop,'mail');
  },true);

  function syncActive(){
    if(popOpen(settings)){setActive('settings');return}
    if(popOpen(pop)){setActive('modules');return}
    const current=manager()?.current?.()||document.body.dataset.auraWorkspace||'home';
    if(current==='talk')setActive('conversation');
    else if(current==='memory')setActive('memory');
    else if(current==='plan')setActive(planSubmode);
    else if(current==='system')setActive('diagnostics');
    else if(current==='maps'||current==='weather')setActive('modules');
    else setActive('home');
  }

  function sweepLegacy(){
    [...rail.children].forEach(node=>{
      if(node===legacy||node===nav||node===lower)return;
      if(node.matches?.('.rail-btn,.rail-spacer'))legacy.appendChild(node);
    });
  }
  const mo=new MutationObserver(()=>sweepLegacy());mo.observe(rail,{childList:true});
  window.addEventListener('aura:workspace-changed',syncActive);
  window.addEventListener('resize',()=>{if(popOpen(pop))positionPopover(pop,nav.querySelector('[data-rail-target="modules"]'));if(popOpen(settings))positionPopover(settings,nav.querySelector('[data-rail-target="settings"]'))});

  function syncCoreStatus(){
    const out=lower.querySelector('[data-core-status]');if(!out)return;
    const text=String(q('#coreChip')?.textContent||q('#stateText')?.textContent||'').toUpperCase();
    out.textContent=/LINKED|READY|IDLE|OPERATION/.test(text)?'Opérationnel':(/CONNECT|WARM|BOOT/.test(text)?'Initialisation':'Local actif');
  }
  const core=q('#coreChip'),state=q('#stateText');
  if(core||state){const sm=new MutationObserver(syncCoreStatus);if(core)sm.observe(core,{childList:true,subtree:true,characterData:true});if(state)sm.observe(state,{childList:true,subtree:true,characterData:true})}

  // Overlay API can appear a few milliseconds after this asset in custom shells.
  registerOverlays();setTimeout(registerOverlays,40);setTimeout(registerOverlays,180);
  sweepLegacy();syncCoreStatus();syncActive();
  document.documentElement.dataset.auraRail='p0702';
  window.dispatchEvent(new CustomEvent('aura:left-rail-ready',{detail:{version:VERSION}}));
})();

// AURA V0.9.3 CONTACTS MODULE VISUAL EXPOSURE
// Visual launcher only. Backend/runtime authority stays in
// PersonalIntegrationDispatcher -> ContactsProvider.
(() => {
  const CONTACTS_SELECTOR = '[data-module="contacts"]';
  const CONTACTS_PROMPT = 'cherche mes contacts';

  const openContactsConversation = () => {
    try {
      const workspace = window.AuraWorkspace;
      workspace?.open?.('talk');
    } catch (_) {}

    window.setTimeout(() => {
      const candidates = [
        '#composer textarea',
        '#composer input[type="text"]',
        '[data-aura-composer] textarea',
        '[data-aura-composer] input',
        '.aura-composer textarea',
        '.aura-composer input',
        'textarea[name="message"]',
        'input[name="message"]'
      ];

      let field = null;

      for (const selector of candidates) {
        field = document.querySelector(selector);
        if (field) break;
      }

      if (!field) return;

      const prototype = Object.getPrototypeOf(field);
      const descriptor = Object.getOwnPropertyDescriptor(
        prototype,
        'value'
      );

      if (descriptor?.set) {
        descriptor.set.call(field, CONTACTS_PROMPT);
      } else {
        field.value = CONTACTS_PROMPT;
      }

      field.dispatchEvent(
        new Event('input', { bubbles: true })
      );
      field.dispatchEvent(
        new Event('change', { bubbles: true })
      );
      field.focus();
    }, 120);
  };

  document.addEventListener(
    'click',
    (event) => {
      const target = event.target?.closest?.(CONTACTS_SELECTOR);
      if (!target) return;

      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();

      const popover = target.closest('.aura-p0702-modules-popover');
      const close = popover?.querySelector?.('[data-pop-close]');

      try {
        close?.click?.();
      } catch (_) {}

      openContactsConversation();
    },
    true
  );
})();

// AURA V0.9.4 D2 R7 DOCUMENTS FILES VISUAL REBUILD

// AURA V0.9.5 D2 R3 NOTIFICATIONS ACTIVITY CENTER VISUAL ROUTING
