// StoryMaker 프론트엔드 공통 코어 유틸 및 전역 상태 (app_core.js)
const APP_VERSION = "1.2.2";

// 전역 상태 변수 (window 객체에 바인딩하여 다른 모듈에서 손쉽게 연동되도록 보장)
window.currentProjectId = null;
window.autosaveTimer = null;
window.isSaving = false;
window.lastParsedBlocks = {};
window.autosaveListenersReady = false;
window.myPersonas = [];
window.pendingAfterLoginAction = null;
window.storymakerBootHydrated = false;
window.storymakerProjectListLoaded = false;

// 공통 유틸 및 헬퍼 함수
function isAdminUser() {
    const rawUser = localStorage.getItem('storymaker_user');
    if (!rawUser) return false;
    try {
        const user = JSON.parse(rawUser);
        return user && user.role === 'admin';
    } catch (e) {
        return false;
    }
}
window.isAdminUser = isAdminUser;

function syncPromptVisibility() {
    const box = document.getElementById('generated-prompt-box');
    const area = document.getElementById('prompt-preview-area');
    const summary = document.getElementById('prompt-ready-summary');
    const count = document.getElementById('prompt-char-count');
    const workspace = document.getElementById('workspace-prompt');
    if (!box || !area || !summary) return;
    const text = (box.innerText || '').trim();
    const ready = !!text && !text.includes('통합 프롬프트를 생성하면');
    const charText = Number(text.length || 0).toLocaleString('ko-KR');
    if (count) count.textContent = charText;
    summary.style.display = 'flex';
    summary.style.justifyContent = 'space-between';
    summary.style.alignItems = 'center';
    summary.style.gap = '18px';
    summary.style.padding = '18px 20px';
    summary.style.borderRadius = '14px';
    summary.style.border = '1px solid rgba(34,211,238,0.32)';
    summary.style.background = ready ? 'rgba(0,230,118,0.08)' : 'rgba(255,179,0,0.08)';
    summary.innerHTML = '<div style="display:flex;align-items:center;gap:12px;"><span style="width:10px;height:10px;border-radius:50%;background:' + (ready ? '#00e676' : '#ffb300') + ';box-shadow:0 0 12px ' + (ready ? 'rgba(0,230,118,0.9)' : 'rgba(255,179,0,0.9)') + ';display:inline-block;"></span><strong>' + (ready ? '글쓰기 준비 완료' : '글쓰기 준비중') + '</strong></div><div style="color:#9AA7C0;font-size:13px;font-weight:800;white-space:nowrap;">전체 <b style="color:#fff;font-size:14px;margin-left:6px;">' + charText + '</b>자</div>';
    const admin = isAdminUser();
    area.style.display = admin ? '' : 'none';
    summary.style.display = admin ? 'none' : 'flex';
    if (workspace) {
        const btn = workspace.querySelector('.accordion-copy-btn');
        if (btn) btn.style.display = admin ? '' : 'none';
    }
}
window.syncPromptVisibility = syncPromptVisibility;

function getCurrentHelpUserName() {
    try {
        const user = JSON.parse(localStorage.getItem('storymaker_user') || '{}');
        return user.username || user.name || user.email || '사용자';
    } catch (e) {
        return '사용자';
    }
}
window.getCurrentHelpUserName = getCurrentHelpUserName;

function resolveHelpContent(text) {
    return String(text || '').replaceAll('{{로그인 사용자}}', getCurrentHelpUserName());
}
window.resolveHelpContent = resolveHelpContent;

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));
}
window.escapeHtml = escapeHtml;

function escapeAttr(value) {
    return escapeHtml(value).replace(/`/g, '&#096;');
}
window.escapeAttr = escapeAttr;

// 현재 로컬 타임스탬프 반환 헬퍼
function getLogTime() {
    const now = new Date();
    return now.toTimeString().split(' ')[0];
}
window.getLogTime = getLogTime;

// 콘솔 창에 실시간 로그 인쇄
function log(message, type = 'info') {
    const consoleBox = document.getElementById('console-logs-box');
    if (!consoleBox) {
        console.warn(`[Log System Off] [${type}] ${message}`);
        return;
    }
    const logItem = document.createElement('div');
    logItem.className = 'log-item';
    logItem.innerHTML = `
        <span class="log-time">[${getLogTime()}]</span>
        <span class="log-text ${type}">${message}</span>
    `;
    consoleBox.appendChild(logItem);
    consoleBox.scrollTop = consoleBox.scrollHeight;
}
window.log = log;

// JWT 인증 헤더를 자동으로 적용하는 안전한 fetch 래퍼 함수
async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem('storymaker_token');
    if (!options.headers) {
        options.headers = {};
    }
    if (token) {
        options.headers['Authorization'] = `Bearer ${token}`;
    }
    
    try {
        options.credentials = 'include';
        const response = await fetch(url, options);
        if (response.status === 401) {
            // 일시적인 인증 확인 실패가 전체 로그아웃으로 번지지 않도록 localStorage는 절대 지우지 않는다.
            // 명시적 로그아웃 버튼을 눌렀을 때만 handleLogout()이 토큰과 사용자 정보를 삭제한다.
            log('인증 확인이 필요합니다. 잠시 후 다시 시도하거나 계속 실패하면 다시 로그인해 주세요.', 'warning');
            try {
                window.dispatchEvent(new CustomEvent('storymaker-auth-check-needed', { detail: { url } }));
            } catch (e) {}
            throw new Error('인증 확인이 필요합니다.');
        }
        return response;
    } catch (err) {
        throw err;
    }
}
window.fetchWithAuth = fetchWithAuth;

// 안전한 이벤트 리스너 연결 헬퍼 함수 (Null 방어)
function safeAddEventListener(target, eventName, handler, label) {
    const el = typeof target === 'string'
        ? document.getElementById(target)
        : target;

    if (!el) {
        console.warn('[StoryMaker] 이벤트 연결 실패:', label || target);
        return false;
    }

    el.addEventListener(eventName, handler);
    return true;
}
window.safeAddEventListener = safeAddEventListener;

// 입력 폼들의 변경 이벤트를 감지하여 자동 저장 리스너 등록
function setupAutosaveListeners() {
    if (window.autosaveListenersReady) return;
    const inputs = [
        'project-title', 'company', 'phone_number', 'keywords', 'persona', 
        'base_content', 'reference_text', 'style', 'ai_preset'
    ];
    
    inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', triggerAutosave);
            el.addEventListener('change', triggerAutosave); // typos fixed, but wait: index.html has 'triggerAutosave'
        }
    });

    // AI 원본 입력 감지 리스너
    const rawInputEl = document.getElementById('chatgpt-raw-input');
    if (rawInputEl) {
        rawInputEl.addEventListener('input', onAiResultInput);
        rawInputEl.addEventListener('paste', () => {
            setTimeout(onAiResultInput, 0);
        });
    }

    window.autosaveListenersReady = true;
}
window.setupAutosaveListeners = setupAutosaveListeners;
