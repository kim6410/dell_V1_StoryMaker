(() => {
  'use strict';

  const PREFIX = '[V1 podcast one-open]';
  const nativeFetch = window.fetch.bind(window);
  const openedJobs = new Set();
  const armedPodcastJobs = new Set();
  const browserPodcastJobs = new Set();
  let browserPodcastWorker = null;
  let activeLatestJobId = '';
  const EXPERIENCE_SESSION_KEY = 'storymaker_experience_lab_session_v1';

  function currentPageName() {
    return new URLSearchParams(window.location.search).get('page') || '';
  }

  function isExperienceLabContext() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('page') === 'experienceLab') return true;
    if (params.get('webgpu_tts_test') === '1') return true;
    if (params.get('inline_lab_frame') === '1') return true;
    return Boolean(document.querySelector(
      '#v1-dashboard-inline-lab-host.open iframe[src*="page=experienceLab"],'
      + ' iframe[src*="page=experienceLab"][src*="inline_lab_frame=1"]'
    ));
  }

  function isOneShotAutomationContext() {
    if (isExperienceLabContext()) return false;
    return ['workpanel', 'write', 'podcast', 'shortform'].includes(currentPageName());
  }

  function seedExperienceLabDefaults() {
    if (!isExperienceLabContext()) return;
    try {
      const raw = sessionStorage.getItem(EXPERIENCE_SESSION_KEY);
      const settings = raw ? JSON.parse(raw) : {};
      const savedSpeed = Number(settings.voiceSpeed);
      if (!Number.isFinite(savedSpeed) || savedSpeed === 1.35) {
        settings.voiceSpeed = 1.2;
        sessionStorage.setItem(EXPERIENCE_SESSION_KEY, JSON.stringify(settings));
      }
    } catch (_) {
      try {
        sessionStorage.setItem(EXPERIENCE_SESSION_KEY, JSON.stringify({ voiceSpeed: 1.2 }));
      } catch (_) {}
    }
  }

  seedExperienceLabDefaults();

  function normalizedUrl(input) {
    if (typeof input === 'string') return input;
    return input && typeof input.url === 'string' ? input.url : '';
  }

  function compactText(element) {
    return String((element && element.textContent) || '').replace(/\s+/g, ' ').trim();
  }

  function findPodcastTrigger() {
    const clickable = Array.from(
      document.querySelectorAll('button, [role="button"], summary, [tabindex="0"]')
    );

    const direct = clickable.find((element) => /03\s*팟캐스트/i.test(compactText(element)));
    if (direct) return direct;

    const podcastCards = Array.from(
      document.querySelectorAll('article, section, li, div')
    )
      .filter((element) => /03\s*팟캐스트/i.test(compactText(element)))
      .sort((a, b) => compactText(a).length - compactText(b).length);

    for (const card of podcastCards) {
      const toggle = Array.from(
        card.querySelectorAll('button, [role="button"], summary, [tabindex="0"]')
      ).find((element) => /펼치기|접기/i.test(compactText(element)) || element.hasAttribute('aria-expanded'));
      if (toggle) return toggle;
    }

    return clickable.find((element) => /팟캐스트/i.test(compactText(element))) || null;
  }

  function podcastEditorVisible() {
    return Array.from(document.querySelectorAll('textarea, input')).some((element) => {
      const marker = [
        element.getAttribute('placeholder'),
        element.getAttribute('aria-label'),
        element.getAttribute('name'),
        element.id
      ].filter(Boolean).join(' ');
      if (!/팟캐스트|대본|podcast|script/i.test(marker)) return false;
      const style = window.getComputedStyle(element);
      return style.display !== 'none'
        && style.visibility !== 'hidden'
        && element.getBoundingClientRect().height > 20;
    });
  }

  function looksExpanded(trigger) {
    if (!trigger) return podcastEditorVisible();
    const aria = trigger.getAttribute('aria-expanded');
    if (aria === 'true') return true;
    if (aria === 'false') return false;
    if (/접기/i.test(compactText(trigger))) return true;
    return podcastEditorVisible();
  }

  function openPodcastOnce(jobId) {
    const safeJobId = String(jobId || '').trim();
    if (!/^mob-[A-Za-z0-9_-]+$/.test(safeJobId)) return;
    if (openedJobs.has(safeJobId)) return;

    let attempts = 0;
    let lastClickAt = 0;
    const timer = window.setInterval(() => {
      attempts += 1;
      const trigger = findPodcastTrigger();

      if (looksExpanded(trigger)) {
        window.clearInterval(timer);
        openedJobs.add(safeJobId);
        console.info(PREFIX, 'podcast accordion confirmed open', safeJobId);
        return;
      }

      if (trigger && Date.now() - lastClickAt >= 1000) {
        lastClickAt = Date.now();
        console.info(PREFIX, 'open podcast accordion', safeJobId, attempts);
        trigger.click();
      }

      if (attempts >= 40) {
        window.clearInterval(timer);
        console.warn(PREFIX, 'podcast accordion open not confirmed', safeJobId);
      }
    }, 250);
  }

  function renderCompletedPodcast(jobId, data) {
    const safeJobId = String(jobId || '').trim();
    if (!/^mob-[A-Za-z0-9_-]+$/.test(safeJobId)) return;

    const hasMp3 = Boolean(data && data.has_mp3);
    const status = String((data && data.status) || '').toLowerCase();
    if (!hasMp3 && status !== 'podcast_completed') return;

    const panelId = `v1-podcast-result-${safeJobId}`;
    if (document.getElementById(panelId)) return;

    const trigger = findPodcastTrigger();
    if (!trigger || !trigger.parentElement) return;

    const panel = document.createElement('div');
    panel.id = panelId;
    panel.setAttribute('data-v1-podcast-result', safeJobId);
    panel.style.cssText = [
      'margin:0 16px 16px',
      'padding:14px 16px',
      'border:1px solid rgba(59,130,246,.35)',
      'border-radius:12px',
      'background:rgba(15,23,42,.72)',
      'color:#e5eefc'
    ].join(';');

    const title = document.createElement('div');
    title.textContent = '팟캐스트 생성 완료';
    title.style.cssText = 'font-weight:700;margin-bottom:10px;color:#bfdbfe';

    const audio = document.createElement('audio');
    audio.controls = true;
    audio.preload = 'metadata';
    audio.src = `/v1-api/mobile/one-shot/jobs/${encodeURIComponent(safeJobId)}/files/mp3`;
    audio.style.cssText = 'width:100%;display:block;margin-bottom:10px';

    const links = document.createElement('div');
    links.style.cssText = 'display:flex;gap:12px;flex-wrap:wrap;font-size:14px';

    const mp3Link = document.createElement('a');
    mp3Link.href = audio.src;
    mp3Link.textContent = 'MP3 다운로드';
    mp3Link.download = `${safeJobId}.mp3`;
    mp3Link.style.cssText = 'color:#93c5fd;text-decoration:none';

    const srtLink = document.createElement('a');
    srtLink.href = `/v1-api/mobile/one-shot/jobs/${encodeURIComponent(safeJobId)}/files/srt`;
    srtLink.textContent = 'SRT 다운로드';
    srtLink.download = `${safeJobId}.srt`;
    srtLink.style.cssText = 'color:#93c5fd;text-decoration:none';

    links.append(mp3Link, srtLink);
    panel.append(title, audio, links);
    trigger.insertAdjacentElement('afterend', panel);
    console.info(PREFIX, 'render completed podcast result', safeJobId);
  }

  function firstText(...values) {
    for (const value of values) {
      const text = String(value || '').trim();
      if (text) return text;
    }
    return '';
  }

  function getOneShotPodcastWorker() {
    if (browserPodcastWorker) return browserPodcastWorker;
    browserPodcastWorker = new Worker(
      '/static/v1/assets/browserPodcast.worker-nPEw1MVN.js',
      { type: 'module', name: 'storymaker-v1-oneshot-browser-podcast' }
    );
    browserPodcastWorker.addEventListener('error', (event) => {
      console.warn(PREFIX, 'one-shot browser podcast worker error', event?.message || event);
    });
    return browserPodcastWorker;
  }

  function generateOneShotBrowserPodcast(script) {
    return new Promise((resolve, reject) => {
      const worker = getOneShotPodcastWorker();
      const id = `oneshot-podcast-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const timeout = window.setTimeout(() => {
        worker.removeEventListener('message', onMessage);
        reject(new Error('브라우저 팟캐스트 생성 시간이 초과되었습니다.'));
      }, 180000);

      function finish() {
        window.clearTimeout(timeout);
        worker.removeEventListener('message', onMessage);
      }

      function onMessage(event) {
        const message = event.data || {};
        if (message.id !== id) return;
        if (message.type === 'progress') {
          const progress = message.progress || {};
          console.info(PREFIX, 'one-shot browser podcast progress', progress.stage, progress.percent, progress.detail);
          return;
        }
        finish();
        if (message.type === 'result') {
          resolve(message.result);
          return;
        }
        const error = new Error(message.message || '브라우저 팟캐스트 생성에 실패했습니다.');
        error.name = message.name || 'Error';
        reject(error);
      }

      worker.addEventListener('message', onMessage);
      worker.postMessage({
        id,
        type: 'generate',
        options: {
          script,
          maleVoice: 'M1',
          femaleVoice: 'F1',
          speed: 1.05,
          voiceVolume: 1,
          pauseSeconds: 0.47,
          inferenceSteps: navigator.gpu ? 6 : 8,
          preferredProvider: 'auto'
        }
      });
    });
  }

  async function uploadOneShotBrowserPodcast(jobId, result) {
    const form = new FormData();
    form.append('mp3', result.mp3Blob, 'browser_podcast.mp3');
    form.append('srt', result.srtBlob, 'browser_podcast.srt');
    form.append('provider', result.provider || 'browser');
    form.append('duration_seconds', String(result.durationSeconds || 0));

    const response = await nativeFetch(
      `/v1-api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/browser-podcast`,
      { method: 'POST', credentials: 'include', body: form }
    );
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.detail || payload.message || '브라우저 팟캐스트 저장에 실패했습니다.');
    }
    return payload;
  }

  async function startOneShotBrowserPodcast(jobId, handoff, importKey) {
    const safeJobId = String(jobId || '').trim();
    if (!/^mob-[A-Za-z0-9_-]+$/.test(safeJobId)) return;
    if (browserPodcastJobs.has(safeJobId)) return;

    const script = firstText(
      importKey === 'PODCAST_80' ? handoff?.PODCAST_80 : handoff?.PODCAST_50,
      handoff?.PODCAST_50,
      handoff?.PODCAST_80
    );
    if (!script) return;

    browserPodcastJobs.add(safeJobId);
    console.info(PREFIX, 'one-shot browser podcast start', safeJobId, importKey);
    try {
      const result = await generateOneShotBrowserPodcast(script);
      const payload = await uploadOneShotBrowserPodcast(safeJobId, result);
      console.info(PREFIX, 'one-shot browser podcast saved', safeJobId, result.provider, result.durationSeconds);
      handleProgress(safeJobId, payload);
    } catch (error) {
      browserPodcastJobs.delete(safeJobId);
      armedPodcastJobs.delete(safeJobId);
      if (browserPodcastWorker) {
        try { browserPodcastWorker.terminate(); } catch (_) {}
        browserPodcastWorker = null;
      }
      console.warn(PREFIX, 'one-shot browser podcast failed', safeJobId, error);
    }
  }

  function armAutomaticPodcast(jobId, data) {
    const safeJobId = String(jobId || '').trim();
    if (!/^mob-[A-Za-z0-9_-]+$/.test(safeJobId)) return;

    const media = data && typeof data.media === 'object' ? data.media : {};
    const outputs = data && typeof data.outputs === 'object' ? data.outputs : {};
    const sourceJobId = String(
      data?.source_job_id
      || data?.archive_group_key
      || media.project_key
      || ''
    ).trim();
    const podcast50 = firstText(outputs.podcast50, outputs.PODCAST_50, data?.PODCAST_50, data?.pipeline?.podcast_script);
    const podcast80 = firstText(outputs.podcast80, outputs.PODCAST_80, data?.PODCAST_80);
    const importKey = podcast50 ? 'PODCAST_50' : (podcast80 ? 'PODCAST_80' : '');
    if (!importKey) {
      console.warn(PREFIX, 'podcast script missing; automatic podcast not armed', safeJobId, sourceJobId);
      return;
    }
    if (armedPodcastJobs.has(safeJobId)) return;

    const title = firstText(
      outputs.blog_titles,
      outputs.BLOG_TITLES,
      data?.BLOG_TITLES,
      data?.title,
      data?.memo,
      data?.project_title,
      data?.persona?.company_name,
      data?.persona?.business_name,
      safeJobId
    );
    const pipelineId = firstText(sourceJobId, data?.pipeline?.source_job_id, data?.pipeline?.archive_group_key, safeJobId);
    const archiveGroupKey = firstText(data?.archive_group_key, sourceJobId, safeJobId);
    const handoff = {
      pipeline_id: pipelineId,
      archive_group_key: archiveGroupKey,
      handoff_id: `${safeJobId}:${sourceJobId || 'no-source'}:podcast-handoff`,
      title,
      BLOG_TITLES: firstText(outputs.blog_titles, outputs.BLOG_TITLES, data?.BLOG_TITLES, title),
      PODCAST_50: podcast50,
      PODCAST_80: podcast80
    };

    window.__STORYMAKER_V1_CURRENT_JOB_ID__ = safeJobId;
    window.__STORYMAKER_CURRENT_JOB_ID__ = safeJobId;
    if (sourceJobId) window.__STORYMAKER_V1_CURRENT_SOURCE_JOB_ID__ = sourceJobId;

    armedPodcastJobs.add(safeJobId);

    for (const storage of [window.sessionStorage, window.localStorage]) {
      try {
        storage.setItem('storymaker_podcast_results', JSON.stringify(handoff));
        storage.setItem('storymaker_auto_import_podcast', importKey);
        storage.setItem('storymaker_auto_run_podcast', '1');
        storage.setItem('storymaker_auto_shortform_after_podcast', '1');
        storage.setItem('storymaker_current_job_id', safeJobId);
        storage.setItem('storymaker_v1_current_job_id', safeJobId);
        if (sourceJobId) storage.setItem('storymaker_current_source_job_id', sourceJobId);
      } catch (_) {}
    }

    startOneShotBrowserPodcast(safeJobId, handoff, importKey);
    console.info(PREFIX, 'automatic one-shot browser podcast armed', safeJobId, sourceJobId, importKey, handoff);
  }

  function armAutomaticShortform(jobId, data) {
    const safeJobId = String(jobId || '').trim();
    if (!/^mob-[A-Za-z0-9_-]+$/.test(safeJobId)) return;

    const media = data && typeof data.media === 'object' ? data.media : {};
    const mp3Url = `/v1-api/mobile/one-shot/jobs/${encodeURIComponent(safeJobId)}/files/mp3`;
    const srtUrl = `/v1-api/mobile/one-shot/jobs/${encodeURIComponent(safeJobId)}/files/srt`;
    const handoff = {
      source: 'server',
      artifact_id: String(media.podcast_job_id || data.podcast_job_id || ''),
      project_key: safeJobId,
      title: String(data.memo || data.project_title || data.persona?.business_name || safeJobId),
      pipeline_id: String(data.archive_group_key || data.source_job_id || media.project_key || ''),
      archive_group_key: String(data.archive_group_key || data.source_job_id || media.project_key || safeJobId),
      target_folder_id: '',
      mp3_url: mp3Url,
      srt_url: srtUrl,
      duration_seconds: Number(media.podcast_duration_seconds || data.podcast_duration_seconds || 0),
      provider: String(media.podcast_provider || data.podcast_provider || 'browser'),
      created_at: String(data.updated_at || data.created_at || new Date().toISOString())
    };

    window.__STORYMAKER_V1_CURRENT_JOB_ID__ = safeJobId;
    window.__STORYMAKER_CURRENT_JOB_ID__ = safeJobId;

    for (const storage of [window.sessionStorage, window.localStorage]) {
      try {
        storage.setItem('storymaker_latest_podcast_for_slideshow', JSON.stringify(handoff));
        storage.setItem('storymaker_auto_run_shortform', '1');
        storage.setItem('storymaker_auto_shortform_after_podcast', '1');
      } catch (_) {}
    }

    window.dispatchEvent(new CustomEvent('storymaker:v1-podcast-ready', {
      detail: { job_id: safeJobId, handoff }
    }));
    console.info(PREFIX, 'automatic shortform armed', safeJobId, handoff);
  }

  function handleProgress(jobId, payload) {
    const data = payload && payload.data ? payload.data : payload;
    if (!data || data.ok === false) return;

    const phase = String(data.current_phase || '').toLowerCase();
    const status = String(data.status || '').toLowerCase();
    const hasMp3 = Boolean(data.has_mp3);

    const outputs = data && typeof data.outputs === 'object' ? data.outputs : {};
    const hasScript = Boolean(
      firstText(
        outputs.podcast50,
        outputs.PODCAST_50,
        outputs.podcast80,
        outputs.PODCAST_80,
        data?.PODCAST_50,
        data?.PODCAST_80,
        data?.pipeline?.podcast_script
      )
    );

    const podcastPhase = phase === 'podcast'
      || status === 'podcast_waiting'
      || status === 'podcast_running'
      || status === 'browser_podcast_waiting';

    const podcastSubmitted = status === 'podcast_submitted'
      || status === 'submitted'
      || String(data.podcast_status || data.media?.podcast_status || '').toLowerCase() === 'submitted';

    if (!hasMp3 && (podcastPhase || podcastSubmitted || hasScript)) {
      armAutomaticPodcast(jobId, data);
    }

    if (hasMp3 || status === 'podcast_completed') {
      armAutomaticShortform(jobId, data);
      renderCompletedPodcast(jobId, data);
    }
  }

  const LATEST_JOB_RELOAD_KEY = 'storymaker_v1_latest_job_reload';
  let latestJobWatcherBusy = false;

  async function syncLatestStoredJob() {
    if (!isOneShotAutomationContext()) return;
    if (latestJobWatcherBusy || document.visibilityState === 'hidden') return;
    latestJobWatcherBusy = true;
    try {
      const listResponse = await nativeFetch('/v1-api/v2/content-board?limit=1&offset=0', {
        credentials: 'same-origin',
        cache: 'no-store'
      });
      if (!listResponse.ok) return;
      const listPayload = await listResponse.json();
      const latest = Array.isArray(listPayload?.items) ? listPayload.items[0] : null;
      const latestJobId = String(
        latest?.job_id || latest?.mobile_job_id || latest?.content_id || latest?.id || ''
      ).trim();
      if (!/^mob-[A-Za-z0-9_-]+$/.test(latestJobId)) return;

      const detailResponse = await nativeFetch(`/v1-api/v2/content-board/${encodeURIComponent(latestJobId)}`, {
        credentials: 'same-origin',
        cache: 'no-store'
      });
      if (!detailResponse.ok) return;
      const detailPayload = await detailResponse.json();
      const detail = detailPayload && detailPayload.data ? detailPayload.data : detailPayload;
      const effectiveJobId = String(detail?.job_id || detail?.mobile_job_id || latestJobId).trim();
      if (!/^mob-[A-Za-z0-9_-]+$/.test(effectiveJobId)) return;
      activeLatestJobId = effectiveJobId;

      let currentJobId = '';
      try {
        currentJobId = String(
          sessionStorage.getItem('storymaker_v1_current_job_id')
          || localStorage.getItem('storymaker_v1_current_job_id')
          || sessionStorage.getItem('storymaker_current_job_id')
          || localStorage.getItem('storymaker_current_job_id')
          || ''
        ).trim();
      } catch (_) {}

      handleProgress(effectiveJobId, detailPayload);

      if (currentJobId !== effectiveJobId) {
        for (const storage of [window.sessionStorage, window.localStorage]) {
          try {
            storage.setItem('storymaker_current_job_id', effectiveJobId);
            storage.setItem('storymaker_v1_current_job_id', effectiveJobId);
          } catch (_) {}
        }

        console.info(PREFIX, 'latest DB job adopted without reload', currentJobId, effectiveJobId);
      }
    } catch (error) {
      console.warn(PREFIX, 'latest DB job sync failed', error);
    } finally {
      latestJobWatcherBusy = false;
    }
  }

  function startLatestStoredJobWatcher() {
    window.setTimeout(syncLatestStoredJob, 500);
    window.setInterval(syncLatestStoredJob, 2500);
  }

  window.fetch = async function v1PodcastOneOpenFetch(input, init) {
    const originalUrl = normalizedUrl(input);
    const progressMatch = originalUrl.match(/\/v1-api\/mobile\/one-shot\/jobs\/(mob-[^/?]+)\/progress/);
    const shouldAdoptLatest = Boolean(
      isOneShotAutomationContext()
      && progressMatch
      && /^mob-[A-Za-z0-9_-]+$/.test(activeLatestJobId)
      && progressMatch[1] !== activeLatestJobId
    );
    const correctedUrl = shouldAdoptLatest
      ? originalUrl.replace(progressMatch[1], activeLatestJobId)
      : originalUrl;
    let requestInput = input;
    if (correctedUrl !== originalUrl) {
      requestInput = typeof input === 'string' ? correctedUrl : new Request(correctedUrl, input);
      console.info(PREFIX, 'progress job adopted from DB', progressMatch[1], activeLatestJobId);
    }
    const response = await nativeFetch(requestInput, init);

    const podcastUploadMatch = originalUrl.match(/\/v1-api\/mobile\/one-shot\/jobs\/(mob-[^/?]+)\/browser-podcast(?:$|\?)/);
    const contentBoardMatch = originalUrl.match(/\/v1-api\/v2\/content-board\/(mob-[^/?]+)(?:$|\?)/);
    const requestedJobId = progressMatch?.[1] || podcastUploadMatch?.[1] || contentBoardMatch?.[1] || '';

    if (response.ok && requestedJobId && isOneShotAutomationContext()) {
      try {
        const payload = await response.clone().json();
        const data = payload && payload.data ? payload.data : payload;
        const effectiveJobId = String(data?.job_id || data?.mobile_job_id || requestedJobId || '').trim();
        if (/^mob-[A-Za-z0-9_-]+$/.test(effectiveJobId)) {
          handleProgress(effectiveJobId, payload);
        }
      } catch (_) {}
    }

    return response;
  };

  startLatestStoredJobWatcher();
})();
