// StoryMaker 프론트엔드 프로젝트 관리 및 CRUD/자동 저장 (app_project.js)

const LOCAL_DRAFT_KEY = 'storymaker_workspace_draft_v1';

// 새 프로젝트 다이얼로그 모달 제어
function showNewProjectModal() {
    const modal = document.getElementById('new-project-modal');
    const nameInput = document.getElementById('new-project-name');
    if (!modal || !nameInput) return;
    
    // YYYYMMDD 날짜 구하기
    const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    const company = (document.getElementById('company')?.value || '').trim() || '오박사';
    const companyShort = company.substring(0, 4);
    
    // 파일명 포맷 기본값 제안
    nameInput.value = `${companyShort}_마케팅작업_${today}`;
    modal.style.display = 'flex';
    nameInput.focus();
    nameInput.select();
}
window.showNewProjectModal = showNewProjectModal;

function closeNewProjectModal() {
    const modal = document.getElementById('new-project-modal');
    if (modal) modal.style.display = 'none';
}
window.closeNewProjectModal = closeNewProjectModal;

// 새 프로젝트 생성 확인 처리 파이프라인
async function confirmCreateNewProject() {
    const nameInput = document.getElementById('new-project-name');
    if (!nameInput) return;
    const title = nameInput.value.trim();
    
    if (!title) {
        alert('프로젝트 이름을 입력해 주세요.');
        return;
    }
    
    // 기존 작업이 있었다면 가볍게 자동 저장 선행 호출
    const baseContentVal = document.getElementById('base_content')?.value || '';
    if (baseContentVal.trim() || window.currentProjectId) {
        await saveProject(false);
    }
    
    log(`새 프로젝트 [${title}] 초기화 및 생성 중...`);
    
    // 1. 화면 폼 입력값들을 완전히 디폴트/초기 값으로 셋업
    const projTitleEl = document.getElementById('project-title');
    if (projTitleEl) projTitleEl.value = title;
    
    if (typeof clearCoreInputs === 'function') clearCoreInputs();
    
    const refTextEl = document.getElementById('reference_text');
    if (refTextEl) refTextEl.value = "대기중";
    const blogUrlEl = document.getElementById('naver-blog-url');
    if (blogUrlEl) blogUrlEl.value = "";
    const styleEl = document.getElementById('style');
    if (styleEl) styleEl.value = "스토리형";
    const presetEl = document.getElementById('ai_preset');
    if (presetEl) presetEl.value = "서울";
    
    const promptBox = document.getElementById('generated-prompt-box');
    if (promptBox) promptBox.innerText = "통합 프롬프트를 생성하면 이곳에 표시됩니다.";
    const rawInput = document.getElementById('chatgpt-raw-input');
    if (rawInput) rawInput.value = "";
    
    const parsedTabs = document.getElementById('parsed-tabs-container');
    if (parsedTabs) parsedTabs.style.display = 'none';
    const snsPlaceholder = document.getElementById('sns-placeholder');
    if (snsPlaceholder) snsPlaceholder.style.display = 'block';
    
    window.currentProjectId = null;
    window.lastParsedBlocks = {};
    localStorage.removeItem('current_project_id');
    localStorage.removeItem(LOCAL_DRAFT_KEY);
    
    // 2. 백엔드 DB 레코드 즉시 자동 생성을 위해 saveProject 비동기 호출 수행
    await saveProject(false);
    
    closeNewProjectModal();
    
    // Reset localStorage accordion states to false (all collapsed)
    localStorage.setItem('storymaker.workspace.prompt.open', 'false');
    localStorage.setItem('storymaker.workspace.ai.open', 'false');
    localStorage.setItem('storymaker.workspace.sns.open', 'false');
    if (typeof initializeWorkspaceAccordions === 'function') {
        initializeWorkspaceAccordions();
    }

    // Clear header info spans
    const pInfo = document.getElementById('prompt-header-info');
    if (pInfo) pInfo.innerText = '';
    const aInfo = document.getElementById('ai-header-info');
    if (aInfo) aInfo.innerText = '';
    const sInfo = document.getElementById('sns-header-info');
    if (sInfo) sInfo.innerText = '';

    showToast('새 프로젝트 생성 완료');
}
window.confirmCreateNewProject = confirmCreateNewProject;

