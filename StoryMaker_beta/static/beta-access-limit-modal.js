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
      title: '무료 제작 한도를 모두 사용했습니다',
      body: '가입일 기준 현재 30일 이용기간의 무료 제작 한도 20건을 모두 사용했습니다. 새로운 AI 원고 생성과 MP4 제작만 중단되며, 기존 콘텐츠와 보관함은 계속 이용할 수 있습니다.',
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
        <p class="balm-body" data-balm-body></p>
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
    modal.querySelector('[data-balm-confirm]').addEventListener('click', () => {
      try {
        window.top.location.href = DASHBOARD_URL;
      } catch (_) {
        window.location.href = DASHBOARD_URL;
      }
    });
    return modal;
  }

  function showAccessLimitModal(message) {
    const target = ensureModal();
    const content = buildDescription(message);
    target.querySelector('#balm-title').textContent = content.title;
    target.querySelector('[data-balm-body]').textContent = content.body;
    target.hidden = false;
    target.querySelector('[data-balm-upgrade]').focus();
  }

  window.alert = function storymakerLimitAwareAlert(message) {
    if (isAccessLimitMessage(message)) {
      showAccessLimitModal(message);
      return;
    }
    return nativeAlert(message);
  };

  window.storymakerShowAccessLimit = showAccessLimitModal;
})();
