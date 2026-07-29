(() => {
  'use strict';

  if (window.__STORYMAKER_V1_GUEST_TRY_LOGIN_CARD__) return;
  window.__STORYMAKER_V1_GUEST_TRY_LOGIN_CARD__ = true;

  const BUTTON_ID = 'storymaker-v1-guest-try-login-card';
  const STYLE_ID = 'storymaker-v1-guest-try-login-card-style';
  const clean = (value = '') => String(value).replace(/\s+/g, ' ').trim();
  let authenticated = null;
  let scheduled = 0;

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #${BUTTON_ID}{
        position:absolute;
        left:50%;
        top:50%;
        transform:translate(-50%,-50%);
        z-index:3;
        min-width:210px;
        min-height:74px;
        display:flex;
        align-items:center;
        justify-content:center;
        padding:12px 16px;
        border:1px solid rgba(103,232,249,.42);
        border-radius:18px;
        background:linear-gradient(145deg,rgba(8,145,178,.24),rgba(15,23,42,.96));
        color:#e6fbff;
        font-size:17px;
        font-weight:950;
        line-height:1.2;
        letter-spacing:-.03em;
        text-align:center;
        white-space:nowrap;
        cursor:pointer;
        box-sizing:border-box;
        box-shadow:0 10px 28px rgba(2,6,23,.22);
        transition:transform .18s ease,border-color .18s ease,background .18s ease,filter .18s ease;
      }
      #${BUTTON_ID}:hover,#${BUTTON_ID}:focus-visible{
        transform:translate(-50%,calc(-50% - 1px));
        border-color:#67e8f9;
        background:linear-gradient(145deg,rgba(8,145,178,.42),rgba(15,23,42,.98));
        filter:brightness(1.06);
        outline:3px solid rgba(34,211,238,.18);
        outline-offset:2px;
      }
      @media(max-width:900px){#${BUTTON_ID}{min-width:188px;min-height:68px;font-size:16px}}
    `;
    document.head.appendChild(style);
  }

  function openLoginModal(event) {
    event?.preventDefault?.();
    event?.stopPropagation?.();
    if (window.StoryMakerV1AuthModal?.show) {
      window.StoryMakerV1AuthModal.show('login');
      return;
    }
    if (typeof window.showAuthModal === 'function') {
      window.showAuthModal('login');
      return;
    }
    if (typeof window.handleLogin === 'function') {
      window.handleLogin(event);
    }
  }

  function findMetricCard(labelText) {
    const label = Array.from(document.querySelectorAll('div,span,p,strong'))
      .find((node) => clean(node.textContent) === labelText);
    if (!label) return null;

    let card = label.parentElement;
    while (card && card !== document.body) {
      const text = clean(card.textContent);
      const rect = card.getBoundingClientRect?.();
      if (rect && rect.width >= 80 && rect.width <= 240 && rect.height >= 55 && rect.height <= 130 && text.startsWith(labelText)) {
        return card;
      }
      card = card.parentElement;
    }
    return null;
  }

  function findDashboardHeader() {
    const currentLabel = Array.from(document.querySelectorAll('div,span,p,strong'))
      .find((node) => clean(node.textContent) === '현재 화면');
    if (!currentLabel) return null;

    let card = currentLabel.parentElement;
    while (card && card !== document.body) {
      const text = clean(card.textContent);
      const rect = card.getBoundingClientRect?.();
      if (rect && rect.width >= 700 && rect.height >= 70 && rect.height <= 150 && text.includes('현재 화면') && text.includes('대시보드') && text.includes('대시보드로 돌아가기')) {
        return card;
      }
      card = card.parentElement;
    }
    return null;
  }

  function removeButton() {
    document.getElementById(BUTTON_ID)?.remove();
  }

  function apply() {
    scheduled = 0;
    if (authenticated !== false) {
      removeButton();
      return;
    }

    const dashboardHeader = findDashboardHeader();
    if (!dashboardHeader) return;
    dashboardHeader.style.position = 'relative';

    ensureStyle();
    let button = document.getElementById(BUTTON_ID);
    if (!button) {
      button = document.createElement('button');
      button.id = BUTTON_ID;
      button.type = 'button';
      button.textContent = '스토리메이커 사용해보기';
      button.setAttribute('aria-label', '로그인하고 스토리메이커 사용해보기');
      button.title = '로그인하고 스토리메이커 사용해보기';
      button.addEventListener('click', openLoginModal);
    }

    if (button.parentElement !== dashboardHeader) {
      dashboardHeader.appendChild(button);
    }
  }

  function scheduleApply() {
    if (scheduled) return;
    scheduled = requestAnimationFrame(apply);
  }

  async function resolveAuth() {
    try {
      const token = String(localStorage.getItem('storymaker_token') || '').trim();
      const headers = { Accept: 'application/json' };
      if (token) headers.Authorization = `Bearer ${token}`;

      const response = await fetch('/v1-api/auth/me', {
        credentials: 'include',
        cache: 'no-store',
        headers,
      });
      const payload = response.ok ? await response.json().catch(() => ({})) : {};
      const user = payload?.data?.user || payload?.user || payload?.data || null;
      authenticated = Boolean(response.ok && user && typeof user === 'object');
    } catch (_) {
      authenticated = false;
    }

    if (authenticated) removeButton();
    scheduleApply();
  }

  function start() {
    const root = document.getElementById('root') || document.body;
    new MutationObserver(scheduleApply).observe(root, { childList: true, subtree: true });
    window.addEventListener('storymaker-auth-changed', resolveAuth);
    window.addEventListener('storage', (event) => {
      if (event.key === 'storymaker_token') resolveAuth();
    });
    resolveAuth();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();
