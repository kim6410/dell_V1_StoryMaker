// StoryMaker 프론트엔드 AI 자동 생성 상태 계기판 및 UI 제어 유틸 (app_generator_progress.js)

// 생성 중 상태 표시 및 스피너 테마 제어 함수
function setAIGenerationStatus(message, state = 'active') {
    const bar = document.getElementById('ai-generation-status');
    const text = document.getElementById('ai-generation-status-text');
    if (!bar || !text) return;
    text.innerText = message;
    bar.classList.remove('active', 'done', 'error');
    bar.classList.add('active');
    if (state === 'done') bar.classList.add('done');
    if (state === 'error') bar.classList.add('error');
}
window.setAIGenerationStatus = setAIGenerationStatus;

// 스피너 표시 숨김 디레이어 함수
function hideAIGenerationStatus(delayMs = 2600) {
    const bar = document.getElementById('ai-generation-status');
    if (!bar) return;
    setTimeout(() => {
        bar.classList.remove('active', 'done', 'error');
    }, delayMs);
}
window.hideAIGenerationStatus = hideAIGenerationStatus;

// 결과 탭 영역 부드러운 스크롤 이동 헬퍼
function scrollToSnsResultArea() {
    const target = document.getElementById('tabs-header-bar')
        || document.getElementById('parsed-tabs-container')
        || document.getElementById('workspace-sns');
    if (!target) return;
    setTimeout(() => {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 120);
}
window.scrollToSnsResultArea = scrollToSnsResultArea;

// 생성 버튼 비활성화 및 로딩 문구 설정 공통 보조 헬퍼
function handleAiGenerationStart(btn) {
    if (!btn) return;
    btn.disabled = true;
    btn.innerText = 'AI 결과 대기 중...';
    btn.style.opacity = '0.7';
}
window.handleAiGenerationStart = handleAiGenerationStart;

// 생성 성공 시 버튼 복구 공통 보조 헬퍼
function handleAiGenerationSuccess(btn) {
    if (!btn) return;
    btn.disabled = false;
    btn.innerText = 'AI 자동생성';
    btn.style.opacity = '1';
}
window.handleAiGenerationSuccess = handleAiGenerationSuccess;

// 에러 발생 시 UI 복구 및 에러 스피너 갱신 보조 헬퍼
function handleAiGenerationError(btn, errorMessage) {
    setAIGenerationStatus(`에러 발생: ${errorMessage}`, 'error');
    if (btn) {
        btn.disabled = false;
        btn.innerText = 'AI 자동생성';
        btn.style.opacity = '1';
    }
    hideAIGenerationStatus(4500);
}
window.handleAiGenerationError = handleAiGenerationError;
