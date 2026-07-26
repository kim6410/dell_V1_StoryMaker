// StoryMaker 프론트엔드 AI 결과 파서 및 마크다운 변환 유틸 (app_generator_parser.js)

// SNS 채널 키 - 한글 라벨 매핑 객체
const labelMap = {
    "BLOG": "블로그",
    "CARROT": "당근",
    "INSTAGRAM": "인스타",
    "NAVER_PLACE": "플레이스",
    "GOOGLE_BUSINESS": "구글",
    "PODCAST_50": "팟캐스트50s",
    "PODCAST_80": "팟캐스트80s",
    "CAROUSEL_7": "카드뉴스",
    "WORDPRESS_SEO": "WordPress SEO"
};
window.labelMap = labelMap;

// 8개 통합 채널 결과 탭UI 동적 바인딩 및 복사/미리보기 버튼 생성
function getChannelColor(key) {
    return {
        BLOG: '#22c55e',
        NAVER_PLACE: '#00c73c',
        GOOGLE_BUSINESS: '#4285f4',
        INSTAGRAM: '#a855f7',
        CARROT: '#f97316',
        CAROUSEL_7: '#8b5cf6',
        PODCAST_50: '#06b6d4',
        PODCAST_80: '#06b6d4',
        WORDPRESS_SEO: '#38bdf8'
    }[key] || '#0ea5e9';
}
window.getChannelColor = getChannelColor;

