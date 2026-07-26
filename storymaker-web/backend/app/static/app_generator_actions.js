// StoryMaker 프론트엔드 복사, 미리보기 및 채널 바로가기 액션 유틸 (app_generator_actions.js)

// 플랫폼 바로가기 링크 설정 및 자동 저장 연동
const CHANNEL_LINKS = {
    naver_blog: "https://blog.naver.com",
    naver_place: "https://new.smartplace.naver.com/",
    carrot: "https://bizprofile.daangn.com/",
    google_business: "https://business.google.com/",
    instagram: "https://www.instagram.com/"
};
window.CHANNEL_LINKS = CHANNEL_LINKS;

function getChannelActionButtonHtml(channelKey) {
    const buttonMap = {
        BLOG: ['네이버 블로그 바로가기', 'naver_blog', 'background:#03c75a; border:1px solid #22c55e; color:#ffffff;'],
        NAVER_PLACE: ['네이버플레이스 바로가기', 'naver_place', 'background:#00a862; border:1px solid #16a34a; color:#ffffff;'],
        CARROT: ['당근마켓 바로가기', 'carrot', 'background:#ff6f0f; border:1px solid #fb923c; color:#ffffff;'],
        INSTAGRAM: ['인스타그램 바로가기', 'instagram', 'background:linear-gradient(135deg,#f58529,#dd2a7b,#8134af,#515bd4); border:1px solid #c084fc; color:#ffffff;'],
        GOOGLE_BUSINESS: ['구글비즈니스 바로가기', 'google_business', 'background:#2563eb; border:1px solid #60a5fa; color:#ffffff;'],
        CAROUSEL_7: ['인스타그램 바로가기', 'instagram', 'background:linear-gradient(135deg,#7c3aed,#dd2a7b,#f97316); border:1px solid #c4b5fd; color:#ffffff;']
    };
    if (channelKey === 'PODCAST_50' || channelKey === 'PODCAST_80') {
        return `<a href="/podcast" class="btn-copy" onclick="sessionStorage.setItem('explicit_nav','true');" style="background:#0891b2; border:1px solid #22d3ee; color:white; text-decoration:none; font-weight:900;">팟캐스트 만들기</a>`;
    }
    const item = buttonMap[channelKey];
    if (!item) return '';
    return `<button type="button" class="btn-copy" onclick="openChannelLink('${item[1]}')" style="${item[2]} font-weight:900;">${item[0]}</button>`;
}
window.getChannelActionButtonHtml = getChannelActionButtonHtml;

async function openChannelLink(channelKey) {
    const url = CHANNEL_LINKS[channelKey];
    if (!url) {
        alert('해당 채널의 바로가기 링크가 존재하지 않습니다.');
        return;
    }
    
    // Plausible Analytics 플랫폼 바로가기 이벤트 추적
    if (typeof trackEvent === 'function') {
        trackEvent("platform_open", { platform: channelKey });
    }
    
    log(`[바로가기] [${channelKey}] 플랫폼 페이지 로드 전 변경사항 자동 저장 진행...`);
    
    try {
        if (typeof saveProject === 'function') {
            await saveProject(false);
        }
        log(`[바로가기] 프로젝트 자동 저장 완료, 새 탭에서 플랫폼을 엽니다.`);
    } catch (err) {
        log(`[바로가기] 자동 저장 중 오류 발생: ${err.message}`, 'warning');
    }
    
    window.open(url, '_blank', 'noopener,noreferrer');
}
window.openChannelLink = openChannelLink;

