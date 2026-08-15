(() => {
  'use strict';

  if (window.__STORYMAKER_BETA_PAGE_BG__) return;
  window.__STORYMAKER_BETA_PAGE_BG__ = true;

  const images = [
    '/static/media/image/Seaside_work.jpg',
    '/static/media/image/Seaside_work_2.jpg',
    '/static/media/image/Seaside_work_3.jpg',
    '/static/media/image/star-dashboard.webp'
  ];

  const style = document.createElement('style');
  style.id = 'storymaker-beta-page-bg-style';
  style.textContent = `
    body{position:relative;background:#07101f!important}
    .sm-beta-page-bg{position:fixed;inset:0;z-index:-3;pointer-events:none;overflow:hidden;background:#07101f}
    .sm-beta-page-bg-layer{position:absolute;inset:-3%;background:center/cover no-repeat;opacity:0;transform:scale(1.03);transition:opacity 2.4s ease-in-out;will-change:opacity,transform;filter:saturate(.82) brightness(.72)}
    .sm-beta-page-bg-layer.is-active{opacity:1;animation:sm-beta-bg-pan 30s ease-in-out forwards}
    .sm-beta-page-bg-shade{position:absolute;inset:0;background:linear-gradient(135deg,rgba(2,8,23,.72),rgba(4,18,39,.58) 48%,rgba(3,12,28,.68));backdrop-filter:blur(.6px)}
    .top,.panel,.card,.archive-card,.detail-block,.archive-modal-shell{background-color:rgba(10,24,45,.72)!important;backdrop-filter:blur(7px)}
    @keyframes sm-beta-bg-pan{0%{transform:scale(1.03) translate3d(0,0,0)}50%{transform:scale(1.10) translate3d(-1.1%,-.7%,0)}100%{transform:scale(1.05) translate3d(.8%,.5%,0)}}
    @media(prefers-reduced-motion:reduce){.sm-beta-page-bg-layer{animation:none!important;transition:opacity .7s ease}}
  `;
  document.head.appendChild(style);

  const root = document.createElement('div');
  root.className = 'sm-beta-page-bg';
  root.setAttribute('aria-hidden', 'true');
  root.innerHTML = '<div class="sm-beta-page-bg-layer is-active"></div><div class="sm-beta-page-bg-layer"></div><div class="sm-beta-page-bg-shade"></div>';
  document.body.prepend(root);

  const layers = [...root.querySelectorAll('.sm-beta-page-bg-layer')];
  let imageIndex = Math.floor(Math.random() * images.length);
  let activeLayer = 0;
  layers[0].style.backgroundImage = `url("${images[imageIndex]}")`;

  const preload = (src) => {
    const image = new Image();
    image.src = src;
  };
  preload(images[(imageIndex + 1) % images.length]);

  window.setInterval(() => {
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
    preload(images[(imageIndex + 1) % images.length]);
  }, 30000);
})();
