import { c as renderBrowserShortform } from './assets/staged-renderer-v1-20260723.js';

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const jobId = params.get('job_id') || sessionStorage.getItem('storymaker_v1_staged_job_id') || '';
let jobData = null;
let settings = {};
let imageFiles = [];
let audioBlob = null;
let subtitleLines = [];
let subtitleCues = [];
let abortController = null;
let progressTimer = null;
let visualProgress = 0;
let previewImageUrls = [];
let lastPreviewFrameIndex = -1;

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

function refreshPreviewImageUrls() {
  previewImageUrls.forEach((url) => URL.revokeObjectURL(url));
  previewImageUrls = imageFiles.map((file) => URL.createObjectURL(file));
  lastPreviewFrameIndex = -1;
}

function updateLivePreviewFrame(frameIndex) {
  if (!$('livePreviewImage') || !previewImageUrls.length) return;
  const safeIndex = Math.max(0, Math.min(previewImageUrls.length - 1, frameIndex));
  if (safeIndex === lastPreviewFrameIndex) return;
  lastPreviewFrameIndex = safeIndex;
  $('livePreviewImage').src = previewImageUrls[safeIndex];
}

function getEffectiveRenderSettings() {
  const mode = $('renderMode')?.value || 'fast';
  const resolution = $('renderResolution')?.value || (mode === 'fast' ? '720x1280' : '1080x1920');
  const [rawWidth, rawHeight] = resolution.split('x').map(Number);
  const selectedFps = Number($('renderFps')?.value || (mode === 'fast' ? 18 : 24));
  return {
    fastDraft: mode === 'fast',
    width: Math.max(360, rawWidth || 720),
    height: Math.max(640, rawHeight || 1280),
    fps: Math.max(12, Math.min(30, selectedFps)),
    imageSeconds: Number(settings.image_sec || 4.5),
    transitionSeconds: Number(settings.transition_sec || 2),
    zoomIntensity: Number(settings.zoom_intensity || 0.004),
    subtitleEnabled: settings.subtitle_enabled !== false
  };
}

function setRunButton(text, disabled) {
  if (!$('run')) return;
  $('run').textContent = text;
  $('run').disabled = !!disabled;
}

function renderResultPlaceholder(message = 'MP4 제작이 끝나면 이 영역에 저장본 미리보기가 자동으로 표시됩니다.') {
  $('result').innerHTML = `<div class="result-empty"><strong>완료 결과 미리보기</strong><p class="muted" style="margin:10px 0 0">${message}</p></div>`;
}

function renderResultError(message) {
  $('result').innerHTML = `<div class="result-error"><strong>제작 실패</strong><p class="muted" style="margin:10px 0 0">${message}</p></div>`;
}

function renderResultPreview(serverUrl, localUrl = '') {
  const cacheSafeUrl = `${serverUrl}${serverUrl.includes('?') ? '&' : '?'}ts=${Date.now()}`;
  const previewUrl = localUrl || cacheSafeUrl;
  const image = $('livePreviewImage');
  const video = $('livePreviewVideo');
  if (image) image.hidden = true;
  if (video) {
    video.src = previewUrl;
    video.hidden = false;
    video.load();
  }
  $('previewOverlay')?.classList.add('is-hidden');
  $('result').hidden = false;
  $('result').innerHTML = `<div class="result-actions" style="justify-content:center"><a class="btn primary" href="${cacheSafeUrl}" target="_blank" rel="noopener">저장본 열기</a><a class="btn secondary" href="${previewUrl}" download="staged_${jobId}.mp4">MP4 다운로드</a></div>`;
}

function renderImageGrid(images) {
  const image = $('livePreviewImage');
  if (image && images.length) {
    image.src = `/v1-api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/staged-image/0`;
    image.hidden = false;
  }
}

function updatePhase(phase) {
  const order = ['Prepare', 'Render', 'Upload', 'Done'];
  const activeIndex = { prepare: 0, render: 1, upload: 2, done: 3 }[phase] ?? 0;
  order.forEach((name, idx) => {
    const el = $(`phase${name}`);
    if (!el) return;
    el.classList.remove('is-active', 'is-done');
    if (idx < activeIndex) el.classList.add('is-done');
    if (idx === activeIndex) el.classList.add('is-active');
  });
}

