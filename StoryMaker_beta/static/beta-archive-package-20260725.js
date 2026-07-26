(() => {
  'use strict';

  const list = document.getElementById('beta-archive-list');
  const detail = document.getElementById('beta-archive-detail');
  const modal = document.getElementById('beta-archive-modal');
  const search = document.getElementById('beta-archive-search');
  const refresh = document.getElementById('beta-archive-refresh');
  const filter = document.getElementById('beta-archive-filter');
  const sort = document.getElementById('beta-archive-sort');
  const statTotal = document.getElementById('archive-stat-total');
  const statCompleted = document.getElementById('archive-stat-completed');
  const statMp3 = document.getElementById('archive-stat-mp3');
  const statMp4 = document.getElementById('archive-stat-mp4');
  let jobs = [];

  const esc = (value) => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

  async function req(url, options = {}) {
    const response = await fetch(url, { cache: 'no-store', ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    return data;
  }

  function ensureDownloadProgress() {
    let layer = document.getElementById('beta-download-progress');
    if (layer) return layer;
    layer = document.createElement('div');
    layer.id = 'beta-download-progress';
    layer.className = 'download-progress-layer';
    layer.hidden = true;
    layer.innerHTML = `<div class="download-progress-card" role="status" aria-live="polite">
      <div class="download-wave" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div>
      <strong id="beta-download-title">다운로드 패키지를 준비하고 있습니다.</strong>
      <p id="beta-download-status">이미지와 미디어를 확인하는 중...</p>
      <div class="download-progress-track"><span id="beta-download-bar"></span></div>
      <div id="beta-download-percent" class="download-progress-percent">0%</div>
    </div>`;
    document.body.appendChild(layer);
    return layer;
  }

  function packageFilename(response, fallback) {
    const disposition = response.headers.get('content-disposition') || '';
    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    if (encoded) {
      try { return decodeURIComponent(encoded); } catch (_) {}
    }
    const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1];
    return plain || fallback;
  }

  async function downloadPackage(jobId) {
    const layer = ensureDownloadProgress();
    const title = layer.querySelector('#beta-download-title');
    const status = layer.querySelector('#beta-download-status');
    const bar = layer.querySelector('#beta-download-bar');
    const percent = layer.querySelector('#beta-download-percent');
    const stages = [
      '업로드 이미지를 확인하는 중...',
      '워터마크·테두리·이미지 효과를 적용하는 중...',
      'MP3·SRT·썸네일·MP4를 모으는 중...',
      'ZIP 파일로 압축하는 중...',
      '다운로드를 준비하는 중...'
    ];
    let stageIndex = 0;
    layer.hidden = false;
    document.body.classList.add('download-progress-open');
    title.textContent = 'StoryMaker Beta 결과를 묶고 있습니다.';
    status.textContent = stages[0];
    bar.style.width = '4%';
    percent.textContent = '준비 중';
    const stageTimer = setInterval(() => {
      stageIndex = Math.min(stages.length - 1, stageIndex + 1);
      status.textContent = stages[stageIndex];
      bar.style.width = `${Math.min(68, 10 + stageIndex * 14)}%`;
    }, 1500);

    try {
      const response = await fetch(`/beta-api/browser/jobs/${encodeURIComponent(jobId)}/download-package`, { cache: 'no-store' });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${response.status}`);
      }
      clearInterval(stageTimer);
      const total = Number(response.headers.get('content-length') || 0);
      const reader = response.body?.getReader();
      const chunks = [];
      let received = 0;
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          chunks.push(value);
          received += value.byteLength;
          if (total > 0) {
            const valuePercent = Math.max(70, Math.min(99, Math.round(received / total * 100)));
            bar.style.width = `${valuePercent}%`;
            percent.textContent = `${valuePercent}%`;
            status.textContent = '완성된 ZIP 파일을 브라우저로 전송하는 중...';
          }
        }
      }
      const blob = reader ? new Blob(chunks, { type: 'application/zip' }) : await response.blob();
      const filename = packageFilename(response, `StoryMaker_Beta_${jobId}.zip`);
      const href = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = href;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(href), 30000);
      bar.style.width = '100%';
      percent.textContent = '100%';
      title.textContent = '다운로드 준비가 끝났습니다.';
      status.textContent = '워터마크 이미지와 MP3·SRT·썸네일·MP4를 한 파일로 받습니다.';
      setTimeout(() => {
        layer.hidden = true;
        document.body.classList.remove('download-progress-open');
      }, 1500);
    } catch (error) {
      clearInterval(stageTimer);
      title.textContent = '다운로드 패키지 생성에 실패했습니다.';
      status.textContent = error.message;
      bar.style.width = '0%';
      percent.textContent = '실패';
      setTimeout(() => {
        layer.hidden = true;
        document.body.classList.remove('download-progress-open');
      }, 2600);
    }
  }

  function ensureCopyToast() {
    let toast = document.getElementById('beta-channel-copy-toast');
    if (toast) return toast;
    toast = document.createElement('div');
    toast.id = 'beta-channel-copy-toast';
    toast.className = 'channel-copy-toast';
    toast.hidden = true;
    document.body.appendChild(toast);
    return toast;
  }

  function showCopyToast(message, failed = false) {
    const toast = ensureCopyToast();
    toast.textContent = message;
    toast.classList.toggle('failed', failed);
    toast.hidden = false;
    clearTimeout(showCopyToast.timer);
    showCopyToast.timer = setTimeout(() => { toast.hidden = true; }, 1800);
  }

  function plainToRichHtml(value, key = '') {
    const lines = String(value || '').replace(/\r\n?/g, '\n').split('\n');
    let previousBlank = true;
    return lines.map((raw) => {
      const line = raw.trim();
      if (!line) { previousBlank = true; return ''; }
      const safe = esc(line).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      if (/^[-_=·•─━]{3,}$/.test(line)) { previousBlank = true; return '<hr>'; }
      if (['본문', '블로그 본문', '추천 제목 5개', '추천 제목', '해시태그', '상담 안내'].includes(line)) {
        previousBlank = false;
        return `${['본문', '블로그 본문'].includes(line) ? '<hr>' : ''}<h2>${safe}</h2>`;
      }
      if (/^(여자|남자)\s*:/.test(line) && /^PODCAST_/.test(key)) {
        previousBlank = false;
        return `<p class="rich-dialogue">${safe.replace(/^([^:]+:)/, '<strong>$1</strong>')}</p>`;
      }
      const heading = previousBlank && line.length <= 42 && !/[.!?。]$/.test(line) && !/^[-•#]/.test(line) && !/^PODCAST_/.test(key);
      previousBlank = false;
      return heading ? `<h3>${safe}</h3>` : `<p>${safe}</p>`;
    }).join('');
  }

  function channelHtml(channel, key) {
    return String(channel?.html || '').trim() || plainToRichHtml(channel?.content || '', key);
  }

  async function copyRichContent(text, htmlValue) {
    const plain = String(text || '');
    const rich = String(htmlValue || '');
    if (!plain.trim()) throw new Error('복사할 콘텐츠가 없습니다.');
    if (navigator.clipboard?.write && window.ClipboardItem && rich.trim()) {
      try {
        await navigator.clipboard.write([new ClipboardItem({
          'text/html': new Blob([rich], { type: 'text/html' }),
          'text/plain': new Blob([plain], { type: 'text/plain' })
        })]);
        return;
      } catch (_) {}
    }
    await copyText(plain);
  }

  async function copyText(text) {
    const value = String(text || '');
    if (!value.trim()) throw new Error('복사할 콘텐츠가 없습니다.');
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(value);
        return;
      } catch (_) {}
    }
    const textarea = document.createElement('textarea');
    textarea.value = value;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    textarea.style.top = '0';
    document.body.appendChild(textarea);
    textarea.select();
    textarea.setSelectionRange(0, textarea.value.length);
    const copied = document.execCommand('copy');
    textarea.remove();
    if (!copied) throw new Error('브라우저 복사 권한을 확인해 주세요.');
  }

  async function selectAndCopyChannel(button, channels) {
    const key = String(button.dataset.channel || '');
    const item = channels[key] || {};
    const content = String(item.content || '');
    const label = String(item.label || key || '콘텐츠');
    detail.querySelectorAll('[data-channel]').forEach((tab) => tab.classList.toggle('active', tab === button));
    const contentBox = document.getElementById('archive-channel-content');
    if (contentBox) contentBox.textContent = content;
    const original = button.dataset.originalLabel || button.textContent.trim();
    button.dataset.originalLabel = original;
    try {
      await copyText(content);
      button.classList.add('copied');
      button.textContent = `${original} 복사됨`;
      showCopyToast(`${label} 콘텐츠를 복사했습니다. 바로 붙여넣어 사용하세요.`);
    } catch (error) {
      showCopyToast(`복사 실패: ${error.message}`, true);
    } finally {
      setTimeout(() => {
        button.classList.remove('copied');
        button.textContent = original;
      }, 1400);
    }
  }

  function flags(job) {
    const assets = job.assets || {};
    return {
      sns: Object.keys(job.content?.channels || {}).length === 8,
      images: Boolean(assets.images?.length),
      mp3: Boolean(assets.browser_audio || assets.audio),
      srt: Boolean(assets.subtitle),
      thumb: Boolean(assets.thumbnail),
      mp4: Boolean(assets.browser_video || assets.video)
    };
  }

  const badge = (label, ready) => `<span class="asset-badge ${ready ? 'ready' : 'waiting'}">${esc(label)}</span>`;

  function renderStats() {
    const allFlags = jobs.map(flags);
    statTotal.textContent = String(jobs.length);
    statCompleted.textContent = String(jobs.filter((job) => String(job.status || '').toLowerCase() === 'completed').length);
    statMp3.textContent = String(allFlags.filter((item) => item.mp3).length);
    statMp4.textContent = String(allFlags.filter((item) => item.mp4).length);
  }

  function formatDate(value) {
    const raw = String(value || '');
    const date = new Date(raw);
    if (Number.isNaN(date.getTime())) return raw || '날짜 미등록';
    return new Intl.DateTimeFormat('ko-KR', { year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' }).format(date);
  }

  function renderList() {
    const query = String(search?.value || '').trim().toLowerCase();
    const mode = filter?.value || 'all';
    let filtered = jobs.filter((job) => {
      const f = flags(job);
      const queryMatch = !query || [job.title, job.beta_job_id, job.business?.name, job.business?.region]
        .some((value) => String(value || '').toLowerCase().includes(query));
      if (!queryMatch) return false;
      if (mode === 'completed') return String(job.status || '').toLowerCase() === 'completed';
      if (mode === 'working') return String(job.status || '').toLowerCase() !== 'completed';
      if (mode === 'media') return f.mp3 || f.mp4 || f.thumb;
      return true;
    });
    const sortMode = sort?.value || 'newest';
    filtered = [...filtered].sort((a, b) => {
      if (sortMode === 'oldest') return String(a.created_at || '').localeCompare(String(b.created_at || ''));
      if (sortMode === 'title') return String(a.title || '').localeCompare(String(b.title || ''), 'ko');
      return String(b.created_at || '').localeCompare(String(a.created_at || ''));
    });
    renderStats();
    if (!filtered.length) {
      list.className = 'empty';
      list.textContent = jobs.length ? '검색 결과가 없습니다.' : 'Beta 제작 결과가 아직 없습니다.';
      return;
    }
    list.className = 'archive-grid';
    list.innerHTML = filtered.map((job) => {
      const f = flags(job);
      const firstImage = job.assets?.images?.length ? `/beta-api/browser/jobs/${encodeURIComponent(job.beta_job_id)}/image/1` : '';
      const thumb = job.assets?.thumbnail ? `/beta-api/jobs/${encodeURIComponent(job.beta_job_id)}/file/thumbnail` : firstImage;
      const assetButton = (label, ready) => `<span class="asset-button ${ready ? 'ready' : 'waiting'}">${esc(label)}</span>`;
      return `<article class="archive-card">
        ${thumb ? `<button type="button" class="archive-thumb-button" data-open-job="${esc(job.beta_job_id)}"><img class="archive-thumb" loading="lazy" src="${thumb}" alt="미리보기"></button>` : `<button type="button" class="archive-thumb-placeholder" data-open-job="${esc(job.beta_job_id)}">미리보기 없음</button>`}
        <div class="archive-main">
          <div class="card-head"><button type="button" class="archive-title-button" data-open-job="${esc(job.beta_job_id)}">${esc(job.title || 'Beta 제작')}</button><span class="status-pill">${esc(job.status || 'created')}</span></div>
          <p class="card-summary">${esc(job.business?.name || '업체 미등록')} · ${esc(job.business?.region || '지역 미등록')} · 이미지 ${job.assets?.images?.length || 0}장</p>
          <div class="archive-date">${esc(formatDate(job.created_at))}</div>
          <div class="job-id">${esc(job.beta_job_id)}</div>
        </div>
        <div class="archive-assets">
          ${assetButton('SNS', f.sns)}${assetButton('이미지', f.images)}${assetButton('MP3', f.mp3)}${assetButton('SRT', f.srt)}${assetButton('썸네일', f.thumb)}${assetButton('MP4', f.mp4)}
          <div class="delete-wrap">
            <button type="button" class="delete-button" data-delete-job="${esc(job.beta_job_id)}">삭제</button>
            <div class="delete-confirm" data-confirm-for="${esc(job.beta_job_id)}" hidden><span>완전히 삭제할까요?</span><button type="button" data-delete-yes="${esc(job.beta_job_id)}">예</button><button type="button" data-delete-no="${esc(job.beta_job_id)}">아니오</button></div>
          </div>
        </div>
      </article>`;
    }).join('');
    list.querySelectorAll('[data-open-job]').forEach((button) => button.addEventListener('click', () => openDetail(button.dataset.openJob)));
    list.querySelectorAll('[data-delete-job]').forEach((button) => button.addEventListener('click', () => {
      list.querySelectorAll('.delete-confirm').forEach((box) => { if (box.dataset.confirmFor !== button.dataset.deleteJob) box.hidden = true; });
      const box = list.querySelector(`[data-confirm-for="${CSS.escape(button.dataset.deleteJob)}"]`);
      if (!box) return;
      box.hidden = !box.hidden;
      if (!box.hidden) {
        const yesButton = box.querySelector('[data-delete-yes]');
        requestAnimationFrame(() => yesButton?.focus({ preventScroll: true }));
      }
    }));
    list.querySelectorAll('[data-delete-no]').forEach((button) => button.addEventListener('click', () => {
      const box = button.closest('.delete-confirm'); if (box) box.hidden = true;
    }));
    list.querySelectorAll('[data-delete-yes]').forEach((button) => button.addEventListener('click', () => deleteJob(button.dataset.deleteYes, button)));
  }

  async function deleteJob(jobId, button) {
    if (!jobId || button.disabled) return;
    button.disabled = true;
    button.textContent = '삭제 중';
    try {
      await req(`/beta-api/jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
      jobs = jobs.filter((job) => job.beta_job_id !== jobId);
      renderList();
    } catch (error) {
      button.disabled = false;
      button.textContent = '예';
      alert(`삭제 실패: ${error.message}`);
    }
  }

  async function openDetail(jobId) {
    modal.hidden = false;
    document.body.classList.add('archive-modal-open');
    detail.innerHTML = '<div class="empty">상세 자료를 불러오는 중...</div>';
    try {
      const job = (await req(`/beta-api/jobs/${encodeURIComponent(jobId)}`)).job || {};
      const assets = job.assets || {};
      const channels = job.content?.channels || {};
      const order = job.content?.channel_order || Object.keys(channels);
      const first = order[0] || '';
      const audioUrl = assets.browser_audio ? `/beta-api/browser/jobs/${encodeURIComponent(jobId)}/file/mp3` : assets.audio ? `/beta-api/jobs/${encodeURIComponent(jobId)}/file/audio` : '';
      const videoUrl = assets.browser_video ? `/beta-api/browser/jobs/${encodeURIComponent(jobId)}/file/mp4` : assets.video ? `/beta-api/jobs/${encodeURIComponent(jobId)}/file/video` : '';
      const subtitleUrl = assets.subtitle ? `/beta-api/jobs/${encodeURIComponent(jobId)}/file/subtitle` : '';
      const images = assets.images || [];
      const thumbnailUrl = assets.thumbnail ? `/beta-api/jobs/${encodeURIComponent(jobId)}/file/thumbnail` : (images.length ? `/beta-api/browser/jobs/${encodeURIComponent(jobId)}/image/1` : '');
      detail.innerHTML = `<div class="detail-head"><div><div class="badge">BETA ARCHIVE DETAIL</div><h2>${esc(job.title || 'Beta 제작')}</h2><p>${esc(job.business?.name || '')} · ${esc(job.business?.region || '')} · ${esc(job.business?.service || '')}</p></div><button id="archive-detail-close" type="button">닫기</button></div>
        <section class="detail-block"><div class="channel-title-row"><h3>SNS 8채널</h3><span>탭을 누르면 해당 콘텐츠가 바로 복사됩니다.</span></div><div class="channel-tabs">${order.map((key, index) => `<button type="button" class="channel-tab${index === 0 ? ' active' : ''}" data-channel="${esc(key)}">${esc(channels[key]?.label || key)}</button>`).join('')}</div><div id="archive-channel-content" class="channel-content rich-channel-content">${channelHtml(channels[first], first)}</div></section>
        <div class="archive-sections archive-sections-all">
          <div id="archive-media-all" class="archive-media-all">
            <section class="archive-section-static media-preview-card"><h3>업로드 이미지 ${images.length}장</h3><div class="image-grid">${images.map((_, index) => `<a href="/beta-api/browser/jobs/${encodeURIComponent(jobId)}/image/${index + 1}" target="_blank"><img loading="lazy" src="/beta-api/browser/jobs/${encodeURIComponent(jobId)}/image/${index + 1}" alt="이미지 ${index + 1}"></a>`).join('') || '<div class="empty-mini">이미지가 없습니다.</div>'}</div>${images.length ? `<div class="media-download-row"><button type="button" class="download-link package-download-button" data-download-package="${esc(jobId)}">가공 이미지 포함 ZIP 다운로드</button></div>` : ''}</section>
            <section class="archive-section-static media-preview-card"><h3>팟캐스트 MP3</h3>${audioUrl ? `<audio class="audio-preview" controls preload="metadata" src="${audioUrl}"></audio><div class="media-download-row"><a class="download-link" href="${audioUrl}" target="_blank" download>MP3 다운로드</a></div>` : '<div class="empty-mini">MP3가 없습니다.</div>'}</section>
            <section class="archive-section-static media-preview-card"><h3>썸네일</h3>${thumbnailUrl ? `<a href="${thumbnailUrl}" target="_blank"><img class="thumbnail-preview" loading="lazy" src="${thumbnailUrl}" alt="썸네일"></a><div class="media-download-row"><a class="download-link" href="${thumbnailUrl}" download>썸네일 다운로드</a></div>` : '<div class="empty-mini">썸네일이 없습니다.</div>'}</section>
            <section class="archive-section-static media-preview-card"><h3>최종 MP4</h3>${videoUrl ? `<video class="mp4-preview" controls preload="metadata" playsinline src="${videoUrl}"></video><div class="media-download-row"><a class="download-link" href="${videoUrl}" target="_blank">MP4 크게 보기</a><a class="download-link" href="${videoUrl}" download>MP4 다운로드</a></div>` : '<div class="empty-mini">MP4가 없습니다.</div>'}</section>
          </div>
          <div class="archive-package-row"><button type="button" class="package-main-button" data-download-package="${esc(jobId)}">이미지 · MP3 · SRT · 썸네일 · MP4 전체 ZIP 다운로드</button></div>
        </div>`;
      document.getElementById('archive-detail-close')?.addEventListener('click', closeDetail);
      detail.querySelectorAll('[data-download-package]').forEach((button) => button.addEventListener('click', () => downloadPackage(button.dataset.downloadPackage)));
      detail.querySelectorAll('[data-channel]').forEach((button) => button.addEventListener('click', () => selectAndCopyChannel(button, channels)));
    } catch (error) {
      detail.innerHTML = `<div class="empty">상세 조회 실패: ${esc(error.message)}</div>`;
    }
  }

  function closeDetail() {
    modal.hidden = true;
    document.body.classList.remove('archive-modal-open');
    detail.innerHTML = '';
  }

  modal?.addEventListener('click', (event) => {
    if (event.target === modal) closeDetail();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !modal.hidden) closeDetail();
  });

  async function load() {
    list.className = 'empty'; list.textContent = '불러오는 중...';
    try {
      const summaries = (await req('/beta-api/jobs')).items || [];
      jobs = await Promise.all(summaries.map(async (item) => {
        try { return { ...item, ...(await req(`/beta-api/jobs/${encodeURIComponent(item.beta_job_id)}`)).job }; }
        catch (_) { return item; }
      }));
      jobs.sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
      renderList();
    } catch (error) {
      list.className = 'empty'; list.textContent = `보관함 조회 실패: ${error.message}`;
    }
  }

  search?.addEventListener('input', renderList);
  filter?.addEventListener('change', renderList);
  sort?.addEventListener('change', renderList);
  refresh?.addEventListener('click', load);
  load();
})();
