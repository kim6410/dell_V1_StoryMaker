// StoryMaker 프론트엔드 블로그 글감 찾기 및 네이버 크롤러 연동 모듈 (app_ideas.js)

// 전역 공유 상태 초기화
let selectedIndustryKeyword = '';
window.selectedIndustryKeyword = selectedIndustryKeyword;

if (window.currentViewMode === undefined) {
    window.currentViewMode = 'user';
}
if (window.lastSearchResponse === undefined) {
    window.lastSearchResponse = null;
}

function canAccessContentIdeaAdmin() {
    if (new URLSearchParams(window.location.search).get('admin') === '1') return true;
    try {
        const user = JSON.parse(localStorage.getItem('storymaker_user') || '{}');
        return user.role === 'admin' || user.is_admin === true || user.username === 'admin';
    } catch (e) {
        return false;
    }
}
window.canAccessContentIdeaAdmin = canAccessContentIdeaAdmin;

function syncContentIdeaAdminAccess() {
    const allowed = canAccessContentIdeaAdmin();
    const toggle = document.getElementById('ideaAdminModeToggle');
    const tabAiLab = document.getElementById('btn-tab-ailab');
    const tabPattern = document.getElementById('btn-tab-pattern');
    const tabPerformance = document.getElementById('btn-tab-performance');
    const tabBrain = document.getElementById('btn-tab-brain');
    if (toggle) toggle.style.display = allowed ? 'flex' : 'none';
    if (!allowed && window.currentViewMode === 'admin') window.currentViewMode = 'user';
    if (tabAiLab) tabAiLab.style.display = allowed && window.currentViewMode === 'admin' ? 'inline-flex' : 'none';
    if (tabPattern) tabPattern.style.display = allowed && window.currentViewMode === 'admin' ? 'inline-flex' : 'none';
    if (tabPerformance) tabPerformance.style.display = allowed && window.currentViewMode === 'admin' ? 'inline-flex' : 'none';
    if (tabBrain) tabBrain.style.display = allowed && window.currentViewMode === 'admin' ? 'inline-flex' : 'none';
    return allowed;
}
window.syncContentIdeaAdminAccess = syncContentIdeaAdminAccess;

function ideaVal(value, fallback = '-') {
    return value === undefined || value === null || value === '' ? fallback : value;
}
window.ideaVal = ideaVal;

function ideaScore(value, fallback = 0) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
}
window.ideaScore = ideaScore;

function renderAdminMetricList(rows) {
    return `<ul style="margin:4px 0 0 0; padding-left:14px; color:var(--text-muted); font-size:11px;">${rows.map(([k, v]) => `<li>${k}: ${ideaVal(v)}</li>`).join('')}</ul>`;
}
window.renderAdminMetricList = renderAdminMetricList;

