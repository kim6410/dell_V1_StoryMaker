// StoryMaker 프론트엔드 페르소나 데이터 및 매핑 관리 모듈 (app_persona.js)

function showPersonaHelp() {
    const modal = document.getElementById('persona-help-modal');
    if (modal) modal.style.display = 'flex';
}
window.showPersonaHelp = showPersonaHelp;

function closePersonaHelp() {
    const modal = document.getElementById('persona-help-modal');
    if (modal) modal.style.display = 'none';
}
window.closePersonaHelp = closePersonaHelp;

function setPersonaError(message = '') {
    const error = document.getElementById('mypage-persona-error');
    if (!error) return;
    error.innerText = message;
    error.style.display = message ? 'block' : 'none';
}
window.setPersonaError = setPersonaError;

async function loadMyPageIndustries(selectedIndustryKey = null) {
    const selector = document.getElementById('mypage-persona-industry');
    if (!selector) return;

    const previousValue = selectedIndustryKey || selector.value || 'general';
    try {
        const response = await fetchWithAuth('/api/auth/industry-templates');
        const res = await response.json();
        if (!response.ok || !res.ok) throw new Error(res.detail || res.message || '업종 목록을 불러오지 못했습니다.');

        const items = Array.isArray(res.data) ? res.data : [];
        if (!items.length) return;

        selector.innerHTML = '';
        let currentCategory = '';
        let group = null;

        items.forEach(item => {
            const category = item.category || '공통';
            if (category !== currentCategory) {
                currentCategory = category;
                group = document.createElement('optgroup');
                group.label = category;
                selector.appendChild(group);
            }
            const option = document.createElement('option');
            option.value = item.industry_key;
            option.innerText = item.label || item.industry_key;
            if (group) group.appendChild(option);
            else selector.appendChild(option);
        });

        const hasPrevious = Array.from(selector.options).some(option => option.value === previousValue);
        selector.value = hasPrevious ? previousValue : (selector.options[0] ? selector.options[0].value : 'general');
    } catch (err) {
        console.warn('[StoryMaker] 업종 목록 DB 로딩 실패, 기본 옵션 유지:', err);
    }
}
window.loadMyPageIndustries = loadMyPageIndustries;

async function loadMyPersonas(selectedId = null) {
    const response = await fetchWithAuth('/api/auth/personas');
    const res = await response.json();
    if (!response.ok || !res.ok) throw new Error(res.detail || res.message || '페르소나 목록을 불러오지 못했습니다.');
    
    window.myPersonas = res.data || [];
    const selector = document.getElementById('mypage-persona-selector');
    if (!selector) return null;
    
    selector.innerHTML = '';
    window.myPersonas.forEach(persona => {
        const option = document.createElement('option');
        option.value = persona.id;
        option.innerText = `${persona.is_default ? '★ ' : ''}${persona.company_name}`;
        selector.appendChild(option);
    });
    const newOption = document.createElement('option');
    newOption.value = '__new__';
    newOption.innerText = '＋ 새 페르소나 작성';
    selector.appendChild(newOption);
    
    const defaultPersona = window.myPersonas.find(persona => persona.is_default) || window.myPersonas[0];
    selector.value = selectedId ? String(selectedId) : (defaultPersona ? String(defaultPersona.id) : '__new__');
    await selectMyPersona(false);
    return window.myPersonas.find(item => String(item.id) === selector.value) || null;
}
window.loadMyPersonas = loadMyPersonas;

async function selectMyPersona(markAsDefault = true) {
    setPersonaError();
    const selector = document.getElementById('mypage-persona-selector');
    if (!selector) return;

    if (selector.value === '__new__') {
        markAsDefault = false;
    }

    const selectedId = Number(selector.value || 0);
    const persona = selector.value === '__new__' ? null : (window.myPersonas || []).find(item => String(item.id) === String(selectedId));
    
    const companyInput = document.getElementById('mypage-persona-company');
    if (companyInput) companyInput.value = persona ? persona.company_name : '';
    
    const industryEl = document.getElementById('mypage-persona-industry');
    if (industryEl) industryEl.value = persona ? (persona.industry_key || 'general') : 'general';
    
    const phoneInput = document.getElementById('mypage-persona-phone');
    if (phoneInput) phoneInput.value = persona ? persona.phone_number : '';
    
    const websiteEl = document.getElementById('mypage-persona-website');
    if (websiteEl) websiteEl.value = persona ? (persona.website_url || '') : '';
    
    const keywordsInput = document.getElementById('mypage-persona-keywords');
    if (keywordsInput) keywordsInput.value = persona ? (persona.keywords || []).join(', ') : '';
    
    const contentInput = document.getElementById('mypage-persona-content');
    if (contentInput) contentInput.value = persona ? persona.content : '';
    
    const deleteBtn = document.getElementById('mypage-persona-delete');
    if (deleteBtn) deleteBtn.style.display = persona ? 'inline-block' : 'none';
    
    if (persona) {
        applyPersonaToWorkspace(persona);
        if (markAsDefault && !persona.is_default) {
            try {
                const response = await fetchWithAuth(`/api/auth/personas/${persona.id}/default`, { method: 'PUT' });
                const res = await response.json();
                if (!response.ok || !res.ok) throw new Error(res.detail || res.message || '기본 페르소나 설정에 실패했습니다.');
                await loadMyPersonas(persona.id);
                if (typeof showToast === 'function') {
                    showToast('기본 페르소나 변경 완료');
                }
            } catch (err) {
                setPersonaError(err.message);
            }
        }
    }
    syncProfileSummary();
}
window.selectMyPersona = selectMyPersona;

