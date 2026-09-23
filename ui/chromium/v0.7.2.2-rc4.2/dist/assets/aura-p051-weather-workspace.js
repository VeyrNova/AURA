/* AURA P0.5.1 CONTEXTUAL WEATHER WORKSPACE */
/* AURA P0.5.1.1 ROBUST WEATHER CONVERSATION BRIDGE */
/* AURA P0.5.1.4 RUNTIME DOM BOOTSTRAP FIX */
/* AURA P0.5.1.5 WEATHER ROOT TDZ FIX */
/* AURA P0.5.1.7 LOCATION PARSER + WEATHER UI POLISH */
/* AURA P0.5.1.8 CANONICAL CORE WEATHER PAYLOAD BRIDGE */
/* AURA P0.5.1.9 UNICODE LOCATION + COMPACT CURRENT CONDITIONS FIX */
/* AURA P0.5.2.3.2 WEATHER ERROR RECOVERY */
/* AURA P0.5.2.8.6.1 WEATHER SOFT TIMEOUT RECOVERY */
(() => {
  'use strict';

  // Bootstrap lock is separate from the actual workspace lock.
  // P0.5.1.1 incorrectly set the workspace lock before the RC4.2 DOM existed,
  // then returned forever. P0.5.1.4 retries until the real HERO is ready.
  if (window.__AURA_P051_WEATHER_BOOTSTRAP__) return;
  window.__AURA_P051_WEATHER_BOOTSTRAP__ = true;

  let auraP051BootAttempts = 0;
  let auraP051BootTimer = 0;

  function auraP051StartWhenReady() {
    if (window.__AURA_P051_WEATHER__) return true;

    const hero = document.querySelector('.hero');
    const stage = document.getElementById('stage');

    if (!hero || !stage || !hero.isConnected || !stage.isConnected) {
      auraP051BootAttempts++;
      if (auraP051BootAttempts < 240) {
        clearTimeout(auraP051BootTimer);
        auraP051BootTimer = window.setTimeout(auraP051StartWhenReady, 100);
      }
      return false;
    }

    // IMPORTANT: only now is the workspace considered initialized.
    window.__AURA_P051_WEATHER__ = true;

    const messages = document.getElementById('messages');
    const talkBtn = document.getElementById('talkBtn');

    auraP051Initialize(hero, stage, messages, talkBtn);
    document.documentElement.dataset.auraWeatherWorkspace = 'ready';
    return true;
  }

  function auraP051Initialize(hero, stage, messages, talkBtn) {

    const clamp = (v,a=0,b=1) => Math.max(a,Math.min(b,v));
    const norm = s => String(s || '').replace(/\s+/g,' ').trim();

    const WX_RX = /\b(m[ée]t[ée]o|weather|temp[ée]rature|pr[ée]visions?|pluie|averses?|orage|neige|vent|rafales?|humidit[ée]|quel temps|temps fait|va[- ]t[- ]il faire)\b/i;

    let pendingWeather = null;
    let lastWeather = null;
    const weatherToken = new URLSearchParams(location.search).get('token') || '';

    // P0.5.2.8.6.1
    // 30 s is only a UI soft threshold. The Core may still be ACTING.
    // Keep accepting the real answer for up to 180 s.
    const WEATHER_SOFT_TIMEOUT_MS = 30000;
    const WEATHER_HARD_TIMEOUT_MS = 120000;
    const WEATHER_FINAL_TIMEOUT_MS = 180000;

    function auraWeatherCoreStillBusy() {
      try {
        const bodyText = norm(document.body?.innerText || '').slice(0,900);
        return /\b(ACTING|THINKING|SEARCHING|PROCESSING|WORKING)\b/i.test(bodyText);
      } catch {
        return false;
      }
    }
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
          <header><span id="auraWxForecastTitle">STRUCTURED FORECAST</span><small id="auraWxHourlyLabel">AWAITING STRUCTURED HOURS</small></header>
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
      // P0.5.1.5: do NOT call resizeCanvas() here.
      // The outer `root` const is still in its Temporal Dead Zone.
      initParticles();

      return root;
    }

    const root = createWorkspace();

    // Safe only after createWorkspace() has returned and `root` exists.
    resizeCanvas();

    function findTalkRailButton() {
      // The actual AURA runtime doesn't expose the left TALK rail through the
      // same id as the composer controls. Resolve it by visible label first.
      const buttons=[...document.querySelectorAll('button')];
      return buttons.find(b=>/\bTALK\b/i.test(norm(b.textContent))) || null;
    }

    async function requestCurrentWeather() {
      const query='Météo de ma position actuelle';
      pendingWeather={query,started:Date.now(),origin:'rail-current-geolocation',softTimeoutShown:false,hardTimeoutShown:false};
      openWeather({query,loading:true});

      if(!navigator.geolocation){
        openWeather({query,loading:false,error:true,parsed:{location:'Position actuelle',condition:'LOCALISATION INDISPONIBLE',raw:'Ce poste ne fournit pas de géolocalisation. Indique une ville à AURA.',source:'DEVICE GEOLOCATION',hourly:[]}});
        pendingWeather=null;
        return;
      }

      navigator.geolocation.getCurrentPosition(async pos=>{
        const lat=Number(pos.coords.latitude),lon=Number(pos.coords.longitude);
        const accuracy=Number(pos.coords.accuracy||0);
        try{
          const response=await fetch(`/api/action?token=${encodeURIComponent(weatherToken)}`,{
            method:'POST',
            cache:'no-store',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({action:'weather_current',latitude:lat,longitude:lon,accuracy})
          });
          if(!response.ok)throw new Error(`HTTP ${response.status}`);
          startBridgePolling();
        }catch(_){
          openWeather({query,loading:false,error:true,parsed:{location:'Position actuelle',condition:'MÉTÉO TEMPORAIREMENT INDISPONIBLE',raw:'AURA n’a pas pu charger la météo de la position actuelle.',source:'WEATHER SERVICE',hourly:[]}});
          pendingWeather=null;
        }
      },()=>{
        openWeather({query,loading:false,error:true,parsed:{location:'Position actuelle',condition:'LOCALISATION NON AUTORISÉE',raw:'Autorise la localisation pour AURA/Chromium, ou indique une ville.',source:'DEVICE GEOLOCATION',hourly:[]}});
        pendingWeather=null;
      },{
        enableHighAccuracy:false,
        timeout:6500,
        maximumAge:0
      });
    }

    function createRailButton() {
      let btn=document.getElementById('auraWeatherBtn');
      if(btn)return btn;

      btn = document.createElement('button');
      btn.id = 'auraWeatherBtn';
      btn.className = 'rail-btn aura-weather-rail-btn';
      btn.title = 'Météo contextuelle';
      btn.innerHTML = `<span>${svgIcon('weather')}</span><small>Weather</small>`;
      btn.addEventListener('click', () => {
        if (active) {
          closeWeather();
        } else {
          requestCurrentWeather();
        }
      });

      const talkRail=findTalkRailButton();
      if(talkRail?.parentElement){
        talkRail.insertAdjacentElement('afterend',btn);
        return btn;
      }

      // Fallback: locate the narrow left rail by the HOME/MEM/SYS labels.
      const candidates=[...document.querySelectorAll('nav,aside,div')].filter(el=>{
        const t=norm(el.textContent);
        const r=el.getBoundingClientRect();
        return r.width>35 && r.width<130 &&
               /\bHOME\b/i.test(t) && /\bMEM\b/i.test(t) && /\bSYS\b/i.test(t);
      });
      if(candidates[0]){
        const mem=[...candidates[0].querySelectorAll('button')].find(b=>/\bMEM\b/i.test(norm(b.textContent)));
        if(mem)mem.insertAdjacentElement('beforebegin',btn);
        else candidates[0].appendChild(btn);
      }
      return btn;
    }

    const railBtn = createRailButton();
    document.documentElement.dataset.auraWeatherUi = railBtn?.isConnected ? 'ready' : 'workspace-only';

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
      const precipVisual = parsed.precipUnit==='mm'
        ? clamp(precipVal/8,0,1)
        : clamp(precipVal/100,0,1);

      let speed = .20 + clamp(windVal/80,0,1)*.65;
      let alpha = .145;
      if(visualLayer==='precip'){speed=.16+precipVisual*.42;alpha=.16}
      if(visualLayer==='clouds'){speed=.10;alpha=.105}

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
      let q=norm(query).replace(/[?!.,]+$/,'');
      if(!q)return '';

      q=q.replace(/\s+(?:aujourd['’]hui|demain|ce\s+matin|cet\s+apr[èe]s-midi|ce\s+soir|maintenant)\s*$/i,'');

      let m=q.match(/\b(?:fait-il|fera-t-il|fait il|fera il|m[ée]t[ée]o|weather|temps)\s+(?:actuellement\s+)?(?:à|a|pour|sur|dans)\s+(.+)$/i);
      if(m)return norm(m[1]);

      m=q.match(/\b(?:à|a|pour|sur|dans)\s+([A-ZÀ-Ÿ][A-Za-zÀ-ÿ0-9'’ .-]{1,64})$/);
      if(m)return norm(m[1]);

      m=q.match(/\b(?:m[ée]t[ée]o|weather)\s+([A-Za-zÀ-ÿ0-9'’ .-]{2,64})$/i);
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
      let raw=norm(text);
      raw=raw
        .replace(/^(?:CONVERSATION\s*)+/i,'')
        .replace(/^(?:AURA\s*)+(?=[ÀA-Z])/i,'')
        .replace(/^AURA(?=À)/i,'')
        .trim();

      const parsed={raw};

      const tempMatches=[...raw.matchAll(/(-?\d{1,2}(?:[.,]\d)?)\s*°\s*C\b/gi)];
      if(tempMatches.length)parsed.temp=tempMatches[0][1].replace(',','.');

      let m=raw.match(/ressenti(?:e)?\s*(?:est\s*)?(?:de|à|:)?\s*(-?\d{1,2}(?:[.,]\d)?)\s*°?\s*C?/i);
      if(m)parsed.feels=m[1].replace(',','.');

      m=raw.match(/humidit[ée]\s*(?:est\s*)?(?:de|à|:)?\s*(\d{1,3})\s*%/i);
      if(m){
        parsed.humidity=m[1]+' %';
        parsed.humidityNumber=Number(m[1]);
      }

      // Handles "le vent souffle à 10 km/h", "vent : 10 km/h", etc.
      m=raw.match(/\bvent\b[^0-9]{0,32}(\d{1,3}(?:[.,]\d)?)\s*km\s*\/?\s*h/i);
      if(!m)m=raw.match(/(\d{1,3}(?:[.,]\d)?)\s*km\s*\/?\s*h[^.]{0,32}\bvent\b/i);
      if(m){
        parsed.wind=m[1].replace(',','.')+' km/h';
        parsed.windNumber=Number(m[1].replace(',','.'));
      }

      // Probability form.
      m=raw.match(/(?:pr[ée]cipitations?|risque de pluie|pluie)\s*(?:est|sont)?\s*(?:de|à|:)?\s*(\d{1,3})\s*%/i);
      if(m){
        parsed.precip=m[1]+' %';
        parsed.precipNumber=Number(m[1]);
        parsed.precipUnit='percent';
      } else {
        // Actual accumulation form used by Aura/Open-Meteo in the video: 0.0 mm.
        m=raw.match(/pr[ée]cipitations?[^0-9]{0,38}(\d{1,3}(?:[.,]\d+)?)\s*mm\b/i);
        if(m){
          parsed.precip=m[1].replace(',','.')+' mm';
          parsed.precipMm=Number(m[1].replace(',','.'));
          parsed.precipNumber=parsed.precipMm;
          parsed.precipUnit='mm';
        }
      }

      parsed.condition=conditionFromText(raw);

      // Prefer the explicit Aura/Open-Meteo location, wherever the DOM text starts.
      m=raw.match(/(?:^|\s)[ÀA]\s+(.{2,96}?)(?=,\s*il\s+fait\b)/i);
      if(m){
        parsed.location=norm(m[1])
          .replace(/^(?:AURA\s*)+/i,'')
          .trim();
      }
      if(!parsed.location)parsed.location=inferLocation(query);

      // Source / verification metadata, if Aura explicitly gives them.
      m=raw.match(/\bsource\s*:\s*([^,.!?]{2,48})/i);
      if(m)parsed.source=norm(m[1]);

      m=raw.match(/\bv[ée]rifi[ée]e?\s*(?:à|a)\s*(\d{1,2}:\d{2})/i);
      if(m)parsed.verifiedAt=m[1];

      // Only create hourly cells when the answer explicitly associates clock time + °C.
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

    function canonicalLocationFromRaw(raw='') {
      const s=norm(raw)
        .replace(/^(?:CONVERSATION\s*)+/i,'')
        .replace(/^(?:AURA\s*)+(?=[ÀA-Z])/i,'')
        .replace(/^AURA(?=À)/i,'')
        .trim();

      if(!s)return '';

      // Aura/Open-Meteo canonical sentence:
      // "À Nice, Région PACA, France, il fait actuellement..."
      let m=s.match(/(?:^|\s)[ÀA]\s+(.{2,120}?)(?=,\s*il\s+fait\b)/i);
      if(m)return norm(m[1]).replace(/^(?:AURA\s*)+/i,'').trim();

      // Secondary form if wording changes slightly.
      m=s.match(/(?:^|\s)[ÀA]\s+(.{2,120}?)(?=,\s*(?:conditions?|temp[ée]rature|le\s+temps)\b)/i);
      if(m)return norm(m[1]).replace(/^(?:AURA\s*)+/i,'').trim();

      return '';
    }

    function enrichParsedWeather(parsed={}, raw='', query='') {
      const out={...(parsed||{})};
      const text=norm(raw || out.raw || '');
      if(text){
        const extracted=parseWeather(text,query);

        // Canonical textual metadata from the Core summary has priority over
        // a short payload.location such as "Nice".
        const canonical=canonicalLocationFromRaw(text) || extracted.location;
        if(canonical)out.location=canonical;

        if(!out.temp && extracted.temp)out.temp=extracted.temp;
        if(!out.feels && extracted.feels)out.feels=extracted.feels;
        if(!out.condition && extracted.condition)out.condition=extracted.condition;
        if(!out.wind && extracted.wind)out.wind=extracted.wind;
        if(out.windNumber==null && extracted.windNumber!=null)out.windNumber=extracted.windNumber;
        if(!out.humidity && extracted.humidity)out.humidity=extracted.humidity;
        if(out.humidityNumber==null && extracted.humidityNumber!=null)out.humidityNumber=extracted.humidityNumber;
        if(!out.precip && extracted.precip)out.precip=extracted.precip;
        if(out.precipNumber==null && extracted.precipNumber!=null)out.precipNumber=extracted.precipNumber;
        if(out.precipMm==null && extracted.precipMm!=null)out.precipMm=extracted.precipMm;
        if(!out.precipUnit && extracted.precipUnit)out.precipUnit=extracted.precipUnit;
        if(!out.source && extracted.source)out.source=extracted.source;
        if(!out.verifiedAt && extracted.verifiedAt)out.verifiedAt=extracted.verifiedAt;
        if((!out.hourly || !out.hourly.length) && extracted.hourly?.length)out.hourly=extracted.hourly;

        out.raw=text;
      }

      if(!out.location)out.location=inferLocation(query);
      if(!Array.isArray(out.hourly))out.hourly=[];
      return out;
    }

    function applyWeather(data) {
      lastWeather=data;
      const p=enrichParsedWeather(data.parsed || {}, data.parsed?.raw || '', data.query || '');
      data.parsed=p;

      const displayLocation=
        canonicalLocationFromRaw(p.raw || '') ||
        p.location ||
        inferLocation(data.query) ||
        'LOCATION NON STRUCTURÉE';

      setText('auraWxLocation',displayLocation);
      root.dataset.locationMode =
        canonicalLocationFromRaw(p.raw || '') ? 'core-canonical' :
        (p.location ? 'payload' : 'query-fallback');
      setText('auraWxTemp',p.temp || '—');
      setText('auraWxDegree',p.temp ? '°C' : '');
      setText('auraWxCondition',p.condition || 'CONDITIONS');
      setText('auraWxFeels',p.feels ? p.feels+' °C' : '—');
      setText('auraWxWind',p.wind || '—');
      setText('auraWxHumidity',p.humidity || '—');
      setText('auraWxPrecip',p.precip || '—');
      setText('auraWxSummary',p.raw || 'Aucune synthèse Aura reçue.');

      const isError=!!data.error;
      window.dispatchEvent(new CustomEvent('aura:workspace-activity',{
        detail:{
          workspace:'weather',
          state:data.loading?'loading':(isError?'error':'ready'),
          label:data.loading?'Localisation et météo':(isError?'Météo indisponible':'Données météo prêtes'),
          detail:String(displayLocation||'')
        }
      }));
      setText(
        'auraWxStatus',
        data.loading ? 'AURA RESEARCH IN PROGRESS' :
        isError ? 'AURA WEATHER ERROR' :
        'AURA DATA READY'
      );

      const sourceMeta = data.loading
        ? 'WAITING'
        : isError
          ? 'CORE · WEATHER ERROR'
          : [p.source ? `CORE · ${p.source.toUpperCase()}` : 'CORE RESPONSE', p.verifiedAt || '']
              .filter(Boolean).join(' · ');
      setText('auraWxDataMode',sourceMeta);

      const status=root.querySelector('.aura-weather-status');
      status?.classList.toggle('ready',!data.loading && !isError);
      status?.classList.toggle('error',isError);
      root.classList.toggle('aura-weather-error',isError);

      const hourly=root.querySelector('#auraWxHourly');
      const hourlyLabel=root.querySelector('#auraWxHourlyLabel');
      const forecastTitle=root.querySelector('#auraWxForecastTitle');
      if(p.hourly?.length){
        if(forecastTitle)forecastTitle.textContent='STRUCTURED FORECAST';
        hourly.innerHTML=p.hourly.map((h,i)=>`
          <article ${i===0?'class="active"':''}>
            <small>${h.time}</small>
            <i></i>
            <strong>${h.temp}°</strong>
          </article>`).join('');
        hourlyLabel.textContent=`${p.hourly.length} HEURES EXTRAITES`;
      } else {
        if(forecastTitle)forecastTitle.textContent='CURRENT CONDITIONS';
        hourly.innerHTML=`
          <div class="aura-weather-hour-empty">
            <strong>DONNÉES TEMPS RÉEL</strong>
            <span>Pas de série horaire dans cette réponse · les conditions actuelles restent affichées ci-dessus.</span>
          </div>`;
        hourlyLabel.textContent='LIVE SNAPSHOT';
        root.classList.add('aura-weather-no-hourly');
      }
      if(p.hourly?.length)root.classList.remove('aura-weather-no-hourly');
    }

    function openWeather(data={}) {
      active=true;
      document.body.classList.add('aura-workspace-active','aura-weather-active');
      root.classList.add('open');
      root.setAttribute('aria-hidden','false');
      railBtn?.classList.add('active');

      const q=data.query||pendingWeather?.query||'';
      if(data.loading){
        root.classList.remove('aura-weather-error');
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
      /* AURA R16.4 USER DISMISS WEATHER: explicit close is authoritative. */
      active=false;
      pendingWeather=null;
      stopBridgePolling();
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
        const raw=payload.summary||payload.text||payload.parsed?.raw||'';

        const initial=payload.parsed || {
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
          precipMm:payload.precipMm,
          precipUnit:payload.precipUnit,
          source:payload.source,
          verifiedAt:payload.verifiedAt,
          hourly:Array.isArray(payload.hourly)?payload.hourly:[],
          raw
        };

        // P0.5.1.8: always reconcile a structured payload with the actual
        // Core summary. This upgrades "Nice" to "Nice, Région PACA, France"
        // without discarding structured numeric fields.
        const parsed=enrichParsedWeather(initial,raw,query);
        openWeather({query,loading:false,parsed});
      },
      close:closeWeather,
      parse:parseWeather
    };

    window.addEventListener('aura:workspace:weather',ev=>{
      window.AURA_WORKSPACES.weather.open(ev.detail||{});
    });

    window.addEventListener('aura:workspace-refresh',ev=>{
      if(String(ev.detail?.workspace||'')==='weather')requestCurrentWeather();
    });

    // ------------------------------------------------------------------
    // P0.5.1.1 ROBUST CONVERSATION BRIDGE
    //
    // The real RC4.2 runtime does not necessarily append the user request as
    // .message.user inside #messages. It can send directly from the composer,
    // then create a separate CONVERSATION popup for the Aura answer.
    // ------------------------------------------------------------------

    let bridgePoll=0;
    let lastAnswerFingerprint='';

    function findComposerInput() {
      const inputs=[...document.querySelectorAll('textarea,input,[contenteditable="true"]')]
        .filter(el=>{
          const r=el.getBoundingClientRect();
          if(r.width<120 || r.height<18 || r.bottom<window.innerHeight*.68)return false;
          const hint=norm(
            el.getAttribute?.('placeholder') ||
            el.getAttribute?.('aria-label') ||
            ''
          );
          return /AURA|Écris|Ecris|message|parler/i.test(hint) || r.width>300;
        });
      return inputs[0] || null;
    }

    function readComposerText() {
      const el=findComposerInput();
      if(!el)return '';
      return norm(el.value ?? el.textContent ?? '');
    }

    // AURA DEV WEATHER AUTO-OPEN GUARD V17
    function developerModeActive(){
      try{
        if(document.documentElement.classList.contains('aura-adf-dev-active'))return true;
        return window.AuraDeveloperModeSurface?.enabled?.()===true;
      }catch(_){
        return false;
      }
    }

    function explicitWeatherCommand(value){
      const q=norm(value);
      if(!q||q.length>320)return false;
      return /^(?:m[ée]t[ée]o|weather)(?:\b|\s|[:;,.-])/i.test(q)
        || /^(?:quel temps|quelle m[ée]t[ée]o|quelles? pr[ée]visions?|temp[ée]rature|va[- ]t[- ]il\s+(?:pleuvoir|neiger|faire)|est[- ]ce qu['’]il va\s+(?:pleuvoir|neiger))/i.test(q);
    }

    function armWeatherRequest(text,origin='composer') {
      if(developerModeActive()&&!explicitWeatherCommand(text))return false;
      const q=norm(text);
      if(!q || !WX_RX.test(q))return false;

      if(pendingWeather && pendingWeather.query===q && Date.now()-pendingWeather.started<15000){
        return true;
      }

      pendingWeather={
        query:q,
        started:Date.now(),
        origin,
        softTimeoutShown:false,
        hardTimeoutShown:false
      };
      openWeather({query:q,loading:true});
      startBridgePolling();
      return true;
    }

    function looksLikeAuraWeatherAnswer(text) {
      const s=norm(text);
      if(s.length<28 || s.length>2200)return false;
      if(pendingWeather && s===pendingWeather.query)return false;

      let score=0;
      if(/-?\d{1,2}(?:[.,]\d+)?\s*°\s*C\b/i.test(s))score+=2;
      if(/\bhumidit[ée]\b/i.test(s))score++;
      if(/\bvent\b/i.test(s) && /\bkm\s*\/?\s*h\b/i.test(s))score++;
      if(/\bpr[ée]cipitations?\b|\bpluie\b/i.test(s))score++;
      if(/\bconditions?\b|\bciel\b|\bd[ée]gag[ée]\b|\bnuage/i.test(s))score++;
      if(/\bsource\s*:/i.test(s))score++;
      return score>=3;
    }

    function looksLikeAuraWeatherError(text) {
      const s=norm(text);
      if(!s || s.length<18 || s.length>1600)return false;
      return (
        /je n['’]ai pas pu v[ée]rifier la m[ée]t[ée]o/i.test(s) ||
        /donn[ée]es m[ée]t[ée]o re[çc]ues sont incompl[èe]tes/i.test(s) ||
        /je n['’]ai pas trouv[ée] de lieu correspondant/i.test(s) ||
        /m[ée]t[ée]o (?:temporairement )?indisponible/i.test(s) ||
        /weather[_ -]?error/i.test(s)
      );
    }

    function consumeAuraWeatherError(text,origin='dom') {
      if(!pendingWeather)return false;
      const s=norm(text);
      if(!looksLikeAuraWeatherError(s))return false;

      const q=pendingWeather.query;
      openWeather({
        query:q,
        loading:false,
        error:true,
        parsed:{
          location:inferLocation(q),
          condition:'MÉTÉO INDISPONIBLE',
          raw:s,
          source:'WEATHER ERROR',
          hourly:[]
        }
      });

      pendingWeather=null;
      stopBridgePolling();

      try{
        window.dispatchEvent(new CustomEvent('aura:weather:error',{
          detail:{query:q,message:s,origin}
        }));
      }catch{}
      return true;
    }

    function consumeAuraWeatherAnswer(text,origin='dom') {
      if(!pendingWeather)return false;
      const age=Date.now()-pendingWeather.started;
      if(age>WEATHER_FINAL_TIMEOUT_MS){
        pendingWeather=null;
        stopBridgePolling();
        return false;
      }

      const s=norm(text);
      if(!looksLikeAuraWeatherAnswer(s))return false;

      const fingerprint=s.slice(0,240);
      if(fingerprint===lastAnswerFingerprint)return true;
      lastAnswerFingerprint=fingerprint;

      const parsed=parseWeather(s,pendingWeather.query);
      openWeather({
        query:pendingWeather.query,
        loading:false,
        parsed,
        bridgeOrigin:origin
      });
      pendingWeather=null;
      stopBridgePolling();
      return true;
    }

    function scanAuraAnswerDOM() {
      if(!pendingWeather)return;

      // First search the most probable answer containers.
      const selectors=[
        '[role="dialog"] p',
        '[role="dialog"] article',
        '[role="dialog"] div',
        '.conversation p',
        '.conversation article',
        '.conversation div',
        '[class*="conversation"] p',
        '[class*="conversation"] div',
        '[class*="message"] p',
        '[class*="message"] div',
        'main p'
      ];

      const seen=new Set();
      const candidates=[];
      for(const sel of selectors){
        document.querySelectorAll(sel).forEach(el=>{
          if(seen.has(el) || root.contains(el))return;
          seen.add(el);

          const text=norm(el.textContent);
          if(text.length<28 || text.length>2200)return;
          const r=el.getBoundingClientRect();
          if(r.width<120 || r.height<18)return;

          if(looksLikeAuraWeatherError(text)){
            if(consumeAuraWeatherError(text,'dom-scan-error'))return;
          }
          if(looksLikeAuraWeatherAnswer(text)){
            candidates.push({el,text,area:r.width*r.height});
          }
        });
      }

      // Prefer the smallest matching textual container, avoiding whole-dialog duplicates.
      candidates.sort((a,b)=>a.area-b.area || a.text.length-b.text.length);
      if(candidates[0])consumeAuraWeatherAnswer(candidates[0].text,'dom-scan');
    }

    function startBridgePolling() {
      if(bridgePoll)return;
      bridgePoll=window.setInterval(()=>{
        if(!pendingWeather){
          stopBridgePolling();
          return;
        }

        const age=Date.now()-pendingWeather.started;
        const q=pendingWeather.query;

        if(
          age>WEATHER_SOFT_TIMEOUT_MS &&
          !pendingWeather.softTimeoutShown
        ){
          pendingWeather.softTimeoutShown=true;
          openWeather({
            query:q,
            loading:true,
            error:false,
            parsed:{
              location:inferLocation(q),
              condition:'RECHERCHE MÉTÉO PROLONGÉE',
              raw:"Aura traite toujours la demande météo. La réponse du Core reste attendue.",
              source:'CORE WAITING',
              hourly:[]
            }
          });
          try{
            window.dispatchEvent(new CustomEvent('aura:weather:slow',{
              detail:{query:q,age,origin:'bridge-soft-timeout'}
            }));
          }catch{}
        }

        if(
          age>WEATHER_HARD_TIMEOUT_MS &&
          !pendingWeather.hardTimeoutShown &&
          !auraWeatherCoreStillBusy()
        ){
          pendingWeather.hardTimeoutShown=true;
          openWeather({
            query:q,
            loading:false,
            error:true,
            parsed:{
              location:inferLocation(q),
              condition:'MÉTÉO TEMPORAIREMENT INDISPONIBLE',
              raw:"La réponse météo du Core dépasse le délai normal. Aura continue néanmoins d'accepter une réponse tardive.",
              source:'WEATHER DELAY',
              hourly:[]
            }
          });
          try{
            window.dispatchEvent(new CustomEvent('aura:weather:error',{
              detail:{query:q,message:'WEATHER CORE DELAY >120S',origin:'bridge-hard-timeout'}
            }));
          }catch{}
        }

        if(age>WEATHER_FINAL_TIMEOUT_MS){
          if(!pendingWeather.hardTimeoutShown){
            openWeather({
              query:q,
              loading:false,
              error:true,
              parsed:{
                location:inferLocation(q),
                condition:'MÉTÉO INDISPONIBLE',
                raw:"Aura n'a pas reçu de réponse météo exploitable du Core après trois minutes.",
                source:'WEATHER TIMEOUT',
                hourly:[]
              }
            });
            try{
              window.dispatchEvent(new CustomEvent('aura:weather:error',{
                detail:{query:q,message:'WEATHER CORE FINAL TIMEOUT',origin:'bridge-final-timeout'}
              }));
            }catch{}
          }
          pendingWeather=null;
          stopBridgePolling();
          return;
        }

        scanAuraAnswerDOM();
      },320);
    }

    function stopBridgePolling() {
      if(bridgePoll){
        clearInterval(bridgePoll);
        bridgePoll=0;
      }
    }

    // Capture Enter BEFORE the existing composer clears its input.
    document.addEventListener('keydown',ev=>{
      if(ev.key!=='Enter' || ev.shiftKey || ev.ctrlKey || ev.altKey)return;
      const target=ev.target;
      if(!(target instanceof HTMLElement))return;
      if(!target.matches('textarea,input,[contenteditable="true"]'))return;

      const text=norm(target.value ?? target.textContent ?? '');
      if(WX_RX.test(text))armWeatherRequest(text,'composer-enter');
    },true);

    // Also capture mouse/touch send. The real send button may not have a stable id.
    document.addEventListener('pointerdown',ev=>{
      const button=ev.target instanceof Element ? ev.target.closest('button') : null;
      if(!button)return;

      const text=readComposerText();
      if(!WX_RX.test(text))return;

      const input=findComposerInput();
      if(!input)return;
      const ir=input.getBoundingClientRect();
      const br=button.getBoundingClientRect();

      // Send controls live close to the bottom composer. Avoid triggering from
      // unrelated sidebar/header buttons while weather text happens to be typed.
      const verticallyClose=Math.abs((br.top+br.height/2)-(ir.top+ir.height/2))<90;
      const horizontallyNear=br.left>ir.left-120 && br.left<ir.right+180;
      if(verticallyClose && horizontallyNear){
        armWeatherRequest(text,'composer-button');
      }
    },true);

    // Global mutation observer: covers the real dynamic CONVERSATION popup.
    const bridgeObserver=new MutationObserver(muts=>{
      if(!pendingWeather)return;

      for(const m of muts){
        for(const n of m.addedNodes){
          if(!(n instanceof HTMLElement) || root.contains(n))continue;

          const elements=[];
          if(n.matches?.('p,article,[class*="message"],[class*="conversation"],[role="dialog"]')){
            elements.push(n);
          }
          n.querySelectorAll?.(
            'p,article,[class*="message"],[class*="conversation"],[role="dialog"]'
          ).forEach(el=>elements.push(el));

          for(const el of elements){
            const s=norm(el.textContent);
            if(consumeAuraWeatherError(s,'mutation-error'))return;
            if(consumeAuraWeatherAnswer(s,'mutation'))return;
          }
        }
      }

      // Some frameworks mutate textContent inside an existing dialog node.
      scanAuraAnswerDOM();
    });
    bridgeObserver.observe(document.body,{childList:true,subtree:true,characterData:true});

    // Compatibility with the P0.5.1 message model when present.
    function onNewMessage(row) {
      if (!(row instanceof HTMLElement)) return;
      const text=norm(row.querySelector?.('p')?.textContent || row.textContent);
      if(!text)return;

      if(row.classList?.contains('user') && WX_RX.test(text)){
        armWeatherRequest(text,'legacy-user-message');
        return;
      }

      if(pendingWeather){
        if(consumeAuraWeatherError(text,'legacy-aura-error'))return;
        consumeAuraWeatherAnswer(text,'legacy-aura-message');
      }
    }

    if(messages){
      const legacyObserver=new MutationObserver(muts=>{
        for(const m of muts)for(const n of m.addedNodes){
          if(n.nodeType===1){
            onNewMessage(n);
            n.querySelectorAll?.('.message').forEach(onNewMessage);
          }
        }
      });
      legacyObserver.observe(messages,{childList:true,subtree:true});
    }

    // Re-resolve the rail after React/vanilla UI boot has created all controls.
    setTimeout(()=>{
      const current=document.getElementById('auraWeatherBtn');
      if(!current || !current.isConnected){
        createRailButton();
      }else{
        const talk=findTalkRailButton();
        if(talk?.parentElement && current.parentElement!==talk.parentElement){
          talk.insertAdjacentElement('afterend',current);
        }
      }
    },1200);
  }

  // Module/deferred main UI may finish after this classic script.
  // Use several safe entry points plus polling; initialization is idempotent.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', auraP051StartWhenReady, {once:true});
  } else {
    auraP051StartWhenReady();
  }
  window.addEventListener('load', auraP051StartWhenReady, {once:true});
  window.setTimeout(auraP051StartWhenReady, 0);
  window.setTimeout(auraP051StartWhenReady, 250);
  window.setTimeout(auraP051StartWhenReady, 750);
})();
