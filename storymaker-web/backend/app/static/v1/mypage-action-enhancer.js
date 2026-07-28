(function(){
  'use strict';
  if (window.__STORYMAKER_MYPAGE_ACTION_ENHANCER__) return;
  window.__STORYMAKER_MYPAGE_ACTION_ENHANCER__ = true;

  const STYLE_ID = 'v1-mypage-action-enhancer-style';
  const TOP_ACTIONS_ID = 'v1-mypage-top-actions';
  const BOTTOM_ACTIONS_ID = 'v1-mypage-bottom-actions';
  const CONFIRM_ID = 'v1-mypage-logout-confirm';
  const PASSWORD_FORM_ID = 'v1-mypage-password-form';
  let saveRequested = false;
  let logoutBypass = false;
  let closeBypass = false;
  let logoutEnterCount = 0;

  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();

  function ensureStyle(){
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #${TOP_ACTIONS_ID}{display:flex;align-items:center;justify-content:flex-end;gap:12px;flex-wrap:wrap}
      #${TOP_ACTIONS_ID}{margin-left:auto;margin-right:0}
      #${BOTTOM_ACTIONS_ID}{display:none!important}
      #${TOP_ACTIONS_ID} button{min-width:118px;min-height:50px;border-radius:999px;padding:0 24px;font-size:15px;font-weight:950;letter-spacing:-.02em;cursor:pointer;transition:transform .18s ease,filter .18s ease,background .18s ease,border-color .18s ease;box-sizing:border-box}
      #${TOP_ACTIONS_ID} button:hover{transform:translateY(-1px);filter:brightness(1.05)}
      #${TOP_ACTIONS_ID} .v1-mypage-action-save{border:1px solid #67e8f9;background:#67e8f9;color:#082f49;box-shadow:0 10px 26px rgba(103,232,249,.16)}
      #${TOP_ACTIONS_ID} .v1-mypage-action-logout{border:1px solid rgba(251,113,133,.62);background:rgba(159,18,57,.20);color:#ffe4e6}
      #${TOP_ACTIONS_ID} .v1-mypage-action-close{border:1px solid rgba(148,163,184,.34);background:rgba(15,23,42,.58);color:#f8fafc}
      [data-v1-mypage-native-bottom="1"]{display:none!important}
      #${CONFIRM_ID}{position:fixed;inset:0;z-index:2147483600;display:none;align-items:center;justify-content:center;padding:18px;background:rgba(2,6,23,.62);backdrop-filter:blur(5px)}
      #${CONFIRM_ID}.is-open{display:flex}
      #${CONFIRM_ID} .v1-logout-box{width:min(360px,calc(100vw - 36px));border:1px solid rgba(148,163,184,.28);border-radius:20px;background:#0f172a;padding:24px;box-shadow:0 24px 70px rgba(0,0,0,.55);text-align:center}
      #${CONFIRM_ID} .v1-logout-title{margin:0;color:#f8fafc;font-size:19px;font-weight:950}
      #${CONFIRM_ID} .v1-logout-desc{margin:10px 0 0;color:#cbd5e1;font-size:13px;font-weight:700;line-height:1.55}
      #${CONFIRM_ID} .v1-logout-actions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:22px}
      #${CONFIRM_ID} button{min-height:44px;border-radius:14px;font-size:14px;font-weight:950;cursor:pointer}
      #${CONFIRM_ID} .v1-logout-no{border:1px solid #475569;background:#1e293b;color:#e2e8f0}
      #${CONFIRM_ID} .v1-logout-yes{border:1px solid #fb7185;background:#9f1239;color:#fff1f2}
      #${PASSWORD_FORM_ID}{margin-top:16px;border:1px solid rgba(103,232,249,.28);border-radius:18px;background:rgba(2,6,23,.64);padding:18px}
      #${PASSWORD_FORM_ID} h4{margin:0;color:#f8fafc;font-size:16px;font-weight:950}
      #${PASSWORD_FORM_ID} p{margin:7px 0 0;color:#94a3b8;font-size:12px;font-weight:700;line-height:1.55}
      #${PASSWORD_FORM_ID} .v1-password-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:15px}
      #${PASSWORD_FORM_ID} label{display:grid;gap:7px;color:#cbd5e1;font-size:12px;font-weight:900}
      #${PASSWORD_FORM_ID} .v1-password-field{position:relative;display:block}
      #${PASSWORD_FORM_ID} input{width:100%;height:46px;border:1px solid rgba(148,163,184,.34);border-radius:13px;background:#020617;color:#f8fafc;padding:0 52px 0 13px;box-sizing:border-box;font-size:14px;outline:none}
      #${PASSWORD_FORM_ID} input:focus{border-color:#67e8f9;box-shadow:0 0 0 3px rgba(103,232,249,.12)}
      #${PASSWORD_FORM_ID} .v1-password-toggle{position:absolute;right:9px;top:50%;transform:translateY(-50%);width:36px;height:36px;display:grid;place-items:center;border:0;border-radius:999px;background:transparent;color:#94a3b8;cursor:pointer;padding:0}
      #${PASSWORD_FORM_ID} .v1-password-toggle:hover,#${PASSWORD_FORM_ID} .v1-password-toggle:focus-visible{background:rgba(103,232,249,.10);color:#67e8f9;outline:none}
      #${PASSWORD_FORM_ID} .v1-password-toggle svg{width:21px;height:21px;pointer-events:none}
      #${PASSWORD_FORM_ID} .v1-password-actions{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:14px;flex-wrap:wrap}
      #${PASSWORD_FORM_ID} .v1-password-message{min-height:20px;color:#fda4af;font-size:12px;font-weight:800}
      #${PASSWORD_FORM_ID} .v1-password-submit{min-height:44px;border:1px solid #67e8f9;border-radius:999px;background:#67e8f9;color:#082f49;padding:0 20px;font-size:13px;font-weight:950;cursor:pointer}
      #${PASSWORD_FORM_ID} .v1-password-submit:disabled{cursor:wait;opacity:.55}
      @media(max-width:720px){#${TOP_ACTIONS_ID}{width:100%;justify-content:stretch;margin:10px 0 0}#${TOP_ACTIONS_ID} button{flex:1;min-width:105px;padding:0 14px;font-size:14px}#${PASSWORD_FORM_ID} .v1-password-grid{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
  }

  function findMyPageDialog(){
    return [...document.querySelectorAll('[role="dialog"],div')].find((node) => {
      const title = [...node.querySelectorAll?.('h1,h2,h3') || []].find((heading) => clean(heading.textContent) === '마이페이지');
      if (!title) return false;
      const rect = node.getBoundingClientRect?.();
      return rect && rect.width > 500 && rect.height > 300;
    }) || null;
  }

  function findButton(dialog, text){
    return [...dialog.querySelectorAll('button')].find((button) => clean(button.textContent) === text) || null;
  }

  function ensureConfirm(){
    let modal = document.getElementById(CONFIRM_ID);
    if (modal) return modal;
    ensureStyle();
    modal = document.createElement('div');
    modal.id = CONFIRM_ID;
    modal.setAttribute('aria-hidden', 'true');
    modal.innerHTML = `
      <div class="v1-logout-box" role="dialog" aria-modal="true" aria-labelledby="v1-logout-title">
        <h2 id="v1-logout-title" class="v1-logout-title">로그아웃 하시겠습니까?</h2>
        <p class="v1-logout-desc">현재 계정의 로그인 세션을 종료합니다.</p>
        <div class="v1-logout-actions">
          <button type="button" class="v1-logout-no">아니오</button>
          <button type="button" class="v1-logout-yes">예</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    modal.querySelector('.v1-logout-no').addEventListener('click', closeConfirm);
    modal.querySelector('.v1-logout-yes').addEventListener('click', confirmLogout);
    modal.addEventListener('mousedown', (event) => { if (event.target === modal) closeConfirm(); });
    modal.addEventListener('keydown', (event) => {
      if (!modal.classList.contains('is-open')) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        closeConfirm();
        return;
      }
      if (event.key !== 'Enter') return;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      logoutEnterCount += 1;
      const desc = modal.querySelector('.v1-logout-desc');
      if (logoutEnterCount === 1) {
        if (desc) desc.textContent = '한 번 더 Enter를 누르면 로그아웃됩니다.';
        modal.querySelector('.v1-logout-yes')?.focus();
        return;
      }
      confirmLogout();
    }, true);
    return modal;
  }

  function openConfirm(){
    const modal = ensureConfirm();
    logoutEnterCount = 0;
    const desc = modal.querySelector('.v1-logout-desc');
    if (desc) desc.textContent = '현재 계정의 로그인 세션을 종료합니다.';
    modal.classList.add('is-open');
    modal.setAttribute('aria-hidden', 'false');
    setTimeout(() => modal.querySelector('.v1-logout-yes')?.focus(), 20);
  }

  function closeConfirm(){
    const modal = document.getElementById(CONFIRM_ID);
    if (!modal) return;
    logoutEnterCount = 0;
    modal.classList.remove('is-open');
    modal.setAttribute('aria-hidden', 'true');
  }

  function closeMyPageImmediately(){
    const dialog = findMyPageDialog();
    if (!dialog) return false;

    if (typeof window.closeMyPageModal === 'function') {
      window.closeMyPageModal();
      return true;
    }

    const nativeClose = [...dialog.querySelectorAll('button')].find((button) => {
      if (button.closest('#' + TOP_ACTIONS_ID) || button.closest('#' + BOTTOM_ACTIONS_ID)) return false;
      return clean(button.textContent) === '닫기';
    });
    if (nativeClose) {
      closeBypass = true;
      try {
        nativeClose.click();
      } finally {
        setTimeout(() => { closeBypass = false; }, 100);
      }
      return true;
    }

    const overlay = dialog.parentElement;
    if (overlay && overlay !== document.body) {
      overlay.dispatchEvent(new MouseEvent('click', {
        bubbles: true,
        cancelable: true,
        view: window
      }));
      return true;
    }
    return false;
  }

  function confirmLogout(){
    closeConfirm();
    logoutBypass = true;
    try {
      if (typeof window.handleLogout === 'function') {
        Promise.resolve(window.handleLogout()).catch(() => {});
        return;
      }
      const dialog = findMyPageDialog();
      const original = dialog ? findButton(dialog, '로그아웃') : null;
      if (original) original.click();
    } finally {
      setTimeout(() => { logoutBypass = false; }, 250);
    }
  }

  function closeMyPageAfterSave(){
    setTimeout(() => {
      if (typeof window.closeMyPageModal === 'function') {
        window.closeMyPageModal();
        return;
      }
      const dialog = findMyPageDialog();
      const close = dialog ? findButton(dialog, '닫기') : null;
      close?.click();
    }, 450);
  }

  const nativeFetch = window.fetch.bind(window);
  window.fetch = async function(input, init){
    const url = typeof input === 'string' ? input : String(input?.url || '');
    const method = String(init?.method || (typeof input !== 'string' ? input?.method : '') || 'GET').toUpperCase();
    let requestInit = init;
    if (/\/v1-api\/auth\/(?:personas|regions)(?:\/[^/?]+)?(?:\?.*)?$/.test(url)) {
      const token = String(localStorage.getItem('storymaker_token') || '').trim();
      if (token) {
        const headers = new Headers(init?.headers || (typeof input !== 'string' ? input?.headers : undefined));
        if (!headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`);
        requestInit = { ...init, headers, credentials: 'include' };
      }
    }
    const response = await nativeFetch(input, requestInit);
    try {
      const isPersonaSave = /\/v1-api\/auth\/personas(?:\/[^/?]+)?(?:\?.*)?$/.test(url) && (method === 'POST' || method === 'PUT');
      if (saveRequested && isPersonaSave) {
        if (response.ok) {
          saveRequested = false;
          closeMyPageAfterSave();
        } else {
          saveRequested = false;
        }
      }
    } catch (_) {}
    return response;
  };


  function authHeaders(){
    const headers = new Headers({'Content-Type':'application/json','Accept':'application/json'});
    const token = String(localStorage.getItem('storymaker_token') || '').trim();
    if (token) headers.set('Authorization', `Bearer ${token}`);
    return headers;
  }

  function passwordEyeSvg(visible){
    return visible
      ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 3l18 18"></path><path d="M10.58 10.58a2 2 0 0 0 2.83 2.83"></path><path d="M9.88 5.09A9.77 9.77 0 0 1 12 4c5 0 9 4 10 8a11.8 11.8 0 0 1-2.17 3.19"></path><path d="M6.61 6.61A11.75 11.75 0 0 0 2 12c1 4 5 8 10 8a9.77 9.77 0 0 0 4.91-1.38"></path></svg>`
      : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s4-8 10-8 10 8 10 8-4 8-10 8-10-8-10-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
  }

  function togglePasswordVisibility(button){
    const field = button.closest('.v1-password-field');
    const input = field?.querySelector('input');
    if (!input) return;
    const nextVisible = input.type === 'password';
    input.type = nextVisible ? 'text' : 'password';
    button.dataset.visible = nextVisible ? '1' : '0';
    button.setAttribute('aria-label', nextVisible ? '비밀번호 숨기기' : '비밀번호 표시');
    button.setAttribute('title', nextVisible ? '비밀번호 숨기기' : '비밀번호 표시');
    button.innerHTML = passwordEyeSvg(nextVisible);
  }

  async function submitPasswordForm(form){
    const currentInput = form.querySelector('[name="current_password"]');
    const newInput = form.querySelector('[name="new_password"]');
    const confirmInput = form.querySelector('[name="confirm_password"]');
    const message = form.querySelector('.v1-password-message');
    const submit = form.querySelector('.v1-password-submit');
    const currentPassword = currentInput?.value || '';
    const newPassword = newInput?.value || '';
    const confirmPassword = confirmInput?.value || '';
    if (!currentPassword) { message.textContent = '현재 비밀번호를 입력해 주세요.'; currentInput?.focus(); return; }
    if (newPassword.length < 8) { message.textContent = '새 비밀번호는 8자 이상이어야 합니다.'; newInput?.focus(); return; }
    if (newPassword !== confirmPassword) { message.textContent = '새 비밀번호 확인이 일치하지 않습니다.'; confirmInput?.focus(); return; }
    if (currentPassword === newPassword) { message.textContent = '새 비밀번호는 현재 비밀번호와 다르게 입력해 주세요.'; newInput?.focus(); return; }
    submit.disabled = true;
    submit.textContent = '변경 중...';
    message.style.color = '#cbd5e1';
    message.textContent = 'WordPress 로그인 비밀번호를 변경하고 있습니다.';
    try {
      const response = await nativeFetch('/v1-api/auth/change-password', {
        method: 'PUT', credentials: 'include', headers: authHeaders(),
        body: JSON.stringify({current_password: currentPassword, new_password: newPassword})
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data.ok === false) throw new Error(data.detail || data.message || '비밀번호 변경에 실패했습니다.');
      message.style.color = '#86efac';
      message.textContent = data.message || '비밀번호가 변경되었습니다. 다시 로그인해 주세요.';
      currentInput.value = ''; newInput.value = ''; confirmInput.value = '';
      setTimeout(() => {
        if (typeof window.handleLogout === 'function') window.handleLogout();
        else window.location.replace('/v1/?action=login');
      }, 900);
    } catch (error) {
      message.style.color = '#fda4af';
      message.textContent = error?.message || '비밀번호 변경에 실패했습니다.';
    } finally {
      submit.disabled = false;
      submit.textContent = '비밀번호 변경';
    }
  }

  function ensurePasswordForm(dialog){
    const settingsHeading = [...dialog.querySelectorAll('h2,h3,h4')].find((node) => clean(node.textContent) === '계정 및 연동 설정');
    if (!settingsHeading) return;
    const section = settingsHeading.closest('section');
    if (!section || section.querySelector('#' + PASSWORD_FORM_ID)) return;

    const form = document.createElement('form');
    form.id = PASSWORD_FORM_ID;
    form.innerHTML = `
      <h4>로그인 비밀번호 변경</h4>
      <p>실제 WordPress 로그인 비밀번호가 변경되며, 완료 후 모든 기기에서 다시 로그인해야 합니다.</p>
      <div class="v1-password-grid">
        <label>현재 비밀번호<span class="v1-password-field"><input type="password" name="current_password" autocomplete="current-password" required><button type="button" class="v1-password-toggle" data-visible="0" aria-label="비밀번호 표시" title="비밀번호 표시">${passwordEyeSvg(false)}</button></span></label>
        <label>새 비밀번호<span class="v1-password-field"><input type="password" name="new_password" autocomplete="new-password" minlength="8" required><button type="button" class="v1-password-toggle" data-visible="0" aria-label="비밀번호 표시" title="비밀번호 표시">${passwordEyeSvg(false)}</button></span></label>
        <label>새 비밀번호 확인<span class="v1-password-field"><input type="password" name="confirm_password" autocomplete="new-password" minlength="8" required><button type="button" class="v1-password-toggle" data-visible="0" aria-label="비밀번호 표시" title="비밀번호 표시">${passwordEyeSvg(false)}</button></span></label>
      </div>
      <div class="v1-password-actions">
        <span class="v1-password-message" aria-live="polite"></span>
        <button type="submit" class="v1-password-submit">비밀번호 변경</button>
      </div>`;
    form.querySelectorAll('.v1-password-toggle').forEach((button) => {
      button.addEventListener('click', () => togglePasswordVisibility(button));
    });
    form.addEventListener('submit', (event) => { event.preventDefault(); submitPasswordForm(form); });

    const infoGrid = [...section.children].find((child) => child.matches?.('div.grid'));
    if (infoGrid) infoGrid.insertAdjacentElement('afterend', form);
    else section.appendChild(form);
  }


  function buildActionSet(id, save, logout, nativeClose){
    const actions = document.createElement('div');
    actions.id = id;

    const runNativeClose = () => {
      closeBypass = true;
      try {
        nativeClose.click();
      } finally {
        setTimeout(() => { closeBypass = false; }, 120);
      }
    };

    const saveButton = document.createElement('button');
    saveButton.type = 'button';
    saveButton.className = 'v1-mypage-action-save';
    saveButton.textContent = '저장 / 수정';
    saveButton.addEventListener('click', () => {
      saveRequested = true;
      save.click();
      setTimeout(runNativeClose, 0);
    });

    const logoutButton = document.createElement('button');
    logoutButton.type = 'button';
    logoutButton.className = 'v1-mypage-action-logout';
    logoutButton.textContent = '로그아웃';
    logoutButton.addEventListener('click', openConfirm);

    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'v1-mypage-action-close';
    closeButton.textContent = '닫기';
    closeButton.addEventListener('click', runNativeClose);

    actions.append(saveButton, logoutButton, closeButton);
    return actions;
  }

  function installTopActions(dialog){
    if (!dialog) return;
    const title = [...dialog.querySelectorAll('h1,h2,h3')].find((node) => clean(node.textContent) === '마이페이지');
    const nativeClose = findButton(dialog, '닫기');
    const save = findButton(dialog, '저장 / 수정');
    const logout = findButton(dialog, '로그아웃');
    if (!title || !nativeClose || !save || !logout) return;

    const header = title.parentElement?.parentElement || title.parentElement;
    if (!header) return;
    ensureStyle();

    if (!dialog.querySelector('#' + TOP_ACTIONS_ID)) {
      const topActions = buildActionSet(TOP_ACTIONS_ID, save, logout, nativeClose);
      header.insertBefore(topActions, nativeClose);
      nativeClose.style.display = 'none';
    }

    dialog.querySelector('#' + BOTTOM_ACTIONS_ID)?.remove();
    const nativeLogout = [...dialog.querySelectorAll('button')].find((button) => {
      if (button.closest('#' + TOP_ACTIONS_ID)) return false;
      return clean(button.textContent) === '로그아웃';
    });
    const nativeBottomRow = nativeLogout?.parentElement;
    if (nativeBottomRow) nativeBottomRow.dataset.v1MypageNativeBottom = '1';
  }

  document.addEventListener('click', (event) => {
    const button = event.target?.closest?.('button');
    if (!button) return;
    const dialog = findMyPageDialog();
    if (!dialog || !dialog.contains(button)) return;
    const text = clean(button.textContent);
    if (text === '저장 / 수정' && button.id !== TOP_ACTIONS_ID) {
      saveRequested = true;
    }
    if (text === '닫기') {
      if (button.classList.contains('v1-mypage-action-close')) return;
      if (closeBypass) return;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      closeMyPageImmediately();
      return;
    }
    if (text === '로그아웃' && !logoutBypass && !button.classList.contains('v1-mypage-top-logout')) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      openConfirm();
    }
  }, true);

  function apply(){
    const dialog = findMyPageDialog();
    if (dialog) { installTopActions(dialog); ensurePasswordForm(dialog); }
  }

  let timer = 0;
  const schedule = () => { clearTimeout(timer); timer = setTimeout(apply, 80); };
  new MutationObserver(schedule).observe(document.documentElement, {childList:true, subtree:true});
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', schedule, {once:true}); else schedule();
})();
