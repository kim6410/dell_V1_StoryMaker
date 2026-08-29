(() => {
  'use strict';

  const STATE = window.__storymakerNarrationOverride = window.__storymakerNarrationOverride || {
    audioFile: null,
    srtFile: null,
  };

  function readAsDataURL(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(new Error(`${file?.name || '파일'} 읽기 실패`));
      reader.readAsDataURL(file);
    });
  }

  function updateInfo(root) {
    const info = root?.querySelector('[data-narration-source-info]');
    if (!info) return;
    if (!STATE.audioFile && !STATE.srtFile) {
      info.textContent = '기본 StoryMaker 음성 + SRT 사용';
      return;
    }
    const audioText = STATE.audioFile ? `음성: ${STATE.audioFile.name}` : '음성: 미선택';
    const srtText = STATE.srtFile ? `SRT: ${STATE.srtFile.name}` : 'SRT: 미선택';
    info.textContent = `${audioText} / ${srtText}`;
  }

  function reset(root) {
    STATE.audioFile = null;
    STATE.srtFile = null;
    const audioInput = root?.querySelector('[data-narration-audio-input]');
    const srtInput = root?.querySelector('[data-narration-srt-input]');
    if (audioInput) audioInput.value = '';
    if (srtInput) srtInput.value = '';
    updateInfo(root);
  }

  function findAnchorCard() {
    const nodes = [...document.querySelectorAll('button,p,h3,h4,span')];
    const label = nodes.find((el) => {
      const text = (el.textContent || '').trim();
      return text === '워터마크 설정' || text === '워터마크';
    });
    if (!label) return null;
    return label.closest('section') || label.closest('div.rounded-2xl') || label.parentElement;
  }

  function buildCard() {
    const card = document.createElement('section');
    card.dataset.storymakerNarrationSource = '1';
    card.className = 'rounded-[2rem] border border-cyan-300/30 bg-cyan-300/10 p-5';
    card.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;">
        <div>
          <p style="font-size:12px;font-weight:900;letter-spacing:.12em;color:#67e8f9;">NARRATION SOURCE</p>
          <h3 style="margin-top:6px;font-size:18px;font-weight:900;color:white;">나레이션 소스</h3>
        </div>
        <button type="button" data-narration-reset style="border:1px solid #475569;border-radius:12px;padding:8px 12px;font-size:12px;font-weight:800;color:#cbd5e1;background:#020617;">기본으로</button>
      </div>
      <p style="margin-top:10px;font-size:12px;line-height:1.6;color:#cbd5e1;">VoiceBox 등에서 만든 TTS 음성과 SRT를 올리면 기존 음성/자막만 대체합니다. BGM, 페이드, 워터마크, 슬라이드 설정은 그대로 사용합니다.</p>
      <input type="file" data-narration-audio-input accept="audio/mpeg,audio/wav,audio/x-wav,audio/mp4,.mp3,.wav,.m4a" hidden>
      <input type="file" data-narration-srt-input accept=".srt,application/x-subrip,text/plain" hidden>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px;">
        <button type="button" data-narration-audio-button style="border-radius:14px;padding:12px;font-size:13px;font-weight:900;color:#083344;background:#67e8f9;">TTS 음성 업로드</button>
        <button type="button" data-narration-srt-button style="border-radius:14px;padding:12px;font-size:13px;font-weight:900;color:#083344;background:#a5f3fc;">SRT 업로드</button>
      </div>
      <div data-narration-source-info style="margin-top:10px;border-radius:12px;background:#020617;padding:10px;font-size:12px;line-height:1.6;color:#94a3b8;">기본 StoryMaker 음성 + SRT 사용</div>
    `;

    const audioInput = card.querySelector('[data-narration-audio-input]');
    const srtInput = card.querySelector('[data-narration-srt-input]');
    card.querySelector('[data-narration-audio-button]').addEventListener('click', () => audioInput.click());
    card.querySelector('[data-narration-srt-button]').addEventListener('click', () => srtInput.click());
    card.querySelector('[data-narration-reset]').addEventListener('click', () => reset(card));

    audioInput.addEventListener('change', () => {
      const file = audioInput.files?.[0];
      if (!file) return;
      const ext = (file.name.split('.').pop() || '').toLowerCase();
      if (!['mp3', 'wav', 'm4a'].includes(ext)) {
        window.alert('TTS 음성은 MP3, WAV, M4A 파일만 사용할 수 있습니다.');
        audioInput.value = '';
        return;
      }
      STATE.audioFile = file;
      updateInfo(card);
    });

    srtInput.addEventListener('change', () => {
      const file = srtInput.files?.[0];
      if (!file) return;
      if (!file.name.toLowerCase().endsWith('.srt')) {
        window.alert('자막은 SRT 파일만 사용할 수 있습니다.');
        srtInput.value = '';
        return;
      }
      STATE.srtFile = file;
      updateInfo(card);
    });

    updateInfo(card);
    return card;
  }

  function ensureCard() {
    if (document.querySelector('[data-storymaker-narration-source="1"]')) return;
    const anchor = findAnchorCard();
    if (!anchor || !anchor.parentElement) return;
    const card = buildCard();
    anchor.parentElement.insertBefore(card, anchor);
  }

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input?.url || '';
    const audio = STATE.audioFile;
    const srt = STATE.srtFile;

    if ((audio || srt) && (!audio || !srt)) {
      if (url.includes('/v1-api/slideshow/create') || url.includes('/v1-api/slideshow/run') || url.includes('127.0.0.1:18087/jobs/mp4')) {
        throw new Error('외부 나레이션은 TTS 음성과 SRT를 함께 선택해야 합니다.');
      }
    }

    if (audio && srt && init?.body instanceof FormData && (url.includes('/v1-api/slideshow/create') || url.includes('/v1-api/slideshow/run'))) {
      init.body.set('narration_audio', audio, audio.name);
      init.body.set('narration_srt', srt, srt.name);
    }

    if (audio && srt && url.includes('127.0.0.1:18087/jobs/mp4') && typeof init?.body === 'string') {
      try {
        const payload = JSON.parse(init.body);
        payload.mp3_name = audio.name;
        payload.mp3_data = await readAsDataURL(audio);
        payload.srt_name = srt.name;
        payload.srt_data = await readAsDataURL(srt);
        init.body = JSON.stringify(payload);
      } catch (error) {
        console.warn('[StoryMaker] 외부 나레이션 로컬 렌더 연결 실패', error);
        throw error;
      }
    }

    return originalFetch(input, init);
  };

  const observer = new MutationObserver(() => ensureCard());
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener('popstate', () => setTimeout(ensureCard, 50));
  setInterval(ensureCard, 1200);
  setTimeout(ensureCard, 300);
})();
