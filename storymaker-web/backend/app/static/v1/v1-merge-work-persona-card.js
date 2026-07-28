(() => {
  'use strict';
  if (window.__STORYMAKER_V1_MERGE_WORK_PERSONA_V3__) return;
  window.__STORYMAKER_V1_MERGE_WORK_PERSONA_V3__ = true;

  const ID = 'storymaker-v1-work-persona-two-rows';
  const clean = (v='') => String(v).replace(/\s+/g,' ').trim();
  const rectArea = (n) => { const r=n?.getBoundingClientRect?.(); return r ? r.width*r.height : Infinity; };

  function findWorkCard(){
    const label=[...document.querySelectorAll('*')].find(n=>clean(n.textContent)==='WORK PANEL');
    if(!label) return null;
    const cards=[]; let n=label;
    for(let i=0;n&&n!==document.body&&i<9;i++,n=n.parentElement){
      const t=clean(n.textContent),r=n.getBoundingClientRect?.();
      if(r&&r.width>600&&r.height>80&&r.height<340&&t.includes('WORK PANEL')&&t.includes('일괄 작업')) cards.push(n);
    }
    return cards.sort((a,b)=>rectArea(a)-rectArea(b))[0]||null;
  }

  function findPersonaCard(work){
    const nodes=[...document.querySelectorAll('div,section,article')].filter(n=>{
      if(n===work||work?.contains(n)||n.id===ID||n.closest('#'+ID)) return false;
      const t=clean(n.textContent),r=n.getBoundingClientRect?.();
      return r&&r.width>500&&r.height>45&&r.height<230&&/01[016789]-?\d{3,4}-?\d{4}/.test(t)&&(/home_repair|집수리|리모델링/.test(t));
    });
    return nodes.sort((a,b)=>rectArea(a)-rectArea(b))[0]||null;
  }

  function ensureStyle(){
    if(document.getElementById(ID+'-style')) return;
    const s=document.createElement('style'); s.id=ID+'-style';
    s.textContent=`
      #${ID}{display:grid!important;gap:12px!important;width:100%!important;padding:20px 24px!important;box-sizing:border-box!important}
      #${ID} .v1-row-one{font-size:clamp(18px,1.35vw,25px);font-weight:900;color:#f8fafc;line-height:1.45}
      #${ID} .v1-row-two{padding:14px 16px;border:1px solid rgba(34,211,238,.32);border-radius:16px;background:rgba(2,6,23,.32)}
      #${ID} .v1-business-summary{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;color:#cbd5e1;font-size:14px;line-height:1.6}
      #${ID} .v1-business-company{font-size:16px;font-weight:900;color:#f8fafc}
      #${ID} .v1-business-separator{color:#64748b}
      #${ID} .v1-row-two>*{margin:0!important;border:0!important;background:transparent!important;box-shadow:none!important;padding:0!important}
      [data-v1-persona-source-hidden="1"]{display:none!important}
      @media(max-width:760px){#${ID}{padding:16px!important}.v1-row-one{font-size:18px!important}}
    `; document.head.appendChild(s);
  }

  function apply(){
    const work=findWorkCard(); if(!work) return false;
    const persona=findPersonaCard(work); if(!persona) return false;
    ensureStyle();

    let box=work.querySelector('#'+ID);
    if(!box){ box=document.createElement('div'); box.id=ID; work.prepend(box); }
    const txt=clean(persona.textContent);
    if(box.dataset.source!==txt){
      const clone=persona.cloneNode(true);
      clone.removeAttribute('id'); clone.querySelectorAll('[id]').forEach(n=>n.removeAttribute('id'));
      clone.style.cssText='margin:0;padding:0;border:0;background:transparent;box-shadow:none;';
      box.innerHTML='<div class="v1-row-one">딸깍 한 번으로 업로드부터 제작까지 이어집니다.</div><div class="v1-row-two"></div>';
      const rawRegion=(txt.match(/지역:\s*(.*?)\s*\/\s*상호:/)||[])[1]?.trim();
      const region=typeof window.formatRegionDisplay==='function'?window.formatRegionDisplay(rawRegion):rawRegion;
      const company=(txt.match(/상호:\s*(.*?)\s*\/\s*전화번호:/)||[])[1]?.trim();
      const phone=(txt.match(/전화번호:\s*(01[016789]-?\d{3,4}-?\d{4})/)||[])[1]?.trim();
      const rowTwo=box.querySelector('.v1-row-two');
      if(company&&region&&phone){
        const summary=document.createElement('div');
        summary.className='v1-business-summary';
        const companyNode=document.createElement('strong');
        companyNode.className='v1-business-company';
        companyNode.textContent=company;
        summary.appendChild(companyNode);
        [region,phone].forEach(value=>{
          const separator=document.createElement('span');
          separator.className='v1-business-separator';
          separator.textContent='/';
          const item=document.createElement('span');
          item.textContent=value;
          summary.append(separator,item);
        });
        rowTwo.appendChild(summary);
      }else{
        rowTwo.appendChild(clone);
      }
      box.dataset.source=txt;
    }

    [...work.children].forEach(ch=>{ if(ch!==box){ ch.style.setProperty('display','none','important'); ch.dataset.v1WorkOld='1'; }});
    persona.dataset.v1PersonaSourceHidden='1';
    return true;
  }

  let timer; const schedule=()=>{clearTimeout(timer);timer=setTimeout(apply,80)};
  new MutationObserver(schedule).observe(document.documentElement,{childList:true,subtree:true,characterData:true});
  setInterval(apply,1000);
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',schedule,{once:true}); else schedule();
})();
