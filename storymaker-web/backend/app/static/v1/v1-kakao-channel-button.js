(() => {
  'use strict';

  if (window.__storymakerKakaoChannelButton) return;
  window.__storymakerKakaoChannelButton = true;

  const CHANNEL_URL = 'https://pf.kakao.com/_FxjaxnX';
  const MAIL_URL = 'mailto:rinsoo641022@gmail.com';
  const BUTTON_ID = 'storymaker-kakao-channel-button';
  const MAIL_BUTTON_ID = 'storymaker-mail-button';
  const WRAP_ID = 'storymaker-contact-buttons';
  const STYLE_ID = 'storymaker-kakao-channel-style';

  function installStyle() {
    if (document.getElementById(STYLE_ID)) return;

    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #${WRAP_ID} {
        position: fixed;
        top: 196px;
        right: 0;
        z-index: 2147483000;
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 10px;
        pointer-events: none;
      }

      #${WRAP_ID} a {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        width: 196px;
        min-height: 50px;
        padding: 0 10px 0 13px;
        box-sizing: border-box;
        border-radius: 999px;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        font-size: 14px;
        font-weight: 900;
        line-height: 1;
        text-decoration: none;
        box-shadow: 0 10px 26px rgba(0, 0, 0, .24), inset 0 1px 0 rgba(255,255,255,.55);
        transition: transform .16s ease, box-shadow .16s ease, filter .16s ease;
        -webkit-tap-highlight-color: transparent;
        pointer-events: auto;
      }

      #${BUTTON_ID} {
        border: 1px solid rgba(60, 45, 0, .18);
        background: #fee500;
        color: #191919;
      }

      #${MAIL_BUTTON_ID} {
        border: 1px solid rgba(0, 72, 130, .20);
        background: linear-gradient(145deg, #ffffff, #dff4ff);
        color: #0f2f73;
      }

      #${WRAP_ID} a:hover {
        transform: translateY(-2px);
        box-shadow: 0 15px 34px rgba(0, 0, 0, .30), inset 0 1px 0 rgba(255,255,255,.58);
        filter: brightness(1.02);
      }

      #${WRAP_ID} a:active {
        transform: translateY(0) scale(.98);
      }

      #${WRAP_ID} .storymaker-contact-icon {
        display: grid;
        place-items: center;
        width: 32px;
        height: 32px;
        flex: 0 0 32px;
        border-radius: 50%;
      }

      #${WRAP_ID} .storymaker-contact-icon svg {
        display: block;
        width: 20px;
        height: 20px;
      }

      #${BUTTON_ID} .storymaker-contact-icon {
        background: #fee500;
        color: #191919;
        border: 1px solid rgba(25, 25, 25, .14);
      }

      #${BUTTON_ID} .storymaker-contact-icon svg {
        width: 24px;
        height: 24px;
        fill: #191919;
      }

      #${MAIL_BUTTON_ID} .storymaker-contact-icon {
        background: #0f2f73;
        color: #ffffff;
      }

      #${MAIL_BUTTON_ID} .storymaker-contact-icon svg {
        fill: none;
        stroke: #ffffff;
        stroke-width: 2;
        stroke-linecap: round;
        stroke-linejoin: round;
      }

      #${WRAP_ID} .storymaker-contact-label {
        white-space: nowrap;
      }

      @media (max-width: 900px) {
        #${WRAP_ID} {
          display: flex !important;
          visibility: visible !important;
          opacity: 1 !important;
          top: auto !important;
          right: 12px !important;
          bottom: calc(55px + env(safe-area-inset-bottom, 0px)) !important;
          z-index: 2147483646 !important;
          gap: 9px;
          transform: translateZ(0);
          -webkit-transform: translateZ(0);
        }

        #${WRAP_ID} a {
          display: inline-flex !important;
          visibility: visible !important;
          opacity: 1 !important;
          width: 52px;
          height: 52px;
          min-height: 52px;
          padding: 0;
          justify-content: center;
          border-radius: 50%;
        }

        #${WRAP_ID} .storymaker-contact-icon {
          width: 34px;
          height: 34px;
          flex-basis: 34px;
          font-size: 13px;
        }

        #${MAIL_BUTTON_ID} .storymaker-contact-icon {
          font-size: 17px;
        }

        #${WRAP_ID} .storymaker-contact-label {
          position: absolute;
          width: 1px;
          height: 1px;
          padding: 0;
          margin: -1px;
          overflow: hidden;
          clip: rect(0, 0, 0, 0);
          white-space: nowrap;
          border: 0;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function installButton() {
    if (!document.body || document.getElementById(WRAP_ID)) return;

    const wrap = document.createElement('div');
    wrap.id = WRAP_ID;
    wrap.setAttribute('aria-label', '스토리메이커 문의 바로가기');

    const kakao = document.createElement('a');
    kakao.id = BUTTON_ID;
    kakao.href = CHANNEL_URL;
    kakao.target = '_blank';
    kakao.rel = 'noopener noreferrer';
    kakao.setAttribute('aria-label', '스토리메이커 카카오톡 채널 문의');
    kakao.title = '카카오톡 채널 문의';
    kakao.innerHTML = '<span class="storymaker-contact-icon" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false"><path d="M12 3C6.48 3 2 6.53 2 10.88c0 2.82 1.89 5.29 4.73 6.68l-.98 3.56c-.09.32.28.58.56.4l4.28-2.83c.46.05.93.08 1.41.08 5.52 0 10-3.53 10-7.89S17.52 3 12 3Z"/></svg></span><span class="storymaker-contact-label">카카오톡 채널</span>';

    const mail = document.createElement('a');
    mail.id = MAIL_BUTTON_ID;
    mail.href = MAIL_URL;
    mail.setAttribute('aria-label', '스토리메이커 이메일 문의');
    mail.title = '이메일 문의 · rinsoo641022@gmail.com';
    mail.innerHTML = '<span class="storymaker-contact-icon" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false"><rect x="3" y="5" width="18" height="14" rx="2"></rect><path d="m4 7 8 6 8-6"></path></svg></span><span class="storymaker-contact-label">이메일 문의</span>';

    wrap.append(kakao, mail);
    document.body.appendChild(wrap);
  }

  function boot() {
    installStyle();
    installButton();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
