// StoryMaker 프론트엔드 관리자 대시보드 및 통계 연동 모듈 (app_admin.js)

let activeDetailTab = 'proj';

async function showAdminDashboard(initialTab = 'dashboard') {
    const modal = document.getElementById('admin-modal');
    if (!modal) return;

    // 관리자 화면은 먼저 즉시 보여준다.
    // 통계/랭킹/회원 목록을 동시에 불러오면 첫 진입 때 화면이 버벅일 수 있다.
    modal.style.display = 'flex';
    switchAdminTab(initialTab);

    log('StoryMaker Audit Center 화면을 먼저 열었습니다. 관리자 데이터는 순차 로딩합니다.');

    window.setTimeout(async () => {
        await Promise.allSettled([
            loadAdminStats()
        ]);
    }, 80);

    window.setTimeout(async () => {
        await Promise.allSettled([
            loadUserRankings()
        ]);
    }, 420);

    window.setTimeout(async () => {
        await Promise.allSettled([
            loadAdminUsers()
        ]);
    }, 760);
}
window.showAdminDashboard = showAdminDashboard;

function closeAdminDashboard() {
    const modal = document.getElementById('admin-modal');
    if (modal) modal.style.display = 'none';
    if (window.location.pathname === '/admin/analytics') {
        window.history.pushState({}, '', '/');
    }
}
window.closeAdminDashboard = closeAdminDashboard;

function switchAdminTab(tabName) {
    const tabs = {
        dashboard: {
            panel: document.getElementById('admin-dashboard-tab-content'),
            button: document.getElementById('btn-admin-tab-dashboard')
        },
        analytics: {
            panel: document.getElementById('admin-analytics-tab-content'),
            button: document.getElementById('btn-admin-tab-analytics')
        },
        requests: {
            panel: document.getElementById('admin-requests-tab-content'),
            button: document.getElementById('btn-admin-tab-requests'),
            load: () => loadFeatureRequests()
        },
        'content-upload': {
            panel: document.getElementById('admin-content-upload-tab-content'),
            button: document.getElementById('btn-admin-tab-content-upload')
        },
        industry: {
            panel: document.getElementById('admin-industry-tab-content'),
            button: document.getElementById('btn-admin-tab-industry'),
            load: () => typeof loadIndustryTemplates === 'function' && loadIndustryTemplates()
        }
    };

    const active = tabs[tabName];
    if (!active || !active.panel || !active.button) return;

    Object.values(tabs).forEach(({ panel, button }) => {
        if (panel) panel.style.display = 'none';
        if (!button) return;
        button.classList.remove('active');
        button.style.color = 'var(--muted)';
        button.style.borderBottomColor = 'transparent';
        button.style.fontWeight = '500';
    });

    active.panel.style.display = 'flex';
    active.button.classList.add('active');
    active.button.style.color = 'var(--text)';
    active.button.style.borderBottomColor = 'var(--accent)';
    active.button.style.fontWeight = '600';

    if (tabName === 'analytics' && window.location.pathname !== '/admin/analytics') {
        window.history.pushState({}, '', '/admin/analytics');
        log('Plausible Analytics 새 탭 링크 활성화 완료');
    } else if (tabName !== 'analytics' && window.location.pathname === '/admin/analytics') {
        window.history.pushState({}, '', '/');
    }

    if (active.load) active.load();
}
window.switchAdminTab = switchAdminTab;

function clearAdminUploadForm() {
    [
        'admin-upload-title',
        'admin-upload-slug',
        'admin-upload-content',
        'admin-upload-categories',
        'admin-upload-tags',
        'admin-upload-excerpt',
        'admin-upload-image-alt'
    ].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    const msg = document.getElementById('admin-upload-status-msg');
    if (msg) msg.innerText = '';
}
window.clearAdminUploadForm = clearAdminUploadForm;