// 1. 프로젝트 목록 로드
async function loadProjectList() {
    try {
        const response = await fetchWithAuth('/api/projects?limit=50');
        if (!response.ok) throw new Error('프로젝트 리스트 패치 실패');
        
        const res = await response.json();
        if (res.ok && res.data) {
            const selector = document.getElementById('project-selector');
            if (!selector) return;
            selector.innerHTML = '<option value="">-- 저장된 프로젝트 선택 --</option>';
            
            res.data.forEach(proj => {
                const opt = document.createElement('option');
                opt.value = proj.id;
                
                // 제목이 길면 말줄임(20자 제한) 처리
                let displayTitle = proj.title;
                if (displayTitle.length > 20) {
                    displayTitle = displayTitle.substring(0, 20) + '...';
                }
                
                opt.innerText = `[${proj.updated_at.split(' ')[0]}] ${displayTitle}`;
                if (window.currentProjectId && proj.id == window.currentProjectId) {
                    opt.selected = true;
                }
                selector.appendChild(opt);
            });
        }
    } catch (err) {
        log(`프로젝트 목록 갱신 실패: ${err.message}`, 'error');
    }
}
window.loadProjectList = loadProjectList;

// 2. 프로젝트 상세 정보 로드 및 화면 바인딩
async function loadSelectedProject() {
    const selector = document.getElementById('project-selector');
    if (!selector) return;
    const selectedId = selector.value;
    
    // 만약 기본 가이드를 다시 고르면 화면만 리셋 (생성은 하지 않음)
    if (!selectedId) {
        window.currentProjectId = null;
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
        window.lastParsedBlocks = {};
        localStorage.removeItem('current_project_id');
        
        // 감성 레벨 체크박스 초기화
        document.querySelectorAll('input[name="tone-level"]').forEach(el => {
            el.checked = ['따뜻함', '전문가'].includes(el.value);
        });
        
        log('작업대 초기화 완료');
        return;
    }

    log(`프로젝트 ID [${selectedId}] 조회 중...`);
    try {
        const response = await fetchWithAuth(`/api/projects/${selectedId}`);
        if (!response.ok) throw new Error('프로젝트 조회 실패');

        const res = await response.json();
        if (res.ok && res.data) {
            const proj = res.data;
            window.currentProjectId = proj.id;
            localStorage.setItem('current_project_id', proj.id);

            // 폼 데이터 맵핑
            const projTitle = document.getElementById('project-title');
            if (projTitle) projTitle.value = proj.title;
            const companyEl = document.getElementById('company');
            if (companyEl) companyEl.value = proj.company || proj.company_name || proj.business_name || '';
            const personaEl = document.getElementById('persona');
            // 프로젝트 선택 시 임시 페르소나 문구로 덮어쓰지 않습니다.
            // 저장된 user_personas DB에서 업체명에 맞는 페르소나를 찾아 작업 화면에 다시 적용합니다.
            try {
                if (typeof loadMyPersonas === 'function') {
                    const personas = window.myPersonas && window.myPersonas.length ? window.myPersonas : null;
                    if (!personas) await loadMyPersonas();
                }
                const projectCompanyName = (proj.company || proj.company_name || proj.business_name || '').trim();
                const matchedPersona = (window.myPersonas || []).find(function(item) {
                    const name = (item && item.company_name ? item.company_name : '').trim();
                    return name && projectCompanyName && (name === projectCompanyName || projectCompanyName.includes(name) || name.includes(projectCompanyName));
                }) || (window.myPersonas || []).find(function(item) { return item && item.is_default; }) || (window.myPersonas || [])[0] || null;
                if (matchedPersona && typeof applyPersonaToWorkspace === 'function') {
                    applyPersonaToWorkspace(matchedPersona);
                } else if (personaEl && !personaEl.value) {
                    personaEl.value = '';
                }
            } catch (personaErr) {
                console.warn('[StoryMaker] 프로젝트 선택 후 페르소나 DB 동기화 실패', personaErr);
            }
            
            const baseContent = document.getElementById('base_content');
            if (baseContent) baseContent.value = proj.base_content || '';
            const refText = document.getElementById('reference_text');
            if (refText) refText.value = proj.reference_text || '';
            const keywordsEl = document.getElementById('keywords');
            if (keywordsEl) keywordsEl.value = proj.keywords ? proj.keywords.join(', ') : '';
            const styleEl = document.getElementById('style');
            if (styleEl && proj.style) styleEl.value = proj.style;
            const presetEl = document.getElementById('ai_preset');
            if (presetEl && proj.ai_preset) presetEl.value = proj.ai_preset;
            
            // tones 설정
            const tonesToSet = proj.tones && proj.tones.length ? proj.tones : ['따뜻함', '전문가'];
            document.querySelectorAll('input[name="tone-level"]').forEach(el => {
                el.checked = tonesToSet.includes(el.value);
            });
            
            const promptBox = document.getElementById('generated-prompt-box');
            const promptPlaceholder = '통합 프롬프트를 생성하면 이곳에 표시됩니다.';
            if (promptBox) {
                promptBox.innerText = proj.generated_prompt || promptPlaceholder;
            }

            const rawInput = document.getElementById('chatgpt-raw-input');
            if (rawInput) {
                rawInput.value = proj.raw_result || '';
                if (typeof onAiResultInput === 'function') {
                    try {
                        onAiResultInput();
                    } catch (e) {
                        console.warn('[StoryMaker] AI 결과 후처리 실패, 프로젝트 본문 로드는 유지합니다.', e);
                    }
                }
            }

            window.lastParsedBlocks = proj.parsed_result_json || {};
            if (window.lastParsedBlocks && Object.keys(window.lastParsedBlocks).length) {
                if (typeof renderParsedTabs === 'function') {
                    try {
                        renderParsedTabs(window.lastParsedBlocks);
                    } catch (e) {
                        console.warn('[StoryMaker] SNS 탭 렌더링 실패, 프로젝트 기본 데이터 로드는 유지합니다.', e);
                    }
                }
            } else {
                const parsedTabs = document.getElementById('parsed-tabs-container');
                const snsPlaceholder = document.getElementById('sns-placeholder');
                if (parsedTabs) parsedTabs.style.display = 'none';
                if (snsPlaceholder) snsPlaceholder.style.display = 'block';
            }

            const promptLen = promptBox ? (promptBox.innerText || '').length : 0;
            console.log("after render prompt length:", promptLen);

            try {
                if (typeof toggleInputCard === 'function') toggleInputCard(true);
                if (typeof toggleAccordionSection === 'function') {
                    toggleAccordionSection('prompt', !!proj.generated_prompt);
                    toggleAccordionSection('ai', !!proj.raw_result);
                    toggleAccordionSection('sns', !!(window.lastParsedBlocks && Object.keys(window.lastParsedBlocks).length));
                }
            } catch (e) {
                console.warn('[StoryMaker] 아코디언 상태 동기화 실패, 프로젝트 로드는 유지합니다.', e);
            }

            selector.value = proj.id;
            
            // 우측 상태창 동기화
            const saveText = document.getElementById('save-status-text');
            if (saveText) {
                saveText.innerText = '모든 작업 저장됨';
                saveText.style.color = 'var(--success)';
            }
            
            log(`프로젝트 [${proj.title}] 로드 완료`, 'success');
        } else {
            throw new Error(res.message);
        }
    } catch (err) {
        log(`프로젝트 로드 오류: ${err.message}`, 'error');
        alert(`불러오기 오류: ${err.message}`);
    }
}
window.loadSelectedProject = loadSelectedProject;

