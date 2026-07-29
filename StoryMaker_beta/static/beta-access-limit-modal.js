(() => {
  'use strict';

  const DASHBOARD_URL = '/v1/';
  const UPGRADE_URL = 'https://www.latpeed.com/';
  const nativeAlert = window.alert.bind(window);
  let modal = null;

  function isAccessLimitMessage(message) {
    const text = String(message || '');
    return (
      text.includes('무료 30일 20회 제작 한도를 모두 사용했습니다') ||
      text.includes('무료 월 20회 제작 한도를 모두 사용했습니다') ||
      text.includes('유료 이용기간 30일이 종료되었습니다') ||
      (text.includes('20회') && text.includes('제작 한도'))
    );
  }

  function buildDescription(message) {
    const text = String(message || '');
    if (text.includes('유료 이용기간')) {
      return {
        title: '유료 이용기간이 종료되었습니다',
        body: '가입일 또는 최근 갱신일 기준 30일 이용기간이 종료되어 새로운 AI 원고 생성과 MP4 제작이 잠시 중단되었습니다. 기존 콘텐츠와 보관함은 계속 이용할 수 있습니다.',
      };
    }
    return {
      title: '월간 무료 한도를 모두 사용하셨어요.',
      body: '가입일 기준 현재 30일 이용기간의 무료 제작 한도 20건을 모두 사용했습니다. 새로운 AI 원고 생성과 MP4 제작만 중단되며, 기존 콘텐츠와 보관함은 계속 이용할 수 있습니다.',
      showRequestButton: true,
    };
  }

  function ensureModal() {
    if (modal && document.body.contains(modal)) return modal;

    modal = document.createElement('div');
    modal.id = 'beta-access-limit-modal';
    modal.hidden = true;
    modal.innerHTML = `
      <div class="balm-backdrop" data-balm-close></div>
      <section class="balm-dialog" role="dialog" aria-modal="true" aria-labelledby="balm-title">
        <div class="balm-icon" aria-hidden="true">!</div>
        <p class="balm-kicker">제작 이용 안내</p>
        <h2 id="balm-title"></h2>
        <div class="balm-body">
          <span data-balm-body></span>
          <button type="button" class="balm-request" data-balm-request aria-label="요청사항 작성" title="요청사항 작성">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"></path>
              <path d="M8 9h.01M12 9h.01M16 9h.01"></path>
            </svg>
          </button>
        </div>
        <div class="balm-note">
          <strong>계속 이용 가능한 기능</strong>
          <span>기존 콘텐츠 확인 · 복사 · 다운로드 · 보관함 · 업체 정보</span>
        </div>
        <div class="balm-actions">
          <button type="button" class="balm-upgrade" data-balm-upgrade>유료회원 가입</button>
          <button type="button" class="balm-confirm" data-balm-confirm>확인</button>
        </div>
      </section>
    `;

    const style = document.createElement('style');
    style.textContent = `
      #beta-access-limit-modal[hidden]{display:none!important}
      #beta-access-limit-modal{position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;padding:24px;font-family:inherit}
      #beta-access-limit-modal .balm-backdrop{position:absolute;inset:0;background:rgba(2,6,23,.78);backdrop-filter:blur(6px)}
      #beta-access-limit-modal .balm-dialog{position:relative;width:min(520px,100%);border:1px solid rgba(103,232,249,.32);border-radius:24px;background:#0c172b;color:#f8fafc;padding:30px;box-shadow:0 30px 90px rgba(0,0,0,.55)}
      #beta-access-limit-modal .balm-icon{display:flex;width:52px;height:52px;align-items:center;justify-content:center;border-radius:16px;background:rgba(251,191,36,.14);border:1px solid rgba(251,191,36,.38);color:#fbbf24;font-size:30px;font-weight:900}
      #beta-access-limit-modal .balm-kicker{margin:20px 0 8px;color:#67e8f9;font-size:14px;font-weight:800;letter-spacing:.08em}
      #beta-access-limit-modal h2{margin:0;font-size:27px;line-height:1.35}
      #beta-access-limit-modal .balm-body{margin:16px 0 0;color:#cbd5e1;font-size:16px;line-height:1.75;word-break:keep-all}
      #beta-access-limit-modal .balm-request{display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;min-height:38px;margin-left:10px;padding:0;border:1px solid #385273;border-radius:12px;background:#14233b;color:#67e8f9;vertical-align:middle;cursor:pointer;transition:.18s ease}
      #beta-access-limit-modal .balm-request:hover{border-color:#67e8f9;background:#17314d;transform:translateY(-1px)}
      #beta-access-limit-modal .balm-request[hidden]{display:none!important}
      #beta-access-limit-modal .balm-note{margin-top:20px;padding:16px 18px;border-radius:16px;background:#111f36;border:1px solid #263b5c;display:grid;gap:7px}
      #beta-access-limit-modal .balm-note strong{color:#f8fafc;font-size:14px}
      #beta-access-limit-modal .balm-note span{color:#93a8c6;font-size:14px;line-height:1.6}
      #beta-access-limit-modal .balm-actions{display:flex;gap:10px;margin-top:24px}
      #beta-access-limit-modal button{min-height:48px;border-radius:14px;padding:0 20px;font-size:15px;font-weight:800;cursor:pointer}
      #beta-access-limit-modal .balm-upgrade{flex:1;border:0;background:#22d3ee;color:#06202a}
      #beta-access-limit-modal .balm-confirm{border:1px solid #385273;background:#14233b;color:#f8fafc}
      @media(max-width:560px){#beta-access-limit-modal .balm-dialog{padding:24px 20px}#beta-access-limit-modal .balm-actions{flex-direction:column}#beta-access-limit-modal .balm-confirm{width:100%}}
    `;
    document.head.appendChild(style);
    document.body.appendChild(modal);

    modal.querySelector('[data-balm-upgrade]').addEventListener('click', () => {
      window.open(UPGRADE_URL, '_blank', 'noopener,noreferrer');
    });
    modal.querySelector('[data-balm-request]').addEventListener('click', () => {
      const message = {
        type: 'storymaker:open-feature-request',
        prefill: {
          title: '무료 제작 한도 관련 요청',
          content: '월간 무료 제작 한도를 모두 사용한 뒤 추가 이용 또는 이용 정책에 관해 문의드립니다.',
        },
      };
      if (window.parent && window.parent !== window) {
        try {
          window.parent.postMessage(message, window.location.origin);
          return;
        } catch (_) {}
      }
      window.postMessage(message, window.location.origin);
    });
    modal.querySelector('[data-balm-confirm]').addEventListener('click', () => {
      modal.hidden = true;
      if (window.parent && window.parent !== window) {
        try {
          window.parent.postMessage({ type: 'storymaker:navigate-dashboard', focus: 'usage-panel' }, window.location.origin);
          return;
        } catch (_) {}
      }
      window.location.assign(`${DASHBOARD_URL}#v1-dashboard-usage-panel`);
    });
    return modal;
  }

  function showAccessLimitModal(message) {
    const target = ensureModal();
    const content = buildDescription(message);
    target.querySelector('#balm-title').textContent = content.title;
    target.querySelector('[data-balm-body]').textContent = content.body;
    const requestButton = target.querySelector('[data-balm-request]');
    if (requestButton) requestButton.hidden = content.showRequestButton !== true;
    target.hidden = false;
    target.querySelector('[data-balm-upgrade]').focus();
  }

  function renderInlineLimitNotice(target, message) {
    if (!target || !isAccessLimitMessage(message)) return;
    const content = buildDescription(message);
    target.innerHTML = '';
    const title = document.createElement('strong');
    title.textContent = content.title;
    const detail = document.createElement('span');
    detail.textContent = ` · ${content.body}`;
    const link = document.createElement('a');
    link.href = UPGRADE_URL;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = ' 유료회원 가입';
    link.style.cssText = 'margin-left:10px;color:#67e8f9;text-decoration:underline;text-underline-offset:3px;font-weight:900';
    target.append(title, detail, link);
  }

  function inspectInlineLimitNotices() {
    const selectors = ['#beta-status', '#sf-status'];
    for (const selector of selectors) {
      const target = document.querySelector(selector);
      if (!target) continue;
      const message = target.textContent || '';
      if (isAccessLimitMessage(message) && !target.querySelector('a[href="https://www.latpeed.com/"]')) {
        renderInlineLimitNotice(target, message);
        showAccessLimitModal(message);
      }
    }
  }

  let allowVideoClickOnce = false;
  document.addEventListener('click', async (event) => {
    const button = event.target?.closest?.('#sf-make');
    if (!button || allowVideoClickOnce) {
      allowVideoClickOnce = false;
      return;
    }
    event.preventDefault();
    event.stopImmediatePropagation();
    button.disabled = true;
    try {
      const response = await fetch('/beta-api/usage-summary', { cache: 'no-store', credentials: 'include' });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      const usage = payload.usage || {};
      if (usage.access_allowed === false) {
        const message = usage.expired
          ? '유료 이용기간 30일이 종료되었습니다. 이용기간을 갱신해 주세요.'
          : '무료 30일 20회 제작 한도를 모두 사용했습니다.';
        renderInlineLimitNotice(document.querySelector('#sf-status'), message);
        showAccessLimitModal(message);
        return;
      }
      allowVideoClickOnce = true;
      button.disabled = false;
      button.click();
    } catch (error) {
      nativeAlert(`영상 제작 가능 여부를 확인하지 못했습니다. ${error.message || error}`);
    } finally {
      if (!allowVideoClickOnce) button.disabled = false;
    }
  }, true);

  const inlineObserver = new MutationObserver(inspectInlineLimitNotices);
  inlineObserver.observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  window.setTimeout(inspectInlineLimitNotices, 0);

  window.alert = function storymakerLimitAwareAlert(message) {
    if (isAccessLimitMessage(message)) {
      showAccessLimitModal(message);
      return;
    }
    return nativeAlert(message);
  };

  window.storymakerShowAccessLimit = showAccessLimitModal;
})();
