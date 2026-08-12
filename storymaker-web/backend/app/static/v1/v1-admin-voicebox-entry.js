(() => {
  'use strict';

  if (window.__STORYMAKER_V1_ADMIN_VOICEBOX_ENTRY__) return;
  window.__STORYMAKER_V1_ADMIN_VOICEBOX_ENTRY__ = true;

  const BUTTON_ID = 'v1-admin-voicebox-entry';
  const TARGET_URL = '/static/v1/voicebox-studio.html';

  function normalize(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

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

  function removeButton() {
    document.getElementById(BUTTON_ID)?.remove();
  }

  function ensureButton() {
    let button = document.getElementById(BUTTON_ID);
    if (button) return button;

    button = document.createElement('button');
    button.id = BUTTON_ID;
    button.type = 'button';
    button.setAttribute('aria-label', 'VoiceBox Studio 열기');
    button.title = 'VoiceBox Studio';
    button.innerHTML = `
      <span class="v1-admin-voicebox-icon" aria-hidden="true">VB</span>
      <span class="v1-admin-voicebox-copy">
        <strong>VoiceBox</strong>
        <small>관리자 음성 스튜디오</small>
      </span>
    `;

    const style = document.createElement('style');
    style.id = 'v1-admin-voicebox-entry-style';
    style.textContent = `
      #${BUTTON_ID}{position:fixed;right:22px;bottom:22px;z-index:2147483000;display:flex;align-items:center;gap:10px;border:1px solid rgba(167,139,250,.55);border-radius:18px;background:linear-gradient(135deg,#111827 0%,#312e81 100%);color:#fff;padding:10px 14px;box-shadow:0 16px 40px rgba(15,23,42,.45);cursor:pointer;font-family:inherit;transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease}
      #${BUTTON_ID}:hover{transform:translateY(-2px);border-color:#c4b5fd;box-shadow:0 20px 48px rgba(49,46,129,.42)}
      #${BUTTON_ID} .v1-admin-voicebox-icon{display:grid;place-items:center;width:38px;height:38px;border-radius:12px;background:#8b5cf6;color:#fff;font-size:13px;font-weight:900;letter-spacing:.04em}
      #${BUTTON_ID} .v1-admin-voicebox-copy{display:grid;text-align:left;line-height:1.1}
      #${BUTTON_ID} strong{font-size:14px;font-weight:900}
      #${BUTTON_ID} small{margin-top:4px;font-size:10px;font-weight:700;color:#ddd6fe}
      @media(max-width:767px){#${BUTTON_ID}{right:12px;bottom:74px;padding:8px 10px;border-radius:15px}#${BUTTON_ID} .v1-admin-voicebox-copy small{display:none}}
    `;
    if (!document.getElementById(style.id)) document.head.appendChild(style);

    button.addEventListener('click', () => {
      try {
        window.sessionStorage.setItem('storymaker_voicebox_admin_entry', String(Date.now()));
      } catch (_) {}
      window.dispatchEvent(new CustomEvent('storymaker-open-inline-lab', {
        detail: { type: 'voicebox', trigger: button },
      }));
    });
    document.body.appendChild(button);
    return button;
  }

  async function refresh() {
    const admin = await fetchAdminState();
    if (admin) ensureButton();
    else removeButton();
  }

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
