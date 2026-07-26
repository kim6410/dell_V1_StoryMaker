// StoryMaker 프론트엔드 AI Worker 폴링 및 헬스 로그 수집 엔진 (app_generator_worker.js)

// 백엔드로 AI Worker 및 프론트 상태 헬스 로그를 전송하는 헬퍼 함수
async function sendHealthLog(stage, data = {}) {
    try {
        await fetch('/api/test/worker-log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                level: 'INFO',
                message: `[StoryMaker Gemini 1.4.10] [HEALTH] ${stage} ${JSON.stringify(data)}`,
                timestamp: new Date().toISOString()
            })
        });
    } catch (e) {
        console.error('Failed to send health log:', e);
    }
}
window.sendHealthLog = sendHealthLog;

function looksLikeStoryMakerPrompt(text) {
    const value = String(text || '');
    const promptMarkers = [
        '## 역할',
        '## StoryMaker 생성 환경',
        '## 반드시 생성할 결과물',
        '## 최상위 출력 규칙',
        '## 모바일 가독성 규칙',
        '콘텐츠 통합 패키지 생성 프롬프트'
    ];
    const promptScore = promptMarkers.filter(marker => value.includes(marker)).length;
    const hasOutputBlocks = /\[BLOCK:(BLOG_TITLES|BLOG_POST|NAVER_PLACE_NEWS|GOOGLE_BUSINESS_POST|INSTAGRAM_POST|PODCAST_50|PODCAST_80)\]/.test(value);
    return promptScore >= 2 && !hasOutputBlocks;
}
window.looksLikeStoryMakerPrompt = looksLikeStoryMakerPrompt;

function looksLikeStoryMakerResult(text) {
    const value = String(text || '').trim();
    if (!value || looksLikeStoryMakerPrompt(value)) return false;
    const required = [
        'BLOG_TITLES',
        'BLOG_POST',
        'NAVER_PLACE_NEWS',
        'GOOGLE_BUSINESS_POST',
        'INSTAGRAM_POST'
    ];
    const count = required.filter(name => value.includes(`[BLOCK:${name}]`)).length;
    return count >= 3;
}
window.looksLikeStoryMakerResult = looksLikeStoryMakerResult;

// Gemini 비동기 생성 결과를 수령하기 위해 백엔드 패키지 API를 롱 폴링하는 함수 (타임아웃 10분)
async function waitForGeminiResult(jobId, timeoutMs = 600000) {
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
        const response = await fetchWithAuth('/api/test/result-package/latest');
        const res = await response.json();
        if (!response.ok || !res.ok) throw new Error(res.message || res.detail || 'Gemini 결과 조회 실패');

        if (res.job_id === jobId && res.status === 'failed') {
            throw new Error(res.error || 'Gemini Worker 처리 실패');
        }

        if (res.job_id === jobId && res.status === 'completed' && res.result_text) {
            if (!looksLikeStoryMakerResult(res.result_text)) {
                throw new Error('Gemini Worker 결과가 콘텐츠 BLOCK 형식이 아닙니다. 프롬프트 원문 유입을 차단했습니다.');
            }
            return res.result_text;
        }

        await new Promise(resolve => setTimeout(resolve, 3000));
    }
    throw new Error('Gemini Worker 결과 대기 시간이 초과되었습니다.');
}
window.waitForGeminiResult = waitForGeminiResult;
