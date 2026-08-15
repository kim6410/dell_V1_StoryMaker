(() => {
  'use strict';

  if (window.__V1_PROGRESS_MP4_BRIDGE__) return;
  window.__V1_PROGRESS_MP4_BRIDGE__ = true;

  const state = {
    actualPercent: 0,
    displayPercent: 0,
    lastActualAt: 0,
    mp4Url: '',
    renderActive: false,
    dotStep: 0,
  };

  const STYLE_ID = 'v1-progress-mp4-bridge-style';
  const MP4_PLAY_ID = 'v1-mp4-play-button';
  const MP4_DOWNLOAD_ID = 'v1-mp4-download-button';

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      @keyframes v1ProgressFlow {
        0% { background-position: 0 0; }
        100% { background-position: 48px 0; }
      }
      [data-v1-progress-flow="1"] {
        position: relative !important;
        overflow: hidden !important;
      }
      [data-v1-progress-flow="1"]::after {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        background-image: linear-gradient(
          135deg,
          rgba(255,255,255,.08) 25%,
          rgba(255,255,255,.28) 25%,
          rgba(255,255,255,.28) 50%,
          rgba(255,255,255,.08) 50%,
          rgba(255,255,255,.08) 75%,
          rgba(255,255,255,.28) 75%
        );
        background-size: 48px 48px;
        animation: v1ProgressFlow 1.1s linear infinite;
      }
      .v1-mp4-bridge-button {
        cursor: pointer;
      }
    `;
    document.head.appendChild(style);
  }

  function walk(value, visitor, depth = 0) {
    if (depth > 8 || value == null) return;
    visitor(value);
    if (Array.isArray(value)) {
      value.forEach((item) => walk(item, visitor, depth + 1));
      return;
    }
    if (typeof value === 'object') {
      Object.values(value).forEach((item) => walk(item, visitor, depth + 1));
    }
  }

  function absorbPayload(payload) {
    let foundPercent = null;
    let foundMp4 = '';
    let completed = false;

    walk(payload, (value) => {
      if (!value || typeof value !== 'object' || Array.isArray(value)) return;

      const media = value.media;
      if (media && typeof media === 'object' && typeof media.mp4_url === 'string' && media.mp4_url) {
        foundMp4 = media.mp4_url;
      }

      if (typeof value.mp4_url === 'string' && value.mp4_url) {
        foundMp4 = value.mp4_url;
      }

      for (const key of ['percent', 'progress', 'progress_percent', 'progressPercent']) {
        const raw = value[key];
        const num = typeof raw === 'number' ? raw : Number(raw);
        if (Number.isFinite(num) && num >= 0 && num <= 100) {
          foundPercent = Math.max(foundPercent ?? 0, num);
        }
      }

      const statusText = [value.status, value.stage, value.worker_status, value.progress_message]
        .filter((item) => typeof item === 'string')
        .join(' ')
        .toLowerCase();
      if (/completed|complete|완료/.test(statusText)) completed = true;
    });

    if (foundMp4) {
      state.mp4Url = foundMp4;
      sessionStorage.setItem('v1:lastMp4Url', foundMp4);
    }

    if (foundPercent != null) {
      state.actualPercent = foundPercent;
      state.lastActualAt = Date.now();
      if (foundPercent >= 90) {
        state.displayPercent = foundPercent;
        state.renderActive = false;
      }
    }

    if (completed) {
      state.actualPercent = 100;
      state.displayPercent = 100;
      state.renderActive = false;
    }
  }

  function hookFetch() {
    if (typeof window.fetch !== 'function' || window.fetch.__v1ProgressMp4Hooked) return;
    const originalFetch = window.fetch.bind(window);
    const wrapped = async (...args) => {
      const response = await originalFetch(...args);
      try {
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
          response.clone().json().then(absorbPayload).catch(() => {});
        }
      } catch (_) {}
      return response;
    };
    wrapped.__v1ProgressMp4Hooked = true;
    window.fetch = wrapped;
  }

  function hookXhr() {
    if (!window.XMLHttpRequest || XMLHttpRequest.prototype.__v1ProgressMp4Hooked) return;
    const originalOpen = XMLHttpRequest.prototype.open;
    const originalSend = XMLHttpRequest.prototype.send;

    XMLHttpRequest.prototype.open = function (...args) {
      this.__v1RequestUrl = String(args[1] || '');
      return originalOpen.apply(this, args);
    };

    XMLHttpRequest.prototype.send = function (...args) {
      this.addEventListener('load', () => {
        try {
          const contentType = this.getResponseHeader('content-type') || '';
          if (contentType.includes('application/json') && typeof this.responseText === 'string') {
            absorbPayload(JSON.parse(this.responseText));
          }
        } catch (_) {}
      });
      return originalSend.apply(this, args);
    };

    XMLHttpRequest.prototype.__v1ProgressMp4Hooked = true;
  }

  function allElements() {
    return Array.from(document.querySelectorAll('body *'));
  }

  function findProgressTextElement() {
    return allElements().find((el) => {
      if (el.children.length > 0) return false;
      return /TOTAL\s*PROGRESS\s*\d{1,3}%/i.test((el.textContent || '').trim());
    });
  }

  function findSlidTextElement() {
    return allElements().find((el) => {
      if (el.children.length > 0) return false;
      return /SLID_Maker\.py\s*실행\s*중/i.test((el.textContent || '').trim());
    });
  }

  function readDomActualPercent(progressTextEl) {
    if (!progressTextEl) return null;
    const match = (progressTextEl.textContent || '').match(/TOTAL\s*PROGRESS\s*(\d{1,3})%/i);
    if (!match) return null;
    const value = Number(match[1]);
    if (!Number.isFinite(value)) return null;

    if (!state.renderActive || value >= 90 || value <= state.actualPercent + 1) {
      return value;
    }
    return null;
  }

  function markProgressBar(progressTextEl) {
    if (!progressTextEl) return;
    const scope = progressTextEl.parentElement?.parentElement || progressTextEl.parentElement || document.body;
    const candidates = Array.from(scope.querySelectorAll('div, span'));
    let best = null;

    for (const el of candidates) {
      const styleWidth = el.style?.width || '';
      const ariaNow = el.getAttribute('aria-valuenow');
      const rect = el.getBoundingClientRect();
      if (rect.width < 30 || rect.height < 3 || rect.height > 40) continue;
      if (/%$/.test(styleWidth) || ariaNow != null) {
        best = el;
        if (/%$/.test(styleWidth)) break;
      }
    }

    if (best) {
      best.dataset.v1ProgressFlow = state.renderActive ? '1' : '0';
      if (state.renderActive && state.displayPercent >= 40 && state.displayPercent <= 88) {
        if (/%$/.test(best.style.width || '')) best.style.width = `${state.displayPercent}%`;
        if (best.hasAttribute('aria-valuenow')) best.setAttribute('aria-valuenow', String(state.displayPercent));
      }
    }
  }

  function targetIncrement(percent) {
    if (percent < 60) return 0.38;
    if (percent < 76) return 0.18;
    return 0.07;
  }

  function updateProgressUi() {
    const progressEl = findProgressTextElement();
    const slidEl = findSlidTextElement();
    const domPercent = readDomActualPercent(progressEl);

    if (domPercent != null) {
      state.actualPercent = domPercent;
      if (domPercent >= 90) {
        state.displayPercent = domPercent;
        state.renderActive = false;
      }
    }

    const slidVisible = Boolean(slidEl);
    if (slidVisible && state.actualPercent >= 40 && state.actualPercent < 90) {
      if (!state.renderActive) {
        state.renderActive = true;
        state.displayPercent = Math.max(40, state.actualPercent);
      }
      state.displayPercent = Math.min(88, state.displayPercent + targetIncrement(state.displayPercent));
    } else if (!slidVisible && state.actualPercent >= 90) {
      state.renderActive = false;
    }

    if (progressEl && state.renderActive) {
      progressEl.textContent = `TOTAL PROGRESS ${Math.floor(state.displayPercent)}%`;
    }

    if (slidEl && state.renderActive) {
      state.dotStep = (state.dotStep % 3) + 1;
      slidEl.textContent = `SLID_Maker.py 실행 중${'.'.repeat(state.dotStep)}`;
    }

    markProgressBar(progressEl);
  }

  function toDownloadUrl(url) {
    if (!url) return '';
    if (/\/view(?:\?|$)/.test(url)) return url.replace('/view', '/download');
    return url.replace(/\/$/, '') + '/download';
  }

  function cloneButton(reference, id, label) {
    const button = document.createElement('button');
    button.type = 'button';
    button.id = id;
    button.textContent = label;
    button.className = `${reference?.className || ''} v1-mp4-bridge-button`.trim();
    if (reference) {
      for (const attr of reference.attributes) {
        if (attr.name.startsWith('data-') && attr.name !== 'data-v1-progress-flow') {
          button.setAttribute(attr.name, attr.value);
        }
      }
    }
    return button;
  }

  function findArchiveButton(labelPattern) {
    return Array.from(document.querySelectorAll('button, a')).find((el) => labelPattern.test((el.textContent || '').trim()));
  }

  function ensureMp4Buttons() {
    const stored = sessionStorage.getItem('v1:lastMp4Url') || '';
    if (!state.mp4Url && stored) state.mp4Url = stored;
    if (!state.mp4Url) return;

    const imageButton = findArchiveButton(/^이미지\s*보기$/);
    const mp3Button = findArchiveButton(/^MP3\s*재생$/i);
    const thumbButton = findArchiveButton(/^썸네일\s*보기$/);
    const reference = thumbButton || mp3Button || imageButton;
    if (!reference || !reference.parentElement) return;

    const container = reference.parentElement;

    let playButton = document.getElementById(MP4_PLAY_ID);
    if (!playButton) {
      playButton = cloneButton(reference, MP4_PLAY_ID, 'MP4 재생');
      playButton.addEventListener('click', () => {
        if (state.mp4Url) window.open(state.mp4Url, '_blank', 'noopener,noreferrer');
      });
      container.appendChild(playButton);
    }

    let downloadButton = document.getElementById(MP4_DOWNLOAD_ID);
    if (!downloadButton) {
      downloadButton = cloneButton(reference, MP4_DOWNLOAD_ID, 'MP4 다운로드');
      downloadButton.addEventListener('click', () => {
        const url = toDownloadUrl(state.mp4Url);
        if (!url) return;
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = '';
        anchor.rel = 'noopener';
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
      });
      container.appendChild(downloadButton);
    }
  }

  function start() {
    injectStyle();
    hookFetch();
    hookXhr();

    const observer = new MutationObserver(() => {
      ensureMp4Buttons();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });

    setInterval(updateProgressUi, 1000);
    setInterval(ensureMp4Buttons, 1200);
  }

  start();
})();