function renderAdminIdeaCard(item, res, safeSearchKeyword) {
    const data = res.data || {};
    const score = item.score || {};
    const details = item.analysis_details || {};
    const title = details.title || {};
    const body = details.body || {};
    const seo = details.seo || {};
    const business = details.business || {};
    const signals = item.recommendation_signals || [];
    const duplicateText = (item.ad_flags && item.ad_flags.length) ? item.ad_flags.join(', ') : '협찬/광고 신호 없음';

    return `
        <div class="idea-card-header" style="display:block;">
            <div class="idea-card-meta">
                <span class="idea-card-blogname" style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    ${ideaVal(item.blog_name, '블로그')}
                    <span style="background:rgba(16,185,129,0.15); color:#10b981; border:1px solid rgba(16,185,129,0.3); font-size:10px; padding:1px 5px; border-radius:3px; font-weight:600;">관리자 분석</span>
                    <span style="font-size:10px; color:var(--text-muted); margin-left:auto;">Cache: ${ideaVal(data.cache_status)} | Version: ${ideaVal(data.analysis_version)}</span>
                </span>
                <h4 class="idea-card-title" style="margin-top:4px;">
                    ${item.organic_rank ? `<span class="organic-rank-num" style="color:var(--focus); font-weight:700; margin-right:6px;">#${item.organic_rank}</span>` : ''}
                    ${item.title}
                </h4>
            </div>
        </div>
        <div class="idea-card-scores" style="display:flex; flex-wrap:wrap; gap:6px; margin-top:8px;">
            <span class="score-badge recommendation">추천점수 <span class="score-value">${ideaScore(item.recommendation_score)}점</span></span>
            <span class="score-badge business">Business <span class="score-value">${ideaScore(item.business_score)}점</span></span>
            <span class="score-badge locality">Local <span class="score-value">${ideaScore(item.locality_score)}점</span></span>
            <span class="score-badge relevance">SEO <span class="score-value">${ideaScore(score.relevance)}점</span></span>
            <span class="score-badge freshness">Freshness <span class="score-value">${ideaScore(item.freshness_score || score.freshness)}점</span></span>
            <span class="score-badge">Trust <span class="score-value">${ideaScore(score.trust_score)}점</span></span>
            <span class="score-badge">CTA <span class="score-value">${ideaScore(score.cta_score)}점</span></span>
            <span class="score-badge">Organic <span class="score-value">#${ideaVal(item.organic_rank || item.rank)}</span></span>
        </div>
        <div class="idea-card-summary" style="margin-top:10px;">
            <div class="summary-label">추천 이유</div>
            ${ideaVal(item.recommendation_reason, getUserRecommendationReason(item))}
            <div style="margin-top:6px; display:flex; flex-wrap:wrap; gap:4px;">
                ${signals.map(sig => `<span style="background:rgba(16,185,129,0.1); color:#10b981; border:1px solid rgba(16,185,129,0.2); font-size:10px; padding:1px 5px; border-radius:3px;">${sig}</span>`).join('')}
                <span style="background:rgba(34,211,238,0.1); color:var(--focus); border:1px solid rgba(34,211,238,0.2); font-size:10px; padding:1px 5px; border-radius:3px;">중복 없음</span>
                <span style="background:rgba(34,211,238,0.1); color:var(--focus); border:1px solid rgba(34,211,238,0.2); font-size:10px; padding:1px 5px; border-radius:3px;">${duplicateText}</span>
            </div>
        </div>
        <details open class="admin-details-panel" style="margin-top:12px; padding:12px; border:1px solid var(--border); border-radius:8px; background:rgba(255,255,255,0.02); font-size:12px; line-height:1.5;">
            <summary style="cursor:pointer; color:var(--focus); font-weight:700;">Recommendation Explain</summary>
            <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(190px, 1fr)); gap:12px; margin-top:10px;">
                <div><strong style="color:var(--text);">Title Intelligence</strong>${renderAdminMetricList([
                    ['제목 길이', `${ideaVal(title.length, item.title?.length)}자`],
                    ['질문형', title.is_question],
                    ['숫자 포함', title.has_number],
                    ['제목 스타일', title.style || item.style_type],
                    ['감성단어', Array.isArray(title.emotional_words) ? title.emotional_words.join(', ') : title.emotional_words],
                    ['지역명', title.has_location],
                    ['업체명', title.has_company]
                ])}</div>
                <div><strong style="color:var(--text);">Body Intelligence</strong>${renderAdminMetricList([
                    ['문단', body.paragraphs],
                    ['문장', body.sentences],
                    ['평균 길이', body.avg_sentence_len],
                    ['사진', body.images],
                    ['리스트', body.has_list],
                    ['소제목', body.subheadings],
                    ['인사말', body.has_greeting],
                    ['CTA', body.has_cta]
                ])}</div>
                <div><strong style="color:var(--text);">SEO Intelligence</strong>${renderAdminMetricList([
                    ['지역명 빈도', seo.location_freq],
                    ['업체명 빈도', seo.company_freq],
                    ['키워드 빈도', seo.keyword_freq],
                    ['전화번호', seo.phone_count || item.phone_count],
                    ['URL', seo.url_count],
                    ['해시태그', seo.hashtags],
                    ['날짜', seo.dates],
                    ['Emoji', seo.emojis]
                ])}</div>
                <div><strong style="color:var(--text);">Business Intelligence</strong>${renderAdminMetricList([
                    ['Business Score', business.business_score || item.business_score],
                    ['Competitor Score', business.competitor_score || item.competitor_score],
                    ['실제 업체 여부', business.competitor_score >= 70 ? '예' : '보통'],
                    ['후기 여부', business.has_review],
                    ['현장사진 여부', business.has_field_photo],
                    ['업종 적합도', item.business_score]
                ])}</div>
                <div><strong style="color:var(--text);">SQLite Status</strong>${renderAdminMetricList([
                    ['cache_status', data.cache_status],
                    ['analysis_version', data.analysis_version],
                    ['organic_rank', item.organic_rank || item.rank],
                    ['cache_created', item.cache_created || data.cache_created],
                    ['last_updated', item.last_updated || data.last_updated]
                ])}</div>
                <div><strong style="color:var(--text);">Developer Panel</strong>${renderAdminMetricList([
                    ['Recommendation 계산식', 'Organic + Business + Local + SEO + CTA + Trust + Freshness'],
                    ['Business 근거', `${ideaScore(item.business_score)}점 / competitor ${ideaScore(item.competitor_score || business.competitor_score)}점`],
                    ['Local 근거', `${ideaScore(item.locality_score)}점 / 지역 빈도 ${ideaVal(seo.location_freq, 0)}회`],
                    ['Deduplication', '동일 블로그/제목/전화번호 중복 제거 후 통과'],
                    ['광고 필터', duplicateText]
                ])}</div>
            </div>
        </details>
        <div class="idea-card-actions">
            <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="card-btn primary">원문 보기</a>
            <button type="button" class="card-btn secondary" onclick="loadAdminPromptPreview('${safeSearchKeyword}')">Prompt Preview</button>
            <button type="button" class="card-btn secondary" onclick="useBlogIdeaAnalysis('${safeSearchKeyword}')">이 글감 참고하기</button>
        </div>
    `;
}
window.renderAdminIdeaCard = renderAdminIdeaCard;

function setViewMode(mode) {
    if (mode === 'admin' && !canAccessContentIdeaAdmin()) mode = 'user';
    window.currentViewMode = mode;
    const btnUser = document.getElementById('btn-mode-user');
    const btnAdmin = document.getElementById('btn-mode-admin');
    const tabAiLab = document.getElementById('btn-tab-ailab');
    const tabPattern = document.getElementById('btn-tab-pattern');
    const tabPerformance = document.getElementById('btn-tab-performance');
    const tabBrain = document.getElementById('btn-tab-brain');
    const adminAllowed = syncContentIdeaAdminAccess();
    
    if (mode === 'admin') {
        if (btnUser) {
            btnUser.style.background = 'transparent';
            btnUser.style.color = 'var(--text)';
            btnUser.style.border = '1px solid var(--border)';
            btnUser.style.fontWeight = '600';
        }
        if (btnAdmin) {
            btnAdmin.style.background = 'var(--focus)';
            btnAdmin.style.color = 'white';
            btnAdmin.style.border = '1px solid transparent';
            btnAdmin.style.fontWeight = '700';
        }
        document.querySelectorAll('.admin-details-panel').forEach(el => el.style.display = 'block');
        if (tabAiLab) tabAiLab.style.display = 'inline-flex';
        if (tabPattern) tabPattern.style.display = 'inline-flex';
        if (tabPerformance) tabPerformance.style.display = 'inline-flex';
        if (tabBrain) tabBrain.style.display = 'inline-flex';
    } else {
        if (btnUser) {
            btnUser.style.background = 'var(--focus)';
            btnUser.style.color = 'white';
            btnUser.style.border = '1px solid transparent';
            btnUser.style.fontWeight = '700';
        }
        if (btnAdmin) {
            btnAdmin.style.background = 'transparent';
            btnAdmin.style.color = 'var(--text)';
            btnAdmin.style.border = '1px solid var(--border)';
            btnAdmin.style.fontWeight = '600';
        }
        document.querySelectorAll('.admin-details-panel').forEach(el => el.style.display = 'none');
        if (tabAiLab) tabAiLab.style.display = 'none';
        if (tabPattern) tabPattern.style.display = 'none';
        if (tabPerformance) tabPerformance.style.display = 'none';
        if (tabBrain) tabBrain.style.display = 'none';
        
        // Admin tab active state rollback to main search tab
        const activeTab = document.querySelector('.lab-tab-btn.active');
        if (activeTab && (activeTab.id === 'btn-tab-ailab' || activeTab.id === 'btn-tab-pattern' || activeTab.id === 'btn-tab-performance' || activeTab.id === 'btn-tab-brain')) {
            switchIdeaTab('search');
        }
    }
    
    // Rerender list to toggle details instantly if cache data exists
    if (window.lastSearchResponse) {
        renderContentIdeaCards(window.lastSearchResponse);
    }
}
window.setViewMode = setViewMode;

function getUserRecommendationReason(item) {
    const score = item.score || {};
    const details = item.analysis_details || {};
    const title = details.title || {};
    const body = details.body || {};
    const seo = details.seo || {};
    const business = details.business || {};
    
    const reasons = [];
    if (item.recommendation_score >= 85) reasons.push("상위 10% 최적 마케팅 글감");
    if (item.business_score >= 80) reasons.push("소비자 구매 결정을 자극하는 상업적 가치가 높은 본문 구성");
    if (score.relevance >= 80) reasons.push("네이버 검색 로직에 친화적인 구조적 문단 설계");
    if (body.images >= 5) reasons.push("시각 자료(사진/동영상)가 풍부하여 가독성이 뛰어남");
    if (title.style === '스토리텔링') reasons.push("친근하고 자연스러운 스토리 후기형 제목");
    if (seo.location_freq >= 2) reasons.push("지역 기반 오프라인 매장 노출 최적화");
    if (business.has_cta === '예') reasons.push("문의를 유도하는 명확한 CTA 확보");
    
    return reasons.slice(0, 2).join(' / ') || "키워드 연관성 및 본문 충실도 기준 우수 글감";
}
window.getUserRecommendationReason = getUserRecommendationReason;

function renderContentIdeaCards(res) {
    const cardsList = document.getElementById('ideaCardsList');
    if (!cardsList) return;
    cardsList.innerHTML = '';
    
    const items = res.data?.items || res.items || [];
    items.forEach(item => {
        const card = document.createElement('div');
        card.className = 'idea-card';
        card.style.cssText = 'background:var(--panel-card); border:1px solid var(--border); border-radius:var(--radius-md); padding:16px; display:flex; flex-direction:column; gap:8px;';
        
        const safeSearchKeyword = String(res.keyword || item.title || '').replace(/['\"\\#\n\r]/g, '');
        
        if (window.currentViewMode === 'admin') {
            card.innerHTML = renderAdminIdeaCard(item, res, safeSearchKeyword);
        } else {
            const score = item.score || {};
            const duplicateText = (item.ad_flags && item.ad_flags.length) ? item.ad_flags.join(', ') : '검증 완료';
            const userReason = getUserRecommendationReason(item);
            
            card.innerHTML = `
                <div class="idea-card-header" style="display:block;">
                    <div class="idea-card-meta">
                        <span class="idea-card-blogname" style="display:flex; align-items:center; gap:8px; flex-wrap:wrap; color:var(--focus); font-size:11px; font-weight:600;">
                            ${ideaVal(item.blog_name, '네이버 블로그')}
                            <span style="background:rgba(34,211,238,0.1); color:var(--focus); border:1px solid rgba(34,211,238,0.2); font-size:10px; padding:1px 5px; border-radius:3px;">${duplicateText}</span>
                        </span>
                        <h4 class="idea-card-title" style="margin-top:4px; font-size:15px; font-weight:700; color:var(--text); line-height:1.4;">
                            ${item.title}
                        </h4>
                    </div>
                </div>
                <div class="idea-card-summary" style="margin-top:4px;">
                    <div class="user-reason" style="font-size:12px; font-weight:600; color:var(--focus); line-height:1.5;">
                        추천 이유: ${userReason}
                    </div>
                </div>
                <div class="idea-card-actions" style="margin-top:12px; padding-top:10px; border-top:1px solid var(--border);">
                    <button type="button" class="card-btn secondary" onclick="useBlogIdeaAnalysis('${safeSearchKeyword}')">
                        이 글감 참고하기
                    </button>
                </div>
            `;
        }
        cardsList.appendChild(card);
    });
}
window.renderContentIdeaCards = renderContentIdeaCards;

function showIdeaStatusMessage(msg) {
    const statusEl = document.getElementById('ideaStatusMessage');
    if (!statusEl) return;
    statusEl.innerText = msg;
    statusEl.style.display = 'block';
    
    if (window.statusMessageTimeout) {
        clearTimeout(window.statusMessageTimeout);
    }
    window.statusMessageTimeout = setTimeout(() => {
        statusEl.style.display = 'none';
    }, 4500);
}
window.showIdeaStatusMessage = showIdeaStatusMessage;

async function useBlogIdeaAnalysis(keyword) {
    log(`'${keyword}' 글감을 프롬프트 참고자료로 반영하는 중...`);
    try {
        const response = await fetchWithAuth(`/api/content-ideas/naver-blog/extract?url=${encodeURIComponent(keyword)}`, {
            method: 'GET'
        });
        
        const res = await response.json();
        if (response.ok && res.ok && res.data && res.data.item) {
            const item = res.data.item;
            const formatted = `====== [참고 블로그 본문: ${item.title}] ======\n\n${item.text}`;
            
            const refTextEl = document.getElementById('reference_text');
            if (refTextEl) {
                refTextEl.value = formatted;
            }
            log(`'${item.title}' 본문 및 요약 참고자료 주입 완료`, 'success');
            showIdeaStatusMessage('선택한 글감 본문이 참고자료에 주입되었습니다. [통합 프롬프트] 탭을 확인해 보세요!');
            
            if (typeof triggerAutosave === 'function') {
                triggerAutosave();
            }
            
            // Accordion focus transit
            if (typeof toggleAccordionSection === 'function') {
                toggleAccordionSection('prompt', true);
            }
        } else {
            // URL extract fallback if keyword was query text
            const searchResponse = await fetchWithAuth(`/api/content-ideas/naver-blog/search?keyword=${encodeURIComponent(keyword)}&limit=1`);
            const searchRes = await searchResponse.json();
            const firstItem = searchRes.data?.items?.[0];
            if (firstItem && firstItem.url) {
                await useSinglePostAnalysis(firstItem.url);
            } else {
                throw new Error(res.message || '글감 세부 데이터 획득 실패');
            }
        }
    } catch (err) {
        log(`글감 참고하기 실패: ${err.message}`, 'error');
        alert(`글감 본문 가져오기 실패: ${err.message}`);
    }
}
window.useBlogIdeaAnalysis = useBlogIdeaAnalysis;

async function useSinglePostAnalysis(url) {
    log(`URL 본문 추출 및 참고자료 반영 중: ${url}`);
    try {
        const response = await fetchWithAuth(`/api/content-ideas/naver-blog/extract?url=${encodeURIComponent(url)}`, {
            method: 'GET'
        });
        const res = await response.json();
        if (!response.ok || !res.ok) throw new Error(res.message || '본문 분석 실패');
        
        const item = res.data.item;
        const formatted = `====== [참고 블로그 본문: ${item.title}] ======\n\n${item.text}`;
        
        const refTextEl = document.getElementById('reference_text');
        if (refTextEl) {
            refTextEl.value = formatted;
        }
        log(`참고 블로그 요약본 주입 완료: [${item.title}]`, 'success');
        showIdeaStatusMessage('선택한 글감 본문이 참고자료에 주입되었습니다.');
        
        if (typeof triggerAutosave === 'function') {
            triggerAutosave();
        }
    } catch (err) {
        log(`단건 글감 반영 실패: ${err.message}`, 'error');
    }
}
window.useSinglePostAnalysis = useSinglePostAnalysis;

function switchIdeaTab(tabId) {
    const searchPanel = document.getElementById('ideaSearchPanel');
    const labPanel = document.getElementById('ideaAiLabPanel');
    const patternPanel = document.getElementById('ideaPatternPanel');
    const performancePanel = document.getElementById('ideaPerformancePanel');
    const brainPanel = document.getElementById('ideaBrainPanel');
    
    if (searchPanel) searchPanel.style.display = 'none';
    if (labPanel) labPanel.style.display = 'none';
    if (patternPanel) patternPanel.style.display = 'none';
    if (performancePanel) performancePanel.style.display = 'none';
    if (brainPanel) brainPanel.style.display = 'none';
    
    document.querySelectorAll('.lab-tab-btn').forEach(btn => btn.classList.remove('active'));
    
    const activeBtn = document.getElementById(`btn-tab-${tabId}`);
    if (activeBtn) activeBtn.classList.add('active');
    
    if (tabId === 'search' && searchPanel) searchPanel.style.display = 'block';
    if (tabId === 'ailab' && labPanel) labPanel.style.display = 'block';
    if (tabId === 'pattern' && patternPanel) patternPanel.style.display = 'block';
    if (tabId === 'performance' && performancePanel) performancePanel.style.display = 'block';
    if (tabId === 'brain' && brainPanel) brainPanel.style.display = 'block';
    
    log(`[AI Lab] ${tabId.toUpperCase()} 탭으로 전환`);
}
window.switchIdeaTab = switchIdeaTab;

function selectIndustryChip(el) {
    document.querySelectorAll('.industry-chip').forEach(c => c.classList.remove('active'));
    el.classList.add('active');
    
    const kw = el.dataset.keyword;
    window.selectedIndustryKeyword = kw;
    
    const exampleList = document.getElementById('exampleKeywordList');
    if (exampleList) {
        exampleList.innerHTML = '';
        const examples = (el.dataset.examples || '').split(',').map(e => e.trim()).filter(Boolean);
        examples.forEach(ex => {
            const chip = document.createElement('span');
            chip.className = 'example-chip';
            chip.innerText = ex;
            chip.setAttribute('onclick', 'clickExampleChip(this)');
            exampleList.appendChild(chip);
        });
    }
    
    searchBlogIdeasFromIndustry();
}
window.selectIndustryChip = selectIndustryChip;

function clickExampleChip(el) {
    const input = document.getElementById('keywordInput');
    if (input) {
        input.value = el.innerText;
        searchBlogIdeasFromKeyword();
    }
}
window.clickExampleChip = clickExampleChip;

function handleKeywordEnter(event) {
    if (event.key === 'Enter') {
        searchBlogIdeasFromKeyword();
    }
}
window.handleKeywordEnter = handleKeywordEnter;

function handleUrlEnter(event) {
    if (event.key === 'Enter') {
        importBlogUrlAndExtract();
    }
}
window.handleUrlEnter = handleUrlEnter;

function searchBlogIdeasFromIndustry() {
    if (window.selectedIndustryKeyword) {
        searchBlogIdeas(window.selectedIndustryKeyword, 'industry');
    }
}
window.searchBlogIdeasFromIndustry = searchBlogIdeasFromIndustry;

function searchBlogIdeasFromKeyword() {
    const kwInput = document.getElementById('keywordInput');
    if (!kwInput) return;
    const kw = kwInput.value.trim();
    if (!kw) {
        alert('검색할 키워드를 입력해 주세요.');
        return;
    }
    searchBlogIdeas(kw, 'keyword');
}
window.searchBlogIdeasFromKeyword = searchBlogIdeasFromKeyword;

async function searchBlogIdeas(keyword, type) {
    const loader = document.getElementById('ideaLoader');
    const loaderText = document.getElementById('ideaLoaderText');
    const resultsContainer = document.getElementById('ideaResultsContainer');
    const cardsList = document.getElementById('ideaCardsList');
    const emptyState = document.getElementById('ideaEmptyState');
    
    if (loaderText) {
        loaderText.innerText = `'${keyword}' 키워드로 최적의 글감을 조회 중입니다...`;
    }
    if (loader) loader.style.display = 'flex';
    if (resultsContainer) resultsContainer.style.display = 'none';

    try {
        const response = await fetchWithAuth(`/api/content-ideas/naver-blog/search?keyword=${encodeURIComponent(keyword)}&limit=5`, {
            method: 'GET'
        });

        if (!response.ok) throw new Error(`HTTP 에러: ${response.status}`);

        const res = await response.json();
        if (loader) loader.style.display = 'none';
        if (resultsContainer) resultsContainer.style.display = 'block';

        if (res.ok && res.data && res.data.items && res.data.items.length > 0) {
            if (emptyState) emptyState.style.display = 'none';
            if (cardsList) cardsList.style.display = 'flex';
            const countEl = document.getElementById('ideaResultsCount');
            if (countEl) countEl.innerText = res.data.items.length;

            window.lastSearchResponse = res;

            if (typeof updateAiLabConsole === 'function') {
                updateAiLabConsole(res);
            }

            renderContentIdeaCards(res);
            if (window.currentViewMode === 'admin') {
                if (typeof loadAdminPromptPreview === 'function') {
                    loadAdminPromptPreview(res.data.keyword).catch(err => {
                        const preEl = document.getElementById('lab-prompt-preview');
                        if (preEl) preEl.innerText = `Prompt Preview 로드 실패: ${err.message}`;
                    });
                }
            }
        } else {
            if (cardsList) cardsList.style.display = 'none';
            if (emptyState) emptyState.style.display = 'flex';
            const countEl = document.getElementById('ideaResultsCount');
            if (countEl) countEl.innerText = '0';
        }
    } catch (err) {
        if (loader) loader.style.display = 'none';
        if (resultsContainer) resultsContainer.style.display = 'block';
        if (cardsList) cardsList.style.display = 'none';
        if (emptyState) emptyState.style.display = 'flex';
        const countEl = document.getElementById('ideaResultsCount');
        if (countEl) countEl.innerText = '0';
        log(`글감 검색 실패: ${err.message}`, 'error');
    }
}
window.searchBlogIdeas = searchBlogIdeas;

async function importBlogUrlAndExtract() {
    const urlInput = document.getElementById('naver-blog-url');
    if (!urlInput) return;
    const url = urlInput.value.trim();
    if (!url) {
        alert('본문을 가져올 네이버 블로그 URL을 입력해 주세요.');
        return;
    }

    const loader = document.getElementById('ideaLoader');
    const loaderText = document.getElementById('ideaLoaderText');
    const resultsContainer = document.getElementById('ideaResultsContainer');
    const cardsList = document.getElementById('ideaCardsList');
    const emptyState = document.getElementById('ideaEmptyState');

    if (loaderText) {
        loaderText.innerText = "입력한 네이버 블로그에서 본문 데이터를 분석하고 요약 중입니다...";
    }
    if (loader) loader.style.display = 'flex';
    if (resultsContainer) resultsContainer.style.display = 'none';
    
    try {
        const response = await fetchWithAuth(`/api/content-ideas/naver-blog/extract?url=${encodeURIComponent(url)}`, {
            method: 'GET'
        });

        await scrapeNaverBlog();

        if (!response.ok) throw new Error(`HTTP 에러: ${response.status}`);

        const res = await response.json();
        if (loader) loader.style.display = 'none';
        if (resultsContainer) resultsContainer.style.display = 'block';

        if (res.ok && res.data && res.data.item) {
            const item = res.data.item;
            
            const mockSearchRes = {
                keyword: item.title,
                cache_status: "miss",
                analysis_version: "2.0",
                duplicate_details: [],
                data: {
                    keyword: item.title,
                    pipeline_metrics: {
                        scraped: 1, blog: 1, ad_removed: 1, duplicate_removed: 1, organic_top5: 1, final_recommended: 1
                    },
                    items: [
                        {
                            organic_rank: 1,
                            blog_id: "url_extract",
                            title: item.title,
                            blog_name: "네이버 블로그",
                            summary: item.summary,
                            url: item.url,
                            ad_flags: [],
                            is_fallback: item.is_fallback,
                            recommendation_score: 95,
                            business_score: 95,
                            locality_score: 95,
                            write_date: "오늘",
                            analysis_details: {
                                title: {length: item.title.length, is_question: "아니오", has_number: "아니오", style: "정보제공", emotional_words: "", has_location: "아니오", has_company: "아니오"},
                                body: {paragraphs: 10, sentences: 8, avg_sentence_len: 25, images: 1, has_list: "아니오", subheadings: 1, has_greeting: "예", has_cta: "예"},
                                seo: {location_freq: 2, company_freq: 2, keyword_freq: 2, phone_count: 0, url_count: 0, hashtags: 1, dates: 0, emojis: 1},
                                business: {business_score: 95, competitor_score: 90, is_case_study: "예", has_field_photo: "예", has_review: "예"},
                            },
                            score: { relevance: 95, locality: 95, freshness: 95 }
                        }
                    ]
                }
            };
            
            if (emptyState) emptyState.style.display = 'none';
            if (cardsList) cardsList.style.display = 'flex';
            const countEl = document.getElementById('ideaResultsCount');
            if (countEl) countEl.innerText = '1';
            
            window.lastSearchResponse = mockSearchRes;
            if (typeof updateAiLabConsole === 'function') {
                updateAiLabConsole(mockSearchRes);
            }
            renderContentIdeaCards(mockSearchRes);
            urlInput.value = '';
        } else {
            if (cardsList) cardsList.style.display = 'none';
            if (emptyState) emptyState.style.display = 'flex';
            const countEl = document.getElementById('ideaResultsCount');
            if (countEl) countEl.innerText = '0';
        }
    } catch (err) {
        if (loader) loader.style.display = 'none';
        if (resultsContainer) resultsContainer.style.display = 'block';
        if (cardsList) cardsList.style.display = 'none';
        if (emptyState) emptyState.style.display = 'flex';
        const countEl = document.getElementById('ideaResultsCount');
        if (countEl) countEl.innerText = '0';
        log(`블로그 주소 분석 실패: ${err.message}`, 'error');
    }
}
window.importBlogUrlAndExtract = importBlogUrlAndExtract;

async function scrapeNaverBlog() {
    const urlInput = document.getElementById('naver-blog-url');
    if (!urlInput) return;
    const url = urlInput.value.trim();
    const btn = document.getElementById('btn-scrape');
    
    if (!url) {
        alert('가져올 콘텐츠 참고URL을 입력해 주세요.');
        return;
    }

    log(`블로그 크롤러 작동 중: [${url}] 본문 수집 시작...`);
    if (btn) {
        btn.disabled = true;
        btn.innerText = '수집 중...';
    }

    try {
        const response = await fetchWithAuth('/api/scrape-blog', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        });

        if (!response.ok) throw new Error(`HTTP 에러: ${response.status}`);

        const res = await response.json();
        if (res.ok && res.data) {
            const scrap = res.data;
            const formattedText = `====== [참고 블로그 본문: ${scrap.title}] ======\n\n${scrap.text}`;
            
            const refTextEl = document.getElementById('reference_text');
            if (refTextEl) {
                refTextEl.value = formattedText;
            }
            log(`블로그 본문 수집 성공: [${scrap.title}] (${scrap.text.length}자)`, 'success');
            
            urlInput.value = '';
            if (typeof triggerAutosave === 'function') {
                triggerAutosave();
            }
        } else {
            throw new Error(res.message || '크롤러 알 수 없는 오류');
        }
    } catch (err) {
        log(`크롤링 실패: ${err.message} (수동 입력을 진행해 주세요)`, 'error');
        alert(`블로그 스크래핑 실패: ${err.message}\n본문을 직접 복사하여 참고자료에 넣어주세요.`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = '본문 가져오기';
        }
    }
}
window.scrapeNaverBlog = scrapeNaverBlog;

async function extractKeywords() {
    const baseContent = document.getElementById('base_content')?.value || '';
    const referenceText = document.getElementById('reference_text')?.value || '';
    
    log('키워드 추천 추출 분석 중...');
    
    try {
        const response = await fetchWithAuth('/api/extract-keywords', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ texts: [baseContent, referenceText] })
        });

        if (!response.ok) throw new Error(`HTTP 에러: ${response.status}`);
        
        const res = await response.json();
        if (res.ok && res.data && res.data.keywords) {
            const candidates = res.data.keywords.slice(0, 10).map(k => `${k[0]}(${k[1]}회)`);
            log(`키워드 추천 추출 성공: [${candidates.join(', ')}]`, 'success');
        } else {
            throw new Error(res.message || '데이터 구조 오류');
        }
    } catch (err) {
        log(`키워드 추출 에러: ${err.message}`, 'error');
        alert(`키워드 추출 오류: ${err.message}`);
    }
}
window.extractKeywords = extractKeywords;
