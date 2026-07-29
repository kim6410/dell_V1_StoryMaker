(() => {
  'use strict';

  if (window.__STORYMAKER_V1_ADMIN_REQUEST_ALERT__) return;
  window.__STORYMAKER_V1_ADMIN_REQUEST_ALERT__ = true;

  const ALERT_ID = 'storymaker-v1-admin-request-alert';
  const STYLE_ID = 'storymaker-v1-admin-request-alert-style';
  const API_ME = '/v1-api/auth/me';
  const ENSURE_INTERVAL_MS = 2000;

  let adminAuthorized = false;
  let ensureTimer = null;

  const clean = (value = '') => String(value ?? '').replace(/\s+/g, ' ').trim();

  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #${ALERT_ID}{display:inline-flex;align-items:center;justify-content:center;width:50px;height:50px;flex:0 0 50px;border:1px solid rgba(148,163,184,.34);border-radius:16px;background:#0f172a;color:#cbd5e1;cursor:pointer;box-shadow:0 10px 28px rgba(2,6,23,.24);transition:transform .18s ease,border-color .18s ease,background .18s ease,color .18s ease}
      #${ALERT_ID}:hover,#${ALERT_ID}:focus-visible{transform:translateY(-1px);border-color:#67e8f9;background:#164e63;color:#fff;outline:3px solid rgba(34,211,238,.22);outline-offset:2px}
      #${ALERT_ID} .sm-request-alert-icon{width:25px;height:25px;display:block;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
    `;
    document.head.appendChild(style);
  }

  function findDashboardHeader() {
    const clickables = Array.from(document.querySelectorAll('button,a,[role="button"]'));
    const returnButton = clickables.find((node) => clean(node.textContent) === '대시보드로 돌아가기');
    if (returnButton?.parentElement) {
      return { container: returnButton.parentElement, before: returnButton };
    }

    const currentLabel = Array.from(document.querySelectorAll('div,section,header,p,span')).find(
      (node) => clean(node.textContent) === '현재 화면' && node.getBoundingClientRect().width > 40,
    );
    if (!currentLabel) return null;

    let card = currentLabel.parentElement;
    while (card && card !== document.body) {
      const rect = card.getBoundingClientRect();
      if (rect.width > 500 && rect.height >= 70 && rect.height <= 180) break;
      card = card.parentElement;
    }
    if (!card || card === document.body) return null;

    const actions = Array.from(card.children).find((node) => {
      const rect = node.getBoundingClientRect();
      return rect.width >= 40 && rect.right > window.innerWidth * 0.65;
    });
    return { container: actions || card, before: actions?.firstElementChild || null };
  }

  function createAlertButton() {
    const button = document.createElement('button');
    button.id = ALERT_ID;
    button.type = 'button';
    button.setAttribute('aria-label', '요청사항 관리 열기');
    button.title = '요청사항 관리 열기';
    button.innerHTML = `
      <svg class="sm-request-alert-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"></path>
        <path d="M8 9h8M8 13h5"></path>
      </svg>
    `;
    button.addEventListener('click', () => {
      window.StoryMakerV1FeatureRequests?.open?.();
    });
    return button;
  }

  function ensureAlertButton() {
    if (!adminAuthorized) return;
    if (document.getElementById(ALERT_ID)) return;

    const target = findDashboardHeader();
    if (!target?.container) return;

    const button = createAlertButton();
    if (target.before) target.container.insertBefore(button, target.before);
    else target.container.appendChild(button);
  }

  function isAdminUser(user) {
    if (!user || typeof user !== 'object') return false;
    const role = clean(user.role || user.user_role || user.type).toLowerCase();
    return user.is_admin === true
      || user.is_admin === 1
      || user.admin === true
      || user.admin === 1
      || role === 'admin'
      || role === 'administrator';
  }

  async function resolveAdmin() {
    try {
      const response = await fetch(API_ME, { credentials: 'include', cache: 'no-store' });
      if (!response.ok) return false;
      const payload = await response.json().catch(() => ({}));
      const user = payload?.data?.user || payload?.user || payload?.data || null;
      return isAdminUser(user);
    } catch (_) {
      return false;
    }
  }

  async function boot() {
    ensureStyles();
    adminAuthorized = await resolveAdmin();
    if (!adminAuthorized) {
      document.getElementById(ALERT_ID)?.remove();
      return;
    }

    ensureAlertButton();
    if (ensureTimer) window.clearInterval(ensureTimer);
    ensureTimer = window.setInterval(ensureAlertButton, ENSURE_INTERVAL_MS);
  }

  window.StoryMakerV1AdminRequestAlert = { ensure: ensureAlertButton };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
