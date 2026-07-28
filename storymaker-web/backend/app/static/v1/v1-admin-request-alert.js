(() => {
  'use strict';

  if (window.__STORYMAKER_V1_ADMIN_REQUEST_ALERT__) return;
  window.__STORYMAKER_V1_ADMIN_REQUEST_ALERT__ = true;

  const ALERT_ID = 'storymaker-v1-admin-request-alert';
  const STYLE_ID = 'storymaker-v1-admin-request-alert-style';
  const API_ADMIN_LIST = '/v1-api/admin/feature-requests';
  const REFRESH_MS = 30000;

  let unansweredCount = 0;
  let refreshTimer = null;
  let refreshBusy = false;
  let adminAuthorized = null;

  const clean = (value = '') => String(value ?? '').replace(/\s+/g, ' ').trim();

  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #${ALERT_ID}{position:relative;display:inline-flex;align-items:center;justify-content:center;width:50px;height:50px;flex:0 0 50px;border:1px solid rgba(148,163,184,.34);border-radius:16px;background:#0f172a;color:#cbd5e1;cursor:pointer;box-shadow:0 10px 28px rgba(2,6,23,.24);transition:transform .18s ease,border-color .18s ease,background .18s ease,color .18s ease}
      #${ALERT_ID}:hover,#${ALERT_ID}:focus-visible{transform:translateY(-1px);border-color:#67e8f9;background:#164e63;color:#fff;outline:3px solid rgba(34,211,238,.22);outline-offset:2px}
      #${ALERT_ID} .sm-request-alert-icon{width:25px;height:25px;display:block;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
      #${ALERT_ID} .sm-request-alert-count{position:absolute;top:-7px;right:-7px;display:none;min-width:23px;height:23px;padding:0 6px;align-items:center;justify-content:center;border:2px solid #07111f;border-radius:999px;background:#f97316;color:#fff;font-size:11px;font-weight:950;line-height:1;box-shadow:0 5px 14px rgba(249,115,22,.38)}
      #${ALERT_ID}.has-unanswered{border-color:#fb923c;background:linear-gradient(135deg,#9a3412,#c2410c);color:#fff;animation:sm-request-alert-pulse 1.35s ease-in-out infinite}
      #${ALERT_ID}.has-unanswered .sm-request-alert-count{display:inline-flex}
      @keyframes sm-request-alert-pulse{0%,100%{transform:scale(1);box-shadow:0 10px 28px rgba(2,6,23,.24),0 0 0 0 rgba(251,146,60,.42)}50%{transform:scale(1.07);box-shadow:0 12px 34px rgba(2,6,23,.3),0 0 0 10px rgba(251,146,60,0)}}
      @media (prefers-reduced-motion:reduce){#${ALERT_ID}.has-unanswered{animation:none}}
    `;
    document.head.appendChild(style);
  }

  function alertMarkup() {
    return `
      <svg class="sm-request-alert-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"></path>
        <path d="M8 9h8M8 13h5"></path>
      </svg>
      <span class="sm-request-alert-count" aria-hidden="true">0</span>
    `;
  }

  function findDashboardHeader() {
    const candidates = Array.from(document.querySelectorAll('button,a,[role="button"]'));
    const returnButton = candidates.find((node) => clean(node.textContent) === '대시보드로 돌아가기');
    if (returnButton?.parentElement) return { container: returnButton.parentElement, before: returnButton };

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
    if (!card) return null;
    const actions = Array.from(card.children).find((node) => {
      const rect = node.getBoundingClientRect();
      return rect.width >= 40 && rect.right > window.innerWidth * 0.65;
    });
    return { container: actions || card, before: actions?.firstElementChild || null };
  }

  function ensureAlertButton() {
    if (adminAuthorized !== true) return null;
    ensureStyles();
    let button = document.getElementById(ALERT_ID);
    const target = findDashboardHeader();
    if (!target) return null;

    if (!button) {
      button = document.createElement('button');
      button.id = ALERT_ID;
      button.type = 'button';
      button.innerHTML = alertMarkup();
      button.addEventListener('click', () => {
        if (window.StoryMakerV1FeatureRequests?.open) {
          window.StoryMakerV1FeatureRequests.open();
        }
      });
    }

    if (button.parentElement !== target.container) {
      if (target.before) target.container.insertBefore(button, target.before);
      else target.container.appendChild(button);
    }
    renderState(button);
    return button;
  }

  function renderState(button = document.getElementById(ALERT_ID)) {
    if (!button) return;
    const hasUnanswered = unansweredCount > 0;
    button.classList.toggle('has-unanswered', hasUnanswered);
    const count = button.querySelector('.sm-request-alert-count');
    if (count) count.textContent = unansweredCount > 99 ? '99+' : String(unansweredCount);
    const label = hasUnanswered
      ? `미답변 요청사항 ${unansweredCount}건. 클릭하여 요청사항 관리 열기`
      : '미답변 요청사항 없음. 클릭하여 요청사항 관리 열기';
    button.setAttribute('aria-label', label);
    button.title = label;
  }

  async function refreshCount() {
    if (refreshBusy) return;
    refreshBusy = true;
    try {
      const response = await fetch(API_ADMIN_LIST, { credentials: 'include', cache: 'no-store' });
      if (response.status === 401 || response.status === 403) {
        adminAuthorized = false;
        document.getElementById(ALERT_ID)?.remove();
        return;
      }
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload?.ok === false) return;
      adminAuthorized = true;
      const items = Array.isArray(payload?.data) ? payload.data : [];
      unansweredCount = items.filter((item) => !clean(item?.admin_note)).length;
      ensureAlertButton();
      renderState();
    } catch (_) {
      // 일시적인 네트워크 오류에는 기존 표시 상태를 유지합니다.
    } finally {
      refreshBusy = false;
    }
  }

  function boot() {
    ensureStyles();
    refreshCount();
    if (refreshTimer) window.clearInterval(refreshTimer);
    refreshTimer = window.setInterval(refreshCount, REFRESH_MS);

    const observer = new MutationObserver(() => ensureAlertButton());
    observer.observe(document.documentElement, { childList: true, subtree: true });

    window.addEventListener('storymaker:feature-request-updated', refreshCount);
    window.addEventListener('focus', refreshCount);
  }

  window.StoryMakerV1AdminRequestAlert = { refresh: refreshCount };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
