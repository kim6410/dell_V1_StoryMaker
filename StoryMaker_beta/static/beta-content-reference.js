(() => {
  'use strict';

  const REFERENCE_HEADER = '-----------------------참고글감---------------------------------';
  const REFERENCE_END = '---------------------참고글감 끝-------------------------------';

  const topic = document.getElementById('beta-topic');
  if (!topic || topic.dataset.referenceShellReady === '1') return;
  topic.dataset.referenceShellReady = '1';

  const host = topic.parentElement;
  const originalLabel = host?.querySelector('label');
  if (!host || !originalLabel) return;

  const headingRow = document.createElement('div');
  headingRow.className = 'beta-reference-heading-row';
  originalLabel.parentNode.insertBefore(headingRow, originalLabel);
  headingRow.appendChild(originalLabel);

  const openButton = document.createElement('button');
  openButton.type = 'button';
  openButton.id = 'beta-reference-open';
  openButton.className = 'beta-reference-search-button';
  openButton.setAttribute('aria-label', '참고글감 열기');
  openButton.setAttribute('title', '참고글감');
  openButton.innerHTML = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="2"/><path d="m16 16 4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
  headingRow.appendChild(openButton);

  const hiddenField = document.createElement('textarea');
  hiddenField.id = 'beta-reference-material';
  hiddenField.name = 'reference_material';
  hiddenField.hidden = true;
  host.appendChild(hiddenField);

  const overlay = document.createElement('div');
  overlay.id = 'beta-reference-overlay';
  overlay.className = 'beta-reference-overlay';
  overlay.setAttribute('aria-hidden', 'true');
  overlay.innerHTML = `
    <div class="beta-reference-modal" role="dialog" aria-modal="true" aria-labelledby="beta-reference-title">
      <div class="beta-reference-modal-header">
        <div>
          <div class="beta-reference-modal-title" id="beta-reference-title">참고글감</div>
          <div class="beta-reference-modal-subtitle">사용자 원문을 건드리지 않고 내용을 풍성하게 보강합니다.</div>
        </div>
        <button type="button" class="beta-reference-close" id="beta-reference-close" aria-label="닫기">×</button>
      </div>
      <div class="beta-reference-modal-body">
        <section class="beta-reference-secret" id="beta-reference-secret">
          <div class="beta-reference-secret-title">글감조회</div>
          <div class="beta-reference-secret-row">
            <input id="beta-reference-query" class="beta-reference-secret-input" type="text" placeholder="검색 키워드 또는 네이버 블로그 URL">
            <button id="beta-reference-fetch" class="beta-reference-secret-button" type="button">자료 가져오기</button>
          </div>
          <div id="beta-reference-search-status" class="beta-reference-secret-note">키워드는 블로그 검색, URL은 본문 추출로 작동합니다.</div>
          <div id="beta-reference-results" class="beta-reference-results"></div>
        </section>
        <div class="beta-reference-help compact">본문을 확인한 뒤 참고글감에 추가를 누르면 기초 콘텐츠 입력칸 하단에 즉시 반영됩니다.</div>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  const secret = overlay.querySelector('#beta-reference-secret');
  const queryInput = overlay.querySelector('#beta-reference-query');
  const fetchButton = overlay.querySelector('#beta-reference-fetch');
  const searchStatus = overlay.querySelector('#beta-reference-search-status');
  const resultsBox = overlay.querySelector('#beta-reference-results');

  function readTopicParts() {
    const value = String(topic.value || '');
    const start = value.indexOf(REFERENCE_HEADER);
    if (start < 0) return { base: value.trim(), reference: '' };
    const end = value.indexOf(REFERENCE_END, start + REFERENCE_HEADER.length);
    const referenceEnd = end >= 0 ? end : value.length;
    return {
      base: value.slice(0, start).trim(),
      reference: value.slice(start + REFERENCE_HEADER.length, referenceEnd).trim()
    };
  }

  function writeTopicReference(reference) {
    const parts = readTopicParts();
    const cleanReference = String(reference || '').trim();
    hiddenField.value = cleanReference;
    topic.value = cleanReference
      ? `${parts.base}\n\n${REFERENCE_HEADER}\n\n${cleanReference}`.trim()
      : parts.base;
    topic.dispatchEvent(new Event('input', { bubbles: true }));
    topic.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function isNaverBlogUrl(value) {
    return /^https?:\/\/(?:m\.)?blog\.naver\.com\//i.test(String(value || '').trim());
  }

  async function requestJson(url, options = {}) {
    const response = await fetch(url, { cache: 'no-store', credentials: 'include', ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    return data;
  }

  function appendReferenceText(title, text) {
    const block = title ? `[${title}]\n${text}` : text;
    const parts = readTopicParts();
    const nextReference = [parts.reference, block.trim()].filter(Boolean).join('\n\n');
    writeTopicReference(nextReference);
    topic.focus();
  }

  function renderBodyPreview(card, item, bodyItem) {
    const previewPanel = card.querySelector('.beta-reference-result-preview');
    const previewTitle = card.querySelector('.beta-reference-result-preview-title');
    const previewText = card.querySelector('.beta-reference-result-preview-text');
    const addButton = card.querySelector('.beta-reference-result-add');
    previewTitle.textContent = bodyItem.title || item.title || '블로그 본문';
    previewText.textContent = bodyItem.text || '';
    previewPanel.classList.add('is-visible');
    addButton.disabled = false;
    addButton.onclick = () => {
      appendReferenceText(bodyItem.title || item.title, bodyItem.text || '');
      addButton.disabled = true;
      addButton.textContent = '본문에 추가됨';
      searchStatus.textContent = `${Number(bodyItem.length || bodyItem.text?.length || 0).toLocaleString('ko-KR')}자를 기초 콘텐츠 입력칸 하단에 바로 추가했습니다.`;
      closeModal();
    };
  }

  function createResultCard(item, index) {
    const card = document.createElement('article');
    card.className = 'beta-reference-result-card';
    card.innerHTML = `
      <div class="beta-reference-result-number">${index + 1}</div>
      <div class="beta-reference-result-main">
        <div class="beta-reference-result-title"></div>
        <div class="beta-reference-result-url"></div>
        <div class="beta-reference-result-actions">
          <button type="button" class="beta-reference-result-view">본문 보기</button>
          <a class="beta-reference-result-open" target="_blank" rel="noopener noreferrer">Link</a>
        </div>
        <section class="beta-reference-result-preview">
          <div class="beta-reference-result-preview-head">
            <strong class="beta-reference-result-preview-title"></strong>
            <button type="button" class="beta-reference-result-add" disabled>참고글감에 추가</button>
          </div>
          <div class="beta-reference-result-preview-text"></div>
        </section>
      </div>`;
    card.querySelector('.beta-reference-result-title').textContent = item.title || '블로그 글';
    card.querySelector('.beta-reference-result-url').textContent = item.url || '';
    card.querySelector('.beta-reference-result-open').href = item.url || '#';

    const viewButton = card.querySelector('.beta-reference-result-view');
    viewButton.addEventListener('click', async () => {
      const previewPanel = card.querySelector('.beta-reference-result-preview');
      if (previewPanel.classList.contains('is-visible')) {
        previewPanel.classList.remove('is-visible');
        viewButton.textContent = '본문 보기';
        return;
      }
      if (card.dataset.loaded === '1') {
        previewPanel.classList.add('is-visible');
        viewButton.textContent = '본문 접기';
        return;
      }
      viewButton.disabled = true;
      viewButton.textContent = '본문 불러오는 중';
      try {
        const data = await requestJson('/beta-api/content-reference/scrape', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: item.url })
        });
        renderBodyPreview(card, item, data.item || {});
        card.dataset.loaded = '1';
        viewButton.textContent = '본문 접기';
        searchStatus.textContent = `${Number(data.item?.length || 0).toLocaleString('ko-KR')}자 본문을 펼쳤습니다.`;
      } catch (error) {
        searchStatus.textContent = `본문 보기 실패: ${error.message}`;
        viewButton.textContent = '다시 보기';
      } finally {
        viewButton.disabled = false;
      }
    });
    return card;
  }

  function renderSearchResults(items) {
    resultsBox.innerHTML = '';
    if (!items.length) {
      resultsBox.innerHTML = '<div class="beta-reference-empty">검색 결과가 없습니다. 키워드를 조금 넓게 바꿔보세요.</div>';
      return;
    }
    const heading = document.createElement('div');
    heading.className = 'beta-reference-results-heading';
    heading.textContent = `검색 결과 ${items.length}개 · 제목을 고른 뒤 본문을 펼쳐 확인하세요.`;
    resultsBox.appendChild(heading);
    items.forEach((item, index) => resultsBox.appendChild(createResultCard(item, index)));
  }

  function renderDirectUrlResult(item) {
    resultsBox.innerHTML = '';
    const card = createResultCard({ title: item.title, url: queryInput.value.trim() }, 0);
    resultsBox.appendChild(card);
    renderBodyPreview(card, { title: item.title, url: queryInput.value.trim() }, item);
    card.dataset.loaded = '1';
    card.querySelector('.beta-reference-result-view').textContent = '본문 접기';
  }

  async function fetchReference() {
    const value = queryInput.value.trim();
    if (!value) {
      searchStatus.textContent = '검색어 또는 네이버 블로그 URL을 입력하세요.';
      queryInput.focus();
      return;
    }
    fetchButton.disabled = true;
    searchStatus.textContent = '자료를 찾고 있습니다.';
    resultsBox.innerHTML = '<div class="beta-reference-loading">검색 중입니다.</div>';
    try {
      if (isNaverBlogUrl(value)) {
        const data = await requestJson('/beta-api/content-reference/scrape', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: value })
        });
        renderDirectUrlResult(data.item || {});
        searchStatus.textContent = `${Number(data.item?.length || 0).toLocaleString('ko-KR')}자 본문을 불러왔습니다. 읽어본 뒤 참고글감에 추가하세요.`;
      } else {
        const data = await requestJson(`/beta-api/content-reference/search?q=${encodeURIComponent(value)}&limit=8`);
        renderSearchResults(data.items || []);
        searchStatus.textContent = data.items?.length ? `${data.items.length}개의 블로그 글을 찾았습니다.` : '검색 결과가 없습니다.';
      }
    } catch (error) {
      resultsBox.innerHTML = '';
      searchStatus.textContent = `글감조회 실패: ${error.message}`;
    } finally {
      fetchButton.disabled = false;
    }
  }

  function openModal() {
    const parts = readTopicParts();
    hiddenField.value = parts.reference;
    secret.classList.add('is-visible');
    overlay.classList.add('is-open');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    window.setTimeout(() => queryInput?.focus(), 0);
  }

  function closeModal() {
    overlay.classList.remove('is-open');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    openButton.focus();
  }

  openButton.addEventListener('click', openModal);
  overlay.querySelector('#beta-reference-close').addEventListener('click', closeModal);
  fetchButton.addEventListener('click', fetchReference);
  queryInput.addEventListener('keydown', (event) => {
    const isEnter = event.key === 'Enter' || event.keyCode === 13;
    if (!isEnter || event.isComposing || event.keyCode === 229) return;
    event.preventDefault();
    event.stopPropagation();
    fetchReference();
  });
  queryInput.addEventListener('keyup', (event) => {
    if ((event.key === 'Enter' || event.keyCode === 13) && !event.isComposing && event.keyCode !== 229) {
      event.preventDefault();
    }
  });
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) closeModal();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && overlay.classList.contains('is-open')) closeModal();
  });
})();
