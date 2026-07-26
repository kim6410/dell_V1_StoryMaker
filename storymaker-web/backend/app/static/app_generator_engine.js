// StoryMaker 프론트엔드 AI 자동 생성 오케스트레이터 및 프롬프트 빌더 (app_generator_engine.js)

function makeStoryMakerGeminiJobId() {
    const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14);
    return `storymaker_main_${stamp}`;
}
window.makeStoryMakerGeminiJobId = makeStoryMakerGeminiJobId;

function formatPromptForWorker(prompt) {
    let value = String(prompt || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
    if (!value) return '';

    const sectionTitles = [
        '역할', 'StoryMaker 생성 환경', 'StoryMaker 생활 배경 엔진', '콘텐츠 감성',
        '오늘의 날짜와 생활 맥락', '현재 시간대와 생활 흐름', '오늘의 현장 날씨',
        '최근 일주일 날씨 흐름', '지역 정보', '업종별 작성 흐름', 'SEO 강도',
        '브랜드 톤', '최우선 반영 규칙', '작업 목표', '반드시 생성할 결과물',
        '최상위 출력 규칙', '모바일 가독성 규칙', '공통 작성 규칙', '블로그 규칙',
        '플레이스 규칙', '구글 규칙', '인스타그램 규칙', '당근마켓 규칙',
        '카드뉴스 규칙', '팟캐스트 규칙', '업체 정보', '입력 자료', '최종 점검 규칙', '중요'
    ];
    const subTitles = [
        '사람다운 문체', '굵은 표시 규칙', '전화번호 규칙', '업체명', '업체 페르소나',
        '기초내용 입력', '참고자료', '핵심 키워드', '[AI Brain Recommendation Summary]', '[압축 참고자료]'
    ];

    value = value.replace(/#+\s*$/gm, '');
    value = value.replace(/```content/g, '\n\n```content\n');
    value = value.replace(/\s*```\s*$/g, '\n```');

    sectionTitles.forEach(title => {
        const escaped = title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        value = value.replace(new RegExp('\\s*##\\s*' + escaped + '\\s*', 'g'), '\n\n## ' + title + '\n\n');
    });
    subTitles.forEach(title => {
        const escaped = title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        value = value.replace(new RegExp('\\s*###?\\s*' + escaped + '\\s*', 'g'), '\n\n### ' + title + '\n\n');
    });

    value = value.replace(/\s*(\[BLOCK:[A-Z0-9_]+\])\s*/g, '\n\n$1\n');
    value = value.replace(/([가-힣A-Za-z0-9).])(-\s+)/g, '$1\n$2');
    value = value.replace(/(작성 원칙|작성 참고|주의|전체 원칙|예시)(-\s+)/g, '$1\n$2');
    value = value.replace(/(BLOG_POST, CARROT_POST|NAVER_PLACE_NEWS, GOOGLE_BUSINESS_POST|INSTAGRAM_POST|CAROUSEL_7|PODCAST_50, PODCAST_80)(-\s+)/g, '$1\n$2');
    value = value.replace(/(대표 지역|우선 활용 지역|생활권 예시|입력자료와 페르소나에서 감지된 지역 후보)([^\n])/g, '$1\n$2');
    value = value.replace(/(업종:|업종 분류:|작성 흐름:|핵심 포인트:|키워드 힌트:|문체 힌트:|피해야 할 표현:)/g, '\n$1');
    value = value.replace(/\n{3,}/g, '\n\n');
    return value.split('\n').map(line => line.trimEnd()).join('\n').trim() + '\n';
}
window.formatPromptForWorker = formatPromptForWorker;

async function saveGeminiPromptSnapshot(prompt, jobId) {
    const formattedPrompt = formatPromptForWorker(prompt);
    const response = await fetchWithAuth('/api/test/prompt-snapshot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            generated_prompt: formattedPrompt,
            project_title: document.getElementById('project-title')?.value || '새 프로젝트',
            payload: { source: 'storymaker-main', job_id: jobId }
        })
    });
    const res = await response.json();
    if (!response.ok || !res.ok) throw new Error(res.message || res.detail || '프롬프트 저장 실패');
    return res.data || {};
}
window.saveGeminiPromptSnapshot = saveGeminiPromptSnapshot;