function setProgress(percent, stage, detail = '') {
  const safe = Math.max(0, Math.min(100, Number(percent || 0)));
  visualProgress = safe;
  $('progressFill').style.width = `${safe}%`;
  $('percent').textContent = `${Math.round(safe)}%`;
  $('stage').textContent = stage || '진행 중';
  $('detail').textContent = detail || '';
  if ($('previewStage')) $('previewStage').textContent = stage || '진행 중';
  if ($('previewDetail')) $('previewDetail').textContent = detail || '';
}

function startProgressAnimation(start = 31, end = 94) {
  stopProgressAnimation();
  visualProgress = start;
  progressTimer = setInterval(() => {
    if (visualProgress >= end) return;
    const gap = end - visualProgress;
    const step = gap > 30 ? 3 : gap > 15 ? 2 : 1;
    visualProgress = Math.min(end, visualProgress + step);
    setProgress(visualProgress, 'MP4 제작 중', '프레임을 렌더링하고 있습니다.');
  }, 850);
}

function stopProgressAnimation(forcePercent = null) {
  if (progressTimer) {
    clearInterval(progressTimer);
    progressTimer = null;
  }
  if (typeof forcePercent === 'number') visualProgress = forcePercent;
}

async function waitForSavedMp4Url() {
  const fallback = `/v1-api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/files/mp4`;
  const started = Date.now();
  while (Date.now() - started < 20000) {
    try {
      const res = await fetch(`/v1-api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}`, { credentials: 'include', cache: 'no-store' });
      const payload = await res.json().catch(() => ({}));
      if (res.ok) {
        const data = payload.data || payload || {};
        const media = data.media || {};
        if (media.mp4_url) return media.mp4_url;
      }
    } catch (_) {}
    await sleep(1200);
  }
  return fallback;
}

function normalizeUrl(url='') {
  if (!url) return '';
  if (url.startsWith('/api/')) return '/v1-api/' + url.slice('/api/'.length);
  return url;
}

async function fetchBlob(url) {
  const res = await fetch(normalizeUrl(url), { credentials: 'include', cache: 'no-store' });
  if (!res.ok) throw new Error(`파일 불러오기 실패: ${res.status}`);
  return await res.blob();
}

async function fetchText(url) {
  const res = await fetch(normalizeUrl(url), { credentials: 'include', cache: 'no-store' });
  if (!res.ok) throw new Error(`텍스트 불러오기 실패: ${res.status}`);
  return await res.text();
}

function srtTimeToSeconds(value = '') {
  const match = String(value).trim().match(/(\d{2}):(\d{2}):(\d{2})[,.](\d{3})/);
  if (!match) return 0;
  return Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3]) + Number(match[4]) / 1000;
}

function parseSrtCues(text = '') {
  return String(text).replace(/\r/g, '').split(/\n{2,}/).map((block) => {
    const lines = block.split('\n').map((line) => line.trim()).filter(Boolean);
    const timeLine = lines.find((line) => line.includes('-->')) || '';
    const [startText = '', endText = ''] = timeLine.split('-->').map((value) => value.trim());
    const cueText = lines.filter((line) => !/^\d+$/.test(line) && !line.includes('-->')).join(' ').replace(/<[^>]+>/g, '').trim();
    return { start: srtTimeToSeconds(startText), end: srtTimeToSeconds(endText), text: cueText };
  }).filter((cue) => cue.text && cue.end > cue.start);
}

