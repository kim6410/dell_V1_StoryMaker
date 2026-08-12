(() => {
  'use strict';

  const gate = document.getElementById('voicebox-auth-gate');
  const gateMessage = document.getElementById('voicebox-auth-message');
  const app = document.getElementById('voicebox-app');
  const scriptInput = document.getElementById('full-script');
  const scriptCounter = document.getElementById('script-counter');
  const chunkSummary = document.getElementById('chunk-summary');
  const chunkList = document.getElementById('chunk-list');
  const emptyState = document.getElementById('empty-state');
  const targetSeconds = document.getElementById('chunk-seconds');
  const voiceProfile = document.getElementById('voice-profile');
  const voiceEngine = document.getElementById('voice-engine');
  const voiceModelSize = document.getElementById('voice-model-size');
  const engineStatus = document.getElementById('engine-status');
  const statusDot = document.querySelector('.status-dot');
  const exportAll = document.getElementById('export-all');
  const playAll = document.getElementById('play-all');

  let chunks = [];
  let engineOnline = false;

  // Studio 껍데기는 인증 응답과 무관하게 즉시 표시한다.
  // 실제 생성/저장 API는 서버의 관리자 권한 검사에서 다시 보호한다.
  if (gate) {
    gate.hidden = true;
    gate.style.display = 'none';
  }
  if (app) app.hidden = false;

  function normalize(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function isAdminUser(user) {
    if (!user || typeof user !== 'object') return false;
    const role = normalize(user.role || user.user_role || user.type).toLowerCase();
    return user.is_admin === true
      || user.is_admin === 1
      || user.admin === true
      || user.admin === 1
      || role === 'admin'
      || role === 'administrator';
  }

  function getAuthHeaders() {
    const headers = { Accept: 'application/json' };
    try {
      const token = String(
        window.localStorage.getItem('storymaker_token')
        || window.sessionStorage.getItem('storymaker_token')
        || window.localStorage.getItem('access_token')
        || window.sessionStorage.getItem('access_token')
        || ''
      ).trim();
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch (_) {}
    return headers;
  }

  function hasRecentAdminEntryGrant() {
    try {
      const raw = Number(window.sessionStorage.getItem('storymaker_voicebox_admin_entry') || 0);
      return raw > 0 && (Date.now() - raw) < 10 * 60 * 1000;
    } catch (_) {
      return false;
    }
  }

  function revealStudio(message = '') {
    gate.hidden = true;
    app.hidden = false;
    if (message && engineStatus) engineStatus.textContent = message;
  }

  async function requireAdmin() {
    const fromAdminButton = hasRecentAdminEntryGrant()
      || new URLSearchParams(window.location.search).get('from') === 'v1-admin';

    if (fromAdminButton) {
      revealStudio('관리자 인증 확인 중 · Studio 사용 가능');
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 3500);
    try {
      const response = await fetch('/v1-api/auth/me', {
        credentials: 'include',
        cache: 'no-store',
        headers: getAuthHeaders(),
        signal: controller.signal,
      });
      window.clearTimeout(timer);
      const payload = response.ok ? await response.json().catch(() => ({})) : {};
      const user = payload?.data?.user || payload?.user || payload?.data || null;
      if (!response.ok || !isAdminUser(user)) {
        revealStudio('관리자 인증 확인 필요 · Studio UI 미리보기');
        return false;
      }
      try {
        window.sessionStorage.setItem('storymaker_voicebox_admin_entry', String(Date.now()));
      } catch (_) {}
      revealStudio();
      return true;
    } catch (_) {
      window.clearTimeout(timer);
      if (fromAdminButton) {
        revealStudio('관리자 세션 확인 지연 · 기능 연결 전 UI 사용 가능');
        return true;
      }
      revealStudio('관리자 인증 응답 지연 · Studio UI 사용 가능');
      return false;
    }
  }

  async function loadVoiceProfiles() {
    voiceProfile.innerHTML = '<option value="">Voice 프로필 불러오는 중...</option>';
    try {
      const response = await fetch('/v1-api/voicebox/profiles', {
        credentials: 'include',
        cache: 'no-store',
        headers: getAuthHeaders(),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || 'Voice 프로필을 불러오지 못했습니다.');
      const profiles = Array.isArray(payload.profiles) ? payload.profiles : [];
      if (!profiles.length) {
        voiceProfile.innerHTML = '<option value="">등록된 Voice 프로필 없음</option>';
        return;
      }
      voiceProfile.innerHTML = profiles.map((profile, index) => {
        const id = escapeHtml(profile.id || '');
        const name = escapeHtml(profile.name || `Voice ${index + 1}`);
        return `<option value="${id}">${name}</option>`;
      }).join('');
    } catch (_) {
      voiceProfile.innerHTML = '<option value="">엔진 연결 후 프로필 선택</option>';
    }
  }

  async function checkEngine() {
    try {
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), 2200);
      const response = await fetch('/v1-api/voicebox/health', {
        credentials: 'include',
        cache: 'no-store',
        headers: getAuthHeaders(),
        signal: controller.signal,
      });
      window.clearTimeout(timer);
      const payload = response.ok ? await response.json().catch(() => ({})) : {};
      engineOnline = response.ok && payload.online === true;
    } catch (_) {
      engineOnline = false;
    }
    engineStatus.textContent = engineOnline ? 'Voicebox 엔진 온라인 · 청크 생성 가능' : 'Voicebox 엔진 연결 대기 · UI 편집 가능';
    statusDot.classList.toggle('online', engineOnline);
    statusDot.classList.toggle('waiting', !engineOnline);
    if (engineOnline) await loadVoiceProfiles();
    renderChunks();
  }

  function estimateSeconds(text) {
    const compact = normalize(text);
    if (!compact) return 0;
    const charsPerSecond = 4.4;
    return Math.max(1, Math.round(compact.length / charsPerSecond));
  }

  function splitSentences(text) {
    const cleaned = String(text || '').replace(/\r\n/g, '\n').trim();
    if (!cleaned) return [];
    const parts = cleaned
      .split(/(?<=[.!?。！？])\s+|\n{2,}|\n(?=\S)/g)
      .map(normalize)
      .filter(Boolean);
    return parts.length ? parts : [normalize(cleaned)];
  }

  function smartChunk(text, seconds) {
    const sentences = splitSentences(text);
    const targetChars = Math.max(70, Math.round(Number(seconds || 30) * 4.4));
    const minChars = Math.round(targetChars * 0.58);
    const maxChars = Math.round(targetChars * 1.38);
    const result = [];
    let current = '';

    for (const sentence of sentences) {
      if (!current) {
        current = sentence;
        continue;
      }
      const candidate = `${current} ${sentence}`.trim();
      if (candidate.length <= maxChars || current.length < minChars) {
        current = candidate;
      } else {
        result.push(current);
        current = sentence;
      }
    }
    if (current) result.push(current);

    if (result.length > 1 && result[result.length - 1].length < minChars * 0.55) {
      const tail = result.pop();
      result[result.length - 1] = `${result[result.length - 1]} ${tail}`.trim();
    }
    return result;
  }

  function makeChunk(text, index) {
    return {
      id: `chunk-${Date.now()}-${index}-${Math.random().toString(36).slice(2, 7)}`,
      text,
      status: 'DRAFT',
      versions: [],
      selectedVersion: null,
      error: '',
    };
  }

  function revokeChunkAudio(chunk) {
    (chunk?.versions || []).forEach(version => {
      if (version?.url) URL.revokeObjectURL(version.url);
    });
  }

  function audioDuration(url) {
    return new Promise(resolve => {
      const audio = new Audio();
      audio.preload = 'metadata';
      audio.onloadedmetadata = () => resolve(Number.isFinite(audio.duration) ? audio.duration : 0);
      audio.onerror = () => resolve(0);
      audio.src = url;
    });
  }

  async function generateChunkAudio(index, regenerate = false) {
    const chunk = chunks[index];
    if (!chunk) return;
    if (!engineOnline) {
      window.alert('Voicebox 엔진이 아직 연결되지 않았습니다. 엔진이 온라인이 되면 이 버튼에서 바로 음성이 생성됩니다.');
      return;
    }
    if (!voiceProfile.value) {
      window.alert('먼저 상단에서 Voice 프로필을 선택해 주세요.');
      voiceProfile.focus();
      return;
    }

    chunk.status = 'PROCESSING';
    chunk.error = '';
    renderChunks();

    try {
      const headers = getAuthHeaders();
      headers['Content-Type'] = 'application/json';
      const response = await fetch('/v1-api/voicebox/generate/chunk', {
        method: 'POST',
        credentials: 'include',
        cache: 'no-store',
        headers,
        body: JSON.stringify({
          profile_id: voiceProfile.value,
          text: chunk.text,
          language: 'ko',
          engine: voiceEngine.value,
          model_size: voiceModelSize.value || null,
          normalize: true,
          max_chunk_chars: 800,
          crossfade_ms: 50,
        }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `음성 생성 실패 (${response.status})`);
      }

      const blob = await response.blob();
      if (!blob.size) throw new Error('생성된 음성 파일이 비어 있습니다.');
      const url = URL.createObjectURL(blob);
      const durationSec = await audioDuration(url);
      const version = {
        id: `v-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        label: `V${chunk.versions.length + 1}`,
        url,
        blob,
        durationSec,
        createdAt: new Date().toISOString(),
      };
      chunk.versions.push(version);
      chunk.selectedVersion = version.id;
      chunk.status = 'COMPLETED';
      chunk.error = '';
      renderChunks();
    } catch (error) {
      chunk.status = 'ERROR';
      chunk.error = error instanceof Error ? error.message : '음성 생성 중 오류가 발생했습니다.';
      renderChunks();
    }
  }

  function updateCounters() {
    scriptCounter.textContent = `${scriptInput.value.length.toLocaleString('ko-KR')}자`;
    chunkSummary.textContent = chunks.length ? `${chunks.length}개 청크` : '0개';
    emptyState.hidden = chunks.length > 0;
    playAll.disabled = !chunks.some(chunk => chunk.selectedVersion);
    exportAll.disabled = !chunks.length || !chunks.every(chunk => chunk.selectedVersion);
  }

  function waveBars(seed) {
    const heights = [18, 31, 23, 38, 27, 44, 21, 34, 49, 26, 39, 20, 33, 46, 24, 36, 28, 42, 22, 35];
    return heights.map((height, index) => `<span style="height:${Math.max(10, height + ((seed + index) % 5) - 2)}%"></span>`).join('');
  }

  function renderChunks() {
    chunkList.innerHTML = '';
    chunks.forEach((chunk, index) => {
      const seconds = estimateSeconds(chunk.text);
      const card = document.createElement('section');
      card.className = 'chunk-card';
      card.dataset.chunkId = chunk.id;
      const buttonLabel = chunk.status === 'PROCESSING' ? '생성 중...' : (engineOnline ? '음성 생성' : '생성 준비');
      const selected = chunk.versions.find(version => version.id === chunk.selectedVersion) || null;
      const actualDuration = selected?.durationSec ? `실제 ${selected.durationSec.toFixed(1)}초` : `예상 ${seconds}초`;
      const statusLabel = chunk.status === 'DRAFT' ? '대본 준비'
        : chunk.status === 'PROCESSING' ? '음성 생성 중'
        : chunk.status === 'COMPLETED' ? '검수 가능'
        : chunk.status === 'ERROR' ? '확인 필요'
        : chunk.status;
      const versionButtons = chunk.versions.length
        ? `<div class="version-strip"><span>생성 버전</span>${chunk.versions.map((version, versionIndex) => `
            <button type="button" class="version-chip ${version.id === chunk.selectedVersion ? 'selected' : ''}" data-action="select-version" data-version-index="${versionIndex}">
              ${escapeHtml(version.label)}${version.durationSec ? ` · ${version.durationSec.toFixed(1)}s` : ''}
            </button>`).join('')}</div>`
        : '';
      const errorMessage = chunk.error ? `<p class="chunk-error">${escapeHtml(chunk.error)}</p>` : '';
      card.innerHTML = `
        <div class="chunk-card-header">
          <div class="chunk-title">
            <span class="chunk-number">${String(index + 1).padStart(2, '0')}</span>
            <div class="chunk-meta">
              <strong>Chunk #${index + 1}</strong>
              <small>${actualDuration} · ${chunk.text.length}자</small>
            </div>
          </div>
          <span class="chunk-status ${chunk.status.toLowerCase()}">${statusLabel}</span>
        </div>
        <textarea class="chunk-text" data-action="edit" ${chunk.status === 'PROCESSING' ? 'disabled' : ''}>${escapeHtml(chunk.text)}</textarea>
        <div class="wave-placeholder ${selected ? 'ready' : ''}">${waveBars(index)}</div>
        ${versionButtons}
        ${errorMessage}
        <div class="chunk-actions">
          <button type="button" class="chunk-generate" data-action="generate" ${chunk.status === 'PROCESSING' ? 'disabled' : ''}>${buttonLabel}</button>
          <button type="button" class="chunk-regenerate" data-action="regenerate" ${!selected || chunk.status === 'PROCESSING' ? 'disabled' : ''}>개별 재생성</button>
          <button type="button" class="chunk-play" data-action="play" ${!selected || chunk.status === 'PROCESSING' ? 'disabled' : ''}>재생</button>
          <button type="button" class="chunk-delete" data-action="delete" ${chunk.status === 'PROCESSING' ? 'disabled' : ''}>청크 삭제</button>
        </div>
      `;
      chunkList.appendChild(card);
    });
    updateCounters();
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function splitNow() {
    const source = scriptInput.value.trim();
    if (!source) {
      window.alert('먼저 전체 대본을 입력해 주세요.');
      scriptInput.focus();
      return;
    }
    chunks.forEach(revokeChunkAudio);
    chunks = smartChunk(source, Number(targetSeconds.value)).map(makeChunk);
    renderChunks();
  }

  function demoScript() {
    scriptInput.value = `오늘은 실제 현장에서 자주 발생하는 배관 막힘의 원인과 해결 과정을 설명드리겠습니다. 고객님은 며칠 전부터 싱크대 물이 천천히 내려가다가 아침부터는 거의 빠지지 않는다고 연락을 주셨습니다.\n\n현장에 도착한 뒤 먼저 배수 상태와 역류 여부를 확인했습니다. 겉으로 보이는 이물질만 제거하는 것이 아니라 배관 안쪽의 기름때와 슬러지가 어느 구간에 쌓였는지 확인하는 과정이 필요합니다.\n\n점검 결과 주방에서 오래 사용하면서 쌓인 기름 성분과 음식물 찌꺼기가 배관 안쪽을 좁게 만들고 있었습니다. 이런 경우 단순히 약품을 붓는 것보다 막힘 위치와 배관 상태에 맞는 장비를 선택해야 합니다.\n\n작업 후에는 다시 여러 차례 물을 흘려보내 배수 속도와 역류 여부를 확인했습니다. 물이 정상적으로 내려가는 것만 확인하고 끝내지 않고, 고객님께 다시 막히는 것을 줄이기 위한 사용 방법도 함께 설명드렸습니다.\n\n하수구나 싱크대 막힘은 같은 증상처럼 보여도 원인이 다를 수 있습니다. 현장 상태를 먼저 확인하고 필요한 범위만 작업하는 것이 시간과 비용을 줄이는 가장 현실적인 방법입니다.`;
    updateCounters();
    splitNow();
  }

  scriptInput.addEventListener('input', updateCounters);
  document.getElementById('split-script').addEventListener('click', splitNow);
  document.getElementById('load-demo').addEventListener('click', demoScript);
  document.getElementById('clear-script').addEventListener('click', () => {
    if (scriptInput.value && !window.confirm('전체 대본과 현재 청크를 비울까요?')) return;
    scriptInput.value = '';
    chunks.forEach(revokeChunkAudio);
    chunks = [];
    renderChunks();
  });
  targetSeconds.addEventListener('change', () => {
    if (scriptInput.value.trim()) splitNow();
  });
  document.getElementById('back-to-v1').addEventListener('click', () => {
    window.location.href = '/v1/';
  });

  chunkList.addEventListener('input', event => {
    const textarea = event.target.closest('[data-action="edit"]');
    if (!textarea) return;
    const card = textarea.closest('[data-chunk-id]');
    const chunk = chunks.find(item => item.id === card?.dataset.chunkId);
    if (!chunk) return;
    revokeChunkAudio(chunk);
    chunk.text = textarea.value;
    chunk.status = 'DRAFT';
    chunk.versions = [];
    chunk.selectedVersion = null;
    chunk.error = '';
    updateCounters();
    const meta = card.querySelector('.chunk-meta small');
    if (meta) meta.textContent = `예상 ${estimateSeconds(chunk.text)}초 · ${chunk.text.length}자 · 실제 생성 후 길이 재계산`;
  });

  chunkList.addEventListener('click', async event => {
    const button = event.target.closest('button[data-action]');
    if (!button) return;
    const card = button.closest('[data-chunk-id]');
    const index = chunks.findIndex(item => item.id === card?.dataset.chunkId);
    if (index < 0) return;
    const chunk = chunks[index];
    const action = button.dataset.action;

    if (action === 'delete') {
      revokeChunkAudio(chunk);
      chunks.splice(index, 1);
      renderChunks();
      return;
    }

    if (action === 'generate' || action === 'regenerate') {
      await generateChunkAudio(index, action === 'regenerate');
      return;
    }

    if (action === 'play') {
      const selected = chunk.versions.find(version => version.id === chunk.selectedVersion);
      if (!selected?.url) return;
      const audio = new Audio(selected.url);
      audio.play().catch(() => window.alert('브라우저에서 생성 음성을 재생하지 못했습니다.'));
      return;
    }

    if (action === 'select-version') {
      const versionIndex = Number(button.dataset.versionIndex);
      const version = chunk.versions[versionIndex];
      if (!version) return;
      chunk.selectedVersion = version.id;
      chunk.status = 'COMPLETED';
      renderChunks();
    }
  });

  exportAll.addEventListener('click', () => {
    window.alert('모든 청크의 최종 버전이 선택되면 WAV/MP3와 SRT를 함께 생성하도록 연결할 예정입니다.');
  });
  playAll.addEventListener('click', async () => {
    const queue = chunks
      .map(chunk => chunk.versions.find(version => version.id === chunk.selectedVersion))
      .filter(Boolean);
    if (!queue.length) return;
    playAll.disabled = true;
    playAll.textContent = '전체 재생 중...';
    try {
      for (const version of queue) {
        await new Promise(resolve => {
          const audio = new Audio(version.url);
          audio.onended = resolve;
          audio.onerror = resolve;
          audio.play().catch(resolve);
        });
      }
    } finally {
      playAll.textContent = '전체 연속 재생';
      updateCounters();
    }
  });

  Promise.resolve()
    .then(requireAdmin)
    .then(allowed => allowed && checkEngine());
  updateCounters();
})();
