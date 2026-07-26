// StoryMaker 프론트엔드 회원 인증 및 세션/마이페이지 제어 (app_auth.js)

// WordPress 인증 화면 이동 전용
function showAuthTab(tab) {
    showAuthModal(tab || 'login');
}
window.showAuthTab = showAuthTab;

function getWordPressAuthUrl(tab) {
    const action = tab === 'join' ? 'register' : (tab || 'login');
    return `/storymaker?action=${encodeURIComponent(action)}`;
}
window.getWordPressAuthUrl = getWordPressAuthUrl;

function ensureStoryMakerLoginModal() {
    let modal = document.getElementById('storymaker-login-modal');
    if (modal) return modal;

    modal = document.createElement('div');
    modal.id = 'storymaker-login-modal';
    modal.setAttribute('aria-hidden', 'true');
    modal.style.cssText = 'position:fixed; inset:0; z-index:10050; display:none; align-items:center; justify-content:center; background:radial-gradient(circle at 50% 0%, rgba(59,130,246,0.18), transparent 34%), rgba(2,6,23,0.78); backdrop-filter:blur(18px); -webkit-backdrop-filter:blur(18px); padding:18px;';
    modal.innerHTML = `
      <div style="width:100%; max-width:408px; background:linear-gradient(180deg, rgba(15,23,42,0.96), rgba(2,6,23,0.98)); color:#e5e7eb; border:1px solid rgba(148,163,184,0.22); border-radius:28px; padding:24px; box-shadow:0 34px 90px rgba(0,0,0,0.58), inset 0 1px 0 rgba(255,255,255,0.08);">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:18px;">
          <strong style="font-size:20px; font-weight:900; letter-spacing:-0.04em; color:#f8fafc;">StoryMaker</strong>
          <button type="button" data-login-close aria-label="닫기" style="width:34px; height:34px; border:1px solid rgba(148,163,184,0.22); border-radius:999px; background:rgba(15,23,42,0.72); font-size:20px; line-height:1; cursor:pointer; color:#cbd5e1;">×</button>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-bottom:22px; padding:5px; border:1px solid rgba(148,163,184,0.18); border-radius:18px; background:rgba(15,23,42,0.72);">
          <button type="button" data-auth-tab="login" aria-pressed="true" style="height:44px; border:0; border-radius:14px; background:linear-gradient(180deg, rgba(59,130,246,0.92), rgba(79,70,229,0.92)); color:#ffffff; font-size:15px; font-weight:900; cursor:pointer; box-shadow:0 10px 24px rgba(59,130,246,0.24);">로그인</button>
          <button type="button" data-auth-tab="register" aria-pressed="false" style="height:44px; border:0; border-radius:14px; background:transparent; color:#94a3b8; font-size:15px; font-weight:800; cursor:pointer;">회원가입</button>
        </div>

        <form id="storymaker-login-form">
          <label style="display:block; font-size:12px; font-weight:800; margin-bottom:8px; color:#94a3b8; letter-spacing:-0.02em;">사용자명 또는 이메일</label>
          <input id="storymaker-login-username" type="text" autocomplete="username" required style="width:100%; height:48px; padding:0 14px; border:1px solid rgba(148,163,184,0.24); border-radius:14px; margin-bottom:14px; box-sizing:border-box; font-size:15px; background:rgba(15,23,42,0.72); color:#f8fafc; outline:none;">
          <label style="display:block; font-size:12px; font-weight:800; margin-bottom:8px; color:#94a3b8; letter-spacing:-0.02em;">비밀번호</label>
          <div style="position:relative; margin-bottom:12px;">
            <input id="storymaker-login-password" type="password" autocomplete="current-password" required style="width:100%; height:48px; padding:0 48px 0 14px; border:1px solid rgba(148,163,184,0.24); border-radius:14px; box-sizing:border-box; font-size:15px; background:rgba(15,23,42,0.72); color:#f8fafc; outline:none;">
            <button type="button" data-password-toggle aria-label="비밀번호 보기" title="비밀번호 보기" style="position:absolute; right:8px; top:50%; transform:translateY(-50%); width:34px; height:34px; border:0; border-radius:999px; background:transparent; color:#94a3b8; cursor:pointer; font-size:17px; line-height:1;">◉</button>
          </div>
          <div id="storymaker-login-error" style="display:none; color:#f87171; font-size:12px; font-weight:800; margin-bottom:12px; line-height:1.5;"></div>
          <button id="storymaker-login-submit" type="submit" style="width:100%; height:50px; border:0; border-radius:16px; background:linear-gradient(90deg,#2563eb,#7c3aed); color:white; font-size:15px; font-weight:950; cursor:pointer; box-shadow:0 14px 32px rgba(37,99,235,0.28);">로그인</button>
        </form>

        <form id="storymaker-register-panel" style="display:none; border:1px solid rgba(148,163,184,0.18); border-radius:18px; padding:18px; background:rgba(15,23,42,0.58);">
          <div style="font-size:15px; font-weight:900; color:#f8fafc; margin-bottom:8px; letter-spacing:-0.03em;">StoryMaker 회원가입</div>
          <div style="font-size:13px; line-height:1.7; color:#94a3b8; margin-bottom:16px;">이 화면에서 가입 정보를 입력하면, 다음 단계에서 이메일 확인 방식으로 연결됩니다.</div>
          <label style="display:block; font-size:12px; font-weight:800; margin-bottom:8px; color:#94a3b8; letter-spacing:-0.02em;">사용자명</label>
          <input id="storymaker-register-username" type="text" autocomplete="username" placeholder="honggildong" style="width:100%; height:48px; padding:0 14px; border:1px solid rgba(148,163,184,0.24); border-radius:14px; margin-bottom:14px; box-sizing:border-box; font-size:15px; background:rgba(15,23,42,0.72); color:#f8fafc; outline:none;">
          <label style="display:block; font-size:12px; font-weight:800; margin-bottom:8px; color:#94a3b8; letter-spacing:-0.02em;">이메일</label>
          <input id="storymaker-register-email" type="email" autocomplete="email" placeholder="example@email.com" style="width:100%; height:48px; padding:0 14px; border:1px solid rgba(148,163,184,0.24); border-radius:14px; margin-bottom:12px; box-sizing:border-box; font-size:15px; background:rgba(15,23,42,0.72); color:#f8fafc; outline:none;">
          <div id="storymaker-register-message" style="display:none; color:#93c5fd; font-size:12px; font-weight:800; margin-bottom:12px; line-height:1.5;"></div>
          <button id="storymaker-register-submit" type="submit" style="width:100%; height:50px; border:0; border-radius:16px; background:linear-gradient(90deg,#2563eb,#7c3aed); color:white; font-size:15px; font-weight:950; cursor:pointer; box-shadow:0 14px 32px rgba(37,99,235,0.28);">회원가입 신청</button>
        </form>

        <div style="display:flex; justify-content:center; gap:18px; margin-top:16px; font-size:13px; font-weight:800;">
          <button type="button" data-auth-tab="password" style="border:0; background:transparent; color:#94a3b8; cursor:pointer; font-weight:800;">비밀번호 찾기</button>
        </div>

        <!-- TODO: GitHub / Google 로그인은 아직 연결 전입니다. provider 설정 완료 후 아래 영역을 활성화하면 됩니다.
        <div style="margin-top:18px; display:flex; flex-direction:column; gap:10px;">
          <button type="button" data-social-login="github" style="height:46px; border:1px solid rgba(148,163,184,0.22); border-radius:14px; background:rgba(15,23,42,0.72); color:#e5e7eb; font-weight:900; cursor:pointer;">GitHub로 계속하기</button>
          <button type="button" data-social-login="google" style="height:46px; border:1px solid rgba(148,163,184,0.22); border-radius:14px; background:rgba(15,23,42,0.72); color:#e5e7eb; font-weight:900; cursor:pointer;">Google로 계속하기</button>
        </div>
        -->
      </div>
    `;
    document.body.appendChild(modal);

    modal.querySelector('[data-login-close]').addEventListener('click', closeStoryMakerLoginModal);
    modal.querySelectorAll('[data-auth-tab]').forEach(function(button) {
        button.addEventListener('click', function() {
            setStoryMakerAuthMode(button.getAttribute('data-auth-tab') || 'login');
        });
    });
    const passwordToggle = modal.querySelector('[data-password-toggle]');
    if (passwordToggle) {
        passwordToggle.addEventListener('click', function() {
            const input = document.getElementById('storymaker-login-password');
            if (!input) return;
            const visible = input.type === 'text';
            input.type = visible ? 'password' : 'text';
            passwordToggle.innerText = visible ? '◉' : '◎';
            passwordToggle.setAttribute('aria-label', visible ? '비밀번호 보기' : '비밀번호 숨기기');
            passwordToggle.setAttribute('title', visible ? '비밀번호 보기' : '비밀번호 숨기기');
        });
    }
    modal.addEventListener('click', function(e) {
        if (e.target === modal) closeStoryMakerLoginModal();
    });
    modal.querySelector('#storymaker-login-form').addEventListener('submit', submitStoryMakerLogin);
    const registerForm = modal.querySelector('#storymaker-register-panel');
    if (registerForm) {
        registerForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const msg = document.getElementById('storymaker-register-message');
            if (msg) {
                msg.innerText = '회원가입 API 연결 준비 중입니다. 지금은 관리자 승인 방식으로 계정 생성 후 로그인할 수 있습니다.';
                msg.style.display = 'block';
            }
        });
    }
    return modal;
}
window.ensureStoryMakerLoginModal = ensureStoryMakerLoginModal;

