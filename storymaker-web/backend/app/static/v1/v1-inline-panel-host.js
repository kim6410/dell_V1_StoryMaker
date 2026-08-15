(() => {
  'use strict';

  if (window.StoryMakerV1InlinePanels) return;

  const HOST_ID = 'storymaker-v1-inline-panel-host';
  const BODY_ID = 'storymaker-v1-inline-panel-body';
  const TITLE_ID = 'storymaker-v1-inline-panel-title';
  const hiddenSiblings = new Map();

  const clean = (value = '') => String(value).replace(/\s+/g, ' ').trim();

  function findDashboardMount() {
    const root = document.getElementById('root') || document.body;
    const sections = Array.from(document.querySelectorAll('section,main,div'));
    const contentArea = sections.find((node) => {
      const className = String(node.className || '');
      const rect = node.getBoundingClientRect?.();
      return className.includes('flex-1') && rect && rect.width > 360 && rect.height > 260;
    });
    return contentArea || document.querySelector('main') || root || document.body;
  }

  function ensureHost() {
    let host = document.getElementById(HOST_ID);
    if (host) return host;

    host = document.createElement('section');
    host.id = HOST_ID;
    host.hidden = true;
    host.innerHTML = `
      <style>
        #${HOST_ID}{width:100%;margin:14px 0 18px;border:1px solid rgba(103,232,249,.22);border-radius:22px;background:rgba(7,17,38,.96);box-shadow:0 18px 50px rgba(0,0,0,.22);overflow:hidden;color:#fff;box-sizing:border-box}
        #${HOST_ID}[hidden]{display:none!important}
        #${HOST_ID} *{box-sizing:border-box}
        .sm-v1-inline-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;border-bottom:1px solid rgba(148,163,184,.18);background:linear-gradient(135deg,rgba(15,23,42,.98),rgba(8,47,73,.78))}
        .sm-v1-inline-title{font-size:15px;font-weight:950;color:#e0f2fe;letter-spacing:-.01em}
        .sm-v1-inline-close{border:1px solid rgba(148,163,184,.35);background:#0f172a;color:#e2e8f0;border-radius:12px;padding:8px 12px;font-weight:900;cursor:pointer}
        #${HOST_ID}.sm-v1-inline-headless .sm-v1-inline-head{display:none!important}
        #${BODY_ID}{width:100%;min-height:min(720px,calc(100vh - 210px));background:#071126}
        @media(max-width:720px){#${HOST_ID}{border-radius:16px;margin:10px 0}#${BODY_ID}{min-height:640px}.sm-v1-inline-head{padding:12px}}
      </style>
      <div class="sm-v1-inline-head">
        <div id="${TITLE_ID}" class="sm-v1-inline-title">V1 dashboard panel</div>
        <button type="button" class="sm-v1-inline-close" data-sm-v1-inline-close>닫기</button>
      </div>
      <div id="${BODY_ID}"></div>
    `;

    const mount = findDashboardMount();
    const currentScreenHeader = Array.from(mount.children || []).find((node) => clean(node.textContent).includes('현재 화면'));
    if (currentScreenHeader?.nextSibling) {
      currentScreenHeader.parentNode.insertBefore(host, currentScreenHeader.nextSibling);
    } else if (mount.prepend) {
      mount.prepend(host);
    } else {
      mount.appendChild(host);
    }

    host.querySelector('[data-sm-v1-inline-close]')?.addEventListener('click', () => close());
    return host;
  }

  function hideDashboardSiblings(host) {
    const parent = host?.parentElement;
    if (!parent) return;
    Array.from(parent.children).forEach((node) => {
      if (node === host || node.id === HOST_ID) return;
      if (!hiddenSiblings.has(node)) {
        hiddenSiblings.set(node, {
          hidden: node.hidden,
          display: node.style.display,
        });
      }
      node.hidden = true;
      node.style.display = 'none';
    });
  }

  function restoreDashboardSiblings() {
    hiddenSiblings.forEach((state, node) => {
      if (!node?.isConnected) return;
      node.hidden = state.hidden;
      node.style.display = state.display;
      if (!state.hidden) node.removeAttribute('hidden');
    });
    hiddenSiblings.clear();
  }

  function open(key = 'panel', title = 'V1 dashboard panel') {
    const host = ensureHost();
    hideDashboardSiblings(host);
    host.dataset.panelKey = key;
    host.classList.toggle('sm-v1-inline-headless', key === 'staged-production');
    host.hidden = false;
    host.removeAttribute('hidden');
    const titleNode = host.querySelector(`#${TITLE_ID}`);
    if (titleNode) titleNode.textContent = title;
    const body = host.querySelector(`#${BODY_ID}`);
    if (body) body.innerHTML = '';
    host.scrollIntoView({block: 'nearest', behavior: 'smooth'});
    return body;
  }

  function close() {
    const host = document.getElementById(HOST_ID);
    if (!host) return;
    clearInlineMenuState();
    host.hidden = true;
    host.setAttribute('hidden', 'true');
    const body = host.querySelector(`#${BODY_ID}`);
    if (body) body.innerHTML = '';
    restoreDashboardSiblings();
  }

  function getBody() {
    return ensureHost().querySelector(`#${BODY_ID}`);
  }

  function isSidebarMenuClick(target) {
    if (!target || target.closest?.(`#${HOST_ID}`)) return false;

    let clickable = target.closest?.('button,a,[role="button"]') || target;
    while (clickable && clickable !== document.body) {
      const rect = clickable.getBoundingClientRect?.();
      if (rect) {
        const inLeftSidebar = rect.left >= 0 && rect.left < 340 && rect.right <= 380;
        const menuSized = rect.width >= 100 && rect.width <= 340 && rect.height >= 28 && rect.height <= 100;
        const label = clean(clickable.textContent);
        if (inLeftSidebar && menuSized && label) {
          const ignoredLabels = new Set(['닫기', '새로고침', '복사']);
          return !ignoredLabels.has(label);
        }
      }
      clickable = clickable.parentElement;
    }
    return false;
  }

  function keepNewDashboardContentHidden() {
    const host = document.getElementById(HOST_ID);
    if (!host || host.hidden) return;
    hideDashboardSiblings(host);
  }

  function clearInlineMenuState() {
    document.querySelectorAll('.sm-v1-request-menu.is-active').forEach((node) => {
      node.classList.remove('is-active');
    });
  }

  document.addEventListener('click', (event) => {
    if (!isSidebarMenuClick(event.target)) return;
    clearInlineMenuState();
    close();
  }, true);

  const routeObserver = new MutationObserver(() => {
    window.requestAnimationFrame(keepNewDashboardContentHidden);
  });
  routeObserver.observe(document.documentElement, {childList: true, subtree: true});

  window.StoryMakerV1InlinePanels = { ensureHost, open, close, getBody };
  console.info('[StoryMaker V1] inline dashboard panel host active');
})();
