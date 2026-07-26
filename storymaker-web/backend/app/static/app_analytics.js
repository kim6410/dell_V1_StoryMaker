// StoryMaker 프론트엔드 AI Lab 분석기 연동 모듈 (app_analytics.js)

// AI Lab 상세 분석 콘솔 및 파이프라인 지표 렌더러
function updateAiLabConsole(res) {
    const data = res.data || res;
    const pm = data.pipeline_metrics || {};
    const pipelineEl = document.getElementById('admin-pipeline-console');
    if (pipelineEl) {
        const steps = [
            ['검색', pm.scraped],
            ['블로그', pm.blog],
            ['광고제외', pm.ad_removed],
            ['중복제거', pm.duplicate_removed],
            ['상위노출', pm.organic_top5],
            ['최종추천', pm.final_recommended]
        ];
        pipelineEl.innerHTML = steps.map(([name, val]) => `
            <div style="text-align:center; padding:8px; background:rgba(0,0,0,0.2); border:1px solid var(--border); border-radius:4px;">
                <div style="font-size:10px; color:var(--text-muted);">${name}</div>
                <div style="font-size:14px; font-weight:700; color:${val ? 'var(--success)' : 'var(--text-muted)'}; margin-top:2px;">${val ? 'PASS' : 'SKIP'}</div>
            </div>
        `).join('');
    }

    const duplicates = data.duplicate_details || [];
    const dupEl = document.getElementById('admin-duplicate-console');
    if (dupEl) {
        if (duplicates.length > 0) {
            dupEl.innerHTML = duplicates.map(dup => `
                <div style="font-size:12px; padding:6px; border-bottom:1px solid rgba(255,255,255,0.05); color:var(--danger);">
                    [중복검출] ${dup.title} (유사도: ${dup.similarity_score}%)
                </div>
            `).join('');
        } else {
            dupEl.innerHTML = '<div style="font-size:12px; color:var(--text-muted); padding:10px;">중복된 글감이 발견되지 않았습니다 (통과)</div>';
        }
    }

    // Load sub console metrics
    if (window.currentViewMode === 'admin') {
        loadPatternKnowledgeConsole();
        loadContentPerformanceConsole();
        loadAiBrainConsole();
    }
}
window.updateAiLabConsole = updateAiLabConsole;

async function loadAdminPromptPreview(keyword) {
    const preEl = document.getElementById('lab-prompt-preview');
    if (!preEl) return;
    preEl.innerText = '프롬프트 미리보기를 생성 중...';
    try {
        const response = await fetchWithAuth(`/api/content-ideas/prompt-preview?keyword=${encodeURIComponent(keyword)}`);
        const res = await response.json();
        if (response.ok && res.ok && res.data) {
            preEl.innerText = res.data.prompt || '(비어 있음)';
        } else {
            throw new Error(res.message || '데이터 구조 오류');
        }
    } catch (err) {
        preEl.innerText = `로딩 실패: ${err.message}`;
    }
}
window.loadAdminPromptPreview = loadAdminPromptPreview;

// 1. Pattern Engine UI 제어 및 API 연동
function setPatternPanel(metrics) {
    const el = document.getElementById('pattern-metrics-summary');
    if (!el) return;
    el.innerHTML = `
        <li>패턴 지식 베이스 키워드 수: <strong>${metrics.keyword_count || 0}개</strong></li>
        <li>최종 갱신 시각: <strong>${metrics.updated_at || '-'}</strong></li>
    `;
}
window.setPatternPanel = setPatternPanel;

async function patternApi(endpoint, options = {}) {
    const response = await fetchWithAuth(`/api/pattern-engine${endpoint}`, options);
    const res = await response.json();
    if (!response.ok || !res.ok) throw new Error(res.detail || res.message || 'Pattern API 에러');
    return res.data || {};
}
window.patternApi = patternApi;

async function loadPatternKnowledgeConsole() {
    const patternConsole = document.getElementById('lab-pattern-console');
    if (!patternConsole) return;
    patternConsole.innerHTML = '패턴 지식 베이스를 읽어오는 중...';
    try {
        const data = await patternApi('/metrics');
        setPatternPanel(data);
        
        const list = await patternApi('/keywords');
        if (list && list.length > 0) {
            patternConsole.innerHTML = list.map(item => `
                <div style="font-size:12px; padding:6px; border-bottom:1px solid rgba(255,255,255,0.05); display:flex; justify-content:space-between;">
                    <span>[${item.type}] <strong>${item.keyword}</strong></span>
                    <span style="color:var(--focus);">가중치: ${item.weight}</span>
                </div>
            `).join('');
        } else {
            patternConsole.innerHTML = '<div style="font-size:12px; color:var(--text-muted); padding:10px;">학습된 마케팅 키워드 패턴이 없습니다.</div>';
        }
    } catch (err) {
        patternConsole.innerHTML = `<div style="font-size:12px; color:var(--danger); padding:10px;">${err.message}</div>`;
    }
}
window.loadPatternKnowledgeConsole = loadPatternKnowledgeConsole;