function setStoryMakerAuthMode(tab) {
    const modal = document.getElementById('storymaker-login-modal');
    if (!modal) return;
    const mode = (tab === 'register' || tab === 'join') ? 'register' : 'login';
    const loginTab = modal.querySelector('[data-auth-tab="login"]');
    const registerTab = modal.querySelector('[data-auth-tab="register"]');
    const loginForm = modal.querySelector('#storymaker-login-form');
    const registerPanel = modal.querySelector('#storymaker-register-panel');
    const setActive = function(el, active) {
        if (!el) return;
        el.setAttribute('aria-pressed', active ? 'true' : 'false');
        el.style.background = active ? 'linear-gradient(180deg, rgba(59,130,246,0.92), rgba(79,70,229,0.92))' : 'transparent';
        el.style.color = active ? '#ffffff' : '#94a3b8';
        el.style.fontWeight = active ? '900' : '800';
        el.style.boxShadow = active ? '0 10px 24px rgba(59,130,246,0.24)' : 'none';
    };
    setActive(loginTab, mode === 'login');
    setActive(registerTab, mode === 'register');
    if (loginForm) loginForm.style.display = mode === 'login' ? 'block' : 'none';
    if (registerPanel) registerPanel.style.display = mode === 'register' ? 'block' : 'none';
    if (mode === 'login') {
        setTimeout(function(){
            const username = document.getElementById('storymaker-login-username');
            if (username) username.focus();
        }, 60);
    }
}
window.setStoryMakerAuthMode = setStoryMakerAuthMode;