async function submitAdminContentToWp(status = 'draft') {
    const title = document.getElementById('admin-upload-title')?.value.trim() || '';
    const content = document.getElementById('admin-upload-content')?.value.trim() || '';
    const msgEl = document.getElementById('admin-upload-status-msg');
    if (!title || !content) {
        alert('글 제목과 본문 내용은 필수 입력 항목입니다.');
        return;
    }

    const btn = status === 'publish'
        ? document.getElementById('btn-admin-content-upload-submit-pub')
        : document.getElementById('btn-admin-content-upload-submit');
    const origText = btn?.innerText || '';
    if (btn) {
        btn.disabled = true;
        btn.innerText = status === 'publish' ? '발행 업로드 중...' : '초안 업로드 중...';
    }
    if (msgEl) {
        msgEl.style.color = 'var(--accent)';
        msgEl.innerText = 'WordPress 서버로 전송 중입니다...';
    }

    try {
        const response = await fetchWithAuth('/api/wordpress/draft', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                slug: document.getElementById('admin-upload-slug')?.value.trim() || '',
                content,
                excerpt: document.getElementById('admin-upload-excerpt')?.value.trim() || '',
                status,
                tags_text: document.getElementById('admin-upload-tags')?.value.trim() || '',
                categories_text: document.getElementById('admin-upload-categories')?.value.trim() || '',
                meta_description: document.getElementById('admin-upload-excerpt')?.value.trim() || '',
                focus_keyword: title.split(' ')[0],
                featured_image_alt: document.getElementById('admin-upload-image-alt')?.value.trim() || ''
            })
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.detail || res.message || 'WordPress 업로드 실패');
        if (msgEl) {
            const statusTxt = status === 'publish' ? '즉시 발행' : '임시저장(초안)';
            msgEl.style.color = 'var(--success)';
            msgEl.innerHTML = `WordPress에 ${statusTxt} 등록 완료! (<a href="${res.link}" target="_blank" style="color:var(--accent); text-decoration:underline;">글 보기</a>)`;
        }
        showToast('WordPress 업로드 완료');
    } catch (err) {
        if (msgEl) {
            msgEl.style.color = 'var(--danger)';
            msgEl.innerText = `업로드 실패: ${err.message}`;
        }
        alert(`오류: ${err.message}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = origText;
        }
    }
}
window.submitAdminContentToWp = submitAdminContentToWp;

let adminIndustryTemplates = [];
let selectedIndustryKey = null;

function renderAdminIndustryCategoryOptions(selectedCategory = '공통') {
    const categoryEl = document.getElementById('admin-industry-category');
    if (!categoryEl) return;
    const categories = Array.from(new Set((adminIndustryTemplates || []).map(item => item.category || '공통')));
    if (!categories.includes('공통')) categories.unshift('공통');
    if (selectedCategory && !categories.includes(selectedCategory)) categories.push(selectedCategory);
    categoryEl.innerHTML = '';
    categories.forEach(category => {
        const option = document.createElement('option');
        option.value = category;
        option.innerText = category;
        categoryEl.appendChild(option);
    });
    categoryEl.value = selectedCategory || '공통';
}
window.renderAdminIndustryCategoryOptions = renderAdminIndustryCategoryOptions;

function renderIndustryTemplateList() {
    const listEl = document.getElementById('admin-industry-template-list');
    if (!listEl) return;
    if (!adminIndustryTemplates.length) {
        listEl.innerHTML = '<div style="padding:18px; color:var(--muted); font-size:13px; text-align:center; border:1px dashed var(--border); border-radius:var(--radius-md);">등록된 업종 템플릿이 없습니다.</div>';
        return;
    }
    listEl.innerHTML = '';
    adminIndustryTemplates.forEach(item => {
        const btn = document.createElement('button');
        btn.type = 'button';
        const isActive = selectedIndustryKey === item.industry_key;
        btn.style.cssText = 'width:100%; padding:11px 12px; border-radius:12px; border:1px solid ' + (isActive ? 'rgba(125,211,252,.72)' : 'rgba(71,85,105,.72)') + '; background:' + (isActive ? 'linear-gradient(135deg, rgba(30,41,59,.96), rgba(15,23,42,.98))' : 'rgba(15,23,42,.76)') + '; color:var(--text); display:flex; flex-direction:column; align-items:flex-start; gap:4px; cursor:pointer; font-size:12px; text-align:left; box-shadow:' + (isActive ? '0 0 0 1px rgba(125,211,252,.18), 0 10px 22px rgba(0,0,0,.22)' : 'none') + ';';
        btn.innerHTML = '<strong style="font-size:13px; color:' + (item.is_active ? 'var(--text)' : 'var(--muted)') + ';">' + escapeHtml(item.label) + '</strong><span style="font-size:11px; color:var(--muted);">' + escapeHtml(item.category || '기타') + ' · ' + escapeHtml(item.industry_key) + (item.is_active ? '' : ' · 비활성') + '</span>';
        btn.onclick = () => selectIndustryTemplate(item.industry_key);
        listEl.appendChild(btn);
    });
}

async function loadIndustryTemplates() {
    const listEl = document.getElementById('admin-industry-template-list');
    if (listEl) listEl.innerHTML = '<div style="padding:18px; color:var(--muted); font-size:13px;">업종 템플릿을 불러오는 중...</div>';
    try {
        const response = await fetchWithAuth('/api/admin/industry-templates');
        const res = await response.json();
        if (!response.ok || !res.ok) throw new Error(res.detail || res.message || '업종 템플릿 조회 실패');
        adminIndustryTemplates = res.data || [];
        if (selectedIndustryKey && !adminIndustryTemplates.some(item => item.industry_key === selectedIndustryKey)) {
            selectedIndustryKey = null;
        }
        if (!selectedIndustryKey && adminIndustryTemplates.length) selectedIndustryKey = adminIndustryTemplates[0].industry_key;
        renderIndustryTemplateList();
        if (selectedIndustryKey) selectIndustryTemplate(selectedIndustryKey);
    } catch (err) {
        if (listEl) listEl.innerHTML = '<div style="padding:18px; color:var(--danger); font-size:13px;">' + escapeHtml(err.message) + '</div>';
    }
}
window.loadIndustryTemplates = loadIndustryTemplates;

function selectIndustryTemplate(industryKey) {
    selectedIndustryKey = industryKey;
    const item = adminIndustryTemplates.find(v => v.industry_key === industryKey);
    renderIndustryTemplateList();
    const empty = document.getElementById('admin-industry-empty');
    const editor = document.getElementById('admin-industry-editor');
    if (!item) {
        if (empty) empty.style.display = 'block';
        if (editor) editor.style.display = 'none';
        return;
    }
    if (empty) empty.style.display = 'none';
    if (editor) editor.style.display = 'flex';
    renderAdminIndustryCategoryOptions(item.category || '공통');
    document.getElementById('admin-industry-label').value = item.label || '';
    document.getElementById('admin-industry-category').value = item.category || '공통';
    document.getElementById('admin-industry-sort').value = item.sort_order ?? 0;
    document.getElementById('admin-industry-active').value = item.is_active ? 'true' : 'false';
    document.getElementById('admin-industry-flow').value = item.content_flow || '';
    document.getElementById('admin-industry-guidance').value = item.prompt_guidance || '';
    document.getElementById('admin-industry-keywords').value = item.keyword_hint || '';
    document.getElementById('admin-industry-tone').value = item.tone_hint || '';
    document.getElementById('admin-industry-avoid').value = item.avoid_hint || '';
    const statusEl = document.getElementById('admin-industry-status');
    if (statusEl) {
        statusEl.style.color = 'var(--muted)';
        statusEl.innerText = item.industry_key + ' · 마지막 수정: ' + (item.updated_at || '-');
    }
}
window.selectIndustryTemplate = selectIndustryTemplate;

function getSelectedIndustryTemplate() {
    return adminIndustryTemplates.find(item => item.industry_key === selectedIndustryKey);
}

function getIndustrySaveMethod() {
    return getSelectedIndustryTemplate() ? 'PUT' : 'POST';
}

function getIndustrySaveUrl() {
    if (getIndustrySaveMethod() === 'POST') return '/api/admin/industry-templates';
    return '/api/admin/industry-templates/' + encodeURIComponent(selectedIndustryKey);
}

function createNewIndustryTemplate() {
    const key = prompt('새 업종 키를 입력하세요. 예: bathroom_remodel');
    if (!key) return;
    selectedIndustryKey = key.trim().toLowerCase().replace(/\s+/g, '_');
    const empty = document.getElementById('admin-industry-empty');
    const editor = document.getElementById('admin-industry-editor');
    if (empty) empty.style.display = 'none';
    if (editor) editor.style.display = 'flex';
    renderAdminIndustryCategoryOptions('공통');
    document.getElementById('admin-industry-label').value = '';
    document.getElementById('admin-industry-category').value = '공통';
    document.getElementById('admin-industry-sort').value = adminIndustryTemplates.length + 1;
    document.getElementById('admin-industry-active').value = 'true';
    document.getElementById('admin-industry-flow').value = '';
    document.getElementById('admin-industry-guidance').value = '';
    document.getElementById('admin-industry-keywords').value = '';
    document.getElementById('admin-industry-tone').value = '';
    document.getElementById('admin-industry-avoid').value = '';
    const statusEl = document.getElementById('admin-industry-status');
    if (statusEl) statusEl.textContent = '새 업종 작성 후 저장을 누르면 목록에 추가됩니다.';
}
window.createNewIndustryTemplate = createNewIndustryTemplate;

async function purgeIndustryTemplate() {
    if (!selectedIndustryKey) return;
    if (!confirm('선택한 업종을 목록에서 제거할까요?')) return;
    const statusEl = document.getElementById('admin-industry-status');
    try {
        const response = await fetchWithAuth('/api/admin/industry-templates/' + encodeURIComponent(selectedIndustryKey) + '/remove', { method: 'POST' });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.detail || data.message || '처리 실패');
        selectedIndustryKey = null;
        if (statusEl) statusEl.textContent = data.message || '처리되었습니다.';
        await loadIndustryTemplates();
    } catch (err) {
        if (statusEl) statusEl.textContent = '처리 실패: ' + err.message;
    }
}
window.purgeIndustryTemplate = purgeIndustryTemplate;

async function saveIndustryOrder() {
    if (!selectedIndustryKey) {
        alert('순서를 바꿀 업종을 먼저 선택한 뒤 정렬 값을 입력해 주세요.');
        return;
    }
    await saveIndustryTemplate();
}
window.saveIndustryOrder = saveIndustryOrder;

async function saveIndustryTemplate() {
    if (!selectedIndustryKey) {
        alert('저장할 업종을 선택해 주세요.');
        return;
    }
    const statusEl = document.getElementById('admin-industry-status');
    const payload = {
        label: document.getElementById('admin-industry-label').value.trim(),
        category: document.getElementById('admin-industry-category').value.trim(),
        sort_order: parseInt(document.getElementById('admin-industry-sort').value || '0', 10),
        is_active: document.getElementById('admin-industry-active').value === 'true',
        content_flow: document.getElementById('admin-industry-flow').value.trim(),
        prompt_guidance: document.getElementById('admin-industry-guidance').value.trim(),
        keyword_hint: document.getElementById('admin-industry-keywords').value.trim(),
        tone_hint: document.getElementById('admin-industry-tone').value.trim(),
        avoid_hint: document.getElementById('admin-industry-avoid').value.trim()
    };
    const method = getIndustrySaveMethod();
    if (method === 'POST') payload.industry_key = selectedIndustryKey;
    if (statusEl) {
        statusEl.style.color = 'var(--warning)';
        statusEl.innerText = '저장 중...';
    }
    try {
        const response = await fetchWithAuth(getIndustrySaveUrl(), {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (!response.ok || !res.ok) throw new Error(res.detail || res.message || '업종 템플릿 저장 실패');
        selectedIndustryKey = res.data.industry_key;
        await loadIndustryTemplates();
        const successMessage = method === 'POST' ? '새 업종이 추가되었습니다.' : '업종별 관리 설정이 저장되었습니다.';
        if (statusEl) {
            statusEl.style.color = 'var(--success)';
            statusEl.innerText = successMessage;
        }
        showToast(successMessage);
    } catch (err) {
        if (statusEl) {
            statusEl.style.color = 'var(--danger)';
            statusEl.innerText = err.message;
        }
        alert(err.message);
    }
}
window.saveIndustryTemplate = saveIndustryTemplate;

async function loadAdminStats() {
    try {
        const response = await fetchWithAuth('/api/admin/stats');
        const res = await response.json();
        if (!response.ok || !res.ok) throw new Error(res.detail || res.message || '통계 조회 실패');
        
        const data = res.data || {};
        
        const usersEl = document.getElementById('stat-total-users');
        if (usersEl) usersEl.innerText = `${data.total_users || 0}명`;
        
        const activeUsersEl = document.getElementById('stat-active-users');
        if (activeUsersEl) activeUsersEl.innerText = `${data.active_users || 0}명`;
        
        const activeRateEl = document.getElementById('stat-active-rate');
        if (activeRateEl) activeRateEl.innerText = `${data.active_rate || 0}%`;
        
        const projectsEl = document.getElementById('stat-total-projects');
        if (projectsEl) projectsEl.innerText = `${data.total_projects || 0}개`;
        
        const logsEl = document.getElementById('stat-total-logs');
        if (logsEl) logsEl.innerText = `${data.total_logs || 0}건`;
        
        const generatorCountEl = document.getElementById('stat-total-generators');
        if (generatorCountEl) generatorCountEl.innerText = `${data.generator_usage || 0}회`;
        
        const paidUsersEl = document.getElementById('stat-paid-users');
        if (paidUsersEl) paidUsersEl.innerText = `${data.paid_users || 0}명`;
        
        const paidRatioEl = document.getElementById('stat-paid-ratio');
        if (paidRatioEl) paidRatioEl.innerText = `${data.paid_ratio || 0}%`;
        
        const newUsersTodayEl = document.getElementById('stat-new-users-today');
        if (newUsersTodayEl) newUsersTodayEl.innerText = `${data.new_users_today || 0}명`;
        
        // Render system activity logs table
        const logsTbody = document.getElementById('admin-activity-logs-tbody');
        if (logsTbody) {
            logsTbody.innerHTML = '';
            const logs = data.recent_logs || [];
            if (logs.length === 0) {
                logsTbody.innerHTML = '<tr><td colspan="4" style="color:var(--muted); padding:16px; text-align:center;">최근 활동 기록이 없습니다.</td></tr>';
            } else {
                logs.forEach(l => {
                    const tr = document.createElement('tr');
                    tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                    
                    let actLabel = l.action;
                    let color = 'var(--text)';
                    if (l.action === 'login') { actLabel = '🔑 로그인'; color = 'var(--success)'; }
                    else if (l.action === 'logout') { actLabel = '🚪 로그아웃'; color = 'var(--muted)'; }
                    else if (l.action === 'join') { actLabel = '📝 회원가입'; color = 'var(--accent)'; }
                    else if (l.action === 'project_create') { actLabel = '🚀 프로젝트 생성'; color = '#ff7300'; }
                    else if (l.action === 'project_update') { actLabel = '💾 프로젝트 저장'; color = '#ffb300'; }
                    else if (l.action === 'prompt_generate') { actLabel = '🤖 AI 프롬프트 빌드'; color = '#e066ff'; }
                    else if (l.action === 'result_parse') { actLabel = '✂️ 채널 파싱 분리'; color = '#00e6ff'; }
                    else if (l.action === 'preview_open') { actLabel = '👁️ 미리보기 열기'; color = '#00c73c'; }
                    else if (l.action === 'html_copy') { actLabel = '📋 클립보드 복사'; color = '#8d6e63'; }
                    else if (l.action === 'platform_open') { actLabel = '🔗 플랫폼 이동'; color = '#9fa8da'; }
                    
                    let metaText = '';
                    if (l.metadata_json) {
                        try {
                            const m = JSON.parse(l.metadata_json);
                            if (m.channel) metaText = ` <span style="font-size:10px; color:var(--muted); padding:1px 4px; background:rgba(255,255,255,0.04); border-radius:2px;">${m.channel}</span>`;
                        } catch(e) {}
                    }
                    
                    tr.innerHTML = `
                        <td style="padding:10px 12px; color:var(--muted); font-size:11px;">${l.created_at}</td>
                        <td style="padding:10px 12px; font-weight:600; color:var(--text);">${l.username}</td>
                        <td style="padding:10px 12px; color:${color}; font-weight:500;">${actLabel}${metaText}</td>
                        <td style="padding:10px 12px; color:var(--muted); font-family:monospace; font-size:11px;">${l.ip_address}</td>
                    `;
                    logsTbody.appendChild(tr);
                });
            }
        }
        
        loadAdminCharts(data);
    } catch (err) {
        log(`[관리자] 지표 조회 실패: ${err.message}`, 'error');
    }
}
window.loadAdminStats = loadAdminStats;

async function loadAdminUsers() {
    const tbody = document.getElementById('admin-users-tbody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="8" style="color:var(--muted); text-align:center; padding:20px;">회원 목록 조회 중...</td></tr>';
    
    try {
        const response = await fetchWithAuth('/api/admin/users');
        const res = await response.json();
        if (!response.ok || !res.ok) throw new Error(res.detail || res.message || '회원 목록 조회 실패');
        
        const list = res.data || [];
        tbody.innerHTML = '';
        if (list.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="color:var(--muted); text-align:center; padding:20px;">가입된 회원이 없습니다.</td></tr>';
        } else {
            list.forEach(u => {
                const tr = document.createElement('tr');
                tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                tr.style.height = '48px';
                
                const tierColor = u.tier === 'paid' ? 'var(--warning)' : 'var(--text-muted)';
                const roleColor = u.role === 'admin' ? 'var(--accent)' : 'var(--text-muted)';
                const statusColor = u.is_active ? 'var(--success)' : 'var(--danger)';
                const statusTxt = u.is_active ? '정상' : '정지';
                
                tr.innerHTML = `
                    <td style="padding:8px 12px; text-align:center;"><input type="checkbox" name="admin-user-chk" value="${u.id}" style="margin:0;"></td>
                    <td style="padding:8px 12px; font-weight:700; color:var(--text);">${u.id}</td>
                    <td style="padding:8px 12px;">
                        <a href="javascript:void(0)" onclick="showUserHistory(${u.id}, '${u.username}')" style="color:var(--focus); font-weight:700; text-decoration:underline;">${u.username}</a>
                    </td>
                    <td style="padding:8px 12px; text-align:center; font-weight:700; color:${tierColor};">${u.tier.toUpperCase()}</td>
                    <td style="padding:8px 12px; text-align:center; font-weight:600; color:${roleColor};">${u.role.toUpperCase()}</td>
                    <td style="padding:8px 12px; text-align:center; font-weight:600; color:${statusColor};">${statusTxt}</td>
                    <td style="padding:8px 12px; color:var(--muted); font-size:11px;">${u.created_at}</td>
                    <td style="padding:8px 12px; text-align:center;">
                        <div style="display:flex; gap:4px; justify-content:center;">
                            <button type="button" class="btn-header" style="padding:3px 7px; font-size:10px; height:auto; width:auto; border-color:${u.is_active ? 'var(--danger)' : 'var(--success)'}; color:${u.is_active ? 'var(--danger)' : 'var(--success)'};" onclick="toggleUserStatus(${u.id}, ${u.is_active}, '${u.username}')">${u.is_active ? '차단' : '해제'}</button>
                            <button type="button" class="btn-header" style="padding:3px 7px; font-size:10px; height:auto; width:auto;" onclick="changeUserRole(${u.id}, '${u.role}')">권한</button>
                            <button type="button" class="btn-header" style="padding:3px 7px; font-size:10px; height:auto; width:auto;" onclick="changeUserTier(${u.id}, '${u.tier}')">등급</button>
                        </div>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" style="color:var(--danger); text-align:center; padding:20px;">${err.message}</td></tr>`;
    }
}
window.loadAdminUsers = loadAdminUsers;

