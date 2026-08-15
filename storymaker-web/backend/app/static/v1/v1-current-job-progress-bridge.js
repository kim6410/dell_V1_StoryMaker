(() => {
  'use strict';

  const PREFIX = '[V1 current-job bridge]';
  const nativeFetch = window.fetch.bind(window);
  let currentJobId = '';

  const normalizeUrl = (input) => {
    if (typeof input === 'string') return input;
    if (input && typeof input.url === 'string') return input.url;
    return '';
  };

  const publishJobId = (jobId) => {
    const value = String(jobId || '').trim();
    if (!/^(?:mob-[A-Za-z0-9_-]+|storymaker_main_[A-Za-z0-9_-]+)$/.test(value)) return;

    currentJobId = value;
    window.__STORYMAKER_V1_CURRENT_JOB_ID__ = value;
    window.__STORYMAKER_CURRENT_JOB_ID__ = value;
    window.__CURRENT_MOBILE_ONE_SHOT_JOB_ID__ = value;
    window.currentMobileOneShotJobId = value;
    window.currentJobId = value;

    try {
      sessionStorage.setItem('storymaker_v1_current_mobile_job_id', value);
    } catch (_) {}

    window.dispatchEvent(new CustomEvent('storymaker:v1-current-job', {
      detail: { jobId: value },
    }));

    console.info(PREFIX, 'current job updated', value);
  };

  try {
    publishJobId(sessionStorage.getItem('storymaker_v1_current_mobile_job_id'));
  } catch (_) {}

  window.fetch = async function v1CurrentJobFetch(input, init) {
    const rawUrl = normalizeUrl(input);
    const method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();

    let nextInput = input;
    const progressMatch = rawUrl.match(/((?:\/v1-api)?\/api\/mobile\/one-shot\/jobs\/)(mob-[^/?]+)(\/progress(?:\?.*)?$)/);

    if (method === 'GET' && progressMatch && currentJobId && progressMatch[2] !== currentJobId) {
      const correctedUrl = rawUrl.replace(progressMatch[0], `${progressMatch[1]}${encodeURIComponent(currentJobId)}${progressMatch[3]}`);
      nextInput = typeof input === 'string' ? correctedUrl : new Request(correctedUrl, input);
      console.warn(PREFIX, 'stale progress request corrected', {
        from: progressMatch[2],
        to: currentJobId,
      });
    }

    const response = await nativeFetch(nextInput, init);

    const isCreateRequest = method === 'POST' && /(?:\/v1-api)?\/api\/mobile\/one-shot\/jobs(?:\?.*)?$/.test(rawUrl);
    if (isCreateRequest && response.ok) {
      response.clone().json().then((payload) => {
        publishJobId(payload && (payload.job_id || payload.jobId));
      }).catch(() => {});
    }

    const isTriggerStatusRequest = method === 'GET' && /(?:\/v1-api)?\/api\/test\/trigger-status(?:\?.*)?$/.test(rawUrl);
    if (isTriggerStatusRequest && response.ok) {
      response.clone().json().then((payload) => {
        const data = payload && payload.data ? payload.data : payload;
        publishJobId(data && (data.archive_job_id || data.mobile_job_id || data.source_job_id || data.job_id || data.jobId));
      }).catch(() => {});
    }

    return response;
  };

  function installManualPodcastButton() {
    if (document.getElementById('v1-inline-manual-podcast-button')) return;

    const button = document.createElement('button');
    button.id = 'v1-inline-manual-podcast-button';
    button.type = 'button';
    button.textContent = '팟캐스트 생성';
    Object.assign(button.style, {
      position: 'fixed',
      right: '28px',
      bottom: '28px',
      zIndex: '2147483647',
      padding: '15px 24px',
      border: '1px solid #36d9ff',
      borderRadius: '12px',
      background: '#0a2440',
      color: '#ffffff',
      fontSize: '16px',
      fontWeight: '800',
      cursor: 'pointer',
      boxShadow: '0 12px 36px rgba(0,0,0,.35)'
    });

    button.addEventListener('click', () => {
      const pageText = String(document.body.innerText || '').replace(/\s+/g, ' ');
      const readyMatch = pageText.match(/(\d+)\s*\/\s*8\s*준비/);
      const readyCount = readyMatch ? Number(readyMatch[1]) : 0;

      if (readyCount < 8) {
        alert(`아직 ${readyCount}/8 슬롯만 준비되었습니다. 8개가 모두 채워진 뒤 다시 눌러주세요.`);
        button.textContent = `${readyCount}/8 준비 대기`;
        return;
      }

      const candidates = Array.from(document.querySelectorAll('button'))
        .filter((el) => el !== button)
        .filter((el) => {
          const text = String(el.textContent || '').replace(/\s+/g, ' ').trim();
          return text.includes('저장/팟캐스트 생성') || text === '팟캐스트 생성';
        });

      const target = candidates.find((el) => el.offsetParent !== null) || candidates[0];
      if (!target) {
        alert('화면의 기존 저장/팟캐스트 생성 버튼을 찾지 못했습니다.');
        return;
      }

      button.textContent = '브라우저 팟캐스트 실행 중...';
      target.click();

      setTimeout(() => {
        button.textContent = '팟캐스트 생성';
      }, 2500);
    });

    document.body.appendChild(button);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', installManualPodcastButton, { once: true });
  } else {
    installManualPodcastButton();
  }
})();

