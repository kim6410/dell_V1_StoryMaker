(() => {
  'use strict';

  if (window.StoryMakerV1FeatureRequests) return;

  const MENU_ID = 'storymaker-v1-feature-request-menu';
  const ADMIN_BUTTON_ID = 'storymaker-v1-feature-request-admin-shortcut';
  const MODAL_ID = 'storymaker-v1-feature-request-modal';
  const API_MY_LIST = '/v1-api/feature-requests';
  const API_CREATE = '/v1-api/feature-requests';
  const API_ADMIN_LIST = '/v1-api/admin/feature-requests';
  const API_ME = '/v1-api/auth/me';
  const STATUSES = ['접수', '처리중', '완료', '보류'];

  let currentUser = null;
  let roleChecked = false;
  let itemsCache = [];

  const clean = (value = '') => String(value).replace(/\s+/g, ' ').trim();
  const esc = (value = '') => String(value)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const isAdmin = () => {
    if (!currentUser || typeof currentUser !== 'object') return false;
    const role = clean(currentUser.role || currentUser.user_role || currentUser.type).toLowerCase();
    return currentUser.is_admin === true || currentUser.admin === true || role === 'admin';
  };
  const answerLabel = (item) => clean(item?.admin_note) ? '답변완료' : '대기중';
  const dateText = (value) => clean(value) || '-';

  const apiFetch = async (url, options = {}) => {
    const response = await fetch(url, {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload?.ok === false) {
      throw new Error(payload?.detail || payload?.message || `요청 처리 실패 (${response.status})`);
    }
    return payload;
  };

  async function resolveRole(force = false) {
    if (roleChecked && !force) return currentUser;
    try {
      const payload = await apiFetch(API_ME);
      currentUser = payload?.data?.user || payload?.user || payload?.data || null;
    } catch (_) {
      currentUser = null;
    }
    roleChecked = true;
    return currentUser;
  }

  function ensureStyles() {
    if (document.getElementById('storymaker-v1-feature-request-style')) return;
    const style = document.createElement('style');
    style.id = 'storymaker-v1-feature-request-style';
    style.textContent = `
      #${MENU_ID}{margin-top:auto!important}
      .sm-v1-request-menu{display:flex!important;align-items:center!important;gap:10px!important;width:100%!important;padding:11px 14px!important;border:0!important;border-radius:12px!important;background:transparent!important;color:#cbd5e1!important;font-weight:800!important;cursor:pointer!important;text-align:left!important}
      .sm-v1-request-menu:hover,.sm-v1-request-menu.is-active{background:rgba(14,165,233,.16)!important;color:#e0f2fe!important}
      .sm-v1-request-wrap{width:100%;max-width:1740px;margin:0 auto;padding:10px 8px 24px;color:#e2e8f0;box-sizing:border-box}
      .sm-v1-request-head{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:16px;flex-wrap:wrap}
      .sm-v1-request-head h2{margin:0;font-size:24px;color:#f8fafc}.sm-v1-request-head p{margin:6px 0 0;color:#94a3b8;font-size:14px}
      .sm-v1-request-actions{display:flex;gap:9px;flex-wrap:wrap;align-items:center}
      .sm-v1-request-btn{border:1px solid rgba(56,189,248,.45);background:linear-gradient(135deg,#0284c7,#0ea5e9);color:#fff;border-radius:11px;padding:10px 15px;font-weight:900;cursor:pointer}
      .sm-v1-request-btn.secondary{background:#0f172a;border-color:rgba(148,163,184,.3);color:#e2e8f0}.sm-v1-request-btn:disabled{opacity:.55;cursor:wait}
      .sm-v1-request-admin-list{display:grid;gap:12px}
      .sm-v1-request-admin-card{background:rgba(15,23,42,.92);border:1px solid rgba(148,163,184,.22);border-radius:16px;padding:14px;display:grid;gap:10px;box-shadow:0 14px 35px rgba(0,0,0,.16);cursor:pointer;transition:.15s}
      .sm-v1-request-admin-card:hover{background:rgba(30,41,59,.82);border-color:rgba(56,189,248,.42);transform:translateY(-1px)}
      .sm-v1-request-admin-top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
      .sm-v1-request-admin-top strong{font-size:14px;color:#f8fafc}
      .sm-v1-request-admin-meta{font-size:11px;color:#94a3b8;margin-top:4px}
      .sm-v1-request-admin-content{white-space:pre-wrap;font-size:13px;line-height:1.7;color:#d5deeb;background:rgba(0,0,0,.14);padding:12px;border-radius:10px}
      .sm-v1-request-admin-answer{font-size:12px;color:#a7f3d0;background:rgba(6,78,59,.2);border:1px solid rgba(52,211,153,.2);padding:9px 11px;border-radius:10px;white-space:pre-wrap}
      .sm-v1-request-admin-open{font-size:11px;color:#7dd3fc;text-align:right;font-weight:800}
      .sm-v1-request-box{border:1px solid rgba(148,163,184,.2);background:rgba(15,23,42,.9);border-radius:18px;overflow:hidden;box-shadow:0 18px 50px rgba(0,0,0,.18)}
      .sm-v1-request-scroll{overflow-x:auto}.sm-v1-request-table{width:100%;min-width:760px;border-collapse:collapse}
      .sm-v1-request-table th{padding:13px 12px;background:#0b1222;color:#94a3b8;font-size:12px;text-align:center;border-bottom:1px solid #243045;white-space:nowrap}
      .sm-v1-request-table td{padding:14px 12px;border-bottom:1px solid rgba(51,65,85,.7);text-align:center;color:#cbd5e1;font-size:14px}
      .sm-v1-request-table tbody tr{cursor:pointer;transition:.15s}.sm-v1-request-table tbody tr:hover{background:rgba(30,41,59,.62)}
      .sm-v1-request-table .title{text-align:left;color:#f8fafc;font-weight:850;max-width:520px}.sm-v1-request-table .writer{text-align:left}
      .sm-v1-badge{display:inline-flex;align-items:center;justify-content:center;min-width:62px;padding:5px 9px;border-radius:999px;font-size:12px;font-weight:900;border:1px solid transparent}
      .sm-v1-status-received{color:#bfdbfe;background:rgba(37,99,235,.18);border-color:rgba(96,165,250,.35)}
      .sm-v1-status-working{color:#fed7aa;background:rgba(234,88,12,.18);border-color:rgba(251,146,60,.35)}
      .sm-v1-status-done{color:#bbf7d0;background:rgba(22,163,74,.18);border-color:rgba(74,222,128,.35)}
      .sm-v1-status-hold{color:#ddd6fe;background:rgba(124,58,237,.18);border-color:rgba(167,139,250,.35)}
      .sm-v1-answer-done{color:#a7f3d0}.sm-v1-answer-wait{color:#94a3b8}
      .sm-v1-request-empty{padding:48px 18px;text-align:center;color:#94a3b8}
      .sm-v1-detail{border:1px solid rgba(148,163,184,.2);background:rgba(15,23,42,.92);border-radius:18px;padding:22px}
      .sm-v1-detail-title{font-size:22px;font-weight:900;color:#fff;margin:0 0 10px}.sm-v1-detail-meta{display:flex;gap:10px;flex-wrap:wrap;color:#94a3b8;font-size:13px;margin-bottom:18px}
      .sm-v1-detail-section{margin-top:16px}.sm-v1-detail-label{font-size:13px;font-weight:900;color:#94a3b8;margin-bottom:8px}
      .sm-v1-detail-content{white-space:pre-wrap;line-height:1.75;color:#e2e8f0;background:#020617;border:1px solid #253047;border-radius:13px;padding:16px;min-height:90px}
      .sm-v1-answer-box{white-space:pre-wrap;line-height:1.75;color:#d1fae5;background:rgba(6,78,59,.25);border:1px solid rgba(52,211,153,.3);border-radius:13px;padding:16px}
      .sm-v1-admin-form{display:grid;grid-template-columns:180px 1fr;gap:12px;margin-top:18px}.sm-v1-admin-form label{display:grid;gap:7px;font-size:13px;font-weight:900;color:#94a3b8}
      .sm-v1-admin-form select,.sm-v1-admin-form textarea{width:100%;box-sizing:border-box;border:1px solid #334155;background:#020617;color:#e2e8f0;border-radius:11px;padding:11px;font:inherit}.sm-v1-admin-form textarea{min-height:150px;resize:vertical}
      .sm-v1-admin-form .full{grid-column:1/-1}.sm-v1-request-message{min-height:22px;margin-top:10px;color:#7dd3fc;font-weight:800}
      #${MODAL_ID}{position:fixed;inset:0;z-index:100000;display:none;align-items:center;justify-content:center;padding:20px;background:rgba(2,6,23,.78);backdrop-filter:blur(5px)}#${MODAL_ID}.is-open{display:flex}
      .sm-v1-request-modal-card{width:min(640px,96vw);background:#0f172a;border:1px solid rgba(56,189,248,.32);border-radius:20px;box-shadow:0 24px 80px rgba(0,0,0,.45);padding:22px;color:#fff}
      .sm-v1-request-modal-card h3{margin:0 0 8px;font-size:22px}.sm-v1-request-modal-card p{margin:0 0 16px;color:#94a3b8}
      .sm-v1-request-field{display:grid;gap:7px;margin-bottom:14px}.sm-v1-request-field label{font-weight:800;color:#e2e8f0}.sm-v1-request-field input,.sm-v1-request-field textarea{width:100%;box-sizing:border-box;border:1px solid rgba(148,163,184,.3);background:#020617;color:#fff;border-radius:12px;padding:12px;font:inherit}.sm-v1-request-field textarea{min-height:180px;resize:vertical}
      @media(max-width:760px){.sm-v1-request-wrap{padding:4px 0 18px}.sm-v1-request-head h2{font-size:21px}.sm-v1-admin-form{grid-template-columns:1fr}.sm-v1-admin-form .full{grid-column:auto}.sm-v1-request-table{min-width:680px}.sm-v1-detail{padding:16px}}
    `;
    document.head.appendChild(style);
  }

  function getInlineHost() {
    if (window.StoryMakerV1InlinePanels?.open) return window.StoryMakerV1InlinePanels.open('feature-requests', '요청사항');
    const main = document.querySelector('main') || document.querySelector('[class*="flex-1"]') || document.getElementById('root') || document.body;
    let host = document.getElementById('storymaker-v1-feature-request-fallback');
    if (!host) { host = document.createElement('section'); host.id = 'storymaker-v1-feature-request-fallback'; main.prepend(host); }
    return host;
  }

  function statusClass(status) {
    return status === '처리중' ? 'sm-v1-status-working' : status === '완료' ? 'sm-v1-status-done' : status === '보류' ? 'sm-v1-status-hold' : 'sm-v1-status-received';
  }

  function statusBadge(status) {
    const value = STATUSES.includes(status) ? status : '접수';
    return `<span class="sm-v1-badge ${statusClass(value)}">${esc(value)}</span>`;
  }

  function ensureModal() {
    let modal = document.getElementById(MODAL_ID);
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = MODAL_ID;
    modal.innerHTML = `<div class="sm-v1-request-modal-card" role="dialog" aria-modal="true"><h3>요청사항 작성</h3><form id="sm-v1-request-form"><div class="sm-v1-request-field"><label>제목<input id="sm-v1-request-title" maxlength="200" minlength="2" required placeholder="요청 제목을 입력하세요"></label></div><div class="sm-v1-request-field"><label>상세 내용<textarea id="sm-v1-request-content" maxlength="5000" minlength="5" required placeholder="어떤 점이 불편한지, 어떻게 개선되면 좋은지 자세히 적어주세요."></textarea></label></div><div class="sm-v1-request-message" id="sm-v1-request-form-status"></div><div class="sm-v1-request-actions" style="justify-content:flex-end"><button type="button" class="sm-v1-request-btn secondary" data-sm-v1-request-close>취소</button><button type="submit" class="sm-v1-request-btn">등록하기</button></div></form></div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', (event) => { if (event.target === modal || event.target.closest('[data-sm-v1-request-close]')) modal.classList.remove('is-open'); });
    modal.querySelector('form').addEventListener('submit', submitRequest);
    return modal;
  }

  async function submitRequest(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('[type="submit"]');
    const message = form.querySelector('#sm-v1-request-form-status');
    button.disabled = true; message.textContent = '등록 중입니다...';
    try {
      await apiFetch(API_CREATE, { method: 'POST', body: JSON.stringify({ title: form.querySelector('#sm-v1-request-title').value.trim(), content: form.querySelector('#sm-v1-request-content').value.trim() }) });
      form.reset(); message.textContent = '요청사항이 접수되었습니다.';
      setTimeout(() => { document.getElementById(MODAL_ID)?.classList.remove('is-open'); openPanel(); }, 450);
    } catch (error) { message.textContent = error.message; }
    finally { button.disabled = false; }
  }

  function tableHtml(items, adminMode) {
    if (adminMode) {
      const cards = items.map((item) => `
        <article class="sm-v1-request-admin-card" data-request-id="${Number(item.id)}">
          <div class="sm-v1-request-admin-top">
            <div>
              <strong>#${Number(item.id)} ${esc(item.title || '')}</strong>
              <div class="sm-v1-request-admin-meta">작성자: ${esc(item.username || '알 수 없음')} · ${esc(dateText(item.created_at))}</div>
            </div>
            ${statusBadge(item.status)}
          </div>
          <div class="sm-v1-request-admin-content">${esc(item.content || '')}</div>
          <div class="sm-v1-request-admin-answer">${clean(item.admin_note) ? `관리자 답변: ${esc(item.admin_note)}` : '관리자 답변 대기 중'}</div>
          <div class="sm-v1-request-admin-open">클릭하여 상태와 답변 수정</div>
        </article>
      `).join('');
      return `<div class="sm-v1-request-admin-list">${cards}</div>`;
    }

    const cols = '<th>번호</th><th>제목</th><th>등록일</th><th>상태</th><th>답변 여부</th>';
    const rows = items.map((item, index) => `<tr data-request-id="${Number(item.id)}"><td>${items.length - index}</td><td class="title">${esc(item.title || '')}</td><td>${esc(dateText(item.created_at))}</td><td>${statusBadge(item.status)}</td><td class="${clean(item.admin_note) ? 'sm-v1-answer-done' : 'sm-v1-answer-wait'}">${answerLabel(item)}</td></tr>`).join('');
    return `<div class="sm-v1-request-box"><div class="sm-v1-request-scroll"><table class="sm-v1-request-table"><thead><tr>${cols}</tr></thead><tbody>${rows}</tbody></table></div></div>`;
  }

  async function renderList(host) {
    const adminMode = isAdmin();
    host.innerHTML = `<div class="sm-v1-request-wrap"><div class="sm-v1-request-head"><div><h2>${adminMode ? '요청사항 관리' : '요청사항'}</h2><p>${adminMode ? '사용자가 등록한 요청을 확인하고 답변과 처리 상태를 관리합니다.' : '스토리 메이커 사용 중, 문의사항과 개선 요청을 등록합니다.'}</p></div><div class="sm-v1-request-actions">${adminMode ? '' : '<button class="sm-v1-request-btn" data-request-new>작성</button>'}<button class="sm-v1-request-btn secondary" data-request-refresh>새로고침</button></div></div><div data-request-list><div class="sm-v1-request-empty">요청사항을 불러오는 중입니다...</div></div></div>`;
    host.querySelector('[data-request-new]')?.addEventListener('click', () => ensureModal().classList.add('is-open'));
    host.querySelector('[data-request-refresh]')?.addEventListener('click', () => renderList(host));
    const list = host.querySelector('[data-request-list]');
    try {
      const payload = await apiFetch(adminMode ? API_ADMIN_LIST : API_MY_LIST);
      itemsCache = Array.isArray(payload?.data) ? payload.data : [];
      if (!itemsCache.length) { list.innerHTML = `<div class="sm-v1-request-box"><div class="sm-v1-request-empty">${adminMode ? '등록된 요청사항이 없습니다.' : '작성한 요청사항이 없습니다.'}</div></div>`; return; }
      list.innerHTML = tableHtml(itemsCache, adminMode);
      list.querySelectorAll('[data-request-id]').forEach((row) => row.addEventListener('click', () => renderDetail(host, Number(row.dataset.requestId))));
    } catch (error) { list.innerHTML = `<div class="sm-v1-request-box"><div class="sm-v1-request-empty">${esc(error.message)}</div></div>`; }
  }

  function renderDetail(host, requestId) {
    const item = itemsCache.find((row) => Number(row.id) === Number(requestId));
    if (!item) return renderList(host);
    const adminMode = isAdmin();
    host.innerHTML = `<div class="sm-v1-request-wrap"><div class="sm-v1-request-head"><div><h2>${adminMode ? '요청사항 상세' : '내 요청 상세'}</h2><p>목록을 벗어나지 않고 상세 내용을 확인합니다.</p></div><button class="sm-v1-request-btn secondary" data-request-back>목록으로</button></div><section class="sm-v1-detail"><h3 class="sm-v1-detail-title">${esc(item.title)}</h3><div class="sm-v1-detail-meta">${adminMode ? `<span>작성자: ${esc(item.username || '알 수 없음')}</span>` : ''}<span>등록일: ${esc(dateText(item.created_at))}</span><span>상태: ${statusBadge(item.status)}</span></div><div class="sm-v1-detail-section"><div class="sm-v1-detail-label">${adminMode ? '요청 본문' : '내 요청 내용'}</div><div class="sm-v1-detail-content">${esc(item.content || '')}</div></div>${adminMode ? adminFormHtml(item) : userAnswerHtml(item)}</section></div>`;
    host.querySelector('[data-request-back]').addEventListener('click', () => renderList(host));
    host.querySelector('[data-request-save]')?.addEventListener('click', () => saveAdminRequest(host, item));
  }

  function userAnswerHtml(item) {
    return `<div class="sm-v1-detail-section"><div class="sm-v1-detail-label">관리자 답변</div>${clean(item.admin_note) ? `<div class="sm-v1-answer-box">${esc(item.admin_note)}</div>` : '<div class="sm-v1-detail-content" style="min-height:auto;color:#94a3b8">아직 관리자 답변이 등록되지 않았습니다.</div>'}</div>`;
  }

  function adminFormHtml(item) {
    return `<div class="sm-v1-admin-form"><label>현재 상태<select data-request-status>${STATUSES.map((status) => `<option value="${status}" ${item.status === status ? 'selected' : ''}>${status}</option>`).join('')}</select></label><label class="full">관리자 답변<textarea data-request-note placeholder="사용자에게 표시할 답변을 입력하세요.">${esc(item.admin_note || '')}</textarea></label><div class="full sm-v1-request-actions" style="justify-content:flex-end"><button class="sm-v1-request-btn" data-request-save>답변 저장</button></div><div class="full sm-v1-request-message" data-request-message></div></div>`;
  }

  async function saveAdminRequest(host, item) {
    const button = host.querySelector('[data-request-save]');
    const message = host.querySelector('[data-request-message]');
    button.disabled = true; message.textContent = '저장 중입니다...';
    try {
      const payload = await apiFetch(`${API_ADMIN_LIST}/${Number(item.id)}`, { method: 'PUT', body: JSON.stringify({ status: host.querySelector('[data-request-status]').value, admin_note: host.querySelector('[data-request-note]').value.trim() || null }) });
      const updated = payload?.data || item;
      itemsCache = itemsCache.map((row) => Number(row.id) === Number(updated.id) ? updated : row);
      message.textContent = '답변과 상태가 저장되었습니다.';
      renderDetail(host, Number(updated.id));
      host.querySelector('[data-request-message]').textContent = '답변과 상태가 저장되었습니다.';
    } catch (error) { message.textContent = error.message; }
    finally { button.disabled = false; }
  }

  async function openPanel() {
    await resolveRole(true);
    const host = getInlineHost();
    if (!host) return;
    renderList(host);
    document.querySelectorAll('.sm-v1-request-menu').forEach((node) => node.classList.add('is-active'));
  }

  function findUsageItem() {
    const labels = ['업체 정보', '사용현황', '보관함', '체험 연구실', '릴스/숏츠', '팟캐스트', '딸깍 제작', '대시보드'];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const textNodes = [];
    let current;
    while ((current = walker.nextNode())) {
      const value = clean(current.nodeValue);
      if (labels.includes(value)) textNodes.push(current);
    }
    for (const wanted of labels) {
      const textNode = textNodes.find((node) => clean(node.nodeValue) === wanted);
      if (!textNode) continue;
      let node = textNode.parentElement;
      let best = null;
      while (node && node !== document.body) {
        const rect = node.getBoundingClientRect();
        const exactText = clean(node.textContent) === wanted;
        const inSidebar = rect.left >= 0 && rect.left < 320 && rect.right <= 340;
        const menuSized = rect.width >= 120 && rect.width <= 300 && rect.height >= 28 && rect.height <= 78;
        if (inSidebar && menuSized) best = node;
        if (exactText && inSidebar && menuSized && node.parentElement) {
          const parentRect = node.parentElement.getBoundingClientRect();
          if (parentRect.width >= 120 && parentRect.width <= 300 && parentRect.height >= 28 && parentRect.height <= 78) best = node.parentElement;
        }
        if (node.tagName === 'BUTTON' || node.tagName === 'A' || node.getAttribute('role') === 'button') {
          const clickableRect = node.getBoundingClientRect();
          if (clickableRect.left < 320 && clickableRect.width >= 120) best = node;
          break;
        }
        node = node.parentElement;
      }
      if (best) return { item: best, sourceText: wanted };
    }
    return null;
  }

  function ensureMenu() {
    if (document.getElementById(MENU_ID)) return true;
    const found = findUsageItem();
    if (!found) return false;
    const usageItem = found.item;
    const item = usageItem.cloneNode(true);
    item.id = MENU_ID;
    item.removeAttribute('href');
    item.querySelectorAll('[id]').forEach((el) => el.removeAttribute('id'));
    const textWalker = document.createTreeWalker(item, NodeFilter.SHOW_TEXT);
    let replaced = false;
    let clonedText;
    while ((clonedText = textWalker.nextNode())) {
      if (clean(clonedText.nodeValue) === found.sourceText) {
        clonedText.nodeValue = '요청사항';
        replaced = true;
        break;
      }
    }
    if (!replaced) item.textContent = '요청사항';
    item.classList.add('sm-v1-request-menu');
    item.addEventListener('click', (event) => { event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation(); openPanel(); }, true);
    usageItem.insertAdjacentElement('afterend', item);
    return true;
  }

  function ensureAdminShortcut() {
    document.getElementById(ADMIN_BUTTON_ID)?.remove();
  }

  async function boot() {
    ensureStyles(); ensureModal(); await resolveRole(); ensureAdminShortcut();
  }

  window.StoryMakerV1FeatureRequests = {
    open: openPanel,
    newRequest: () => ensureModal().classList.add('is-open'),
    refresh: boot,
  };
  const observer = new MutationObserver(() => { ensureAdminShortcut(); });
  observer.observe(document.documentElement, { childList: true, subtree: true });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true }); else boot();
})();
