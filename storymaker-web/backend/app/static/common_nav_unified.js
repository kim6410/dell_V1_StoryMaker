(function(){
  const params = new URLSearchParams(location.search);
  const NAV_ID = 'sns-ai-global-nav';
  const CSS_ID = 'storymaker-nav-unified-css';
  const HEADER_URL = '/static/header-nav.html?v=20260705-mobile-session-menu-3';
  const CSS_URL = '/static/storymaker_nav_unified.css?v=20260705-mobile-session-menu-3';
  const FOOTER_CSS_URL = '/static/footer_unified.css?v=20260703-footer-unify-1';
  const FOOTER_HTML_URL = '/static/footer-unified.html?v=20260703-footer-unify-1';
  const WP_REGISTER_URL = '/storymaker?action=register';

  if (params.get('embed') === '1') {
    setupEmbedMode();
    return;
  }

  function setupEmbedMode(){
    document.documentElement.classList.add('storymaker-embed-mode');
    ensureStylesheet('storymaker-embed-mode-css', '/static/embed_mode.css?v=20260703-embed-2');

    function sendEmbedHeight(){
      try {
        let maxBottom = 0;
        document.querySelectorAll('body > *').forEach(function(el){
          if (!el || el.id === NAV_ID) return;
          const cs = window.getComputedStyle(el);
          if (cs.display === 'none' || cs.visibility === 'hidden' || cs.position === 'fixed') return;
          if (el.matches && el.matches('.modal-backdrop,.help-modal,.license-backdrop,[aria-hidden="true"]')) return;
          const r = el.getBoundingClientRect();
          if (!r || r.height < 1) return;
          maxBottom = Math.max(maxBottom, r.bottom + window.scrollY);
        });
        const h = Math.max(760, Math.ceil(maxBottom + 24));
        if (h <= 12000) window.parent.postMessage({ storymakerEmbedHeight: h }, 'https://mystorymaker.net');
      } catch(e) {}
    }

    function apply(){
      if (!document.body) return;
      document.body.classList.add('storymaker-embed-mode');
      const nav = document.getElementById(NAV_ID);
      if (nav) nav.remove();
      sendEmbedHeight();
    }

    if (document.body) apply();
    document.addEventListener('DOMContentLoaded', function(){
      apply();
      setTimeout(sendEmbedHeight, 350);
      setTimeout(sendEmbedHeight, 1200);
    });
    window.addEventListener('load', sendEmbedHeight);
    window.addEventListener('resize', sendEmbedHeight);
    setInterval(sendEmbedHeight, 1600);
  }

  function ensureStylesheet(id, href){
    if (document.getElementById(id)) return;
    const link = document.createElement('link');
    link.id = id;
    link.rel = 'stylesheet';
    link.href = href;
    document.head.appendChild(link);
  }

  function ensureCss(){
    ensureStylesheet(CSS_ID, CSS_URL);
  }

  function ensureFooter(){
    ensureStylesheet('storymaker-footer-unified-css', FOOTER_CSS_URL);

    let footer = document.getElementById('sns-ai-global-footer');
    if (!footer) {
      footer = document.createElement('div');
      footer.id = 'sns-ai-global-footer';
      document.body.appendChild(footer);
    }
    if (footer.dataset.loaded === '1') return;

    fetch(FOOTER_HTML_URL, { cache: 'no-store' })
      .then(function(res){ return res.ok ? res.text() : ''; })
      .then(function(html){
        if (!html) return;
        footer.innerHTML = html;
        footer.dataset.loaded = '1';
      })
      .catch(function(){});
  }

  function getUser(){
    try { return JSON.parse(localStorage.getItem('storymaker_user') || '{}') || {}; }
    catch(e) { return {}; }
  }

  function hasToken(){
    return !!String(localStorage.getItem('storymaker_token') || '').trim();
  }

  function isLoggedIn(){
    const user = getUser();
    const authOk = String(localStorage.getItem('storymaker_auth_ok') || '') === '1';
    return hasToken() || authOk || !!(user && (user.username || user.email || user.id));
  }

  function isAdminUser(){
    const user = getUser();
    const role = String(user.role || '').toLowerCase();
    const roles = Array.isArray(user.roles) ? user.roles.map(function(r){ return String(r).toLowerCase(); }) : [];
    return isLoggedIn() && (
      user.is_admin === true ||
      user.is_admin === 1 ||
      String(user.is_admin).toLowerCase() === 'true' ||
      role === 'admin' ||
      role === 'administrator' ||
      role === '관리자' ||
      roles.includes('admin') ||
      roles.includes('administrator') ||
      user.username === 'admin'
    );
  }

  function login(){
    try { sessionStorage.setItem('storymaker_auth_return_url', location.href); } catch(e) {}
    if (typeof window.showAuthModal === 'function') window.showAuthModal('login');
    else location.href = '/storymaker';
  }

  function join(){
    try { sessionStorage.setItem('storymaker_auth_return_url', location.href); } catch(e) {}
    if (typeof window.showAuthModal === 'function') window.showAuthModal('register');
    else location.href = WP_REGISTER_URL;
  }

  function openMyPage(e){
    if (e && typeof e.preventDefault === 'function') e.preventDefault();
    if (e && typeof e.stopPropagation === 'function') e.stopPropagation();

    try { closeMobileMenu(document.getElementById(NAV_ID)); } catch(err) {}

    if (typeof window.showMyPageModal === 'function') {
      return window.showMyPageModal();
    }

    // 모바일에서 공통 헤더가 app_auth.js보다 먼저 바인딩되는 경우를 방어한다.
    // 마이페이지 모달 함수가 늦게 준비되면 0.12초 뒤 다시 열고,
    // 그래도 없을 때만 action=mypage URL로 이동한다.
    setTimeout(function(){
      if (typeof window.showMyPageModal === 'function') {
        window.showMyPageModal();
        return;
      }
      return;
    }, 120);
    return false;
  }

  function logout(){
    if (typeof window.handleLogout === 'function') return window.handleLogout();
    localStorage.removeItem('storymaker_token');
    localStorage.removeItem('storymaker_user');
    localStorage.removeItem('storymaker_auth_ok');
    localStorage.removeItem('current_project_id');
    location.href = '/storymaker';
  }

  function openAdmin(){
    if (!isAdminUser()) {
      alert('관리자 계정으로 로그인해야 이용할 수 있습니다.');
      return;
    }
    if (typeof window.showAdminDashboard === 'function') window.showAdminDashboard();
    else location.href = '/storymaker?action=admin';
  }

  function normalizedPath(){
    let p = String(location.pathname || '').toLowerCase();
    while (p.length > 1 && p.endsWith('/')) p = p.slice(0, -1);
    return p || '/';
  }

  function activeKey(){
    const p = normalizedPath();
    if (p === '/' || p === '/app' || p.includes('dashboard')) return 'dashboard';
    if (p === '/app/storymaker' || p === '/storymaker' || p.includes('/storymaker')) return 'storymaker';
    if (p === '/app/podcast' || p === '/podcast' || p.includes('/podcast')) return 'podcast';
    if (p === '/app/slideshow' || p === '/slideshow' || p.includes('/slideshow')) return 'slideshow';
    return '';
  }

  function isWpAppPath(){
    const p = normalizedPath();
    const host = String(location.hostname || '').toLowerCase();
    return host === 'mystorymaker.net' && (p === '/app' || p.startsWith('/app/'));
  }

  function appHref(key){
    const APP_ORIGIN = window.location.origin;
    if (isWpAppPath()) {
      if (key === 'dashboard') return '/app/';
      if (key === 'storymaker') return '/app/storymaker';
      if (key === 'podcast') return '/app/podcast';
      if (key === 'slideshow') return '/app/slideshow';
      return '/app/';
    }
    if (key === 'dashboard') return APP_ORIGIN + '/';
    if (key === 'storymaker') return APP_ORIGIN + '/storymaker';
    if (key === 'podcast') return APP_ORIGIN + '/podcast';
    if (key === 'slideshow') return APP_ORIGIN + '/slideshow';
    return APP_ORIGIN + '/';
  }

  function normalizeAppLinks(nav){
    nav.querySelectorAll('[data-app-link]').forEach(function(a){
      const href = appHref(a.dataset.appLink);
      if (href && a.getAttribute('href') !== href) a.setAttribute('href', href);
    });
  }

  function unifyInquiryMenu(nav){
    const shell = nav.querySelector('#site-header, .ob-site-header');
    if (!shell) return;

    const mainMenu = shell.querySelector('.ob-nav-wp-main');
    const serviceMenu = shell.querySelector('.sns-ai-service-line');
    if (!mainMenu) return;

    let inquiry = shell.querySelector('[data-public-link="inquiry"]');
    if (!inquiry) {
      inquiry = Array.from(shell.querySelectorAll('a')).find(function(a){
        return String(a.textContent || '').trim() === '문의/제휴';
      });
    }
    if (!inquiry) return;

    inquiry.setAttribute('href', 'https://mystorymaker.net/inquiry/');
    inquiry.setAttribute('data-public-link', 'inquiry');

    const faq = mainMenu.querySelector('[data-public-link="faq"]');
    if (faq) faq.insertAdjacentElement('afterend', inquiry);
    else mainMenu.appendChild(inquiry);

    if (serviceMenu) {
      serviceMenu.querySelectorAll('a').forEach(function(a){
        if (a !== inquiry && String(a.textContent || '').trim() === '문의/제휴') a.remove();
      });
    }
  }

  function closeMobileMenu(nav){
    nav.classList.remove('is-mobile-menu-open');
    const toggle = nav.querySelector('.sns-ai-mobile-menu-toggle');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
  }

  function ensureMobileToggle(nav){
    const shell = nav.querySelector('.sns-ai-nav.ob-site-header, #site-header.ob-site-header, .ob-site-header');
    if (!shell || shell.querySelector('.sns-ai-mobile-menu-toggle')) return;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'sns-ai-mobile-menu-toggle';
    btn.setAttribute('aria-label', '모바일 메뉴 열기');
    btn.setAttribute('aria-expanded', 'false');
    btn.textContent = '☰';
    btn.addEventListener('click', function(e){
      e.stopPropagation();
      const open = !nav.classList.contains('is-mobile-menu-open');
      nav.classList.toggle('is-mobile-menu-open', open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    shell.appendChild(btn);
  }

  function removeLegacyLogoutButtons(nav){
    return;
  }

  function renderAuthSlot(nav){
    removeLegacyLogoutButtons(nav);
    const slot = nav.querySelector('[data-auth-slot]');
    if (!slot) return;

    const nextHtml = isLoggedIn()
      ? '<button type="button" class="sns-ai-mypage-text-btn" data-mypage title="마이페이지" aria-label="마이페이지">마이페이지</button><button type="button" class="sns-ai-mobile-logout-btn" data-logout>로그아웃</button>'
      : '<button type="button" class="sns-ai-login-btn" data-login>로그인</button><button type="button" class="sns-ai-join-btn" data-join>회원가입</button>';

    if (slot.dataset.renderedHtml !== nextHtml) {
      slot.innerHTML = nextHtml;
      slot.dataset.renderedHtml = nextHtml;
    }

    const actions = [
      ['[data-login]', login],
      ['[data-join]', join],
      ['[data-logout]', logout],
      ['[data-mypage]', openMyPage],
      ['[data-admin]', openAdmin]
    ];

    actions.forEach(function(pair){
      const el = slot.querySelector(pair[0]);
      if (el && !el.dataset.bound) {
        el.dataset.bound = '1';
        el.addEventListener('click', pair[1]);
      }
    });
  }

  function bindOutsideClose(nav){
    if (!nav || nav.dataset.outsideCloseBound === '1') return;
    nav.dataset.outsideCloseBound = '1';
    document.addEventListener('click', function(e){
      if (!nav.classList.contains('is-mobile-menu-open')) return;
      if (nav.contains(e.target)) return;
      closeMobileMenu(nav);
    }, true);
    document.addEventListener('touchstart', function(e){
      if (!nav.classList.contains('is-mobile-menu-open')) return;
      if (nav.contains(e.target)) return;
      closeMobileMenu(nav);
    }, { capture: true, passive: true });
  }

  function applyState(nav){
    normalizeAppLinks(nav);
    unifyInquiryMenu(nav);
    bindOutsideClose(nav);
    const key = activeKey();

    nav.classList.add('is-unified-header');
    nav.querySelectorAll('[data-app-link]').forEach(function(a){
      a.classList.toggle('is-active', a.dataset.appLink === key);
      if (!a.dataset.bound) {
        a.dataset.bound = '1';
        a.addEventListener('click', function(){ closeMobileMenu(nav); });
      }
    });

    nav.querySelectorAll('[data-public-link]').forEach(function(a){
      if (!a.dataset.bound) {
        a.dataset.bound = '1';
        a.addEventListener('click', function(){ closeMobileMenu(nav); });
      }
    });

    renderAuthSlot(nav);
    ensureMobileToggle(nav);
  }

  async function render(){
    if (!document.body) return document.addEventListener('DOMContentLoaded', render, { once: true });
    ensureCss();

    try {
      document.querySelectorAll('.tool-topbar,.topbar,.local-topbar,.app-topbar,.page-topbar,.podcast-topbar,.slideshow-topbar,.studio-topbar').forEach(function(el){ el.remove(); });
    } catch(e) {}

    let nav = document.getElementById(NAV_ID);
    if (!nav) {
      nav = document.createElement('div');
      nav.id = NAV_ID;
      document.body.prepend(nav);
    }

    if (!nav.dataset.loaded) {
      try {
        const res = await fetch(HEADER_URL, { cache: 'no-store' });
        if (!res.ok) throw new Error('header fetch failed');
        nav.innerHTML = await res.text();
      } catch(e) {
        nav.innerHTML = '<header id="site-header" class="sns-ai-nav ob-site-header"><div class="ob-brand-line"><a class="ob-logo storymaker-brand" href="https://mystorymaker.net/"><span class="storymaker-logo-mark">S</span><span class="storymaker-logo-text">StoryMaker</span></a></div><nav class="ob-nav ob-nav-wp-main"><a href="https://mystorymaker.net/" data-public-link="home">홈</a><a href="https://mystorymaker.net/about/" data-public-link="about">소개</a><a href="https://mystorymaker.net/guide/" data-public-link="guide">활용법</a><a href="https://mystorymaker.net/blog/" data-public-link="blog">블로그</a><a href="https://mystorymaker.net/faq/" data-public-link="faq">FAQ</a></nav><div class="sns-ai-actions" data-auth-slot></div><nav class="sns-ai-service-line" aria-label="서비스 메뉴"><a href="https://app.mystorymaker.net/" data-app-link="dashboard">앱바로가기</a><a href="https://app.mystorymaker.net/storymaker" data-app-link="storymaker">SNS 글쓰기</a><a href="https://app.mystorymaker.net/podcast" data-app-link="podcast">팟캐스트</a><a href="https://app.mystorymaker.net/slideshow" data-app-link="slideshow">릴스/쇼츠</a><a href="https://mystorymaker.net/inquiry/" data-public-link="inquiry">문의/제휴</a></nav></header>';
      }
      nav.dataset.loaded = 'true';
    }

    applyState(nav);
    ensureFooter();
  }

  window.snsAiUnifiedRender = render;
  window.snsAiOpenMyPage = openMyPage;
  window.addEventListener('storage', render);
  window.addEventListener('storymaker-auth-changed', render);
  window.addEventListener('focus', render);
  document.addEventListener('visibilitychange', function(){ if (!document.hidden) render(); });
  document.addEventListener('touchend', function(e){
    const target = e.target && e.target.closest ? e.target.closest('[data-mypage]') : null;
    if (!target) return;
    openMyPage(e);
  }, true);
  setInterval(function(){
    const nav = document.getElementById(NAV_ID);
    if (nav) {
      removeLegacyLogoutButtons(nav);
      removeLegacyLogoutButtons(document);
      renderAuthSlot(nav);
    }
  }, 1500);

  render();
  document.addEventListener('DOMContentLoaded', render);
  window.addEventListener('load', render);

  try {
    const originalSetItem = localStorage.setItem;
    localStorage.setItem = function(key, value){
      const result = originalSetItem.apply(this, arguments);
      if (key === 'storymaker_token' || key === 'storymaker_user' || key === 'storymaker_auth_ok') setTimeout(render, 0);
      return result;
    };
  } catch(e) {
    window.addEventListener('storymaker-auth-changed', render);
  }
})();