function syncProfileSummary() {
    const summary = document.getElementById('mypage-profile-summary');
    const defaultPersona = (window.myPersonas || []).find(persona => persona.is_default) || (window.myPersonas || [])[0] || null;
    if (summary) {
        if (defaultPersona) {
            summary.innerText = `${defaultPersona.company_name} (${defaultPersona.keywords?.slice(0,3).join(', ')}...)`;
        } else {
            summary.innerText = '등록된 업체 정보가 없습니다.';
        }
    }
    syncActivePersonaHeader(defaultPersona);
}
window.syncProfileSummary = syncProfileSummary;

function syncActivePersonaHeader(persona = null) {
    const companyEl = document.getElementById('active-persona-company-display');
    const phoneEl = document.getElementById('active-persona-phone-display');
    if (!companyEl && !phoneEl) return;

    if (!persona) {
        const selector = document.getElementById('mypage-persona-selector');
        const selectedId = selector ? selector.value : '';
        persona = (window.myPersonas || []).find(item => String(item.id) === String(selectedId)) ||
                  (window.myPersonas || []).find(item => item.is_default) ||
                  (window.myPersonas || [])[0] || null;
    }

    const company = persona && persona.company_name ? persona.company_name : '업체명 미등록';
    const phone = persona && persona.phone_number ? persona.phone_number : '전화번호 미등록';
    if (companyEl) companyEl.innerText = company;
    if (phoneEl) phoneEl.innerText = phone;
}
window.syncActivePersonaHeader = syncActivePersonaHeader;

function applyPersonaToWorkspace(persona) {
    if (!persona) return;
    syncActivePersonaHeader(persona);
    const companyInput = document.getElementById('company');
    if (companyInput) companyInput.value = persona.company_name || '';
    
    const phoneInput = document.getElementById('phone_number');
    if (phoneInput) phoneInput.value = persona.phone_number || '';
    
    const keywordsInput = document.getElementById('keywords');
    if (keywordsInput) keywordsInput.value = (persona.keywords || []).join(', ');

    const industryInput = document.getElementById('industry_key');
    if (industryInput) industryInput.value = persona.industry_key || 'general';
    
    const personaInput = document.getElementById('persona');
    if (personaInput) personaInput.value = persona.content || '';

    const profileCompanySummary = document.getElementById('profile-company-summary');
    if (profileCompanySummary) profileCompanySummary.innerText = persona.company_name || '마이페이지 등록 필요';

    const profilePhoneSummary = document.getElementById('profile-phone-summary');
    if (profilePhoneSummary) profilePhoneSummary.innerText = persona.phone_number || '전화번호 미등록';

    const profileKeywordsSummary = document.getElementById('profile-keywords-summary');
    if (profileKeywordsSummary) profileKeywordsSummary.innerText = (persona.keywords || []).join(', ') || '마이페이지 등록 필요';

    const profilePersonaSummary = document.getElementById('profile-persona-summary');
    if (profilePersonaSummary) profilePersonaSummary.innerText = persona.content || '마이페이지에서 상세 설명을 등록해 주세요';
}
window.applyPersonaToWorkspace = applyPersonaToWorkspace;

function newMyPersona() {
    setPersonaError();
    const selector = document.getElementById('mypage-persona-selector');
    if (selector) selector.value = '__new__';
    
    const companyInput = document.getElementById('mypage-persona-company');
    if (companyInput) companyInput.value = '';
    
    const industryEl = document.getElementById('mypage-persona-industry');
    if (industryEl) industryEl.value = 'general';
    
    const phoneInput = document.getElementById('mypage-persona-phone');
    if (phoneInput) phoneInput.value = '';
    
    const websiteEl = document.getElementById('mypage-persona-website');
    if (websiteEl) websiteEl.value = '';
    
    const keywordsInput = document.getElementById('mypage-persona-keywords');
    if (keywordsInput) keywordsInput.value = '';
    
    const contentInput = document.getElementById('mypage-persona-content');
    if (contentInput) contentInput.value = '';
    
    const deleteBtn = document.getElementById('mypage-persona-delete');
    if (deleteBtn) deleteBtn.style.display = 'none';
}
window.newMyPersona = newMyPersona;

