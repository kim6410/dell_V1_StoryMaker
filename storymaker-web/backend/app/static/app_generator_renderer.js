// StoryMaker 프론트엔드 AI 결과 탭 렌더러 (app_generator_renderer.js)

// 8개 통합 채널 결과 탭UI 동적 바인딩 및 복사/미리보기 버튼 생성
function renderParsedTabs(blocks) {
    const container = document.getElementById('parsed-tabs-container');
    const headerBar = document.getElementById('tabs-header-bar');
    const contentPanes = document.getElementById('tabs-content-panes');
    const registrationLinks = document.getElementById('channel-registration-links');

    if (!headerBar || !contentPanes) return;

    headerBar.innerHTML = '';
    contentPanes.innerHTML = '';
    const oldPodcastShortcut = document.getElementById('podcast-shortcut-bar');
    if (oldPodcastShortcut) oldPodcastShortcut.remove();
    if (blocks["PODCAST_50"] || blocks["PODCAST_80"]) {
        const podcastShortcutBar = document.createElement('div');
        podcastShortcutBar.id = 'podcast-shortcut-bar-disabled';
        podcastShortcutBar.style.cssText = 'display:flex; align-items:center; justify-content:flex-start; gap:8px; margin:2px 0 -2px 500px; padding:0; background:transparent; width:max-content;';
        podcastShortcutBar.innerHTML = '<button type="button" class="btn-copy" style="width:auto; background:#0891b2; border:1px solid #22d3ee; color:white; padding:7px 13px; border-radius:8px; font-size:12px; font-weight:900; white-space:nowrap; box-shadow:0 8px 18px rgba(8,145,178,.22);">🎙️ 팟캐스트 만들기</button>';
        podcastShortcutBar.querySelector('button').onclick = () => {
            sessionStorage.setItem('explicit_nav', 'true');
            location.href = '/podcast';
        };
    }

    // 1. 블로그 통합 (제목 + 본문 + 태그)
    const blogTitle = blocks["BLOG_TITLES"] ? blocks["BLOG_TITLES"].trim() : "";
    const blogPost = blocks["BLOG_POST"] ? blocks["BLOG_POST"].trim() : "";
    const blogTags = blocks["BLOG_HASHTAGS"] ? blocks["BLOG_HASHTAGS"].trim() : "";
    let blogCombined = "";
    if (blogTitle) blogCombined += `${blogTitle}\n\n`;
    if (blogPost) blogCombined += `${blogPost}`;
    if (blogTags) blogCombined += `\n\n${blogTags}`;
    if (blogCombined) {
        window.wpCachedData = {
            title: blogTitle.split('\n').find(line => line.trim()) || '제목 없음',
            slug: '',
            focus_keyword: (blogTitle.split('\n').find(line => line.trim()) || '').split(',')[0],
            seo_title: blogTitle.split('\n').find(line => line.trim()) || '제목 없음',
            meta_description: blogPost.replace(/\s+/g, ' ').slice(0, 155),
            categories: '',
            tags: blogTags.replace(/#/g, '').replace(/\s+/g, ', '),
            featured_image_alt: blogTitle.split('\n').find(line => line.trim()) || 'StoryMaker 블로그 이미지',
            og_title: blogTitle.split('\n').find(line => line.trim()) || '제목 없음',
            og_description: blogPost.replace(/\s+/g, ' ').slice(0, 155),
            html_body: typeof convertBlogToHtml === 'function' ? convertBlogToHtml(blogTitle, blogPost, blogTags) : ''
        };
    }

    // 2. 당근 통합 (제목 + 본문 + 태그)
    const carrotTitle = blocks["CARROT_TITLES"] ? blocks["CARROT_TITLES"].trim() : "";
    const carrotPost = blocks["CARROT_POST"] ? blocks["CARROT_POST"].trim() : "";
    const carrotTags = blocks["CARROT_HASHTAGS"] ? blocks["CARROT_HASHTAGS"].trim() : "";
    let carrotCombined = "";
    if (carrotTitle) carrotCombined += `${carrotTitle}\n\n`;
    if (carrotPost) carrotCombined += `${carrotPost}`;
    if (carrotTags) carrotCombined += `\n\n${carrotTags}`;

    // 3. 인스타 통합 (본문 + 태그)
    const cleanInstagramPostForDisplay = (text) => String(text || '').split('\n').map(line => {
        const trimmed = line.trim();
        const mark = String.fromCharCode(58);
        const labels = ['문의', '연락처', '전화'];
        for (const label of labels) {
            if (trimmed.startsWith(label + mark)) {
                return trimmed.slice((label + mark).length).trim();
            }
        }
        return line;
    }).join('\n').trim();
    const instaPost = blocks["INSTAGRAM_POST"] ? cleanInstagramPostForDisplay(blocks["INSTAGRAM_POST"]) : "";
    const instaTags = blocks["INSTAGRAM_HASHTAGS"] ? blocks["INSTAGRAM_HASHTAGS"].trim() : "";
    let instaCombined = "";
    if (instaPost) instaCombined += `${instaPost}`;
    if (instaTags) instaCombined += `\n\n${instaTags}`;

    function formatPodcastDialogueForDisplay(text) {
        return String(text || '')
            .replace(/\r\n/g, '\n')
            .replace(/\n{3,}/g, '\n\n')
            .replace(/\n(?=\[(?:남성|여성)\])/g, '\n\n')
            .replace(/\n{3,}/g, '\n\n')
            .trim();
    }

    // 9개 통합 블록 정의
    const combinedBlocks = {};
    if (blogCombined) combinedBlocks["BLOG"] = blogCombined;
    combinedBlocks["NAVER_PLACE"] = blocks["NAVER_PLACE_NEWS"] || "이번 생성 결과에는 스마트플레이스 소식 내용이 아직 없습니다.\n\n통합 프롬프트를 다시 만들고 AI 자동생성을 실행하면 이 탭에 플레이스용 게시글이 표시됩니다.";
    combinedBlocks["GOOGLE_BUSINESS"] = blocks["GOOGLE_BUSINESS_POST"] || "이번 생성 결과에는 구글 마이비즈니스 게시글이 아직 없습니다.\n\n통합 프롬프트를 다시 만들고 AI 자동생성을 실행하면 이 탭에 구글용 게시글이 표시됩니다.";
    if (instaCombined) combinedBlocks["INSTAGRAM"] = instaCombined;
    if (carrotCombined) combinedBlocks["CARROT"] = carrotCombined;
    combinedBlocks["CAROUSEL_7"] = blocks["CAROUSEL_7"] || "이번 생성 결과에는 카드뉴스 자료가 아직 없습니다.";
    combinedBlocks["PODCAST_50"] = blocks["PODCAST_50"] ? formatPodcastDialogueForDisplay(blocks["PODCAST_50"]) : "이번 생성 결과에는 팟캐스트 50초 대본이 아직 없습니다.";
    combinedBlocks["PODCAST_80"] = blocks["PODCAST_80"] ? formatPodcastDialogueForDisplay(blocks["PODCAST_80"]) : "이번 생성 결과에는 팟캐스트 80초 대본이 아직 없습니다.";
    if (typeof isAdminUser === 'function' && isAdminUser() && blocks["WORDPRESS_SEO"]) {
        combinedBlocks["WORDPRESS_SEO"] = blocks["WORDPRESS_SEO"];
    }

    localStorage.setItem('storymaker_podcast_results', JSON.stringify({
        PODCAST_50: blocks["PODCAST_50"] || '',
        PODCAST_80: blocks["PODCAST_80"] || '',
        title: document.getElementById('project-title')?.value || '',
        updated_at: new Date().toISOString()
    }));

    const labelMapToUse = window.labelMap || labelMap;

    let isFirst = true;
    for (const [key, value] of Object.entries(combinedBlocks)) {
        if (!value.trim()) continue;
        
        const label = labelMapToUse[key] || key;

        const tabBtn = document.createElement('button');
        tabBtn.type = 'button';
        tabBtn.className = `tab-btn ${isFirst ? 'active' : ''}`;
        tabBtn.innerText = label;
        tabBtn.dataset.channel = key;
        tabBtn.setAttribute('onclick', `switchTab(event, 'pane-${key}')`);
        headerBar.appendChild(tabBtn);

        const pane = document.createElement('div');
        pane.id = `pane-${key}`;
        pane.className = `tab-content sns-page sns-page-${key} ${isFirst ? 'active' : ''}`;
        
        if (key === "BLOG") {
            pane.innerHTML = `
                <div class="preview-header" style="margin-top: 8px;">
                    <span style="display:none;">채널 태그: [BLOCK:${key}]</span>
                    <div style="display:flex; gap:8px;">
                        <!-- <button type="button" class="btn-copy secondary" id="btn-preview-${key}">미리보기</button> -->
                        <button type="button" class="btn-copy secondary" onclick="copyText('text-${key}', '${key}')">텍스트 복사</button>
                        ${typeof getChannelActionButtonHtml === 'function' ? getChannelActionButtonHtml(key) : ''}
                        <!-- WordPress 초안 / 즉시 발행 버튼은 UI에서 숨김 처리함. 필요 시 아래 기능을 별도 관리자 UI에서 다시 연결합니다. -->
                    </div>
                </div>
                <pre class="pre-box" id="text-${key}" style="max-height: 380px; color: #e2e8f0;">${value}</pre>
            `;
        } else if (key === "WORDPRESS_SEO") {
            const wpData = typeof parseWordPressSEO === 'function' ? parseWordPressSEO(value) : {};
            window.wpCachedData = wpData; // 전역 캐시 공유
            
            const fullPackageText = `[WordPress 제목]\n${wpData.title || ''}\n\n[Slug]\n${wpData.slug || ''}\n\n[포커스 키워드]\n${wpData.focus_keyword || ''}\n\n[SEO 제목]\n${wpData.seo_title || ''}\n\n[메타 설명]\n${wpData.meta_description || ''}\n\n[카테고리]\n${wpData.categories || ''}\n\n[태그]\n${wpData.tags || ''}\n\n[대표 이미지 ALT]\n${wpData.featured_image_alt || ''}\n\n[OG 제목]\n${wpData.og_title || ''}\n\n[OG 설명]\n${wpData.og_description || ''}\n\n[본문 HTML]\n${wpData.html_body || ''}`;

            pane.innerHTML = `
                <div class="wp-seo-container" style="margin-top: 16px; display: flex; flex-direction: column; gap: 24px;">
                    
                    <!-- 1. SEO 메타 카드 -->
                    <div class="card wp-card" style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                        <h4 style="color: #38bdf8; font-size: 1.1rem; margin-top: 0; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; font-weight: 600;">
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
                            SEO 메타 정보
                        </h4>
                        <div style="display: flex; flex-direction: column; gap: 12px;">
                            ${typeof createWpMetaRow === 'function' ? createWpMetaRow("WordPress 제목", wpData.title, "wp-title", "title") : ''}
                            ${typeof createWpMetaRow === 'function' ? createWpMetaRow("Slug", wpData.slug, "wp-slug", "slug") : ''}
                            ${typeof createWpMetaRow === 'function' ? createWpMetaRow("포커스 키워드", wpData.focus_keyword, "wp-focus-keyword", "focus_keyword") : ''}
                            ${typeof createWpMetaRow === 'function' ? createWpMetaRow("SEO 제목", wpData.seo_title, "wp-seo-title", "seo_title") : ''}
                            ${typeof createWpMetaRow === 'function' ? createWpMetaRow("메타 설명", wpData.meta_description, "wp-meta-desc", "meta_description") : ''}
                            ${typeof createWpMetaRow === 'function' ? createWpMetaRow("카테고리", wpData.categories, "wp-categories", "categories") : ''}
                            ${typeof createWpMetaRow === 'function' ? createWpMetaRow("태그", wpData.tags, "wp-tags", "tags") : ''}
                            ${typeof createWpMetaRow === 'function' ? createWpMetaRow("대표 이미지 ALT", wpData.featured_image_alt, "wp-img-alt", "featured_image_alt") : ''}
                            ${typeof createWpMetaRow === 'function' ? createWpMetaRow("OG 제목", wpData.og_title, "wp-og-title", "og_title") : ''}
                            ${typeof createWpMetaRow === 'function' ? createWpMetaRow("OG 설명", wpData.og_description, "wp-og-desc", "og_description") : ''}
                        </div>
                        <div style="margin-top: 20px; display: flex; justify-content: flex-end;">
                            <button type="button" class="btn-copy" style="background: #0284c7; color: white;" onclick="copyWpSeoMetaAll()">
                                SEO 정보 전체 복사
                            </button>
                        </div>
                    </div>

                    <!-- 2. WordPress 본문 HTML 카드 -->
                    <div class="card wp-card" style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                            <h4 style="color: #38bdf8; font-size: 1.1rem; margin: 0; display: flex; align-items: center; gap: 8px; font-weight: 600;">
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/></svg>
                                본문 HTML
                            </h4>
                            <div style="display: flex; gap: 8px;">
                                <button type="button" class="btn-copy secondary" onclick="previewWpBodyHtml()">미리보기</button>
                                <button type="button" class="btn-copy secondary" onclick="copyWpBodyHtml()">본문 HTML 복사</button>
                            </div>
                        </div>
                        <pre class="pre-box" style="max-height: 250px; color: #e2e8f0; font-family: monospace; font-size: 0.85rem; background: #0f172a; padding: 12px; border-radius: 6px; overflow-y: auto; white-space: pre-wrap; word-break: break-all;">${typeof escapeHtml === 'function' ? escapeHtml(wpData.html_body) : (wpData.html_body || '')}</pre>
                    </div>

                    <!-- 3. 전체 패키지 카드 및 WordPress 2단계 연동 -->
                    <div class="card wp-card" style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                            <h4 style="color: #38bdf8; font-size: 1.1rem; margin: 0; display: flex; align-items: center; gap: 8px; font-weight: 600;">
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>
                                전체 복사 패키지
                            </h4>
                            <button type="button" class="btn-copy" onclick="copyWpPackageAll()">전체 패키지 복사</button>
                        </div>
                        <pre class="pre-box" style="max-height: 150px; color: #e2e8f0; font-family: monospace; font-size: 0.85rem; background: #0f172a; padding: 12px; border-radius: 6px; overflow-y: auto; white-space: pre-wrap; word-break: break-all;">${typeof escapeHtml === 'function' ? escapeHtml(fullPackageText) : fullPackageText}</pre>
                        
                        <!-- 2단계 API 초안 등록 연동부 (비활성화 상태) -->
                        <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #334155; display: flex; flex-direction: column; gap: 8px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                                <div>
                                    <span style="color: #94a3b8; font-size: 0.85rem; display: block;">WordPress 2단계 초안 자동 등록</span>
                                    <span style="color: #ef4444; font-size: 0.8rem; font-weight: 500;">WordPress API 설정 후 사용할 수 있습니다.</span>
                                </div>
                                <button type="button" class="btn-copy" id="btn-send-wordpress-draft" style="background: #0284c7; color: white; border: 1px solid #38bdf8;" onclick="sendWordPressDraft('draft')">
                                    WordPress 초안으로 보내기
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } else {
            pane.innerHTML = `
                <div class="preview-header" style="margin-top: 8px;">
                    <span style="display:none;">채널 태그: [BLOCK:${key}]</span>
                    <div style="display:flex; gap:8px;">
                        <button type="button" class="btn-copy secondary" onclick="copyText('text-${key}', '${key}')">텍스트 복사</button>
                        ${typeof getChannelActionButtonHtml === 'function' ? getChannelActionButtonHtml(key) : ''}
                    </div>
                </div>
                <pre class="pre-box" id="text-${key}" style="max-height: 380px; color: #e2e8f0;">${value}</pre>
            `;
        }
        contentPanes.appendChild(pane);

        // Bind naver blog preview dynamically
        if (key === "BLOG") {
            const previewBtn = document.getElementById(`btn-preview-${key}`);
            if (previewBtn) {
                previewBtn.onclick = () => {
                    if (typeof openHtmlPreview === 'function') {
                        openHtmlPreview(blogTitle, blogPost, blogTags);
                    }
                };
            }
        }
        isFirst = false;
    }

    if (contentPanes && (blocks["PODCAST_50"] || blocks["PODCAST_80"])) {
        const podcastNextAction = document.createElement('div');
        podcastNextAction.id = 'podcast-next-action-bar';
        podcastNextAction.style.cssText = 'display:flex; justify-content:center; align-items:center; margin:3mm 0 6px; padding:0 12px 4px;';
        podcastNextAction.innerHTML = '<button type="button" class="btn-copy" style="min-width:220px; background:linear-gradient(135deg,#06b6d4,#0891b2); border:1px solid #67e8f9; color:white; padding:13px 22px; border-radius:14px; font-size:16px; font-weight:900; letter-spacing:-0.02em; box-shadow:0 14px 28px rgba(6,182,212,.24);">팟캐스트 만들기</button>';
        podcastNextAction.querySelector('button').onclick = () => {
            sessionStorage.setItem('explicit_nav', 'true');
            sessionStorage.setItem('storymaker_auto_import_podcast', 'PODCAST_50');
            location.href = '/podcast';
        };
        contentPanes.appendChild(podcastNextAction);
    }

    if (container) container.style.display = 'block';
    
    const snsPlaceholder = document.getElementById('sns-placeholder');
    if (snsPlaceholder) snsPlaceholder.style.display = 'none';

    // Update Header Info
    const now = new Date();
    const timeStr = now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');
    
    let totalCharCount = 0;
    Object.values(combinedBlocks).forEach(val => {
        totalCharCount += val.length;
    });

    const snsInfo = document.getElementById('sns-header-info');
    if (snsInfo) {
        snsInfo.innerText = `${timeStr} | 총 ${Object.keys(combinedBlocks).length}개 채널 (${totalCharCount.toLocaleString()}자)`;
    }

    if (typeof toggleAccordionSection === 'function') {
        toggleAccordionSection('sns', true); // SNS 자동 펼침
    }
}
window.renderParsedTabs = renderParsedTabs;
