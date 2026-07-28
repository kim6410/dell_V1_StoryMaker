(function(){
  'use strict';
  if (window.__STORYMAKER_MYPAGE_ACTION_ENHANCER__) return;
  window.__STORYMAKER_MYPAGE_ACTION_ENHANCER__ = true;

  const STYLE_ID = 'v1-mypage-action-enhancer-style';
  const TOP_ACTIONS_ID = 'v1-mypage-top-actions';
  const CONFIRM_ID = 'v1-mypage-logout-confirm';
  let saveRequested = false;
  let logoutBypass = false;
  let logoutEnterCount = 0;

  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();

  function ensureStyle(){
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #${TOP_ACTIONS_ID}{display:flex;align-items:center;gap:10px;margin-left:auto;margin-right:12px;flex-wrap:wrap;justify-content:flex-end}
      #${TOP_ACTIONS_ID} button{min-height:46px;border-radius:999px;padding:0 22px;font-size:14px;font-weight:950;cursor:pointer;transition:.18s ease}
      #${TOP_ACTIONS_ID} .v1-mypage-top-save{border:1px solid #67e8f9;background:#67e8f9;color:#082f49}
      #${TOP_ACTIONS_ID} .v1-mypage-top-save:hover{filter:brightness(.95);transform:translateY(-1px)}
      #${TOP_ACTIONS_ID} .v1-mypage-top-logout{border:1px solid rgba(251,113,133,.6);background:rgba(159,18,57,.18);color:#ffe4e6}
      #${TOP_ACTIONS_ID} .v1-mypage-top-logout:hover{background:rgba(190,24,93,.28)}
      #${CONFIRM_ID}{position:fixed;inset:0;z-index:2147483600;display:none;align-items:center;justify-content:center;padding:18px;background:rgba(2,6,23,.62);backdrop-filter:blur(5px)}
      #${CONFIRM_ID}.is-open{display:flex}
      #${CONFIRM_ID} .v1-logout-box{width:min(360px,calc(100vw - 36px));border:1px solid rgba(148,163,184,.28);border-radius:20px;background:#0f172a;padding:24px;box-shadow:0 24px 70px rgba(0,0,0,.55);text-align:center}
      #${CONFIRM_ID} .v1-logout-title{margin:0;color:#f8fafc;font-size:19px;font-weight:950}
      #${CONFIRM_ID} .v1-logout-desc{margin:10px 0 0;color:#cbd5e1;font-size:13px;font-weight:700;line-height:1.55}
      #${CONFIRM_ID} .v1-logout-actions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:22px}
      #${CONFIRM_ID} button{min-height:44px;border-radius:14px;font-size:14px;font-weight:950;cursor:pointer}
      #${CONFIRM_ID} .v1-logout-no{border:1px solid #475569;background:#1e293b;color:#e2e8f0}
      #${CONFIRM_ID} .v1-logout-yes{border:1px solid #fb7185;background:#9f1239;color:#fff1f2}
      @media(max-width:720px){#${TOP_ACTIONS_ID}{width:100%;margin:10px 0 0;justify-content:flex-start}#${TOP_ACTIONS_ID} button{flex:1;min-width:130px}}
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
    const response = await nativeFetch(input, init);
    try {
      const url = typeof input === 'string' ? input : String(input?.url || '');
      const method = String(init?.method || (typeof input !== 'string' ? input?.method : '') || 'GET').toUpperCase();
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

  function installTopActions(dialog){
    if (!dialog || dialog.querySelector('#' + TOP_ACTIONS_ID)) return;
    const title = [...dialog.querySelectorAll('h1,h2,h3')].find((node) => clean(node.textContent) === '마이페이지');
    const close = findButton(dialog, '닫기');
    const save = findButton(dialog, '저장 / 수정');
    const logout = findButton(dialog, '로그아웃');
    if (!title || !close || !save || !logout) return;

    const header = title.parentElement?.parentElement || title.parentElement;
    if (!header) return;
    ensureStyle();

    const actions = document.createElement('div');
    actions.id = TOP_ACTIONS_ID;
    const saveTop = document.createElement('button');
    saveTop.type = 'button';
    saveTop.className = 'v1-mypage-top-save';
    saveTop.textContent = '저장 / 수정';
    saveTop.addEventListener('click', () => {
      saveRequested = true;
      save.click();
    });
    const logoutTop = document.createElement('button');
    logoutTop.type = 'button';
    logoutTop.className = 'v1-mypage-top-logout';
    logoutTop.textContent = '로그아웃';
    logoutTop.addEventListener('click', openConfirm);
    actions.append(saveTop, logoutTop);
    header.insertBefore(actions, close);
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
    if (text === '로그아웃' && !logoutBypass && !button.classList.contains('v1-mypage-top-logout')) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      openConfirm();
    }
  }, true);

  function apply(){
    const dialog = findMyPageDialog();
    if (dialog) installTopActions(dialog);
  }

  let timer = 0;
  const schedule = () => { clearTimeout(timer); timer = setTimeout(apply, 80); };
  new MutationObserver(schedule).observe(document.documentElement, {childList:true, subtree:true});
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', schedule, {once:true}); else schedule();
})();