async function deleteSelectedUsers() {
    const checked = Array.from(document.querySelectorAll('input[name="admin-user-chk"]:checked')).map(chk => Number(chk.value));
    if (checked.length === 0) {
        alert('삭제할 회원을 선택해 주세요.');
        return;
    }
    if (!confirm(`선택한 ${checked.length}명의 회원을 강제 탈퇴 처리하시겠습니까?\n프로젝트와 페르소나 데이터가 모두 영구 삭제됩니다.`)) {
        return;
    }
    
    log(`[관리자] 선택 회원 ${checked.length}명 강제 탈퇴 처리 진행 중...`);
    try {
        const response = await fetchWithAuth('/api/admin/users/bulk-delete', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_ids: checked })
        });
        const res = await response.json();
        if (response.ok && res.ok) {
            log(`선택한 회원 ${checked.length}명이 강제 탈퇴되었습니다.`, 'success');
            showToast('탈퇴 처리 완료');
            await loadAdminStats();
            await loadAdminUsers();
        } else {
            throw new Error(res.message || res.detail || '삭제 실패');
        }
    } catch (err) {
        log(`[관리자 오류] 회원 강제 탈퇴 실패: ${err.message}`, 'error');
        alert(`오류: ${err.message}`);
    }
}
window.deleteSelectedUsers = deleteSelectedUsers;

