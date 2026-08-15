(() => {
  'use strict';

  const isPodcastPage = () => location.pathname === '/v1/podcast' || location.pathname.endsWith('/v1/podcast');
  if (!isPodcastPage()) return;

  const MUSIC_TEXTS = [
    '배경음악 설정 (음악선택 + 믹싱볼륨)',
    '배경음악 사용 여부',
    '음악 볼륨',
    '음악 프리셋',
  ];

  const MUSIC_KEYS = new Set([
    'music_random', 'music_file', 'music_volume', 'music_enabled',
    'bgm_random', 'bgm_file', 'bgm_volume', 'bgm_enabled',
    'background_music', 'background_music_file', 'background_music_volume',
    'use_music', 'use_bgm', 'selected_music', 'selected_bgm',
  ]);

  function isPodcastRequest(url) {
    return /\/(?:v1-api\/)?podcast(?:\/|\?|$)/i.test(String(url || ''));
  }

  function cleanObject(value) {
    if (!value || typeof value !== 'object') return value;
    if (Array.isArray(value)) {
      value.forEach(cleanObject);
      return value;
    }

    for (const key of Object.keys(value)) {
      const lower = key.toLowerCase();
      if (MUSIC_KEYS.has(lower) || lower.includes('background_music') || lower.startsWith('bgm_')) {
        if (lower.includes('volume')) value[key] = 0;
        else if (lower.includes('enabled') || lower.startsWith('use_') || lower.endsWith('_random')) value[key] = false;
        else value[key] = '';
        continue;
      }
      cleanObject(value[key]);
    }
    return value;
  }

  function cleanBody(body) {
    if (!body) return body;

    if (typeof body === 'string') {
      try {
        return JSON.stringify(cleanObject(JSON.parse(body)));
      } catch (_) {
        try {
          const params = new URLSearchParams(body);
          for (const key of Array.from(params.keys())) {
            const lower = key.toLowerCase();
            if (MUSIC_KEYS.has(lower) || lower.includes('background_music') || lower.startsWith('bgm_')) {
              params.set(key, lower.includes('volume') ? '0' : lower.includes('enabled') || lower.startsWith('use_') || lower.endsWith('_random') ? 'false' : '');
            }
          }
          return params.toString();
        } catch (_) {
          return body;
        }
      }
    }

    if (body instanceof FormData) {
      for (const key of Array.from(body.keys())) {
        const lower = key.toLowerCase();
        if (MUSIC_KEYS.has(lower) || lower.includes('background_music') || lower.startsWith('bgm_')) {
          body.set(key, lower.includes('volume') ? '0' : lower.includes('enabled') || lower.startsWith('use_') || lower.endsWith('_random') ? 'false' : '');
        }
      }
      return body;
    }

    if (body instanceof URLSearchParams) {
      for (const key of Array.from(body.keys())) {
        const lower = key.toLowerCase();
        if (MUSIC_KEYS.has(lower) || lower.includes('background_music') || lower.startsWith('bgm_')) {
          body.set(key, lower.includes('volume') ? '0' : lower.includes('enabled') || lower.startsWith('use_') || lower.endsWith('_random') ? 'false' : '');
        }
      }
    }

    return body;
  }

  function hideMusicControls() {
    const nodes = document.querySelectorAll('details, label, button, div, p, span');
    for (const node of nodes) {
      const text = String(node.textContent || '').replace(/\s+/g, ' ').trim();
      if (!text) continue;

      if (text.includes(MUSIC_TEXTS[0])) {
        const target = node.closest('details') || node.closest('section') || node.parentElement;
        if (target) {
          target.style.setProperty('display', 'none', 'important');
          target.dataset.storymakerVoiceOnlyHidden = '1';
        }
        continue;
      }

      if (MUSIC_TEXTS.slice(1).some((label) => text === label || text.startsWith(`${label} `))) {
        const target = node.closest('label') || node.parentElement;
        if (target) {
          target.style.setProperty('display', 'none', 'important');
          target.dataset.storymakerVoiceOnlyHidden = '1';
        }
      }
    }
  }

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : String(input?.url || '');
    const method = String(init.method || (typeof input !== 'string' && input?.method) || 'GET').toUpperCase();

    if (method !== 'GET' && isPodcastRequest(url)) {
      init = { ...init, body: cleanBody(init.body) };
      console.info('[StoryMaker Podcast] BGM fields removed from fetch request:', url);
    }

    return originalFetch(input, init);
  };

  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this.__storymakerPodcastRequest = String(method || 'GET').toUpperCase() !== 'GET' && isPodcastRequest(url);
    this.__storymakerPodcastUrl = String(url || '');
    return originalOpen.call(this, method, url, ...rest);
  };

  XMLHttpRequest.prototype.send = function (body) {
    if (this.__storymakerPodcastRequest) {
      body = cleanBody(body);
      console.info('[StoryMaker Podcast] BGM fields removed from XHR request:', this.__storymakerPodcastUrl);
    }
    return originalSend.call(this, body);
  };

  hideMusicControls();
  const observer = new MutationObserver(hideMusicControls);
  observer.observe(document.documentElement, { childList: true, subtree: true });

  console.info('[StoryMaker Podcast] strict voice-only mode active: all Podcast BGM request fields disabled.');
})();