async function load() {
  if (!jobId) throw new Error('현재 단계별 작업 ID가 없습니다.');
  const res = await fetch(`/v1-api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}`, { credentials: 'include', cache: 'no-store' });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || '작업 조회 실패');
  jobData = payload.data || payload;
  try { settings = JSON.parse(sessionStorage.getItem('storymaker_v1_staged_stage5_settings') || localStorage.getItem('storymaker_v1_staged_stage5_settings') || '{}'); } catch { settings = {}; }
  if ($('renderResolution') && settings.resolution) $('renderResolution').value = settings.resolution;
  if ($('renderFps') && settings.fps) $('renderFps').value = String(settings.fps);
  if ($('renderMode')) $('renderMode').value = settings.fast_draft === false ? 'quality' : 'fast';

  const images = Array.isArray(jobData.images) ? jobData.images : [];
  renderImageGrid(images);
  renderResultPlaceholder();
  updatePhase('prepare');
  setRunButton('현재 작업으로 MP4 제작', true);

  const media = jobData.media || {};
  const renderSettings = getEffectiveRenderSettings();
  const { width, height, fps } = renderSettings;
  $('settings').innerHTML = `<p>이미지당 ${renderSettings.imageSeconds}초 · 전환 ${renderSettings.transitionSeconds}초</p><p>자막 ${renderSettings.subtitleEnabled ? '사용' : '사용 안 함'}</p>`;
  $('caps').innerHTML = `<span class="pill">WebGPU ${navigator.gpu ? '가능' : '미지원'}</span><span class="pill">H.264 ${'VideoEncoder' in window ? '가능' : '미지원'}</span><span class="pill">AAC ${'AudioEncoder' in window ? '가능' : '미지원'}</span>`;

  setProgress(5, '미디어 불러오는 중', `이미지 ${images.length}장과 완성 MP3를 준비합니다.`);
  imageFiles = [];
  const thumbnailUrl = media.thumbnail_url || `/v1-api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/files/thumbnail`;
  try {
    const thumbnailBlob = await fetchBlob(thumbnailUrl);
    if (thumbnailBlob && thumbnailBlob.size) {
      imageFiles.push(new File([thumbnailBlob], '00_thumbnail.jpg', { type: thumbnailBlob.type || 'image/jpeg' }));
      setProgress(8, '썸네일 준비 중', '완성 썸네일을 MP4 첫 장면으로 추가했습니다.');
    }
  } catch (error) {
    console.warn('[STAGED-MP4] 썸네일 첫 장면 추가 실패, 원본 이미지로 계속 진행합니다.', error);
  }
  for (let i = 0; i < images.length; i++) {
    const blob = await fetchBlob(`/v1-api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/staged-image/${i}`);
    imageFiles.push(new File([blob], images[i].stored_name || `image_${i + 1}.jpg`, { type: blob.type || 'image/jpeg' }));
    setProgress(5 + Math.round(((i + 1) / Math.max(1, images.length)) * 20), '이미지 준비 중', `${i + 1}/${images.length}`);
  }
  const mp3Url = media.mp3_url || `/v1-api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/files/mp3`;
  audioBlob = await fetchBlob(mp3Url);
  subtitleLines = [];
  subtitleCues = [];
  if (settings.subtitle_enabled !== false) {
    try {
      const srtUrl = media.srt_url || `/v1-api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/files/srt`;
      subtitleCues = parseSrtCues(await fetchText(srtUrl));
      subtitleLines = subtitleCues.map((cue) => cue.text);
    } catch (error) {
      console.warn('[STAGED-MP4] SRT 불러오기 실패', error);
    }
  }
  if (!imageFiles.length) throw new Error('렌더링할 이미지가 없습니다.');
  if (!audioBlob || !audioBlob.size) throw new Error('완성 MP3를 불러오지 못했습니다.');
  refreshPreviewImageUrls();
  updateLivePreviewFrame(0);
  setProgress(30, '제작 준비 완료', `이미지 ${imageFiles.length}장 · MP3 ${(audioBlob.size / 1024 / 1024).toFixed(2)}MB · 자막 ${subtitleLines.length}줄`);
  setRunButton('현재 작업으로 MP4 제작', false);
}

