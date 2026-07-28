(() => {
  'use strict';

  if (window.__STORYMAKER_V1_COMPANY_BG__) return;
  window.__STORYMAKER_V1_COMPANY_BG__ = true;

  const images = [
    '/static/media/image/Seaside_work.jpg',
    '/static/media/image/Seaside_work_2.jpg',
    '/static/media/image/Seaside_work_3.jpg',
    '/static/media/image/star-dashboard.webp'
  ];

  let root = null;
  let timer = null;
  let imageIndex = 0;
  let activeLayer = 0;

  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();

  function isCompanyPage() {
    const text = clean(document.body?.innerText || '');
    return text.includes('업체 정보') && text.includes('추가 업체 등록') && text.includes('업체 페르소나');
  }

  function ensureStyle() {
    if (document.getElementById('storymaker-v1-company-bg-style')) return;
    const style = document.createElement('style');
    style.id = 'storymaker-v1-company-bg-style';
    style.textContent = `
      .sm-v1-company-bg{position:fixed;inset:0;z-index:-2;pointer-events:none;overflow:hidden;background:#020817}
      .sm-v1-company-bg-layer{position:absolute;inset:-3%;background:center/cover no-repeat;opacity:0;transform:scale(1.03);transition:opacity 2.4s ease-in-out;filter:saturate(.82) brightness(.70);will-change:opacity,transform}
      .sm-v1-company-bg-layer.is-active{opacity:1;animation:sm-v1-company-bg-pan 30s ease-in-out forwards}
      .sm-v1-company-bg-shade{position:absolute;inset:0;background:linear-gradient(135deg,rgba(2,8,23,.72),rgba(5,20,42,.56) 50%,rgba(3,12,28,.68));backdrop-filter:blur(.6px)}
      body.sm-v1-company-bg-active{background:#020817!important}
      body.sm-v1-company-bg-active #root>div{background:transparent!important}
      body.sm-v1-company-bg-active main section,
      body.sm-v1-company-bg-active main>div{background-color:rgba(7,18,38,.70)!important;backdrop-filter:blur(7px)}
      @keyframes sm-v1-company-bg-pan{0%{transform:scale(1.03) translate3d(0,0,0)}50%{transform:scale(1.10) translate3d(-1.1%,-.7%,0)}100%{transform:scale(1.05) translate3d(.8%,.5%,0)}}
      @media(prefers-reduced-motion:reduce){.sm-v1-company-bg-layer{animation:none!important;transition:opacity .7s ease}}
    `;
    document.head.appendChild(style);
  }

  function mount() {
    if (root) return;
    ensureStyle();
    root = document.createElement('div');
    root.className = 'sm-v1-company-bg';
    root.setAttribute('aria-hidden', 'true');
    root.innerHTML = '<div class="sm-v1-company-bg-layer is-active"></div><div class="sm-v1-company-bg-layer"></div><div class="sm-v1-company-bg-shade"></div>';
    document.body.prepend(root);
    document.body.classList.add('sm-v1-company-bg-active');

    const layers = [...root.querySelectorAll('.sm-v1-company-bg-layer')];
    imageIndex = Math.floor(Math.random() * images.length);
    activeLayer = 0;
    layers[0].style.backgroundImage = `url("${images[imageIndex]}")`;

    timer = window.setInterval(() => {
      if (!root || !document.body.contains(root)) return;
      const nextLayer = activeLayer === 0 ? 1 : 0;
      imageIndex = (imageIndex + 1) % images.length;
      const current = layers[activeLayer];
      const next = layers[nextLayer];
      next.style.backgroundImage = `url("${images[imageIndex]}")`;
      next.classList.remove('is-active');
      void next.offsetWidth;
      current.classList.remove('is-active');
      next.classList.add('is-active');
      activeLayer = nextLayer;
      const preload = new Image();
      preload.src = images[(imageIndex + 1) % images.length];
    }, 30000);
  }

  function unmount() {
    if (timer) window.clearInterval(timer);
    timer = null;
    root?.remove();
    root = null;
    document.body.classList.remove('sm-v1-company-bg-active');
  }

  function sync() {
    if (isCompanyPage()) mount();
    else unmount();
  }

  let frame = 0;
  const observer = new MutationObserver(() => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(sync);
  });

  observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  window.addEventListener('popstate', sync);
  window.addEventListener('hashchange', sync);
  sync();
})();
