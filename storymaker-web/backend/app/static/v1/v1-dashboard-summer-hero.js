(() => {
  'use strict';
  if (window.__STORYMAKER_V1_SUMMER_HERO__) return;
  window.__STORYMAKER_V1_SUMMER_HERO__ = true;

  const HERO_ID = 'storymaker-v1-summer-hero';
  let IMAGES = [
    '/static/media/image/Seaside_work.jpg',
    '/static/media/image/Seaside_work_2.jpg',
    '/static/media/image/Seaside_work_3.jpg',
    '/static/media/image/star-dashboard.webp'
  ];
  let imagesReady = false;

  async function loadHeroImages() {
    try {
      const response = await fetch('/v1-api/v1/dashboard/hero-images', {
        cache: 'no-store',
        credentials: 'include'
      });
      const data = await response.json();
      if (response.ok && Array.isArray(data.images) && data.images.length) {
        IMAGES = data.images;
      }
    } catch (_) {
      // API 조회 실패 시 기존 기본 이미지 목록을 사용한다.
    } finally {
      imagesReady = true;
    }
  }

  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();


  function findDashboardCard() {
    const label = [...document.querySelectorAll('h1,h2,h3,p,div,span')].find((el) =>
      clean(el.textContent) === '오늘 만들 콘텐츠와 업체 상태를 한눈에 봅니다'
    );
    if (!label) return null;

    let node = label;
    while (node && node !== document.body) {
      const rect = node.getBoundingClientRect();
      if (rect.width > 650 && rect.height > 100 && rect.height < 360) return node;
      node = node.parentElement;
    }
    return label.parentElement;
  }

  function ensureStyle() {
    if (document.getElementById(HERO_ID + '-style')) return;
    const style = document.createElement('style');
    style.id = HERO_ID + '-style';
    style.textContent = `
      #${HERO_ID}{position:relative;display:block;width:100%;max-width:none;overflow:hidden;min-height:min(650px,72vh);border-radius:24px;border:0;background:#0b1730;box-shadow:none;isolation:isolate;margin:0}
      .sm-v1-hero-bg{position:absolute;inset:-3%;z-index:-2;background:center/cover no-repeat;opacity:0;transform:scale(1.02);transition:opacity 3.2s ease-in-out;will-change:transform,opacity}
      .sm-v1-hero-bg.is-active{opacity:1;animation:sm-v1-hero-kenburns 30s ease-in-out forwards}
      .sm-v1-hero-bg.is-leaving{opacity:0}
      @keyframes sm-v1-hero-kenburns{0%{transform:scale(1.03) translate3d(0,0,0)}50%{transform:scale(1.16) translate3d(-1.25%,-.9%,0)}100%{transform:scale(1.07) translate3d(.9%,.65%,0)}}
      #${HERO_ID}::before{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(8,26,74,.88) 0%,rgba(8,26,74,.66) 36%,rgba(8,26,74,.28) 61%,rgba(8,26,74,.03) 84%);z-index:0}
      #${HERO_ID}::after{content:"";position:absolute;inset:auto 0 0;height:34%;background:linear-gradient(0deg,rgba(1,8,25,.28),transparent);z-index:0}
      .sm-v1-hero-content{position:relative;z-index:1;display:flex;flex-direction:column;justify-content:center;align-items:flex-start;min-height:min(650px,72vh);width:min(68%,820px);padding:clamp(38px,5vw,76px);padding-right:20px;box-sizing:border-box}
      .sm-v1-hero-kicker{font-size:clamp(26px,3vw,44px);font-weight:900;color:#8fd6ff;text-shadow:0 2px 10px rgba(0,0,0,.35);margin-bottom:4px;letter-spacing:-.05em}
      .sm-v1-hero-title{margin:0;color:#f7fbff;font-size:clamp(42px,4.35vw,68px);line-height:1.04;letter-spacing:-.055em;font-weight:950;text-shadow:0 3px 16px rgba(0,0,0,.58),0 1px 0 rgba(0,0,0,.28);white-space:nowrap}
      .sm-v1-hero-title span{background:linear-gradient(120deg,#9be3ff,#5d7dff);-webkit-background-clip:text;background-clip:text;color:transparent}
      .sm-v1-hero-sub{margin:20px 0 0;color:#eef6ff;font-size:clamp(17px,1.55vw,23px);font-weight:800;line-height:1.55;text-shadow:0 2px 10px rgba(0,0,0,.45)}
      .sm-v1-hero-sub strong{color:#9ad9ff}
      .sm-v1-hero-actions{display:flex;gap:18px;flex-wrap:wrap;margin-top:42px}
      .sm-v1-hero-btn{min-width:245px;padding:20px 28px;border-radius:20px;border:1px solid rgba(31,132,255,.6);font-size:clamp(18px,1.6vw,24px);font-weight:950;cursor:pointer;transition:.2s ease;box-shadow:0 15px 35px rgba(21,103,238,.22)}
      .sm-v1-hero-btn.primary{color:#fff;background:linear-gradient(125deg,#00a8ed,#6c21f5)}
      .sm-v1-hero-btn.secondary{color:#087cd4;background:rgba(255,255,255,.93);backdrop-filter:blur(10px)}
      .sm-v1-hero-btn:hover{transform:translateY(-3px) scale(1.015);filter:brightness(1.07)}
      @media(max-width:900px){#${HERO_ID}{min-height:560px}#${HERO_ID}::before{background:linear-gradient(90deg,rgba(8,26,74,.9),rgba(8,26,74,.7) 55%,rgba(8,26,74,.24))}.sm-v1-hero-bg{background-position:62% center}.sm-v1-hero-content{min-height:560px;width:100%;padding:34px 26px}.sm-v1-hero-title{white-space:normal}.sm-v1-hero-actions{gap:12px;margin-top:30px}.sm-v1-hero-btn{width:100%;min-width:0}}
      @media(prefers-reduced-motion:reduce){.sm-v1-hero-bg{animation:none!important;transition:opacity .8s ease-in-out}}
    `;
    document.head.appendChild(style);
  }

  function mount() {
    if (!imagesReady) return false;
    if (document.getElementById(HERO_ID)) return true;
    const card = findDashboardCard();
    if (!card || !card.parentElement) return false;

    ensureStyle();
    const hero = document.createElement('section');
    hero.id = HERO_ID;
    const startIndex = Math.floor(Math.random() * IMAGES.length);
    hero.innerHTML = `
      <div class="sm-v1-hero-bg is-active" data-bg="0"></div>
      <div class="sm-v1-hero-bg" data-bg="1"></div>
      <div class="sm-v1-hero-content">
        <div class="sm-v1-hero-kicker">3분이면</div>
        <h1 class="sm-v1-hero-title"><span>SNS</span> 콘텐츠 완성</h1>
        <p class="sm-v1-hero-sub">사진 몇 장으로 <strong>블로그 · 인스타 · 쇼츠 · 팟캐스트</strong>까지 한 번에!</p>
        <div class="sm-v1-hero-actions">
          <button type="button" class="sm-v1-hero-btn primary" data-go="beta-production">일괄 제작 딸깍</button>
        </div>
      </div>`;

    const bgLayers = [...hero.querySelectorAll('.sm-v1-hero-bg')];
    let imageIndex = startIndex;
    let activeLayer = 0;
    bgLayers[0].style.backgroundImage = `url("${IMAGES[imageIndex]}")`;

    const preloadNext = () => {
      const img = new Image();
      img.src = IMAGES[(imageIndex + 1) % IMAGES.length];
    };
    preloadNext();

    const slideTimer = setInterval(() => {
      if (!document.body.contains(hero)) {
        clearInterval(slideTimer);
        return;
      }

      const current = bgLayers[activeLayer];
      const nextLayerIndex = activeLayer === 0 ? 1 : 0;
      const next = bgLayers[nextLayerIndex];

      if (IMAGES.length > 1) {
        let nextIndex = imageIndex;
        while (nextIndex === imageIndex) {
          nextIndex = Math.floor(Math.random() * IMAGES.length);
        }
        imageIndex = nextIndex;
      }
      next.style.backgroundImage = `url("${IMAGES[imageIndex]}")`;
      next.classList.remove('is-active', 'is-leaving');
      void next.offsetWidth;

      current.classList.add('is-leaving');
      next.classList.add('is-active');

      setTimeout(() => {
        current.classList.remove('is-active', 'is-leaving');
      }, 3400);

      activeLayer = nextLayerIndex;
      preloadNext();
    }, 30000);

    hero.addEventListener('click', (event) => {
      const button = event.target.closest('[data-go="beta-production"]');
      if (!button) return;
      location.href = '/v1/?page=betaProduction';
    });

    const host = card.parentElement;
    host.insertBefore(hero, card);
    card.style.display = 'none';
    host.style.display = 'block';
    host.style.width = '100%';
    host.style.maxWidth = 'none';
    host.style.padding = '0';
    host.style.margin = '0';
    host.style.gap = '0';
    host.style.border = '0';
    host.style.background = 'transparent';
    host.style.boxShadow = 'none';
    host.style.overflow = 'hidden';

    [...host.querySelectorAll('button,a,[role="button"]')].forEach((el) => {
      if (!el.closest('#' + HERO_ID) && clean(el.textContent) === '작업 시작') {
        el.style.display = 'none';
      }
    });
    return true;
  }

  loadHeroImages();

  let attempts = 0;
  const timer = setInterval(() => {
    attempts += 1;
    if (mount() || attempts > 100) clearInterval(timer);
  }, 200);

  new MutationObserver(mount).observe(document.documentElement, { childList: true, subtree: true });
})();
