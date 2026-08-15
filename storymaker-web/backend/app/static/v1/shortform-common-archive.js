(() => {
  'use strict';

  if (window.__STORYMAKER_SHORTFORM_COMMON_ARCHIVE__) return;
  window.__STORYMAKER_SHORTFORM_COMMON_ARCHIVE__ = true;

  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();

  function isShortformScreen() {
    const path = location.pathname.toLowerCase();
    if (path.includes('shortform') || path.includes('reels')) return true;
    return Array.from(document.querySelectorAll('h1,h2,h3')).some((el) =>
      /reels\s*\/\s*shorts|릴스\s*\/\s*쇼츠/i.test(clean(el.textContent)),
    );
  }

  function findArchiveMenuButton() {
    const labels = Array.from(document.querySelectorAll('button,a,[role="button"],[role="menuitem"],li,div,span'));
    for (const label of labels) {
      if (clean(label.textContent) !== '보관함') continue;
      if (label.dataset.storymakerArchiveProxy === '1') continue;

      const clickable = label.closest('button,a,[role="button"],[role="menuitem"],li') || label;
      if (clickable.dataset.storymakerArchiveProxy === '1') continue;

      const rect = clickable.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) return clickable;
    }
    return null;
  }

  function openCommonArchive(event) {
    event?.preventDefault?.();
    event?.stopImmediatePropagation?.();

    const archiveButton = findArchiveMenuButton();
    if (archiveButton) {
      archiveButton.click();
      return;
    }

    // SPA 메뉴가 아직 렌더링되지 않은 경우 새로고침 뒤에도 보관함 진입 의도를 유지한다.
    sessionStorage.setItem('storymaker_open_common_archive', '1');
    location.assign('/v1/');
  }

  function bindArchiveButtons() {
    if (!isShortformScreen()) return;

    for (const button of document.querySelectorAll('button,a,[role="button"]')) {
      if (clean(button.textContent) !== '내보관함') continue;
      if (button.dataset.storymakerArchiveProxy === '1') continue;

      button.dataset.storymakerArchiveProxy = '1';
      button.removeAttribute('href');
      button.addEventListener('click', openCommonArchive, true);
      button.title = 'V2 공용 보관함 열기';
    }
  }

  function resumeArchiveNavigation() {
    if (sessionStorage.getItem('storymaker_open_common_archive') !== '1') return;
    const archiveButton = findArchiveMenuButton();
    if (!archiveButton) return;
    sessionStorage.removeItem('storymaker_open_common_archive');
    archiveButton.click();
  }

  function extractThumbnailUrl(payload) {
    const roots = [payload, payload?.data, payload?.result, payload?.data?.result].filter(Boolean);
    const keys = [
      'final_image_url',
      'image_url',
      'thumbnail_url',
      'thumbnail_prepared_collage_url',
      'thumbnail_collage_url',
    ];

    for (const root of roots) {
      for (const key of keys) {
        const value = clean(root?.[key]);
        if (value) return value;
      }
      const list = root?.image_urls || root?.images;
      if (Array.isArray(list) && clean(list[0])) return clean(list[0]);
    }
    return '';
  }

  function thumbnailJobIds() {
    const keys = [
      'storymaker_thumbnail_job_id',
      'storymaker_thumbnail_pending_job_v1',
      'storymaker_thumbnail_request_started',
    ];
    const ids = [];
    for (const storage of [localStorage, sessionStorage]) {
      for (const key of keys) {
        const raw = clean(storage.getItem(key));
        if (!raw) continue;
        try {
          const parsed = JSON.parse(raw);
          const id = clean(parsed?.job_id || parsed?.jobId || parsed?.thumbnail_job_id || parsed);
          if (id) ids.push(id);
        } catch {
          ids.push(raw);
        }
      }
    }
    return [...new Set(ids.filter((id) => /^[a-z0-9_.-]+$/i.test(id)))];
  }

  async function resolveThumbnailUrl() {
    const ids = thumbnailJobIds();
    for (const id of ids) {
      try {
        const response = await fetch(`/v1-api/test/thumbnail-result/${encodeURIComponent(id)}?t=${Date.now()}`, {
          cache: 'no-store',
          credentials: 'same-origin',
        });
        if (!response.ok) continue;
        const url = extractThumbnailUrl(await response.json());
        if (url) return url;
      } catch (_) {}
    }

    try {
      const response = await fetch(`/v1-api/test/thumbnail-result/latest?t=${Date.now()}`, {
        cache: 'no-store',
        credentials: 'same-origin',
      });
      if (response.ok) {
        const url = extractThumbnailUrl(await response.json());
        if (url) return url;
      }
    } catch (_) {}

    return '';
  }

  function findThumbnailSection() {
    const labels = Array.from(document.querySelectorAll('h1,h2,h3,h4,p,span,strong,div'))
      .filter((el) => clean(el.textContent) === '썸네일 미리보기');
    const label = labels[0];
    if (!label) return null;

    let node = label.parentElement;
    while (node && node !== document.body) {
      if (node.querySelector('button,a,img')) return node;
      node = node.parentElement;
    }
    return label.parentElement;
  }

  function applyThumbnail(section, url) {
    if (!section || !url) return;
    section.dataset.storymakerThumbnailUrl = url;

    let image = section.querySelector('img[data-storymaker-thumbnail-preview="1"]');
    if (!image) {
      const existing = Array.from(section.querySelectorAll('img')).find((img) => {
        const src = clean(img.currentSrc || img.src);
        return !src.startsWith('data:image/svg') && !/logo|icon/i.test(src);
      });
      image = existing || document.createElement('img');
      image.dataset.storymakerThumbnailPreview = '1';
      if (!existing) {
        image.alt = '생성된 썸네일 미리보기';
        image.style.cssText = 'display:block;max-width:420px;width:100%;height:auto;margin:16px auto;border-radius:16px;object-fit:contain;';
        const label = Array.from(section.querySelectorAll('*')).find((el) => clean(el.textContent) === '썸네일 미리보기');
        (label?.parentElement || section).appendChild(image);
      }
    }
    if (image.src !== new URL(url, location.origin).href) image.src = url;

    for (const button of section.querySelectorAll('button,a,[role="button"]')) {
      if (clean(button.textContent) !== '썸네일 다운로드') continue;
      button.disabled = false;
      button.removeAttribute('disabled');
      button.style.pointerEvents = 'auto';
      button.style.opacity = '1';
      button.dataset.storymakerThumbnailDownload = '1';
      button.onclick = null;
      button.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `storymaker-thumbnail-${Date.now()}.png`;
        anchor.rel = 'noopener';
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
      }, true);
    }
  }

  let resolving = false;
  async function repairThumbnail() {
    if (resolving) return;
    const section = findThumbnailSection();
    if (!section || section.dataset.storymakerThumbnailResolved === '1') return;

    resolving = true;
    try {
      const url = await resolveThumbnailUrl();
      if (!url) return;
      applyThumbnail(section, url);
      section.dataset.storymakerThumbnailResolved = '1';
      console.info('[StoryMaker Shortform] thumbnail linked:', url);
    } finally {
      resolving = false;
    }
  }

  function applyAll() {
    bindArchiveButtons();
    resumeArchiveNavigation();
    void repairThumbnail();
  }

  applyAll();
  new MutationObserver(applyAll).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
  window.addEventListener('popstate', applyAll);

  console.info('[StoryMaker V1 Shortform] local archive and thumbnail resolver active.');
})();
