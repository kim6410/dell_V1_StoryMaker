(() => {
  'use strict';

  const MENU_ITEMS = [
    { key: 'betaProduction', label: '딸깍 제작', src: '/v1/beta/production' },
    { key: 'betaArchive', label: '보관함', src: '/v1/beta/archive' },
  ];

  function findNav() {
    return Array.from(document.querySelectorAll('nav')).find((nav) =>
      Array.from(nav.querySelectorAll('button')).some((button) => {
        const label = String(button.textContent || '').trim();
        return label.includes('업체 정보') || label.includes('요청사항') || label.includes('요금제');
      })
    );
  }

  const ACTIVE_MENU_CLASSES = [
    'border', 'border-blue-900/80', 'bg-gradient-to-br',
    'from-slate-900', 'via-blue-950', 'to-blue-900', 'text-blue-50'
  ];

  function syncBetaMenuSelection(activeKey = '') {
    const nav = findNav();
    if (!nav) return;

    nav.querySelectorAll('button').forEach((button) => {
      button.removeAttribute('aria-current');
      button.removeAttribute('data-active');
      ACTIVE_MENU_CLASSES.forEach((className) => button.classList.remove(className));
    });

    if (!activeKey) return;
    const activeButton = nav.querySelector(`[data-storymaker-beta-key="${activeKey}"]`);
    if (!activeButton) return;
    activeButton.setAttribute('data-active', '1');
    activeButton.setAttribute('aria-current', 'page');
    ACTIVE_MENU_CLASSES.forEach((className) => activeButton.classList.add(className));
  }

  function findContentSection() {
    return Array.from(document.querySelectorAll('main section')).find((section) =>
      section.className && String(section.className).includes('min-w-0') && String(section.className).includes('flex-1')
    );
  }

  function restoreNormalContent() {
    const section = findContentSection();
    const panel = document.getElementById('storymaker-beta-independent-panel');
    if (panel) panel.remove();
    if (section) {
      Array.from(section.children).forEach((child) => {
        if (child instanceof HTMLElement) child.style.removeProperty('display');
      });
    }
    document.querySelectorAll('[data-storymaker-beta-menu="1"]').forEach((button) => {
      button.removeAttribute('data-active');
      button.removeAttribute('aria-current');
      ACTIVE_MENU_CLASSES.forEach((className) => button.classList.remove(className));
    });
  }

  function openBeta(item, updateHistory = true) {
    const section = findContentSection();
    if (!section) return;

    restoreNormalContent();
    Array.from(section.children).forEach((child) => {
      if (child instanceof HTMLElement) child.style.display = 'none';
    });

    const panel = document.createElement('div');
    panel.id = 'storymaker-beta-independent-panel';
    panel.style.display = 'block';
    panel.className = 'overflow-hidden rounded-3xl border border-cyan-300/20 bg-slate-950 shadow-2xl';
    panel.style.width = '100%';
    panel.style.maxWidth = '100%';
    panel.style.height = 'calc(100vh - 32px)';
    panel.style.minHeight = '820px';
    panel.innerHTML = `
      <iframe
        title="${item.label}"
        src="${item.src}"
        class="block w-full border-0 bg-slate-950"
        style="display:block;width:100%;height:100%;min-height:820px;border:0;background:#020617"
        loading="eager"
        referrerpolicy="same-origin"
      ></iframe>
    `;
    section.appendChild(panel);
    panel.querySelector('[data-beta-close="1"]')?.addEventListener('click', () => {
      restoreNormalContent();
      history.pushState({}, '', '/v1/');
    });

    syncBetaMenuSelection(item.key);
    if (updateHistory) history.pushState({}, '', `/v1/?page=${encodeURIComponent(item.key)}`);
  }

  function installDashboardButtons() {
    {
      const existingDashboardCard = document.getElementById('storymaker-beta-dashboard-actions');
      if (existingDashboardCard) existingDashboardCard.remove();
      return;
    }

    const section = findContentSection();
    if (!section) return;

    const currentTitle = Array.from(section.querySelectorAll('h2')).find((node) =>
      String(node.textContent || '').trim() === '대시보드'
    );
    const existing = document.getElementById('storymaker-beta-dashboard-actions');

    if (!currentTitle || document.getElementById('storymaker-beta-independent-panel')) {
      if (existing) existing.remove();
      return;
    }
    if (existing) return;

    const actions = document.createElement('section');
    actions.id = 'storymaker-beta-dashboard-actions';
    actions.className = 'mb-5 overflow-hidden rounded-[2rem] border border-cyan-300/25 bg-gradient-to-br from-slate-900 via-slate-900 to-cyan-950/50 p-5 shadow-2xl shadow-cyan-950/25 ring-1 ring-white/5';
    actions.innerHTML = `
      <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div class="flex items-center gap-2">
            <span class="rounded-full border border-cyan-300/40 bg-cyan-300/10 px-3 py-1 text-[11px] font-black tracking-[0.14em] text-cyan-200">DELL BETA</span>
            <span class="text-xs font-bold text-slate-400">V1 내부 완전 독립 실행</span>
          </div>
          <h3 class="mt-3 text-2xl font-black text-white">새로운 Beta 제작 흐름</h3>
          <p class="mt-2 text-sm leading-6 text-slate-300">Windows Beta의 제작 데이터와 보관함을 Dell V1 안에서 독립적으로 사용합니다.</p>
        </div>
        <div class="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[430px]">
          <button type="button" data-beta-dashboard-key="betaProduction" class="group rounded-2xl border border-cyan-300/35 bg-cyan-300/10 px-5 py-4 text-left shadow-lg shadow-cyan-950/20 transition hover:-translate-y-0.5 hover:border-cyan-200 hover:bg-cyan-300/20">
            <span class="block text-xs font-black tracking-[0.14em] text-cyan-300">BETA PRODUCTION</span>
            <span class="mt-1 block text-lg font-black text-white">딸깍 제작</span>
            <span class="mt-1 block text-xs font-bold text-slate-400">콘텐츠·음성·숏폼 자동 제작</span>
          </button>
          <button type="button" data-beta-dashboard-key="betaArchive" class="group rounded-2xl border border-violet-300/35 bg-violet-300/10 px-5 py-4 text-left shadow-lg shadow-violet-950/20 transition hover:-translate-y-0.5 hover:border-violet-200 hover:bg-violet-300/20">
            <span class="block text-xs font-black tracking-[0.14em] text-violet-300">BETA ARCHIVE</span>
            <span class="mt-1 block text-lg font-black text-white">보관함</span>
            <span class="mt-1 block text-xs font-bold text-slate-400">글·MP3·SRT·썸네일·MP4 확인</span>
          </button>
        </div>
      </div>
    `;

    const headerCard = Array.from(section.children).find((child) =>
      child instanceof HTMLElement && String(child.textContent || '').includes('현재 화면')
    );
    if (headerCard && headerCard.nextSibling) section.insertBefore(actions, headerCard.nextSibling);
    else section.prepend(actions);

    actions.querySelectorAll('[data-beta-dashboard-key]').forEach((button) => {
      button.addEventListener('click', () => {
        const item = MENU_ITEMS.find((entry) => entry.key === button.getAttribute('data-beta-dashboard-key'));
        if (item) openBeta(item);
      });
    });
  }

  function installMenu() {
    installDashboardButtons();
    const nav = findNav();
    if (!nav) return;
    if (nav.querySelector('[data-storymaker-beta-menu="1"]')) {
      const panel = document.getElementById('storymaker-beta-independent-panel');
      if (panel) {
        const requestedKey = new URLSearchParams(location.search).get('page') || '';
        const activeItem = MENU_ITEMS.find((entry) => entry.key === requestedKey);
        if (activeItem) syncBetaMenuSelection(activeItem.key);
      }
      return;
    }

    const template = nav.querySelector('button');
    MENU_ITEMS.forEach((item, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.storymakerBetaMenu = '1';
      button.dataset.storymakerBetaKey = item.key;
      button.className = template?.className || 'rounded-lg px-4 py-3.5 text-left text-lg font-black text-slate-100 hover:bg-slate-900';
      button.innerHTML = `<span class="flex w-full items-center justify-between gap-3"><span>${item.label}</span><span class="rounded-full border border-cyan-300/40 bg-cyan-300/10 px-2 py-0.5 text-[10px] font-semibold text-cyan-200">BETA</span></span>`;
      button.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        openBeta(item);
      });
      const companyButton = Array.from(nav.querySelectorAll('button')).find((candidate) =>
        String(candidate.textContent || '').includes('업체 정보')
      );
      if (companyButton) {
        nav.insertBefore(button, companyButton);
      } else {
        nav.appendChild(button);
      }
    });

    nav.addEventListener('click', (event) => {
      const target = event.target instanceof Element ? event.target.closest('button') : null;
      if (target && !target.matches('[data-storymaker-beta-menu="1"]')) restoreNormalContent();
    }, true);

    const requested = new URLSearchParams(location.search).get('page');
    const item = MENU_ITEMS.find((entry) => entry.key === requested);
    if (item) setTimeout(() => openBeta(item, false), 100);
  }

  const observer = new MutationObserver(installMenu);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  installMenu();
})();
