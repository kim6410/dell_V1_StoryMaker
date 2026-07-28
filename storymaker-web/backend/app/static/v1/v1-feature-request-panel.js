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
  let currentAdminFilter = 'all';
  let currentAdminSearch = '';
  let currentAdminPage = 1;
  let currentAdminComposing = false;
  const ADMIN_PAGE_SIZE = 10;

  const clean = (value = '') => String(value ?? '').replace(/\s+/g, ' ').trim();
  const esc = (value = '') => String(value)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const isAdmin = () => {
    if (!currentUser || typeof currentUser !== 'object') return false;
    const role = clean(currentUser.role || currentUser.user_role || currentUser.type).toLowerCase();
    return currentUser.is_admin === true || currentUser.admin === true || role === 'admin';
  };
  const displayStatus = (item) => clean(item?.admin_note) ? '완료' : (STATUSES.includes(item?.status) ? item.status : '접수');
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
      #storymaker-v1-inline-panel-host[data-panel-key="feature-requests"] .sm-v1-inline-title{font-size:20px!important}
      .sm-v1-request-wrap{width:100%;max-width:1740px;margin:0 auto;padding:10px 8px 24px;color:#e2e8f0;box-sizing:border-box}
      .sm-v1-request-head{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:16px;flex-wrap:wrap}
      .sm-v1-request-head h2{margin:0;font-size:24px;color:#f8fafc}.sm-v1-request-head p{margin:6px 0 0;color:#94a3b8;font-size:14px}
      .sm-v1-request-actions{display:flex;gap:9px;flex-wrap:wrap;align-items:center}
      .sm-v1-request-btn{border:1px solid rgba(56,189,248,.45);background:linear-gradient(135deg,#0284c7,#0ea5e9);color:#fff;border-radius:11px;padding:10px 15px;font-weight:900;cursor:pointer}
      .sm-v1-request-btn.secondary{background:#0f172a;border-color:rgba(148,163,184,.3);color:#e2e8f0}.sm-v1-request-btn:disabled{opacity:.55;cursor:wait}
      .sm-v1-request-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 12px;margin-bottom:10px;border:1px solid rgba(51,65,85,.72);border-radius:14px;background:rgba(15,23,42,.72);flex-wrap:wrap}
      .sm-v1-request-toolbar-left{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.sm-v1-request-total{font-size:13px;font-weight:900;color:#e2e8f0}
      .sm-v1-request-filter-group{display:flex;gap:6px;align-items:center}.sm-v1-request-filter{border:1px solid rgba(71,85,105,.8);background:#0f172a;color:#94a3b8;border-radius:999px;padding:6px 11px;font-size:12px;font-weight:900;cursor:pointer}
      .sm-v1-request-filter.is-active{border-color:rgba(34,211,238,.65);background:rgba(8,145,178,.18);color:#cffafe}.sm-v1-request-refresh-small{border:1px solid rgba(71,85,105,.8);background:#111827;color:#cbd5e1;border-radius:10px;padding:7px 10px;font-size:12px;font-weight:900;cursor:pointer}
      .sm-v1-request-search{display:flex;align-items:center;gap:8px;min-width:min(360px,100%);flex:1;max-width:520px}.sm-v1-request-search input{width:100%;height:38px;border:1px solid rgba(71,85,105,.8);border-radius:11px;background:#020617;color:#e2e8f0;padding:0 13px;font-size:12px;font-weight:750;outline:none}.sm-v1-request-search input:focus{border-color:#22d3ee;box-shadow:0 0 0 3px rgba(34,211,238,.1)}
      .sm-v1-request-admin-list{display:grid;gap:7px}
      .sm-v1-request-admin-card{background:linear-gradient(180deg,rgba(15,23,42,.96),rgba(10,18,34,.94));border:1px solid rgba(71,85,105,.72);border-radius:13px;padding:0;display:grid;box-shadow:0 7px 20px rgba(0,0,0,.12);overflow:hidden;transition:.15s}
      .sm-v1-request-admin-card:hover{border-color:rgba(56,189,248,.42);transform:translateY(-1px)}
      .sm-v1-request-admin-top{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:12px 14px;cursor:pointer}
      .sm-v1-request-admin-title{font-size:14px;color:#f8fafc;font-weight:950;line-height:1.45}.sm-v1-request-admin-meta{font-size:14px;color:#94a3b8;margin-top:4px;line-height:1.45}.sm-v1-request-author-link{border:0;background:transparent;color:#7dd3fc;padding:0;font:inherit;font-weight:900;cursor:pointer;text-decoration:underline;text-decoration-color:rgba(125,211,252,.45);text-underline-offset:3px}.sm-v1-request-author-link:hover{color:#cffafe;text-decoration-color:#67e8f9}
      .sm-v1-request-admin-body{display:none;padding:0 14px 12px;border-top:1px solid rgba(51,65,85,.55)}.sm-v1-request-admin-card.is-open .sm-v1-request-admin-body{display:grid;gap:8px;padding-top:11px}
      .sm-v1-request-section-label{font-size:10px;font-weight:950;letter-spacing:.08em;color:#64748b;text-transform:uppercase;margin-bottom:4px}
      .sm-v1-request-admin-content{white-space:pre-wrap;font-size:12px;line-height:1.65;color:#dbe7f3;background:rgba(2,6,23,.5);border:1px solid rgba(51,65,85,.48);padding:10px 11px;border-radius:9px}
      .sm-v1-request-admin-answer{font-size:12px;line-height:1.6;color:#a7f3d0;background:rgba(6,78,59,.18);border:1px solid rgba(52,211,153,.18);padding:9px 11px;border-radius:9px;white-space:pre-wrap}
      .sm-v1-request-admin-answer.is-wait{color:#94a3b8;background:rgba(15,23,42,.65);border-style:dashed;border-color:#475569}
      .sm-v1-request-admin-footer{display:flex;justify-content:flex-end}.sm-v1-request-admin-open{border:1px solid rgba(56,189,248,.32);background:rgba(14,165,233,.1);color:#7dd3fc;border-radius:9px;padding:7px 10px;font-size:11px;font-weight:900;cursor:pointer}
      .sm-v1-request-pagination{display:flex;align-items:center;justify-content:center;gap:6px;margin-top:12px}.sm-v1-request-page{min-width:34px;height:34px;border:1px solid rgba(71,85,105,.8);border-radius:9px;background:#0f172a;color:#94a3b8;font-size:12px;font-weight:900;cursor:pointer}.sm-v1-request-page.is-active{border-color:#22d3ee;background:rgba(8,145,178,.18);color:#cffafe}.sm-v1-request-page:disabled{opacity:.4;cursor:default}
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
      .sm-v1-detail{border:1px solid rgba(148,163,184,.2);background:linear-gradient(180deg,#0f172a,#0b1220);border-radius:18px;padding:22px}
      .sm-v1-detail-title{font-size:22px;font-weight:900;color:#fff;margin:0 0 10px}.sm-v1-detail-meta{display:flex;gap:10px;flex-wrap:wrap;color:#94a3b8;font-size:13px;margin-bottom:18px}
      .sm-v1-chat{display:flex;flex-direction:column;gap:18px;padding:20px 16px;border:1px solid rgba(51,65,85,.72);background:linear-gradient(180deg,rgba(15,23,42,.7),rgba(2,6,23,.82));border-radius:18px;min-height:260px}
      .sm-v1-chat-row{display:flex;align-items:flex-end;gap:10px}.sm-v1-chat-row.user{justify-content:flex-end}.sm-v1-chat-row.admin{justify-content:flex-start}
      .sm-v1-chat-avatar{display:grid;place-items:center;width:38px;height:38px;flex:0 0 38px;border-radius:50%;background:#115e59;color:#fff;font-size:12px;font-weight:950;box-shadow:0 6px 16px rgba(0,0,0,.25)}
      .sm-v1-chat-stack{display:flex;flex-direction:column;max-width:min(76%,760px)}.sm-v1-chat-row.user .sm-v1-chat-stack{align-items:flex-end}.sm-v1-chat-row.admin .sm-v1-chat-stack{align-items:flex-start}
      .sm-v1-chat-name{margin:0 3px 6px;color:#94a3b8;font-size:12px;font-weight:900}.sm-v1-chat-time{margin:6px 4px 0;color:#64748b;font-size:11px;font-weight:800}
      .sm-v1-chat-bubble{position:relative;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7;padding:14px 16px;border-radius:18px;font-size:15px;box-shadow:0 8px 24px rgba(0,0,0,.18)}
      .sm-v1-chat-row.user .sm-v1-chat-bubble{background:#facc15;color:#172033;border-bottom-right-radius:5px}
      .sm-v1-chat-row.admin .sm-v1-chat-bubble{background:#fff;color:#172033;border-bottom-left-radius:5px}
      .sm-v1-chat-wait{align-self:flex-start;color:#94a3b8;background:rgba(15,23,42,.9);border:1px dashed #475569;border-radius:15px;padding:13px 15px;font-size:13px}
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
    if (window.StoryMakerV1InlinePanels?.open) return window.StoryMakerV1InlinePanels.open('feature-requests', '사용자 요청');
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
      const cards = items.map((item) => {
        const hasAnswer = Boolean(clean(item.admin_note));
        return `
        <article class="sm-v1-request-admin-card" data-request-id="${Number(item.id)}">
          <div class="sm-v1-request-admin-top" data-request-toggle>
            <div>
              <div class="sm-v1-request-admin-title">#${Number(item.id)} ${esc(item.title || '')}</div>
              <div class="sm-v1-request-admin-meta">작성자 <button type="button" class="sm-v1-request-author-link" data-request-subscriber="${esc(item.username || '')}">${esc(item.username || '알 수 없음')}</button> · ${esc(dateText(item.created_at))}</div>
            </div>
            ${statusBadge(displayStatus(item))}
          </div>
          <div class="sm-v1-request-admin-body">
            <div>
              <div class="sm-v1-request-section-label">요청 본문</div>
              <div class="sm-v1-request-admin-content">${esc(item.content || '')}</div>
            </div>
            <div>
              <div class="sm-v1-request-section-label">관리자 답변</div>
              <div class="sm-v1-request-admin-answer${hasAnswer ? '' : ' is-wait'}">${hasAnswer ? esc(item.admin_note) : '답변 대기'}</div>
            </div>
            <div class="sm-v1-request-admin-footer"><button type="button" class="sm-v1-request-admin-open" data-request-edit>상태/답변 수정</button></div>
          </div>
        </article>
      `;
      }).join('');
      return `<div class="sm-v1-request-admin-list">${cards}</div>`;
    }

    const cols = '<th>번호</th><th>제목</th><th>등록일</th><th>상태</th>';
    const rows = items.map((item, index) => `<tr data-request-id="${Number(item.id)}"><td>${items.length - index}</td><td class="title">${esc(item.title || '')}</td><td>${esc(dateText(item.created_at))}</td><td>${statusBadge(displayStatus(item))}</td></tr>`).join('');
    return `<div class="sm-v1-request-box"><div class="sm-v1-request-scroll"><table class="sm-v1-request-table"><thead><tr>${cols}</tr></thead><tbody>${rows}</tbody></table></div></div>`;
  }

  async function renderList(host) {
    const adminMode = isAdmin();
    host.innerHTML = adminMode
      ? `<div class="sm-v1-request-wrap"><div data-request-toolbar></div><div data-request-list><div class="sm-v1-request-empty">요청사항을 불러오는 중입니다...</div></div></div>`
      : `<div class="sm-v1-request-wrap"><div class="sm-v1-request-head"><div><h2>요청사항</h2><p>스토리 메이커 사용 중, 문의사항과 개선 요청을 등록합니다.</p></div><div class="sm-v1-request-actions"><button class="sm-v1-request-btn" data-request-new>작성</button><button class="sm-v1-request-btn secondary" data-request-refresh>새로고침</button></div></div><div data-request-list><div class="sm-v1-request-empty">요청사항을 불러오는 중입니다...</div></div></div>`;
    host.querySelector('[data-request-new]')?.addEventListener('click', () => ensureModal().classList.add('is-open'));
    host.querySelector('[data-request-refresh]')?.addEventListener('click', () => renderList(host));
    const list = host.querySelector('[data-request-list]');
    const toolbar = host.querySelector('[data-request-toolbar]');

    const paintAdminList = () => {
      if (!adminMode || !toolbar) return;
      const total = itemsCache.length;
      const done = itemsCache.filter((item) => displayStatus(item) === '완료').length;
      const pending = total - done;
      toolbar.innerHTML = `<div class="sm-v1-request-toolbar">
        <div class="sm-v1-request-toolbar-left">
          <span class="sm-v1-request-total">전체 ${total}건</span>
          <div class="sm-v1-request-filter-group">
            <button type="button" class="sm-v1-request-filter ${currentAdminFilter === 'all' ? 'is-active' : ''}" data-request-filter="all">전체</button>
            <button type="button" class="sm-v1-request-filter ${currentAdminFilter === 'pending' ? 'is-active' : ''}" data-request-filter="pending">대기 ${pending}</button>
            <button type="button" class="sm-v1-request-filter ${currentAdminFilter === 'done' ? 'is-active' : ''}" data-request-filter="done">완료 ${done}</button>
          </div>
        </div>
        <div class="sm-v1-request-search"><input type="search" value="${esc(currentAdminSearch)}" placeholder="번호, 제목, 작성자, 본문, 답변 검색" data-request-search></div>
        <button type="button" class="sm-v1-request-refresh-small" data-request-refresh-small aria-label="요청사항 새로고침">↻ 새로고침</button>
      </div>`;
      const byStatus = currentAdminFilter === 'done'
        ? itemsCache.filter((item) => displayStatus(item) === '완료')
        : currentAdminFilter === 'pending'
          ? itemsCache.filter((item) => displayStatus(item) !== '완료')
          : itemsCache;
      const keyword = clean(currentAdminSearch).toLowerCase();
      const filtered = keyword ? byStatus.filter((item) => [item.id, item.title, item.username, item.content, item.admin_note].some((value) => String(value || '').toLowerCase().includes(keyword))) : byStatus;
      const totalPages = Math.max(1, Math.ceil(filtered.length / ADMIN_PAGE_SIZE));
      currentAdminPage = Math.min(Math.max(1, currentAdminPage), totalPages);
      const pageItems = filtered.slice((currentAdminPage - 1) * ADMIN_PAGE_SIZE, currentAdminPage * ADMIN_PAGE_SIZE);
      const pagination = filtered.length > ADMIN_PAGE_SIZE ? `<div class="sm-v1-request-pagination">
        <button type="button" class="sm-v1-request-page" data-request-page="prev" ${currentAdminPage === 1 ? 'disabled' : ''}>‹</button>
        ${Array.from({length: totalPages}, (_, index) => index + 1).map((page) => `<button type="button" class="sm-v1-request-page ${page === currentAdminPage ? 'is-active' : ''}" data-request-page="${page}">${page}</button>`).join('')}
        <button type="button" class="sm-v1-request-page" data-request-page="next" ${currentAdminPage === totalPages ? 'disabled' : ''}>›</button>
      </div>` : '';
      list.innerHTML = pageItems.length
        ? `${tableHtml(pageItems, true)}${pagination}`
        : '<div class="sm-v1-request-box"><div class="sm-v1-request-empty">검색 조건에 맞는 요청사항이 없습니다.</div></div>';
      toolbar.querySelectorAll('[data-request-filter]').forEach((button) => button.addEventListener('click', () => {
        currentAdminFilter = button.dataset.requestFilter || 'all';
        currentAdminPage = 1;
        paintAdminList();
      }));
      const searchInput = toolbar.querySelector('[data-request-search]');
      searchInput?.addEventListener('compositionstart', () => {
        currentAdminComposing = true;
      });
      searchInput?.addEventListener('compositionend', (event) => {
        currentAdminComposing = false;
        currentAdminSearch = event.target.value || '';
        currentAdminPage = 1;
        paintAdminList();
        const input = toolbar.querySelector('[data-request-search]');
        input?.focus();
        input?.setSelectionRange(currentAdminSearch.length, currentAdminSearch.length);
      });
      searchInput?.addEventListener('input', (event) => {
        if (currentAdminComposing || event.isComposing) return;
        currentAdminSearch = event.target.value || '';
        currentAdminPage = 1;
        paintAdminList();
        const input = toolbar.querySelector('[data-request-search]');
        input?.focus();
        input?.setSelectionRange(currentAdminSearch.length, currentAdminSearch.length);
      });
      toolbar.querySelector('[data-request-refresh-small]')?.addEventListener('click', () => renderList(host));
      list.querySelectorAll('[data-request-subscriber]').forEach((button) => button.addEventListener('click', async (event) => {
        event.preventDefault();
        event.stopPropagation();
        const username = button.dataset.requestSubscriber || '';
        try {
          const bridge = window.StoryMakerV1AdminMembers;
          if (!bridge?.openSubscriberDashboard) throw new Error('회원관리 연결 기능을 불러오지 못했습니다.');
          await bridge.openSubscriberDashboard(username);
        } catch (error) {
          alert(error instanceof Error ? error.message : String(error));
        }
      }));
      list.querySelectorAll('[data-request-toggle]').forEach((header) => header.addEventListener('click', () => {
        const card = header.closest('[data-request-id]');
        if (!card) return;
        const willOpen = !card.classList.contains('is-open');
        list.querySelectorAll('[data-request-id].is-open').forEach((openCard) => {
          if (openCard !== card) openCard.classList.remove('is-open');
        });
        card.classList.toggle('is-open', willOpen);
      }));
      list.querySelectorAll('[data-request-edit]').forEach((button) => button.addEventListener('click', (event) => {
        event.stopPropagation();
        renderDetail(host, Number(button.closest('[data-request-id]')?.dataset.requestId));
      }));
      list.querySelectorAll('[data-request-page]').forEach((button) => button.addEventListener('click', () => {
        const value = button.dataset.requestPage;
        currentAdminPage = value === 'prev' ? currentAdminPage - 1 : value === 'next' ? currentAdminPage + 1 : Number(value);
        paintAdminList();
      }));
    };

    try {
      const payload = await apiFetch(adminMode ? API_ADMIN_LIST : API_MY_LIST);
      itemsCache = Array.isArray(payload?.data) ? payload.data : [];
      if (adminMode) { paintAdminList(); return; }
      if (!itemsCache.length) { list.innerHTML = '<div class="sm-v1-request-box"><div class="sm-v1-request-empty">작성한 요청사항이 없습니다.</div></div>'; return; }
      list.innerHTML = tableHtml(itemsCache, false);
      list.querySelectorAll('[data-request-id]').forEach((row) => row.addEventListener('click', () => renderDetail(host, Number(row.dataset.requestId))));
    } catch (error) { list.innerHTML = `<div class="sm-v1-request-box"><div class="sm-v1-request-empty">${esc(error.message)}</div></div>`; }
  }

  function renderDetail(host, requestId) {
    const item = itemsCache.find((row) => Number(row.id) === Number(requestId));
    if (!item) return renderList(host);
    const adminMode = isAdmin();
    host.innerHTML = `<div class="sm-v1-request-wrap"><div class="sm-v1-request-head"><div><h2>${adminMode ? '요청사항 상세' : '내 요청 상세'}</h2><p>사용자와 관리자의 대화를 한눈에 확인합니다.</p></div><button class="sm-v1-request-btn secondary" data-request-back>목록으로</button></div><section class="sm-v1-detail"><h3 class="sm-v1-detail-title">${esc(item.title)}</h3><div class="sm-v1-detail-meta">${adminMode ? `<span>작성자: ${esc(item.username || '알 수 없음')}</span>` : ''}<span>등록일: ${esc(dateText(item.created_at))}</span><span>상태: ${statusBadge(displayStatus(item))}</span></div>${conversationHtml(item, adminMode)}${adminMode ? adminFormHtml(item) : ''}</section></div>`;
    host.querySelector('[data-request-back]').addEventListener('click', () => renderList(host));
    host.querySelector('[data-request-save]')?.addEventListener('click', () => saveAdminRequest(host, item));
  }

  function conversationHtml(item, adminMode) {
    const userName = adminMode ? esc(item.username || '사용자') : '나';
    const requestBubble = `<div class="sm-v1-chat-row user"><div class="sm-v1-chat-stack"><div class="sm-v1-chat-name">${userName}</div><div class="sm-v1-chat-bubble">${esc(item.content || '')}</div><div class="sm-v1-chat-time">${esc(dateText(item.created_at))}</div></div></div>`;
    const adminBubble = clean(item.admin_note)
      ? `<div class="sm-v1-chat-row admin"><div class="sm-v1-chat-avatar">관리자</div><div class="sm-v1-chat-stack"><div class="sm-v1-chat-name">스토리메이커 관리자</div><div class="sm-v1-chat-bubble">${esc(item.admin_note)}</div><div class="sm-v1-chat-time">${esc(dateText(item.updated_at))}</div></div></div>`
      : '<div class="sm-v1-chat-wait">관리자가 요청을 확인하고 있습니다. 답변이 등록되면 이곳에 대화 형태로 표시됩니다.</div>';
    return `<div class="sm-v1-chat">${requestBubble}${adminBubble}</div>`;
  }

  function adminFormHtml(item) {
    return `<div class="sm-v1-admin-form"><label>현재 상태<select data-request-status>${STATUSES.map((status) => `<option value="${status}" ${displayStatus(item) === status ? 'selected' : ''}>${status}</option>`).join('')}</select></label><label class="full">관리자 답변<textarea data-request-note placeholder="답변을 입력하고 저장하면 상태가 자동으로 완료로 변경됩니다.">${esc(item.admin_note || '')}</textarea></label><div class="full sm-v1-request-actions" style="justify-content:flex-end"><button class="sm-v1-request-btn" data-request-save>답변 저장</button></div><div class="full sm-v1-request-message" data-request-message></div></div>`;
  }

  async function saveAdminRequest(host, item) {
    const button = host.querySelector('[data-request-save]');
    const message = host.querySelector('[data-request-message]');
    button.disabled = true; message.textContent = '저장 중입니다...';
    try {
      const note = host.querySelector('[data-request-note]').value.trim();
      const selectedStatus = host.querySelector('[data-request-status]').value;
      const payload = await apiFetch(`${API_ADMIN_LIST}/${Number(item.id)}`, { method: 'PUT', body: JSON.stringify({ status: note ? '완료' : selectedStatus, admin_note: note || null }) });
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
        clonedText.nodeValue = '사용자 요청';
        replaced = true;
        break;
      }
    }
    if (!replaced) item.textContent = '사용자 요청';
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
    newRequest: (prefill = {}) => {
      const modal = ensureModal();
      const title = modal.querySelector('#sm-v1-request-title');
      const content = modal.querySelector('#sm-v1-request-content');
      const message = modal.querySelector('#sm-v1-request-form-status');
      if (title) title.value = clean(prefill.title || '');
      if (content) content.value = String(prefill.content || '').trim();
      if (message) message.textContent = '';
      modal.classList.add('is-open');
      setTimeout(() => title?.focus(), 30);
    },
    refresh: boot,
  };
  const observer = new MutationObserver(() => { ensureAdminShortcut(); });
  observer.observe(document.documentElement, { childList: true, subtree: true });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true }); else boot();
})();