async function loadUserRankings() {
    const listEl = document.getElementById('admin-rankings-list');
    if (!listEl) return;
    listEl.innerHTML = '<div style="color:var(--muted); padding:10px; font-size:12px;">랭킹 분석 중...</div>';
    
    try {
        const response = await fetchWithAuth('/api/admin/rankings');
        const res = await response.json();
        if (!response.ok || !res.ok) throw new Error(res.detail || res.message || '랭킹 분석 실패');
        
        const data = res.data || {};
        const projects = data.projects_ranking || [];
        const duration = data.duration_ranking || [];
        
        let html = '<div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:6px;">';
        
        // Project Ranking
        html += '<div style="background:rgba(255,255,255,0.01); border:1px solid var(--border); border-radius:var(--radius-sm); padding:12px;">';
        html += '<strong style="color:var(--accent); font-size:12px; display:block; border-bottom:1px solid var(--border); padding-bottom:6px; margin-bottom:8px;">📁 프로젝트 최다 생성</strong>';
        if (projects.length === 0) {
            html += '<div style="color:var(--muted); font-size:11px; padding:10px; text-align:center;">생성 기록 없음</div>';
        } else {
            projects.forEach((item, index) => {
                html += `
                    <div style="display:flex; justify-content:space-between; font-size:11px; padding:4px 0;">
                        <span><strong style="color:var(--text); margin-right:4px;">#${index+1}</strong> ${item.username}</span>
                        <span style="color:var(--muted);">${item.project_count}개 생성</span>
                    </div>
                `;
            });
        }
        html += '</div>';
        
        // Duration Ranking
        html += '<div style="background:rgba(255,255,255,0.01); border:1px solid var(--border); border-radius:var(--radius-sm); padding:12px;">';
        html += '<strong style="color:var(--success); font-size:12px; display:block; border-bottom:1px solid var(--border); padding-bottom:6px; margin-bottom:8px;">⏱️ 누적 사용시간 (최근 30일)</strong>';
        if (duration.length === 0) {
            html += '<div style="color:var(--muted); font-size:11px; padding:10px; text-align:center;">기록 없음</div>';
        } else {
            duration.forEach((item, index) => {
                const hour = (item.total_seconds / 3600).toFixed(1);
                html += `
                    <div style="display:flex; justify-content:space-between; font-size:11px; padding:4px 0;">
                        <span><strong style="color:var(--text); margin-right:4px;">#${index+1}</strong> ${item.username}</span>
                        <span style="color:var(--muted);">${hour}시간 사용</span>
                    </div>
                `;
            });
        }
        html += '</div></div>';
        
        listEl.innerHTML = html;
        
    } catch (err) {
        listEl.innerHTML = `<div style="color:var(--danger); padding:10px; font-size:12px;">${err.message}</div>`;
    }
}
window.loadUserRankings = loadUserRankings;

