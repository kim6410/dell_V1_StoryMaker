(() => {
  'use strict';

  const KEY = '__STORYMAKER_V1_PC_JOB_LINK_GUARD__';
  if (window[KEY]?.started) return;

  const nativeFetch = window.fetch.bind(window);
  let currentPcJobId = '';
  const staleMobileJobs = new Set();

  const log = (message, detail) => {
    console.info('[V1 PC JOB GUARD]', message, detail || '');
    window.dispatchEvent(new CustomEvent('storymaker:v1-pc-job-guard', {
      detail: { message, ...(detail || {}) }
    }));
  };

  function clearStoredMobileJob() {
    try {
      const raw = localStorage.getItem('storymaker_mobile_active_job');
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed?.job_id?.startsWith('mob-')) staleMobileJobs.add(parsed.job_id);
      }
      localStorage.removeItem('storymaker_mobile_active_job');
    } catch (_) {
      try { localStorage.removeItem('storymaker_mobile_active_job'); } catch (_) {}
    }
  }

  function setCurrentPcJob(jobId) {
    if (!/^storymaker_main_\d{14}$/i.test(String(jobId || ''))) return;
    currentPcJobId = String(jobId);
    window.__STORYMAKER_V1_CURRENT_JOB_ID__ = currentPcJobId;
    window.__STORYMAKER_CURRENT_JOB_ID__ = currentPcJobId;
    clearStoredMobileJob();
    try {
      sessionStorage.setItem('storymaker_v1_current_pc_job', currentPcJobId);
    } catch (_) {}
    window.dispatchEvent(new CustomEvent('storymaker:v1-current-job', {
      detail: { job_id: currentPcJobId, source: 'pc-main-job' }
    }));
    log('현재 PC 작업 연결', { jobId: currentPcJobId });
  }

  function currentPcJob() {
    if (currentPcJobId) return currentPcJobId;
    try {
      const stored = sessionStorage.getItem('storymaker_v1_current_pc_job') || '';
      if (/^storymaker_main_\d{14}$/i.test(stored)) currentPcJobId = stored;
    } catch (_) {}
    return currentPcJobId;
  }

  function syntheticStoppedProgress(jobId) {
    const body = JSON.stringify({
      ok: true,
      data: {
        job_id: jobId,
        status: 'cancelled',
        percent: 100,
        stage: '과거 모바일 작업 조회 종료',
        message: '현재 PC 딸깍 제작과 관계없는 이전 모바일 작업입니다.'
      }
    });
    return new Response(body, {
      status: 200,
      headers: { 'Content-Type': 'application/json; charset=utf-8' }
    });
  }

  function promoteLatestBackendPodcast(jobId, payload) {
    if (!jobId || !payload || typeof payload !== 'object') return;

    const stack = [payload];
    let media = null;
    while (stack.length) {
      const value = stack.pop();
      if (!value || typeof value !== 'object') continue;
      if (value.media && typeof value.media === 'object') {
        const candidate = value.media;
        const projectKey = String(candidate.project_key || value.source_job_id || value.archive_group_key || '');
        if (projectKey === jobId && candidate.mp3_url) {
          media = candidate;
          break;
        }
      }
      if (Array.isArray(value)) stack.push(...value);
      else stack.push(...Object.values(value));
    }
    if (!media?.mp3_url) return;

    const fresh = {
      source: 'server',
      artifact_id: '',
      project_key: jobId,
      pipeline_id: jobId,
      archive_group_key: jobId,
      mp3_url: `${media.mp3_url}${String(media.mp3_url).includes('?') ? '&' : '?'}v=${Date.now()}`,
      srt_url: media.srt_url
        ? `${media.srt_url}${String(media.srt_url).includes('?') ? '&' : '?'}v=${Date.now()}`
        : '',
      created_at: new Date().toISOString()
    };

    for (const storage of [window.sessionStorage, window.localStorage]) {
      try {
        for (let index = storage.length - 1; index >= 0; index -= 1) {
          const key = storage.key(index);
          if (!key) continue;
          const raw = storage.getItem(key);
          if (!raw || !raw.includes(jobId)) continue;
          try {
            const parsed = JSON.parse(raw);
            if (!parsed || typeof parsed !== 'object') continue;
            const projectKey = String(parsed.project_key || parsed.pipeline_id || parsed.archive_group_key || '');
            if (projectKey !== jobId) continue;
            storage.setItem(key, JSON.stringify({ ...parsed, ...fresh }));
          } catch (_) {}
        }
      } catch (_) {}
    }

    try {
      for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
        const key = sessionStorage.key(index) || '';
        if (key.includes('auto_mp4_clicked_') && key.includes(jobId)) sessionStorage.removeItem(key);
      }
    } catch (_) {}

    window.__STORYMAKER_V1_LATEST_SERVER_PODCAST__ = fresh;
    window.dispatchEvent(new CustomEvent('storymaker:v1-server-podcast-ready', { detail: fresh }));
    log('최신 서버 팟캐스트 우선 연결', { jobId, mp3_url: fresh.mp3_url });
  }

  window.fetch = async function pcJobGuardFetch(input, init = {}) {
    const rawUrl = typeof input === 'string' ? input : String(input?.url || '');
    const method = String(init?.method || (typeof input !== 'string' && input?.method) || 'GET').toUpperCase();

    const imageMatch = rawUrl.match(/\/v1-api\/mobile\/one-shot\/main-jobs\/(storymaker_main_\d{14})\/images(?:$|\?)/i);
    if (method === 'POST' && imageMatch) {
      setCurrentPcJob(imageMatch[1]);
      return nativeFetch(input, init);
    }

    const progressMatch = rawUrl.match(/\/v1-api\/mobile\/one-shot\/jobs\/(mob-\d{14}-[a-f0-9]{8})\/progress(?:$|\?)/i);
    if (method === 'GET' && progressMatch && currentPcJob()) {
      const mobId = progressMatch[1];
      staleMobileJobs.add(mobId);
      log('과거 mob 폴링 차단', { mobId, currentPcJobId: currentPcJob() });
      return syntheticStoppedProgress(mobId);
    }

    const uploadMatch = rawUrl.match(/\/v1-api\/mobile\/one-shot\/jobs\/([^/]+)\/(browser-podcast|browser-shortform)(?:$|\?)/i);
    if (method === 'POST' && uploadMatch && currentPcJob()) {
      const requestedId = decodeURIComponent(uploadMatch[1]);
      const endpointKind = uploadMatch[2];
      if (requestedId !== currentPcJob()) {
        const correctedUrl = `/v1-api/mobile/one-shot/jobs/${encodeURIComponent(currentPcJob())}/${endpointKind}`;
        log('PC 결과 업로드 대상 교정', { requestedId, correctedUrl, endpointKind });
        return nativeFetch(correctedUrl, init);
      }
    }

    const response = await nativeFetch(input, init);
    const activeJobId = currentPcJob();
    if (
      method === 'GET'
      && activeJobId
      && rawUrl.includes('/v1-api/mobile/one-shot/jobs/')
      && response.ok
    ) {
      response.clone().json().then((payload) => {
        promoteLatestBackendPodcast(activeJobId, payload);
      }).catch(() => {});
    }
    return response;
  };

  clearStoredMobileJob();

  window[KEY] = {
    started: true,
    version: '20260722-pc-job-link-guard-1',
    getCurrentPcJob: currentPcJob,
    staleMobileJobs
  };

  log('PC 작업 연결 가드 준비 완료', { version: window[KEY].version });
})();
