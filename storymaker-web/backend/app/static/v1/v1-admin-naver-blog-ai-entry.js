(() => {
  'use strict';

  if (window.__STORYMAKER_V1_ADMIN_NAVER_BLOG_AI_ENTRY__) return;
  window.__STORYMAKER_V1_ADMIN_NAVER_BLOG_AI_ENTRY__ = true;

  const BUTTON_ID = 'v1-admin-naver-blog-ai-entry';
  const PANEL_KEY = 'naver-blog-ai';
  const TARGET_URL = '/static/v1/naver-blog-ai.html';

  const normalize = (value) => String(value || '').replace(/\s+/g, ' ').trim();

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

  async function fetchAdminState() {
    try {
      const response = await fetch('/v1-api/auth/me', {
        credentials: 'include',
        cache: 'no-store',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) return false;
      const payload = await response.json().catch(() => ({}));
      const user = payload?.data?.user || payload?.user || payload?.data || null;
      return isAdminUser(user);
    } catch (_) {
      return false;
    }
  }

  function findNav() {
    return Array.from(document.querySelectorAll('nav')).find((nav) =>
      Array.from(nav.querySelectorAll('button')).some((button) => normalize(button.textContent).includes('보관함'))
    );
  }

  function removeButton() {
    document.getElementById(BUTTON_ID)?.remove();
  }

  function openPanel(button) {
    const host = window.StoryMakerV1InlinePanels;
    if (!host || typeof host.open !== 'function') {
      location.href = TARGET_URL;
      return;
    }

    const body = host.open(PANEL_KEY, '네이버 블로그 AI');
    if (!body) return;
    body.style.minHeight = 'calc(100vh - 140px)';
    body.innerHTML = `
      <iframe
        src="${TARGET_URL}"
        title="네이버 블로그 AI"
        style="display:block;width:100%;height:calc(100vh - 140px);min-height:900px;border:0;background:#020617"
        loading="eager"
        referrerpolicy="same-origin"
      ></iframe>
    `;

    document.querySelectorAll('[data-storymaker-beta-menu="1"]').forEach((item) => {
      item.removeAttribute('aria-current');
      item.removeAttribute('data-active');
    });
    button.setAttribute('aria-current', 'page');
    button.dataset.active = '1';
  }

  function buildButton(template) {
    const button = document.createElement('button');
    button.id = BUTTON_ID;
    button.type = 'button';
    button.dataset.storymakerAdminNaverBlogAi = '1';
    button.className = template?.className || 'rounded-lg px-4 py-3.5 text-left text-lg font-black text-slate-100 hover:bg-slate-900';
    button.innerHTML = `
      <span style="display:flex;width:100%;align-items:center;gap:12px">
        <span aria-hidden="true" style="display:inline-flex;width:20px;height:20px;flex:0 0 20px;align-items:center;justify-content:center;color:#22c55e">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 4h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z"/>
            <path d="m8 15 2.4-2.6a2 2 0 0 1 3 0L16 15"/>
            <path d="M8 9h.01"/>
          </svg>
        </span>
        <span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">네이버 블로그 AI</span>
      </span>
    `;
    button.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      openPanel(button);
    });
    return button;
  }

  function ensureButton() {
    if (document.getElementById(BUTTON_ID)) return;
    const nav = findNav();
    if (!nav) return;

    const archiveButton = Array.from(nav.querySelectorAll('button')).find((button) => normalize(button.textContent).includes('보관함'));
    if (!archiveButton) return;

    const button = buildButton(archiveButton);
    if (archiveButton.nextSibling) nav.insertBefore(button, archiveButton.nextSibling);
    else nav.appendChild(button);
  }

  async function refresh() {
    const admin = await fetchAdminState();
    if (admin) ensureButton();
    else removeButton();
  }

  const observer = new MutationObserver(() => {
    if (!document.getElementById(BUTTON_ID)) refresh();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  window.addEventListener('storymaker-auth-changed', refresh);
  window.addEventListener('pageshow', refresh);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) refresh();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', refresh, { once: true });
  } else {
    refresh();
  }
})();