// 모바일 미리보기 모달 제어
function showPreviewModal(title, text) {
    const modal = document.getElementById('preview-modal');
    const titleEl = document.getElementById('preview-modal-title');
    const contentEl = document.getElementById('preview-modal-content');
    if (!modal || !titleEl || !contentEl) return;

    titleEl.innerText = `${title} 모바일 미리보기`;
    
    // 실제 게시글 스타일 렌더링 (마크다운 제목, 해시태그 하이라이팅, 줄바꿈)
    let formatted = text;
    
    // HTML escape 처리
    formatted = formatted
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

    // 굵게 마크다운 처리: **문장** → <strong>문장</strong>
    formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // 줄바꿈 처리
    formatted = formatted.replace(/\n/g, '<br>');

    // 마크다운 제목(#...) 또는 "제목:" 라인 렌더링
    formatted = formatted.replace(/^(#+)\s+(.+)$/gm, (match, hashes, content) => {
        const level = hashes.length;
        const size = 18 - (level * 2);
        return `<strong style="font-size: ${size}px; color: var(--accent); display: block; margin: 12px 0 6px 0;">${content}</strong>`;
    });
    
    // "제목:" 형태의 라벨 굵게 처리
    formatted = formatted.replace(/(제목:)\s*(.+)/g, '<strong style="color: var(--accent); font-size: 15px; display:block; margin-bottom:8px;">$1 $2</strong>');
    formatted = formatted.replace(/(본문:)\s*/g, '<strong style="color: var(--muted); font-size: 13px; display:block; margin: 14px 0 6px 0;">$1</strong>');
    formatted = formatted.replace(/(태그:)\s*/g, '<strong style="color: var(--muted); font-size: 13px; display:block; margin: 14px 0 6px 0;">$1</strong>');

    // 해시태그 파란색 하이라이트 처리 (단어 경계 고려)
    formatted = formatted.replace(/(#[^\s#<]+)/g, '<span class="hashtag" style="color: #0088ff; font-weight: 600; cursor: pointer;">$1</span>');

    contentEl.innerHTML = formatted;
    modal.style.display = 'flex';
    log(`[미리보기] [${title}] 모바일 뷰어 구동 완료`);
}
window.showPreviewModal = showPreviewModal;

function closePreviewModal() {
    const modal = document.getElementById('preview-modal');
    if (modal) modal.style.display = 'none';
}
window.closePreviewModal = closePreviewModal;

// 통합 프롬프트 HTML 미리보기 전용 유틸
// 원본 프롬프트/DB 저장값은 변경하지 않고, 브라우저 미리보기용 HTML만 생성한다.
function normalizePromptLineBreaks(value) {
    return String(value || '')
        .replace(/\\\\r\\\\n/g, '\n')
        .replace(/\\\\n/g, '\n')
        .replace(/\\r\\n/g, '\n')
        .replace(/\\n/g, '\n')
        .replace(/\r\n/g, '\n')
        .replace(/\r/g, '\n')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
}
window.normalizePromptLineBreaks = normalizePromptLineBreaks;

function getPromptTextForPreview() {
    const promptBox = document.getElementById('generated-prompt-box');
    const rawText = promptBox ? (promptBox.textContent || promptBox.innerText || '') : '';
    return normalizePromptLineBreaks(rawText);
}
window.getPromptTextForPreview = getPromptTextForPreview;

function escapePromptPreviewHtml(value) {
    return String(value || '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    }[ch]));
}
window.escapePromptPreviewHtml = escapePromptPreviewHtml;

function normalizePromptMarkdown(markdownText) {
    return normalizePromptLineBreaks(markdownText)
        .replace(/([^\n])(#{1,6})(?=\s*\S)/g, '$1\n\n$2')
        .replace(/(#{1,6})([^\s#])/g, '$1 $2')
        .replace(/([^\n])\s+(-\s+)/g, '$1\n$2')
        .replace(/([^\n])\s+(\d+\.\s+)/g, '$1\n$2')
        .replace(/([^\n])\s+(\[[A-Z0-9_:-]+\])/g, '$1\n\n$2')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
}
window.normalizePromptMarkdown = normalizePromptMarkdown;

function formatPromptInline(value, options = {}) {
    let html = escapePromptPreviewHtml(value)
        .replace(/\*\*([^*\n]{1,80})\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code>$1</code>');
    if (options.sentenceBreaks) {
        html = html.replace(/\.\s*/g, '.<br>');
    }
    return html;
}
window.formatPromptInline = formatPromptInline;

function splitPromptHeadingBody(headingText) {
    const text = String(headingText || '').trim();
    const match = text.match(/^(.{2,46}?(?:규칙|환경|선택|키워드|흐름|맥락|날씨|역할|중요|가이드|점검|원칙|요청사항))\s*[-:：]?\s*(.+)$/);
    if (match && match[2] && match[2].trim().length > 4) {
        return { title: match[1].trim(), body: match[2].trim() };
    }
    return { title: text, body: '' };
}
window.splitPromptHeadingBody = splitPromptHeadingBody;

function renderPromptBodyBlock(text) {
    const normalized = String(text || '').replace(/^\s*[-:：]\s*/, '').trim();
    if (!normalized) return '';
    const pieces = normalized.split(/\s+-\s+/).map(v => v.trim()).filter(Boolean);
    if (pieces.length <= 1) {
        return `<p>${formatPromptInline(normalized, { sentenceBreaks: true })}</p>`;
    }
    const lead = pieces[0] ? `<p>${formatPromptInline(pieces[0], { sentenceBreaks: true })}</p>` : '';
    const list = pieces.slice(1).map(piece => `<li>${formatPromptInline(piece, { sentenceBreaks: true })}</li>`).join('');
    return `${lead}<ul>${list}</ul>`;
}
window.renderPromptBodyBlock = renderPromptBodyBlock;

function markdownPromptToHtml(markdownText) {
    const lines = normalizePromptMarkdown(markdownText).split('\n');
    let html = '';
    let listType = null;

    const closeList = () => {
        if (!listType) return;
        html += listType === 'ol' ? '</ol>' : '</ul>';
        listType = null;
    };

    const openList = (type) => {
        if (listType === type) return;
        closeList();
        html += type === 'ol' ? '<ol>' : '<ul>';
        listType = type;
    };

    lines.forEach(rawLine => {
        const line = rawLine.trim();
        if (!line) {
            closeList();
            html += '<div class="sm-gap"></div>';
            return;
        }

        const heading = line.match(/^(#{1,6})\s+(.+)$/);
        if (heading) {
            closeList();
            const level = Math.min(heading[1].length, 4);
            const parts = splitPromptHeadingBody(heading[2]);
            html += `<h${level}>${formatPromptInline(parts.title)}</h${level}>`;
            if (parts.body) html += renderPromptBodyBlock(parts.body);
            return;
        }

        const bullet = line.match(/^[-*]\s+(.+)$/);
        if (bullet) {
            openList('ul');
            html += `<li>${formatPromptInline(bullet[1], { sentenceBreaks: true })}</li>`;
            return;
        }

        const ordered = line.match(/^\d+\.\s+(.+)$/);
        if (ordered) {
            openList('ol');
            html += `<li>${formatPromptInline(ordered[1], { sentenceBreaks: true })}</li>`;
            return;
        }

        closeList();
        html += `<p>${formatPromptInline(line, { sentenceBreaks: true })}</p>`;
    });

    closeList();
    return html;
}
window.markdownPromptToHtml = markdownPromptToHtml;

function buildPromptPreviewHtml(bodyHtml) {
    return `<!doctype html><html lang="ko"><head><meta name="robots" content="noindex, nofollow"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>StoryMaker 프롬프트 미리보기</title><style>
        body{background:#f4f6f9;margin:0;padding:40px 20px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,'Noto Sans KR','Malgun Gothic',sans-serif;color:#333;line-height:1.8;display:flex;justify-content:center;}
        .container{max-width:720px;width:100%;background:#fff;padding:40px;box-sizing:border-box;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,.05);border:1px solid #e1e4e6;}
        .seo-helper{background:#f8f9fa;border:1px solid #e9ecef;border-radius:8px;padding:15px;margin-bottom:30px;font-size:13px;line-height:1.65;color:#666;}
        .seo-helper-title{font-weight:700;color:#333;margin-bottom:5px;}
        h1{font-size:26px;font-weight:800;line-height:1.4;margin:10px 0 30px;color:#111;border-bottom:2px solid #00c73c;padding-bottom:15px;word-break:keep-all;}
        h2{font-size:20px;font-weight:700;line-height:1.5;margin-top:35px;margin-bottom:15px;color:#222;border-left:4px solid #00c73c;padding-left:12px;padding-top:22px;border-top:1px dashed #cfd8dc;word-break:keep-all;}
        h3{font-size:18px;font-weight:700;line-height:1.5;margin-top:30px;margin-bottom:12px;color:#333;border-left:4px solid #00c73c;padding-left:12px;padding-top:18px;border-top:1px dashed #cfd8dc;word-break:keep-all;}
        h4{font-size:16px;font-weight:700;line-height:1.55;margin:22px 0 10px;color:#444;padding-left:10px;border-left:3px solid #9ca3af;word-break:keep-all;}
        p{font-size:17px;font-weight:400;line-height:1.8;margin-top:0;margin-bottom:24px;color:#444;word-break:keep-all;overflow-wrap:break-word;white-space:normal;}
        ul,ol{margin:8px 0 24px 24px;padding:0;}
        li{font-size:16px;font-weight:400;line-height:1.75;margin:6px 0;color:#444;word-break:keep-all;overflow-wrap:break-word;}
        strong{font-weight:700;color:#222;}
        code{background:#f1f3f5;border:1px solid #e5e7eb;border-radius:6px;padding:2px 6px;color:#0f766e;font-size:.92em;}
        .sm-gap{height:8px;}
        @media(max-width:720px){body{padding:18px 10px}.container{padding:28px 20px 54px}h1{font-size:23px}h2{font-size:19px}p{font-size:16px}}
    </style></head><body><main class="container"><div class="seo-helper"><div class="seo-helper-title">StoryMaker 프롬프트 미리보기</div>마크다운을 HTML로 변환한 보기 화면입니다. 원본 프롬프트와 DB 저장 내용은 변경하지 않습니다.</div>${bodyHtml}</main></body></html>`;
}
window.buildPromptPreviewHtml = buildPromptPreviewHtml;

function openPromptHtmlPreview(event) {
    if (event) event.stopPropagation();
    const promptText = getPromptTextForPreview();
    if (!promptText || promptText.includes('통합 프롬프트를 생성하면')) {
        alert('미리보기할 프롬프트가 없습니다. 먼저 통합 프롬프트를 만들어 주세요.');
        return;
    }
    const fullHtml = buildPromptPreviewHtml(markdownPromptToHtml(promptText));
    const blob = new Blob([fullHtml], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank', 'noopener,noreferrer');
}
window.openPromptHtmlPreview = openPromptHtmlPreview;

async function copyAccordionContent(event, type) {
    event.stopPropagation();
    let textToCopy = '';
    const btn = event.currentTarget;
    if (!btn) return;
    const origText = btn.innerText;

    if (type === 'prompt') {
        textToCopy = getPromptTextForPreview();
    } else if (type === 'ai') {
        textToCopy = document.getElementById('chatgpt-raw-input')?.value || '';
    } else if (type === 'sns') {
        textToCopy = typeof getCombinedSnsText === 'function' ? getCombinedSnsText() : '';
    }

    if (!textToCopy || !textToCopy.trim()) {
        alert('복사할 내용이 없습니다.');
        return;
    }

    const success = await copyTextDirect(textToCopy, type === 'prompt' ? '통합 프롬프트' : (type === 'ai' ? 'AI 원문 결과' : 'SNS 통합 원고'));
    if (success) {
        btn.innerText = '✓ 복사완료';
        btn.style.background = 'var(--success)';
        btn.style.color = '#fff';
        btn.style.borderColor = 'transparent';
        setTimeout(() => {
            btn.innerText = origText;
            btn.style.background = '';
            btn.style.color = '';
            btn.style.borderColor = '';
        }, 1500);
    }
}
window.copyAccordionContent = copyAccordionContent;

function getCombinedSnsText() {
    const blocks = window.lastParsedBlocks || {};
    let combined = '';
    
    // 블로그
    const blogTitle = blocks["BLOG_TITLES"] ? blocks["BLOG_TITLES"].trim() : "";
    const blogPost = blocks["BLOG_POST"] ? blocks["BLOG_POST"].trim() : "";
    const blogTags = blocks["BLOG_HASHTAGS"] ? blocks["BLOG_HASHTAGS"].trim() : "";
    if (blogTitle || blogPost || blogTags) {
        combined += `[네이버 블로그]\n`;
        if (blogTitle) combined += `${blogTitle}\n\n`;
        if (blogPost) combined += `${blogPost}`;
        if (blogTags) combined += `\n\n${blogTags}`;
        combined += `\n\n====================\n\n`;
    }
    
    // 스마트플레이스 소식
    const place = blocks["NAVER_PLACE_NEWS"] ? blocks["NAVER_PLACE_NEWS"].trim() : "";
    if (place) {
        combined += `[네이버 스마트플레이스 소식]\n${place}\n\n====================\n\n`;
    }
    
    // 구글 비즈니스
    const google = blocks["GOOGLE_BUSINESS_POST"] ? blocks["GOOGLE_BUSINESS_POST"].trim() : "";
    if (google) {
        combined += `[구글 마이비즈니스]\n${google}\n\n====================\n\n`;
    }
    
    // 인스타그램
    const instaPost = blocks["INSTAGRAM_POST"] ? blocks["INSTAGRAM_POST"].trim() : "";
    const instaTags = blocks["INSTAGRAM_HASHTAGS"] ? blocks["INSTAGRAM_HASHTAGS"].trim() : "";
    if (instaPost || instaTags) {
        combined += `[인스타그램]\n`;
        if (instaPost) combined += `${instaPost}`;
        if (instaTags) combined += `\n\n${instaTags}`;
        combined += `\n\n====================\n\n`;
    }
    
    // 당근마켓
    const carrotTitle = blocks["CARROT_TITLES"] ? blocks["CARROT_TITLES"].trim() : "";
    const carrotPost = blocks["CARROT_POST"] ? blocks["CARROT_POST"].trim() : "";
    const carrotTags = blocks["CARROT_HASHTAGS"] ? blocks["CARROT_HASHTAGS"].trim() : "";
    if (carrotTitle || carrotPost || carrotTags) {
        combined += `[당근마켓 비즈프로필]\n`;
        if (carrotTitle) combined += `${carrotTitle}\n\n`;
        if (carrotPost) combined += `${carrotPost}`;
        if (carrotTags) combined += `\n\n${carrotTags}`;
        combined += `\n\n====================\n\n`;
    }

    // 카드뉴스 자료
    const carousel = blocks["CAROUSEL_7"] ? blocks["CAROUSEL_7"].trim() : "";
    if (carousel) {
        combined += `[인스타 카드뉴스 콘티]\n${carousel}\n\n====================\n\n`;
    }

    // 팟캐스트 대본들
    const pod50 = blocks["PODCAST_50"] ? blocks["PODCAST_50"].trim() : "";
    if (pod50) {
        combined += `[팟캐스트 50초 오디오 대본]\n${pod50}\n\n====================\n\n`;
    }
    const pod80 = blocks["PODCAST_80"] ? blocks["PODCAST_80"].trim() : "";
    if (pod80) {
        combined += `[팟캐스트 80초 오디오 대본]\n${pod80}\n\n====================\n\n`;
    }

    // 워드프레스
    const wp = blocks["WORDPRESS_SEO"] ? blocks["WORDPRESS_SEO"].trim() : "";
    if (wp) {
        combined += `[WordPress SEO 패키지]\n${wp}\n\n====================\n\n`;
    }

    return combined.trim();
}
window.getCombinedSnsText = getCombinedSnsText;

function updateSnsHeaderInfo(blocks) {
    const labelMapToUse = window.labelMap || {};
    const timeStr = new Date().toTimeString().split(' ')[0].slice(0, 5);
    
    const combinedBlocks = {};
    const blogTitle = blocks["BLOG_TITLES"] ? blocks["BLOG_TITLES"].trim() : "";
    const blogPost = blocks["BLOG_POST"] ? blocks["BLOG_POST"].trim() : "";
    const blogTags = blocks["BLOG_HASHTAGS"] ? blocks["BLOG_HASHTAGS"].trim() : "";
    if (blogTitle || blogPost || blogTags) {
        combinedBlocks["BLOG"] = (blogTitle + blogPost + blogTags);
    }
    if (blocks["NAVER_PLACE_NEWS"]) combinedBlocks["NAVER_PLACE"] = blocks["NAVER_PLACE_NEWS"];
    if (blocks["GOOGLE_BUSINESS_POST"]) combinedBlocks["GOOGLE_BUSINESS"] = blocks["GOOGLE_BUSINESS_POST"];
    
    const instaPost = blocks["INSTAGRAM_POST"] ? blocks["INSTAGRAM_POST"].trim() : "";
    const instaTags = blocks["INSTAGRAM_HASHTAGS"] ? blocks["INSTAGRAM_HASHTAGS"].trim() : "";
    if (instaPost || instaTags) {
        combinedBlocks["INSTAGRAM"] = (instaPost + instaTags);
    }
    const carrotTitle = blocks["CARROT_TITLES"] ? blocks["CARROT_TITLES"].trim() : "";
    const carrotPost = blocks["CARROT_POST"] ? blocks["CARROT_POST"].trim() : "";
    const carrotTags = blocks["CARROT_HASHTAGS"] ? blocks["CARROT_HASHTAGS"].trim() : "";
    if (carrotTitle || carrotPost || carrotTags) {
        combinedBlocks["CARROT"] = (carrotTitle + carrotPost + carrotTags);
    }
    if (blocks["CAROUSEL_7"]) combinedBlocks["CAROUSEL_7"] = blocks["CAROUSEL_7"];
    if (blocks["PODCAST_50"]) combinedBlocks["PODCAST_50"] = blocks["PODCAST_50"];
    if (blocks["PODCAST_80"]) combinedBlocks["PODCAST_80"] = blocks["PODCAST_80"];
    if (typeof isAdminUser === 'function' && isAdminUser() && blocks["WORDPRESS_SEO"]) {
        combinedBlocks["WORDPRESS_SEO"] = blocks["WORDPRESS_SEO"];
    }

    let totalCharCount = 0;
    Object.values(combinedBlocks).forEach(val => {
        totalCharCount += val.length;
    });

    const snsInfo = document.getElementById('sns-header-info');
    if (snsInfo) {
        snsInfo.innerText = `${timeStr} | 총 ${Object.keys(combinedBlocks).length}개 채널 (${totalCharCount.toLocaleString()}자)`;
    }
}
window.updateSnsHeaderInfo = updateSnsHeaderInfo;

let lastAiInputLength = 0;
window.lastAiInputLength = lastAiInputLength;

function onAiResultInput() {
    const rawInput = document.getElementById('chatgpt-raw-input');
    if (!rawInput) return;
    const text = rawInput.value || '';
    
    // 더티 체크 및 실시간 글자수 출력
    const rawLen = text.length;
    const countEl = document.getElementById('chatgpt-char-count');
    if (countEl) {
        countEl.textContent = rawLen.toLocaleString('ko-KR');
    }
    
    const countBadge = document.getElementById('chatgpt-char-count-badge');
    if (countBadge) {
        countBadge.textContent = rawLen.toLocaleString('ko-KR');
    }
    
    if (Math.abs(rawLen - window.lastAiInputLength) > 10) {
        window.lastAiInputLength = rawLen;
        
        const now = new Date();
        const timeStr = now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');
        const aiInfo = document.getElementById('ai-header-info');
        if (aiInfo) {
            aiInfo.innerText = `${timeStr} | ${rawLen.toLocaleString()}자 입력됨`;
        }
    }
}
window.onAiResultInput = onAiResultInput;

function switchTab(evt, paneId) {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => btn.classList.remove('active'));
    tabContents.forEach(pane => pane.classList.remove('active'));
    
    evt.currentTarget.classList.add('active');
    const targetPane = document.getElementById(paneId);
    if (targetPane) targetPane.classList.add('active');
    
    const channelKey = paneId.replace('pane-', '');
    log(`[SNS 분리] ${window.labelMap[channelKey] || channelKey} 결과 탭으로 전환`);
}
window.switchTab = switchTab;

function showToast(message) {
    const toast = document.getElementById('toast');
    if (!toast) {
        console.warn(`[Toast Off] ${message}`);
        return;
    }
    toast.innerText = message;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 2800);
}
window.showToast = showToast;

async function copyText(elementId, channelKey) {
    const preBox = document.getElementById(elementId);
    if (!preBox) return;
    const text = preBox.innerText;
    
    const label = window.labelMap[channelKey] || channelKey;
    const success = await copyTextDirect(text, label);
    if (success) {
        logActivity("html_copy", "project", window.currentProjectId, JSON.stringify({ channel: channelKey, type: "plain_text", label: label }));
    }
}
window.copyText = copyText;

async function logActivity(action, targetType, targetId, metadataJson = '{}') {
    try {
        await fetchWithAuth('/api/activity-logs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action,
                target_type: targetType,
                target_id: parseInt(targetId) || null,
                metadata_json: metadataJson
            })
        });
    } catch (e) {
        console.error("활동 로그 기록 실패:", e);
    }
}
window.logActivity = logActivity;

// 네이버 블로그 브라우저 미리보기 새 창 열기 (Blob 방식)
function openHtmlPreview(title, post, hashtags) {
    const html = typeof convertBlogToHtml === 'function' ? convertBlogToHtml(title, post, hashtags) : '';
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener,noreferrer");
    logActivity("preview_open", "project", window.currentProjectId, JSON.stringify({ channel: "BLOG", type: "html_browser" }));
}
window.openHtmlPreview = openHtmlPreview;

// 네이버 블로그 HTML 클립보드 서식 복사 (text/html + text/plain)
async function copyHtmlToClipboard(title, post, hashtags) {
    const html = typeof convertBlogToHtml === 'function' ? convertBlogToHtml(title, post, hashtags) : '';
    
    let plainText = "";
    if (title) plainText += `제목:\n${title}\n\n`;
    if (post) plainText += `본문:\n${post}`;
    if (hashtags) plainText += `\n\n태그:\n${hashtags}`;

    try {
        if (navigator.clipboard && window.ClipboardItem) {
            const htmlBlob = new Blob([html], { type: "text/html" });
            const textBlob = new Blob([plainText], { type: "text/plain" });
            const item = new ClipboardItem({
                "text/html": htmlBlob,
                "text/plain": textBlob
            });
            await navigator.clipboard.write([item]);
            showToast("HTML 서식 복사가 완료되었습니다!");
            log('HTML 클립보드 서식 복사 성공', 'success');
        } else {
            await navigator.clipboard.writeText(plainText);
            showToast("일반 텍스트로 복사되었습니다.");
            log('HTML 복사 미지원 환경으로 일반 텍스트 복사 실행', 'warning');
        }
        logActivity("html_copy", "project", window.currentProjectId, JSON.stringify({ channel: "BLOG", type: "text_html" }));
    } catch (err) {
        console.error("HTML 복사 에러:", err);
        try {
            const textarea = document.createElement("textarea");
            textarea.value = plainText;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand("copy");
            document.body.removeChild(textarea);
            showToast("일반 텍스트로 복사되었습니다.");
            logActivity("html_copy", "project", window.currentProjectId, JSON.stringify({ channel: "BLOG", type: "plain_text_fallback" }));
        } catch (fallbackErr) {
            alert("복사에 실패했습니다: " + err.message);
        }
    }
}
window.copyHtmlToClipboard = copyHtmlToClipboard;

let wpCachedData = null;
window.wpCachedData = wpCachedData;

// WordPress SEO 결과 마크다운 파싱 헬퍼 함수
function parseWordPressSEO(text) {
    const result = {
        title: "",
        slug: "",
        focus_keyword: "",
        seo_title: "",
        meta_description: "",
        categories: "",
        tags: "",
        featured_image_alt: "",
        og_title: "",
        og_description: "",
        html_body: ""
    };
    
    if (!text) return result;
    
    const markerPatterns = ["[본문 HTML]", "본문 HTML:", "- 본문 HTML:", "[HTML 본문]", "HTML 본문:"];
    let markerIdx = -1;
    let markerLength = 0;
    for (const marker of markerPatterns) {
        const idx = text.indexOf(marker);
        if (idx !== -1 && (markerIdx === -1 || idx < markerIdx)) {
            markerIdx = idx;
            markerLength = marker.length;
        }
    }
    
    let headerText = text;
    let bodyText = "";
    
    if (markerIdx !== -1) {
        headerText = text.substring(0, markerIdx);
        bodyText = text.substring(markerIdx + markerLength).trim();
    } else {
        const htmlStart = text.search(/<h[1-6]|<p|<ul|<ol|<div|<section/i);
        if (htmlStart !== -1) {
            headerText = text.substring(0, htmlStart);
            bodyText = text.substring(htmlStart).trim();
        }
    }
    
    const lines = headerText.split('\n');
    lines.forEach(line => {
        const trimmed = line.trim();
        if (!trimmed) return;
        
        const match = trimmed.match(/^[-*\s]*([^:]+)\s*:\s*(.*)$/);
        if (match) {
            const key = match[1].trim();
            const val = match[2].trim();
            
            if (key.includes("WordPress 제목") || key.includes("제목")) {
                result.title = val;
            } else if (key.includes("Slug") || key.includes("슬러그")) {
                result.slug = val;
            } else if (key.includes("포커스 키워드") || key.includes("키워드")) {
                result.focus_keyword = val;
            } else if (key.includes("SEO 제목")) {
                result.seo_title = val;
            } else if (key.includes("메타 설명") || key.includes("설명")) {
                result.meta_description = val;
            } else if (key.includes("카테고리")) {
                result.categories = val;
            } else if (key.includes("태그")) {
                result.tags = val;
            } else if (key.includes("대표 이미지 ALT") || key.includes("ALT")) {
                result.featured_image_alt = val;
            } else if (key.includes("OG 제목") || key.includes("Open Graph 제목")) {
                result.og_title = val;
            } else if (key.includes("OG 설명") || key.includes("Open Graph 설명")) {
                result.og_description = val;
            }
        }
    });
    
    let cleanBody = bodyText;
    if (cleanBody.startsWith("```")) {
        cleanBody = cleanBody.replace(/^```[a-zA-Z0-9]*\n/, "");
        cleanBody = cleanBody.replace(/\n```$/, "");
        cleanBody = cleanBody.trim();
    }
    
    result.html_body = cleanBody;
    return result;
}
window.parseWordPressSEO = parseWordPressSEO;

// WordPress 메타 행 UI 렌더링 헬퍼 함수
function createWpMetaRow(label, value, uniqueId, fieldKey) {
    return `
        <div class="wp-meta-row" style="display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: #0f172a; border-radius: 6px; border: 1px solid #334155; gap: 12px;">
            <div style="flex: 1; display: flex; flex-direction: column; min-width: 0;">
                <span style="color: #94a3b8; font-size: 0.75rem; font-weight: 600;">${label}</span>
                <span id="${uniqueId}" style="color: #f1f5f9; font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px;">${value || '(없음)'}</span>
            </div>
            <button type="button" class="btn-copy secondary" style="padding: 4px 8px; font-size: 0.75rem; min-width: 50px;" onclick="copyWpMetaField('${fieldKey}', '${label}')">복사</button>
        </div>
    `;
}
window.createWpMetaRow = createWpMetaRow;

// 특정 메타 필드 복사 헬퍼 함수
function copyWpMetaField(fieldKey, label) {
    if (!window.wpCachedData || !window.wpCachedData[fieldKey]) {
        showToast('복사할 내용이 없습니다.');
        return;
    }
    copyTextDirect(window.wpCachedData[fieldKey], label);
}
window.copyWpMetaField = copyWpMetaField;

// SEO 메타 정보 전체 복사 헬퍼 함수
function copyWpSeoMetaAll() {
    if (!window.wpCachedData) return;
    const seoMetaText = `[WordPress 제목]: ${window.wpCachedData.title}
[Slug]: ${window.wpCachedData.slug}
[포커스 키워드]: ${window.wpCachedData.focus_keyword}
[SEO 제목]: ${window.wpCachedData.seo_title}
[메타 설명]: ${window.wpCachedData.meta_description}
[카테고리]: ${window.wpCachedData.categories}
[태그]: ${window.wpCachedData.tags}
[대표 이미지 ALT]: ${window.wpCachedData.featured_image_alt}
[OG 제목]: ${window.wpCachedData.og_title}
[OG 설명]: ${window.wpCachedData.og_description}`;
    copyTextDirect(seoMetaText, 'SEO 메타 정보 전체');
}
window.copyWpSeoMetaAll = copyWpSeoMetaAll;

// WordPress 본문 HTML 복사 헬퍼 함수
function copyWpBodyHtml() {
    if (!window.wpCachedData) return;
    copyTextDirect(window.wpCachedData.html_body, '본문 HTML');
}
window.copyWpBodyHtml = copyWpBodyHtml;

// WordPress 본문 HTML 미리보기 헬퍼 함수
function previewWpBodyHtml() {
    if (!window.wpCachedData) return;
    previewHtmlDirect(window.wpCachedData.html_body);
}
window.previewWpBodyHtml = previewWpBodyHtml;

// WordPress 전체 패키지 복사 헬퍼 함수
function copyWpPackageAll() {
    if (!window.wpCachedData) return;
    const fullPackageText = `[WordPress 제목]
${window.wpCachedData.title}

[Slug]
${window.wpCachedData.slug}

[포커스 키워드]
${window.wpCachedData.focus_keyword}

[SEO 제목]
${window.wpCachedData.seo_title}

[메타 설명]
${window.wpCachedData.meta_description}

[카테고리]
${window.wpCachedData.categories}

[태그]
${window.wpCachedData.tags}

[대표 이미지 ALT]
${window.wpCachedData.featured_image_alt}

[OG 제목]
${window.wpCachedData.og_title}

[OG 설명]
${window.wpCachedData.og_description}

[본문 HTML]
${window.wpCachedData.html_body}`;
    copyTextDirect(fullPackageText, '전체 패키지');
}
window.copyWpPackageAll = copyWpPackageAll;

// 클립보드 직접 복사 헬퍼 함수 (토스트 연동)
async function copyTextDirect(text, label) {
    if (!text) {
        showToast('복사할 내용이 없습니다.');
        return false;
    }
    let success = false;
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        try {
            await navigator.clipboard.writeText(text);
            showToast(`${label} 복사 완료`);
            success = true;
        } catch (err) {
            console.warn('Modern clipboard copy failed, falling back', err);
        }
    }
    if (!success) {
        try {
            const textarea = document.createElement("textarea");
            textarea.value = text;
            textarea.style.position = "fixed";
            textarea.style.top = "-9999px";
            textarea.style.left = "-9999px";
            document.body.appendChild(textarea);
            textarea.select();
            textarea.setSelectionRange(0, 99999);
            const successful = document.execCommand("copy");
            document.body.removeChild(textarea);
            if (successful) {
                showToast(`${label} 복사 완료`);
                success = true;
            } else {
                alert('복사에 실패했습니다. 직접 선택해서 복사해 주세요.');
            }
        } catch (err) {
            alert('복사에 실패했습니다. 직접 선택해서 복사해 주세요.');
        }
    }
    if (success) {
        if (typeof logActivity === 'function') {
            logActivity("html_copy", "project", window.currentProjectId, JSON.stringify({ channel: "WORDPRESS_SEO", type: "plain_text", label: label }));
        }
    }
    return success;
}
window.copyTextDirect = copyTextDirect;

// HTML 본문 새 창 미리보기 헬퍼 함수
function previewHtmlDirect(html) {
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener,noreferrer");
    if (typeof logActivity === 'function') {
        logActivity("preview_open", "project", window.currentProjectId, JSON.stringify({ channel: "WORDPRESS_SEO", type: "html_browser" }));
    }
}
window.previewHtmlDirect = previewHtmlDirect;

// StoryMaker legacy /storymaker safety guard
// 외부망/LTE에서 중복 클릭과 작업 꼬임을 줄이기 위한 최소 안전장치입니다.
(function initStoryMakerLegacySafetyGuard() {
    if (window.__storymakerLegacySafetyGuardLoaded) return;
    window.__storymakerLegacySafetyGuardLoaded = true;
    if (!/\/storymaker\/?$/.test(window.location.pathname || '')) return;

    const state = {
        busy: false,
        reason: '',
        lastActionAt: 0,
        releaseTimer: null,
        resultWatcher: null,
        original: new WeakMap()
    };

    window.__storymakerLegacySafetyState = state;

    function notify(message) {
        if (typeof window.showToast === 'function') {
            window.showToast(message);
            return;
        }
        if (typeof window.log === 'function') {
            window.log('[안전장치] ' + message, 'warning');
            return;
        }
        console.warn('[StoryMaker Safety]', message);
    }

    function elementText(el) {
        return String(
            (el && (el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.getAttribute('title'))) || ''
        ).trim();
    }

    function isActionElement(el) {
        if (!el || !el.matches) return false;
        const raw = [
            el.id || '',
            el.name || '',
            el.className || '',
            el.getAttribute('onclick') || '',
            elementText(el)
        ].join(' ').toLowerCase();

        return /(생성|만들기|결과\s*정리|사진\s*반영|팟캐스트|숏폼|쇼츠|릴스|ai|프롬프트|prompt|generate|slideshow|shortform|podcast)/i.test(raw);
    }

    function getActionControls() {
        const candidates = Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"], a.btn-copy, .btn-copy'));
        return candidates.filter(isActionElement);
    }

    function remember(el) {
        if (!el || state.original.has(el)) return;
        state.original.set(el, {
            text: elementText(el),
            disabled: !!el.disabled,
            pointerEvents: el.style.pointerEvents || '',
            opacity: el.style.opacity || '',
            ariaDisabled: el.getAttribute('aria-disabled')
        });
    }

    function setControlLocked(el, locked) {
        if (!el) return;
        remember(el);
        const original = state.original.get(el) || {};

        if (locked) {
            if ('disabled' in el) el.disabled = true;
            el.setAttribute('aria-disabled', 'true');
            el.style.pointerEvents = 'none';
            el.style.opacity = '0.58';
            const current = elementText(el);
            if (current && !/진행|생성중|처리중|대기/.test(current)) {
                if (el.tagName === 'INPUT') el.value = '작업 진행 중';
                else el.textContent = current + ' · 진행 중';
            }
            return;
        }

        if ('disabled' in el) el.disabled = !!original.disabled;
        if (original.ariaDisabled === null || original.ariaDisabled === undefined) {
            el.removeAttribute('aria-disabled');
        } else {
            el.setAttribute('aria-disabled', original.ariaDisabled);
        }
        el.style.pointerEvents = original.pointerEvents || '';
        el.style.opacity = original.opacity || '';
        if (original.text) {
            if (el.tagName === 'INPUT') el.value = original.text;
            else el.textContent = original.text;
        }
    }

    function hasParsedResult() {
        try {
            if (window.lastParsedBlocks && Object.keys(window.lastParsedBlocks).length > 0) return true;
            const rawInput = document.getElementById('chatgpt-raw-input');
            const value = rawInput ? String(rawInput.value || rawInput.textContent || '') : '';
            if (/\[BLOCK:(BLOG_TITLES|BLOG_POST|NAVER_PLACE_NEWS|GOOGLE_BUSINESS_POST|INSTAGRAM_POST|PODCAST_50|PODCAST_80|CAROUSEL_7)\]/.test(value)) return true;
            const panes = document.getElementById('content-panes');
            if (panes && panes.querySelector('.sns-page, .tab-content, .content-page')) return true;
        } catch (err) {
            return false;
        }
        return false;
    }

    function clearTimers() {
        if (state.releaseTimer) window.clearTimeout(state.releaseTimer);
        if (state.resultWatcher) window.clearInterval(state.resultWatcher);
        state.releaseTimer = null;
        state.resultWatcher = null;
    }

    function setBusy(on, reason, options = {}) {
        state.busy = !!on;
        state.reason = on ? (reason || '작업 진행 중') : '';
        clearTimers();

        getActionControls().forEach(el => setControlLocked(el, on));

        const rawInput = document.getElementById('chatgpt-raw-input');
        if (rawInput) {
            if (!on) {
                rawInput.disabled = false;
            } else if (/AI|결과|생성|parse|trigger/i.test(reason || '')) {
                rawInput.disabled = true;
            }
        }

        if (!on) return;

        const maxMs = Number(options.maxMs || 180000);
        if (options.waitForResult) {
            state.resultWatcher = window.setInterval(function () {
                if (hasParsedResult()) setBusy(false, 'result-ready');
            }, 1200);
        }
        state.releaseTimer = window.setTimeout(function () {
            setBusy(false, 'timeout-release');
        }, maxMs);
    }

    document.addEventListener('click', function (event) {
        const target = event.target && event.target.closest ? event.target.closest('button, input[type="button"], input[type="submit"], a.btn-copy, .btn-copy') : null;
        if (!target || !isActionElement(target)) return;

        const now = Date.now();
        if (state.busy || now - state.lastActionAt < 900) {
            event.preventDefault();
            event.stopPropagation();
            notify('현재 작업이 진행 중입니다. 완료 후 다시 눌러 주세요.');
            return false;
        }
        state.lastActionAt = now;
    }, true);

    const nativeFetch = window.fetch;
    if (typeof nativeFetch === 'function' && !nativeFetch.__storymakerLegacySafetyWrapped) {
        const wrappedFetch = async function (input, init) {
            const url = String(typeof input === 'string' ? input : (input && input.url) || '');
            const isAiStart = /\/api\/test\/(trigger|run|start)/.test(url);
            const isAiParse = /\/api\/(parse-result|test\/result-package)/.test(url);
            const isMediaStart = /\/api\/(slideshow\/(run|create)|podcast\/run)/.test(url);

            if (isAiStart) setBusy(true, 'AI 결과 생성 중', { waitForResult: true, maxMs: 240000 });
            else if (isAiParse) setBusy(true, 'AI 결과 정리 중', { waitForResult: true, maxMs: 120000 });
            else if (isMediaStart) setBusy(true, '미디어 생성 중', { maxMs: 240000 });

            let response;
            try {
                response = await nativeFetch.apply(this, arguments);
                return response;
            } catch (err) {
                if (isAiStart || isAiParse || isMediaStart) {
                    window.setTimeout(function () { setBusy(false, 'request-error'); }, 500);
                }
                throw err;
            } finally {
                if (isAiStart && response && response.ok === false) {
                    window.setTimeout(function () { setBusy(false, 'ai-request-failed'); }, 500);
                } else if (isAiParse) {
                    window.setTimeout(function () { setBusy(false, 'parse-complete'); }, 1200);
                } else if (isMediaStart) {
                    window.setTimeout(function () { setBusy(false, 'media-request-complete'); }, 2000);
                } else if (isAiStart && hasParsedResult()) {
                    window.setTimeout(function () { setBusy(false, 'ai-result-ready'); }, 1200);
                }
            }
        };
        wrappedFetch.__storymakerLegacySafetyWrapped = true;
        window.fetch = wrappedFetch;
    }

    window.addEventListener('pagehide', function () { setBusy(false, 'pagehide'); });
})();
