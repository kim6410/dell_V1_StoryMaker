(() => {
  'use strict';
  const mq = matchMedia('(max-width: 767px)');
  let scheduled = false;
  const clean = v => String(v || '').replace(/\s+/g, ' ').trim();
  const visible = n => n instanceof HTMLElement && getComputedStyle(n).display !== 'none';
  const isTarget = () => {
    if (!mq.matches) return false;
    const u = new URL(location.href);
    if (u.searchParams.get('page') === 'betaProduction') return true;
    return [...document.querySelectorAll('h1,h2,h3,button')].some(n => visible(n) && /딸깍\s*제작|모바일 작업실/.test(clean(n.textContent)));
  };
  const moduleFor = node => {
    let cur = node;
    for (let i=0; cur && i<8; i++, cur=cur.parentElement) {
      const text = clean(cur.textContent);
      if (text.length > 40 && text.length < 5000 && (cur.matches('section,article') || /rounded|border/.test(cur.className || ''))) return cur;
    }
    return node.parentElement;
  };
  const removeOldMedia = () => {
    const patterns = [
      /BROWSER AI/i,
      /팟캐스트.*생성|팟캐스트 만들기|목소리 선택/,
      /숏폼.*MP4|MP4.*생성|동영상 만들기/,
      /썸네일.*생성|대표 썸네일|썸네일 스튜디오/
    ];
    [...document.querySelectorAll('h1,h2,h3,h4,strong,p,button')].forEach(n => {
      if (!visible(n)) return;
      const text = clean(n.textContent);
      if (!patterns.some(p => p.test(text))) return;
      const box = moduleFor(n);
      if (box && box.id !== 'sm-mobile-pc-continue-card' && box.isConnected) box.remove();
    });
  };
  const insertCard = () => {
    if (document.getElementById('sm-mobile-pc-continue-card')) return;
    const anchors = [...document.querySelectorAll('button,p,strong,h2,h3')].filter(n => visible(n));
    const anchor = anchors.find(n => /생성 완료|저장 완료|결과 확인|글과 사진/.test(clean(n.textContent))) || anchors.find(n => /콘텐츠 자동생성|딸깍 제작/.test(clean(n.textContent)));
    if (!anchor) return;
    const host = moduleFor(anchor)?.parentElement || anchor.parentElement;
    if (!host) return;
    const card = document.createElement('section');
    card.id='sm-mobile-pc-continue-card';
    card.innerHTML='<div class="sm-icon">PC</div><div><strong>글과 사진 저장 후 PC에서 이어서 제작</strong><p>모바일에서는 글과 사진까지만 생성해 보관함에 저장합니다. 팟캐스트, 숏폼 MP4, 썸네일은 PC의 Beta 보관함에서 계속 제작해 주세요.</p></div>';
    host.appendChild(card);
  };
  const apply = () => {
    scheduled=false;
    if (!isTarget()) return;
    removeOldMedia();
    insertCard();
  };
  const schedule=()=>{ if(!scheduled){ scheduled=true; requestAnimationFrame(apply); } };
  new MutationObserver(schedule).observe(document.documentElement,{subtree:true,childList:true});
  addEventListener('popstate',schedule);
  mq.addEventListener?.('change',schedule);
  schedule();
})();