function loadAdminCharts(data) {
    try {
        const signup = data.signup_trend_7d || [];
        const days = signup.map(s => s.day);
        const counts = signup.map(s => s.count);
        drawVerticalBarChart('chart-signup-canvas', days, counts, '가입 회원수', '#ff7300');
        
        const rank = data.ranking_data || [];
        const usernames = rank.map(r => r.username);
        const projectCounts = rank.map(r => r.project_count);
        const usageTimes = rank.map(r => r.total_duration_seconds);
        
        drawHorizontalBarChart('chart-user-proj-canvas', usernames, projectCounts, '프로젝트 수', '#0088ff', '개');
        drawHorizontalBarChart('chart-user-time-canvas', usernames, usageTimes, '누적 사용시간', '#00e6ff', '초');
    } catch (err) {
        console.error('Failed to render admin charts:', err);
    }
}
window.loadAdminCharts = loadAdminCharts;

function drawVerticalBarChart(canvasId, labels, data, labelName, colorHex) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    
    const width = rect.width;
    const height = rect.height;
    
    ctx.clearRect(0, 0, width, height);
    
    if (!data || data.length === 0) {
        ctx.fillStyle = '#6e8294';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('데이터가 없습니다.', width / 2, height / 2);
        return;
    }
    
    const paddingLeft = 35;
    const paddingRight = 15;
    const paddingTop = 25;
    const paddingBottom = 30;
    
    const chartWidth = width - paddingLeft - paddingRight;
    const chartHeight = height - paddingTop - paddingBottom;
    
    const maxVal = Math.max(...data, 1);
    const colCount = data.length;
    const colWidth = chartWidth / colCount;
    const barWidth = colWidth * 0.55;
    
    ctx.strokeStyle = 'rgba(255,255,255,0.06)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(paddingLeft, paddingTop);
    ctx.lineTo(paddingLeft, height - paddingBottom);
    ctx.lineTo(width - paddingRight, height - paddingBottom);
    ctx.stroke();
    
    const gridRows = 4;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#6e8294';
    ctx.font = '9px sans-serif';
    for (let i = 0; i <= gridRows; i++) {
        const val = Math.round((maxVal / gridRows) * i);
        const yPos = height - paddingBottom - (chartHeight / gridRows) * i;
        ctx.fillText(String(val), paddingLeft - 6, yPos);
        
        if (i > 0) {
            ctx.strokeStyle = 'rgba(255,255,255,0.03)';
            ctx.beginPath();
            ctx.moveTo(paddingLeft, yPos);
            ctx.lineTo(width - paddingRight, yPos);
            ctx.stroke();
        }
    }
    
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (let i = 0; i < colCount; i++) {
        const val = data[i];
        const label = labels[i];
        const barHeight = (val / maxVal) * chartHeight;
        
        const xPos = paddingLeft + (i * colWidth) + (colWidth - barWidth) / 2;
        const yPos = height - paddingBottom - barHeight;
        
        const grad = ctx.createLinearGradient(xPos, yPos, xPos, yPos + barHeight);
        grad.addColorStop(0, colorHex);
        grad.addColorStop(1, 'rgba(255,115,0,0.02)');
        
        ctx.fillStyle = grad;
        ctx.beginPath();
        if (barHeight > 5) {
            ctx.roundRect(xPos, yPos, barWidth, barHeight, [4, 4, 0, 0]);
        } else {
            ctx.rect(xPos, yPos, barWidth, Math.max(1, barHeight));
        }
        ctx.fill();
        
        ctx.fillStyle = '#6e8294';
        ctx.fillText(label, xPos + barWidth / 2, height - paddingBottom + 6);
        
        if (val > 0) {
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 9px sans-serif';
            ctx.fillText(String(val), xPos + barWidth / 2, yPos - 12);
        }
    }
}
window.drawVerticalBarChart = drawVerticalBarChart;

