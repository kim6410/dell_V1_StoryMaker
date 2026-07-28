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
  let isAdmin = false;
  const PAGE_SIZE = 10;
  let currentPage = 1;

  function detectAdmin(user) {
    if (!user || typeof user !== 'object') return false;
    const role = String(user.role || user.user_role || user.type || '').trim().toLowerCase();
    return user.is_admin === true || user.admin === true || role === 'admin' || role === 'administrator' || role === '관리자';
  }

  async function resolveAdminAccess() {
    try {
      const response = await fetch(`/v1-api/auth/me?_=${Date.now()}`, {
        credentials: 'include',
        cache: 'no-store',
        headers: { Accept: 'application/json', 'Cache-Control': 'no-cache' }
      });
      const payload = await response.json().catch(() => ({}));
      const user = payload?.data?.user || payload?.user || payload?.data || payload;
      isAdmin = response.ok && detectAdmin(user);
    } catch (_) {
      isAdmin = false;
    }
  }

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

  function cleanCopyMarkdown(value) {
    return String(value || '')
      .replace(/\*\*(.+?)\*\*/g, '$1')
      .replace(/__(.+?)__/g, '$1')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/^#{1,6}\s+/gm, '')
      .replace(/^[-*+]\s+/gm, '')
      .replace(/^>\s+/gm, '');
  }

  function wrapCopyLine(value, maxLength = 24) {
    const words = String(value || '').trim().split(/\s+/).filter(Boolean);
    if (!words.length) return '';
    const rows = [];
    let current = '';
    words.forEach((word) => {
      if (!current) {
        current = word;
      } else if (`${current} ${word}`.length <= maxLength) {
        current += ` ${word}`;
      } else {
        rows.push(current);
        current = word;
      }
    });
    if (current) rows.push(current);
    return rows.join('\n');
  }

  function mobileCopyText(value) {
    const source = cleanCopyMarkdown(value).replace(/\r\n?/g, '\n');
    const output = [];
    source.split('\n').forEach((raw) => {
      const line = raw.trim();
      if (!line) {
        if (output.length && output[output.length - 1] !== '') output.push('');
        return;
      }
      const sentences = line.match(/[^.!?。！？]+[.!?。！？]?/g) || [line];
      sentences.forEach((sentence) => {
        const cleaned = sentence.trim();
        if (!cleaned) return;
        output.push(wrapCopyLine(cleaned, 24));
        if (/[.!?。！？]$/.test(cleaned)) output.push('');
      });
    });
    return output.join('\n').replace(/\n{3,}/g, '\n\n').trim();
  }

  function mobileCopyHtml(value) {
    return `<div style="white-space:pre-wrap;font-family:Arial,'Malgun Gothic',sans-serif;font-size:16px;line-height:1.9;color:#222;">${esc(mobileCopyText(value)).replace(/\n/g, '<br>')}</div>`;
  }

  function mobileBlogCopyHtml(value) {
    const source = String(value || '').replace(/\r\n?/g, '\n');
    let titleUsed = false;
    const blocks = [];
    source.split('\n').forEach((raw) => {
      const original = raw.trim();
      const line = cleanCopyMarkdown(original).trim();
      if (!line) return;
      if (/^[-_=·•─━]{3,}$/.test(original)) {
        blocks.push('<hr style="border:0;border-top:1px solid #d8dde6;margin:28px 0;">');
        return;
      }
      const numbered = /^\d+\./.test(line);
      const markdownHeading = /^#{1,6}\s+/.test(original);
      const mainTitle = !titleUsed && !numbered && line.length <= 52 && !/[.!?。！？]$/.test(line);
      if (mainTitle) {
        titleUsed = true;
        blocks.push(`<h2 style="margin:24px 0 20px;font-size:24px;line-height:1.55;font-weight:800;">${esc(wrapCopyLine(line, 24)).replace(/\n/g, '<br>')}</h2>`);
        return;
      }
      if (markdownHeading) {
        blocks.push(`<h3 style="margin:28px 0 16px;font-size:21px;line-height:1.6;font-weight:800;">${esc(wrapCopyLine(line, 24)).replace(/\n/g, '<br>')}</h3>`);
        return;
      }
      if (numbered) {
        blocks.push(`<p style="margin:0 0 12px;font-size:16px;line-height:1.9;">${esc(wrapCopyLine(line, 24)).replace(/\n/g, '<br>')}</p>`);
        return;
      }
      const sentences = line.match(/[^.!?。！？]+[.!?。！？]?/g) || [line];
      sentences.forEach((sentence) => {
        const cleaned = sentence.trim();
        if (!cleaned) return;
        blocks.push(`<p style="margin:0 0 18px;font-size:16px;line-height:1.9;">${esc(wrapCopyLine(cleaned, 24)).replace(/\n/g, '<br>')}</p>`);
      });
    });
    return `<article style="font-family:Arial,'Malgun Gothic',sans-serif;color:#222;background:#fff;max-width:720px;">${blocks.join('')}</article>`;
  }

  function archiveCopyPayload(item, key) {
    const plain = mobileCopyText(item?.content || '');
    if (key === 'BLOG') return { plain, rich: mobileBlogCopyHtml(item?.content || '') };
    return { plain, rich: mobileCopyHtml(item?.content || '') };
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

  async function selectAndCopyChannel(button, channels, copyNow = true) {
    const key = String(button.dataset.channel || '');
    const item = channels[key] || {};
    const label = String(item.label || key || '콘텐츠');
    detail.querySelectorAll('[data-channel]').forEach((tab) => tab.classList.toggle('active', tab === button));
    const payload = archiveCopyPayload(item, key);
    const contentBox = document.getElementById('archive-channel-content');
    if (contentBox) {
      contentBox.classList.toggle('archive-channel-dark', key !== 'BLOG');
      contentBox.innerHTML = key === 'BLOG' ? payload.rich : mobileCopyHtml(item.content || '');
    }
    const smartBar = document.getElementById('archive-smart-copy-bar');
    const smartLabel = document.getElementById('archive-smart-copy-label');
    const smartMeta = document.getElementById('archive-smart-copy-meta');
    const smartButton = document.getElementById('archive-channel-copy');
    if (smartLabel) smartLabel.textContent = label;
    if (smartMeta) smartMeta.textContent = `${payload.plain.length.toLocaleString('ko-KR')}자 · ${key === 'BLOG' ? '서식 유지 복사' : '텍스트 복사'}`;
    if (smartButton) smartButton.textContent = key === 'BLOG' ? '블로그 서식 복사' : `${label} 복사`;
    if (smartBar) {
      smartBar.classList.remove('channel-switching');
      void smartBar.offsetWidth;
      smartBar.classList.add('channel-switching');
    }
    if (!copyNow) return;
    try {
      smartButton?.classList.add('copying');
      await copyRichContent(payload.plain, payload.rich);
      smartButton?.classList.remove('copying');
      smartButton?.classList.add('copied');
      if (smartButton) smartButton.textContent = '복사 완료';
      showCopyToast(`${label} 콘텐츠를 복사했습니다. 바로 붙여넣어 사용하세요.`);
    } catch (error) {
      smartButton?.classList.remove('copying');
      smartButton?.classList.add('failed');
      if (smartButton) smartButton.textContent = '다시 시도';
      showCopyToast(`복사 실패: ${error.message}`, true);
    } finally {
      setTimeout(() => {
        smartButton?.classList.remove('copied', 'failed');
        if (smartButton) smartButton.textContent = key === 'BLOG' ? '블로그 서식 복사' : `${label} 복사`;
      }, 1500);
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
    const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    currentPage = Math.min(Math.max(1, currentPage), totalPages);
    const pageStart = (currentPage - 1) * PAGE_SIZE;
    const pageItems = filtered.slice(pageStart, pageStart + PAGE_SIZE);
    renderStats();
    if (!filtered.length) {
      list.className = 'empty';
      list.textContent = jobs.length ? '검색 결과가 없습니다.' : 'Beta 제작 결과가 아직 없습니다.';
      return;
    }
    list.className = 'archive-grid';
    list.innerHTML = pageItems.map((job) => {
      const f = flags(job);
      const firstImage = job.assets?.images?.length ? `/beta-api/browser/jobs/${encodeURIComponent(job.beta_job_id)}/image/1` : '';
      const thumb = job.assets?.thumbnail ? `/beta-api/jobs/${encodeURIComponent(job.beta_job_id)}/file/thumbnail` : firstImage;
      const assetButton = (label, ready) => `<span class="asset-button ${ready ? 'ready' : 'waiting'}">${esc(label)}</span>`;
      return `<article class="archive-card" data-card-job="${esc(job.beta_job_id)}" tabindex="0" role="button" aria-label="${esc(job.title || 'Beta 제작')} 상세보기">
        ${thumb ? `<button type="button" class="archive-thumb-button" data-open-job="${esc(job.beta_job_id)}"><img class="archive-thumb" loading="lazy" src="${thumb}" alt="미리보기"></button>` : `<button type="button" class="archive-thumb-placeholder" data-open-job="${esc(job.beta_job_id)}">미리보기 없음</button>`}
        <div class="archive-main">
          <div class="card-head"><button type="button" class="archive-title-button" data-open-job="${esc(job.beta_job_id)}">${esc(job.title || 'Beta 제작')}</button></div>
          <div class="archive-date">${esc(formatDate(job.created_at))}</div>
        </div>
        <div class="archive-assets">
          ${assetButton('SNS', f.sns)}${assetButton('이미지', f.images)}${assetButton('MP3', f.mp3)}${assetButton('썸네일', f.thumb)}${assetButton('MP4', f.mp4)}
          <div class="delete-wrap"><button type="button" class="delete-button" data-delete-job="${esc(job.beta_job_id)}" ${job.media_deleted_at ? 'disabled' : ''}>${job.media_deleted_at ? '파일 삭제됨' : '파일 삭제'}</button><div class="delete-confirm" data-confirm-for="${esc(job.beta_job_id)}" hidden><span>목록과 DB는 남기고 저장 파일만 삭제할까요?</span><button type="button" data-delete-yes="${esc(job.beta_job_id)}">예</button><button type="button" data-delete-no="${esc(job.beta_job_id)}">아니오</button></div></div>
        </div>
      </article>`;
    }).join('') + `<nav class="archive-pagination" aria-label="보관함 페이지 이동">
      <button type="button" data-page-prev ${currentPage <= 1 ? 'disabled' : ''}>이전</button>
      <span>${currentPage} / ${totalPages} 페이지 · 전체 ${filtered.length}개</span>
      <button type="button" data-page-next ${currentPage >= totalPages ? 'disabled' : ''}>다음</button>
    </nav>`;
    list.querySelector('[data-page-prev]')?.addEventListener('click', () => {
      if (currentPage <= 1) return;
      currentPage -= 1;
      renderList();
      list.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    list.querySelector('[data-page-next]')?.addEventListener('click', () => {
      if (currentPage >= totalPages) return;
      currentPage += 1;
      renderList();
      list.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    list.querySelectorAll('[data-open-job]').forEach((button) => button.addEventListener('click', (event) => {
      event.stopPropagation();
      openDetail(button.dataset.openJob);
    }));
    list.querySelectorAll('[data-card-job]').forEach((card) => {
      const openCard = (event) => {
        if (event.target.closest('button,a,input,select,textarea,[data-delete-job],[data-delete-yes],[data-delete-no]')) return;
        openDetail(card.dataset.cardJob);
      };
      card.addEventListener('click', openCard);
      card.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        openDetail(card.dataset.cardJob);
      });
    });
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

  function ensureMediaPreviewModal() {
    let layer = document.getElementById('archive-media-preview-modal');
    if (layer) return layer;
    layer = document.createElement('div');
    layer.id = 'archive-media-preview-modal';
    layer.className = 'archive-media-preview-modal';
    layer.hidden = true;
    layer.innerHTML = `<div class="archive-media-preview-card" role="dialog" aria-modal="true" aria-labelledby="archive-media-preview-title">
      <div class="archive-media-preview-head"><h3 id="archive-media-preview-title">미디어 미리보기</h3><button type="button" data-media-preview-close>닫기</button></div>
      <div id="archive-media-preview-body" class="archive-media-preview-body"></div>
      <a id="archive-media-preview-download" class="archive-media-preview-download" href="#" download>다운로드</a>
    </div>`;
    document.body.appendChild(layer);
    layer.addEventListener('click', (event) => {
      if (event.target === layer || event.target.closest('[data-media-preview-close]')) closeMediaPreview();
    });
    layer.querySelector('#archive-media-preview-download')?.addEventListener('click', downloadMediaPreviewFile);
    return layer;
  }

  async function downloadMediaPreviewFile(event) {
    event.preventDefault();
    const button = event.currentTarget;
    const url = String(button?.href || '');
    if (!url || url.endsWith('#')) return;
    const original = button.textContent;
    button.textContent = '다운로드 준비 중...';
    button.setAttribute('aria-disabled', 'true');
    try {
      const response = await fetch(url, { credentials: 'include', cache: 'no-store' });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${response.status}`);
      }
      const blob = await response.blob();
      if (!blob.size) throw new Error('다운로드 파일이 비어 있습니다.');
      const disposition = response.headers.get('content-disposition') || '';
      const utf8Name = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
      const plainName = disposition.match(/filename="?([^";]+)"?/i)?.[1];
      const filename = decodeURIComponent(utf8Name || plainName || button.getAttribute('download') || 'download');
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1500);
      button.textContent = '다운로드 완료';
    } catch (error) {
      button.textContent = '다운로드 실패';
      showCopyToast(`다운로드 실패: ${error.message}`, true);
    } finally {
      window.setTimeout(() => {
        button.textContent = original;
        button.removeAttribute('aria-disabled');
      }, 1500);
    }
  }

  function closeMediaPreview() {
    const layer = document.getElementById('archive-media-preview-modal');
    if (!layer) return;
    const video = layer.querySelector('video');
    if (video) {
      video.pause();
      video.removeAttribute('src');
      video.load();
    }
    layer.hidden = true;
    document.body.classList.remove('archive-media-preview-open');
  }

  function openMediaPreview({ type, url, urls = [], title, downloadName, downloadUrl }) {
    const galleryUrls = Array.isArray(urls) ? urls.filter(Boolean) : [];
    if (!url && !galleryUrls.length) return;
    const layer = ensureMediaPreviewModal();
    const body = layer.querySelector('#archive-media-preview-body');
    const heading = layer.querySelector('#archive-media-preview-title');
    const download = layer.querySelector('#archive-media-preview-download');
    heading.textContent = title || '미디어 미리보기';
    if (type === 'gallery') {
      body.innerHTML = `<div class="archive-media-preview-gallery">${galleryUrls.map((item, index) => `<figure><img src="${esc(item)}" alt="업로드 이미지 ${index + 1}"><figcaption>${index + 1} / ${galleryUrls.length}</figcaption></figure>`).join('')}</div>`;
    } else {
      body.innerHTML = type === 'video'
        ? `<video controls playsinline preload="metadata" src="${esc(url)}"></video>`
        : `<img src="${esc(url)}" alt="${esc(title || '미디어 미리보기')}">`;
    }
    download.href = downloadUrl || url;
    download.setAttribute('download', downloadName || '');
    layer.hidden = false;
    document.body.classList.add('archive-media-preview-open');
  }

  async function deleteJob(jobId, button) {
    if (!jobId || button.disabled) return;
    button.disabled = true;
    button.textContent = '파일 삭제 중';
    try {
      const result = await req(`/beta-api/jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
      await load();
      alert(`저장 파일만 삭제했습니다. 목록과 DB 기록은 그대로 유지됩니다.${result.deleted_bytes ? `\n삭제 용량: ${Number(result.deleted_bytes).toLocaleString('ko-KR')}바이트` : ''}`);
    } catch (error) {
      button.disabled = false;
      button.textContent = '예';
      alert(`파일 삭제 실패: ${error.message}`);
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
        <section class="detail-block"><div class="channel-title-row"><h3>SNS 8채널</h3><span>채널을 선택하면 아래 복사 바가 자동으로 따라옵니다.</span></div><div class="channel-tabs">${order.map((key, index) => `<button type="button" class="channel-tab${index === 0 ? ' active' : ''}" data-channel="${esc(key)}">${esc(channels[key]?.label || key)}</button>`).join('')}</div><div id="archive-channel-content" class="channel-content rich-channel-content${first === 'BLOG' ? '' : ' archive-channel-dark'}">${first === 'BLOG' ? archiveCopyPayload(channels[first], first).rich : mobileCopyHtml(channels[first]?.content || '')}</div><div id="archive-smart-copy-bar" class="archive-smart-copy-bar"><div class="archive-smart-copy-info"><span class="archive-smart-copy-kicker">현재 채널</span><strong id="archive-smart-copy-label">${esc(channels[first]?.label || first || '콘텐츠')}</strong><small id="archive-smart-copy-meta">${archiveCopyPayload(channels[first], first).plain.length.toLocaleString('ko-KR')}자 · ${first === 'BLOG' ? '서식 유지 복사' : '텍스트 복사'}</small></div><button id="archive-channel-copy" type="button">${first === 'BLOG' ? '블로그 서식 복사' : `${esc(channels[first]?.label || first || '콘텐츠')} 복사`}</button></div></section>
        <div class="archive-sections archive-sections-all">
          <div id="archive-media-all" class="archive-media-all">
            <section class="archive-section-static media-preview-card"><h3>업로드 이미지 ${images.length}장</h3><div class="image-grid">${images.map((_, index) => { const imageUrl = `/beta-api/browser/jobs/${encodeURIComponent(jobId)}/image/${index + 1}`; return `<button type="button" class="archive-media-thumb" data-media-preview="gallery" data-media-url="${imageUrl}" data-media-title="업로드 이미지 ${images.length}장" data-media-download="${esc(jobId)}_images.zip"><img loading="lazy" src="${imageUrl}" alt="이미지 ${index + 1}"></button>`; }).join('') || '<div class="empty-mini">이미지가 없습니다.</div>'}</div>${images.length ? `<div class="media-download-row"><a class="download-link" href="/beta-api/browser/jobs/${encodeURIComponent(jobId)}/images-download" download>다운로드</a></div>` : ''}</section>
            <section class="archive-section-static media-preview-card"><h3>팟캐스트 MP3</h3>${audioUrl ? `<audio class="audio-preview" controls preload="metadata" src="${audioUrl}"></audio><div class="media-download-row"><a class="download-link" href="${audioUrl}" download>다운로드</a></div>` : '<div class="empty-mini">MP3가 없습니다.</div>'}</section>
            <section class="archive-section-static media-preview-card"><h3>썸네일</h3>${thumbnailUrl ? `<button type="button" class="archive-media-thumb archive-media-thumb-large" data-media-preview="image" data-media-url="${thumbnailUrl}" data-media-title="썸네일 미리보기" data-media-download="${esc(jobId)}_thumbnail.png"><img class="thumbnail-preview" loading="lazy" src="${thumbnailUrl}" alt="썸네일"></button><div class="media-download-row"><a class="download-link" href="${thumbnailUrl}" download>다운로드</a></div>` : '<div class="empty-mini">썸네일이 없습니다.</div>'}</section>
            <section class="archive-section-static media-preview-card"><h3>최종 MP4</h3>${videoUrl ? `<button type="button" class="archive-media-thumb archive-video-thumb" data-media-preview="video" data-media-url="${videoUrl}" data-media-title="최종 MP4 미리보기" data-media-download="${esc(jobId)}.mp4"><video class="mp4-preview" muted preload="metadata" playsinline src="${videoUrl}"></video><span>눌러서 크게 보기</span></button><div class="media-download-row"><a class="download-link" href="${videoUrl}" download>다운로드</a></div>` : '<div class="empty-mini">MP4가 없습니다.</div>'}</section>
          </div>
          <div class="archive-package-row"><button type="button" class="package-main-button" data-download-package="${esc(jobId)}">이미지 · MP3 · SRT · 썸네일 · MP4 전체 ZIP 다운로드</button></div>
        </div>`;
      document.getElementById('archive-detail-close')?.addEventListener('click', closeDetail);
      detail.querySelectorAll('[data-download-package]').forEach((button) => button.addEventListener('click', () => downloadPackage(button.dataset.downloadPackage)));
      detail.querySelectorAll('[data-channel]').forEach((button) => button.addEventListener('click', () => selectAndCopyChannel(button, channels, false)));
      document.getElementById('archive-smart-copy-bar')?.addEventListener('click', (event) => {
        event.preventDefault();
        const active = detail.querySelector('[data-channel].active');
        if (active) selectAndCopyChannel(active, channels, true);
      });
      detail.querySelectorAll('[data-media-preview]').forEach((button) => button.addEventListener('click', () => {
        const type = button.dataset.mediaPreview;
        const galleryButtons = type === 'gallery' ? [...detail.querySelectorAll('[data-media-preview="gallery"]')] : [];
        openMediaPreview({
          type,
          url: button.dataset.mediaUrl,
          urls: galleryButtons.map((item) => item.dataset.mediaUrl),
          title: button.dataset.mediaTitle,
          downloadName: button.dataset.mediaDownload,
          downloadUrl: type === 'gallery' ? `/beta-api/browser/jobs/${encodeURIComponent(jobId)}/images-download` : '',
        });
      }));
    } catch (error) {
      detail.innerHTML = `<div class="empty">상세 조회 실패: ${esc(error.message)}</div>`;
    }
  }

  function closeDetail() {
    closeMediaPreview();
    modal.hidden = true;
    document.body.classList.remove('archive-modal-open');
    detail.innerHTML = '';
  }

  modal?.addEventListener('click', (event) => {
    if (event.target === modal) closeDetail();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    const mediaLayer = document.getElementById('archive-media-preview-modal');
    if (mediaLayer && !mediaLayer.hidden) {
      closeMediaPreview();
      return;
    }
    if (!modal.hidden) closeDetail();
  });

  async function load() {
    list.className = 'empty'; list.textContent = '불러오는 중...';
    try {
      await resolveAdminAccess();
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

  search?.addEventListener('input', () => { currentPage = 1; renderList(); });
  filter?.addEventListener('change', () => { currentPage = 1; renderList(); });
  sort?.addEventListener('change', () => { currentPage = 1; renderList(); });
  refresh?.addEventListener('click', () => { currentPage = 1; load(); });
  load();
})();
