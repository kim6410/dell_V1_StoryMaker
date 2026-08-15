(() => {
  if (window.__STORYMAKER_V1_ARCHIVE_MEDIA_BRIDGE__) return;
  window.__STORYMAKER_V1_ARCHIVE_MEDIA_BRIDGE__ = true;

  const state = {
    detail: null,
    detailUrl: '',
    listItems: [],
    selectedJobId: '',
    modalObjectUrls: new Set(),
    activeMediaElements: new Set(),
  };

  const buttonKinds = [
    ['이미지 보기', 'images'],
    ['MP3 재생', 'mp3'],
    ['숏폼/쇼츠 보기', 'mp4'],
    ['썸네일 보기', 'thumbnail'],
  ];

  function readToken() {
    const keys = ['storymaker_token', 'access_token'];
    for (const key of keys) {
      const value = String(localStorage.getItem(key) || sessionStorage.getItem(key) || '').trim();
      if (value) return value;
    }
    return '';
  }

  function firstString(...values) {
    for (const value of values) {
      const text = String(value || '').trim();
      if (text) return text;
    }
    return '';
  }

  function assetId(asset) {
    const value = Number(asset?.asset_id || asset?.id || 0);
    return Number.isInteger(value) && value > 0 ? value : 0;
  }

  function assetViewUrl(asset) {
    const id = assetId(asset);
    return id ? `/api/v2/content-board/assets/${id}/view` : '';
  }

  function assetDownloadUrl(asset) {
    const direct = firstString(asset?.download_url);
    if (direct) return direct;
    const id = assetId(asset);
    return id ? `/api/v2/content-board/assets/${id}/download` : '';
  }

  function assetName(asset, fallback) {
    return firstString(asset?.download_name, asset?.original_filename, fallback);
  }

  function assetsByType(detail, type) {
    const assets = Array.isArray(detail?.assets) ? detail.assets : [];
    return assets.filter((asset) => String(asset?.asset_type || '').toLowerCase() === type && assetId(asset));
  }

  function mediaSources(detail) {
    return {
      images: assetsByType(detail, 'image'),
      mp3: assetsByType(detail, 'mp3')[0] || null,
      mp4: assetsByType(detail, 'mp4')[0] || null,
      thumbnail: assetsByType(detail, 'thumbnail')[0] || null,
    };
  }

  function normalizeText(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function itemJobId(item) {
    const value = firstString(item?.job_id, item?.content_id);
    return /^mob-[0-9]{14}-[a-f0-9]{8}$/i.test(value) ? value : '';
  }

  function rememberListItems(payload) {
    const items = Array.isArray(payload?.items)
      ? payload.items
      : Array.isArray(payload?.data?.items)
        ? payload.data.items
        : [];
    if (items.length) state.listItems = items.filter((item) => itemJobId(item));
  }

  function itemMatchesNode(item, nodeText) {
    const title = normalizeText(firstString(item?.title, item?.memo));
    if (title && nodeText.includes(title)) return true;

    const personaName = normalizeText(firstString(item?.persona?.company_name, item?.persona?.business_name));
    const createdAt = normalizeText(item?.created_at);
    return Boolean(personaName && createdAt && nodeText.includes(personaName) && nodeText.includes(createdAt.slice(5, 16)));
  }

  function findListItemForNode(node) {
    const items = Array.isArray(state.listItems) ? state.listItems : [];
    let current = node instanceof Element ? node : null;

    for (let depth = 0; current && depth < 12; depth += 1, current = current.parentElement) {
      const nodeText = normalizeText(current.textContent);
      if (!nodeText) continue;
      const matches = items.filter((item) => itemMatchesNode(item, nodeText));
      if (matches.length === 1) return matches[0];
    }

    if (state.selectedJobId) {
      const selected = items.find((item) => itemJobId(item) === state.selectedJobId);
      if (selected) return selected;
    }
    return items.length === 1 ? items[0] : null;
  }

  function selectListItem(item) {
    const jobId = itemJobId(item);
    if (!jobId) return null;
    state.selectedJobId = jobId;
    state.detailUrl = `/api/v2/content-board/${jobId}`;
    state.detail = Array.isArray(item?.assets) ? item : null;
    return item;
  }

  async function loadListItems() {
    if (Array.isArray(state.listItems) && state.listItems.length) return state.listItems;

    const headers = {};
    const token = readToken();
    if (token) headers.Authorization = `Bearer ${token}`;

    const response = await fetch('/api/v2/content-board?limit=20&offset=0', {
      method: 'GET',
      credentials: 'include',
      cache: 'no-store',
      headers,
    });
    if (!response.ok) {
      const detail = await readErrorDetail(response);
      throw new Error(detail || `보관함 목록을 불러오지 못했습니다. (HTTP ${response.status})`);
    }

    const payload = await response.json();
    rememberListItems(payload);
    return state.listItems;
  }

  async function readErrorDetail(response) {
    try {
      const payload = await response.clone().json();
      return firstString(payload?.detail, payload?.message, payload?.error);
    } catch (_) {
      return '';
    }
  }

  async function fetchAssetBlob(asset, expectedKind, useDownload = false) {
    const rawUrl = useDownload ? assetDownloadUrl(asset) : assetViewUrl(asset);
    if (!rawUrl) throw new Error('자산 ID가 없어 미디어 주소를 만들 수 없습니다.');

    const resolved = new URL(rawUrl, location.href);
    const sameOrigin = resolved.origin === location.origin;
    const token = readToken();
    const headers = {};
    if (sameOrigin && token) headers.Authorization = `Bearer ${token}`;

    const response = await fetch(resolved.toString(), {
      method: 'GET',
      credentials: sameOrigin ? 'include' : 'omit',
      cache: 'no-store',
      headers,
    });

    if (!response.ok) {
      const detail = await readErrorDetail(response);
      throw new Error(detail || `보관함 미디어를 불러오지 못했습니다. (HTTP ${response.status})`);
    }

    const headerType = String(response.headers.get('content-type') || '').toLowerCase();
    const blob = await response.blob();
    const blobType = String(blob.type || headerType || '').toLowerCase();
    if (!blob.size) throw new Error('빈 미디어 응답입니다.');

    const accepted = {
      image: ['image/'],
      audio: ['audio/', 'application/octet-stream'],
      video: ['video/', 'application/octet-stream'],
      any: [],
    }[expectedKind] || [];

    if (accepted.length && blobType && !accepted.some((prefix) => blobType.startsWith(prefix))) {
      throw new Error(`미디어 형식이 올바르지 않습니다. (${blobType})`);
    }

    return { blob, response };
  }

  function registerObjectUrl(blob) {
    const url = URL.createObjectURL(blob);
    state.modalObjectUrls.add(url);
    return url;
  }

  function stopActiveMedia() {
    for (const element of state.activeMediaElements) {
      try {
        element.pause?.();
        element.currentTime = 0;
        element.removeAttribute?.('src');
        element.load?.();
      } catch (_) {}
    }
    state.activeMediaElements.clear();
  }

  function revokeModalObjectUrls() {
    for (const url of state.modalObjectUrls) URL.revokeObjectURL(url);
    state.modalObjectUrls.clear();
  }

  function closeModal() {
    stopActiveMedia();
    revokeModalObjectUrls();
    document.querySelectorAll('[data-v1-archive-modal="1"]').forEach((node) => node.remove());
  }

  function createModal(title) {
    closeModal();
    const overlay = document.createElement('div');
    overlay.dataset.v1ArchiveModal = '1';
    overlay.style.cssText = 'position:fixed;inset:0;z-index:2147483646;background:rgba(2,6,23,.88);display:flex;align-items:center;justify-content:center;padding:24px;';

    const panel = document.createElement('div');
    panel.style.cssText = 'width:min(1100px,96vw);max-height:92vh;overflow:auto;border:1px solid #334155;border-radius:20px;background:#071226;color:#fff;padding:18px;box-shadow:0 24px 80px rgba(0,0,0,.55);';

    const head = document.createElement('div');
    head.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:16px;';
    const heading = document.createElement('strong');
    heading.textContent = title;
    heading.style.fontSize = '17px';
    const close = document.createElement('button');
    close.type = 'button';
    close.textContent = '닫기';
    close.style.cssText = 'border:1px solid #64748b;border-radius:999px;background:#0f172a;color:#fff;padding:8px 14px;cursor:pointer;';
    close.addEventListener('click', closeModal);
    head.append(heading, close);

    const body = document.createElement('div');
    body.dataset.v1ArchiveModalBody = '1';
    panel.append(head, body);
    overlay.append(panel);
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) closeModal();
    });
    document.body.appendChild(overlay);
    return body;
  }

  function setMessage(container, message, isError = false) {
    container.replaceChildren();
    const p = document.createElement('p');
    p.textContent = message;
    p.style.cssText = `margin:0;padding:28px;text-align:center;color:${isError ? '#fca5a5' : '#cbd5e1'};font-weight:700;line-height:1.6;`;
    container.appendChild(p);
  }

  function waitForMedia(element, successEvents, label) {
    return new Promise((resolve, reject) => {
      let settled = false;
      const cleanup = () => {
        successEvents.forEach((name) => element.removeEventListener(name, onSuccess));
        element.removeEventListener('error', onError);
      };
      const onSuccess = () => {
        if (settled) return;
        settled = true;
        cleanup();
        resolve();
      };
      const onError = () => {
        if (settled) return;
        settled = true;
        cleanup();
        reject(new Error(`${label} 로드에 실패했습니다.${element.error?.code ? ` (code ${element.error.code})` : ''}`));
      };
      successEvents.forEach((name) => element.addEventListener(name, onSuccess, { once: true }));
      element.addEventListener('error', onError, { once: true });
      element.load?.();
    });
  }

  async function downloadAsset(asset) {
    const { blob, response } = await fetchAssetBlob(asset, 'any', true);
    let filename = assetName(asset, 'storymaker-download');
    const disposition = response.headers.get('content-disposition') || '';
    const utf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    const plain = disposition.match(/filename="?([^";]+)"?/i);
    try {
      if (utf8?.[1]) filename = decodeURIComponent(utf8[1].trim());
      else if (plain?.[1]) filename = plain[1].trim();
    } catch (_) {}

    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = filename;
    anchor.style.display = 'none';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 2000);
  }

  function addDownloadButton(container, asset, label) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    button.style.cssText = 'display:block;width:100%;margin-top:12px;border:0;border-radius:14px;background:#67e8f9;color:#082f49;padding:12px 16px;font-weight:800;cursor:pointer;';
    button.addEventListener('click', async () => {
      const original = button.textContent;
      button.disabled = true;
      button.textContent = '다운로드 준비 중...';
      try {
        await downloadAsset(asset);
      } catch (error) {
        alert(error?.message || '다운로드하지 못했습니다.');
      } finally {
        button.disabled = false;
        button.textContent = original;
      }
    });
    container.appendChild(button);
  }

  async function openImages(assets) {
    if (!assets.length) throw new Error('저장된 이미지가 없습니다.');
    const body = createModal(`이미지 보기 (${assets.length}장)`);
    body.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;';

    await Promise.all(assets.map(async (asset, index) => {
      const box = document.createElement('div');
      box.style.cssText = 'min-height:180px;border:1px solid #334155;border-radius:14px;background:#020617;padding:8px;color:#cbd5e1;';
      box.textContent = `${index + 1}번 이미지 불러오는 중...`;
      body.appendChild(box);
      try {
        const { blob } = await fetchAssetBlob(asset, 'image');
        const img = document.createElement('img');
        img.alt = assetName(asset, `보관함 이미지 ${index + 1}`);
        img.style.cssText = 'display:block;width:100%;max-height:65vh;object-fit:contain;border-radius:10px;';
        const loaded = waitForMedia(img, ['load'], `${index + 1}번 이미지`);
        img.src = registerObjectUrl(blob);
        box.replaceChildren(img);
        await loaded;
        addDownloadButton(box, asset, '이미지 다운로드');
      } catch (error) {
        setMessage(box, error?.message || '이미지를 불러오지 못했습니다.', true);
      }
    }));
  }

  async function openSingleMedia(asset, kind) {
    if (!asset) throw new Error(`저장된 ${kind === 'audio' ? 'MP3' : kind === 'video' ? 'MP4' : '썸네일'}가 없습니다.`);
    const title = kind === 'audio' ? 'MP3 재생' : kind === 'video' ? '숏폼/쇼츠 보기' : '썸네일 보기';
    const body = createModal(title);
    setMessage(body, `${title} 불러오는 중...`);

    const { blob } = await fetchAssetBlob(asset, kind === 'image' ? 'image' : kind);
    const objectUrl = registerObjectUrl(blob);
    let element;
    let events;

    if (kind === 'audio') {
      element = document.createElement('audio');
      element.controls = true;
      element.loop = false;
      element.autoplay = false;
      element.preload = 'metadata';
      element.style.cssText = 'display:block;width:100%;margin:30px 0;';
      state.activeMediaElements.add(element);
      events = ['loadedmetadata', 'canplay'];
    } else if (kind === 'video') {
      element = document.createElement('video');
      element.controls = true;
      element.loop = false;
      element.autoplay = false;
      element.playsInline = true;
      element.preload = 'metadata';
      element.style.cssText = 'display:block;max-width:100%;max-height:78vh;margin:0 auto;border-radius:14px;background:#000;';
      state.activeMediaElements.add(element);
      events = ['loadedmetadata', 'canplay'];
    } else {
      element = document.createElement('img');
      element.alt = assetName(asset, '보관함 썸네일');
      element.style.cssText = 'display:block;max-width:100%;max-height:78vh;object-fit:contain;margin:0 auto;border-radius:14px;background:#020617;';
      events = ['load'];
    }

    const loaded = waitForMedia(element, events, title);
    element.src = objectUrl;
    body.replaceChildren(element);
    await loaded;
    addDownloadButton(body, asset, `${title} 다운로드`);
  }

  async function ensureDetail(button) {
    if (state.detail && Array.isArray(state.detail.assets)) return state.detail;

    if (!Array.isArray(state.listItems) || !state.listItems.length) await loadListItems();
    const matchedItem = findListItemForNode(button);
    if (matchedItem) selectListItem(matchedItem);
    if (state.detail && Array.isArray(state.detail.assets)) return state.detail;

    if (!state.detailUrl) {
      throw new Error('선택한 보관함 작업을 찾지 못했습니다. 보관함을 새로고침한 뒤 다시 눌러주세요.');
    }

    const headers = {};
    const token = readToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    const response = await fetch(state.detailUrl, { credentials: 'include', cache: 'no-store', headers });
    if (!response.ok) {
      const detail = await readErrorDetail(response);
      throw new Error(detail || `보관함 상세 정보를 불러오지 못했습니다. (HTTP ${response.status})`);
    }
    const payload = await response.json();
    state.detail = payload?.data || null;
    if (!state.detail) throw new Error('보관함 상세 응답에 데이터가 없습니다.');
    return state.detail;
  }

  async function handle(kind, button) {
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = '불러오는 중...';
    try {
      const detail = await ensureDetail(button);
      const sources = mediaSources(detail);
      if (kind === 'images') await openImages(sources.images);
      else if (kind === 'mp3') await openSingleMedia(sources.mp3, 'audio');
      else if (kind === 'mp4') await openSingleMedia(sources.mp4, 'video');
      else if (kind === 'thumbnail') await openSingleMedia(sources.thumbnail, 'image');
    } catch (error) {
      const body = createModal('보관함 미디어');
      setMessage(body, error?.message || '미디어를 열지 못했습니다.', true);
    } finally {
      button.disabled = false;
      button.textContent = originalText;
    }
  }

  function buttonKind(button) {
    const text = String(button?.textContent || '').trim();
    for (const [label, kind] of buttonKinds) {
      if (text.includes(label)) return kind;
    }
    return '';
  }

  document.addEventListener('click', (event) => {
    const button = event.target?.closest?.('button');
    if (!button) return;

    const buttonText = normalizeText(button.textContent);
    if (buttonText === '상세') {
      const item = findListItemForNode(button);
      if (item) selectListItem(item);
      return;
    }

    const kind = buttonKind(button);
    if (!kind) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    void handle(kind, button);
  }, true);

  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await nativeFetch(...args);
    try {
      const raw = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
      const url = new URL(raw, location.href);
      const isList = url.pathname === '/api/v2/content-board';
      const isDetail = /^\/api\/v2\/content-board\/mob-[0-9]{14}-[a-f0-9]{8}\/?$/i.test(url.pathname);
      if (isList && response.ok) {
        const payload = await response.clone().json();
        rememberListItems(payload);
      } else if (isDetail && response.ok) {
        const payload = await response.clone().json();
        if (payload?.data && Array.isArray(payload.data.assets)) {
          state.detail = payload.data;
          state.detailUrl = `${url.pathname}${url.search}`;
          state.selectedJobId = itemJobId(payload.data);
        }
      }
    } catch (_) {}
    return response;
  };

  window.addEventListener('beforeunload', revokeModalObjectUrls);
  console.info('[StoryMaker V1] archive media bridge ready: asset-id-only-v7');
})();