// [자동 생성] 기본 경로: Gemini Worker pending job. OpenAI 직접 호출은 Legacy 함수로만 유지한다.
async function generateAIContentAutomatically(btn = null) {
    btn = btn || document.querySelector('button[onclick*="generateAIContentAutomatically"]');
    const promptBox = document.getElementById('generated-prompt-box');
    const prompt = (promptBox?.innerText || '').trim();

    if (!prompt || prompt === '통합 프롬프트를 생성하면 이곳에 표시됩니다.') {
        alert('통합 프롬프트를 먼저 만들어 주세요.');
        return;
    }

    const jobId = makeStoryMakerGeminiJobId();
    // V1 PC 작업 ID를 생성 즉시 MP4 저장 브리지까지 명시적으로 전달한다.
    window.__STORYMAKER_V1_CURRENT_JOB_ID__ = jobId;
    window.__STORYMAKER_V1_CURRENT_PC_JOB_ID__ = jobId;
    document.documentElement.setAttribute('data-v1-job-id', jobId);
    try {
        sessionStorage.setItem('v1_active_pc_job_id', jobId);
    } catch (_) {}
    window.dispatchEvent(new CustomEvent('storymaker:v1-current-job', {
        detail: { job_id: jobId, jobId }
    }));
    if (typeof setAIGenerationStatus === 'function') {
        setAIGenerationStatus('자동생성을 시작합니다. 프롬프트를 준비하는 중입니다.');
    }
    
    try {
        if (btn) {
            btn.disabled = true;
            btn.innerText = 'AI 결과 대기 중...';
        }

        const promptSnapshot = await saveGeminiPromptSnapshot(prompt, jobId);
        const triggerResponse = await fetchWithAuth('/api/test/trigger-start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                job_id: jobId,
                project_title: document.getElementById('project-title')?.value || '새 프로젝트',
                action: 'GENERATE_GEMINI',
                prompt_path: promptSnapshot.prompt_for_chatgpt
            })
        });
        const triggerRes = await triggerResponse.json();
        if (!triggerResponse.ok || !triggerRes.ok) throw new Error(triggerRes.message || triggerRes.detail || 'Gemini 작업 생성 실패');

        if (typeof setAIGenerationStatus === 'function') {
            setAIGenerationStatus('Gemini Worker가 생성 요청을 받았습니다. 결과를 기다리는 중입니다.');
        }
        log(`Gemini Worker pending job 생성: ${jobId}`, 'success');
        if (typeof toggleAccordionSection === 'function') {
            toggleAccordionSection('ai', true);
        }

        if (typeof setAIGenerationStatus === 'function') {
            setAIGenerationStatus('AI Worker가 본문을 작성하고 있습니다. 잠시만 기다려 주세요.');
        }
        
        // window 또는 글로벌 스코프에 보존된 waitForGeminiResult 호출
        const resultText = await waitForGeminiResult(jobId);
        if (typeof looksLikeStoryMakerResult === 'function' && !looksLikeStoryMakerResult(resultText)) {
            throw new Error('AI 결과가 SNS 콘텐츠 BLOCK 형식이 아니어서 입력칸 반영을 중단했습니다.');
        }
        const textarea = document.getElementById('chatgpt-raw-input');
        if (textarea) {
            textarea.value = resultText;
        }
        if (typeof onAiResultInput === 'function') {
            onAiResultInput();
        }
        if (typeof triggerAutosave === 'function') {
            triggerAutosave();
        }

        if (typeof setAIGenerationStatus === 'function') {
            setAIGenerationStatus('결과 반영 완료. SNS별 분리를 실행합니다.', 'done');
        }
        if (typeof parseChatGPTResult === 'function') {
            await parseChatGPTResult();
        }
        if (typeof scrollToSnsResultArea === 'function') {
            scrollToSnsResultArea();
        }
        if (typeof hideAIGenerationStatus === 'function') {
            hideAIGenerationStatus();
        }
    } catch (err) {
        log(`Gemini 자동 생성 에러: ${err.message}`, 'error');
        alert(`AI 결과 생성 중 오류가 발생했습니다:\n${err.message}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = 'AI 자동생성';
        }
    }
}
window.generateAIContentAutomatically = generateAIContentAutomatically;

// Legacy DOM 호출 호환용
function handleAutoGenerate() {
    return generateAIContentAutomatically();
}
window.handleAutoGenerate = handleAutoGenerate;

// 프롬프트 생성 전 입력값 검증 헬퍼 함수들
function isReferenceEmptyForPrompt() {
    const ref = (document.getElementById('reference_text')?.value || '').trim();
    const url = (document.getElementById('naver-blog-url')?.value || '').trim();
    return (!url && (!ref || ref === '없음'));
}
window.isReferenceEmptyForPrompt = isReferenceEmptyForPrompt;

function getPersonaFieldValue(item) {
    const workspaceValue = (document.getElementById(item.workspaceId)?.value || '').trim();
    if (workspaceValue) return workspaceValue;

    const mypageValue = (document.getElementById(item.mypageId)?.value || '').trim();
    if (mypageValue) return mypageValue;

    const defaultPersona = (window.myPersonas || []).find(persona => persona.is_default) || (window.myPersonas || [])[0] || null;
    if (!defaultPersona) return '';

    if (item.key === 'company') return (defaultPersona.company_name || defaultPersona.company || '').trim();
    if (item.key === 'phone') return (defaultPersona.phone_number || defaultPersona.phoneNumber || defaultPersona.phone || defaultPersona.tel || defaultPersona.business_phone || '').trim();
    if (item.key === 'keywords') return Array.isArray(defaultPersona.keywords) ? defaultPersona.keywords.join(', ').trim() : String(defaultPersona.keywords || '').trim();
    if (item.key === 'persona') return (defaultPersona.content || defaultPersona.persona || '').trim();
    return '';
}
window.getPersonaFieldValue = getPersonaFieldValue;

function getMissingPersonaFieldForPrompt() {
    const checks = [
        { key: 'company', label: '업체명', workspaceId: 'company', mypageId: 'mypage-persona-company' },
        { key: 'phone', label: '전화번호', workspaceId: 'phone_number', mypageId: 'mypage-persona-phone' },
        { key: 'keywords', label: '핵심 키워드', workspaceId: 'keywords', mypageId: 'mypage-persona-keywords' },
        { key: 'persona', label: '페르소나 상세 설명', workspaceId: 'persona', mypageId: 'mypage-persona-content' }
    ];
    return checks.find(item => !getPersonaFieldValue(item)) || null;
}
window.getMissingPersonaFieldForPrompt = getMissingPersonaFieldForPrompt;

async function openMyPageAndFocusPersonaField(fieldId) {
    if (typeof showMyPageModal === 'function') {
        await showMyPageModal();
    }
    if (typeof switchMyPageTab === 'function') {
        switchMyPageTab('persona');
    }
    setTimeout(() => {
        const target = document.getElementById(fieldId);
        if (target) {
            target.focus();
            target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }, 250);
}
window.openMyPageAndFocusPersonaField = openMyPageAndFocusPersonaField;

async function validateBeforeGeneratePrompt() {
    const baseContent = (document.getElementById('base_content')?.value || '').trim();
    if (!baseContent) {
        alert('기초내용을 먼저 입력해 주세요.\n\n오늘 작업한 현장 내용, 문제 상황, 해결 과정, 결과를 입력해야 통합 프롬프트를 만들 수 있습니다.');
        const baseEl = document.getElementById('base_content');
        if (baseEl) {
            baseEl.focus();
            baseEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        return false;
    }

    if (isReferenceEmptyForPrompt()) {
        alert('참고자료 또는 콘텐츠 참고URL을 입력해 주세요.\n\n참고할 글이 있으면 콘텐츠 참고URL에 넣고 본문 가져오기를 누르세요. 참고할 자료가 없다면 참고자료 입력칸에 직접 내용을 적어 주세요.');
        const urlEl = document.getElementById('naver-blog-url');
        if (urlEl) {
            urlEl.focus();
            urlEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        return false;
    }

    let missingPersona = getMissingPersonaFieldForPrompt();
    if (missingPersona) {
        if (typeof loadDefaultPersonaIntoWorkspace === 'function') {
            await loadDefaultPersonaIntoWorkspace();
        }
        missingPersona = getMissingPersonaFieldForPrompt();
    }

    if (missingPersona) {
        alert(`마이페이지 업체 페르소나 정보가 부족합니다.\n\n누락 항목: ${missingPersona.label}\n\n업체명, 전화번호, 핵심 키워드, 페르소나 상세 설명은 모두 입력되어야 통합 프롬프트를 만들 수 있습니다.`);
        await openMyPageAndFocusPersonaField(missingPersona.mypageId);
        return false;
    }
    return true;
}
window.validateBeforeGeneratePrompt = validateBeforeGeneratePrompt;

async function generatePromptWithValidation() {
    const isValid = await validateBeforeGeneratePrompt();
    if (!isValid) return;
    return generatePrompt();
}
window.generatePromptWithValidation = generatePromptWithValidation;

function isStoryMakerTestMode() {
    return new URLSearchParams(window.location.search).get('test_mode') === '1';
}
window.isStoryMakerTestMode = isStoryMakerTestMode;

async function saveTestPromptSnapshot(generatedPrompt, requestPayload) {
    if (!isStoryMakerTestMode()) return;
    try {
        const response = await fetchWithAuth('/api/test/prompt-snapshot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                generated_prompt: generatedPrompt,
                project_title: document.getElementById('project-title')?.value || 'test_prompt',
                payload: requestPayload || {}
            })
        });
        const res = await response.json();
        if (!response.ok || !res.ok) throw new Error(res.message || res.detail || '테스트 프롬프트 저장 실패');
        log(`TEST ONLY 프롬프트 임시파일 저장 완료: ${res.data.prompt_for_chatgpt}`, 'success');
    } catch (err) {
        log(`TEST ONLY 프롬프트 임시파일 저장 실패: ${err.message}`, 'warning');
    }
}
window.saveTestPromptSnapshot = saveTestPromptSnapshot;

async function generatePrompt() {
    // 통합 프롬프트 만들기 클릭 시 기존 AI 결과 및 SNS 분리 데이터 초기화
    const inputArea = document.getElementById('chatgpt-raw-input');
    if (inputArea) {
        inputArea.value = '';
    }
    window.lastParsedBlocks = {};
    const snsContainer = document.getElementById('parsed-tabs-container');
    if (snsContainer) {
        snsContainer.style.display = 'none';
    }
    const snsPlaceholder = document.getElementById('sns-placeholder');
    if (snsPlaceholder) {
        snsPlaceholder.style.display = 'block';
    }

    const baseContentEl = document.getElementById('base_content');
    const baseContentValue = baseContentEl ? baseContentEl.value.trim() : '';
    if (!baseContentValue) {
        alert('기초내용을 먼저 입력해 주세요.\n\n오늘 작업한 현장 내용, 문제 상황, 해결 과정, 결과를 입력해야 통합 프롬프트를 만들 수 있습니다.');
        if (baseContentEl) {
            baseContentEl.focus();
            baseContentEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        return;
    }
    const selectedStyle = document.getElementById('style').value;
    const styleGuideMap = {
        '스토리형': '글쓰기 스타일은 반드시 스토리형으로 작성한다. 현장 상황, 고객 고민, 작업 과정, 해결 후 변화를 자연스러운 후기 흐름으로 풀어쓴다.',
        '대화형': '글쓰기 스타일은 반드시 대화형으로 작성한다. 고객 질문과 전문가 답변이 오가는 방식으로 쉽고 친근하게 구성한다.',
        '뉴스형': '글쓰기 스타일은 반드시 뉴스형으로 작성한다. 문제 발생 배경, 현장 확인, 조치 내용, 결과를 객관적이고 정보성 있게 정리한다.'
    };
    const payload = {
        company: document.getElementById('company').value.trim(),
        persona: [
            document.getElementById('persona').value,
            document.getElementById('phone_number').value.trim() ? `대표 전화번호: ${document.getElementById('phone_number').value.trim()}` : '',
            styleGuideMap[selectedStyle] || `글쓰기 스타일은 반드시 ${selectedStyle}으로 작성한다.`
        ].filter(Boolean).join('\n'),
        base_content: document.getElementById('base_content').value,
        reference_text: document.getElementById('reference_text').value,
        keywords: document.getElementById('keywords').value.split(',').map(k => k.trim()).filter(Boolean),
        style: selectedStyle,
        ai_preset: document.getElementById('ai_preset').value,
        region: document.getElementById('ai_preset').value,
        industry_key: document.getElementById('industry_key')?.value || 'general',
        tones: Array.from(document.querySelectorAll('input[name="tone-level"]:checked')).map(el => el.value).slice(0, 5)
    };

    log(`통합 프롬프트 조립 요청 중...`);

    try {
        const response = await fetchWithAuth('/api/generate-prompt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error(`HTTP 에러: ${response.status}`);

        const res = await response.json();
        if (res.ok && res.data && res.data.generated_prompt) {
            document.getElementById('generated-prompt-box').innerText = res.data.generated_prompt;
            console.log("prompt length:", res.data.generated_prompt.length);
            log('통합 프롬프트 마크다운 생성 완료', 'success');

            setTimeout(() => {
                const promptBox = document.getElementById('generated-prompt-box');
                const promptText = promptBox ? (promptBox.innerText || promptBox.textContent || '') : '';
                const weatherBlockMatch = promptText.match(/## 오늘의 현장 날씨\s*([\s\S]*?)(?:\n## |$)/)
                    || promptText.match(/## 최근 일주일 날씨 흐름\s*([\s\S]*?)(?:\n## |$)/)
                    || promptText.match(/## 현재 현장 상황\s*([\s\S]*?)(?:\n## |$)/);
                const legacyWeatherLine = promptText.split('\n').find((line) => line.trim().startsWith('- 오늘 날씨 참고:')) || '';
                const legacyWeatherText = legacyWeatherLine.replace('- 오늘 날씨 참고:', '').trim();
                const weatherText = weatherBlockMatch
                    ? weatherBlockMatch[1].split('\n').map(line => line.trim()).filter(Boolean).join(' / ')
                    : legacyWeatherText;
                const weatherLogText = weatherText.replace(/## .+$/s, '').replace(/\s+/g, ' ').trim().slice(0, 120);
                if (weatherLogText && !weatherLogText.includes('실패') && !weatherLogText.includes('찾지 못했습니다') && !weatherLogText.includes('초과') && !weatherLogText.includes('비어 있습니다') && !weatherLogText.includes('날씨 정보는 아직 충분하지 않습니다')) {
                    log('날씨 반영 확인: ' + weatherLogText, 'success');
                } else {
                    log('날씨 반영 확인 필요: 날씨 참고 정보 없음', 'warning');
                }
            }, 80);
            await saveTestPromptSnapshot(res.data.generated_prompt, payload);
            
            // Update Header Info
            const now = new Date();
            const timeStr = now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');
            const charCount = res.data.generated_prompt.length;
            document.getElementById('prompt-header-info').innerText = `${timeStr} | ${charCount.toLocaleString()}자`;

            // Clear AI & SNS info
            const aiInfo = document.getElementById('ai-header-info');
            if (aiInfo) aiInfo.innerText = `${timeStr} | 프롬프트 ${charCount.toLocaleString()}자`;
            const snsInfo = document.getElementById('sns-header-info');
            if (snsInfo) snsInfo.innerText = '';

            // Reset AI input last length
            window.lastAiInputLength = 0;

            // Accordion transitions
            if (typeof toggleAccordionSection === 'function') {
                toggleAccordionSection('prompt', true);  // Prompt 자동 펼침
                toggleAccordionSection('ai', true);     // AI 접힘
                toggleAccordionSection('sns', false);    // SNS 접힘
            }

            if (typeof trackEvent === 'function') {
                trackEvent("prompt_generate");
            }
            if (typeof triggerAutosave === 'function') {
                triggerAutosave();
            }
        } else {
            throw new Error(res.message || '데이터 구조 오류');
        }
    } catch (err) {
        log(`프롬프트 만들기 에러: ${err.message}`, 'error');
        alert(`프롬프트 만들기 오류: ${err.message}`);
    }
}
window.generatePrompt = generatePrompt;
