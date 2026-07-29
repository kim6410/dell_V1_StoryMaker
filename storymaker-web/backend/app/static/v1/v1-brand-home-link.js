(() => {
  'use strict';
  if (window.__STORYMAKER_V1_BRAND_HOME_LINK__) return;
  window.__STORYMAKER_V1_BRAND_HOME_LINK__ = true;

  const HOME_URL = '/v1';
  const HOME_BUTTON_TEXT = '대시보드로 돌아가기';
  const BRAND_TITLE_OLD = 'StoryMaker AI v1';
  const BRAND_TITLE_NEW = '스토리메이커';
  const BRAND_TITLE_WITH_BADGE = '스토리메이커 자동';
  const BRAND_BADGE_CLASS = 'storymaker-v1-auto-badge';
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();

  function findBrandBlock() {
    const title = [...document.querySelectorAll('h1,h2,h3,div,span,p')]
      .find((el) => {
        const text = clean(el.textContent);
        return text === BRAND_TITLE_OLD || text === BRAND_TITLE_NEW || text === BRAND_TITLE_WITH_BADGE;
      });
    if (!title) return null;

    let node = title;
    while (node && node !== document.body) {
      const text = clean(node.textContent);
      const rect = node.getBoundingClientRect?.();
      if (
        text.includes('STORYMAKER') &&
        (text.includes(BRAND_TITLE_OLD) || text.includes(BRAND_TITLE_NEW)) &&
        text.includes('소상공인 콘텐츠 대시보드') &&
        rect && rect.width >= 160 && rect.width <= 420 && rect.height >= 70 && rect.height <= 240
      ) return node;
      node = node.parentElement;
    }
    return title.parentElement;
  }

  function resetV1ViewState() {
    try { window.StoryMakerV1InlinePanels?.close?.(); } catch (_) {}

    [
      'storymaker-weather-panel',
      'storymaker-weather-overlay',
      'storymaker-v1-feature-request-fallback',
      'storymaker-v1-member-overlay',
      'storymaker-v1-admin-overlay'
    ].forEach((id) => document.getElementById(id)?.remove());

    document.querySelectorAll([
      '.sm-v1-request-menu.is-active',
      '#storymaker-v1-feature-request-menu.is-active',
      '[data-weather-linked].is-active',
      '[data-storymaker-clock-weather-trigger].is-active'
    ].join(',')).forEach((node) => node.classList.remove('is-active'));

    try {
      sessionStorage.removeItem('storymaker-v1-active-panel');
      sessionStorage.removeItem('storymaker-v1-admin-view');
    } catch (_) {}
  }

  function goHome(event) {
    if (event?.type === 'keydown' && event.key !== 'Enter' && event.key !== ' ') return;
    event?.preventDefault?.();
    event?.stopPropagation?.();
    event?.stopImmediatePropagation?.();
    resetV1ViewState();
    location.assign(HOME_URL);
  }

  function bindHomeNode(node, datasetKey) {
    if (!node || node.dataset[datasetKey] === '1') return;
    node.dataset[datasetKey] = '1';
    node.setAttribute('role', node.getAttribute('role') || 'button');
    node.setAttribute('tabindex', node.getAttribute('tabindex') || '0');
    node.setAttribute('aria-label', 'StoryMaker V1 초기 대시보드로 이동');
    node.title = '대시보드로 이동';
    node.style.cursor = 'pointer';
    node.style.userSelect = 'none';
    node.addEventListener('click', goHome, true);
    node.addEventListener('keydown', goHome, true);
    node.querySelectorAll?.('*').forEach((child) => { child.style.cursor = 'pointer'; });
  }

  function ensureBrandBadgeStyle() {
    if (document.getElementById('storymaker-v1-auto-badge-style')) return;
    const style = document.createElement('style');
    style.id = 'storymaker-v1-auto-badge-style';
    style.textContent = `
      .${BRAND_BADGE_CLASS}{
        display:inline-flex;
        align-items:center;
        justify-content:center;
        margin-left:9px;
        padding:3px 9px;
        border:1px solid rgba(34,211,238,.72);
        border-radius:999px;
        background:rgba(8,145,178,.12);
        color:#67e8f9;
        font-size:11px;
        font-weight:900;
        line-height:1.2;
        letter-spacing:0;
        vertical-align:middle;
        white-space:nowrap;
      }
    `;
    document.head.appendChild(style);
  }

  function installBrand() {
    const brandBlock = findBrandBlock();
    const title = brandBlock
      ? [...brandBlock.querySelectorAll('h1,h2,h3,div,span,p')].find((el) => {
          const text = clean(el.textContent);
          return text === BRAND_TITLE_OLD || text === BRAND_TITLE_NEW || text === BRAND_TITLE_WITH_BADGE;
        })
      : null;
    if (title) {
      ensureBrandBadgeStyle();
      const badge = title.querySelector(`.${BRAND_BADGE_CLASS}`);
      if (clean(title.textContent) !== BRAND_TITLE_WITH_BADGE || !badge) {
        title.textContent = BRAND_TITLE_NEW;
        const autoBadge = document.createElement('span');
        autoBadge.className = BRAND_BADGE_CLASS;
        autoBadge.textContent = '자동';
        title.appendChild(autoBadge);
      }
    }
    bindHomeNode(brandBlock, 'v1BrandHomeBound');
  }

  function installHardcodedButtons() {
    [...document.querySelectorAll('button,a,[role="button"]')].forEach((node) => {
      if (clean(node.textContent).includes(HOME_BUTTON_TEXT)) {
        bindHomeNode(node, 'v1HardcodedHomeBound');
      }
    });
  }

  const MENU_ICONS = {
    '대시보드': '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
    '새 콘텐츠 제작': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>',
    '진행 중 작업': '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/></svg>',
    '보관함': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7.5h6l2 2H21v9.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M3 7.5V6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v1.5"/></svg>',
    '보관함 Beta': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7.5h6l2 2H21v9.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M8 14h8M12 10v8"/></svg>',
    '마이페이지': '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4.5 21a7.5 7.5 0 0 1 15 0"/></svg>',
    '구독 및 사용량': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
    '사용현황': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
    '업체 정보': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 21V8l8-5 8 5v13"/><path d="M9 21v-6h6v6M8 10h.01M12 10h.01M16 10h.01"/></svg>',
    '딸깍 제작': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13 2 4 14h7l-1 8 9-12h-7z"/></svg>',
    '릴스/숏츠': '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="3" width="16" height="18" rx="3"/><path d="m10 9 5 3-5 3z"/></svg>',
    '팟캐스트': '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="3" width="8" height="12" rx="4"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6"/></svg>',
    '체험 연구실': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6M10 3v5l-5 9a2.5 2.5 0 0 0 2.2 4h9.6A2.5 2.5 0 0 0 19 17l-5-9V3"/><path d="M8 15h8"/></svg>'
  };

  function ensureMenuIconStyle() {
    if (document.getElementById('storymaker-v1-menu-icon-style')) return;
    const style = document.createElement('style');
    style.id = 'storymaker-v1-menu-icon-style';
    style.textContent = `
      .sm-v1-menu-item{position:relative!important;display:flex!important;align-items:center!important;gap:12px!important;min-height:46px!important;border-radius:12px!important;transition:background-color .18s ease,color .18s ease,transform .18s ease,box-shadow .18s ease!important}
      .sm-v1-menu-item .sm-v1-menu-icon{width:20px!important;height:20px!important;min-width:20px!important;max-width:20px!important;min-height:20px!important;max-height:20px!important;display:inline-flex!important;align-items:center!important;justify-content:center!important;flex:0 0 20px!important;overflow:hidden!important;color:#94a3b8;transition:color .18s ease,transform .18s ease!important}
      .sm-v1-menu-item .sm-v1-menu-icon svg{display:block!important;width:20px!important;height:20px!important;min-width:20px!important;max-width:20px!important;min-height:20px!important;max-height:20px!important;flex:0 0 20px!important;fill:none!important;stroke:currentColor!important;stroke-width:1.8!important;stroke-linecap:round!important;stroke-linejoin:round!important}
      .sm-v1-menu-item:hover{background:rgba(56,189,248,.12)!important;color:#e0f2fe!important;transform:translateX(2px)}
      .sm-v1-menu-item:hover .sm-v1-menu-icon{color:#38bdf8;transform:scale(1.08)}
      .sm-v1-menu-item[data-sm-menu-active="1"],.sm-v1-menu-item[aria-current="page"],.sm-v1-menu-item.is-active,.sm-v1-menu-item.active{background:linear-gradient(90deg,rgba(56,189,248,.22),rgba(59,130,246,.12))!important;color:#7dd3fc!important;box-shadow:inset 3px 0 0 #38bdf8!important}
      .sm-v1-menu-item[data-sm-menu-active="1"] .sm-v1-menu-icon,.sm-v1-menu-item[aria-current="page"] .sm-v1-menu-icon,.sm-v1-menu-item.is-active .sm-v1-menu-icon,.sm-v1-menu-item.active .sm-v1-menu-icon{color:#38bdf8!important}
      @media (prefers-reduced-motion:reduce){.sm-v1-menu-item,.sm-v1-menu-item .sm-v1-menu-icon{transition:none!important}.sm-v1-menu-item:hover{transform:none}}
    `;
    document.head.appendChild(style);
  }

  function findMenuClickable(textNode) {
    let node = textNode?.parentElement;
    while (node && node !== document.body) {
      if (node.matches?.('button,a,[role="button"],[tabindex]')) return node;
      const rect = node.getBoundingClientRect?.();
      if (rect && rect.width >= 130 && rect.width <= 360 && rect.height >= 34 && rect.height <= 70) return node;
      node = node.parentElement;
    }
    return null;
  }

  function installMenuIcons() {
    ensureMenuIconStyle();
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const textNodes = [];
    let current;
    while ((current = walker.nextNode())) textNodes.push(current);

    textNodes.forEach((textNode) => {
      const label = clean(textNode.nodeValue);
      const icon = MENU_ICONS[label];
      if (!icon) return;
      const clickable = findMenuClickable(textNode);
      if (!clickable || clickable.dataset.smMenuIconBound === '1') return;
      clickable.dataset.smMenuIconBound = '1';
      clickable.classList.add('sm-v1-menu-item');
      const iconNode = document.createElement('span');
      iconNode.className = 'sm-v1-menu-icon';
      iconNode.innerHTML = icon;
      iconNode.setAttribute('aria-hidden', 'true');
      clickable.insertBefore(iconNode, clickable.firstChild);
      clickable.addEventListener('click', () => {
        document.querySelectorAll('.sm-v1-menu-item[data-sm-menu-active="1"]').forEach((node) => node.removeAttribute('data-sm-menu-active'));
        clickable.dataset.smMenuActive = '1';
      }, true);
    });
  }

  function removeExistingMenuIcons() {
    const menuLabels = new Set([
      '대시보드', '새 콘텐츠 만들기', '진행 중 작업', '보관함', '보관함 Beta',
      '마이페이지', '구독 및 사용량', '사용현황', '업체 정보', '딸깍 제작',
      '릴스/쇼츠', '팟캐스트', '체험 연구실', '회원 관리', '요청사항', '요금제',
      '작업큐', '업종별 관리'
    ]);
    document.querySelectorAll('nav').forEach((nav) => {
      nav.querySelectorAll('button,a,[role="button"]').forEach((node) => {
        const label = clean(node.textContent).replace(/\s*BETA\s*$/i, '').trim();
        if (!menuLabels.has(label)) return;
        node.querySelectorAll('.sm-v1-menu-icon,svg').forEach((icon) => icon.remove());
        node.classList.remove('sm-v1-menu-item');
      });
    });
  }

  function renameCreationMenu() {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let textNode;
    while ((textNode = walker.nextNode())) {
      if (clean(textNode.nodeValue) !== '딸깍 제작') continue;
      textNode.nodeValue = String(textNode.nodeValue || '').replace('딸깍 제작', '새 콘텐츠 제작');
    }
  }

  function install() {
    installBrand();
    installHardcodedButtons();
    renameCreationMenu();
    removeExistingMenuIcons();
    installMenuIcons();
  }

  document.addEventListener('click', (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    const button = target.closest('button,a,[role="button"]');
    if (button && clean(button.textContent).includes(HOME_BUTTON_TEXT)) goHome(event);
  }, true);

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    const button = target.closest('button,a,[role="button"]');
    if (button && clean(button.textContent).includes(HOME_BUTTON_TEXT)) goHome(event);
  }, true);

  install();
  new MutationObserver(install).observe(document.documentElement, { childList: true, subtree: true });
})();