async function run() {
  if (!jobData || !imageFiles.length || !audioBlob) {
    setProgress(0, '제작 시작 불가', '현재 작업의 이미지 또는 완성 MP3가 준비되지 않았습니다.');
    return;
  }

  setRunButton('MP4 제작 중...', true);
  renderResultPlaceholder('렌더링이 완료되면 저장본 미리보기가 여기에 자동으로 표시됩니다.');
  updatePhase('render');
  setProgress(31, 'MP4 제작 시작', '브라우저 렌더링 엔진을 시작하고 있습니다.');
  startProgressAnimation(31, 93);
  abortController = new AbortController();

  try {
    const { width, height, fps } = getEffectiveRenderSettings();

    const result = await renderBrowserShortform({
      audioBlob,
      imageFiles,
      title: settings.title || settings.brand || jobData.persona?.business_name || 'StoryMaker',
      caption: '',
      eyebrow: settings.eyebrow || '스토리메이커 연구소',
      businessName: settings.brand || jobData.persona?.business_name || '',
      businessPhone: settings.phone || jobData.persona?.phone || '',
      businessNameFontSize: Math.min(Number(settings.brand_size || 34), String(settings.brand || '').length > 10 ? 30 : 34),
      businessPhoneFontSize: Math.min(Number(settings.phone_size || 30), 30),
      bottomMargin: Number(settings.margin_bottom || 80),
      scriptLines: subtitleLines,
      subtitleCues,
      subtitleStartSeconds: 0,
      subtitleDurationSeconds: 120,
      subtitleFontSize: Math.max(24, Number(settings.subtitle_size || 30)),
      width,
      height,
      fps,
      maxDurationSeconds: 120,
      perfScreen: 'staged-production',
      signal: abortController.signal,
      onProgress: (p) => {
        stopProgressAnimation();
        const renderPercent = Math.min(94, 31 + Number(p.percent || 0) * 0.63);
        setProgress(renderPercent, p.stage || 'MP4 제작 중', p.detail || '프레임을 렌더링하고 있습니다.');
        const frameIndex = Math.max(0, Math.min(imageFiles.length - 1, Math.floor((Number(p.percent || 0) / 100) * imageFiles.length)));
        updateLivePreviewFrame(frameIndex);
      }
    });

    stopProgressAnimation(94);
    updatePhase('upload');
    setProgress(96, 'MP4 서버 저장 중', '보관함, 작업 데이터, DB 동기화를 진행합니다.');

    const form = new FormData();
    form.append('mp4', result.mp4Blob, `staged_${jobId}.mp4`);
    form.append('provider', 'browser-staged');
    form.append('duration_seconds', String(Number(result.durationSeconds || 0)));

    const upload = await fetch(`/v1-api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/browser-shortform`, {
      method: 'POST',
      credentials: 'include',
      body: form
    });

    const saved = await upload.json().catch(() => ({}));
    if (!upload.ok) throw new Error(saved.detail || 'MP4 저장 실패');

    setProgress(99, '저장 완료 확인', '완료 미리보기를 바로 준비하고 있습니다.');

    const localUrl = URL.createObjectURL(result.mp4Blob);
    const savedData = saved.data || saved || {};
    const savedMedia = savedData.media || {};
    const serverUrl = savedMedia.mp4_url || savedMedia.preview_mp4_url || savedData.mp4_url || `/v1-api/mobile/one-shot/jobs/${encodeURIComponent(jobId)}/files/mp4`;

    updatePhase('done');
    setProgress(100, 'MP4 제작·저장 완료', '현재 작업, 보관함, DB 동기화까지 완료되었습니다.');
    renderResultPreview(serverUrl, localUrl);
    setRunButton('다시 제작하기', false);
  } catch (error) {
    stopProgressAnimation();
    updatePhase('prepare');
    setProgress(Math.max(0, visualProgress || 0), '제작 실패', error?.message || String(error));
    renderResultError(error?.message || String(error));
    setRunButton('현재 작업으로 MP4 제작', false);
  }
}

['renderMode','renderResolution','renderFps'].forEach((id) => $(id)?.addEventListener('change', () => {
  if (id === 'renderMode') {
    const fast = $('renderMode').value === 'fast';
    $('renderResolution').value = fast ? '720x1280' : '1080x1920';
    $('renderFps').value = fast ? '18' : '24';
  }
  const renderSettings = getEffectiveRenderSettings();
  $('settings').innerHTML = `<p>${renderSettings.width}×${renderSettings.height} · ${renderSettings.fps} FPS</p><p>이미지당 ${renderSettings.imageSeconds}초 · 전환 ${renderSettings.transitionSeconds}초</p><p>자막 ${renderSettings.subtitleEnabled ? '사용' : '사용 안 함'}</p>`;
}));

$('run').addEventListener('click', run);
$('back').addEventListener('click', () => { location.href = '/static/v1/staged-production.html'; });
load().catch((error) => {
  setProgress(0, '준비 실패', error.message || String(error));
  renderResultError(error.message || String(error));
  setRunButton('현재 작업으로 MP4 제작', true);
});