function closeStoryMakerLoginModal() {
    const modal = document.getElementById('storymaker-login-modal');
    if (!modal) return;
    modal.style.display = 'none';
    modal.setAttribute('aria-hidden', 'true');
}
window.closeStoryMakerLoginModal = closeStoryMakerLoginModal;

async function submitStoryMakerLogin(e) {
    if (e) e.preventDefault();
    const usernameEl = document.getElementById('storymaker-login-username');
    const passwordEl = document.getElementById('storymaker-login-password');
    const errorEl = document.getElementById('storymaker-login-error');
    const submitBtn = document.getElementById('storymaker-login-submit');
    const username = usernameEl ? usernameEl.value.trim() : '';
    const password = passwordEl ? passwordEl.value : '';
    if (!username || !password) return;
    if (errorEl) {
        errorEl.style.display = 'none';
        errorEl.innerText = '';
    }
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerText = '로그인 중...';
    }
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ username, password })
        });
        const res = await response.json();
        if (!response.ok || !res.ok || !res.data) {
            throw new Error(res.detail || res.message || '로그인에 실패했습니다.');
        }
        await completeAuthentication(res.data, 'WordPress');
        localStorage.setItem('storymaker_auth_ok', '1');
        window.dispatchEvent(new CustomEvent('storymaker-auth-changed'));
        closeStoryMakerLoginModal();
        if (typeof window.snsAiUnifiedRender === 'function') window.snsAiUnifiedRender();
    } catch (err) {
        if (errorEl) {
            errorEl.innerText = err.message || '로그인에 실패했습니다.';
            errorEl.style.display = 'block';
        }
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerText = '로그인';
        }
    }
}
window.submitStoryMakerLogin = submitStoryMakerLogin;

function showAuthModal(tab) {
    if (tab === 'lostpassword' || tab === 'password') {
        window.location.href = getWordPressAuthUrl('lostpassword');
        return;
    }
    const modal = ensureStoryMakerLoginModal();
    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
    setStoryMakerAuthMode(tab || 'login');
}
window.showAuthModal = showAuthModal;

function openAuthModalFromUrlAction() {
    try {
        const params = new URLSearchParams(window.location.search || '');
        const action = String(params.get('action') || '').toLowerCase();
        if (action === 'login') {
            showAuthModal('login');
        } else if (action === 'register' || action === 'join') {
            showAuthModal('register');
        } else if (action === 'mypage' && typeof window.showMyPageModal === 'function') {
            window.showMyPageModal();
        }
    } catch (e) {}
}
window.openAuthModalFromUrlAction = openAuthModalFromUrlAction;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', openAuthModalFromUrlAction, { once: true });
} else {
    setTimeout(openAuthModalFromUrlAction, 0);
}

// WordPress 회원가입 화면 이동 처리
async function handleJoin(e) {
    if (e) e.preventDefault();
    showAuthModal('register');
}
window.handleJoin = handleJoin;