function drawHorizontalBarChart(canvasId, labels, data, labelName, colorHex, unit = '') {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    
    const width = rect.width;
    const height = rect.height;
    
    ctx.clearRect(0, 0, width, height);
    
    if (!data || data.length === 0) {
        ctx.fillStyle = '#6e8294';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('데이터가 없습니다.', width / 2, height / 2);
        return;
    }
    
    const paddingLeft = 60;
    const paddingRight = 55;
    const paddingTop = 15;
    const paddingBottom = 15;
    
    const chartWidth = width - paddingLeft - paddingRight;
    const chartHeight = height - paddingTop - paddingBottom;
    
    const maxVal = Math.max(...data, 1);
    const rowCount = data.length;
    const rowHeight = chartHeight / rowCount;
    const barHeight = rowHeight * 0.55;
    
    ctx.textBaseline = 'middle';
    
    for (let i = 0; i < rowCount; i++) {
        const val = data[i];
        const label = labels[i];
        const barWidth = (val / maxVal) * chartWidth;
        
        const xPos = paddingLeft;
        const yPos = paddingTop + (i * rowHeight) + (rowHeight - barHeight) / 2;
        
        const grad = ctx.createLinearGradient(xPos, yPos, xPos + barWidth, yPos);
        grad.addColorStop(0, 'rgba(0,136,255,0.02)');
        grad.addColorStop(1, colorHex);
        
        ctx.fillStyle = grad;
        ctx.beginPath();
        if (barWidth > 5) {
            ctx.roundRect(xPos, yPos, barWidth, barHeight, [0, 4, 4, 0]);
        } else {
            ctx.rect(xPos, yPos, Math.max(1, barWidth), barHeight);
        }
        ctx.fill();
        
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 10px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(label, paddingLeft - 8, yPos + barHeight / 2);
        
        ctx.fillStyle = '#6e8294';
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'left';
        
        let displayVal = val;
        if (unit === '초') {
            const min = Math.floor(val / 60);
            if (min >= 60) {
                displayVal = `${(val / 3600).toFixed(1)}시간`;
            } else {
                displayVal = `${min}분`;
            }
        } else {
            displayVal = `${val}${unit}`;
        }
        ctx.fillText(displayVal, xPos + barWidth + 6, yPos + barHeight / 2);
    }
}
window.drawHorizontalBarChart = drawHorizontalBarChart;

