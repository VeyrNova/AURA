/* AURA P0.7.0.1 COMMAND PALETTE ADAPTIVE BASELINE + MAPS WORKSPACE */
/* AURA P0.6.4.0.1 — Command Palette Shortcut Isolation
   UI-only navigation layer. No LLM, Core or security-path changes.
*/
(()=>{
  'use strict';

  const workspace=document.querySelector('.workspace');
  if(!workspace)return;

  const palette=document.createElement('section');
  palette.className='aura-p0635-palette glass';
  palette.setAttribute('role','dialog');
  palette.setAttribute('aria-modal','true');
  palette.setAttribute('aria-label','Commandes workspace AURA');
  palette.innerHTML=`
    <header>
      <div><i></i><b>COMMAND PALETTE</b><span>WORKSPACE LOCAL</span></div>
      <kbd>ESC</kbd>
    </header>
    <label>
      <span>⌕</span>
      <input data-search autocomplete="off" spellcheck="false" placeholder="Ouvrir un workspace ou lancer une action…" />
    </label>
    <div data-list class="aura-p0635-list"></div>
    <footer>
      <span>↑ ↓ naviguer</span>
      <span>↵ exécuter</span>
      <b>CTRL + K</b>
    </footer>`;
  workspace.appendChild(palette);

  const search=palette.querySelector('[data-search]');
  const list=palette.querySelector('[data-list]');

  const ITEMS=[
    {id:'home',label:'HOME',detail:'Retourner à l’accueil AURA',keywords:'accueil home retour',action:()=>window.AuraWorkspace?.home?.()},
    {id:'talk',label:'TALK',detail:'Ouvrir la Conversation complète',keywords:'conversation parler talk',action:()=>window.AuraWorkspace?.open?.('talk')},
    {id:'plan',label:'PLAN',detail:'Tâches · rappels · notes',keywords:'plan tâches taches rappels notes productivité productivite',action:()=>window.AuraWorkspace?.open?.('plan')},
    {id:'weather',label:'WEATHER',detail:'Météo et localisation',keywords:'weather météo meteo localisation',action:()=>window.AuraWorkspace?.open?.('weather')},
    {id:'maps',label:'MAPS',detail:'Cartes · itinéraires · POI · météo trajet',keywords:'maps carte cartes navigation itineraire itinéraire route trajet poi',action:()=>window.AuraWorkspace?.open?.('maps')},
    {id:'memory',label:'MEM',detail:'Mémoire locale AURA',keywords:'mem mémoire memoire souvenirs',action:()=>window.AuraWorkspace?.open?.('memory')},
    {id:'system',label:'SYS',detail:'Système · sécurité · actions locales',keywords:'sys system système securite sécurité',action:()=>window.AuraWorkspace?.open?.('system')},
    {id:'refresh',label:'ACTUALISER',detail:'Rafraîchir le workspace courant',keywords:'refresh actualiser rafraichir mettre a jour',conditional:true,action:()=>{
      const current=window.AuraWorkspace?.current?.()||'home';
      if(['plan','weather','memory','system'].includes(current)){
        window.dispatchEvent(new CustomEvent('aura:workspace-refresh',{
          detail:{workspace:current,source:'command-palette'}
        }));
      }
    }},
    {id:'close',label:'FERMER',detail:'Fermer le workspace courant',keywords:'fermer close quitter retour home',conditional:true,action:()=>{
      const current=window.AuraWorkspace?.current?.()||'home';
      if(current!=='home')window.AuraWorkspace?.close?.(current);
    }},
  ];

  let open=false;
  let visible=[];
  let selected=0;
  let previousFocus=null;

  const normalize=text=>String(text||'')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g,'')
    .toLowerCase()
    .trim();

  function current(){
    return String(window.AuraWorkspace?.current?.()||document.body.dataset.auraWorkspace||'home');
  }

  function availableItems(){
    const active=current();
    return ITEMS.filter(item=>{
      if(!item.conditional)return true;
      if(item.id==='refresh')return ['plan','weather','memory','system'].includes(active);
      if(item.id==='close')return active!=='home';
      return true;
    });
  }

  function icon(id){
    return ({
      home:'⌂',talk:'◉',plan:'✓',weather:'☁',maps:'⌖',memory:'◇',
      system:'▦',refresh:'↻',close:'×'
    })[id]||'•';
  }

  function render(){
    const query=normalize(search.value);
    visible=availableItems().filter(item=>{
      if(!query)return true;
      return normalize(`${item.label} ${item.detail} ${item.keywords}`).includes(query);
    });
    if(selected>=visible.length)selected=Math.max(0,visible.length-1);

    list.innerHTML=visible.length
      ?visible.map((item,index)=>`
        <button data-index="${index}" class="${index===selected?'selected':''}">
          <i>${icon(item.id)}</i>
          <div><b>${item.label}</b><span>${item.detail}</span></div>
          ${item.id===current()?'<em>ACTIF</em>':''}
        </button>`).join('')
      :'<div class="aura-p0635-empty">Aucune commande locale correspondante.</div>';

    list.querySelector('.selected')?.scrollIntoView({block:'nearest'});
  }

  function openPalette(){
    if(open)return;
    open=true;
    previousFocus=document.activeElement;
    search.value='';
    selected=0;
    palette.classList.add('open');
    document.body.classList.add('aura-command-palette-open');
    render();
    setTimeout(()=>search.focus({preventScroll:true}),0);
  }

  function closePalette({restore=true}={}){
    if(!open)return;
    open=false;
    palette.classList.remove('open');
    document.body.classList.remove('aura-command-palette-open');
    if(restore){
      setTimeout(()=>{
        try{previousFocus?.focus?.({preventScroll:true})}catch{previousFocus?.focus?.()}
      },0);
    }
  }

  function execute(index=selected){
    const item=visible[index];
    if(!item)return;
    closePalette({restore:false});
    try{item.action()}catch{}
  }

  document.addEventListener('keydown',event=>{
    // Ctrl+K belongs exclusively to Command Palette.
    // Ctrl+Shift+K is reserved for Router Observatory.
    if((event.ctrlKey||event.metaKey)&&!event.shiftKey&&event.key.toLowerCase()==='k'){
      event.preventDefault();
      event.stopImmediatePropagation();
      open?closePalette():openPalette();
      return;
    }
    if(!open)return;

    if(event.key==='Escape'){
      event.preventDefault();
      event.stopImmediatePropagation();
      closePalette();
      return;
    }
    if(event.key==='ArrowDown'){
      event.preventDefault();
      selected=Math.min(Math.max(0,visible.length-1),selected+1);
      render();
      return;
    }
    if(event.key==='ArrowUp'){
      event.preventDefault();
      selected=Math.max(0,selected-1);
      render();
      return;
    }
    if(event.key==='Enter'){
      event.preventDefault();
      execute();
    }
  },true);

  search.addEventListener('input',()=>{
    selected=0;
    render();
  });

  list.addEventListener('mousemove',event=>{
    const button=event.target.closest('button[data-index]');
    if(!button)return;
    const index=Number(button.dataset.index);
    if(Number.isInteger(index)&&index!==selected){
      selected=index;
      render();
    }
  });

  list.addEventListener('click',event=>{
    const button=event.target.closest('button[data-index]');
    if(!button)return;
    execute(Number(button.dataset.index));
  });

  palette.addEventListener('mousedown',event=>{
    if(event.target===palette)closePalette();
  });

  window.addEventListener('aura:workspace-changed',()=>{
    if(open)render();
  });

  window.AuraCommandPalette=Object.freeze({
    open:openPalette,
    close:closePalette,
    isOpen:()=>open,
  });
})();