// 인증 완료 세션 바인딩 처리 공통화
async function completeAuthentication(authData, providerLabel) {
    const token = authData.access_token || authData.token;
    const user = authData.user || authData;
    
    if (!token || !user) {
        log('인증 데이터가 불완전하여 로그인 처리를 중단합니다.', 'error');
        return;
    }
    
    localStorage.setItem('storymaker_token', token);
    localStorage.setItem('storymaker_user', JSON.stringify(user));
    

    const loggedInUser = document.getElementById('logged-in-user');
    if (loggedInUser) loggedInUser.innerText = `${user.username} (${user.role})`;
    
    const userInfoBar = document.getElementById('user-info-bar');
    if (userInfoBar) userInfoBar.style.display = 'flex';
    
    // 관리자 전용 Admin 메뉴 활성화 분기
    const adminBtn = document.getElementById('admin-menu-btn');
    if (adminBtn) {
        if (user.role === 'admin') {
            adminBtn.style.display = 'inline-block';
        } else {
            adminBtn.style.display = 'none';
        }
    }
    
    log(`[${providerLabel}] 로그인 승인: ${user.username} 계정 활성화`, 'success');
    showToast(`${user.username}님, 반갑습니다!`);
    
    await hydrateWorkspaceAfterAuth();
}
window.completeAuthentication = completeAuthentication;

async function hydrateWorkspaceAfterAuth() {
    if (window.storymakerHydrating) {
        return;
    }
    window.storymakerHydrating = true;
    window.storymakerBootHydrated = false;
    try {
        if (typeof clearCoreInputs === 'function') clearCoreInputs();
        if (typeof checkApiHealth === 'function') await checkApiHealth();
        if (typeof setupAutosaveListeners === 'function') await setupAutosaveListeners();
        if (typeof loadProjectList === 'function') {
            await loadProjectList();
            window.storymakerProjectListLoaded = true;
        }

        const savedProjectId = localStorage.getItem('current_project_id');
        if (savedProjectId) {
            const selector = document.getElementById('project-selector');
            if (selector) selector.value = savedProjectId;
            if (typeof loadSelectedProject === 'function') await loadSelectedProject();
        }

        // 화면 첫 진입 시에는 저장 프로젝트 유무와 관계없이 DB의 기본 업체/페르소나 정보를 다시 입힌다.
        // 이전 프로젝트 복원 흐름이 기본 사용자/관리자 데이터를 가로막지 않도록 분리한다.
        if (typeof loadDefaultPersonaIntoWorkspace === 'function') {
            await loadDefaultPersonaIntoWorkspace();
        }
        if (typeof window.syncStoryMakerPersonaFromDb === 'function') {
            await window.syncStoryMakerPersonaFromDb(true);
        }
        if (typeof syncProfileSummary === 'function') {
            syncProfileSummary();
        }
        if (typeof updateWpButtonsState === 'function') updateWpButtonsState();
        window.storymakerBootHydrated = true;
    } catch (err) {
        log(`로그인 후 작업공간 복구 실패: ${err.message}`, 'warning');
    } finally {
        window.storymakerHydrating = false;
    }
}
window.hydrateWorkspaceAfterAuth = hydrateWorkspaceAfterAuth;

// 구글 로그인 성공 콜백 핸들러
async function handleGoogleCredential(googleResponse) {
    log('구글 인증 토큰 획득 성공. 백엔드 세션 연결 시도 중...');
    try {
        const response = await fetch('/api/auth/google', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ credential: googleResponse.credential })
        });
        const res = await response.json();
        if (response.ok && res.ok && res.data) {
            await completeAuthentication(res.data, 'Google OTP');
        } else {
            throw new Error(res.message || res.detail || '구글 연동 로그인 실패');
        }
    } catch (err) {
        log(`구글 로그인 실패: ${err.message}`, 'error');
        alert(`구글 연동 로그인에 실패했습니다:\n${err.message}`);
    }
}
window.handleGoogleCredential = handleGoogleCredential;

// 구글 원탭 로그인 SDK 렌더링 초기화
async function initializeGoogleLogin() {
    // ponytail: google login setup left intact; harmless.
    const client = window.google?.accounts?.id;
    if (!client) {
        // SDK 미로드 상태 시 0.4초 후 재시도
        setTimeout(initializeGoogleLogin, 400);
        return;
    }
    
    try {
        client.initialize({
            client_id: "641064106410-abc.apps.googleusercontent.com", // dummy placeholder, WP 호스팅 연계
            callback: handleGoogleCredential,
            auto_select: false,
            cancel_on_tap_outside: true
        });
        
        const loginContainer = document.getElementById("google-login-btn-container");
        if (loginContainer) {
            client.renderButton(loginContainer, {
                theme: "outline",
                size: "large",
                width: 280,
                text: "signup_with"
            });
        }
    } catch (e) {
        console.warn('구글 원탭 연동 준비 중 오류 발생:', e);
    }
}
window.initializeGoogleLogin = initializeGoogleLogin;

// WordPress 로그인 화면 이동 처리
async function handleLogin(e) {
    if (e) e.preventDefault();
    window.location.href = getWordPressAuthUrl('login');
}
window.handleLogin = handleLogin;

