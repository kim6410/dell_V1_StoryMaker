(() => {
  'use strict';

  const PREFIX = '[V1 manual podcast]';
  const STORAGE_KEY = 'storymaker_v1_current_mobile_job_id';
  const PANEL_ID = 'v1-manual-podcast-panel';
  const nativeFetch = window.fetch.bind(window);
  let currentJobId = '';
  let lastReadyJobId = '';
  let pollTimer = null;
  let busy = false;

  const validJobId = (value) => /^mob-[0-9]{14}-[a-f0-9]{8}$/i.test(String(value || '').trim());

  function publishJobId(value) {
    const jobId = String(value || '').trim();
    if (!validJobId(jobId)) return;
    currentJobId = jobId;
    window.__STORYMAKER_V1_CURRENT_JOB_ID__ = jobId;
    window.__STORYMAKER_CURRENT_JOB_ID__ = jobId;
    window.currentMobileOneShotJobId = jobId;
    window.currentJobId = jobId;
    try {
      sessionStorage.setItem(STORAGE_KEY, jobId);
      sessionStorage.setItem('storymaker_v1_current_mobile_job_id', jobId);
      sessionStorage.setItem('storymaker_v1_current_job_id', jobId);
      localStorage.setItem('storymaker_v1_current_job_id', jobId);
    } catch (_) {}
  }

  function resolveJobId() {
    const candidates = [
      currentJobId,
      window.__STORYMAKER_V1_CURRENT_JOB_ID__,
      window.__STORYMAKER_CURRENT_JOB_ID__,
      window.__CURRENT_MOBILE_ONE_SHOT_JOB_ID__,
      window.currentMobileOneShotJobId,
      window.currentJobId,
    ];
    try {
      candidates.push(
        sessionStorage.getItem(STORAGE_KEY),
        sessionStorage.getItem('storymaker_v1_current_mobile_job_id'),
        sessionStorage.getItem('storymaker_v1_current_job_id'),
        localStorage.getItem('storymaker_v1_current_job_id'),
      );
    } catch (_) {}
    const found = candidates.find(validJobId) || '';
    if (found) publishJobId(found);
    return found;
  }

  function pick(obj, keys) {
    for (const key of keys) {
      const value = obj && obj[key];
      if (typeof value === 'string' && value.trim()) return value.trim();
    }
    return '';
  }

  function countFilledSlots(data) {
    const outputs = (data && data.outputs) || {};
    const raw = String((data && data.raw_result) || '');
    const slots = [
      pick(outputs, ['blog_titles', 'BLOG_TITLES']) || (/\[BLOCK:BLOG_TITLES\]/.test(raw) ? '1' : ''),
      pick(outputs, ['blog_post', 'BLOG_POST', 'blog', 'BLOG']) || (/\[BLOCK:BLOG_POST\]/.test(raw) ? '1' : ''),
      pick(outputs, ['blog_hashtags', 'BLOG_HASHTAGS']) || (/\[BLOCK:BLOG_HASHTAGS\]/.test(raw) ? '1' : ''),
      pick(outputs, ['instagram', 'INSTAGRAM_POST']) || (/\[BLOCK:INSTAGRAM_POST\]/.test(raw) ? '1' : ''),
      pick(outputs, ['place', 'NAVER_PLACE_NEWS']) || (/\[BLOCK:NAVER_PLACE_NEWS\]/.test(raw) ? '1' : ''),
      pick(outputs, ['google_business', 'GOOGLE_BUSINESS_POST']) || (/\[BLOCK:GOOGLE_BUSINESS_POST\]/.test(raw) ? '1' : ''),
      pick(outputs, ['carrot', 'CARROT_POST', 'DAANGN_POST']) || (/\[BLOCK:(?:CARROT_POST|DAANGN_POST)\]/.test(raw) ? '1' : ''),
      pick(outputs, ['podcast50', 'podcast80', 'podcast_50', 'podcast_80', 'PODCAST_50', 'PODCAST_80']) || (/\[BLOCK:PODCAST_(?:50|80)\]/.test(raw) ? '1' : ''),
    ];
    return slots.filter(Boolean).length;
  }

  function ensurePanel() {
    let panel = document.getElementById(PANEL_ID);
    if (panel) return panel;

    panel = document.createElement('section');
    panel.id = PANEL_ID;
    panel.setAttribute('aria-live', 'polite');
    panel.innerHTML = `
      <div class="v1-mp-head">
        <strong>팟캐스트 생성</strong>
        <button type="button" class="v1-mp-close" aria-label="닫기">×</button>
      </div>
      <div class="v1-mp-body">
        <div class="v1-mp-ready">8개 슬롯 확인 중...</div>
        <div class="v1-mp-job"></div>
        <button type="button" class="v1-mp-start" disabled>팟캐스트 생성</button>
        <div class="v1-mp-status">결과 슬롯이 모두 채워지면 버튼이 활성화됩니다.</div>
      </div>`;

    const style = document.createElement('style');
    style.textContent = `
      #${PANEL_ID}{position:fixed;right:22px;bottom:22px;width:min(360px,calc(100vw - 28px));z-index:2147483000;background:#fff;border:1px solid #d8dee9;border-radius:16px;box-shadow:0 18px 50px rgba(15,23,42,.24);font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#eafcff;display:block;overflow:hidden;background:#071126;border-color:#174b63}
      #${PANEL_ID}.open{display:block}
      #${PANEL_ID} .v1-mp-head{display:flex;align-items:center;justify-content:space-between;padding:15px 17px;background:#f3f6fb;border-bottom:1px solid #e4e9f1;font-size:16px}
      #${PANEL_ID} .v1-mp-close{border:0;background:transparent;font-size:25px;line-height:1;cursor:pointer;color:#64748b}
      #${PANEL_ID} .v1-mp-body{padding:17px}
      #${PANEL_ID} .v1-mp-ready{font-weight:700;margin-bottom:7px}
      #${PANEL_ID} .v1-mp-job{font-size:11px;color:#64748b;word-break:break-all;margin-bottom:14px}
      #${PANEL_ID} .v1-mp-start{width:100%;border:0;border-radius:11px;padding:13px 16px;font-size:15px;font-weight:800;cursor:pointer;background:#2563eb;color:#fff}
      #${PANEL_ID} .v1-mp-start:disabled{cursor:not-allowed;background:#a8b4c6}
      #${PANEL_ID} .v1-mp-status{margin-top:11px;font-size:13px;line-height:1.45;color:#475569;white-space:pre-wrap}
      #${PANEL_ID}.success .v1-mp-start{background:#15803d}
      @media(max-width:600px){#${PANEL_ID}{right:14px;bottom:14px}}
    `;
    document.head.appendChild(style);
    document.body.appendChild(panel);

    panel.querySelector('.v1-mp-close').addEventListener('click', () => panel.classList.remove('open'));
    panel.querySelector('.v1-mp-start').addEventListener('click', startPodcast);
    return panel;
  }

  function setPanelState({ slotCount, jobId, status, ready, completed }) {
    const panel = ensurePanel();
    panel.querySelector('.v1-mp-ready').textContent = completed
      ? '팟캐스트 생성 완료'
      : `${slotCount}/8 슬롯 준비`;
    panel.querySelector('.v1-mp-job').textContent = jobId ? `작업 ID: ${jobId}` : '작업 ID 확인 중';
    panel.querySelector('.v1-mp-status').textContent = status || '';
    const button = panel.querySelector('.v1-mp-start');
    button.disabled = !ready || busy || completed;
    button.textContent = completed ? '생성 완료' : (busy ? '생성 요청 중...' : '팟캐스트 생성');
    panel.classList.toggle('success', Boolean(completed));
    if (ready || completed) panel.classList.add('open');
  }

  async function fetchJob(jobId) {
    const response = await nativeFetch(`/api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}`, {
      credentials: 'include',
      cache: 'no-store',
    });
    if (!response.ok) throw new Error(`작업 조회 실패 (${response.status})`);
    const payload = await response.json();
    return payload && payload.data ? payload.data : payload;
  }

  async function inspectCurrentJob() {
    const jobId = resolveJobId();
    if (!jobId) return;
    try {
      const data = await fetchJob(jobId);
      const slotCount = countFilledSlots(data);
      const media = (data && data.media) || {};
      const completed = Boolean(media.mp3_url || media.mp3_path || String(media.podcast_status || '').toLowerCase() === 'completed');
      const ready = Boolean(jobId) && !completed;
      const status = completed
        ? 'MP3/SRT가 작업에 연결됐습니다.'
        : ready
          ? '8개 슬롯이 모두 준비됐습니다. 아래 버튼을 눌러 Dell V1 서버에서 팟캐스트를 생성하세요.'
          : `결과 슬롯 ${slotCount}개 확인됨. 8개가 채워질 때까지 기다립니다.`;
      setPanelState({ slotCount, jobId, status, ready, completed });
      if (ready && lastReadyJobId !== jobId) {
        lastReadyJobId = jobId;
        ensurePanel().classList.add('open');
      }
    } catch (error) {
      console.debug(PREFIX, error);
    }
  }

  async function startPodcast() {
    const jobId = resolveJobId();
    if (!jobId || busy) return;

    const candidates = Array.from(document.querySelectorAll('button'))
      .filter((button) => !button.closest(`#${PANEL_ID}`))
      .filter((button) => {
        const text = String(button.textContent || '').replace(/\s+/g, ' ').trim();
        return text === '팟캐스트 생성' || text.includes('저장/팟캐스트 생성');
      });
    const target = candidates.find((button) => button.offsetParent !== null && !button.disabled)
      || candidates.find((button) => !button.disabled);

    if (!target) {
      setPanelState({
        slotCount: 8,
        jobId,
        status: '화면의 실제 팟캐스트 생성 버튼을 찾지 못했습니다. 제작 화면을 다시 열어주세요.',
        ready: true,
        completed: false,
      });
      return;
    }

    busy = true;
    setPanelState({
      slotCount: 8,
      jobId,
      status: '브라우저 Worker 팟캐스트 생성을 시작합니다...',
      ready: true,
      completed: false,
    });

    try {
      target.click();
      window.dispatchEvent(new CustomEvent('storymaker:v1-podcast-manual-start', {
        detail: { jobId, mode: 'browser-worker', buttonText: String(target.textContent || '').trim() },
      }));
    } catch (error) {
      setPanelState({
        slotCount: 8,
        jobId,
        status: `오류: ${error.message || error}`,
        ready: true,
        completed: false,
      });
    } finally {
      busy = false;
      setTimeout(inspectCurrentJob, 1500);
    }
  }

  window.addEventListener('storymaker:v1-current-job', (event) => {
    publishJobId(event && event.detail && event.detail.jobId);
    setTimeout(inspectCurrentJob, 100);
  });

  window.fetch = async function v1ManualPodcastFetch(input, init) {
    const response = await nativeFetch(input, init);
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    if (method === 'POST' && response.ok && (/\/api\/test\/result-package/.test(url) || /\/api\/mobile\/one-shot\/jobs(?:\?|$)/.test(url))) {
      response.clone().json().then((payload) => {
        const data = payload && payload.data ? payload.data : payload;
        publishJobId(
          (data && (data.archive_job_id || data.job_id || data.jobId)) ||
          (payload && (payload.archive_job_id || payload.job_id || payload.jobId))
        );
        setTimeout(inspectCurrentJob, 250);
      }).catch(() => {});
    }
    return response;
  };

  function boot() {
    ensurePanel();
    resolveJobId();
    inspectCurrentJob();
    pollTimer = window.setInterval(inspectCurrentJob, 2500);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