async function showUserHistory(userId, username) {
    document.getElementById('admin-target-user-name').innerText = username;
    const projList = document.getElementById('admin-user-projects-list');
    const personaList = document.getElementById('admin-user-personas-list');
    const sessTbody = document.getElementById('admin-user-sessions-tbody');
    const logsList = document.getElementById('admin-user-logs-list');
    
    projList.innerHTML = '<div style="color:var(--muted); padding:12px;">프로젝트 조회 중...</div>';
    personaList.innerHTML = '<div style="color:var(--muted); padding:12px;">페르소나 조회 중...</div>';
    sessTbody.innerHTML = '<tr><td colspan="4" style="color:var(--muted); padding:12px; text-align:center;">세션 기록 조회 중...</td></tr>';
    logsList.innerHTML = '<div style="color:var(--muted); padding:12px;">활동 로그 조회 중...</div>';
    
    document.getElementById('admin-user-detail-modal').style.display = 'flex';
    
    switchDetailTab('proj');
    
    try {
        const [resHistory, resProj, resPersonas] = await Promise.all([
            fetchWithAuth(`/api/admin/users/${userId}/history`),
            fetchWithAuth(`/api/admin/users/${userId}/projects`),
            fetchWithAuth(`/api/admin/users/${userId}/personas`)
        ]);
        
        if (resHistory.ok && resProj.ok && resPersonas.ok) {
            const historyJson = await resHistory.json();
            const projJson = await resProj.json();
            const personaJson = await resPersonas.json();
            
            if (historyJson.ok && projJson.ok && personaJson.ok) {
                const hData = historyJson.data;
                const pData = projJson.data;
                const personas = personaJson.data || [];
                
                // 7-1. 프로젝트 탭 렌더링
                projList.innerHTML = '';
                if (pData.length === 0) {
                    projList.innerHTML = '<div style="color:var(--muted); padding:16px; text-align:center; font-size:12px;">작업 프로젝트가 없습니다.</div>';
                } else {
                    pData.forEach(p => {
                        const div = document.createElement('div');
                        div.style.padding = '10px 14px';
                        div.style.borderBottom = '1px solid var(--border)';
                        div.style.display = 'flex';
                        div.style.justifyContent = 'space-between';
                        div.style.alignItems = 'center';
                        div.style.fontSize = '12px';
                        
                        div.innerHTML = `
                            <div>
                                <strong style="color:var(--text);">${p.title}</strong>
                                <div style="font-size:11px; color:var(--muted); margin-top:3px;">업체: ${p.company_name}</div>
                            </div>
                            <span style="color:var(--muted); font-size:11px;">${p.updated_at}</span>
                        `;
                        projList.appendChild(div);
                    });
                }

                personaList.innerHTML = '';
                if (personas.length === 0) {
                    personaList.innerHTML = '<div style="color:var(--muted); padding:16px; text-align:center; font-size:12px;">저장된 사용자 페르소나가 없습니다.</div>';
                } else {
                    personas.forEach(persona => {
                        const card = document.createElement('div');
                        card.style.padding = '14px';
                        card.style.border = '1px solid var(--border)';
                        card.style.borderRadius = 'var(--radius-sm)';
                        card.style.background = 'rgba(255,255,255,0.02)';

                        const title = document.createElement('strong');
                        title.style.color = 'var(--accent)';
                        title.textContent = persona.company_name;

                        const phone = document.createElement('div');
                        phone.style.cssText = 'font-size:11px; color:var(--success); margin-top:5px;';
                        phone.textContent = `전화번호: ${persona.phone_number}`;

                        const keywords = document.createElement('div');
                        keywords.style.cssText = 'font-size:11px; color:var(--warning); margin:6px 0;';
                        keywords.textContent = (persona.keywords || []).length ? `키워드: ${persona.keywords.join(', ')}` : '키워드: 없음';

                        const content = document.createElement('div');
                        content.style.cssText = 'font-size:12px; color:var(--text); white-space:pre-wrap; line-height:1.65;';
                        content.textContent = persona.content;

                        const updated = document.createElement('div');
                        updated.style.cssText = 'font-size:10px; color:var(--muted); margin-top:8px; text-align:right;';
                        updated.textContent = `최근 수정: ${persona.updated_at}`;

                        card.append(title, phone, keywords, content, updated);
                        personaList.appendChild(card);
                    });
                }
                
                // 7-2. 세션 탭 렌더링
                sessTbody.innerHTML = '';
                if (hData.sessions.length === 0) {
                    sessTbody.innerHTML = '<tr><td colspan="4" style="color:var(--muted); padding:16px; text-align:center;">세션 접속 기록이 없습니다.</td></tr>';
                } else {
                    hData.sessions.forEach(s => {
                        const min = Math.floor(s.duration_seconds / 60);
                        const durationTxt = s.duration_seconds > 0 ? `${min}분` : '1분 미만';
                        
                        const tr = document.createElement('tr');
                        tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                        tr.innerHTML = `
                            <td style="padding:8px; color:var(--text);">${s.login_at}</td>
                            <td style="padding:8px; color:var(--muted);">${s.logout_at || '종료 추정 (미명시)'}</td>
                            <td style="padding:8px; text-align:right; font-weight:600; color:var(--success);">${durationTxt}</td>
                            <td style="padding:8px; color:var(--muted); font-family:monospace;">${s.ip_address}</td>
                        `;
                        sessTbody.appendChild(tr);
                    });
                }
                
                // 7-3. 활동 로그 탭 렌더링
                logsList.innerHTML = '';
                if (hData.logs.length === 0) {
                    logsList.innerHTML = '<div style="color:var(--muted); padding:16px; text-align:center; font-size:12px;">활동 로그가 없습니다.</div>';
                } else {
                    hData.logs.forEach(l => {
                        const div = document.createElement('div');
                        div.style.padding = '8px 12px';
                        div.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                        div.style.fontSize = '12px';
                        div.style.display = 'flex';
                        div.style.justifyContent = 'space-between';
                        div.style.alignItems = 'start';
                        
                        let actionLabel = l.action;
                        let color = 'var(--text)';
                        if (l.action === 'login') { actionLabel = '🔑 로그인'; color = 'var(--success)'; }
                        else if (l.action === 'logout') { actionLabel = '🚪 로그아웃'; color = 'var(--muted)'; }
                        else if (l.action === 'join') { actionLabel = '📝 회원가입'; color = 'var(--accent)'; }
                        else if (l.action === 'project_create') { actionLabel = '🚀 프로젝트 생성'; color = '#ff7300'; }
                        else if (l.action === 'project_update') { actionLabel = '💾 프로젝트 저장'; color = '#ffb300'; }
                        else if (l.action === 'prompt_generate') { actionLabel = '🤖 AI 프롬프트 빌드'; color = '#e066ff'; }
                        else if (l.action === 'result_parse') { actionLabel = '✂️ 채널 파싱 분리'; color = '#00e6ff'; }
                        else if (l.action === 'preview_open') { actionLabel = '👁️ 미리보기 열기'; color = '#00c73c'; }
                        else if (l.action === 'html_copy') { actionLabel = '📋 클립보드 복사'; color = '#8d6e63'; }
                        else if (l.action === 'platform_open') { actionLabel = '🔗 플랫폼 이동'; color = '#9fa8da'; }
                        
                        let metaTxt = '';
                        if (l.metadata_json) {
                            try {
                                const m = JSON.parse(l.metadata_json);
                                if (m.channel) metaTxt = ` <span style="color:var(--muted); font-size:10px; padding:2px 5px; background:rgba(255,255,255,0.04); border-radius:3px;">${m.channel}</span>`;
                            } catch(e) {}
                        }
                        
                        div.innerHTML = `
                            <div>
                                <span style="font-weight:600; color:${color};">${actionLabel}</span>
                                ${metaTxt}
                                <div style="font-size:10px; color:var(--muted); margin-top:3px;">IP: ${l.ip_address} | ${l.user_agent.substring(0, 45)}...</div>
                            </div>
                            <span style="font-size:11px; color:var(--muted);">${l.created_at}</span>
                        `;
                        logsList.appendChild(div);
                    });
                }
            }
        }
    } catch (err) {
        console.error(err);
        projList.innerHTML = '<div style="color:var(--danger); padding:12px;">데이터 조회 중 오류 발생</div>';
    }
}
window.showUserHistory = showUserHistory;