// 로그아웃 처리 핸들러
async function handleLogout() {
    try { sessionStorage.setItem('storymaker_explicit_logout', '1'); } catch (e) {}

    // 서버 세션과 HttpOnly 인증 쿠키를 먼저 끊습니다.
    // localStorage만 지우면 쿠키 인증으로 다시 로그인 복구되는 문제가 발생합니다.
    try {
        const tokenForLogout = localStorage.getItem('storymaker_token') || '';
        const headers = tokenForLogout ? { 'Authorization': `Bearer ${tokenForLogout}` } : {};
        await fetch('/api/auth/logout', {
            method: 'POST',
            headers,
            credentials: 'include'
        });
    } catch (e) {
        console.warn('[StoryMaker] 서버 로그아웃 호출 실패, 로컬 세션은 계속 정리합니다.', e);
    }

    localStorage.removeItem('storymaker_token');
    localStorage.removeItem('storymaker_user');
    localStorage.removeItem('storymaker_auth_ok');
    localStorage.removeItem('current_project_id');
    window.currentProjectId = null;
    if (typeof clearCoreInputs === 'function') clearCoreInputs();
    
    // 화면 및 UI 초기화 (요소 존재 여부 예외 방어)
    const userInfoBar = document.getElementById('user-info-bar');
    const adminMenuBtn = document.getElementById('admin-menu-btn');
    const adminModal = document.getElementById('admin-modal');
    
    if (userInfoBar) userInfoBar.style.display = 'none';
    if (adminMenuBtn) adminMenuBtn.style.display = 'none';
    if (adminModal) adminModal.style.display = 'none';
    
    const projSelector = document.getElementById('project-selector');
    if (projSelector) projSelector.innerHTML = '<option value="">-- 저장된 프로젝트 선택 --</option>';
    
    const projTitle = document.getElementById('project-title');
    if (projTitle) projTitle.value = '새 프로젝트';
    
    const rawInput = document.getElementById('chatgpt-raw-input');
    if (rawInput) rawInput.value = '';
    
    const promptBox = document.getElementById('generated-prompt-box');
    if (promptBox) promptBox.innerText = "통합 프롬프트를 생성하면 이곳에 표시됩니다.";
    
    const parsedTabs = document.getElementById('parsed-tabs-container');
    if (parsedTabs) parsedTabs.style.display = 'none';
    
    const snsPlaceholder = document.getElementById('sns-placeholder');
    if (snsPlaceholder) snsPlaceholder.style.display = 'block';
    
    // 저장 상태 초기화
    const statusText = document.getElementById('save-status-text');
    if (statusText) {
        statusText.innerText = '모든 작업 저장됨';
        statusText.style.color = 'var(--muted)';
    }
    
    log('로그아웃 완료. 안전하게 세션을 차단했습니다.', 'warning');
    
    // Reload the page to fully reset state and ensure guest view
    location.reload();
}
window.handleLogout = handleLogout;

// 마이페이지 모달 제어
async function showMyPageModal() {
    const errorDiv = document.getElementById('mypage-error');
    if (errorDiv) errorDiv.style.display = 'none';
    
    const currentPw = document.getElementById('change-current-password');
    if (currentPw) currentPw.value = '';
    const newPw = document.getElementById('change-new-password');
    if (newPw) newPw.value = '';

    // API 키 로드
    const savedKey = localStorage.getItem('api_key') || '';
    const apiKeyInput = document.getElementById('mypage-api-key');
    if (apiKeyInput) apiKeyInput.value = savedKey;

    const modal = document.getElementById('mypage-modal');
    if (modal) modal.style.display = 'none';

    log('마이페이지 정보 조회 중...');
    try {
        const response = await fetchWithAuth('/api/auth/me');
        if (response.ok) {
            const res = await response.json();
            if (res.ok && res.data) {
                const user = res.data;
                const userNm = document.getElementById('my-username');
                if (userNm) userNm.innerText = user.username;
                
                const userRl = document.getElementById('my-role');
                if (userRl) userRl.innerText = user.role === 'admin' ? '관리자 (Admin)' : '일반 사용자 (User)';
                
                // 회원 등급 채우기
                const tierEl = document.getElementById('my-tier');
                if (tierEl) {
                    if (user.role === 'admin') {
                        tierEl.innerText = '관리자 계정';
                        tierEl.style.color = 'var(--accent)';
                    } else {
                        tierEl.innerText = user.tier === 'paid' ? '결제 사용자 (Premium)' : '무료 사용자 (Free)';
                        tierEl.style.color = user.tier === 'paid' ? 'var(--warning)' : 'var(--muted)';
                    }
                }

                const projCount = document.getElementById('my-project-count');
                if (projCount) projCount.innerText = user.project_count || 0;

                // 워드프레스 설정 토글 제어
                const wpCheckbox = document.getElementById('mypage-wp-enabled');
                const wpStatusMsg = document.getElementById('mypage-wp-status-msg');
                const isPremium = user.role === 'admin' || user.tier === 'paid';
                
                if (wpCheckbox) {
                    if (!isPremium) {
                        wpCheckbox.checked = false;
                        wpCheckbox.disabled = true;
                        if (wpStatusMsg) {
                            wpStatusMsg.innerText = '※ 워드프레스 연동 기능은 결제(Premium) 회원 이상만 활성화할 수 있습니다.';
                            wpStatusMsg.style.display = 'block';
                        }
                    } else {
                        wpCheckbox.checked = !!user.wp_enabled;
                        wpCheckbox.disabled = false;
                        if (wpStatusMsg) {
                            wpStatusMsg.style.display = 'none';
                        }
                    }
                }

                // DB 업종 목록과 페르소나 리스트 로딩 및 탭 분기 허용
                if (typeof loadMyPageIndustries === 'function') {
                    await loadMyPageIndustries();
                }
                if (typeof loadMyPersonas === 'function') {
                    await loadMyPersonas();
                }
                switchMyPageTab('persona');
                
                if (typeof window.openMyPageModalUi === 'function') {
                    window.openMyPageModalUi();
                } else if (modal) {
                    modal.style.display = 'flex';
                }
                return true;
            }
        }
    } catch (err) {
        log(`마이페이지 조회 실패: ${err.message}`, 'error');
        return false;
    }
    return false;
}
window.showMyPageModal = showMyPageModal;

