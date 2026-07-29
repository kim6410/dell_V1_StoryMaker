(() => {
  'use strict';

  const MOBILE_QUERY = window.matchMedia('(max-width: 767px)');
  const PRELOAD_DISABLED_KEY = 'storymaker_browser_ai_preload_disabled';
  const AUTO_KEYS = new Set([
    'storymaker_auto_import_podcast',
    'storymaker_auto_run_podcast',
    'storymaker_auto_shortform_after_podcast',
    'storymaker_auto_run_shortform',
    'storymaker_latest_podcast_for_slideshow',
    'storymaker_shortform_draft_v1',
    'storymaker_thumbnail_request_started',
    'storymaker_thumbnail_job_id',
    'storymaker_thumbnail_pending_job_v1',
    'storymaker_thumbnail_request_error'
  ]);

  const originalFetch = window.fetch;
  const OriginalWorker = window.Worker;
  const originalSetItem = Storage.prototype.setItem;
  const originalRemoveItem = Storage.prototype.removeItem;
  const previousPreloadValue = (() => {
    try { return localStorage.getItem(PRELOAD_DISABLED_KEY); } catch { return null; }
  })();

  let active = false;
  let cleanupTimer = null;

  const isLocalStorage = (storage) => {
    try { return storage === window.localStorage; } catch { return false; }
  };

  const shouldBlockAsset = (value) => {
    const text = String(value || '');
    return text.includes('/static/v1/browser-tts/') ||
      text.includes('browserPodcast.worker-') ||
      text.includes('storymaker-browser-podcast');
  };

  const clearAutoFlags = () => {
    for (const storage of [window.sessionStorage, window.localStorage]) {
      for (const key of AUTO_KEYS) {
        try { originalRemoveItem.call(storage, key); } catch {}
      }
    }
  };

  const blockPreloadEvent = (event) => {
    if (!active) return;
    event.preventDefault?.();
    event.stopImmediatePropagation?.();
  };

  function MobileSafeWorker(...args) {
    if (active && shouldBlockAsset(args[0])) {
      throw new DOMException('모바일에서는 Browser AI 음성 엔진을 실행하지 않습니다.', 'AbortError');
    }
    return Reflect.construct(OriginalWorker, args, new.target || OriginalWorker);
  }
  MobileSafeWorker.prototype = OriginalWorker.prototype;
  Object.setPrototypeOf(MobileSafeWorker, OriginalWorker);

  function activate() {
    if (active) return;
    active = true;

    try { originalSetItem.call(localStorage, PRELOAD_DISABLED_KEY, '1'); } catch {}
    clearAutoFlags();

    Storage.prototype.setItem = function mobileSafeSetItem(key, value) {
      const normalized = String(key || '');
      if (active && normalized === PRELOAD_DISABLED_KEY && isLocalStorage(this)) {
        return originalSetItem.call(this, PRELOAD_DISABLED_KEY, '1');
      }
      if (active && AUTO_KEYS.has(normalized)) {
        try { originalRemoveItem.call(this, normalized); } catch {}
        return;
      }
      return originalSetItem.call(this, key, value);
    };

    Storage.prototype.removeItem = function mobileSafeRemoveItem(key) {
      const normalized = String(key || '');
      if (active && normalized === PRELOAD_DISABLED_KEY && isLocalStorage(this)) {
        return originalSetItem.call(this, PRELOAD_DISABLED_KEY, '1');
      }
      return originalRemoveItem.call(this, key);
    };

    window.fetch = function mobileSafeFetch(input, init) {
      const target = typeof input === 'string' ? input : input?.url;
      if (active && shouldBlockAsset(target)) {
        return Promise.reject(new DOMException('모바일 Browser AI 모델 다운로드가 차단되었습니다.', 'AbortError'));
      }
      return originalFetch.call(this, input, init);
    };

    window.Worker = MobileSafeWorker;
    window.addEventListener('storymaker-browser-ai-preload', blockPreloadEvent, true);
    cleanupTimer = window.setInterval(clearAutoFlags, 800);

    document.documentElement.setAttribute('data-sm-mobile-browser-ai-disabled', '1');
  }

  function deactivate() {
    if (!active) return;
    active = false;

    Storage.prototype.setItem = originalSetItem;
    Storage.prototype.removeItem = originalRemoveItem;
    window.fetch = originalFetch;
    window.Worker = OriginalWorker;
    window.removeEventListener('storymaker-browser-ai-preload', blockPreloadEvent, true);

    if (cleanupTimer !== null) {
      window.clearInterval(cleanupTimer);
      cleanupTimer = null;
    }

    try {
      if (previousPreloadValue === null) {
        originalRemoveItem.call(localStorage, PRELOAD_DISABLED_KEY);
      } else {
        originalSetItem.call(localStorage, PRELOAD_DISABLED_KEY, previousPreloadValue);
      }
    } catch {}

    document.documentElement.removeAttribute('data-sm-mobile-browser-ai-disabled');
  }

  const handleViewport = () => {
    if (MOBILE_QUERY.matches) activate();
    else deactivate();
  };

  MOBILE_QUERY.addEventListener?.('change', handleViewport);
  window.addEventListener('pagehide', deactivate, { once: true });
  handleViewport();
})();