async function savePatternLearningTarget() {
    const keyword = document.getElementById('pattern-learn-keyword')?.value.trim();
    const type = document.getElementById('pattern-learn-type')?.value;
    const weight = Number(document.getElementById('pattern-learn-weight')?.value || 1.0);
    
    if (!keyword) {
        alert('패턴 학습 키워드를 입력해 주세요.');
        return;
    }
    
    try {
        await patternApi('/keywords', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword, type, weight })
        });
        if (typeof showIdeaStatusMessage === 'function') {
            showIdeaStatusMessage(`[패턴 저장] '${keyword}' 패턴 키워드를 추가했습니다.`);
        }
        await loadPatternKnowledgeConsole();
        document.getElementById('pattern-learn-keyword').value = '';
    } catch (err) {
        if (typeof showIdeaStatusMessage === 'function') {
            showIdeaStatusMessage(`패턴 저장 실패: ${err.message}`);
        }
    }
}
window.savePatternLearningTarget = savePatternLearningTarget;

async function runPatternLearningOnce() {
    try {
        await patternApi('/learn-once', { method: 'POST' });
        await loadPatternKnowledgeConsole();
        if (typeof showIdeaStatusMessage === 'function') {
            showIdeaStatusMessage('패턴 지식 베이스 강제 학습을 완료했습니다.');
        }
    } catch (err) {
        if (typeof showIdeaStatusMessage === 'function') {
            showIdeaStatusMessage(`패턴 학습 실패: ${err.message}`);
        }
    }
}
window.runPatternLearningOnce = runPatternLearningOnce;

async function discoverPatternKeywords() {
    try {
        const list = await patternApi('/discover');
        if (typeof showIdeaStatusMessage === 'function') {
            showIdeaStatusMessage(`[패턴 발굴] 신규 후보 키워드 ${list.length}개를 탐색했습니다.`);
        }
        await loadPatternKnowledgeConsole();
    } catch (err) {
        if (typeof showIdeaStatusMessage === 'function') {
            showIdeaStatusMessage(`패턴 발굴 실패: ${err.message}`);
        }
    }
}
window.discoverPatternKeywords = discoverPatternKeywords;


// 2. Performance Engine UI 제어 및 API 연동
function setPerfText(metrics) {
    const el = document.getElementById('performance-summary');
    if (!el) return;
    el.innerHTML = `
        <li>마케팅 수집 샘플 모수: <strong>${metrics.total_samples || 0}건</strong></li>
        <li>평균 상위 노출 스코어: <strong>${metrics.avg_score?.toFixed(1) || 0}점</strong></li>
        <li>CTA 전환 최적화 스코어: <strong>${metrics.avg_cta?.toFixed(1) || 0}점</strong></li>
    `;
}
window.setPerfText = setPerfText;

async function performanceApi(endpoint, options = {}) {
    const response = await fetchWithAuth(`/api/performance-engine${endpoint}`, options);
    const res = await response.json();
    if (!response.ok || !res.ok) throw new Error(res.detail || res.message || 'Performance API 에러');
    return res.data || {};
}
window.performanceApi = performanceApi;

async function loadContentPerformanceConsole() {
    const perfConsole = document.getElementById('lab-performance-console');
    if (!perfConsole) return;
    perfConsole.innerHTML = '샘플링 성과 데이터를 읽어오는 중...';
    try {
        const data = await performanceApi('/metrics');
        setPerfText(data);
        
        const list = await performanceApi('/samples');
        if (list && list.length > 0) {
            perfConsole.innerHTML = list.map(item => `
                <div style="font-size:12px; padding:6px; border-bottom:1px solid rgba(255,255,255,0.05); display:flex; justify-content:space-between;">
                    <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:70%;">[랭킹 #${item.rank}] ${item.title}</span>
                    <span style="color:var(--success); font-weight:700;">Score: ${item.performance_score}점</span>
                </div>
            `).join('');
        } else {
            perfConsole.innerHTML = '<div style="font-size:12px; color:var(--text-muted); padding:10px;">성능 샘플링 성과 지표가 비어 있습니다.</div>';
        }
    } catch (err) {
        perfConsole.innerHTML = `<div style="font-size:12px; color:var(--danger); padding:10px;">${err.message}</div>`;
    }
}
window.loadContentPerformanceConsole = loadContentPerformanceConsole;

