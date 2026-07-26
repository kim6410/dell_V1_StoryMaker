(() => {
  'use strict';

  const GLOBAL_KEY = '__STORYMAKER_V1_BROWSER_MP4_SAVE_BRIDGE__';
  if (window[GLOBAL_KEY]?.started) return;

  const PREFIX = '[StoryMaker V1] browser MP4 save bridge';
  const pageParams = new URLSearchParams(window.location.search);
  const isExperienceLab = pageParams.get('page') === 'experienceLab'
    || pageParams.get('webgpu_tts_test') === '1'
    || pageParams.get('inline_lab_frame') === '1';

  if (isExperienceLab) {
    window[GLOBAL_KEY] = {
      started: true,
      disabled: true,
      reason: 'experience-lab-local-only',
      version: '20260727-experience-lab-guard-1'
    };
    console.info(PREFIX, 'disabled for browser-only experience lab');
    return;
  }

  const JOB_RE = /(?:storymaker_main_\d{14}|mob-\d{14}-[a-f0-9]{8})/ig;
  const processed = new Map();
  const objectUrlBlobs = new Map();
  const nativeCreateObjectURL = URL.createObjectURL.bind(URL);
  const nativeRevokeObjectURL = URL.revokeObjectURL.bind(URL);
  let timer = null;

  // 브라우저 렌더러가 만든 MP4 Blob을 생성 순간에 보관한다.
  // Blob URL이 곧바로 해제되더라도 서버 업로드는 원본 Blob으로 계속할 수 있다.
  URL.createObjectURL = function storymakerV1CreateObjectURL(blob) {
    const objectUrl = nativeCreateObjectURL(blob);
    if (blob instanceof Blob && blob.size > 0) {
      objectUrlBlobs.set(objectUrl, blob);

      // 최종 MP4 생성 함수가 넘긴 원본 Blob을 DOM 재검색 없이 즉시 업로드합니다.
      if (String(blob.type || '').toLowerCase().includes('video/mp4')) {
        window.setTimeout(() => uploadGeneratedMp4Blob(blob, objectUrl), 0);
      }

      window.setTimeout(schedule, 0);
    }
    return objectUrl;
  };

  URL.revokeObjectURL = function storymakerV1RevokeObjectURL(objectUrl) {
    nativeRevokeObjectURL(objectUrl);
    // 업로드 재시도를 위해 Blob 참조는 잠시 유지한다.
    window.setTimeout(() => objectUrlBlobs.delete(String(objectUrl || '')), 120000);
  };

  function authHeaders() {
    const token = String(
      localStorage.getItem('storymaker_token')
      || sessionStorage.getItem('storymaker_token')
      || localStorage.getItem('access_token')
      || sessionStorage.getItem('access_token')
      || ''
    ).trim();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  function extractJobIds(value) {
    const matches = String(value || '').match(JOB_RE) || [];
    return [...new Set(matches.map((item) => item.toLowerCase()))];
  }

  // V1 안에 남아 있는 구형 MP4 저장 호출을 안전하게 교정합니다.
  // /api/mobile/... 또는 오래된 storymaker_main_* 요청이 들어오면
  // 현재 source 작업 ID와 /v1-api 전용 경로로 바꿔 서버에 전달합니다.
  const previousFetch = window.fetch.bind(window);
  window.fetch = async function storymakerV1Mp4FetchGuard(input, init = {}) {
    const rawUrl = typeof input === 'string' ? input : String(input?.url || '');
    const method = String(init?.method || (typeof input !== 'string' && input?.method) || 'GET').toUpperCase();

    if (method === 'POST' && /\/api\/mobile\/one-shot\/jobs\/[^/]+\/browser-shortform(?:$|\?)/.test(rawUrl)) {
      const currentId = currentMobileJobId() || currentSourceJobId();
      if (currentId) {
        const correctedUrl = `/v1-api/mobile/one-shot/jobs/${encodeURIComponent(currentId)}/browser-shortform`;
        console.warn(PREFIX, 'legacy MP4 upload request corrected', { rawUrl, correctedUrl, currentId });
        return previousFetch(correctedUrl, init);
      }
    }

    return previousFetch(input, init);
  };

  function newestJobId(values) {
    const ids = values.flatMap(extractJobIds);
    if (!ids.length) return '';
    // mob-YYYYMMDDHHMMSS-xxxxxxxx 형식이므로 문자열 내림차순이 최신 순서와 같습니다.
    return [...new Set(ids)].sort().reverse()[0] || '';
  }

  function elementJobId(element) {
    if (!element) return '';
    const values = [];
    let node = element;

    for (let depth = 0; node && depth < 12; depth += 1, node = node.parentElement) {
      values.push(
        node.getAttribute?.('data-v1-job-id') || '',
        node.getAttribute?.('data-job-id') || '',
        node.getAttribute?.('data-job') || '',
        node.getAttribute?.('data-mobile-job-id') || '',
        node.id || ''
      );
    }

    return newestJobId(values);
  }

  function visibleElementJobId() {
    const selectors = [
      '[data-v1-job-id]',
      '[data-mobile-job-id]',
      '[data-job-id]',
      '[data-job]'
    ];
    const values = [];

    document.querySelectorAll(selectors.join(',')).forEach((element) => {
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      const visible = style.display !== 'none'
        && style.visibility !== 'hidden'
        && rect.width > 0
        && rect.height > 0;
      if (!visible) return;

      values.push(
        element.getAttribute('data-v1-job-id') || '',
        element.getAttribute('data-mobile-job-id') || '',
        element.getAttribute('data-job-id') || '',
        element.getAttribute('data-job') || ''
      );
    });

    return newestJobId(values);
  }

  function recentNetworkJobId() {
    try {
      const entries = performance.getEntriesByType('resource') || [];
      const values = entries
        .slice(-300)
        .reverse()
        .map((entry) => entry?.name || '');
      return newestJobId(values);
    } catch (_) {
      return '';
    }
  }

  function globalJobId() {
    return newestJobId([
      window.__STORYMAKER_V1_CURRENT_JOB_ID__,
      window.__STORYMAKER_CURRENT_JOB_ID__,
      window.__CURRENT_MOBILE_ONE_SHOT_JOB_ID__,
      window.currentMobileOneShotJobId,
      window.currentJobId,
      location.href
    ]);
  }

  function storageJobId() {
    const values = [];
    const allowedKey = /(current|active|latest).*(job|mobile|one.?shot)|(job|mobile|one.?shot).*(current|active|latest)/i;

    for (const storage of [window.sessionStorage, window.localStorage]) {
      try {
        for (let index = 0; index < storage.length; index += 1) {
          const key = storage.key(index) || '';
          if (!allowedKey.test(key)) continue;
          values.push(key, storage.getItem(key) || '');
        }
      } catch (_) {
        // Storage 접근 제한은 무시합니다.
      }
    }

    return newestJobId(values);
  }

  function sourceStorymakerJobId(value) {
    const ids = extractJobIds(value).filter((id) => id.startsWith('storymaker_main_'));
    return ids.sort().reverse()[0] || '';
  }

  function mobileJobId(value) {
    const ids = extractJobIds(value).filter((id) => id.startsWith('mob-'));
    return ids.sort().reverse()[0] || '';
  }

  function currentMobileJobId() {
    const handoffValues = [];
    for (const storage of [window.sessionStorage, window.localStorage]) {
      try {
        handoffValues.push(storage.getItem('storymaker_latest_podcast_for_slideshow') || '');
      } catch (_) {}
    }
    const handoffId = mobileJobId(handoffValues.join(' '));
    if (handoffId) return handoffId;

    const networkId = mobileJobId(recentNetworkJobId());
    if (networkId) return networkId;

    const visibleId = mobileJobId([
      visibleElementJobId(),
      elementJobId(document.querySelector('video')),
      location.href
    ].join(' '));
    if (visibleId) return visibleId;

    return mobileJobId([
      window.__STORYMAKER_V1_CURRENT_JOB_ID__,
      window.__STORYMAKER_CURRENT_JOB_ID__,
      window.__CURRENT_MOBILE_ONE_SHOT_JOB_ID__,
      window.currentMobileOneShotJobId,
      window.currentJobId,
      storageJobId()
    ].join(' '));
  }

  function currentSourceJobId() {
    const networkId = recentNetworkJobId();
    if (networkId && networkId.startsWith('storymaker_main_')) return networkId;

    const explicitId = sourceStorymakerJobId([
      window.__STORYMAKER_V1_CURRENT_JOB_ID__,
      window.__STORYMAKER_CURRENT_JOB_ID__,
      location.href
    ].join(' '));
    if (explicitId) return explicitId;

    return sourceStorymakerJobId([
      visibleElementJobId(),
      elementJobId(document.querySelector('video')),
      storageJobId()
    ].join(' '));
  }

  function findJobId(video) {
    // 딸깍 제작 MP4는 현재 mob-* 작업에 저장해야 MP3·MP4·보관함이 한 작업으로 연결됩니다.
    // mob-*를 찾지 못한 오래된 화면에서만 source storymaker_main_*를 최후 대안으로 사용합니다.
    return currentMobileJobId()
      || mobileJobId(elementJobId(video))
      || currentSourceJobId()
      || sourceStorymakerJobId(elementJobId(video));
  }

  function statusElement(video) {
    const parent = video.parentElement || document.body;
    let status = parent.querySelector('[data-v1-mp4-save-status]');
    if (!status) {
      status = document.createElement('div');
      status.dataset.v1Mp4SaveStatus = '1';
      status.style.cssText = 'margin-top:8px;font-size:13px;line-height:1.5;color:#475569;';
      video.insertAdjacentElement('afterend', status);
    }
    return status;
  }

  function setStatus(video, text, state) {
    const status = statusElement(video);
    status.textContent = text;
    status.dataset.state = state;
  }

  function replaceDownloadLinks(sourceUrl, serverUrl, jobId) {
    document.querySelectorAll('a[href]').forEach((anchor) => {
      const href = anchor.getAttribute('href') || '';
      if (href === sourceUrl || anchor.href === sourceUrl) {
        anchor.href = serverUrl;
        anchor.download = `${jobId}_shortform.mp4`;
      }
    });
  }

  function isUploadableSource(src) {
    if (!src) return false;
    if (src.startsWith('blob:')) return true;

    try {
      const url = new URL(src, location.href);
      const localRenderer = ['127.0.0.1', 'localhost'].includes(url.hostname)
        && /\/outputs\/mp4\//i.test(url.pathname);
      return localRenderer || /\.mp4(?:$|\?)/i.test(url.pathname);
    } catch (_) {
      return false;
    }
  }

  async function uploadGeneratedMp4Blob(blob, sourceUrl, attempt = 0) {
    if (!(blob instanceof Blob) || blob.size <= 0) return;

    const videos = Array.from(document.querySelectorAll('video'));
    const matchedVideo = videos.find((video) => {
      const current = video.currentSrc || video.src || video.querySelector('source')?.src || '';
      return current === sourceUrl;
    }) || videos[0] || null;

    const jobId = findJobId(matchedVideo);
    if (!jobId) {
      if (attempt < 30) {
        window.setTimeout(() => uploadGeneratedMp4Blob(blob, sourceUrl, attempt + 1), 500);
      } else {
        console.error(PREFIX, 'direct upload stopped: current job ID not found', { sourceUrl, size: blob.size });
      }
      return;
    }

    const key = `${jobId}|direct-mp4|${sourceUrl}|${blob.size}`;
    if (['uploading', 'saved'].includes(processed.get(key))) return;
    processed.set(key, 'uploading');

    try {
      const mp4 = blob.type === 'video/mp4'
        ? blob
        : blob.slice(0, blob.size, 'video/mp4');

      const form = new FormData();
      form.append('mp4', mp4, 'shortform.mp4');
      form.append('provider', 'browser-webcodecs-direct-blob');
      form.append('duration_seconds', matchedVideo && Number.isFinite(matchedVideo.duration)
        ? String(matchedVideo.duration)
        : '0');

      const endpoint = `/v1-api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/browser-shortform`;
      const response = await fetch(endpoint, {
        method: 'POST',
        body: form,
        credentials: 'include',
        headers: authHeaders()
      });
      const payload = await response.json().catch(() => ({}));

      if (!response.ok || !payload.ok || !payload.video_url) {
        throw new Error(payload.detail || payload.message || `서버 저장 HTTP ${response.status}`);
      }

      processed.set(key, 'saved');
      replaceDownloadLinks(sourceUrl, payload.video_url, jobId);

      videos.forEach((video) => {
        const current = video.currentSrc || video.src || video.querySelector('source')?.src || '';
        if (current !== sourceUrl) return;

        const currentTime = Number.isFinite(video.currentTime) ? video.currentTime : 0;
        const shouldResume = !video.paused;
        video.src = payload.video_url;
        video.dataset.v1ServerSaved = 'true';
        video.dataset.v1JobId = jobId;
        video.load();
        video.addEventListener('loadedmetadata', () => {
          if (currentTime > 0 && currentTime < video.duration) video.currentTime = currentTime;
          if (shouldResume) video.play().catch(() => {});
        }, { once: true });
        setStatus(video, `영상 서버 저장 완료 · ${jobId}`, 'saved');
      });

      window.dispatchEvent(new CustomEvent('storymaker:v1-browser-mp4-saved', {
        detail: { ...payload, job_id: jobId, direct_blob: true }
      }));
      console.log(PREFIX, 'direct original Blob saved', { jobId, endpoint, size: blob.size, payload });
    } catch (error) {
      processed.set(key, 'failed');
      console.error(PREFIX, 'direct original Blob save failed', { jobId, sourceUrl, size: blob.size, error });

      if (attempt < 3) {
        window.setTimeout(() => {
          processed.delete(key);
          uploadGeneratedMp4Blob(blob, sourceUrl, attempt + 1);
        }, 1500);
      }
    }
  }

  async function saveVideo(video, sourceUrl, jobId) {
    const key = `${jobId}|${sourceUrl}`;
    if (['uploading', 'saved'].includes(processed.get(key))) return;

    processed.set(key, 'uploading');
    video.dataset.v1JobId = jobId;
    setStatus(video, `영상 제작 완료 · 서버 저장 중 (${jobId})`, 'uploading');

    try {
      let source = objectUrlBlobs.get(sourceUrl) || null;
      if (!source) {
        const sourceResponse = await fetch(sourceUrl, { cache: 'no-store' });
        if (!sourceResponse.ok) {
          throw new Error(`MP4 읽기 HTTP ${sourceResponse.status}`);
        }
        source = await sourceResponse.blob();
      }

      if (!source?.size) throw new Error('생성된 MP4가 비어 있습니다.');
      const mp4 = source.type === 'video/mp4'
        ? source
        : source.slice(0, source.size, 'video/mp4');

      const form = new FormData();
      form.append('mp4', mp4, 'shortform.mp4');
      form.append('provider', sourceUrl.startsWith('blob:') ? 'browser-webcodecs' : 'local-renderer-18087');
      form.append('duration_seconds', Number.isFinite(video.duration) ? String(video.duration) : '0');

      const endpoint = `/v1-api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/browser-shortform`;
      const response = await fetch(endpoint, {
        method: 'POST',
        body: form,
        credentials: 'include',
        headers: authHeaders()
      });
      const payload = await response.json().catch(() => ({}));

      if (!response.ok || !payload.ok || !payload.video_url) {
        throw new Error(payload.detail || payload.message || `서버 저장 HTTP ${response.status}`);
      }

      const currentTime = Number.isFinite(video.currentTime) ? video.currentTime : 0;
      const shouldResume = !video.paused;
      video.src = payload.video_url;
      video.dataset.v1ServerSaved = 'true';
      video.dataset.v1JobId = jobId;
      video.load();
      video.addEventListener('loadedmetadata', () => {
        if (currentTime > 0 && currentTime < video.duration) video.currentTime = currentTime;
        if (shouldResume) video.play().catch(() => {});
      }, { once: true });

      replaceDownloadLinks(sourceUrl, payload.video_url, jobId);
      processed.set(key, 'saved');
      const sizeMb = Math.max(0.1, Number(payload.size || source.size) / 1024 / 1024).toFixed(1);
      setStatus(video, `영상 서버 저장 완료 · ${sizeMb}MB · ${jobId}`, 'saved');

      window.dispatchEvent(new CustomEvent('storymaker:v1-browser-mp4-saved', {
        detail: { ...payload, job_id: jobId }
      }));
      console.log(PREFIX, 'saved', { jobId, endpoint, payload });
    } catch (error) {
      processed.set(key, 'failed');
      setStatus(video, `영상 제작 완료 · 서버 저장 실패: ${error.message || error}`, 'failed');
      console.error(PREFIX, 'save failed', { jobId, sourceUrl, error });
      window.setTimeout(() => processed.delete(key), 15000);
    }
  }

  function scan() {
    document.querySelectorAll('video').forEach((video) => {
      if (video.dataset.v1ServerSaved === 'true') return;

      const source = video.currentSrc
        || video.src
        || video.querySelector('source')?.src
        || '';
      if (!isUploadableSource(source)) return;

      const jobId = findJobId(video);
      if (!jobId) {
        setStatus(video, '영상 제작 완료 · 현재 작업 ID 확인 대기', 'waiting');
        return;
      }

      video.dataset.v1JobId = jobId;
      saveVideo(video, source, jobId);
    });
  }

  function schedule() {
    window.clearTimeout(timer);
    timer = window.setTimeout(scan, 250);
  }

  new MutationObserver(schedule).observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['src', 'data-v1-job-id', 'data-job-id', 'data-job']
  });

  window.addEventListener('load', scan);
  window.addEventListener('storymaker:v1-current-job', (event) => {
    const jobId = newestJobId([event?.detail?.job_id, event?.detail?.jobId]);
    if (jobId) window.__STORYMAKER_V1_CURRENT_JOB_ID__ = jobId;
    schedule();
  });
  window.setInterval(scan, 1500);

  window[GLOBAL_KEY] = {
    started: true,
    scan,
    findJobId,
    version: '20260719-current-job-2'
  };

  scan();
  console.log(PREFIX, 'ready', window[GLOBAL_KEY].version);


  const AUTO_MP4_KEY_PREFIX = 'storymaker_v1_auto_mp4_clicked_';
  function autoMp4ButtonCandidate() {
    return Array.from(document.querySelectorAll('button, [role="button"]')).find((el) => {
      const text=[el.innerText||'',el.textContent||'',el.getAttribute('aria-label')||'',el.getAttribute('title')||''].join(' ').replace(/\s+/g,' ').trim().toLowerCase();
      if (!text || el.disabled || el.getAttribute('aria-disabled') === 'true') return false;
      const rect=el.getBoundingClientRect();
      if (rect.width<=0 || rect.height<=0) return false;
      if (/download|save/.test(text)) return false;
      return /(mp4|shortform)/.test(text) && /(render|start)/.test(text);
    }) || null;
  }
  function autoStartBrowserMp4() {
    try {
      const jobId=findJobId(document.body);
      if (!jobId) return;
      const key=AUTO_MP4_KEY_PREFIX+jobId;
      if (sessionStorage.getItem(key)==='1') return;
      const button=autoMp4ButtonCandidate();
      if (!button) return;
      sessionStorage.setItem(key,'1');
      console.log(PREFIX,'auto MP4 render start',{jobId});
      button.click();
    } catch (error) { console.warn(PREFIX,'auto MP4 render start failed',error); }
  }
  window.setInterval(autoStartBrowserMp4,1500);
  window.setTimeout(autoStartBrowserMp4,1200);
})();