function ensureProjectLoaderBindings() {
    const selector = document.getElementById('project-selector');
    if (selector && !selector.dataset.storymakerProjectBound) {
        selector.addEventListener('change', function() {
            if (typeof loadSelectedProject === 'function') {
                loadSelectedProject();
            }
        });
        selector.dataset.storymakerProjectBound = '1';
    }

    const token = localStorage.getItem('storymaker_token');
    if (token && window.storymakerBootHydrated && !window.storymakerProjectListLoaded && typeof loadProjectList === 'function') {
        window.storymakerProjectListLoaded = true;
        loadProjectList().catch(function(err) {
            window.storymakerProjectListLoaded = false;
            console.warn('[StoryMaker] 프로젝트 목록 자동 복구 로드 실패', err);
        });
    }
}

window.ensureProjectLoaderBindings = ensureProjectLoaderBindings;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(ensureProjectLoaderBindings, 800);
    });
} else {
    setTimeout(ensureProjectLoaderBindings, 800);
}

// 3. 프로젝트 저장
async function saveProject(manual = false) {
    if (window.isSaving) return;
    window.isSaving = true;

    const saveStatus = document.getElementById('save-status-text');
    if (saveStatus) {
        saveStatus.innerText = '저장 중...';
        saveStatus.style.color = 'var(--warning)';
    }

    const title = document.getElementById('project-title')?.value || '새 프로젝트';
    const companyName = document.getElementById('company')?.value || '';
    
    let companyId = 1;
    if (companyName.includes("숯불")) companyId = 2;
    else if (companyName.includes("결로")) companyId = 3;

    const promptText = document.getElementById('generated-prompt-box')?.innerText || '';
    const rawResultText = document.getElementById('chatgpt-raw-input')?.value || '';
    const promptPlaceholder = '통합 프롬프트를 생성하면 이곳에 표시됩니다.';

    const payload = {
        title: title.trim() || '무제 프로젝트',
        company_id: companyId,
        base_content: document.getElementById('base_content')?.value || '',
        reference_text: document.getElementById('reference_text')?.value || '',
        keywords: (document.getElementById('keywords')?.value || '').split(',').map(k => k.trim()).filter(Boolean),
        style: document.getElementById('style')?.value || '스토리형',
        ai_preset: document.getElementById('ai_preset')?.value || 'ChatGPT',
        tones: Array.from(document.querySelectorAll('input[name="tone-level"]:checked')).map(el => el.value).slice(0, 5),
        generated_prompt: promptText && promptText !== promptPlaceholder ? promptText : '',
        raw_result: rawResultText,
        parsed_result_json: window.lastParsedBlocks && Object.keys(window.lastParsedBlocks).length ? window.lastParsedBlocks : {}
    };

    try {
        let response;
        let url;
        let method;

        if (window.currentProjectId) {
            url = `/api/projects/${window.currentProjectId}`;
            method = 'PUT';
        } else {
            url = '/api/projects';
            method = 'POST';
        }

        response = await fetchWithAuth(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            let errorBody = `HTTP 에러 ${response.status}`;
            try {
                const errData = await response.json();
                errorBody += `: ${errData.message || errData.detail || JSON.stringify(errData)}`;
            } catch (e) {
                try {
                    const rawTxt = await response.text();
                    errorBody += `: ${rawTxt}`;
                } catch (e2) {}
            }
            throw new Error(errorBody);
        }

        const res = await response.json();
        if (res.ok && res.data) {
            const isNew = !window.currentProjectId;
            const savedProj = res.data;
            window.currentProjectId = savedProj.id;
            
            if (isNew) {
                if (typeof trackEvent === 'function') {
                    trackEvent("project_create");
                }
                
                // Guest 모드인 경우 로컬 스토리지에 생성된 프로젝트 ID를 보관
                try {
                    const isGuest = (JSON.parse(localStorage.getItem('storymaker_user') || '{}').username || '') === 'guest';
                    if (isGuest) {
                        let ids = JSON.parse(localStorage.getItem('guest_project_ids') || '[]');
                        if (!ids.includes(savedProj.id)) {
                            ids.push(savedProj.id);
                            localStorage.setItem('guest_project_ids', JSON.stringify(ids));
                        }
                    }
                } catch (e) {
                    console.error('Failed to track guest project ID:', e);
                }
            }
            localStorage.setItem('current_project_id', savedProj.id);
            
            const promptBox = document.getElementById('generated-prompt-box');
            const promptLen = promptBox ? (promptBox.innerText || '').length : 0;
            console.log("after save prompt length:", promptLen);
            
            if (manual) {
                log(`프로젝트 저장 완료 (ID: ${savedProj.id})`, 'success');
                if (typeof showToast === 'function') {
                    showToast('저장 완료');
                }
            } else {
                log('자동 저장 완료', 'success');
            }
            
            await loadProjectList();
        } else {
            throw new Error(res.message || '저장 응답 데이터 규격 이상');
        }
    } catch (err) {
        log(`저장 실패 상세: ${err.message}`, 'error');
        if (manual) alert(`저장 오류: ${err.message}`);
    } finally {
        window.isSaving = false;
        if (saveStatus) {
            saveStatus.innerText = '모든 작업 저장됨';
            saveStatus.style.color = 'var(--success)';
        }
    }
}
window.saveProject = saveProject;