function switchMyPageTab(tabName) {
    const personaTab = document.getElementById('mypage-persona-section');
    const settingsTab = document.getElementById('mypage-settings-section');
    const personaBtn = document.getElementById('btn-mypage-tab-persona');
    const settingsBtn = document.getElementById('btn-mypage-tab-settings');
    
    if (!personaTab || !settingsTab || !personaBtn || !settingsBtn) return;
    
    if (tabName === 'persona') {
        personaTab.style.display = 'block';
        settingsTab.style.display = 'none';
        
        personaBtn.classList.add('active');
        personaBtn.style.color = 'var(--text)';
        personaBtn.style.borderBottomColor = 'var(--accent)';
        personaBtn.style.fontWeight = '600';
        
        settingsBtn.classList.remove('active');
        settingsBtn.style.color = 'var(--muted)';
        settingsBtn.style.borderBottomColor = 'transparent';
        settingsBtn.style.fontWeight = '500';
    } else if (tabName === 'settings') {
        personaTab.style.display = 'none';
        settingsTab.style.display = 'flex';
        
        settingsBtn.classList.add('active');
        settingsBtn.style.color = 'var(--text)';
        settingsBtn.style.borderBottomColor = 'var(--accent)';
        settingsBtn.style.fontWeight = '600';
        
        personaBtn.classList.remove('active');
        personaBtn.style.color = 'var(--muted)';
        personaBtn.style.borderBottomColor = 'transparent';
        personaBtn.style.fontWeight = '500';
    }
}
window.switchMyPageTab = switchMyPageTab;

function returnFromMyPage() {
    const modal = document.getElementById('mypage-modal');
    if (modal) modal.style.display = 'none';

    try {
        const url = new URL(window.location.href);
        const action = url.searchParams.get('action');
        const isMyPageRoute = action === 'mypage' || url.pathname.includes('/mypage') || url.hash.toLowerCase().includes('mypage');
        if (isMyPageRoute) {
            url.searchParams.delete('action');
            url.hash = '';
            const cleanUrl = url.pathname + (url.search ? url.search : '');
            window.history.replaceState(null, '', cleanUrl || '/storymaker');
        }
    } catch(e) {}
}
window.returnFromMyPage = returnFromMyPage;

function closeMyPageModal() {
    returnFromMyPage();
}
window.closeMyPageModal = closeMyPageModal;

async function toggleWpEnabled(element) {
    const isChecked = element.checked;
    log(`워드프레스 연동 상태 변경 중... (${isChecked ? '활성화' : '비활성화'})`);
    try {
        const response = await fetchWithAuth('/api/auth/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ wp_enabled: isChecked })
        });
        const res = await response.json();
        if (!response.ok || !res.ok) throw new Error(res.detail || res.message || '설정 저장 실패');
        log('워드프레스 연동 설정이 저장되었습니다.', 'success');
        
        // 로컬 스토리지에 캐시된 유저 정보 갱신
        const userStr = localStorage.getItem('storymaker_user');
        if (userStr) {
            const user = JSON.parse(userStr);
            user.wp_enabled = isChecked;
            localStorage.setItem('storymaker_user', JSON.stringify(user));
        }
        
        // 워크스페이스 내 워드프레스 버튼 상태 업데이트
        updateWpButtonsState();
    } catch (err) {
        log(`워드프레스 설정 변경 실패: ${err.message}`, 'error');
        element.checked = !isChecked; // 상태 롤백
        alert(`설정 변경에 실패했습니다: ${err.message}`);
    }
}
window.toggleWpEnabled = toggleWpEnabled;