async function saveMyPersona() {
    setPersonaError();
    const company = document.getElementById('mypage-persona-company')?.value.trim() || '';
    if (!company) {
        setPersonaError('업체명은 필수 입력 항목입니다.');
        return;
    }
    
    const industry_key = document.getElementById('mypage-persona-industry')?.value || 'general';
    const phone_number = document.getElementById('mypage-persona-phone')?.value.trim() || '';
    const website_url = document.getElementById('mypage-persona-website')?.value.trim() || '';
    const keywords = (document.getElementById('mypage-persona-keywords')?.value || '').split(',').map(k => k.trim()).filter(Boolean);
    const content = document.getElementById('mypage-persona-content')?.value.trim() || '';
    
    const selector = document.getElementById('mypage-persona-selector');
    if (!selector) return;
    const selectedValue = selector.value || '__new__';
    const selectedPersona = (window.myPersonas || []).find(item => String(item.id) === String(selectedValue));
    const isNew = selectedValue === '__new__' || !selectedPersona;
    const method = isNew ? 'POST' : 'PUT';
    const url = isNew ? '/api/auth/personas' : `/api/auth/personas/${selectedValue}`;
    
    try {
        const response = await fetchWithAuth(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ company_name: company, industry_key, phone_number, website_url, keywords, content })
        });
        const rawText = await response.text();
        let res = {};
        try {
            res = rawText ? JSON.parse(rawText) : {};
        } catch (parseErr) {
            throw new Error('서버 응답을 읽지 못했습니다. 상태코드: ' + response.status);
        }
        if (!response.ok || !res.ok) {
            let detail = res.detail || res.message || '페르소나 저장에 실패했습니다.';
            if (Array.isArray(detail)) {
                detail = detail.map(item => item.msg || JSON.stringify(item)).join('\n');
            } else if (typeof detail === 'object') {
                detail = JSON.stringify(detail, null, 2);
            }
            throw new Error(detail);
        }
        
        const nextId = res.data && res.data.id ? res.data.id : selectedValue;
        const nextPersona = await loadMyPersonas(nextId);
        if (nextPersona) applyPersonaToWorkspace(nextPersona);
        if (typeof showToast === 'function') {
            showToast(isNew ? '새 페르소나 저장 완료' : '페르소나 수정 완료');
        }
        if (typeof window.returnFromMyPage === 'function') {
            window.returnFromMyPage();
        } else if (typeof window.closeMyPageModal === 'function') {
            window.closeMyPageModal();
        }
    } catch (err) {
        setPersonaError(err.message || String(err));
        console.error('[StoryMaker] 페르소나 저장 실패', err);
    }
}
window.saveMyPersona = saveMyPersona;

async function deleteMyPersona() {
    const selector = document.getElementById('mypage-persona-selector');
    if (!selector || selector.value === '__new__') return;
    if (!confirm('정말로 이 페르소나 정보를 삭제하시겠습니까?')) return;
    
    setPersonaError();
    try {
        const response = await fetchWithAuth(`/api/auth/personas/${selector.value}`, { method: 'DELETE' });
        const res = await response.json();
        if (!response.ok || !res.ok) throw new Error(res.detail || res.message || '페르소나 삭제에 실패했습니다.');
        
        const nextPersona = await loadMyPersonas();
        if (nextPersona) {
            applyPersonaToWorkspace(nextPersona);
        } else {
            const companyInput = document.getElementById('company');
            if (companyInput) companyInput.value = '';
            const phoneInput = document.getElementById('phone_number');
            if (phoneInput) phoneInput.value = '';
            const keywordsInput = document.getElementById('keywords');
            if (keywordsInput) keywordsInput.value = '';
            const personaInput = document.getElementById('persona');
            if (personaInput) personaInput.value = '';
        }
        if (typeof showToast === 'function') {
            showToast('페르소나 삭제 완료');
        }
    } catch (err) {
        setPersonaError(err.message);
    }
}
window.deleteMyPersona = deleteMyPersona;

async function loadDefaultPersonaIntoWorkspace() {
    try {
        const response = await fetchWithAuth('/api/auth/personas');
        const res = await response.json();
        if (!response.ok || !res.ok) throw new Error(res.detail || res.message || '기본 페르소나 조회 실패');
        window.myPersonas = res.data || [];
        const defaultPersona = window.myPersonas.find(persona => persona.is_default) || window.myPersonas[0];
        if (defaultPersona) {
            applyPersonaToWorkspace(defaultPersona);
            log(`[페르소나] ${defaultPersona.company_name} 기본값을 첫 화면에 적용했습니다.`, 'success');
        }
    } catch (err) {
        log(`기본 페르소나 적용 실패: ${err.message}`, 'warning');
    }
}
window.loadDefaultPersonaIntoWorkspace = loadDefaultPersonaIntoWorkspace;
