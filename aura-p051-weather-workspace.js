/* AURA P0.5.1 CONTEXTUAL WEATHER WORKSPACE */
(() => {
  'use strict';

  if (window.__AURA_P051_WEATHER__) return;
  window.__AURA_P051_WEATHER__ = true;

  const hero = document.querySelector('.hero');
  const stage = document.getElementById('stage');
  const messages = document.getElementById('messages');
  const talkBtn = document.getElementById('talkBtn');

  if (!hero || !stage) return;

  const clamp = (v,a=0,b=1) => Math.max(a,Math.min(b,v));
  const norm = s => String(s || '').replace(/\s+/g,' ').trim();

  const WX_RX = /\b(m[ée]t[ée]o|weather|temp[ée]rature|pr[ée]visions?|pluie|averses?|orage|neige|vent|rafales?|humidit[ée]|quel temps|temps fait|va[- ]t[- ]il faire)\b/i;

  let pendingWeather = null;
  let lastWeather = null;
  let active = false;
  let canvas = null;
  let ctx = null;
  let anim = 0;
  let lastFrame = 0;
  let particles = [];
  let visualLayer = 'wind';

  function svgIcon(type) {
    const common = `viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"`;
    const icons = {
      weather:`<svg ${common}><path d="M6 15.5a4.5 4.5 0 1 1 1.8-8.62A5.8 5.8 0 0 1 18.6 9.6 3.2 3.2 0 0 1 18 16H7"/><path d="M8 19h.01M12 19h.01M16 19h.01"/></svg>`,
      close:`<svg ${common}><path d="M6 6l12 12M18 6 6 18"/></svg>`,
      wind:`<svg ${common}><path d="M3 8h10c2.8 0 2.8-4 0-4-1.2 0-2 .5-2.5 1.4M3 12h15c3.5 0 3.5 5 0 5-1.4 0-2.3-.6-2.9-1.6M3 16h7"/></svg>`,
      drop:`<svg ${common}><path d="M12 3s5 5.8 5 10a5 5 0 0 1-10 0c0-4.2 5-10 5-10z"/></svg>`,
      humidity:`<svg ${common}><path d="M8 5s3 3.5 3 6a3 3 0 0 1-6 0c0-2.5 3-6 3-6zM16 9s3 3.5 3 6a3 3 0 0 1-6 0c0-2.5 3-6 3-6z"/></svg>`,
      thermometer:`<svg ${common}><path d="M10 14.8V5a2 2 0 1 1 4 0v9.8a4 4 0 1 1-4 0z"/><path d="M12 12v5"/></svg>`,
      pin:`<svg ${common}><path d="M12 21s6-5.2 6-11a6 6 0 1 0-12 0c0 5.8 6 11 6 11z"/><circle cx="12" cy="10" r="2"/></svg>`
    };
    return icons[type] || icons.weather;
  }

  function createWorkspace() {
    const root = document.createElement('section');
    root.id = 'auraWeatherWorkspace';
    root.className = 'aura-weather-workspace';
    root.setAttribute('aria-hidden','true');

    root.innerHTML = `
      <canvas class="aura-weather-field" aria-hidden="true"></canvas>
      <div class="aura-weather-map-grid" aria-hidden="true"></div>
      <div class="aura-weather-vignette" aria-hidden="true"></div>

      <header class="aura-weather-topbar">
        <div class="aura-weather-brand">
          <img src="/assets/AURA_LOGO_SYMBOL_NEON.svg?v=p051-20260816" alt="">
          <div>
            <span>CONTEXTUAL WORKSPACE</span>
            <strong>WEATHER</strong>
          </div>
        </div>
        <div class="aura-weather-status">
          <i></i><span id="auraWxStatus">AWAITING AURA DATA</span>
        </div>
        <button id="auraWxClose" class="aura-weather-close" aria-label="Fermer la météo">${svgIcon('close')}</button>
      </header>

      <section class="aura-weather-current">
        <div class="aura-weather-location">
          <span>${svgIcon('pin')}</span>
          <div><small>LOCATION</small><strong id="auraWxLocation">—</strong></div>
        </div>
        <div class="aura-weather-temperature">
          <strong id="auraWxTemp">—</strong><span id="auraWxDegree"></span>
        </div>
        <div class="aura-weather-condition" id="auraWxCondition">AURA WEATHER DATA REQUIRED</div>
        <div class="aura-weather-feels">RESSENTI <b id="auraWxFeels">—</b></div>
      </section>

      <section class="aura-weather-metrics">
        <article>
          <span>${svgIcon('wind')}</span>
          <small>WIND</small>
          <strong id="auraWxWind">—</strong>
        </article>
        <article>
          <span>${svgIcon('humidity')}</span>
          <small>HUMIDITY</small>
          <strong id="auraWxHumidity">—</strong>
        </article>
        <article>
          <span>${svgIcon('drop')}</span>
          <small>PRECIP.</small>
          <strong id="auraWxPrecip">—</strong>
        </article>
      </section>

      <div class="aura-weather-layers" role="group" aria-label="Couches météo">
        <button class="active" data-layer="wind">WIND</button>
        <button data-layer="precip">PRECIP</button>
        <button data-layer="clouds">CLOUDS</button>
      </div>

      <section class="aura-weather-synthesis glass">
        <header><span>AURA SYNTHESIS</span><b id="auraWxDataMode">NO DATA</b></header>
        <p id="auraWxSummary">Demande la météo à Aura. Le workspace affichera uniquement les informations présentes dans sa réponse.</p>
      </section>

      <section class="aura-weather-hourly glass">
        <header><span>STRUCTURED FORECAST</span><small id="auraWxHourlyLabel">AWAITING STRUCTURED HOURS</small></header>
        <div id="auraWxHourly" class="aura-weather-hourly-row">
          <div class="aura-weather-hour-empty">Aucune donnée horaire structurée reçue.</div>
        </div>
      </section>

      <footer class="aura-weather-foot">
        <span>ATMOSPHERIC FIELD · VISUAL LAYER</span>
        <span>DATA SOURCE · AURA CORE RESPONSE</span>
      </footer>
    `;

    hero.appendChild(root);

    canvas = root.querySelector('.aura-weather-field');
    ctx = canvas.getContext('2d',{alpha:true,desynchronized:true});

    root.querySelector('#auraWxClose').addEventListener('click', closeWeather);
    root.querySelectorAll('.aura-weather-layers button').forEach(btn => {
      btn.addEventListener('click', () => {
        root.querySelectorAll('.aura-weather-layers button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        visualLayer = btn.dataset.layer || 'wind';
      });
    });

    window.addEventListener('keydown', e => {
      if (e.key === 'Escape' && active) closeWeather();
    });

    if (typeof ResizeObserver !== 'undefined') {
      new ResizeObserver(resizeCanvas).observe(root);
    } else {
      window.addEventListener('resize',resizeCanvas,{passive:true});
    }
    resizeCanvas();
    initParticles();

    return root;
  }

  const root = createWorkspace();

  function createRailButton() {
    const btn = document.createElement('button');
    btn.id = 'auraWeatherBtn';
    btn.className = 'rail-btn aura-weather-rail-btn';
    btn.title = 'Météo contextuelle';
    btn.innerHTML = `<span>${svgIcon('weather')}</span><small>WX</small>`;
    btn.addEventListener('click', () => {
      if (active) closeWeather();
      else openWeather(lastWeather || {query:'Météo', loading:true});
    });

    if (talkBtn && talkBtn.parentElement) {
      talkBtn.insertAdjacentElement('afterend',btn);
    }
    return btn;
  }
  const railBtn = createRailButton();

  function resizeCanvas() {
    if (!canvas || !ctx) return;
    const r = root.getBoundingClientRect();
    const dpr = Math.min(1.35,Math.max(1,window.devicePixelRatio||1));
    canvas.width = Math.max(1,Math.round(r.width*dpr));
    canvas.height = Math.max(1,Math.round(r.height*dpr));
    canvas.style.width = r.width+'px';
    canvas.style.height = r.height+'px';
    ctx.setTransform(dpr,0,0,dpr,0,0);
  }

  function initParticles() {
    let seed = 0xA051;
    const rnd=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296};
    particles = Array.from({length:210},()=>({
      x:rnd(), y:rnd(),
      life:rnd(),
      speed:.15+rnd()*.55,
      phase:rnd()*Math.PI*2,
      width:.35+rnd()*.65
    }));
  }

  function renderField(now) {
    anim = requestAnimationFrame(renderField);
    if (!active || !ctx || now-lastFrame < 1000/30) return;
    lastFrame = now;

    const r = root.getBoundingClientRect();
    const w=r.width,h=r.height;
    if (w<2||h<2)return;
    const t=now/1000;
    ctx.clearRect(0,0,w,h);

    const parsed = lastWeather?.parsed || {};
    const windVal = Number(parsed.windNumber) || 0;
    const precipVal = Number(parsed.precipNumber) || 0;

    let speed = .20 + clamp(windVal/80,0,1)*.65;
    let alpha = .10;
    if(visualLayer==='precip'){speed=.16+clamp(precipVal/100,0,1)*.42;alpha=.12}
    if(visualLayer==='clouds'){speed=.10;alpha=.075}

    // Large smooth contour/isobar curves.
    ctx.save();
    ctx.globalCompositeOperation='lighter';
    for(let k=0;k<12;k++){
      const yy=h*(.10+k*.075);
      ctx.beginPath();
      for(let x=-40;x<=w+40;x+=18){
        const n1=Math.sin(x*.006+t*.11+k*.61);
        const n2=Math.sin(x*.013-t*.075+k*.27);
        const y=yy+n1*22+n2*9;
        if(x===-40)ctx.moveTo(x,y);else ctx.lineTo(x,y);
      }
      const hue = k%3===0 ? '99,243,255' : k%3===1 ? '155,92,255' : '218,92,255';
      ctx.strokeStyle=`rgba(${hue},${alpha*.22})`;
      ctx.lineWidth=.7;
      ctx.stroke();
    }
    ctx.restore();

    // Windy-like flow particles; decorative field, speed optionally derived from parsed wind.
    ctx.save();
    ctx.globalCompositeOperation='lighter';
    for(const p of particles){
      p.life += .004*p.speed*speed;
      if(p.life>1){p.life-=1;p.x=(p.x+.173)%1;p.y=(p.y+.419)%1}
      const baseX=(p.x + p.life*.34*speed)%1;
      const wave=Math.sin((p.y*8+t*.22+p.phase))*0.032 + Math.sin(baseX*12-t*.13)*.012;
      let x=baseX*w;
      let y=(p.y+wave)*h;
      let dx=(16+26*p.speed)*speed;
      let dy=Math.cos(p.phase+t*.25+p.y*4)*3;

      let rgb='99,243,255';
      if(visualLayer==='precip')rgb='155,92,255';
      if(visualLayer==='clouds')rgb='193,213,235';

      const grad=ctx.createLinearGradient(x-dx,y-dy,x,y);
      grad.addColorStop(0,`rgba(${rgb},0)`);
      grad.addColorStop(1,`rgba(${rgb},${alpha*(.45+.35*p.speed)})`);
      ctx.strokeStyle=grad;
      ctx.lineWidth=p.width;
      ctx.beginPath();ctx.moveTo(x-dx,y-dy);ctx.lineTo(x,y);ctx.stroke();
    }
    ctx.restore();

    // Location-centered atmospheric focus.
    const g=ctx.createRadialGradient(w*.56,h*.47,0,w*.56,h*.47,Math.min(w,h)*.34);
    const focusRgb=visualLayer==='precip'?'155,92,255':visualLayer==='clouds'?'145,180,215':'99,243,255';
    g.addColorStop(0,`rgba(${focusRgb},.055)`);
    g.addColorStop(.45,`rgba(${focusRgb},.018)`);
    g.addColorStop(1,`rgba(${focusRgb},0)`);
    ctx.fillStyle=g;
    ctx.fillRect(0,0,w,h);
  }
  anim = requestAnimationFrame(renderField);

  function inferLocation(query) {
    const q=norm(query).replace(/[?!.,]+$/,'');
    let m=q.match(/\b(?:à|a|pour|sur|dans|de)\s+([A-ZÀ-Ÿ][A-Za-zÀ-ÿ0-9'’ .-]{1,52})$/);
    if(m)return norm(m[1]);
    m=q.match(/\b(?:m[ée]t[ée]o|weather)\s+(?:à|a|pour|sur|de)?\s*([A-Za-zÀ-ÿ0-9'’ .-]{2,52})$/i);
    if(m)return norm(m[1]);
    return '';
  }

  function conditionFromText(text) {
    const t=text.toLowerCase();
    const table=[
      [/(orage|thunder)/,'ORAGE'],
      [/(neige|snow)/,'NEIGE'],
      [/(gr[êe]le|hail)/,'GRÊLE'],
      [/(averse|pluie|rain)/,'PLUIE'],
      [/(brouillard|brume|fog|mist)/,'BROUILLARD'],
      [/(tr[èe]s nuageux|couvert|overcast)/,'COUVERT'],
      [/(nuage|cloud)/,'NUAGEUX'],
      [/(ensoleill|soleil|sunny|clear|d[ée]gag[ée])/,'DÉGAGÉ']
    ];
    for(const [rx,label] of table)if(rx.test(t))return label;
    return 'CONDITIONS';
  }

  function parseWeather(text,query='') {
    const raw=norm(text);
    const parsed={raw};

    const tempMatches=[...raw.matchAll(/(-?\d{1,2}(?:[.,]\d)?)\s*°\s*C\b/gi)];
    if(tempMatches.length)parsed.temp=tempMatches[0][1].replace(',','.');

    let m=raw.match(/ressenti(?:e)?\s*(?:de|à|:)?\s*(-?\d{1,2}(?:[.,]\d)?)\s*°?\s*C?/i);
    if(m)parsed.feels=m[1].replace(',','.');

    m=raw.match(/humidit[ée]\s*(?:de|à|:)?\s*(\d{1,3})\s*%/i);
    if(m){parsed.humidity=m[1]+' %';parsed.humidityNumber=Number(m[1])}

    m=raw.match(/(?:vent|vents?)\s*(?:de|à|:|autour de)?\s*(\d{1,3}(?:[.,]\d)?)\s*km\s*\/?\s*h/i);
    if(!m)m=raw.match(/(\d{1,3}(?:[.,]\d)?)\s*km\s*\/?\s*h[^.]{0,28}\bvent/i);
    if(m){parsed.wind=m[1].replace(',','.')+' km/h';parsed.windNumber=Number(m[1].replace(',','.'))}

    m=raw.match(/(?:pr[ée]cipitations?|risque de pluie|pluie)\s*(?:de|à|:)?\s*(\d{1,3})\s*%/i);
    if(m){parsed.precip=m[1]+' %';parsed.precipNumber=Number(m[1])}

    parsed.condition=conditionFromText(raw);
    parsed.location=inferLocation(query);

    // Only create hourly cells when the answer explicitly associates a clock time with a temperature.
    const hourly=[];
    const hrx=/(?:\b(\d{1,2})(?:\s*h|:)(\d{2})?\b)[^°\n]{0,22}?(-?\d{1,2}(?:[.,]\d)?)\s*°\s*C/gi;
    let hm;
    while((hm=hrx.exec(raw)) && hourly.length<8){
      const hh=String(Number(hm[1])).padStart(2,'0');
      const mm=hm[2]||'00';
      hourly.push({time:`${hh}:${mm}`,temp:hm[3].replace(',','.')});
    }
    parsed.hourly=hourly;

    return parsed;
  }

  function setText(id,value,fallback='—'){
    const el=root.querySelector('#'+id);
    if(el)el.textContent=value || fallback;
  }

  function applyWeather(data) {
    lastWeather=data;
    const p=data.parsed || {};
    setText('auraWxLocation',p.location || inferLocation(data.query) || 'LOCATION NON STRUCTURÉE');
    setText('auraWxTemp',p.temp || '—');
    setText('auraWxDegree',p.temp ? '°C' : '');
    setText('auraWxCondition',p.condition || 'CONDITIONS');
    setText('auraWxFeels',p.feels ? p.feels+' °C' : '—');
    setText('auraWxWind',p.wind || '—');
    setText('auraWxHumidity',p.humidity || '—');
    setText('auraWxPrecip',p.precip || '—');
    setText('auraWxSummary',p.raw || 'Aucune synthèse Aura reçue.');
    setText('auraWxStatus',data.loading ? 'AURA RESEARCH IN PROGRESS' : 'AURA DATA READY');
    setText('auraWxDataMode',data.loading ? 'WAITING' : 'CORE RESPONSE');

    const status=root.querySelector('.aura-weather-status');
    status?.classList.toggle('ready',!data.loading);

    const hourly=root.querySelector('#auraWxHourly');
    const hourlyLabel=root.querySelector('#auraWxHourlyLabel');
    if(p.hourly?.length){
      hourly.innerHTML=p.hourly.map((h,i)=>`
        <article ${i===0?'class="active"':''}>
          <small>${h.time}</small>
          <i></i>
          <strong>${h.temp}°</strong>
        </article>`).join('');
      hourlyLabel.textContent=`${p.hourly.length} HEURES EXTRAITES`;
    } else {
      hourly.innerHTML='<div class="aura-weather-hour-empty">Aucune donnée horaire structurée dans la réponse Aura.</div>';
      hourlyLabel.textContent='NO STRUCTURED HOURS';
    }
  }

  function openWeather(data={}) {
    active=true;
    document.body.classList.add('aura-workspace-active','aura-weather-active');
    root.classList.add('open');
    root.setAttribute('aria-hidden','false');
    railBtn?.classList.add('active');

    const q=data.query||pendingWeather?.query||'';
    if(data.loading){
      applyWeather({
        query:q,
        loading:true,
        parsed:{
          location:inferLocation(q),
          condition:'RECHERCHE EN COURS',
          raw:'Aura recherche les conditions météo. Le workspace attend sa réponse Core sans effectuer de requête réseau parallèle.',
          hourly:[]
        }
      });
    } else if(data.parsed || data.text){
      const parsed=data.parsed || parseWeather(data.text,q);
      applyWeather({query:q,loading:false,parsed});
    } else if(lastWeather) {
      applyWeather(lastWeather);
    } else {
      applyWeather({
        query:q,loading:false,
        parsed:{
          location:inferLocation(q),
          condition:'AURA WEATHER DATA REQUIRED',
          raw:'Demande la météo à Aura. Les données affichées ici proviendront de sa réponse.',
          hourly:[]
        }
      });
    }

    resizeCanvas();
  }

  function closeWeather() {
    active=false;
    document.body.classList.remove('aura-weather-active','aura-workspace-active');
    root.classList.remove('open');
    root.setAttribute('aria-hidden','true');
    railBtn?.classList.remove('active');
  }

  // Public future-proof API for a later structured Core weather event.
  window.AURA_WORKSPACES = window.AURA_WORKSPACES || {};
  window.AURA_WORKSPACES.weather = {
    open(payload={}) {
      const query=payload.query||'';
      const parsed=payload.parsed || {
        location:payload.location||inferLocation(query),
        temp:payload.temperature ?? payload.temp,
        feels:payload.feels,
        condition:payload.condition,
        wind:payload.wind,
        windNumber:payload.windNumber,
        humidity:payload.humidity,
        humidityNumber:payload.humidityNumber,
        precip:payload.precipitation || payload.precip,
        precipNumber:payload.precipNumber,
        hourly:Array.isArray(payload.hourly)?payload.hourly:[],
        raw:payload.summary||payload.text||''
      };
      openWeather({query,loading:false,parsed});
    },
    close:closeWeather,
    parse:parseWeather
  };

  window.addEventListener('aura:workspace:weather',ev=>{
    window.AURA_WORKSPACES.weather.open(ev.detail||{});
  });

  function onNewMessage(row) {
    if (!(row instanceof HTMLElement) || !row.matches('.message')) return;
    const text=norm(row.querySelector('p')?.textContent || row.textContent);
    if(!text)return;

    if(row.classList.contains('user') && WX_RX.test(text)){
      pendingWeather={query:text,started:Date.now()};
      openWeather({query:text,loading:true});
      return;
    }

    if(row.classList.contains('aura') && pendingWeather){
      const age=Date.now()-pendingWeather.started;
      if(age <= 180000){
        const parsed=parseWeather(text,pendingWeather.query);
        openWeather({query:pendingWeather.query,loading:false,parsed});
        pendingWeather=null;
      }
    }
  }

  if(messages){
    const observer=new MutationObserver(muts=>{
      for(const m of muts)for(const n of m.addedNodes){
        if(n.nodeType===1){
          if(n.matches?.('.message'))onNewMessage(n);
          n.querySelectorAll?.('.message').forEach(onNewMessage);
        }
      }
    });
    observer.observe(messages,{childList:true,subtree:true});
  }
})();