function saveWorkspaceDraftLocal() {
    try {
        const getValue = (id) => document.getElementById(id)?.value || '';
        const promptText = document.getElementById('generated-prompt-box')?.innerText || '';
        const promptPlaceholder = '통합 프롬프트를 생성하면 이곳에 표시됩니다.';
        const draft = {
            saved_at: new Date().toISOString(),
            currentProjectId: window.currentProjectId,
            project_title: getValue('project-title'),
            base_content: getValue('base_content'),
            reference_text: getValue('reference_text'),
            naver_blog_url: getValue('naver-blog-url'),
            style: getValue('style'),
            ai_preset: getValue('ai_preset'),
            generated_prompt: promptText && promptText !== promptPlaceholder ? promptText : '',
            raw_result: getValue('chatgpt-raw-input'),
            parsed_result_json: window.lastParsedBlocks && Object.keys(window.lastParsedBlocks).length ? window.lastParsedBlocks : {}
        };
        localStorage.setItem(LOCAL_DRAFT_KEY, JSON.stringify(draft));
    } catch (e) {
        console.warn('[StoryMaker] 로컬 작업 임시저장 실패', e);
    }
}
window.saveWorkspaceDraftLocal = saveWorkspaceDraftLocal;

function restoreWorkspaceDraftLocal() {
    try {
        const raw = localStorage.getItem(LOCAL_DRAFT_KEY);
        if (!raw) return false;
        const draft = JSON.parse(raw);
        const setValue = (id, value) => {
            const el = document.getElementById(id);
            if (el && value !== undefined && value !== null) el.value = value;
        };
        setValue('project-title', draft.project_title || '새 프로젝트');
        setValue('base_content', draft.base_content || '');
        setValue('reference_text', draft.reference_text || '대기중');
        setValue('naver-blog-url', draft.naver_blog_url || '');
        setValue('style', draft.style || '스토리형');
        setValue('ai_preset', draft.ai_preset || 'ChatGPT');
        const promptBox = document.getElementById('generated-prompt-box');
        const promptPlaceholder = '통합 프롬프트를 생성하면 이곳에 표시됩니다.';
        if (promptBox) promptBox.innerText = draft.generated_prompt || promptPlaceholder;
        setValue('chatgpt-raw-input', draft.raw_result || '');
        window.lastParsedBlocks = draft.parsed_result_json || {};
        if (window.lastParsedBlocks && Object.keys(window.lastParsedBlocks).length) {
            if (typeof renderParsedTabs === 'function') {
                renderParsedTabs(window.lastParsedBlocks);
            }
        }
        if (draft.raw_result && typeof onAiResultInput === 'function') {
            onAiResultInput();
        }
        if (draft.currentProjectId) window.currentProjectId = draft.currentProjectId;
        return true;
    } catch (e) {
        console.warn('[StoryMaker] 로컬 작업 복구 실패', e);
        return false;
    }
}
window.restoreWorkspaceDraftLocal = restoreWorkspaceDraftLocal;

window.addEventListener('beforeunload', saveWorkspaceDraftLocal);
document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'hidden') saveWorkspaceDraftLocal();
});

// 4. 입력값 변경 감지 디바운스 자동 저장 기동
function triggerAutosave() {
    saveWorkspaceDraftLocal();
    if (window.autosaveTimer) {
        clearTimeout(window.autosaveTimer);
    }
    
    window.autosaveTimer = setTimeout(() => {
        const baseContent = document.getElementById('base_content')?.value || '';
        if (baseContent.trim() || window.currentProjectId) {
            saveProject(false);
        }
    }, 1200);
}
window.triggerAutosave = triggerAutosave;
