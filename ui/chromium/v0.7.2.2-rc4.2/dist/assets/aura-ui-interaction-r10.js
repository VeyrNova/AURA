(() => {
  if (window.__AURA_R10_SEMANTIC_DOCK__) return;
  window.__AURA_R10_SEMANTIC_DOCK__ = true;

  const ICONS = {
    home:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 10.5 12 3.7l8.5 6.8"/><path d="M5.5 9.5V20h13V9.5"/><path d="M9.5 20v-6h5v6"/></svg>',
    conversation:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5.5h14v10H9l-4 3v-13Z"/><path d="M8 9h8M8 12h5"/></svg>',
    memory:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5.5" rx="6.5" ry="2.5"/><path d="M5.5 5.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"/><path d="M5.5 10.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"/></svg>',
    tasks:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="4.5" width="14" height="16" rx="2"/><path d="M9 4.5v-1h6v1"/><path d="m8.5 12 2 2 5-5"/></svg>',
    agenda:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4.5" y="6" width="15" height="14" rx="2"/><path d="M8 3.5V8M16 3.5V8M4.5 10h15"/><path d="M8 14h3M13 14h3M8 17h3"/></svg>',
    modules:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></svg>',
    music:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V7l9-2v11"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="15.5" cy="16" r="2.5"/></svg>',
    'aura-live':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 14v-4M12 16V8M15 13v-2"/></svg>',
    diagnostics:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="16" height="12" rx="2"/><path d="M8 20h8M12 17v3"/><path d="M7.5 12h2l1.2-3 2.1 6 1.2-3h2.5"/></svg>',
    settings:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19 13.5v-3l-2-.6a7 7 0 0 0-.7-1.7l1-1.8-2.1-2.1-1.8 1a7 7 0 0 0-1.7-.7L11 2.5H8l-.6 2.1a7 7 0 0 0-1.7.7l-1.8-1-2.1 2.1 1 1.8a7 7 0 0 0-.7 1.7L.5 10.5v3l2.1.6c.2.6.4 1.2.7 1.7l-1 1.8 2.1 2.1 1.8-1c.5.3 1.1.5 1.7.7l.6 2.1h3l.6-2.1c.6-.2 1.2-.4 1.7-.7l1.8 1 2.1-2.1-1-1.8c.3-.5.5-1.1.7-1.7l2.1-.6Z" transform="scale(.82) translate(2.7 2.7)"/></svg>'
  };

  /* Exact semantic routing.
     Do NOT route by index: P0702 owns 9 targets and Music is injected separately. */
  const ITEMS = [
    {id:'home',         label:'Accueil',       selector:'.aura-p0702-nav-btn[data-rail-target="home"]'},
    {id:'conversation', label:'Conversation',  selector:'.aura-p0702-nav-btn[data-rail-target="conversation"]'},
    {id:'memory',       label:'Mémoire',        selector:'.aura-p0702-nav-btn[data-rail-target="memory"]'},
    {id:'tasks',        label:'Tâches',         selector:'.aura-p0702-nav-btn[data-rail-target="tasks"]'},
    {id:'agenda',       label:'Agenda',         selector:'.aura-p0702-nav-btn[data-rail-target="agenda"]'},
    {id:'modules',      label:'Modules',        selector:'.aura-p0702-nav-btn[data-rail-target="modules"]'},
    {id:'music',        label:'Musique',        selector:'#aura-music-nav-v180'},
    {id:'aura-live',    label:'AURA Live',      selector:'.aura-p0702-nav-btn[data-rail-target="aura-live"]'},
    {id:'diagnostics',  label:'Diagnostics',    selector:'.aura-p0702-nav-btn[data-rail-target="diagnostics"]'},
    {id:'settings',     label:'Paramètres',     selector:'.aura-p0702-nav-btn[data-rail-target="settings"]'}
  ];

  function bindLens(el){
    if(!el || el.dataset.auraR10Lens === '1') return;
    el.dataset.auraR10Lens = '1';

    el.addEventListener('pointermove', event => {
      const r = el.getBoundingClientRect();
      if(!r.width || !r.height) return;
      const x = Math.max(0,Math.min(100,((event.clientX-r.left)/r.width)*100));
      const y = Math.max(0,Math.min(100,((event.clientY-r.top)/r.height)*100));
      el.style.setProperty('--gx',`${x.toFixed(1)}%`);
      el.style.setProperty('--gy',`${y.toFixed(1)}%`);
    });

    el.addEventListener('pointerleave',() => {
      el.style.setProperty('--gx','50%');
      el.style.setProperty('--gy','50%');
    });
  }

  function resolve(item){
    return document.querySelector(item.selector);
  }

  function inferActive(){
    const music = document.getElementById('aura-music-player-v180');
    if(music?.classList.contains('open')) return 'music';

    const active = document.querySelector('.aura-p0702-nav-btn.active[data-rail-target]');
    if(active?.dataset?.railTarget) return active.dataset.railTarget;

    const w = String(document.body?.dataset?.auraWorkspace || '').toLowerCase();
    if(w === 'talk') return 'conversation';
    if(w === 'memory') return 'memory';
    if(w === 'aura-live') return 'aura-live';
    if(w === 'system') return 'diagnostics';
    if(w === 'maps' || w === 'weather') return 'modules';
    if(w === 'plan'){
      const agenda = document.querySelector('.aura-p0702-nav-btn.active[data-rail-target="agenda"]');
      return agenda ? 'agenda' : 'tasks';
    }

    return 'home';
  }

  function panelIsOpen(){
    const w = String(document.body?.dataset?.auraWorkspace || '').toLowerCase();
    if(w && w !== 'home') return true;

    const selectors = [
      '.aura-p0702-popover.open:not([hidden])',
      '.aura-p0623-drawer.open',
      '.aura-p0626-memory.open',
      '.aura-p0627-system.open',
      '.aura-p0712-conversation-drawer.open:not([hidden])',
      '.aura-navigation-workspace.open',
      '.aura-weather-workspace.open',
      '#aura-music-player-v180.open'
    ];

    return selectors.some(sel => document.querySelector(sel));
  }

  function syncDock(){
    const dock = document.getElementById('auraR10Dock');
    if(!dock) return;

    const active = inferActive();
    dock.querySelectorAll('.aura-r10-dock-btn').forEach(btn => {
      btn.classList.toggle('is-active',btn.dataset.r10Id === active);
    });

    dock.classList.toggle('aura-r10-panel-mode',panelIsOpen());
  }

  function buildDock(){
    if(document.getElementById('auraR10Dock')) return true;

    /* Wait for P0702 to create its semantic nav before mounting R10. */
    const semanticHome = document.querySelector('.aura-p0702-nav-btn[data-rail-target="home"]');
    if(!semanticHome) return false;

    const dock = document.createElement('nav');
    dock.id = 'auraR10Dock';
    dock.setAttribute('aria-label','Navigation AURA');

    ITEMS.forEach(item => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'aura-r10-dock-btn';
      b.dataset.r10Id = item.id;
      b.title = item.label;
      b.setAttribute('aria-label',item.label);

      const icon = document.createElement('span');
      icon.className = 'aura-r10-dock-icon';
      icon.setAttribute('aria-hidden','true');
      icon.innerHTML = ICONS[item.id];

      const label = document.createElement('span');
      label.className = 'aura-r10-dock-label';
      label.setAttribute('aria-hidden','true');
      label.textContent = item.label;

      b.append(icon,label);

      b.addEventListener('click',() => {
        const target = resolve(item);

        if(!target){
          const toast = document.getElementById('toast');
          if(toast){
            toast.textContent = `${item.label} n'est pas encore disponible.`;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'),1800);
          }
          return;
        }

        target.click();
        setTimeout(syncDock,25);
        setTimeout(syncDock,120);
      });

      dock.appendChild(b);
    });

    document.body.appendChild(dock);
    bindLens(dock);
    syncDock();
    return true;
  }

  function setupComposer(){
    const composer = document.querySelector('#composer') || document.querySelector('.composer');
    const input = document.querySelector('#messageInput');
    if(!composer || !input) return;

    bindLens(composer);

    if(composer.dataset.auraR10Bound === '1') return;
    composer.dataset.auraR10Bound = '1';

    const sync = () => {
      const writing =
        document.activeElement === input ||
        Boolean(String(input.value || '').trim());

      composer.classList.toggle('aura-r10-writing',writing);
    };

    input.addEventListener('focus',sync);
    input.addEventListener('blur',() => setTimeout(sync,30));
    input.addEventListener('input',sync);
    sync();
  }

  function installObservers(){
    if(document.documentElement.dataset.auraR10Observers === '1') return;
    document.documentElement.dataset.auraR10Observers = '1';

    window.addEventListener('aura:workspace-changed',() => setTimeout(syncDock,0));

    const body = document.body;
    if(body){
      const bodyObserver = new MutationObserver(syncDock);
      bodyObserver.observe(body,{
        attributes:true,
        attributeFilter:['data-aura-workspace','class'],
        childList:true,
        subtree:false
      });
    }

    /* P0702 active classes are the navigation authority. */
    const nav = document.querySelector('.aura-p0702-nav');
    if(nav){
      const navObserver = new MutationObserver(syncDock);
      navObserver.observe(nav,{
        attributes:true,
        attributeFilter:['class'],
        subtree:true
      });
    }

    /* Low-cost fallback for Music open/close and product drawers. */
    setInterval(syncDock,500);
  }

  function boot(){
    setupComposer();

    if(buildDock()){
      installObservers();
      return;
    }

    let attempts = 0;
    const timer = setInterval(() => {
      attempts += 1;
      setupComposer();

      if(buildDock() || attempts > 40){
        clearInterval(timer);
        installObservers();
      }
    },100);
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded',boot,{once:true});
  }else{
    boot();
  }
})();