(() => {
  'use strict';

  const PREFIX = '[V1 frontend recovery]';
  const POLL_MS = 3000;
  let reloadRequested = false;
  let progressCheckInFlight = false;

  const getCurrentJobId = () => {
    const candidates = [
      window.__STORYMAKER_V1_CURRENT_JOB_ID__,
      window.__STORYMAKER_CURRENT_JOB_ID__,
      window.__CURRENT_MOBILE_ONE_SHOT_JOB_ID__,
      window.currentMobileOneShotJobId,
      window.currentJobId,
      (() => {
        try {
          return sessionStorage.getItem('storymaker_v1_current_mobile_job_id');
        } catch (_) {
          return '';
        }
      })(),
    ];
    return String(candidates.find(Boolean) || '').trim();
  };

  const pageText = () => String(document.body && document.body.innerText || '').replace(/\s+/g, ' ');

  const isFrontendWaitingForMp3 = () => {
    const text = pageText();
    return /MP3|팟캐스트/.test(text) && /생성 중|제작 중|처리 중|기다려|진행 중/.test(text);
  };

  const isFailureScreen = () => {
    const text = pageText();
    return /제작 실패|생성 실패|작업 실패|오류가 발생|시간 초과|중단되었습니다/.test(text);
  };

  const clickMenuByText = (labels) => {
    const elements = Array.from(document.querySelectorAll('button, a, [role="button"]'));
    const target = elements.find((el) => {
      const text = String(el.textContent || '').replace(/\s+/g, ' ').trim();
      return labels.some((label) => text.includes(label));
    });
    if (target) {
      target.click();
      return true;
    }
    return false;
  };

  const installEscapePanel = () => {
    if (!isFailureScreen()) return;
    if (document.getElementById('v1-failure-escape-panel')) return;

    const panel = document.createElement('div');
    panel.id = 'v1-failure-escape-panel';
    Object.assign(panel.style, {
      position: 'fixed',
      left: '50%',
      bottom: '24px',
      transform: 'translateX(-50%)',
      zIndex: '2147483647',
      display: 'flex',
      gap: '10px',
      flexWrap: 'wrap',
      justifyContent: 'center',
      padding: '12px',
      border: '1px solid rgba(255,255,255,.18)',
      borderRadius: '14px',
      background: 'rgba(8,18,32,.96)',
      boxShadow: '0 14px 40px rgba(0,0,0,.4)',
    });

    const addButton = (label, handler) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = label;
      Object.assign(button.style, {
        border: '1px solid #38bdf8',
        borderRadius: '10px',
        padding: '10px 16px',
        background: '#0b2945',
        color: '#fff',
        fontWeight: '800',
        cursor: 'pointer',
      });
      button.addEventListener('click', handler);
      panel.appendChild(button);
    };

    addButton('결과 다시 확인', () => window.location.reload());
    addButton('내 보관함', () => {
      if (!clickMenuByText(['내 보관함', '보관함'])) window.location.href = '/v1';
    });
    addButton('새 작업', () => {
      if (!clickMenuByText(['딸깍 제작', '새 작업', '콘텐츠 제작'])) window.location.href = '/v1';
    });
    addButton('메인 화면', () => { window.location.href = '/v1'; });

    document.body.appendChild(panel);
    console.warn(PREFIX, 'failure escape panel installed');
  };

  const readProgress = async () => {
    const jobId = getCurrentJobId();
    if (!/^mob-[A-Za-z0-9_-]+$/.test(jobId)) return;

    try {
      const response = await fetch(`/v1-api/api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/progress?_=${Date.now()}`, {
        method: 'GET',
        cache: 'no-store',
        credentials: 'include',
      });
      if (!response.ok) return;

      const payload = await response.json();
      const data = payload && payload.data ? payload.data : payload;
      const media = data && data.media ? data.media : data;
      const status = String((media && (media.status || media.podcast_status)) || (data && data.status) || '').toLowerCase();
      const mp3Url = media && (media.mp3_url || media.mp3Url);
      const completed = status === 'podcast_completed' || status === 'completed' || Boolean(mp3Url);

      if (completed) {
        window.dispatchEvent(new CustomEvent('storymaker:v1-podcast-completed', {
          detail: { jobId, payload: data },
        }));

        if (isFrontendWaitingForMp3() && !reloadRequested) {
          const reloadKey = `storymaker_v1_mp3_recovery_${jobId}`;
          let alreadyReloaded = false;
          try {
            alreadyReloaded = sessionStorage.getItem(reloadKey) === '1';
            if (!alreadyReloaded) sessionStorage.setItem(reloadKey, '1');
          } catch (_) {}

          if (!alreadyReloaded) {
            reloadRequested = true;
            console.warn(PREFIX, 'backend MP3 completed; refreshing stale frontend', jobId);
            window.setTimeout(() => window.location.reload(), 300);
          }
        }
      }
    } catch (error) {
      console.debug(PREFIX, 'progress check skipped', error && error.message);
    }
  };

  const tick = () => {
    installEscapePanel();
    if (progressCheckInFlight) return;

    progressCheckInFlight = true;
    Promise.resolve(readProgress()).finally(() => {
      progressCheckInFlight = false;
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tick, { once: true });
  } else {
    tick();
  }
  window.setInterval(tick, POLL_MS);
})();
