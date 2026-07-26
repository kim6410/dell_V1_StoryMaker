// StoryMaker 프론트엔드 WordPress 초안 및 발행 연동 유틸 (app_generator_wordpress.js)

// WordPress 초안 자동 등록 및 즉시 발행 처리 함수
async function sendWordPressDraft(status = 'draft') {
    const userStr = localStorage.getItem('storymaker_user');
    const user = userStr ? JSON.parse(userStr) : null;
    if (!user) {
        if (typeof showToast === 'function') {
            showToast('오류: 로그인이 필요합니다.');
        } else {
            alert('오류: 로그인이 필요합니다.');
        }
        return;
    }
    if (user.role !== 'admin' && user.tier !== 'paid') {
        if (typeof showToast === 'function') {
            showToast('🔒 워드프레스 연동은 Premium 결제 사용자 전용 기능입니다.');
        } else {
            alert('🔒 워드프레스 연동은 Premium 결제 사용자 전용 기능입니다.');
        }
        return;
    }
    if (!user.wp_enabled) {
        if (typeof showToast === 'function') {
            showToast('⚙️ 마이페이지 설정에서 워드프레스 연동을 활성화해 주세요.');
        } else {
            alert('⚙️ 마이페이지 설정에서 워드프레스 연동을 활성화해 주세요.');
        }
        return;
    }

    const cachedBlocks = window.lastParsedBlocks;
    const cachedWpData = window.wpCachedData;

    const hasStoryMakerBlocks = cachedBlocks && cachedBlocks.BLOG_POST;
    if (!hasStoryMakerBlocks && !cachedWpData) {
        if (typeof showToast === 'function') {
            showToast('WordPress로 보낼 블로그 데이터가 없습니다.');
        } else {
            alert('WordPress로 보낼 블로그 데이터가 없습니다.');
        }
        return;
    }

    const btn = document.getElementById('btn-send-wordpress-draft') || document.getElementById('btn-send-wordpress-draft-blog');
    if (btn) {
        btn.disabled = true;
        btn.innerText = status === 'publish' ? 'WordPress 발행 중...' : 'WordPress 초안 저장 중...';
        btn.style.opacity = '0.7';
    }

    try {
        const payload = {
            title: cachedWpData.title || cachedWpData.seo_title || '제목 없음',
            slug: cachedWpData.slug || '',
            content: cachedWpData.html_body || '',
            excerpt: cachedWpData.meta_description || cachedWpData.og_description || '',
            status: status,
            tags_text: cachedWpData.tags || '',
            categories_text: cachedWpData.categories || '',
            meta_description: cachedWpData.meta_description || '',
            focus_keyword: cachedWpData.focus_keyword || '',
            featured_image_alt: cachedWpData.featured_image_alt || ''
        };

        const response = await fetchWithAuth('/api/wordpress/draft', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const raw = await response.text();
        let res = {};
        try {
            res = raw ? JSON.parse(raw) : {};
        } catch (parseErr) {
            res = { detail: raw || 'WordPress 서버가 JSON이 아닌 응답을 반환했습니다.' };
        }
        if (!response.ok) {
            const errorMsg = typeof normalizeErrorMessage === 'function'
                ? (normalizeErrorMessage(res.detail) || normalizeErrorMessage(res.message) || 'WordPress 초안 등록 실패')
                : (res.detail || res.message || 'WordPress 초안 등록 실패');
            throw new Error(errorMsg);
        }

        const wpStatusLabel = status === 'publish' ? '발행' : '초안 등록';
        if (typeof showToast === 'function') {
            showToast(`WordPress ${wpStatusLabel} 완료`);
        }
        log(`[WordPress] ${wpStatusLabel} 완료: ID ${res.id}`, 'success');
        if (typeof logActivity === 'function') {
            logActivity('wordpress_draft_create', 'project', window.currentProjectId, JSON.stringify({ post_id: res.id, status: res.status }));
        }

        if (res.link) {
            window.open(res.link, '_blank', 'noopener,noreferrer');
        }
    } catch (err) {
        if (typeof showToast === 'function') {
            showToast('WordPress 전송 실패');
        }
        log(`WordPress 초안 등록 실패: ${err.message}`, 'error');
        alert(`WordPress 초안 등록 실패:\n${err.message}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = btn.id === 'btn-publish-wordpress-blog' ? '즉시 발행' : (btn.id === 'btn-send-wordpress-draft-blog' ? 'WordPress 초안' : 'WordPress 초안으로 보내기');
            btn.style.opacity = '1';
        }
    }
}
window.sendWordPressDraft = sendWordPressDraft;
