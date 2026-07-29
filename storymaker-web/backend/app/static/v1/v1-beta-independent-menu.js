(() => {
  'use strict';

  const MENU_ITEMS = [
    {
      key: 'betaProduction',
      label: '새 콘텐츠 제작',
      src: '/v1/beta/production',
      icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>',
    },
    {
      key: 'betaArchive',
      label: '보관함',
      src: '/v1/beta/archive',
      icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7.5h6l2 2h10v9.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M3 7.5V6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v1.5"/></svg>',
    },
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

  const COMPANY_INFO_ICON = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/></svg>';

  function ensureCompanyInfoIcon(button) {
    if (!button || button.querySelector('.storymaker-company-info-menu-row')) return;

    const label = String(button.textContent || '').trim() || '업체 정보';
    const row = document.createElement('span');
    row.className = 'storymaker-company-info-menu-row';
    row.style.setProperty('display', 'flex', 'important');
    row.style.setProperty('flex-direction', 'row', 'important');
    row.style.setProperty('align-items', 'center', 'important');
    row.style.setProperty('gap', '12px', 'important');
    row.style.setProperty('width', '100%', 'important');
    row.style.setProperty('white-space', 'nowrap', 'important');

    const icon = document.createElement('span');
    icon.className = 'storymaker-company-info-menu-icon';
    icon.style.setProperty('display', 'inline-flex', 'important');
    icon.style.setProperty('align-items', 'center', 'important');
    icon.style.setProperty('justify-content', 'center', 'important');
    icon.style.setProperty('width', '20px', 'important');
    icon.style.setProperty('height', '20px', 'important');
    icon.style.setProperty('flex', '0 0 20px', 'important');
    icon.style.setProperty('color', '#22d3ee', 'important');
    icon.setAttribute('aria-hidden', 'true');
    icon.innerHTML = COMPANY_INFO_ICON;

    const text = document.createElement('span');
    text.className = 'storymaker-company-info-menu-label';
    text.style.setProperty('display', 'inline-block', 'important');
    text.style.setProperty('white-space', 'nowrap', 'important');
    text.style.setProperty('line-height', '1.25', 'important');
    text.textContent = label;

    row.append(icon, text);
    button.replaceChildren(row);
  }

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
            <span class="mt-1 block text-lg font-black text-white">새 콘텐츠 제작</span>
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
      button.innerHTML = `<span class="flex w-full items-center justify-between gap-3"><span class="flex min-w-0 items-center gap-3"><span class="storymaker-beta-menu-icon inline-flex h-5 w-5 shrink-0 items-center justify-center text-cyan-300" aria-hidden="true">${item.icon || ''}</span><span class="truncate">${item.label}</span></span><span class="shrink-0 rounded-full border border-cyan-300/40 bg-cyan-300/10 px-2 py-0.5 text-[10px] font-semibold text-cyan-200">BETA</span></span>`;
      button.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        openBeta(item);
      });
      const companyButton = Array.from(nav.querySelectorAll('button')).find((candidate) =>
        String(candidate.textContent || '').includes('업체 정보')
      );
      if (companyButton) {
        ensureCompanyInfoIcon(companyButton);
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

  function focusDashboardUsagePanel() {
    let attempts = 0;
    const focus = () => {
      attempts += 1;
      const panel = document.getElementById('v1-dashboard-usage-panel');
      if (panel) {
        const usageButton = panel.querySelector('[data-v1d-usage]');
        const detail = panel.querySelector('[data-v1d-detail]');
        if (detail?.hidden && usageButton instanceof HTMLElement) usageButton.click();
        window.setTimeout(() => {
          const focusTarget = panel.querySelector('[data-v1d-detail]:not([hidden])') || panel;
          focusTarget.setAttribute('tabindex', '-1');
          focusTarget.scrollIntoView({ behavior: 'smooth', block: 'center' });
          focusTarget.focus({ preventScroll: true });
          focusTarget.animate(
            [
              { boxShadow: '0 0 0 0 rgba(34,211,238,0)' },
              { boxShadow: '0 0 0 5px rgba(34,211,238,.42)' },
              { boxShadow: '0 0 0 0 rgba(34,211,238,0)' },
            ],
            { duration: 2200, easing: 'ease-out' }
          );
        }, 180);
        return;
      }
      if (attempts < 40) window.setTimeout(focus, 100);
    };
    focus();
  }

  const QUEUE_SUMMARY_URL = '/v1/beta-api/gemini-worker/queue-summary';
  let queueSummaryTimer = 0;
  let queueSummaryLoading = false;

  function formatQueueWait(seconds, status, position) {
    if (status === 'claimed' || status === 'sent') return '처리 중';
    if (!position) return '바로 시작 가능';
    const safeSeconds = Math.max(0, Number(seconds || 0));
    if (safeSeconds < 60) return safeSeconds > 0 ? '약 1분 이내' : '곧 시작';
    return `약 ${Math.max(1, Math.ceil(safeSeconds / 60))}분`;
  }

  function removeLegacyQueueCards() {
    const aside = document.querySelector('aside');
    if (!aside) return;

    Array.from(aside.querySelectorAll('section')).forEach((section) => {
      if (section.id === 'storymaker-live-queue-summary') return;
      const text = String(section.textContent || '');
      if (text.includes('QUEUE') && text.includes('작업 현황')) section.remove();
    });
  }

  function findQueueSummaryHost() {
    const aside = document.querySelector('aside');
    if (!aside) return null;

    removeLegacyQueueCards();
    const existing = aside.querySelector('#storymaker-live-queue-summary');
    if (existing) return existing;

    const nav = aside.querySelector('nav');
    if (!nav) return null;
    const section = document.createElement('section');
    section.id = 'storymaker-live-queue-summary';
    section.className = 'mt-[11px] rounded-[1.5rem] border border-cyan-300/20 bg-slate-900/80 p-4 shadow-xl shadow-cyan-950/20';
    aside.insertBefore(section, nav);
    return section;
  }

  function renderQueueSummary(data) {
    const card = findQueueSummaryHost();
    if (!card) return;
    card.id = 'storymaker-live-queue-summary';
    card.removeAttribute('role');
    card.removeAttribute('tabindex');
    card.style.cursor = 'default';

    const processingCount = Math.max(0, Number(data?.processing_count || 0));
    const position = data?.my_position == null ? null : Math.max(1, Number(data.my_position));
    const status = String(data?.my_status || 'idle');
    const positionLabel = status === 'claimed' || status === 'sent'
      ? '처리 중'
      : position
        ? `${position}번째`
        : '대기 없음';
    const waitLabel = formatQueueWait(data?.estimated_wait_seconds, status, position);
    const badge = processingCount > 0 ? '작업 중' : '원활';

    card.innerHTML = `
      <div class="flex items-start justify-between gap-3">
        <div>
          <p class="text-xs font-black tracking-[0.18em] text-cyan-300 uppercase">QUEUE</p>
          <h3 class="mt-1 text-base font-black text-white">실시간 대기열</h3>
        </div>
        <span class="shrink-0 rounded-full bg-cyan-300/10 px-3 py-1 text-xs font-black text-cyan-200">${badge}</span>
      </div>
      <dl class="mt-4 space-y-2.5 text-sm font-bold">
        <div class="flex items-center justify-between gap-3"><dt class="text-slate-400">현재 처리 작업</dt><dd class="shrink-0 text-white">${processingCount}건</dd></div>
        <div class="flex items-center justify-between gap-3"><dt class="text-slate-400">내 작업 순번</dt><dd class="shrink-0 text-cyan-100">${positionLabel}</dd></div>
        <div class="flex items-center justify-between gap-3"><dt class="text-slate-400">대기시간</dt><dd class="shrink-0 text-cyan-100">${waitLabel}</dd></div>
      </dl>
    `;
  }

  async function refreshQueueSummary() {
    if (queueSummaryLoading || document.hidden) return;
    queueSummaryLoading = true;
    try {
      const response = await fetch(QUEUE_SUMMARY_URL, {
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      renderQueueSummary(payload?.data || {});
    } catch (_) {
      renderQueueSummary({ processing_count: 0, my_position: null, my_status: 'idle', estimated_wait_seconds: 0 });
    } finally {
      queueSummaryLoading = false;
    }
  }

  function startQueueSummary() {
    refreshQueueSummary();
    if (queueSummaryTimer) return;
    queueSummaryTimer = window.setInterval(refreshQueueSummary, 5000);
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) refreshQueueSummary();
    });
  }

  window.addEventListener('message', (event) => {
    if (event.origin !== window.location.origin) return;
    if (event.data?.type !== 'storymaker:navigate-dashboard') return;
    restoreNormalContent();
    syncBetaMenuSelection('');
    history.pushState({}, '', '/v1/#v1-dashboard-usage-panel');
    window.dispatchEvent(new PopStateEvent('popstate'));
    focusDashboardUsagePanel();
  });

  const observer = new MutationObserver(() => {
    installMenu();
    removeLegacyQueueCards();
    if (!document.getElementById('storymaker-live-queue-summary')) refreshQueueSummary();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
  installMenu();
  removeLegacyQueueCards();
  startQueueSummary();
})();
