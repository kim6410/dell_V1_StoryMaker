(() => {
  'use strict';

  if (window.__STORYMAKER_V1_DASHBOARD_INLINE_LABS_V2__) return;
  window.__STORYMAKER_V1_DASHBOARD_INLINE_LABS_V2__ = true;

  if (new URLSearchParams(location.search).get('inline_lab_frame') === '1') return;

  const normalize = value => String(value || '').replace(/\s+/g, ' ').trim();
  let adminAccess = false;
  let adminResolved = false;

  function isAdminUser(user) {
    if (!user || typeof user !== 'object') return false;
    const role = normalize(user.role || user.user_role || user.type).toLowerCase();
    return user.is_admin === true
      || user.is_admin === 1
      || user.admin === true
      || user.admin === 1
      || role === 'admin'
      || role === 'administrator';
  }

  async function resolveAdminAccess() {
    try {
      const response = await fetch('/v1-api/auth/me', {
        credentials: 'include',
        cache: 'no-store',
        headers: { Accept: 'application/json' },
      });
      const payload = response.ok ? await response.json().catch(() => ({})) : {};
      const user = payload?.data?.user || payload?.user || payload?.data || null;
      adminAccess = response.ok && isAdminUser(user);
    } catch (_) {
      adminAccess = false;
    } finally {
      adminResolved = true;
      scheduleTagCards();
    }
  }

  function removeNextWorkList(root) {
    const heading = Array.from(root.querySelectorAll('h1,h2,h3,h4,p,span,div'))
      .find(node => normalize(node.textContent) === '다음 작업 목록');
    if (!heading) return;

    let card = heading.closest('section,article');
    if (!card) {
      card = heading.parentElement;
      while (card && card !== root && card.parentElement) {
        const text = normalize(card.textContent);
        const rect = card.getBoundingClientRect?.();
        if (text.includes('업체 DB') && text.includes('프로젝트') && rect?.width > 500) break;
        card = card.parentElement;
      }
    }
    if (card && card !== root) card.remove();
  }

  const HOST_ID = 'v1-dashboard-inline-lab-host';
  const HIDDEN_CLASS = 'v1-inline-dashboard-hidden';

  const LABS = {
    experience: {
      title: 'AI 연구실',
      subtitle: 'WebGPU · 로컬 실험 도구',
      url: '/v1/?page=experienceLab&inline_lab_frame=1'
    },
    nemotron: {
      title: '네모트론 연구실',
      subtitle: '대화 · 번역 · 프롬프트 실험',
      url: '/static/v1/nemotron-lab/index.html?inline_lab_frame=1'
    },
    voicebox: {
      title: 'VoiceBox Studio',
      subtitle: '내 목소리 · 30초 청크 · 생성/재생성 · 최종 음성 제작',
      url: '/static/v1/voicebox-studio.html?from=v1-admin&inline_lab_frame=1'
    }
  };

  let activeType = '';
  let dashboardContainer = null;
  let hiddenNodes = [];
  let tagFrame = 0;

  function ensureStyles() {
    if (document.getElementById('v1-dashboard-inline-labs-style-v2')) return;
    const style = document.createElement('style');
    style.id = 'v1-dashboard-inline-labs-style-v2';
    style.textContent = `
      .${HIDDEN_CLASS}{display:none!important}
      #${HOST_ID}{display:none;width:100%;min-width:0;margin:0;padding:0}
      #${HOST_ID}.open{display:block}
      #${HOST_ID} .v1-inline-shell{position:relative;width:calc(100% - 28px);min-width:0;margin:14px;border:1px solid rgba(103,232,249,.28);border-radius:24px;background:#020617;box-shadow:0 22px 55px rgba(2,6,23,.42),inset 0 0 0 1px rgba(139,92,246,.08);overflow:hidden}
      #${HOST_ID} .v1-inline-shell::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:linear-gradient(180deg,#67e8f9,#8b5cf6);z-index:3;pointer-events:none}
      #${HOST_ID} .v1-inline-toolbar{display:none!important}
      #${HOST_ID} .v1-inline-heading{min-width:0}
      #${HOST_ID} .v1-inline-title{font-size:16px;font-weight:900;color:#f8fbff}
      #${HOST_ID} .v1-inline-subtitle{margin-top:2px;font-size:12px;font-weight:700;color:#8ca5c8}
      #${HOST_ID} .v1-inline-actions{display:flex;align-items:center;gap:8px}
      #${HOST_ID} .v1-inline-switch,#${HOST_ID} .v1-inline-close{border:1px solid rgba(103,232,249,.28);border-radius:999px;background:#0a1730;color:#dffbff;padding:8px 13px;font-size:12px;font-weight:900;cursor:pointer;white-space:nowrap}
      #${HOST_ID} .v1-inline-switch.active{border-color:#67e8f9;background:rgba(8,145,178,.22);color:#fff}
      #${HOST_ID} .v1-inline-frame-wrap{display:none;width:100%;min-width:0;background:#020617}
      #${HOST_ID} .v1-inline-frame-wrap.active{display:block}
      #${HOST_ID} iframe{display:block;width:100%;height:calc(130vh - 247px);min-height:936px;border:0;background:#020617}
      @media(max-width:900px){
        #${HOST_ID} .v1-inline-toolbar{align-items:flex-start;flex-direction:column}
        #${HOST_ID} .v1-inline-actions{width:100%;flex-wrap:wrap}
        #${HOST_ID} iframe{height:calc(130vh - 189px);min-height:832px}
      }
    `;
    document.head.appendChild(style);
  }

  function cardTypeFromText(text) {
    if (text.includes('네모트론 연구실') || text.includes('AI 연구실 2')) return 'nemotron';
    if (text.includes('AI 연구실') && text.includes('WebGPU')) return 'experience';
    return '';
  }

  function isCompanyCardText(text) {
    return text.includes('COMPANY') && !text.includes('최근 생성') && !text.includes('AI 연구실');
  }

  function openCompanyInfo() {
    const menuButton = Array.from(document.querySelectorAll('nav button, aside button, [role="navigation"] button'))
      .find(button => normalize(button.textContent) === '업체 정보');
    menuButton?.click();
  }

  function tagCards() {
    tagFrame = 0;
    const root = document.getElementById('root') || document.body;
    removeNextWorkList(root);

    root.querySelectorAll('[data-v1-inline-lab]').forEach(node => {
      node.removeAttribute('data-v1-inline-lab');
      node.style.removeProperty('display');
      node.style.removeProperty('cursor');
    });
    root.querySelectorAll('[data-v1-company-dashboard-link]').forEach(node => {
      node.removeAttribute('data-v1-company-dashboard-link');
      node.style.removeProperty('cursor');
    });

    const nodes = Array.from(root.querySelectorAll('button,a,[role="button"],section,article,div'))
      .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length);

    for (const node of nodes) {
      const text = normalize(node.textContent);
      if (!text || text.length > 150) continue;

      if (isCompanyCardText(text)) {
        if (node.querySelector('[data-v1-company-dashboard-link="1"]')) continue;
        node.dataset.v1CompanyDashboardLink = '1';
        node.style.cursor = 'pointer';
        continue;
      }

      const type = cardTypeFromText(text);
      if (!type || text.includes('COMPANY')) continue;
      if (node.querySelector(`[data-v1-inline-lab="${type}"]`)) continue;

      node.dataset.v1InlineLab = type;
      if (!adminResolved || !adminAccess) {
        node.style.setProperty('display', 'none', 'important');
        node.style.removeProperty('cursor');
      } else {
        node.style.removeProperty('display');
        node.style.cursor = 'pointer';
      }
    }
  }

  function scheduleTagCards() {
    if (tagFrame) return;
    tagFrame = requestAnimationFrame(tagCards);
  }

  function getTaggedCards() {
    return Array.from(document.querySelectorAll('[data-v1-inline-lab]'));
  }

  function commonAncestor(nodes) {
    if (!nodes.length) return null;
    let current = nodes[0];
    while (current && current !== document.body) {
      if (nodes.every(node => current.contains(node))) return current;
      current = current.parentElement;
    }
    return null;
  }

  function findDashboardContainer(trigger) {
    const cards = getTaggedCards();
    const main = trigger.closest('main') || document.querySelector('#root main') || document.querySelector('main');

    if (cards.length >= 2) {
      let ancestor = commonAncestor(cards);
      while (ancestor && ancestor !== main && ancestor.parentElement !== main) {
        const rect = ancestor.getBoundingClientRect();
        if (rect.width >= 500 && rect.height >= 220) break;
        ancestor = ancestor.parentElement;
      }
      if (ancestor && ancestor !== document.body && ancestor !== document.documentElement) return ancestor;
    }

    const card = trigger.closest('section,article,[class*="grid"],[class*="content"],div');
    if (card && main?.contains(card)) {
      let candidate = card;
      while (candidate.parentElement && candidate.parentElement !== main) {
        const parent = candidate.parentElement;
        const text = normalize(parent.textContent);
        if (text.includes('AI 연구실') && text.includes('네모트론 연구실')) candidate = parent;
        else break;
      }
      return candidate;
    }

    return main;
  }

  function createHost(container) {
    ensureStyles();
    let host = document.getElementById(HOST_ID);
    if (host && host.parentElement !== container) container.appendChild(host);
    if (host) return host;

    host = document.createElement('div');
    host.id = HOST_ID;
    host.innerHTML = `
      <div class="v1-inline-shell">
        <div class="v1-inline-toolbar">
          <div class="v1-inline-heading">
            <div class="v1-inline-title">AI 연구실</div>
            <div class="v1-inline-subtitle">WebGPU · 로컬 실험 도구</div>
          </div>
          <div class="v1-inline-actions">
            <button type="button" class="v1-inline-switch" data-switch-lab="experience">AI 연구실</button>
            <button type="button" class="v1-inline-switch" data-switch-lab="nemotron">네모트론 연구실</button>
            <button type="button" class="v1-inline-switch" data-switch-lab="voicebox">VoiceBox</button>
            <button type="button" class="v1-inline-close">대시보드로 돌아가기</button>
          </div>
        </div>
        <div class="v1-inline-frame-wrap" data-lab-frame="experience">
          <iframe title="StoryMaker V1 AI 연구실" loading="eager" allow="clipboard-read; clipboard-write; microphone; autoplay"></iframe>
        </div>
        <div class="v1-inline-frame-wrap" data-lab-frame="nemotron">
          <iframe title="StoryMaker V1 네모트론 연구실" loading="eager" allow="clipboard-read; clipboard-write; microphone; autoplay"></iframe>
        </div>
        <div class="v1-inline-frame-wrap" data-lab-frame="voicebox">
          <iframe title="StoryMaker V1 VoiceBox Studio" loading="eager" allow="clipboard-read; clipboard-write; microphone; autoplay"></iframe>
        </div>
      </div>
    `;
    host.querySelector('.v1-inline-close').addEventListener('click', closeLabs);
    host.querySelectorAll('[data-switch-lab]').forEach(button => {
      button.addEventListener('click', () => activateLab(button.dataset.switchLab));
    });
    container.appendChild(host);
    return host;
  }

  function hideDashboard(container, host) {
    hiddenNodes.forEach(node => node.classList.remove(HIDDEN_CLASS));
    hiddenNodes = [];
    Array.from(container.children).forEach(child => {
      if (child === host) return;
      child.classList.add(HIDDEN_CLASS);
      hiddenNodes.push(child);
    });

    const dashboardHeader = Array.from(document.querySelectorAll('main header, main section, main div'))
      .filter(node => {
        const text = normalize(node.textContent);
        return text.includes('현재 화면') && text.includes('대시보드') && text.includes('대시보드로 돌아가기');
      })
      .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length)[0];
    if (dashboardHeader && !hiddenNodes.includes(dashboardHeader)) {
      dashboardHeader.classList.add(HIDDEN_CLASS);
      hiddenNodes.push(dashboardHeader);
    }
  }

  function pauseFrame(frame) {
    try {
      const doc = frame.contentDocument;
      doc?.querySelectorAll('video,audio').forEach(media => {
        try { media.pause(); } catch (_) {}
        const stream = media.srcObject;
        if (stream?.getTracks) stream.getTracks().forEach(track => track.stop());
      });
    } catch (_) {}
  }

  function hideCompactBlockByText(doc, requiredTexts) {
    const candidates = Array.from(doc.querySelectorAll('header, section, article, div'));
    const matched = candidates
      .filter(node => requiredTexts.every(text => normalize(node.textContent).includes(text)))
      .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length)[0];
    if (matched) matched.style.setProperty('display', 'none', 'important');
  }

  function cleanExperienceFrame(frame) {
    try {
      const doc = frame.contentDocument;
      if (!doc) return;
      if (!doc.getElementById('v1-inline-experience-clean-style')) {
        const style = doc.createElement('style');
        style.id = 'v1-inline-experience-clean-style';
        style.textContent = `
          html,body{margin:0!important;min-height:100%!important;background:#020617!important;overflow:auto!important}
          body>div{min-height:100%!important}
          main{min-height:100%!important}
          main>header,body>header{display:none!important}
          main>div>aside{display:none!important}
          main>div{max-width:none!important;margin:0!important;min-height:100%!important}
          main>div>section{padding:18px!important;width:100%!important;max-width:none!important}
          .shell>.sidebar{display:none!important}
          .shell{display:block!important;min-height:100vh!important}
          .shell>main{width:100%!important;max-width:none!important;margin:0!important;padding:18px!important}
          .shell>main>.topbar{display:none!important}
          .grid.gap-5{grid-template-columns:minmax(0,1.08fr) minmax(360px,.92fr)!important;align-items:start!important}
          .grid.gap-5>section:nth-child(2),.grid.gap-5>aside:nth-child(2),.grid.gap-5>div:nth-child(2){position:sticky!important;top:18px!important;align-self:start!important}
          video,canvas{display:block!important;width:100%!important;height:auto!important;max-height:72vh!important;background:#000!important;border-radius:20px!important}
          @media(max-width:1180px){.grid.gap-5{grid-template-columns:1fr!important}.grid.gap-5>section:nth-child(2),.grid.gap-5>aside:nth-child(2),.grid.gap-5>div:nth-child(2){position:relative!important;top:auto!important}}
        `;
        doc.head.appendChild(style);
      }
      const hideExperienceChrome = () => {
        hideCompactBlockByText(doc, ['현재 화면', '체험 연구실']);
        hideCompactBlockByText(doc, ['간편한 숏폼 생성', '도움말']);
        hideCompactBlockByText(doc, ['브라우저 작업 로그', '로그 지우기']);
      };
      hideExperienceChrome();
      if (!doc.__v1InlineCleanupObserver && doc.body) {
        doc.__v1InlineCleanupObserver = new MutationObserver(hideExperienceChrome);
        doc.__v1InlineCleanupObserver.observe(doc.body, { childList: true, subtree: true });
      }

      doc.querySelectorAll('video').forEach(video => {
        video.controls = true;
        video.playsInline = true;
        video.preload = 'metadata';
      });
    } catch (_) {}
  }

  function cleanNemotronFrame(frame) {
    try {
      const doc = frame.contentDocument;
      if (!doc || doc.getElementById('v1-inline-nemotron-clean-style')) return;
      const style = doc.createElement('style');
      style.id = 'v1-inline-nemotron-clean-style';
      style.textContent = `
        html,body{margin:0!important;min-height:100%!important;background:#020617!important;overflow:auto!important}
        body>header,.sidebar,.app-sidebar,.left-sidebar{display:none!important}
        main,.main,.content,.app-main{width:100%!important;max-width:none!important;margin:0!important;padding:18px!important}
      `;
      doc.head.appendChild(style);
    } catch (_) {}
  }

  function cleanVoiceboxFrame(frame) {
    try {
      const doc = frame.contentDocument;
      if (!doc) return;
      doc.getElementById('back-to-v1')?.style.setProperty('display', 'none', 'important');
      doc.documentElement.style.background = '#020617';
      doc.body.style.margin = '0';
    } catch (_) {}
  }

  function prepareFrame(type, frame) {
    const clean = type === 'experience'
      ? cleanExperienceFrame
      : type === 'nemotron'
        ? cleanNemotronFrame
        : cleanVoiceboxFrame;
    frame.onload = () => {
      clean(frame);
      setTimeout(() => clean(frame), 350);
      setTimeout(() => clean(frame), 1000);
    };
    const wanted = new URL(LABS[type].url, location.origin).href;
    if (!frame.src || frame.src !== wanted) frame.src = LABS[type].url;
    else clean(frame);
  }

  function activateLab(type) {
    if (!LABS[type]) return;
    const host = document.getElementById(HOST_ID);
    if (!host) return;

    activeType = type;
    host.querySelector('.v1-inline-title').textContent = LABS[type].title;
    host.querySelector('.v1-inline-subtitle').textContent = LABS[type].subtitle;

    host.querySelectorAll('[data-switch-lab]').forEach(button => {
      button.classList.toggle('active', button.dataset.switchLab === type);
    });

    host.querySelectorAll('[data-lab-frame]').forEach(wrap => {
      const isActive = wrap.dataset.labFrame === type;
      wrap.classList.toggle('active', isActive);
      const frame = wrap.querySelector('iframe');
      if (isActive) prepareFrame(type, frame);
      else pauseFrame(frame);
    });
  }

  function openLab(type, trigger) {
    const container = findDashboardContainer(trigger);
    if (!container) return;
    dashboardContainer = container;
    const host = createHost(container);
    hideDashboard(container, host);
    host.classList.add('open');
    activateLab(type);
    host.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }

  function closeLabs() {
    const host = document.getElementById(HOST_ID);
    host?.querySelectorAll('iframe').forEach(pauseFrame);
    host?.classList.remove('open');
    hiddenNodes.forEach(node => node.classList.remove(HIDDEN_CLASS));
    hiddenNodes = [];
    activeType = '';
    if (dashboardContainer) dashboardContainer.scrollIntoView({ block: 'start', behavior: 'smooth' });
    dashboardContainer = null;
    scheduleTagCards();
  }

  document.addEventListener('click', event => {
    const companyCard = event.target.closest('[data-v1-company-dashboard-link="1"]');
    if (companyCard) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      openCompanyInfo();
      return;
    }

    const tagged = event.target.closest('[data-v1-inline-lab]');
    if (!tagged || !adminResolved || !adminAccess) return;
    const type = tagged.dataset.v1InlineLab;
    if (!LABS[type]) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    openLab(type, tagged);
  }, true);

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && activeType) closeLabs();
  });

  window.addEventListener('storymaker-open-inline-lab', event => {
    const type = event?.detail?.type;
    const trigger = event?.detail?.trigger || document.getElementById('v1-admin-voicebox-entry') || document.body;
    if (!LABS[type]) return;
    openLab(type, trigger);
  });

  function startObserver() {
    const root = document.getElementById('root') || document.body;
    const observer = new MutationObserver(scheduleTagCards);
    observer.observe(root, { childList: true, subtree: true });
    scheduleTagCards();
    resolveAdminAccess();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startObserver, { once: true });
  } else {
    startObserver();
  }
})();