function updateWpButtonsState() {
    const userStr = localStorage.getItem('storymaker_user');
    const user = userStr ? JSON.parse(userStr) : null;
    
    const btn1 = document.getElementById('btn-send-wordpress-draft-blog');
    const btn2 = document.getElementById('btn-send-wordpress-draft');
    
    if (!user) return;
    
    const isPremium = user.role === 'admin' || user.tier === 'paid';
    const isWpEnabled = !!user.wp_enabled;
    
    [btn1, btn2].forEach(btn => {
        if (!btn) return;
        if (!isPremium) {
            btn.style.background = '#475569';
            btn.style.borderColor = '#64748b';
            btn.style.opacity = '0.6';
            btn.innerHTML = '🔒 WordPress 초안';
        } else if (!isWpEnabled) {
            btn.style.background = '#475569';
            btn.style.borderColor = '#64748b';
            btn.style.opacity = '0.6';
            btn.innerHTML = 'WordPress (꺼짐)';
        } else {
            btn.style.background = '#0284c7';
            btn.style.borderColor = '#38bdf8';
            btn.style.opacity = '1.0';
            btn.innerHTML = 'WordPress 초안';
        }
    });
}
window.updateWpButtonsState = updateWpButtonsState;

// OpenAI API 키 저장 함수
function saveApiKey() {
    const apiKey = document.getElementById('mypage-api-key').value.trim();
    localStorage.setItem('api_key', apiKey);
    alert('API 키가 저장되었습니다.');
    if (typeof log === 'function') {
        log('[UX] OpenAI API 키를 localStorage에 저장했습니다.');
    }
}
window.saveApiKey = saveApiKey;

// 작업 정보 입력 아코디언 토글 함수
function toggleAccordion() {
    const content = document.getElementById('accordion-content');
    const icon = document.getElementById('accordion-icon');
    if (!content || !icon) return;
    if (content.style.display === 'none') {
        content.style.display = 'block';
        icon.textContent = '▲';
        if (typeof log === 'function') {
            log('[UX] 작업 정보 입력 영역을 펼쳤습니다.');
        }
    } else {
        content.style.display = 'none';
        icon.textContent = '▼';
        if (typeof log === 'function') {
            log('[UX] 작업 정보 입력 영역을 접었습니다.');
        }
    }
}
window.toggleAccordion = toggleAccordion;

// API 키 확인 함수
function checkApiKey() {
    const localKey = localStorage.getItem('api_key') || 
                     localStorage.getItem('openai_api_key') || 
                     localStorage.getItem('storymaker_api_key') || 
                     localStorage.getItem('openai');
    if (localKey && localKey.trim()) {
        return localKey.trim();
    }

    const userStr = localStorage.getItem('storymaker_user');
    if (userStr) {
        try {
            const user = JSON.parse(userStr);
            const userKey = user.api_key || 
                            user.openai_api_key || 
                            user.openai_key || 
                            user.apiKey;
            if (userKey && userKey.trim()) {
                return userKey.trim();
            }
        } catch (e) {}
    }

    if (window.currentUser && (window.currentUser.api_key || window.currentUser.openai_api_key)) {
        return (window.currentUser.api_key || window.currentUser.openai_api_key).trim();
    }

    return null;
}
window.checkApiKey = checkApiKey;

// 비밀번호 변경 처리 핸들러
async function handleChangePassword(e) {
    e.preventDefault();
    const currentPwInput = document.getElementById('change-current-password');
    const newPwInput = document.getElementById('change-new-password');
    const errorDiv = document.getElementById('mypage-error');
    
    if (!currentPwInput || !newPwInput || !errorDiv) return;
    errorDiv.style.display = 'none';

    log('비밀번호 변경 요청 중...');
    try {
        const response = await fetchWithAuth('/api/auth/change-password', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                current_password: currentPwInput.value,
                new_password: newPwInput.value
            })
        });

        const res = await response.json();
        if (response.ok && res.ok) {
            log('비밀번호가 성공적으로 변경되었습니다. 보안을 위해 재로그인을 수행합니다.', 'success');
            showToast('비밀번호 변경 완료. 다시 로그인해 주세요.');
            closeMyPageModal();
            handleLogout();
        } else {
            throw new Error(res.message || res.detail || '비밀번호 변경에 실패했습니다.');
        }
    } catch (err) {
        errorDiv.innerText = err.message;
        errorDiv.style.display = 'block';
        log(`비밀번호 변경 실패: ${err.message}`, 'error');
    }
}
window.handleChangePassword = handleChangePassword;