function closeAdminUserDetailModal() {
    const modal = document.getElementById('admin-user-detail-modal');
    if (modal) modal.style.display = 'none';
}
window.closeAdminUserDetailModal = closeAdminUserDetailModal;

function switchDetailTab(tabName) {
    activeDetailTab = tabName;
    
    const buttons = ['proj', 'personas', 'sess', 'logs'];
    buttons.forEach(b => {
        const btn = document.getElementById(`tab-detail-${b}`);
        const pane = document.getElementById(`pane-detail-${b}`);
        if (btn && pane) {
            if (b === tabName) {
                btn.classList.add('active');
                pane.style.display = 'block';
            } else {
                btn.classList.remove('active');
                pane.style.display = 'none';
            }
        }
    });
}
window.switchDetailTab = switchDetailTab;

async function toggleUserStatus(userId, isCurrentActive, username) {
    const newActiveState = !isCurrentActive;
    const stateTxt = newActiveState ? '활성화' : '비활성화';
    
    if (!confirm(`[${username}] 계정을 정말로 ${stateTxt} 하시겠습니까?`)) {
        return;
    }
    
    log(`[관리자] [${username}] 계정 상태 ${stateTxt} 적용 중...`);
    try {
        const response = await fetchWithAuth(`/api/admin/users/${userId}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_active: newActiveState })
        });
        
        const res = await response.json();
        if (response.ok && res.ok) {
            log(`[${username}] 계정이 ${stateTxt} 되었습니다.`, 'success');
            if (typeof showToast === 'function') {
                showToast(`${stateTxt} 처리 완료`);
            }
            
            await loadAdminStats();
            await loadAdminUsers();
        } else {
            throw new Error(res.message || res.detail || '상태 제어 실패');
        }
    } catch (err) {
        log(`[관리자 오류] 계정 상태 변경 실패: ${err.message}`, 'error');
        alert(`오류: ${err.message}`);
    }
}
window.toggleUserStatus = toggleUserStatus;

async function changeUserRole(userId, currentRole) {
    const newRole = currentRole === 'admin' ? 'user' : 'admin';
    const roleTxt = newRole === 'admin' ? 'ADMIN(관리자)' : 'USER(일반 사용자)';
    
    if (!confirm(`이 계정의 권한을 정말로 ${roleTxt}(으)로 변경하시겠습니까?`)) {
        return;
    }
    
    log(`[관리자] 계정 ID [${userId}] 권한을 ${newRole}로 변경 요청 중...`);
    try {
        const response = await fetchWithAuth(`/api/admin/users/${userId}/role`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role: newRole })
        });
        
        const res = await response.json();
        if (response.ok && res.ok) {
            log(`계정 권한이 ${roleTxt}(으)로 변경 완료되었습니다.`, 'success');
            if (typeof showToast === 'function') {
                showToast('권한 변경 완료');
            }
            
            await loadAdminStats();
            await loadAdminUsers();
        } else {
            throw new Error(res.message || res.detail || '권한 변경 실패');
        }
    } catch (err) {
        log(`[관리자 오류] 권한 변경 실패: ${err.message}`, 'error');
        alert(`오류: ${err.message}`);
    }
}
window.changeUserRole = changeUserRole;

async function changeUserTier(userId, currentTier) {
    const newTier = currentTier === 'paid' ? 'free' : 'paid';
    const tierTxt = newTier === 'paid' ? 'PREMIUM(결제 사용자)' : 'FREE(무료 사용자)';
    
    if (!confirm(`이 계정의 등급을 정말로 ${tierTxt}(으)로 변경하시겠습니까?`)) {
        return;
    }
    
    log(`[관리자] 계정 ID [${userId}] 등급을 ${newTier}로 변경 요청 중...`);
    try {
        const response = await fetchWithAuth(`/api/admin/users/${userId}/tier`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tier: newTier })
        });
        
        const res = await response.json();
        if (response.ok && res.ok) {
            log(`계정 등급이 ${tierTxt}(으)로 변경 완료되었습니다.`, 'success');
            if (typeof showToast === 'function') {
                showToast('등급 변경 완료');
            }
            
            await loadAdminStats();
            await loadAdminUsers();
        } else {
            throw new Error(res.message || res.detail || '등급 변경 실패');
        }
    } catch (err) {
        log(`[관리자 오류] 등급 변경 실패: ${err.message}`, 'error');
        alert(`오류: ${err.message}`);
    }
}
window.changeUserTier = changeUserTier;
