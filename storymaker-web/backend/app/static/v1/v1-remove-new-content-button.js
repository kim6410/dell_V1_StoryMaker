(() => {
  'use strict';

  if (window.__STORYMAKER_V1_REMOVE_NEW_CONTENT_BUTTON__) return;
  window.__STORYMAKER_V1_REMOVE_NEW_CONTENT_BUTTON__ = true;

  const TARGET_TEXT = '새 콘텐츠 만들기';
  const clean = (value = '') => String(value).replace(/\s+/g, ' ').trim();

  function removeTargetButton() {
    const candidates = Array.from(document.querySelectorAll('button, a, [role="button"]'));
    for (const node of candidates) {
      if (clean(node.textContent) !== TARGET_TEXT) continue;
      node.remove();
    }
  }

  function boot() {
    removeTargetButton();
    const observer = new MutationObserver(removeTargetButton);
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