// 로그인 상태 유지 검증 및 UI 동기화
async function checkLoginStatus() {
    const token = localStorage.getItem('storymaker_token');
    const userInfoBar = document.getElementById('user-info-bar');
    const loggedInUser = document.getElementById('logged-in-user');
    
    if (!token) {
        const explicitLogout = sessionStorage.getItem('storymaker_explicit_logout') === '1';
        if (explicitLogout) {
            sessionStorage.removeItem('storymaker_explicit_logout');
            log('로그아웃 후 이전 StoryMaker 화면으로 돌아왔습니다.', 'warning');
            if (typeof window.snsAiUnifiedRender === 'function') window.snsAiUnifiedRender();
            return false;
        }

        // localStorage가 비어 있어도 HttpOnly storymaker_token 쿠키가 살아 있을 수 있다.
        // 이 경우 바로 WordPress 로그인 화면으로 보내면 정상 로그인 사용자도 입구에서 막힌다.
        try {
            const cookieResponse = await fetch('/api/auth/me', {
                credentials: 'include'
            });
            if (cookieResponse.ok) {
                const cookieRes = await cookieResponse.json();
                if (cookieRes.ok && cookieRes.data) {
                    const user = cookieRes.data;
                    localStorage.setItem('storymaker_user', JSON.stringify(user));
                    localStorage.setItem('storymaker_auth_ok', '1');
                    window.dispatchEvent(new CustomEvent('storymaker-auth-changed'));
                    if (loggedInUser) loggedInUser.innerText = `${user.username} (${user.role})`;
                    if (userInfoBar) userInfoBar.style.display = 'flex';

                    const adminBtn = document.getElementById('admin-menu-btn');
                    if (adminBtn) {
                        adminBtn.style.display = user.role === 'admin' ? 'inline-block' : 'none';
                    }

                    log(`쿠키 인증 승인: [${user.username}] 계정 접속 활성화`, 'success');
                    await hydrateWorkspaceAfterAuth();
                    return true;
                }
            }
        } catch (err) {
            log(`쿠키 인증 확인 실패: ${err.message}`, 'warning');
        }

        const params = new URLSearchParams(window.location.search);
        const tabParam = params.get('tab');
        if (tabParam) {
            window.history.replaceState(null, null, window.location.pathname);
        }
        log("StoryMaker 세션이 없습니다. 게스트 모드로 화면을 엽니다. 계정 기능은 로그인 후 사용할 수 있습니다.", 'warning');
        if (userInfoBar) userInfoBar.style.display = 'none';
        if (loggedInUser) loggedInUser.innerText = '';
        const adminBtn = document.getElementById('admin-menu-btn');
        if (adminBtn) adminBtn.style.display = 'none';
        if (typeof window.snsAiUnifiedRender === 'function') window.snsAiUnifiedRender();
        return false;
    }
    
    try {
        const authHeaders = { 'Authorization': `Bearer ${token}` };
        const response = await fetch('/api/auth/me', {
            headers: authHeaders,
            credentials: 'include'
        });
        
        if (response.ok) {
            const res = await response.json();
            if (res.ok && res.data) {
                const user = res.data;
                localStorage.setItem('storymaker_user', JSON.stringify(user));
                if (loggedInUser) loggedInUser.innerText = `${user.username} (${user.role})`;
                if (userInfoBar) userInfoBar.style.display = 'flex';
                
                const adminBtn = document.getElementById('admin-menu-btn');
                if (adminBtn) {
                    if (user.role === 'admin') {
                        adminBtn.style.display = 'inline-block';
                    } else {
                        adminBtn.style.display = 'none';
                    }
                }
                
                log(`인증 승인: [${user.username}] 계정 접속 활성화`, 'success');
                
                await hydrateWorkspaceAfterAuth();
                return true;
            }
        }
        throw new Error('세션 데이터 복구 실패');
    } catch (err) {
        log(`JWT 인증 확인 실패: ${err.message}. 쿠키 인증으로 복구를 다시 시도합니다.`, 'warning');
        try {
            const cookieResponse = await fetch('/api/auth/me', {
                credentials: 'include'
            });
            if (cookieResponse.ok) {
                const cookieRes = await cookieResponse.json();
                if (cookieRes.ok && cookieRes.data) {
                    const user = cookieRes.data;
                    localStorage.setItem('storymaker_user', JSON.stringify(user));
                    localStorage.setItem('storymaker_auth_ok', '1');
                    window.dispatchEvent(new CustomEvent('storymaker-auth-changed'));
                    if (loggedInUser) loggedInUser.innerText = `${user.username} (${user.role})`;
                    if (userInfoBar) userInfoBar.style.display = 'flex';
                    const adminBtn = document.getElementById('admin-menu-btn');
                    if (adminBtn) adminBtn.style.display = user.role === 'admin' ? 'inline-block' : 'none';
                    log(`쿠키 인증으로 세션 복구 완료: [${user.username}]`, 'success');
                    await hydrateWorkspaceAfterAuth();
                    return true;
                }
            }
        } catch (cookieErr) {
            log(`쿠키 인증 복구 실패: ${cookieErr.message}`, 'warning');
        }
        return false;
    }
}
window.checkLoginStatus = checkLoginStatus;
