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
  const chunksPanel = document.getElementById('chunks-panel');
  const targetSeconds = document.getElementById('chunk-seconds');
  const voiceGender = document.getElementById('voice-gender');
  const voiceProfile = document.getElementById('voice-profile');
  const voiceEngine = document.getElementById('voice-engine');
  const voiceModelSize = document.getElementById('voice-model-size');
  const engineStatus = document.getElementById('engine-status');
  const statusDot = document.querySelector('.status-dot');
  const exportAll = document.getElementById('export-all');
  const playAll = document.getElementById('play-all');
  const generateAll = document.getElementById('generate-all');
  const generateAllBottom = document.getElementById('generate-all-bottom');
  const mergeAndSave = document.getElementById('merge-and-save');
  const batchStatusLabel = document.getElementById('batch-status-label');
  const batchStatusCount = document.getElementById('batch-status-count');
  const batchProgressBar = document.getElementById('batch-progress-bar');
  const batchProgressTrack = document.querySelector('.batch-progress-track');
  const finalizeReadyText = document.getElementById('finalize-ready-text');
  const projectName = document.getElementById('project-name');
  const silenceMs = document.getElementById('silence-ms');
  const ttsSpeed = document.getElementById('tts-speed');
  const backgroundMusic = document.getElementById('background-music');
  const musicVolume = document.getElementById('music-volume');
  const voiceCloneModal = document.getElementById('voice-clone-modal');
  const voiceCloneForm = document.getElementById('voice-clone-form');
  const cloneSubmit = document.getElementById('clone-submit');
  const cloneFormMessage = document.getElementById('clone-form-message');
  const cloneUploadProgress = document.getElementById('clone-upload-progress');
  const cloneUploadLabel = document.getElementById('clone-upload-label');
  const cloneUploadPercent = document.getElementById('clone-upload-percent');
  const cloneUploadBar = document.getElementById('clone-upload-bar');

  let chunks = [];
  let engineOnline = false;
  let batchGenerating = false;
  let batchStoppedByError = false;
  let availableVoiceProfiles = [];
  let availableMusicTracks = [];

  async function loadBackgroundMusicOptions() {
    if (!backgroundMusic) return;
    try {
      const response = await fetch('/v1-api/podcast/public/music/manifest', { cache: 'no-store' });
      if (!response.ok) throw new Error(`music manifest ${response.status}`);
      const payload = await response.json();
      availableMusicTracks = Array.isArray(payload.items)
        ? payload.items.filter(item => item && item.download_url && item.name)
        : [];
      const current = backgroundMusic.value || 'none';
      backgroundMusic.querySelectorAll('option[data-music-track]').forEach(option => option.remove());
      availableMusicTracks.forEach(item => {
        const option = document.createElement('option');
        option.value = item.name;
        option.textContent = item.name.replace(/\.[^.]+$/, '');
        option.dataset.musicTrack = '1';
        backgroundMusic.appendChild(option);
      });
      backgroundMusic.value = current === 'none' || current === 'random' || availableMusicTracks.some(item => item.name === current) ? current : 'none';
    } catch (error) {
      availableMusicTracks = [];
      console.warn('VoiceBox BGM manifest load failed:', error);
    }
  }

  function speedAdjustedChannels(buffer, speed) {
    const safeSpeed = Math.max(0.9, Math.min(1.15, Number(speed) || 1));
    if (Math.abs(safeSpeed - 1) < 0.001) {
      return {
        channels: Array.from({ length: buffer.numberOfChannels }, (_, channel) => buffer.getChannelData(channel)),
        length: buffer.length,
      };
    }
    const targetLength = Math.max(1, Math.round(buffer.length / safeSpeed));
    const channels = [];
    for (let channel = 0; channel < buffer.numberOfChannels; channel += 1) {
      const source = buffer.getChannelData(channel);
      const target = new Float32Array(targetLength);
      for (let i = 0; i < targetLength; i += 1) {
        const sourcePos = i * safeSpeed;
        const left = Math.min(source.length - 1, Math.floor(sourcePos));
        const right = Math.min(source.length - 1, left + 1);
        const frac = sourcePos - left;
        target[i] = source[left] * (1 - frac) + source[right] * frac;
      }
      channels.push(target);
    }
    return { channels, length: targetLength };
  }

  async function mixBackgroundMusicIntoChannels(channels, sampleRate) {
    const mode = backgroundMusic?.value || 'none';
    if (mode === 'none' || !availableMusicTracks.length) return { channels, trackName: '' };
    const track = mode === 'random'
      ? availableMusicTracks[Math.floor(Math.random() * availableMusicTracks.length)]
      : availableMusicTracks.find(item => item.name === mode);
    if (!track) return { channels, trackName: '' };

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return { channels, trackName: '' };
    const context = new AudioContextClass({ sampleRate });
    try {
      const musicUrl = String(track.download_url || '').startsWith('/api/')
        ? `/v1-api/${String(track.download_url).slice('/api/'.length)}`
        : track.download_url;
      const response = await fetch(musicUrl, { cache: 'force-cache', credentials: 'include' });
      if (!response.ok) throw new Error(`배경음악을 불러오지 못했습니다: ${track.name}`);
      const musicBuffer = await context.decodeAudioData((await response.arrayBuffer()).slice(0));
      const leftMusic = musicBuffer.getChannelData(0);
      const rightMusic = musicBuffer.numberOfChannels > 1 ? musicBuffer.getChannelData(1) : leftMusic;
      const musicRatio = musicBuffer.sampleRate / sampleRate;
      const volume = Math.max(0, Math.min(0.5, Number(musicVolume?.value || 0.15)));
      const fadeFrames = Math.min(Math.round(sampleRate * 1.2), Math.floor(channels[0].length / 4));
      const output = channels.map(source => new Float32Array(source));
      while (output.length < 2) output.push(new Float32Array(output[0]));
      for (let i = 0; i < output[0].length; i += 1) {
        const musicIndex = Math.floor(i * musicRatio) % leftMusic.length;
        const fadeIn = fadeFrames ? Math.min(1, i / fadeFrames) : 1;
        const fadeOut = fadeFrames ? Math.min(1, (output[0].length - 1 - i) / fadeFrames) : 1;
        const gain = volume * Math.max(0, Math.min(fadeIn, fadeOut));
        output[0][i] = Math.tanh(output[0][i] * 0.92 + leftMusic[musicIndex] * gain);
        output[1][i] = Math.tanh(output[1][i] * 0.92 + rightMusic[musicIndex] * gain);
      }
      return { channels: output, trackName: track.name };
    } finally {
      await context.close().catch(() => {});
    }
  }
  const GPU_BATCH_SIZE = 4;
  const AUTO_PLAY_THRESHOLD = 0.7;
  let batchAutoPlayContext = null;
  let batchAutoPlaybackStarted = false;
  let batchAutoPlaybackPromise = null;

  const OFFICIAL_VOICE_META = {
    Sohee: { gender: 'female', label: 'Sohee · 한국 여성 · 따뜻함' },
    Serena: { gender: 'female', label: 'Serena · 부드러운 여성' },
    Vivian: { gender: 'female', label: 'Vivian · 밝은 여성' },
    Ono_Anna: { gender: 'female', label: 'Ono Anna · 발랄한 여성' },
    Aiden: { gender: 'male', label: 'Aiden · 밝고 또렷한 남성' },
    Ryan: { gender: 'male', label: 'Ryan · 힘 있고 리듬감 있는 남성' },
    Dylan: { gender: 'male', label: 'Dylan · 젊고 자연스러운 남성' },
    Eric: { gender: 'male', label: 'Eric · 활기 있는 허스키 남성' },
    Uncle_Fu: { gender: 'male', label: 'Uncle Fu · 묵직한 중년 남성' },
  };

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

  function voiceCategoryForProfile(profile) {
    const voiceId = String(profile?.preset_voice_id || '').trim();
    const official = OFFICIAL_VOICE_META[voiceId];
    if (profile?.voice_type === 'preset' && profile?.preset_engine === 'qwen_custom_voice' && official) {
      return official.gender;
    }
    return 'custom';
  }

  function syncEngineFromSelectedProfile() {
    const selectedOption = voiceProfile.selectedOptions?.[0];
    if (selectedOption?.dataset.engine && [...voiceEngine.options].some(option => option.value === selectedOption.dataset.engine)) {
      voiceEngine.value = selectedOption.dataset.engine;
    }
    updateBatchUi();
  }

  function renderVoiceProfileOptions(preferredProfileId = '') {
    const category = voiceGender?.value || 'female';
    const filtered = availableVoiceProfiles.filter(profile => voiceCategoryForProfile(profile) === category);
    if (!filtered.length) {
      const emptyLabel = category === 'custom' ? '등록된 내 목소리 없음' : '사용 가능한 공식 보이스 없음';
      voiceProfile.innerHTML = `<option value="">${emptyLabel}</option>`;
      syncEngineFromSelectedProfile();
      return;
    }

    voiceProfile.innerHTML = filtered.map((profile, index) => {
      const id = escapeHtml(profile.id || '');
      const voiceId = String(profile.preset_voice_id || '').trim();
      const official = OFFICIAL_VOICE_META[voiceId];
      const name = escapeHtml(official?.label || profile.name || `내 목소리 ${index + 1}`);
      const defaultEngine = escapeHtml(profile.default_engine || profile.preset_engine || 'qwen');
      return `<option value="${id}" data-engine="${defaultEngine}">${name}</option>`;
    }).join('');

    if (preferredProfileId && filtered.some(profile => profile.id === preferredProfileId)) {
      voiceProfile.value = preferredProfileId;
    } else if (category === 'female') {
      const sohee = filtered.find(profile => profile.preset_voice_id === 'Sohee');
      if (sohee?.id) voiceProfile.value = sohee.id;
    }
    syncEngineFromSelectedProfile();
  }

  async function loadVoiceProfiles(preferredProfileId = '') {
    voiceProfile.innerHTML = '<option value="">Voice 프로필 불러오는 중...</option>';
    try {
      const response = await fetch('/v1-api/voicebox/profiles', {
        credentials: 'include',
        cache: 'no-store',
        headers: getAuthHeaders(),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || 'Voice 프로필을 불러오지 못했습니다.');
      availableVoiceProfiles = Array.isArray(payload.profiles) ? payload.profiles : [];
      if (!availableVoiceProfiles.length) {
        voiceProfile.innerHTML = '<option value="">등록된 Voice 프로필 없음</option>';
        return;
      }
      renderVoiceProfileOptions(preferredProfileId);
    } catch (_) {
      availableVoiceProfiles = [];
      voiceProfile.innerHTML = '<option value="">엔진 연결 후 프로필 선택</option>';
    }
  }

  function openVoiceCloneModal() {
    if (!voiceCloneModal) return;
    voiceCloneModal.hidden = false;
    document.body.classList.add('modal-open');
    cloneFormMessage.textContent = '';
    cloneUploadProgress.hidden = true;
    cloneUploadBar.style.width = '0%';
    cloneUploadPercent.textContent = '0%';
    window.setTimeout(() => document.getElementById('clone-profile-name')?.focus(), 30);
  }

  function closeVoiceCloneModal() {
    if (!voiceCloneModal || cloneSubmit?.disabled) return;
    voiceCloneModal.hidden = true;
    document.body.classList.remove('modal-open');
  }

  function submitCloneProfileWithProgress(formData) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/v1-api/voicebox/profiles/clone');
      xhr.withCredentials = true;
      const authHeaders = getAuthHeaders();
      if (authHeaders.Authorization) xhr.setRequestHeader('Authorization', authHeaders.Authorization);

      xhr.upload.addEventListener('progress', event => {
        cloneUploadProgress.hidden = false;
        if (!event.lengthComputable) {
          cloneUploadLabel.textContent = '목소리 샘플을 서버로 전송하고 있습니다.';
          cloneUploadPercent.textContent = '전송 중';
          return;
        }
        const percent = Math.max(0, Math.min(100, Math.round((event.loaded / event.total) * 100)));
        cloneUploadLabel.textContent = percent < 100 ? '목소리 샘플을 서버로 전송하고 있습니다.' : 'VoiceBox가 음성 프로필을 만들고 있습니다.';
        cloneUploadPercent.textContent = `${percent}%`;
        cloneUploadBar.style.width = `${percent}%`;
      });

      xhr.addEventListener('load', () => {
        let payload = {};
        try { payload = JSON.parse(xhr.responseText || '{}'); } catch (_) {}
        if (xhr.status >= 200 && xhr.status < 300) resolve(payload);
        else reject(new Error(payload.detail || `목소리 등록 실패 (${xhr.status})`));
      });
      xhr.addEventListener('error', () => reject(new Error('목소리 샘플 전송 중 네트워크 오류가 발생했습니다.')));
      xhr.addEventListener('timeout', () => reject(new Error('목소리 등록 시간이 초과되었습니다.')));
      xhr.timeout = 90000;
      xhr.send(formData);
    });
  }

  async function handleVoiceCloneSubmit(event) {
    event.preventDefault();
    if (!voiceCloneForm || !cloneSubmit) return;
    const fileInput = document.getElementById('clone-audio-file');
    const file = fileInput?.files?.[0];
    if (!file) {
      cloneFormMessage.textContent = '먼저 음성 샘플 파일을 선택해 주세요.';
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      cloneFormMessage.textContent = '음성 샘플은 50MB 이하 파일만 등록할 수 있습니다.';
      return;
    }

    cloneSubmit.disabled = true;
    cloneSubmit.textContent = '등록 중...';
    cloneFormMessage.textContent = '';
    cloneUploadProgress.hidden = false;
    cloneUploadLabel.textContent = '목소리 샘플을 준비하고 있습니다.';
    cloneUploadPercent.textContent = '0%';
    cloneUploadBar.style.width = '0%';

    try {
      const formData = new FormData(voiceCloneForm);
      const payload = await submitCloneProfileWithProgress(formData);
      const createdProfile = payload.profile || null;
      cloneUploadBar.style.width = '100%';
      cloneUploadPercent.textContent = '100%';
      cloneUploadLabel.textContent = '내 목소리 프로필 등록 완료';
      cloneFormMessage.textContent = '등록이 완료됐습니다. 지금 바로 이 목소리로 청크를 생성할 수 있습니다.';
      if (voiceGender) voiceGender.value = 'custom';
      await loadVoiceProfiles(createdProfile?.id || '');
      window.setTimeout(() => {
        voiceCloneForm.reset();
        voiceCloneModal.hidden = true;
        document.body.classList.remove('modal-open');
      }, 900);
    } catch (error) {
      cloneFormMessage.textContent = error instanceof Error ? error.message : '목소리 등록 중 오류가 발생했습니다.';
      cloneUploadLabel.textContent = '등록 실패';
    } finally {
      cloneSubmit.disabled = false;
      cloneSubmit.textContent = '내 목소리 등록';
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

  function sentenceChunks(text) {
    return splitSentences(text);
  }

  function makeChunk(text, index) {
    return {
      id: `chunk-${Date.now()}-${index}-${Math.random().toString(36).slice(2, 7)}`,
      text,
      status: 'DRAFT',
      versions: [],
      selectedVersion: null,
      error: '',
      progress: {
        phase: 'idle',
        label: '대기',
        startedAt: 0,
        bytesReceived: 0,
        totalBytes: 0,
        percent: null,
      },
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

  function sleep(ms) {
    return new Promise(resolve => window.setTimeout(resolve, ms));
  }

  function setChunkProgress(chunk, phase, label, options = {}) {
    chunk.progress = {
      ...(chunk.progress || {}),
      phase,
      label,
      startedAt: chunk.progress?.startedAt || Date.now(),
      bytesReceived: options.bytesReceived ?? chunk.progress?.bytesReceived ?? 0,
      totalBytes: options.totalBytes ?? chunk.progress?.totalBytes ?? 0,
      percent: Number.isFinite(options.percent) ? options.percent : null,
    };
    renderChunks();
  }

  async function generateChunkAudio(index, regenerate = false) {
    const chunk = chunks[index];
    if (!chunk) return false;
    if (!engineOnline) {
      window.alert('Voicebox 엔진이 아직 연결되지 않았습니다. 엔진이 온라인이 되면 이 버튼에서 바로 음성이 생성됩니다.');
      return false;
    }
    if (!voiceProfile.value) {
      window.alert('먼저 상단에서 Voice 프로필을 선택해 주세요.');
      voiceProfile.focus();
      return false;
    }

    chunk.status = 'PROCESSING';
    chunk.error = '';
    chunk.progress = {
      phase: 'starting',
      label: regenerate ? '재생성 작업을 준비하고 있습니다.' : '음성 생성 작업을 준비하고 있습니다.',
      startedAt: Date.now(),
      bytesReceived: 0,
      totalBytes: 0,
      percent: null,
    };
    renderChunks();

    try {
      const headers = getAuthHeaders();
      headers['Content-Type'] = 'application/json';
      const requestBody = {
        profile_id: voiceProfile.value,
        text: chunk.text,
        language: 'ko',
        engine: voiceEngine.value,
        model_size: voiceModelSize.value || null,
        normalize: true,
        max_chunk_chars: 800,
        crossfade_ms: 50,
      };

      const startResponse = await fetch('/v1-api/voicebox/generate/start', {
        method: 'POST',
        credentials: 'include',
        cache: 'no-store',
        headers,
        body: JSON.stringify(requestBody),
      });
      const startPayload = await startResponse.json().catch(() => ({}));
      if (!startResponse.ok || !startPayload.generation_id) {
        throw new Error(startPayload.detail || `음성 생성 시작 실패 (${startResponse.status})`);
      }

      const generationId = startPayload.generation_id;
      setChunkProgress(chunk, 'generating', 'VoiceBox가 나레이션을 생성하고 있습니다.');

      let finalStatus = null;
      const deadline = Date.now() + 180000;
      while (Date.now() < deadline) {
        await sleep(700);
        const statusResponse = await fetch(`/v1-api/voicebox/generate/${encodeURIComponent(generationId)}/status`, {
          credentials: 'include',
          cache: 'no-store',
          headers: getAuthHeaders(),
        });
        const statusPayload = await statusResponse.json().catch(() => ({}));
        if (!statusResponse.ok) {
          throw new Error(statusPayload.detail || `생성 상태 확인 실패 (${statusResponse.status})`);
        }

        finalStatus = statusPayload;
        if (statusPayload.status === 'loading_model') {
          setChunkProgress(chunk, 'loading_model', '음성 모델을 GPU에 준비하고 있습니다.');
        } else if (statusPayload.status === 'generating') {
          setChunkProgress(chunk, 'generating', 'VoiceBox가 나레이션을 생성하고 있습니다.');
        } else if (statusPayload.status === 'completed') {
          break;
        } else if (statusPayload.status === 'failed') {
          throw new Error(statusPayload.error || 'VoiceBox 음성 생성에 실패했습니다.');
        }
      }

      if (!finalStatus || finalStatus.status !== 'completed') {
        throw new Error('VoiceBox 음성 생성 시간이 초과되었습니다.');
      }

      setChunkProgress(chunk, 'receiving', '완성된 오디오를 브라우저로 전송하고 있습니다.', { percent: 0 });
      const audioResponse = await fetch(`/v1-api/voicebox/generate/${encodeURIComponent(generationId)}/audio`, {
        credentials: 'include',
        cache: 'no-store',
        headers: getAuthHeaders(),
      });
      if (!audioResponse.ok) {
        const payload = await audioResponse.json().catch(() => ({}));
        throw new Error(payload.detail || `오디오 수신 실패 (${audioResponse.status})`);
      }

      const totalBytes = Number(audioResponse.headers.get('content-length') || 0);
      let blob;
      if (audioResponse.body && typeof audioResponse.body.getReader === 'function') {
        const reader = audioResponse.body.getReader();
        const parts = [];
        let bytesReceived = 0;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          if (!value) continue;
          parts.push(value);
          bytesReceived += value.byteLength;
          const percent = totalBytes > 0 ? Math.min(100, Math.round((bytesReceived / totalBytes) * 100)) : null;
          chunk.progress = {
            ...(chunk.progress || {}),
            phase: 'receiving',
            label: '완성된 오디오를 브라우저로 전송하고 있습니다.',
            bytesReceived,
            totalBytes,
            percent,
          };
          renderChunks();
        }
        blob = new Blob(parts, { type: audioResponse.headers.get('content-type') || 'audio/wav' });
      } else {
        blob = await audioResponse.blob();
      }

      if (!blob.size) throw new Error('생성된 음성 파일이 비어 있습니다.');
      const url = URL.createObjectURL(blob);
      const durationSec = await audioDuration(url);
      const version = {
        id: `v-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        label: `V${chunk.versions.length + 1}`,
        url,
        blob,
        durationSec,
        generationId,
        createdAt: new Date().toISOString(),
      };
      chunk.versions.push(version);
      chunk.selectedVersion = version.id;
      chunk.status = 'COMPLETED';
      chunk.error = '';
      chunk.progress = {
        phase: 'completed',
        label: `생성 완료 · ${durationSec.toFixed(1)}초`,
        startedAt: chunk.progress?.startedAt || Date.now(),
        bytesReceived: blob.size,
        totalBytes: blob.size,
        percent: 100,
      };
      renderChunks();
      return true;
    } catch (error) {
      chunk.status = 'ERROR';
      chunk.error = error instanceof Error ? error.message : '음성 생성 중 오류가 발생했습니다.';
      chunk.progress = {
        ...(chunk.progress || {}),
        phase: 'error',
        label: chunk.error,
        percent: null,
      };
      renderChunks();
      return false;
    }
  }

  function selectedVersionForChunk(chunk) {
    return chunk?.versions?.find(version => version.id === chunk.selectedVersion) || null;
  }

  function updateBatchUi(message = '') {
    const total = chunks.length;
    const completed = chunks.filter(chunk => Boolean(selectedVersionForChunk(chunk))).length;
    const percent = total > 0 ? Math.round((completed / total) * 100) : 0;
    const allReady = total > 0 && completed === total;
    const canGenerate = engineOnline && Boolean(voiceProfile?.value) && total > 0 && !batchGenerating && !allReady;

    if (batchStatusCount) batchStatusCount.textContent = `${completed} / ${total}`;
    if (batchProgressBar) batchProgressBar.style.width = `${percent}%`;
    if (batchProgressTrack) batchProgressTrack.setAttribute('aria-valuenow', String(percent));

    if (batchStatusLabel) {
      if (message) batchStatusLabel.textContent = message;
      else if (batchGenerating) batchStatusLabel.textContent = `전체 순차 생성 중 · ${completed}/${total} 완료`;
      else if (batchStoppedByError) batchStatusLabel.textContent = `순차 생성이 오류 청크에서 중지되었습니다 · ${completed}/${total} 완료`;
      else if (allReady) batchStatusLabel.textContent = `모든 청크 생성 완료 · ${total}개 준비됨`;
      else if (total) batchStatusLabel.textContent = `순차 생성을 시작할 준비가 되었습니다 · ${completed}/${total} 완료`;
      else batchStatusLabel.textContent = '대본을 분할하면 전체 순차 생성을 시작할 수 있습니다.';
    }

    if (finalizeReadyText) {
      finalizeReadyText.textContent = allReady
        ? `모든 청크가 준비됐습니다. ${Number(silenceMs?.value || 300) / 1000}초 간격으로 합쳐 자동 저장할 수 있습니다.`
        : `모든 청크가 생성되면 최종 합치기 버튼이 활성화됩니다. 현재 ${completed}/${total} 완료.`;
    }

    if (generateAll) generateAll.disabled = !canGenerate;
    if (generateAllBottom) generateAllBottom.disabled = !canGenerate;
    if (mergeAndSave) mergeAndSave.disabled = !allReady || batchGenerating;
    if (exportAll) exportAll.disabled = !allReady || batchGenerating;
  }

  async function unlockBatchAutoPlayback() {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return false;
    try {
      if (!batchAutoPlayContext) batchAutoPlayContext = new AudioContextClass();
      if (batchAutoPlayContext.state === 'suspended') await batchAutoPlayContext.resume();
      const buffer = batchAutoPlayContext.createBuffer(1, 1, batchAutoPlayContext.sampleRate);
      const source = batchAutoPlayContext.createBufferSource();
      source.buffer = buffer;
      source.connect(batchAutoPlayContext.destination);
      source.start();
      return true;
    } catch (_) {
      return false;
    }
  }

  async function receiveBatchGeneration(index, item) {
    const chunk = chunks[index];
    if (!chunk || !item?.generation_id) return false;
    setChunkProgress(chunk, 'receiving', '배치 생성 완료 · 오디오를 브라우저로 받고 있습니다.', { percent: 0 });
    const response = await fetch(`/v1-api/voicebox/generate/${encodeURIComponent(item.generation_id)}/audio`, {
      credentials: 'include',
      cache: 'no-store',
      headers: getAuthHeaders(),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `오디오 수신 실패 (${response.status})`);
    }
    const blob = await response.blob();
    if (!blob.size) throw new Error('배치에서 생성된 음성 파일이 비어 있습니다.');
    const url = URL.createObjectURL(blob);
    const durationSec = Number(item.duration || 0) || await audioDuration(url);
    const version = {
      id: `v-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      label: `V${chunk.versions.length + 1}`,
      url,
      blob,
      durationSec,
      generationId: item.generation_id,
      createdAt: new Date().toISOString(),
    };
    chunk.versions.push(version);
    chunk.selectedVersion = version.id;
    chunk.status = 'COMPLETED';
    chunk.error = '';
    chunk.progress = {
      phase: 'completed',
      label: `배치 생성 완료 · ${durationSec.toFixed(1)}초`,
      startedAt: chunk.progress?.startedAt || Date.now(),
      bytesReceived: blob.size,
      totalBytes: blob.size,
      percent: 100,
    };
    renderChunks();
    return true;
  }

  async function generateChunkBatch(indices) {
    const validIndices = indices.filter(index => chunks[index] && !selectedVersionForChunk(chunks[index]));
    if (!validIndices.length) return true;
    validIndices.forEach(index => {
      const chunk = chunks[index];
      chunk.status = 'PROCESSING';
      chunk.error = '';
      chunk.progress = {
        phase: 'generating',
        label: `${validIndices.length}문장 GPU 배치 생성 중`,
        startedAt: Date.now(),
        bytesReceived: 0,
        totalBytes: 0,
        percent: null,
      };
    });
    renderChunks();

    try {
      const headers = getAuthHeaders();
      headers['Content-Type'] = 'application/json';
      const response = await fetch('/v1-api/voicebox/generate/batch', {
        method: 'POST',
        credentials: 'include',
        cache: 'no-store',
        headers,
        body: JSON.stringify({
          profile_id: voiceProfile.value,
          texts: validIndices.map(index => chunks[index].text),
          language: 'ko',
          engine: voiceEngine.value,
          model_size: voiceModelSize.value || '0.6B',
          normalize: true,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !Array.isArray(payload.items) || payload.items.length !== validIndices.length) {
        throw new Error(payload.detail || `배치 생성 실패 (${response.status})`);
      }
      await Promise.all(validIndices.map((index, offset) => receiveBatchGeneration(index, payload.items[offset])));
      return true;
    } catch (error) {
      if (validIndices.length > 1) {
        const middle = Math.ceil(validIndices.length / 2);
        updateBatchUi(`${validIndices.length}문장 배치가 맞지 않아 더 작은 배치로 자동 재시도합니다.`);
        const first = await generateChunkBatch(validIndices.slice(0, middle));
        const second = first ? await generateChunkBatch(validIndices.slice(middle)) : false;
        return first && second;
      }
      const index = validIndices[0];
      chunks[index].status = 'DRAFT';
      updateBatchUi(`문장 #${index + 1}은 단일 생성으로 자동 재시도합니다.`);
      return generateChunkAudio(index, false);
    }
  }

  function buildGpuBatchGroups(indices) {
    const groups = [];
    for (let cursor = 0; cursor < indices.length; cursor += GPU_BATCH_SIZE) {
      groups.push(indices.slice(cursor, cursor + GPU_BATCH_SIZE));
    }
    return groups;
  }

  async function playGeneratedChunksAsReady() {
    if (!batchAutoPlayContext) return;
    for (let index = 0; index < chunks.length; index += 1) {
      let version = selectedVersionForChunk(chunks[index]);
      while (!version && batchGenerating && chunks[index]?.status !== 'ERROR') {
        await sleep(200);
        version = selectedVersionForChunk(chunks[index]);
      }
      if (!version?.blob) break;
      try {
        if (batchAutoPlayContext.state === 'suspended') await batchAutoPlayContext.resume();
        const arrayBuffer = await version.blob.arrayBuffer();
        const audioBuffer = await batchAutoPlayContext.decodeAudioData(arrayBuffer.slice(0));
        await new Promise(resolve => {
          const source = batchAutoPlayContext.createBufferSource();
          source.buffer = audioBuffer;
          source.playbackRate.value = Math.max(0.9, Math.min(1.15, Number(ttsSpeed?.value || 1)));
          source.connect(batchAutoPlayContext.destination);
          source.onended = resolve;
          source.start();
        });
      } catch (_) {
        break;
      }
    }
  }

  function maybeStartBatchAutoPlayback() {
    if (batchAutoPlaybackStarted || !chunks.length || !batchAutoPlayContext) return;
    const completed = chunks.filter(chunk => Boolean(selectedVersionForChunk(chunk))).length;
    const thresholdCount = Math.ceil(chunks.length * AUTO_PLAY_THRESHOLD);
    if (completed < thresholdCount) return;
    batchAutoPlaybackStarted = true;
    updateBatchUi(`${completed}/${chunks.length} 완료 · 약 70% 준비되어 브라우저 자동 재생을 시작합니다. 남은 음성은 계속 생성합니다.`);
    batchAutoPlaybackPromise = playGeneratedChunksAsReady();
  }

  async function generateAllSequentially() {
    if (batchGenerating) return;
    if (!chunks.length) {
      window.alert('먼저 대본을 문장 기준 청크로 분할해 주세요.');
      return;
    }
    if (!engineOnline) {
      window.alert('VoiceBox 엔진이 온라인인지 먼저 확인해 주세요.');
      return;
    }
    if (!voiceProfile?.value) {
      window.alert('먼저 사용할 Voice 프로필을 선택해 주세요.');
      voiceProfile?.focus();
      return;
    }

    await unlockBatchAutoPlayback();
    batchAutoPlaybackStarted = false;
    batchAutoPlaybackPromise = null;
    batchGenerating = true;
    batchStoppedByError = false;
    let shouldAutoMerge = false;
    const pendingIndices = chunks
      .map((chunk, index) => selectedVersionForChunk(chunk) ? -1 : index)
      .filter(index => index >= 0);
    const groups = buildGpuBatchGroups(pendingIndices);
    updateBatchUi(`GPU 배치 생성을 시작합니다 · 최대 ${GPU_BATCH_SIZE}문장씩 묶어 처리합니다.`);

    try {
      for (const group of groups) {
        if (!group.length) continue;
        updateBatchUi(`문장 ${group.map(index => `#${index + 1}`).join(', ')} GPU 배치 생성 중`);
        const success = await generateChunkBatch(group);
        if (!success) {
          batchStoppedByError = true;
          updateBatchUi('배치 생성 오류로 자동 작업을 중지했습니다. 오류 문장을 확인해 주세요.');
          break;
        }
        maybeStartBatchAutoPlayback();
      }

      shouldAutoMerge = chunks.length > 0 && chunks.every(chunk => Boolean(selectedVersionForChunk(chunk)));
      if (shouldAutoMerge) {
        batchStoppedByError = false;
        updateBatchUi(`전체 ${chunks.length}개 문장 생성 완료 · 재생은 계속하면서 최종 WAV 자동 합치기를 시작합니다.`);
      }
    } finally {
      batchGenerating = false;
      if (!shouldAutoMerge && !batchStoppedByError) updateBatchUi();
      updateCounters();
    }

    if (shouldAutoMerge) await mergeSelectedChunksAndSave();
  }

  function encodeMergedWav(channelData, sampleRate) {
    const channels = channelData.length;
    const frames = channelData[0]?.length || 0;
    const bytesPerSample = 2;
    const blockAlign = channels * bytesPerSample;
    const buffer = new ArrayBuffer(44 + frames * blockAlign);
    const view = new DataView(buffer);
    const writeText = (offset, text) => {
      for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i));
    };

    writeText(0, 'RIFF');
    view.setUint32(4, 36 + frames * blockAlign, true);
    writeText(8, 'WAVE');
    writeText(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, channels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * blockAlign, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, 16, true);
    writeText(36, 'data');
    view.setUint32(40, frames * blockAlign, true);

    let offset = 44;
    for (let frame = 0; frame < frames; frame += 1) {
      for (let channel = 0; channel < channels; channel += 1) {
        const sample = Math.max(-1, Math.min(1, channelData[channel][frame] || 0));
        view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
        offset += 2;
      }
    }
    return new Blob([buffer], { type: 'audio/wav' });
  }

  function safeFilename(value) {
    return String(value || 'VoiceBox_나레이션')
      .trim()
      .replace(/[\\/:*?\"<>|]+/g, '_')
      .replace(/\s+/g, '_')
      .slice(0, 80) || 'VoiceBox_나레이션';
  }

  function formatSrtTime(seconds) {
    const totalMs = Math.max(0, Math.round(Number(seconds || 0) * 1000));
    const hours = Math.floor(totalMs / 3600000);
    const minutes = Math.floor((totalMs % 3600000) / 60000);
    const secs = Math.floor((totalMs % 60000) / 1000);
    const ms = totalMs % 1000;
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(ms).padStart(3, '0')}`;
  }

  function buildMergedSrt(adjusted, gapFrames, sampleRate) {
    let frameOffset = 0;
    return adjusted.map((item, index) => {
      const start = frameOffset / sampleRate;
      const end = (frameOffset + item.length) / sampleRate;
      frameOffset += item.length;
      if (index < adjusted.length - 1) frameOffset += gapFrames;
      return `${index + 1}\n${formatSrtTime(start)} --> ${formatSrtTime(end)}\n${String(chunks[index]?.text || '').trim()}\n`;
    }).join('\n');
  }

  async function mergeSelectedChunksAndSave() {
    if (batchGenerating) return;
    const selectedVersions = chunks.map(selectedVersionForChunk);
    if (!chunks.length || selectedVersions.some(version => !version?.blob)) {
      window.alert('모든 청크의 최종 음성이 준비된 뒤 합칠 수 있습니다.');
      return;
    }

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      window.alert('이 브라우저에서는 WAV 병합 기능을 사용할 수 없습니다.');
      return;
    }

    const buttonSet = [mergeAndSave, exportAll].filter(Boolean);
    buttonSet.forEach(button => {
      button.disabled = true;
      button.dataset.originalText = button.textContent;
      button.textContent = '최종 WAV 합치는 중...';
    });
    if (finalizeReadyText) finalizeReadyText.textContent = '각 청크를 PCM으로 변환하고 하나의 WAV로 합치고 있습니다.';

    const context = new AudioContextClass({ sampleRate: 24000 });
    try {
      const decoded = [];
      for (let index = 0; index < selectedVersions.length; index += 1) {
        if (batchStatusLabel) batchStatusLabel.textContent = `최종 WAV 병합 중 · Chunk #${index + 1} 변환`;
        const arrayBuffer = await selectedVersions[index].blob.arrayBuffer();
        decoded.push(await context.decodeAudioData(arrayBuffer.slice(0)));
      }

      const sampleRate = context.sampleRate;
      const speed = Math.max(0.9, Math.min(1.15, Number(ttsSpeed?.value || 1)));
      const adjusted = decoded.map(buffer => speedAdjustedChannels(buffer, speed));
      const channelCount = Math.max(1, ...adjusted.map(item => item.channels.length));
      const gapFrames = Math.max(0, Math.round(sampleRate * (Number(silenceMs?.value || 300) / 1000)));
      const totalFrames = adjusted.reduce((sum, item) => sum + item.length, 0) + gapFrames * Math.max(0, adjusted.length - 1);
      let merged = Array.from({ length: channelCount }, () => new Float32Array(totalFrames));

      let writeOffset = 0;
      adjusted.forEach((item, bufferIndex) => {
        for (let channel = 0; channel < channelCount; channel += 1) {
          const source = item.channels[Math.min(channel, item.channels.length - 1)];
          merged[channel].set(source, writeOffset);
        }
        writeOffset += item.length;
        if (bufferIndex < adjusted.length - 1) writeOffset += gapFrames;
      });

      const mixed = await mixBackgroundMusicIntoChannels(merged, sampleRate);
      merged = mixed.channels;
      const wavBlob = encodeMergedWav(merged, sampleRate);
      const downloadUrl = URL.createObjectURL(wavBlob);
      const anchor = document.createElement('a');
      const filename = `${safeFilename(projectName?.value)}_최종나레이션.wav`;
      anchor.href = downloadUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 30000);

      const srtText = buildMergedSrt(adjusted, gapFrames, sampleRate);
      const srtBlob = new Blob([srtText], { type: 'application/x-subrip;charset=utf-8' });
      const srtUrl = URL.createObjectURL(srtBlob);
      const srtAnchor = document.createElement('a');
      srtAnchor.href = srtUrl;
      srtAnchor.download = `${safeFilename(projectName?.value)}_최종나레이션.srt`;
      document.body.appendChild(srtAnchor);
      srtAnchor.click();
      srtAnchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(srtUrl), 30000);

      const totalSeconds = totalFrames / sampleRate;
      const bgmLabel = mixed.trackName ? ` · BGM ${mixed.trackName.replace(/\.[^.]+$/, '')}` : ' · BGM 없음';
      if (batchStatusLabel) batchStatusLabel.textContent = `최종 WAV 저장 완료 · ${totalSeconds.toFixed(1)}초 · ${speed.toFixed(2)}x`;
      if (finalizeReadyText) finalizeReadyText.textContent = `${filename} 자동 저장 완료 · TTS ${speed.toFixed(2)}x · 청크 간 ${Number(silenceMs?.value || 300) / 1000}초${bgmLabel}`;
    } catch (error) {
      const message = error instanceof Error ? error.message : '최종 WAV 병합 중 오류가 발생했습니다.';
      if (batchStatusLabel) batchStatusLabel.textContent = '최종 WAV 병합 실패';
      if (finalizeReadyText) finalizeReadyText.textContent = message;
      window.alert(message);
    } finally {
      await context.close().catch(() => {});
      buttonSet.forEach(button => {
        button.textContent = button.dataset.originalText || '최종 WAV 합치기·저장';
        delete button.dataset.originalText;
      });
      updateCounters();
    }
  }

  function updateCounters() {
    scriptCounter.textContent = `${scriptInput.value.length.toLocaleString('ko-KR')}자`;
    chunkSummary.textContent = chunks.length ? `${chunks.length}개 청크` : '0개';
    emptyState.hidden = true;
    if (chunksPanel) chunksPanel.hidden = chunks.length === 0;
    playAll.disabled = !chunks.some(chunk => chunk.selectedVersion);
    updateBatchUi();
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
      const progress = chunk.progress || {};
      const elapsedSec = progress.startedAt ? Math.max(0, Math.round((Date.now() - progress.startedAt) / 1000)) : 0;
      const hasPercent = Number.isFinite(progress.percent);
      const receivedKb = progress.bytesReceived ? Math.round(progress.bytesReceived / 1024) : 0;
      const totalKb = progress.totalBytes ? Math.round(progress.totalBytes / 1024) : 0;
      const transferText = progress.phase === 'receiving'
        ? `${receivedKb.toLocaleString('ko-KR')} KB${totalKb ? ` / ${totalKb.toLocaleString('ko-KR')} KB` : ''}`
        : `${elapsedSec}초 경과`;
      const progressHtml = chunk.status === 'PROCESSING' || progress.phase === 'completed'
        ? `<div class="generation-progress ${escapeHtml(progress.phase || 'starting')}">
            <div class="generation-progress-head">
              <span class="generation-progress-label"><i></i>${escapeHtml(progress.label || '음성 생성 준비 중')}</span>
              <span class="generation-progress-meta">${hasPercent ? `${Math.round(progress.percent)}% · ` : ''}${transferText}</span>
            </div>
            <div class="generation-progress-track ${hasPercent ? 'determinate' : 'indeterminate'}" role="progressbar" ${hasPercent ? `aria-valuenow="${Math.round(progress.percent)}" aria-valuemin="0" aria-valuemax="100"` : 'aria-label="음성 생성 진행 중"'}>
              <span class="generation-progress-bar" style="${hasPercent ? `width:${Math.max(0, Math.min(100, progress.percent))}%` : ''}"></span>
            </div>
            <div class="generation-progress-steps">
              <span class="${['generating','receiving','completed'].includes(progress.phase) ? 'done' : 'active'}">모델 준비</span>
              <span class="${['receiving','completed'].includes(progress.phase) ? 'done' : progress.phase === 'generating' ? 'active' : ''}">음성 생성</span>
              <span class="${progress.phase === 'completed' ? 'done' : progress.phase === 'receiving' ? 'active' : ''}">오디오 수신</span>
              <span class="${progress.phase === 'completed' ? 'done active' : ''}">완료</span>
            </div>
          </div>`
        : '';
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
        ${progressHtml}
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
    chunks = sentenceChunks(source).map(makeChunk);
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
    chunk.progress = {
      phase: 'idle',
      label: '대기',
      startedAt: 0,
      bytesReceived: 0,
      totalBytes: 0,
      percent: null,
    };
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
      audio.playbackRate = Math.max(0.9, Math.min(1.15, Number(ttsSpeed?.value || 1)));
      audio.preservesPitch = true;
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

  generateAll?.addEventListener('click', generateAllSequentially);
  generateAllBottom?.addEventListener('click', generateAllSequentially);
  mergeAndSave?.addEventListener('click', mergeSelectedChunksAndSave);
  exportAll?.addEventListener('click', mergeSelectedChunksAndSave);
  silenceMs?.addEventListener('change', () => updateBatchUi());
  ttsSpeed?.addEventListener('change', () => updateBatchUi());
  backgroundMusic?.addEventListener('change', () => updateBatchUi());
  musicVolume?.addEventListener('change', () => updateBatchUi());
  loadBackgroundMusicOptions();

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
          audio.playbackRate = Math.max(0.9, Math.min(1.15, Number(ttsSpeed?.value || 1)));
          audio.preservesPitch = true;
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

  document.getElementById('open-voice-clone')?.addEventListener('click', openVoiceCloneModal);
  document.querySelectorAll('[data-clone-close]').forEach(button => {
    button.addEventListener('click', closeVoiceCloneModal);
  });
  voiceCloneForm?.addEventListener('submit', handleVoiceCloneSubmit);
  voiceGender?.addEventListener('change', () => renderVoiceProfileOptions());
  voiceProfile?.addEventListener('change', syncEngineFromSelectedProfile);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && voiceCloneModal && !voiceCloneModal.hidden) closeVoiceCloneModal();
  });

  Promise.resolve()
    .then(requireAdmin)
    .then(allowed => allowed && checkEngine());
  updateCounters();
})();
