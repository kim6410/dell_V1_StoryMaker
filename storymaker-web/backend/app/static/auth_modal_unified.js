// StoryMaker Unified Auth Modal v1
(function(){
  function icon(name){
    const icons = {
      user: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 21a8 8 0 0 0-16 0"/><circle cx="12" cy="7" r="4"/></svg>',
      mail: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>',
      lock: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="10" width="16" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>',
      eye: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>',
      eyeOff: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18"/><path d="M10.6 10.6A3 3 0 0 0 13.4 13.4"/><path d="M7.1 7.1C3.9 8.7 2 12 2 12s3.5 6 10 6c1.7 0 3.2-.4 4.4-1"/><path d="M14.2 6.3A10.6 10.6 0 0 0 12 6C5.5 6 2 12 2 12s.9 1.5 2.5 3"/><path d="M19.5 15C21.1 13.5 22 12 22 12s-3.5-6-10-6"/></svg>',
      check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>',
      warn: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10.3 4.2 2.6 18a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>'
    };
    return icons[name] || '';
  }

  function ensureCss(){
    if (document.getElementById('storymaker-auth-modal-css-link')) return;
    const link = document.createElement('link');
    link.id = 'storymaker-auth-modal-css-link';
    link.rel = 'stylesheet';
    link.href = '/static/auth_modal_unified.css?v=20260705-auth-art-1';
    document.head.appendChild(link);
  }

  function ensureStoryMakerLoginModal(){
    ensureCss();
    let modal = document.getElementById('storymaker-login-modal');
    if (modal && modal.dataset.unifiedAuth === '1') return modal;
    if (modal) modal.remove();

    modal = document.createElement('div');
    modal.id = 'storymaker-login-modal';
    modal.dataset.unifiedAuth = '1';
    modal.setAttribute('aria-hidden', 'true');
    modal.innerHTML = `
      <div class="sm-auth-card" role="dialog" aria-modal="true" aria-label="StoryMaker 통합 인증">
        <div class="sm-auth-head">
          <div class="sm-auth-brand">
            <strong class="sm-auth-title">StoryMaker</strong>
            <span class="sm-auth-sub">SNS AI Studio를 시작해보세요.</span>
          </div>
          <button type="button" class="sm-auth-close" data-login-close aria-label="닫기">×</button>
        </div>

        <div class="sm-auth-tabs" role="tablist" aria-label="인증 메뉴">
          <button type="button" class="sm-auth-tab is-active" data-auth-tab="login" aria-pressed="true">로그인</button>
          <button type="button" class="sm-auth-tab" data-auth-tab="register" aria-pressed="false">회원가입</button>
        </div>

        <form id="storymaker-login-form" class="sm-auth-panel is-active">
          <label class="sm-auth-label" for="storymaker-login-username">사용자명 또는 이메일</label>
          <div class="sm-auth-field"><span class="sm-auth-icon">${icon('user')}</span><input id="storymaker-login-username" class="sm-auth-input" type="text" autocomplete="username" placeholder="사용자명 또는 이메일을 입력하세요" required></div>
          <label class="sm-auth-label" for="storymaker-login-password">비밀번호</label>
          <div class="sm-auth-field"><span class="sm-auth-icon">${icon('lock')}</span><input id="storymaker-login-password" class="sm-auth-input has-eye" type="password" autocomplete="current-password" placeholder="비밀번호를 입력하세요" required><button type="button" class="sm-auth-eye" data-password-toggle data-target="storymaker-login-password" aria-label="비밀번호 보기" title="비밀번호 보기">${icon('eye')}</button></div>
          <div id="storymaker-login-error" class="sm-auth-message is-error"></div>
          <div class="sm-auth-row"><label class="sm-auth-check"><input id="storymaker-remember-login" type="checkbox">로그인 상태 유지</label><button type="button" class="sm-auth-link" data-auth-link="password">비밀번호를 잊으셨나요?</button></div>
          <button id="storymaker-login-submit" class="sm-auth-submit" type="submit">로그인</button>
        </form>

        <form id="storymaker-register-panel" class="sm-auth-panel">
          <label class="sm-auth-label" for="storymaker-register-username">사용자명</label>
          <div class="sm-auth-field"><span class="sm-auth-icon">${icon('user')}</span><input id="storymaker-register-username" class="sm-auth-input" type="text" autocomplete="username" placeholder="사용자명을 입력하세요"></div>
          <label class="sm-auth-label" for="storymaker-register-email">이메일</label>
          <div class="sm-auth-field"><span class="sm-auth-icon">${icon('mail')}</span><input id="storymaker-register-email" class="sm-auth-input" type="email" autocomplete="email" placeholder="이메일을 입력하세요"></div>
          <label class="sm-auth-label" for="storymaker-register-password">비밀번호</label>
          <div class="sm-auth-field"><span class="sm-auth-icon">${icon('lock')}</span><input id="storymaker-register-password" class="sm-auth-input has-eye" type="password" autocomplete="new-password" placeholder="비밀번호를 입력하세요"><button type="button" class="sm-auth-eye" data-password-toggle data-target="storymaker-register-password" aria-label="비밀번호 보기" title="비밀번호 보기">${icon('eye')}</button></div>
          <label class="sm-auth-label" for="storymaker-register-password-confirm">비밀번호 확인</label>
          <div class="sm-auth-field"><span class="sm-auth-icon">${icon('lock')}</span><input id="storymaker-register-password-confirm" class="sm-auth-input has-eye" type="password" autocomplete="new-password" placeholder="비밀번호를 다시 입력하세요"><button type="button" class="sm-auth-eye" data-password-toggle data-target="storymaker-register-password-confirm" aria-label="비밀번호 보기" title="비밀번호 보기">${icon('eye')}</button></div>
          <div id="storymaker-register-message" class="sm-auth-message"></div>
          <button id="storymaker-register-submit" class="sm-auth-submit" type="submit">회원가입 신청</button>
          <div class="sm-auth-mini-links">
            <button type="button" class="sm-auth-link" data-auth-link="find-id">아이디 찾기</button>
            <span class="sm-auth-dot">·</span>
            <button type="button" class="sm-auth-link" data-auth-link="password">비밀번호 찾기</button>
          </div>
          <p class="sm-auth-note" style="text-align:center;margin-top:8px;margin-bottom:0;">회원가입 시 이메일 인증이 필요합니다.</p>
        </form>

        <form id="storymaker-id-panel" class="sm-auth-panel">
          <div class="sm-auth-state" style="padding-top:2px;"><span class="sm-auth-state-icon" style="color:#60a5fa;background:rgba(37,99,235,.13);box-shadow:0 0 0 8px rgba(37,99,235,.06)">${icon('user')}</span><h3>아이디 찾기</h3><p>가입 시 사용한 이메일 주소를 입력하시면 가입 여부와 아이디 안내를 확인할 수 있게 연결합니다.</p></div>
          <label class="sm-auth-label" for="storymaker-id-email">이메일 주소</label>
          <div class="sm-auth-field"><span class="sm-auth-icon">${icon('mail')}</span><input id="storymaker-id-email" class="sm-auth-input" type="email" autocomplete="email" placeholder="이메일을 입력하세요"></div>
          <div id="storymaker-id-message" class="sm-auth-message"></div>
          <button id="storymaker-id-submit" class="sm-auth-submit" type="submit">아이디 찾기</button>
          <button type="button" class="sm-auth-link" data-auth-link="login" style="width:100%;margin-top:16px;">로그인으로 돌아가기</button>
        </form>

        <form id="storymaker-password-panel" class="sm-auth-panel">
          <div class="sm-auth-state" style="padding-top:2px;"><span class="sm-auth-state-icon" style="color:#60a5fa;background:rgba(37,99,235,.13);box-shadow:0 0 0 8px rgba(37,99,235,.06)">${icon('mail')}</span><h3>비밀번호 재설정</h3><p>가입 시 사용한 이메일 주소를 입력하시면 비밀번호 재설정 링크를 보내드립니다.</p></div>
          <label class="sm-auth-label" for="storymaker-password-email">이메일 주소</label>
          <div class="sm-auth-field"><span class="sm-auth-icon">${icon('mail')}</span><input id="storymaker-password-email" class="sm-auth-input" type="email" autocomplete="email" placeholder="이메일을 입력하세요"></div>
          <div id="storymaker-password-message" class="sm-auth-message"></div>
          <button id="storymaker-password-submit" class="sm-auth-submit" type="submit">재설정 링크 보내기</button>
          <button type="button" class="sm-auth-link" data-auth-link="login" style="width:100%;margin-top:16px;">로그인으로 돌아가기</button>
        </form>

        <div id="storymaker-auth-success" class="sm-auth-panel">
          <div class="sm-auth-state"><span class="sm-auth-state-icon">${icon('check')}</span><h3 id="storymaker-auth-success-title">요청이 완료되었습니다.</h3><p id="storymaker-auth-success-text">메일함을 확인해 주세요.</p><button type="button" class="sm-auth-submit" data-auth-link="login">로그인으로 돌아가기</button></div>
        </div>

        <!-- TODO: GitHub / Google 로그인은 아직 연결 전입니다. provider 설정 완료 후 아래 영역을 활성화하면 됩니다.
        <div class="sm-auth-social">
          <button type="button" data-social-login="github">GitHub로 계속하기</button>
          <button type="button" data-social-login="google">Google로 계속하기</button>
        </div>
        -->
      </div>
    `;
    document.body.appendChild(modal);
    bindAuthModal(modal);
    return modal;
  }

  function bindAuthModal(modal){
    modal.querySelector('[data-login-close]').addEventListener('click', closeStoryMakerLoginModal);
    modal.querySelectorAll('[data-auth-tab],[data-auth-link]').forEach(function(button){
      button.addEventListener('click', function(e){
        e.preventDefault();
        setStoryMakerAuthMode(button.getAttribute('data-auth-tab') || button.getAttribute('data-auth-link') || 'login');
      });
    });
    modal.querySelectorAll('[data-password-toggle]').forEach(function(button){
      button.addEventListener('click', function(){
        const targetId = button.getAttribute('data-target');
        const input = targetId ? document.getElementById(targetId) : null;
        if (!input) return;
        const visible = input.type === 'text';
        input.type = visible ? 'password' : 'text';
        button.innerHTML = visible ? icon('eye') : icon('eyeOff');
        button.setAttribute('aria-label', visible ? '비밀번호 보기' : '비밀번호 숨기기');
        button.setAttribute('title', visible ? '비밀번호 보기' : '비밀번호 숨기기');
      });
    });
    modal.addEventListener('click', function(e){ if (e.target === modal) closeStoryMakerLoginModal(); });
    document.addEventListener('keydown', function(e){ if (e.key === 'Escape' && modal.style.display === 'flex') closeStoryMakerLoginModal(); });
    modal.querySelector('#storymaker-login-form').addEventListener('submit', function(e){
      if (typeof window.submitStoryMakerLogin === 'function') return window.submitStoryMakerLogin(e);
    });
    modal.querySelector('#storymaker-register-panel').addEventListener('submit', submitRegister);
    modal.querySelector('#storymaker-id-panel').addEventListener('submit', submitFindId);
    modal.querySelector('#storymaker-password-panel').addEventListener('submit', submitPasswordReset);
  }

  function setStoryMakerAuthMode(tab){
    const modal = document.getElementById('storymaker-login-modal');
    if (!modal) return;
    const mode = (tab === 'register' || tab === 'join') ? 'register' : (tab === 'find-id' || tab === 'id') ? 'find-id' : (tab === 'password' || tab === 'lostpassword') ? 'password' : (tab === 'success') ? 'success' : 'login';
    modal.querySelectorAll('.sm-auth-tab').forEach(function(btn){
      const active = btn.getAttribute('data-auth-tab') === mode;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    modal.querySelectorAll('.sm-auth-panel').forEach(function(panel){ panel.classList.remove('is-active'); });
    const target = mode === 'register' ? '#storymaker-register-panel' : mode === 'find-id' ? '#storymaker-id-panel' : mode === 'password' ? '#storymaker-password-panel' : mode === 'success' ? '#storymaker-auth-success' : '#storymaker-login-form';
    const panel = modal.querySelector(target);
    if (panel) panel.classList.add('is-active');
    setTimeout(function(){
      const focusTarget = mode === 'register' ? document.getElementById('storymaker-register-username') : mode === 'find-id' ? document.getElementById('storymaker-id-email') : mode === 'password' ? document.getElementById('storymaker-password-email') : document.getElementById('storymaker-login-username');
      if (focusTarget) focusTarget.focus();
    }, 60);
  }

  function showSuccess(title, text){
    const titleEl = document.getElementById('storymaker-auth-success-title');
    const textEl = document.getElementById('storymaker-auth-success-text');
    if (titleEl) titleEl.innerText = title || '요청이 완료되었습니다.';
    if (textEl) textEl.innerText = text || '메일함을 확인해 주세요.';
    setStoryMakerAuthMode('success');
  }

  async function submitRegister(e){
    if (e) e.preventDefault();
    const username = (document.getElementById('storymaker-register-username')?.value || '').trim();
    const email = (document.getElementById('storymaker-register-email')?.value || '').trim();
    const pw = document.getElementById('storymaker-register-password')?.value || '';
    const pw2 = document.getElementById('storymaker-register-password-confirm')?.value || '';
    const msg = document.getElementById('storymaker-register-message');
    const btn = document.getElementById('storymaker-register-submit');
    if (msg) { msg.classList.remove('is-error'); msg.style.display = 'none'; msg.innerText = ''; }
    if (!username) {
      if (msg) { msg.innerText = '사용자명을 입력해 주세요. 한글 이름도 사용할 수 있습니다.'; msg.classList.add('is-error'); msg.style.display = 'block'; }
      return;
    }
    if (!email) {
      if (msg) { msg.innerText = '이메일 주소를 입력해 주세요.'; msg.classList.add('is-error'); msg.style.display = 'block'; }
      return;
    }
    if (!/^\S+@\S+\.\S+$/.test(email)) {
      if (msg) { msg.innerText = '올바른 이메일 주소를 입력해 주세요.'; msg.classList.add('is-error'); msg.style.display = 'block'; }
      return;
    }
    if (!pw) {
      if (msg) { msg.innerText = '비밀번호를 입력해 주세요.'; msg.classList.add('is-error'); msg.style.display = 'block'; }
      return;
    }
    if (pw.length < 6) {
      if (msg) { msg.innerText = '비밀번호는 최소 6자 이상 입력해 주세요.'; msg.classList.add('is-error'); msg.style.display = 'block'; }
      return;
    }
    if (pw !== pw2) {
      if (msg) { msg.innerText = '비밀번호와 비밀번호 확인이 일치하지 않습니다.'; msg.classList.add('is-error'); msg.style.display = 'block'; }
      return;
    }
    if (btn) { btn.disabled = true; btn.innerText = '가입 처리 중...'; }
    try {
      const response = await fetch('https://mystorymaker.net/wp-json/storymaker/v1/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username, email: email, password: pw })
      });
      const data = await response.json().catch(function(){ return {}; });
      if (!response.ok || data.ok === false) {
        throw new Error(data.message || data.detail || '회원가입 처리에 실패했습니다.');
      }
      showSuccess('회원가입이 완료되었습니다!', data.message || '회원가입이 완료되었습니다. 이메일을 확인해 주세요.');
    } catch (err) {
      if (msg) {
        msg.innerText = err.message || '회원가입 처리에 실패했습니다.';
        msg.classList.add('is-error');
        msg.style.display = 'block';
      }
    } finally {
      if (btn) { btn.disabled = false; btn.innerText = '회원가입 신청'; }
    }
  }

  function submitFindId(e){
    if (e) e.preventDefault();
    const email = (document.getElementById('storymaker-id-email')?.value || '').trim();
    const msg = document.getElementById('storymaker-id-message');
    if (msg) { msg.classList.remove('is-error'); msg.style.display = 'none'; msg.innerText = ''; }
    if (!email) {
      if (msg) { msg.innerText = '아이디를 찾을 이메일 주소를 입력해 주세요.'; msg.classList.add('is-error'); msg.style.display = 'block'; }
      return;
    }
    showSuccess('아이디 찾기 안내', '입력하신 이메일 기준으로 가입 정보를 확인하는 기능을 연결할 예정입니다. 현재는 이메일 주소로 로그인할 수 있습니다.');
  }

  function submitPasswordReset(e){
    if (e) e.preventDefault();
    const email = (document.getElementById('storymaker-password-email')?.value || '').trim();
    const msg = document.getElementById('storymaker-password-message');
    if (msg) { msg.classList.remove('is-error'); msg.style.display = 'none'; msg.innerText = ''; }
    if (!email) {
      if (msg) { msg.innerText = '비밀번호를 재설정할 이메일 주소를 입력해 주세요.'; msg.classList.add('is-error'); msg.style.display = 'block'; }
      return;
    }
    showSuccess('이메일을 발송했습니다', '입력하신 이메일로 비밀번호 재설정 링크를 보냈습니다. 메일함을 확인해 주세요.');
  }

  function showAuthModal(tab){
    const modal = ensureStoryMakerLoginModal();
    modal.style.display = 'flex';
    modal.classList.add('is-open');
    modal.setAttribute('aria-hidden', 'false');
    setStoryMakerAuthMode(tab || 'login');
  }

  function closeStoryMakerLoginModal(){
    const modal = document.getElementById('storymaker-login-modal');
    if (!modal) return;
    modal.style.display = 'none';
    modal.classList.remove('is-open');
    modal.setAttribute('aria-hidden', 'true');
  }

  function handleLogin(e){ if (e) e.preventDefault(); showAuthModal('login'); }
  function handleJoin(e){ if (e) e.preventDefault(); showAuthModal('register'); }

  window.ensureStoryMakerLoginModal = ensureStoryMakerLoginModal;
  window.setStoryMakerAuthMode = setStoryMakerAuthMode;
  window.showAuthModal = showAuthModal;
  window.closeStoryMakerLoginModal = closeStoryMakerLoginModal;
  window.handleLogin = handleLogin;
  window.handleJoin = handleJoin;
  window.submitStoryMakerRegister = submitRegister;
  window.submitStoryMakerFindId = submitFindId;
  window.submitStoryMakerPasswordReset = submitPasswordReset;

  function openFromAction(){
    try {
      const params = new URLSearchParams(window.location.search || '');
      const action = String(params.get('action') || '').toLowerCase();
      if (action === 'login') showAuthModal('login');
      else if (action === 'register' || action === 'join') showAuthModal('register');
      else if (action === 'password' || action === 'lostpassword') showAuthModal('password');
      else if (action === 'mypage') runWhenReady(function(){
        if (typeof window.showMyPageModal === 'function') return window.showMyPageModal();
        return false;
      });
      else if (action === 'admin') runWhenReady(function(){
        if (typeof window.showAdminDashboard === 'function') { window.showAdminDashboard(); return true; }
        if (typeof window.openAdminDashboard === 'function') { window.openAdminDashboard(); return true; }
        return false;
      });
    } catch(e) {}
  }

  function runWhenReady(fn){
    let tries = 0;
    const tick = function(){
      tries += 1;
      let done = false;
      try { done = fn() === true; } catch(e) { done = false; }
      if (!done && tries < 20) setTimeout(tick, 150);
    };
    tick();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', openFromAction, { once: true });
  else setTimeout(openFromAction, 250);
  window.addEventListener('load', function(){ setTimeout(openFromAction, 350); }, { once: true });
})();