// 네이버 블로그용 HTML 변환 규칙 적용 함수 (마크다운 후처리)
function convertBlogToHtml(title, post, hashtags) {
    const pickMainBlogTitle = (titleText) => {
        const normalized = String(titleText || '')
            .replace(/^(제목:|title:)\s*/i, '')
            .replace(/\s+/g, ' ')
            .trim();
        if (!normalized) return '제목 없음';
        const numberedTitles = normalized
            .split(/\s+\d+\.\s+/)
            .map(v => v.trim())
            .filter(Boolean);
        if (numberedTitles.length > 1 && /^1\.\s*/.test(normalized)) {
            return numberedTitles[0].replace(/^1\.\s*/, '').trim() || '제목 없음';
        }
        return normalized.replace(/^1\.\s*/, '').trim() || '제목 없음';
    };
    const pickRecommendedBlogTitles = (titleText) => {
        const normalized = String(titleText || '')
            .replace(/^(제목:|title:)\s*/i, '')
            .replace(/\s+/g, ' ')
            .trim();
        if (!normalized) return [];
        const matches = Array.from(normalized.matchAll(/(?:^|\s)(\d+)\.\s*(.*?)(?=\s+\d+\.\s*|$)/g));
        const titles = matches
            .map(match => match[2].trim())
            .filter(Boolean)
            .slice(0, 5);
        return titles.length ? titles : [pickMainBlogTitle(normalized)];
    };
    const cleanTitle = title ? pickMainBlogTitle(title) : '제목 없음';
    const recommendedTitles = pickRecommendedBlogTitles(title);
    const formatInlineMarkdown = (text) => text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    
    let bodyHtml = '';
    if (post) {
        const paragraphs = post.split(/\n\s*\n/);
        paragraphs.forEach(para => {
            para = para.trim();
            if (!para) return;
            
            if (para.startsWith('###')) {
                const text = para.replace(/^###\s*/, '').trim();
                bodyHtml += `<h3>${text}</h3>`;
            } else if (para.startsWith('##')) {
                const text = para.replace(/^##\s*/, '').trim();
                bodyHtml += `<h2>${text}</h2>`;
            } else if (para.startsWith('#')) {
                const text = para.replace(/^#\s*/, '').trim();
                if (text && text !== cleanTitle) {
                    bodyHtml += `<h2>${formatInlineMarkdown(text)}</h2>`;
                }
            } else if (para.startsWith('**') && para.endsWith('**') && para.length < 100) {
                const text = para.replace(/^\*\*|\*\*$/g, '').trim();
                bodyHtml += `<h3>${text}</h3>`;
            } else if (para.startsWith('[') && para.endsWith(']') && para.length < 60) {
                const text = para.slice(1, -1).trim();
                bodyHtml += `<h3>${text}</h3>`;
            } else if (para.startsWith('■') || para.startsWith('▶') || para.startsWith('◆')) {
                if (para.indexOf('\n') === -1 && para.length < 80) {
                    bodyHtml += `<h2>${formatInlineMarkdown(para)}</h2>`;
                } else {
                    bodyHtml += `<p>${formatInlineMarkdown(para)}</p>`;
                }
            } else {
                bodyHtml += `<p>${formatInlineMarkdown(para)}</p>`;
            }
        });
    }
    
    let tagsHtml = '';
    if (hashtags) {
        const tagMatches = hashtags.match(/#[^\s,]+/g);
        if (tagMatches) {
            tagsHtml += '<div class="tags-container">';
            tagMatches.forEach(tag => {
                tagsHtml += `<span class="tag">${tag}</span>`;
            });
            tagsHtml += '</div>';
        }
    }
    
    return `<!DOCTYPE html>
<html lang="ko">
<head>
    <meta name="robots" content="noindex, nofollow">
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${cleanTitle} - 네이버 블로그 미리보기</title>
  <style>
    body {
      background-color: #f4f6f9;
      margin: 0;
      padding: 40px 20px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans KR", sans-serif;
      color: #333333;
      display: flex;
      justify-content: center;
    }
    .container {
      max-width: 720px;
      width: 100%;
      background-color: #ffffff;
      padding: 40px;
      box-sizing: border-box;
      border-radius: 12px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
      border: 1px solid #e1e4e6;
    }
    h1 {
      font-size: 26px;
      font-weight: 800;
      line-height: 1.4;
      margin-top: 10px;
      margin-bottom: 30px;
      color: #111111;
      border-bottom: 2px solid #00c73c;
      padding-bottom: 15px;
      word-break: keep-all;
    }
    h2 {
      font-size: 20px;
      font-weight: 700;
      line-height: 1.5;
      margin-top: 35px;
      margin-bottom: 15px;
      color: #222222;
      border-left: 4px solid #00c73c;
      padding-left: 12px;
    }
    h3 {
      font-size: 18px;
      font-weight: 700;
      line-height: 1.5;
      margin-top: 30px;
      margin-bottom: 12px;
      color: #333333;
      border-left: 4px solid #00c73c;
      padding-left: 12px;
    }
    p {
      font-size: 17px;
      line-height: 1.8;
      margin-top: 0;
      margin-bottom: 24px;
      color: #444444;
      word-break: break-all;
      white-space: pre-wrap;
    }
    .tags-container {
      margin-top: 40px;
      padding-top: 20px;
      border-top: 1px dashed #e1e4e6;
    }
    .tag {
      display: inline-block;
      background-color: #f1f3f5;
      color: #00c73c;
      padding: 6px 12px;
      font-size: 14px;
      border-radius: 20px;
      margin-right: 8px;
      margin-bottom: 8px;
      font-weight: 600;
    }
    .seo-helper {
      background-color: #f8f9fa;
      border: 1px solid #e9ecef;
      border-radius: 8px;
      padding: 15px;
      margin-bottom: 30px;
      font-size: 13px;
      color: #666;
    }
    .seo-helper-title {
      font-weight: 700;
      color: #333;
      margin-bottom: 5px;
    }
    .recommend-title-box {
      margin: 28px 0 34px;
      padding: 20px 22px;
      border: 1px solid #22c55e;
      border-radius: 12px;
      background: #f7fff9;
    }
    .recommend-title-label {
      margin-bottom: 12px;
      font-size: 19px;
      line-height: 1.35;
      font-weight: 800;
      color: #16a34a;
    }
    .recommend-title-box ol {
      margin: 0;
      padding: 0;
      list-style: none;
      counter-reset: recommend-title;
    }
    .recommend-title-box li {
      counter-increment: recommend-title;
      position: relative;
      padding: 9px 0 9px 34px;
      border-top: 1px dashed #d7e7dc;
      font-size: 15px;
      line-height: 1.55;
      font-weight: 600;
      color: #1f2937;
    }
    .recommend-title-box li:first-child {
      border-top: 0;
    }
    .recommend-title-box li::before {
      content: counter(recommend-title);
      position: absolute;
      left: 0;
      top: 10px;
      width: 22px;
      height: 22px;
      border-radius: 7px;
      background: #22c55e;
      color: #fff;
      font-size: 12px;
      line-height: 22px;
      text-align: center;
      font-weight: 800;
    }
    h2, h3 {
      margin-top: 34px;
      padding-top: 22px;
      border-top: 1px dashed #cfd8dc;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="seo-helper">
      <div class="seo-helper-title">💡 네이버 블로그 SEO 및 포스팅 가이드</div>
      본 미리보기는 글자 크기 17px, 줄간격 1.8의 모바일 가독성 최적화(최대 너비 720px)로 렌더링되었습니다. 
      상단의 초록색 라인은 <strong>H1 제목</strong>, 왼쪽 초록색 바는 <strong>H2/H3 소제목</strong> 지표를 나타내며, 본문은 <strong>P 문단</strong> 구조로 깔끔하게 구성되어 검색 엔진 최적화(SEO) 점수에 매우 유리합니다.
    </div>
    ${recommendedTitles.length ? `
    <section class="recommend-title-box">
      <div class="recommend-title-label">추천 제목</div>
      <ol>
        ${recommendedTitles.map(v => `<li>${escapeHtml(v)}</li>`).join('')}
      </ol>
    </section>
    ` : ''}
    <h1>${cleanTitle}</h1>
    ${bodyHtml}
    ${tagsHtml}
  </div>
</body>
</html>`;
}
window.convertBlogToHtml = convertBlogToHtml;

// ChatGPT 결과 원문 파싱 분리 요청 (SNS별 분리 연동)
async function parseChatGPTResult() {
    const rawText = document.getElementById('chatgpt-raw-input')?.value || '';
    if (!rawText.trim()) {
        alert('파싱할 ChatGPT 출력 원문을 입력해 주세요.');
        return;
    }

    log('ChatGPT 원문 코드 블록 식별 및 채널별 분리 중...');

    try {
        const response = await fetchWithAuth('/api/parse-result', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ raw_result: rawText })
        });

        if (!response.ok) throw new Error(`HTTP 에러: ${response.status}`);

        const res = await response.json();
        if (res.ok && res.data && res.data.blocks) {
            window.lastParsedBlocks = res.data.blocks;
            
            if (typeof renderParsedTabs === 'function') {
                renderParsedTabs(window.lastParsedBlocks);
            }
            log(`파싱 완료: 총 ${Object.keys(window.lastParsedBlocks).length}개 마케팅 채널 격리 성공`, 'success');
            if (typeof scrollToSnsResultArea === 'function') {
                scrollToSnsResultArea();
            }
            
            if (typeof triggerAutosave === 'function') {
                triggerAutosave();
            }

            // Check if BLOG_TITLES, BLOG_POST, INSTAGRAM_POST, CAROUSEL_7 are all present
            const hasBlogTitles = !!window.lastParsedBlocks["BLOG_TITLES"];
            const hasBlogPost = !!window.lastParsedBlocks["BLOG_POST"];
            const hasInstaPost = !!window.lastParsedBlocks["INSTAGRAM_POST"];
            const hasCarousel = !!window.lastParsedBlocks["CAROUSEL_7"];

            if (hasBlogTitles && hasBlogPost && hasInstaPost && hasCarousel) {
                if (typeof sendHealthLog === 'function') {
                    await sendHealthLog('storymaker_sns_split_done');
                    await sendHealthLog('thumbnail_job_create_start');
                }
                
                try {
                    const jobRes = await fetchWithAuth('/api/test/thumbnail-job-auto', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    const jobData = await jobRes.json();
                    if (jobRes.ok && jobData.ok) {
                        if (typeof sendHealthLog === 'function') {
                            await sendHealthLog('thumbnail_job_create_done', { job_id: jobData.job_id });
                        }
                    } else {
                        throw new Error(jobData.message || 'Job creation failed');
                    }
                } catch (e) {
                    if (typeof sendHealthLog === 'function') {
                        await sendHealthLog('thumbnail_job_create_failed', { error: e.message });
                    }
                }
            } else {
                if (typeof sendHealthLog === 'function') {
                    await sendHealthLog('gemini_reset_skipped_no_thumbnail_job', {
                        hasBlogTitles, hasBlogPost, hasInstaPost, hasCarousel
                    });
                }
            }
        } else {
            throw new Error(res.message || '분리 연산 실패');
        }
    } catch (err) {
        log(`결과 파싱 에러: ${err.message}`, 'error');
        alert(`결과 파싱 오류: ${err.message}`);
    }
}
window.parseChatGPTResult = parseChatGPTResult;