async function scoreContentPerformance() {
    const text = document.getElementById('perf-target-text')?.value.trim() || '';
    if (!text) {
        alert('채점할 본문을 입력해 주세요.');
        return;
    }
    
    try {
        const result = await performanceApi('/score', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        if (typeof showIdeaStatusMessage === 'function') {
            showIdeaStatusMessage(`[본문 채점 완료] 상위노출 스코어: ${result.performance_score}점 / CTA: ${result.cta_score}점`);
        }
        await loadContentPerformanceConsole();
    } catch (err) {
        if (typeof showIdeaStatusMessage === 'function') {
            showIdeaStatusMessage(`성능 채점 실패: ${err.message}`);
        }
    }
}
window.scoreContentPerformance = scoreContentPerformance;

async function runPerformanceAnalysisOnce() {
    try {
        await performanceApi('/analyze-once', { method: 'POST' });
        await loadContentPerformanceConsole();
        if (typeof showIdeaStatusMessage === 'function') {
            showIdeaStatusMessage('성능 분석 알고리즘 업데이트를 완료했습니다.');
        }
    } catch (err) {
        if (typeof showIdeaStatusMessage === 'function') {
            showIdeaStatusMessage(`성능 분석 업데이트 실패: ${err.message}`);
        }
    }
}
window.runPerformanceAnalysisOnce = runPerformanceAnalysisOnce;


// 3. AI Brain Engine UI 제어 및 API 연동
function setBrainText(metrics) {
    const el = document.getElementById('brain-metrics-summary');
    if (!el) return;
    el.innerHTML = `
        <li>AI 지식 컨텍스트 파일 수: <strong>${metrics.context_files || 0}개</strong></li>
        <li>연관 키워드 매칭 가중치: <strong>${metrics.concept_weight?.toFixed(2) || 1.0}</strong></li>
    `;
}
window.setBrainText = setBrainText;

async function brainApi(endpoint, options = {}) {
    const response = await fetchWithAuth(`/api/ai-brain${endpoint}`, options);
    const res = await response.json();
    if (!response.ok || !res.ok) throw new Error(res.detail || res.message || 'AI Brain API 에러');
    return res.data || {};
}
window.brainApi = brainApi;

async function loadAiBrainConsole() {
    const brainConsole = document.getElementById('lab-brain-console');
    if (!brainConsole) return;
    brainConsole.innerHTML = '지식 컨텍스트 데이터를 분석하는 중...';
    try {
        const data = await brainApi('/metrics');
        setBrainText(data);
        
        const list = await brainApi('/contexts');
        if (list && list.length > 0) {
            brainConsole.innerHTML = list.map(item => `
                <div style="font-size:12px; padding:6px; border-bottom:1px solid rgba(255,255,255,0.05); display:flex; justify-content:space-between;">
                    <span>[${item.domain}] <strong>${item.filename}</strong></span>
                    <span style="color:var(--warning);">개념 일치도: ${item.match_score}%</span>
                </div>
            `).join('');
        } else {
            brainConsole.innerHTML = '<div style="font-size:12px; color:var(--text-muted); padding:10px;">등록된 지식 파일 컨텍스트가 없습니다.</div>';
        }
    } catch (err) {
        brainConsole.innerHTML = `<div style="font-size:12px; color:var(--danger); padding:10px;">${err.message}</div>`;
    }
}
window.loadAiBrainConsole = loadAiBrainConsole;

async function scoreAiBrainPrompt() {
    const promptText = document.getElementById('brain-target-prompt')?.value.trim() || '';
    if (!promptText) {
        alert('검사할 프롬프트를 입력해 주세요.');
        return;
    }
    
    try {
        const result = await brainApi('/score', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: promptText })
        });
        if (typeof showIdeaStatusMessage === 'function') {
            showIdeaStatusMessage(`AI Brain Overall Score ${result.overall_score}/100`);
        }
        await loadAiBrainConsole();
    } catch (err) {
        if (typeof showIdeaStatusMessage === 'function') {
            showIdeaStatusMessage(`AI Brain 점수 계산 실패: ${err.message}`);
        }
    }
}
window.scoreAiBrainPrompt = scoreAiBrainPrompt;

async function runAiBrainOnce() {
    try {
        await brainApi('/run-once', { method: 'POST' });
        await loadAiBrainConsole();
        if (typeof showIdeaStatusMessage === 'function') {
            showIdeaStatusMessage('AI Brain 분석을 실행했습니다.');
        }
    } catch (err) {
        if (typeof showIdeaStatusMessage === 'function') {
            showIdeaStatusMessage(`AI Brain 실행 실패: ${err.message}`);
        }
    }
}
window.runAiBrainOnce = runAiBrainOnce;
