(()=>{"use strict";
if(window.__AURA_V2_PRODUCT_UI_CLEANUP_R2__)return;
window.__AURA_V2_PRODUCT_UI_CLEANUP_R2__=true;

const norm=v=>String(v||"").replace(/\s+/g," ").trim();
const shown=e=>{
  if(!(e instanceof Element))return false;
  const s=getComputedStyle(e);
  return s.display!=="none"&&s.visibility!=="hidden"&&s.opacity!=="0";
};
const composerContext=e=>!!(e instanceof Element&&e.closest(
  '[class*="composer" i],[id*="composer" i],[data-aura-composer],'+
  '[class*="prompt" i],[class*="message-input" i],[class*="input-area" i],form'
));
const lowOnScreen=e=>{
  try{
    const r=e.getBoundingClientRect();
    return r.height>0 && r.top>=window.innerHeight*0.72;
  }catch(_){return false}
};
const exactLeafs=re=>[...document.querySelectorAll(
  'button,[role="button"],a,div,span,p,label,[role="status"],input[value]'
)].filter(e=>{
  const t=e.matches("input[value]")?norm(e.value):norm(e.textContent);
  if(!re.test(t))return false;
  return ![...e.children].some(c=>re.test(norm(c.textContent)));
});

function hidePlanAura(){
  const re=/^plan\s+aura$/i;
  for(const e of exactLeafs(re)){
    if(!(composerContext(e)||lowOnScreen(e)))continue;
    e.dataset.auraV2ProductHidden="1";
    e.setAttribute("aria-hidden","true");

    let p=e.parentElement;
    for(let i=0;p&&i<4;i++,p=p.parentElement){
      const txt=norm(p.textContent);
      const rect=p.getBoundingClientRect();
      if(/^plan\s+aura$/i.test(txt) && rect.height<=120){
        p.dataset.auraV2ProductCollapsed="1";
        break;
      }
    }
  }
}

function activeApproval(){
  const selectors=[
    '[role="dialog"]','[aria-modal="true"]',
    '[data-status="waiting_confirmation"]','[data-state="waiting_confirmation"]',
    '[data-status="pending_approval"]','[data-state="pending_approval"]',
    '[class*="approval" i]','[class*="confirmation" i]',
    '[class*="supervised-plan" i]','[class*="plan-card" i]'
  ].join(",");
  const words=/(confirmer|confirmation|approuver|approbation|autoriser|autorisation|annuler|ex[eé]cuter|waiting[_ -]?confirmation|pending[_ -]?approval)/i;
  return [...document.querySelectorAll(selectors)].some(e=>
    shown(e)&&words.test(
      norm(e.textContent)+" "+
      norm(e.getAttribute("data-state"))+" "+
      norm(e.getAttribute("data-status"))+" "+
      norm(e.getAttribute("aria-label"))
    )
  );
}

function hideIdleBlockedSupervision(){
  if(activeApproval())return;
  const re=/^supervision\s*:\s*bloqu[eé]e?$/i;
  for(const e of exactLeafs(re)){
    const badge=e.closest(
      '[role="status"],[class*="badge" i],[class*="supervision" i],[class*="status" i]'
    )||e;
    badge.dataset.auraV2ProductHidden="1";
    badge.setAttribute("aria-hidden","true");
  }
}

function repair(){
  hidePlanAura();
  hideIdleBlockedSupervision();
}

let queued=false;
function schedule(){
  if(queued)return;
  queued=true;
  requestAnimationFrame(()=>{queued=false;repair();});
}

if(document.readyState==="loading"){
  document.addEventListener("DOMContentLoaded",repair,{once:true});
}else{
  repair();
}

new MutationObserver(schedule).observe(document.documentElement,{
  childList:true,
  subtree:true,
  characterData:true,
  attributes:true,
  attributeFilter:["class","style","hidden","data-state","data-status"]
});

window.addEventListener("aura:a200:plan",schedule);
window.addEventListener("aura:a200:approval",schedule);
window.addEventListener("aura:a200:state",schedule);
window.addEventListener("resize",schedule);

console.info("[AURA] Product UI cleanup R2 active");
})();