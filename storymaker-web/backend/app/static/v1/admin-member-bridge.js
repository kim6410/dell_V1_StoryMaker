(() => {
  'use strict';

  if (window.__STORYMAKER_V1_ADMIN_MEMBER_INLINE__) return;
  window.__STORYMAKER_V1_ADMIN_MEMBER_INLINE__ = true;

  const MENU_LABEL = '\ud68c\uc6d0\uad00\ub9ac';
  const USAGE_LABEL = '\uc0ac\uc6a9\ud604\ud669';
  const PANEL_ID = 'storymaker-admin-member-panel';
  const MENU_MARK = 'data-storymaker-member-menu';
  const MENU_AUTH_MARK = 'data-storymaker-admin-authorized';

  document.querySelectorAll(`[${MENU_MARK}]`).forEach((node) => node.remove());

  let memberItems = [];
  let currentUserId = null;
  let currentPersonas = [];
  let adminRegionOptions = [];
  let adminAccess = false;

  function isAdminUser(user) {
    if (!user || typeof user !== 'object') return false;
    const role = clean(user.role || user.user_role || user.type).toLowerCase();
    return user.is_admin === true || user.admin === true || role === 'admin';
  }

  const STYLE_OPTIONS = ['Naver Blog', 'Tistory', 'Instagram', 'Threads', 'Brunch', 'WordPress'];
  const TONE_OPTIONS = ['professional', 'friendly', 'trustworthy', 'calm', 'witty', 'clear'];
  const INDUSTRY_OPTIONS = [
    ['general', 'General'], ['home_repair', 'Home repair'], ['boiler_facility', 'Boiler/facility'],
    ['appliance_clean', 'Appliance cleaning'], ['general_cleaning', 'Cleaning'], ['restaurant', 'Restaurant'],
    ['cafe', 'Cafe'], ['beauty_wellness', 'Beauty/wellness'], ['car_repair', 'Car repair'],
    ['pet_beauty_hotel', 'Pet'], ['real_estate', 'Real estate'], ['education_academy', 'Education'],
  ];

  const clean = (value = '') => String(value).replace(/\s+/g, ' ').trim();
  const esc = (value) => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

  function findTextElement(label) {
    return Array.from(document.querySelectorAll('button,a,div,span,p')).find(
      (el) => clean(el.textContent) === label && el.getBoundingClientRect().width > 40,
    );
  }

  function menuClickableFromLabel(labelEl) {
    let node = labelEl;
    while (node && node !== document.body) {
      const rect = node.getBoundingClientRect();
      const tag = node.tagName;
      if ((tag === 'BUTTON' || tag === 'A' || node.getAttribute('role') === 'button') && rect.width > 80) return node;
      if (rect.width > 120 && rect.height >= 34 && rect.height <= 90) return node;
      node = node.parentElement;
    }
    return labelEl;
  }

  function createMenu() {
    if (document.querySelector(`[${MENU_MARK}]`)) return true;
    const anchorLabels = [USAGE_LABEL, '요금제', '작업큐', '업종별 관리', '보관함'];
    const usageLabel = anchorLabels.map((label) => findTextElement(label)).find(Boolean);
    if (!usageLabel) return false;
    const usageItem = menuClickableFromLabel(usageLabel);
    const memberItem = usageItem.cloneNode(true);
    memberItem.setAttribute(MENU_MARK, '1');
    memberItem.setAttribute(MENU_AUTH_MARK, '1');
    memberItem.removeAttribute('href');
    memberItem.querySelectorAll('[id]').forEach((el) => el.removeAttribute('id'));
    const exact = Array.from(memberItem.querySelectorAll('*')).find((el) => clean(el.textContent) === USAGE_LABEL);
    if (exact) exact.textContent = MENU_LABEL;
    else memberItem.textContent = MENU_LABEL;
    memberItem.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      showPanel();
    }, true);
    usageItem.insertAdjacentElement('afterend', memberItem);
    return true;
  }

  function summaryCard(key, label, note) {
    return `<div class="sm-member-card"><div>${esc(label)}</div><strong data-member-summary="${esc(key)}">-</strong><small>${esc(note)}</small></div>`;
  }

  function panelHtml() {
    return `
      <style>
        #${PANEL_ID}{position:relative;width:100%;min-height:min(760px,calc(100vh - 210px));z-index:auto;background:transparent;color:#fff;overflow:visible;padding:0;font-family:inherit;box-sizing:border-box}
        #${PANEL_ID} *{box-sizing:border-box}.sm-member-wrap{width:100%;max-width:1740px;margin:0 auto;padding:0 8px 18px}
        .sm-member-head,.sm-member-box{border:1px solid rgba(103,232,249,.22);background:rgba(15,23,42,.92);border-radius:20px;padding:18px;box-shadow:0 20px 60px rgba(0,0,0,.2)}
        .sm-member-top{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}.sm-member-desc{font-size:15px;line-height:1.55;color:#cbd5e1;font-weight:800}
        .sm-member-close,.sm-action{border:1px solid rgba(148,163,184,.35);background:#0f172a;color:#e2e8f0;border-radius:12px;padding:9px 14px;font-weight:900;cursor:pointer}
        .sm-danger{border-color:rgba(248,113,113,.5);background:rgba(127,29,29,.35);color:#fecaca}.sm-primary{border-color:rgba(34,211,238,.55);background:rgba(8,145,178,.25);color:#a5f3fc}
        .sm-member-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin-top:14px}.sm-member-card{min-height:72px;border:1px solid #334155;background:rgba(2,6,23,.58);border-radius:14px;padding:12px 14px}
        .sm-member-card div{font-size:12px;font-weight:900;color:#94a3b8}.sm-member-card strong{display:inline-block;font-size:25px;line-height:1;margin-top:7px}.sm-member-card small{display:block;margin-top:5px;font-size:11px;color:#a5f3fc;font-weight:800}
        .sm-member-box{margin-top:12px;border-color:#334155}.sm-member-filters{display:grid;grid-template-columns:1fr 190px 190px auto auto;gap:10px}.sm-member-input{width:100%;border:1px solid #334155;background:#020617;color:#cbd5e1;border-radius:12px;padding:11px 13px;font-weight:800}
        .sm-member-toolbar{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:8px}.sm-member-table{width:100%;min-width:1120px;border-collapse:collapse}.sm-member-table th{background:rgba(2,6,23,.75);color:#94a3b8;font-size:12px;text-align:left;padding:11px 10px}.sm-member-table td{border-top:1px solid #1e293b;padding:14px 10px;text-align:center;color:#cbd5e1;font-weight:800;font-size:14px}.sm-member-table tr:hover{background:rgba(30,41,59,.32)}
        .sm-user-link{background:none;border:0;color:#fff;font-weight:900;cursor:pointer;text-decoration:underline;text-underline-offset:4px}.sm-check{width:17px;height:17px;cursor:pointer}.sm-scroll{overflow-x:auto}
        .sm-detail{position:fixed;inset:0;z-index:12000;display:flex;align-items:flex-start;justify-content:center;padding:28px;background:rgba(2,6,23,.78);overflow:auto}.sm-detail[hidden]{display:none}.sm-detail-card{width:min(1120px,calc(100vw - 56px));max-height:calc(100vh - 56px);overflow:auto;background:#0f172a;border:1px solid #334155;border-radius:20px;padding:22px;box-shadow:0 30px 90px rgba(0,0,0,.55)}
        .sm-detail-head{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:16px}.sm-detail-head h3{margin:0;font-size:22px}.sm-persona-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.sm-persona-item{border:1px solid #334155;background:#020617;border-radius:14px;padding:16px;cursor:pointer;color:#fff;text-align:left}.sm-persona-item strong{display:block;font-size:17px}.sm-persona-item small{display:block;margin-top:7px;color:#94a3b8}
        .sm-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.sm-field{display:flex;flex-direction:column;gap:6px}.sm-field.full{grid-column:1/-1}.sm-field label{font-size:12px;color:#94a3b8;font-weight:900}.sm-field input,.sm-field textarea,.sm-field select{border:1px solid #334155;background:#020617;color:#e2e8f0;border-radius:10px;padding:11px;font:inherit}.sm-field textarea{min-height:130px;resize:vertical}.sm-tone-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;border:1px solid #334155;background:#020617;border-radius:12px;padding:12px}.sm-tone-option{display:flex!important;align-items:center;gap:8px;border:1px solid #334155;border-radius:10px;padding:9px 10px;color:#cbd5e1!important;cursor:pointer}.sm-tone-option input{width:16px;height:16px;padding:0}.sm-detail-actions{display:flex;justify-content:flex-end;gap:9px;margin-top:16px;flex-wrap:wrap}.sm-user-meta{font-size:13px;color:#94a3b8;margin-bottom:14px}
        @media(max-width:1200px){.sm-member-grid{grid-template-columns:repeat(3,1fr)}.sm-member-filters{grid-template-columns:1fr 1fr}.sm-member-filters>*:first-child{grid-column:1/-1}}
        @media(max-width:700px){.sm-member-grid{grid-template-columns:repeat(2,1fr)}.sm-member-filters,.sm-form{grid-template-columns:1fr}}
      </style>
      <div class="sm-member-wrap">
        <div class="sm-member-head">
          <div class="sm-member-top">
            <div class="sm-member-desc">WordPress users and local StoryMaker users are shown together. This panel is embedded inside V1, not a popup.</div>
            <button class="sm-member-close" type="button">Close</button>
          </div>
          <div class="sm-member-grid">
            ${summaryCard('wordpress_linked_ids', 'WordPress linked IDs', 'from local DB')}
            ${summaryCard('storymaker_users', 'StoryMaker users', 'local DB')}
            ${summaryCard('linked_ids', 'Linked IDs', 'WP ID exists')}
            ${summaryCard('local_only', 'Local only', 'no WP ID')}
            ${summaryCard('wordpress_missing', 'WP missing', 'checked live')}
            ${summaryCard('persona_users', 'Persona users', 'business profile')}
          </div>
        </div>
        <div class="sm-member-box"><div class="sm-member-filters">
          <input id="sm-member-search" class="sm-member-input" placeholder="Search ID or username">
          <select id="sm-member-status" class="sm-member-input"><option value="all">All statuses</option><option value="linked_ok">Linked OK</option><option value="local_only">Local only</option><option value="wordpress_missing">WP missing</option><option value="wordpress_only">WordPress only</option></select>
          <select id="sm-member-persona" class="sm-member-input"><option value="all">All personas</option><option value="yes">Has persona</option><option value="no">No persona</option></select>
          <button id="sm-member-refresh" class="sm-action" type="button">Refresh</button>
          <button id="sm-member-delete" class="sm-action sm-danger" type="button">Delete selected</button>
        </div></div>
        <div class="sm-member-box">
          <div class="sm-member-toolbar"><div><strong>Integrated member list</strong><div id="sm-member-status-text" style="margin-top:5px;color:#94a3b8;font-size:13px;font-weight:800">Loading members.</div></div><div id="sm-selected-count" style="color:#a5f3fc;font-weight:900">0 selected</div></div>
          <div class="sm-scroll"><table class="sm-member-table"><thead><tr><th><input id="sm-check-all" class="sm-check" type="checkbox"></th><th>Status</th><th>WordPress</th><th>StoryMaker</th><th>WP ID</th><th>Local ID</th><th>Persona</th><th>Projects</th><th>Last login</th><th>Manage</th></tr></thead><tbody id="sm-member-tbody"><tr><td colspan="10">Loading.</td></tr></tbody></table></div>
        </div>
      </div>
      <div id="sm-member-detail" class="sm-detail" hidden><div class="sm-detail-card"><div class="sm-detail-head"><h3 id="sm-detail-title">My page</h3><button id="sm-detail-close" class="sm-action">Close</button></div><div id="sm-detail-body"></div></div></div>`;
  }

  function renderMembers() {
    const panel = document.getElementById(PANEL_ID);
    if (!panel) return;
    const search = clean(panel.querySelector('#sm-member-search')?.value).toLowerCase();
    const status = panel.querySelector('#sm-member-status')?.value || 'all';
    const persona = panel.querySelector('#sm-member-persona')?.value || 'all';
    const tbody = panel.querySelector('#sm-member-tbody');
    const filtered = memberItems.filter((item) => {
      const local = item.storymaker || {};
      const wp = item.wordpress || {};
      const primary = item.primary_persona || {};
      const haystack = `${local.id ?? ''} ${local.username ?? ''} ${wp.id ?? ''} ${wp.username ?? ''} ${primary.company_name ?? ''} ${primary.phone_number ?? ''} ${primary.region ?? ''} ${primary.industry_key ?? ''}`.toLowerCase();
      if (search && !haystack.includes(search)) return false;
      if (status !== 'all' && item.status !== status) return false;
      if (persona === 'yes' && Number(item.persona_count || 0) < 1) return false;
      if (persona === 'no' && Number(item.persona_count || 0) > 0) return false;
      return true;
    });
    panel.querySelector('#sm-member-status-text').textContent = `${filtered.length.toLocaleString()} / ${memberItems.length.toLocaleString()} users shown. WordPress link is kept.`;
    if (!filtered.length) {
      tbody.innerHTML = '<tr><td colspan="10">No matching members.</td></tr>';
      updateSelectedCount();
      return;
    }
    tbody.innerHTML = filtered.map((item) => {
      const local = item.storymaker || null;
      const wp = item.wordpress || {};
      const localId = local ? Number(local.id) : null;
      const statusText = item.status || '-';
      return `<tr>
        <td>${local ? `<input class="sm-check sm-row-check" type="checkbox" value="${localId}">` : ''}</td>
        <td>${esc(statusText)}</td>
        <td>${wp.username ? esc(wp.username) : '-'}</td>
        <td>${local ? `<button class="sm-user-link" data-user-id="${localId}">${esc(local.username || '-')}</button>` : '-'}</td>
        <td>${esc(wp.id ?? local?.wordpress_user_id ?? '-')}</td>
        <td>${esc(local?.id ?? '-')}</td>
        <td>${Number(item.persona_count || 0)}</td>
        <td>${Number(item.project_count || 0)}</td>
        <td>${esc(local?.last_login_at || '-')}</td>
        <td>${local ? `<button class="sm-action sm-primary" data-member-mypage-user-id="${localId}" data-member-key="local:${localId}">My page</button>` : '<span style="color:#64748b">WP only</span>'}</td>
      </tr>`;
    }).join('');
    updateSelectedCount();
  }

  function updateSelectedCount() {
    const panel = document.getElementById(PANEL_ID);
    if (!panel) return;
    const count = panel.querySelectorAll('.sm-row-check:checked').length;
    panel.querySelector('#sm-selected-count').textContent = `${count} selected`;
  }

  async function loadMembers() {
    const panel = document.getElementById(PANEL_ID);
    if (!panel) return;
    panel.querySelector('#sm-member-status-text').textContent = 'Loading WordPress + StoryMaker member data.';
    try {
      const response = await fetch('/v1-api/admin/members', {credentials: 'include', headers: {Accept: 'application/json'}});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) throw new Error(payload.detail || payload.message || `HTTP ${response.status}`);
      const data = payload.data || {};
      const summary = data.summary || {};
      panel.querySelectorAll('[data-member-summary]').forEach((el) => {
        const value = summary[el.dataset.memberSummary];
        el.textContent = value == null ? '-' : Number(value).toLocaleString();
      });
      memberItems = Array.isArray(data.items) ? data.items : [];
      renderMembers();
    } catch (error) {
      panel.querySelector('#sm-member-status-text').textContent = `Failed to load member data: ${error instanceof Error ? error.message : String(error)}`;
    }
  }

  async function ensureRegions() {
    if (adminRegionOptions.length) return;
    const response = await fetch('/v1-api/auth/regions', {credentials: 'include', headers: {Accept: 'application/json'}}).catch(() => null);
    if (!response) return;
    const payload = await response.json().catch(() => ({}));
    const rows = Array.isArray(payload?.data) ? payload.data : [];
    adminRegionOptions = rows.map((row) => String(row?.name || row?.label || row?.value || '').trim()).filter(Boolean);
  }


  async function loadBillingSummary(userId) {
    try {
      const response = await fetch(`/v1-api/admin/members/${Number(userId)}/billing-summary`, {credentials: 'include', headers: {Accept: 'application/json'}});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) throw new Error(payload.detail || payload.message || `HTTP ${response.status}`);
      return payload.data || null;
    } catch (error) {
      return {error: error instanceof Error ? error.message : String(error), readonly: true};
    }
  }

  function billingSummaryHtml(summary) {
    if (!summary) return '';
    if (summary.error) return `<div class="sm-member-box" style="margin:0 0 14px;border-color:rgba(248,113,113,.35)"><strong>과금 요약</strong><div class="sm-user-meta">불러오기 실패: ${esc(summary.error)}</div></div>`;
    const addon = summary.addon_allowed ? '가능' : '불가';
    const freeCredit = summary.free_signup_credit_given ? '지급완료' : '미지급';
    const plans = Array.isArray(summary.plans) ? summary.plans : [];
    return `<div class="sm-member-box sm-billing-box" data-billing-user-id="${Number(summary.user_id || currentUserId)}" style="margin:0 0 14px">
      <div class="sm-detail-head" style="margin-bottom:10px"><h3 style="margin:0">과금 요약</h3><span class="sm-badge">관리자</span></div>
      <div class="sm-member-cards" style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-bottom:10px">
        <div class="sm-member-card"><div>요금제</div><strong>${esc(summary.plan_name || summary.plan_code || '-')}</strong><small>${esc(summary.subscription_status || '-')}</small></div>
        <div class="sm-member-card"><div>기본 제공</div><strong>${Number(summary.base_video_credits || 0).toLocaleString()}회</strong><small>월 기준</small></div>
        <div class="sm-member-card"><div>잔여량</div><strong>${Number(summary.remaining_credits || 0).toLocaleString()}회</strong><small>사용 ${Number(summary.total_used || 0).toLocaleString()}회</small></div>
        <div class="sm-member-card"><div>Free 20회</div><strong>${esc(freeCredit)}</strong><small>추가충전 ${esc(addon)}</small></div>
      </div>
      <div class="sm-user-meta">이월 ${Number(summary.carryover_percent || 0)}% · 저장 ${Number(summary.storage_days || 0)}일 · 변경은 이 회원에게만 적용됩니다.</div>
      <div class="sm-member-toolbar" style="margin-top:12px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;align-items:center">
        <select class="sm-member-input" data-billing-plan>${plans.map((plan) => `<option value="${esc(plan.code)}" ${plan.code === summary.plan_code ? 'selected' : ''}>${esc(plan.name)} · ${Number(plan.base_video_credits || 0).toLocaleString()}회 · ${Number(plan.monthly_price_krw || 0).toLocaleString()}원</option>`).join('')}</select>
        <button type="button" class="sm-action" data-billing-change-plan>요금제 변경</button>
        <button type="button" class="sm-action" data-billing-free-credit ${summary.free_signup_credit_given ? 'disabled' : ''}" ${summary.free_signup_credit_given ? 'disabled' : ''}>무료 20회 지급</button>
        <button type="button" class="sm-action" data-billing-addon ${summary.addon_allowed ? '' : 'disabled'}" ${summary.addon_allowed ? '' : 'disabled'}>추가충전 30회</button>
      </div>
      <div class="sm-user-meta" data-billing-message style="margin-top:10px;color:#67e8f9"></div>
    </div>`;
  }


  async function refreshBillingBox(userId) {
    const summary = await loadBillingSummary(userId);
    const oldBox = document.querySelector('.sm-billing-box');
    if (oldBox) oldBox.outerHTML = billingSummaryHtml(summary);
    attachBillingHandlers();
  }

  async function postBillingAction(userId, url, options = {}) {
    const box = document.querySelector('.sm-billing-box');
    const message = box?.querySelector('[data-billing-message]');
    if (message) message.textContent = '처리 중입니다...';
    const response = await fetch(url, {credentials: 'include', headers: {'Content-Type': 'application/json', Accept: 'application/json'}, ...options});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) throw new Error(payload.detail || payload.message || `HTTP ${response.status}`);
    if (message) message.textContent = payload.message || '저장되었습니다.';
    await refreshBillingBox(userId);
  }

  function attachBillingHandlers() {
    const box = document.querySelector('.sm-billing-box');
    if (!box || box.dataset.bound === '1') return;
    box.dataset.bound = '1';
    const userId = Number(box.dataset.billingUserId || currentUserId);
    box.querySelector('[data-billing-free-credit]')?.addEventListener('click', async () => {
      try { await postBillingAction(userId, `/v1-api/admin/members/${userId}/billing/free-signup-credit`, {method: 'POST', body: '{}'}); }
      catch (error) { const m = box.querySelector('[data-billing-message]'); if (m) m.textContent = error.message; }
    });
    box.querySelector('[data-billing-change-plan]')?.addEventListener('click', async () => {
      const planCode = box.querySelector('[data-billing-plan]')?.value || 'free';
      try { await postBillingAction(userId, `/v1-api/admin/members/${userId}/billing/plan`, {method: 'PUT', body: JSON.stringify({plan_code: planCode})}); }
      catch (error) { const m = box.querySelector('[data-billing-message]'); if (m) m.textContent = error.message; }
    });
    box.querySelector('[data-billing-addon]')?.addEventListener('click', async () => {
      try { await postBillingAction(userId, `/v1-api/admin/members/${userId}/billing/addon-credit`, {method: 'POST', body: JSON.stringify({quantity: 30, price_krw: 4900})}); }
      catch (error) { const m = box.querySelector('[data-billing-message]'); if (m) m.textContent = error.message; }
    });
  }

  function prependBillingSummary(html, summary) {
    return billingSummaryHtml(summary) + html;
  }

  async function openUser(userId) {
    const panel = document.getElementById(PANEL_ID);
    const detail = panel?.querySelector('#sm-member-detail');
    const body = panel?.querySelector('#sm-detail-body');
    if (!detail || !body) throw new Error('Member detail area is missing.');
    currentUserId = userId;
    currentPersonas = [];
    detail.hidden = false;
    detail.removeAttribute('hidden');
    body.textContent = 'Loading my page data.';
    detail.scrollIntoView({block: 'nearest', behavior: 'smooth'});
    try {
      await ensureRegions();
      const response = await fetch(`/v1-api/admin/members/${userId}/personas`, {credentials: 'include', headers: {Accept: 'application/json'}});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) throw new Error(payload.detail || payload.message || `HTTP ${response.status}`);
      const data = payload.data || {};
      const billingSummary = await loadBillingSummary(userId);
      currentPersonas = Array.isArray(data.personas) ? data.personas : [];
      panel.querySelector('#sm-detail-title').textContent = `${data.user?.username || 'User'} 마이페이지`;
      if (!currentPersonas.length) {
        body.innerHTML = prependBillingSummary('<div class="sm-user-meta">No registered business persona.</div>', billingSummary);
        attachBillingHandlers();
      } else if (currentPersonas.length === 1) {
        renderPersonaForm(currentPersonas[0], data.user);
        body.insertAdjacentHTML('afterbegin', billingSummaryHtml(billingSummary));
        attachBillingHandlers();
      } else {
        renderPersonaChooser(data.user);
        body.insertAdjacentHTML('afterbegin', billingSummaryHtml(billingSummary));
        attachBillingHandlers();
      }
    } catch (error) {
      body.textContent = `Failed to load my page data: ${error instanceof Error ? error.message : String(error)}`;
    }
  }

  function renderPersonaChooser(user) {
    const body = document.getElementById('sm-detail-body');
    body.innerHTML = `<div class="sm-user-meta">Local ID ${esc(user?.id)} / WP ID ${esc(user?.wordpress_user_id ?? '-')}</div><div class="sm-persona-list">${currentPersonas.map((p) => `<button class="sm-persona-item" data-persona-id="${Number(p.id)}"><strong>${esc(p.company_name || 'No company name')}</strong><small>${esc(p.region || 'No region')} / ${esc(p.industry_key || 'No industry')}${p.is_default ? ' / default' : ''}</small></button>`).join('')}</div>`;
  }

  function renderPersonaForm(persona, user) {
    const body = document.getElementById('sm-detail-body');
    const tones = Array.isArray(persona.default_tones) ? persona.default_tones : [];
    const keywords = Array.isArray(persona.keywords) ? persona.keywords.join(', ') : '';
    body.innerHTML = `<div class="sm-mypage-kicker">MY PAGE</div><h2 class="sm-mypage-title">마이페이지</h2><div class="sm-mypage-summary"><div>사용자명: <strong>${esc(user?.username || '')}</strong></div><div>역할: <strong>${esc((user?.role || 'user') === 'admin' ? '관리자 (Admin)' : '일반 사용자')}</strong></div><div>회원 등급: <strong>${esc(user?.tier || 'free')}</strong></div><div>내 프로젝트 수: <strong>${Number(user?.project_count || 0).toLocaleString()}개</strong></div></div><div class="sm-mypage-tabs"><div class="sm-mypage-tab is-active">업체 페르소나 관리</div><div class="sm-mypage-tab">계정 및 연동 설정</div></div><section class="sm-mypage-section"><div class="sm-detail-head"><div><h3 style="margin:0">상세정보</h3><div class="sm-user-meta">관리자가 선택 회원의 정보를 직접 수정합니다. · Local ID ${esc(user?.id || currentUserId)} · Persona ID ${esc(persona.id)}</div></div></div><form id="sm-persona-form" class="sm-form">
        <div class="sm-field"><label>Company</label><input name="company_name" value="${esc(persona.company_name || '')}" required></div>
        <div class="sm-field"><label>Phone</label><input name="phone_number" value="${esc(persona.phone_number || '')}"></div>
        <div class="sm-field"><label>Website</label><input name="website_url" value="${esc(persona.website_url || '')}"></div>
        <div class="sm-field"><label>Region</label><select name="region" required><option value="">Select region</option>${adminRegionOptions.map((region) => `<option value="${esc(region)}" ${persona.region === region ? 'selected' : ''}>${esc(region)}</option>`).join('')}${persona.region && !adminRegionOptions.includes(persona.region) ? `<option value="${esc(persona.region)}" selected>${esc(persona.region)}</option>` : ''}</select></div>
        <div class="sm-field"><label>Industry</label><select name="industry_key" required><option value="">Select industry</option>${INDUSTRY_OPTIONS.map(([value, label]) => `<option value="${esc(value)}" ${persona.industry_key === value ? 'selected' : ''}>${esc(label)}</option>`).join('')}${persona.industry_key && !INDUSTRY_OPTIONS.some(([value]) => value === persona.industry_key) ? `<option value="${esc(persona.industry_key)}" selected>${esc(persona.industry_key)}</option>` : ''}</select></div>
        <div class="sm-field"><label>Default style</label><select name="default_style"><option value="">Select style</option>${STYLE_OPTIONS.map((style) => `<option value="${esc(style)}" ${persona.default_style === style ? 'selected' : ''}>${esc(style)}</option>`).join('')}</select></div>
        <div class="sm-field"><label>Blog length</label><select name="blog_content_length"><option value="1200" ${Number(persona.blog_content_length) === 1200 ? 'selected' : ''}>1200</option><option value="1500" ${Number(persona.blog_content_length) !== 1200 && Number(persona.blog_content_length) !== 2000 ? 'selected' : ''}>1500</option><option value="2000" ${Number(persona.blog_content_length) === 2000 ? 'selected' : ''}>2000</option></select></div>
        <div class="sm-field full"><label>Default tones</label><div class="sm-tone-grid">${TONE_OPTIONS.map((tone) => `<label class="sm-tone-option"><input type="checkbox" name="default_tones" value="${esc(tone)}" ${tones.includes(tone) ? 'checked' : ''}><span>${esc(tone)}</span></label>`).join('')}</div></div>
        <div class="sm-field full"><label>Keywords, comma separated</label><input name="keywords" value="${esc(keywords)}"></div>
        <div class="sm-field full"><label>Business detail</label><textarea name="content">${esc(persona.content || '')}</textarea></div>
        <div class="sm-field full"><label class="sm-tone-option"><input type="checkbox" name="is_default" value="1" ${persona.is_default ? 'checked' : ''}><span>Use as default business</span></label></div>
      </form>
      <div class="sm-detail-actions">${currentPersonas.length > 1 ? '<button id="sm-persona-back" class="sm-action">업체 선택</button>' : ''}<button id="sm-persona-cancel" class="sm-action">취소</button><button id="sm-persona-save" class="sm-action sm-primary" data-persona-id="${Number(persona.id)}">저장 / 수정</button><button id="sm-persona-close" class="sm-action">닫기</button></div></form></section>`;
  }

  async function savePersona(personaId) {
    const form = document.getElementById('sm-persona-form');
    if (!form) return;
    const data = new FormData(form);
    const split = (value) => String(value || '').split(',').map((part) => part.trim()).filter(Boolean);
    const body = {
      company_name: data.get('company_name'),
      phone_number: data.get('phone_number'),
      website_url: data.get('website_url'),
      region: data.get('region'),
      industry_key: data.get('industry_key'),
      default_style: data.get('default_style'),
      blog_content_length: Number(data.get('blog_content_length') || 1500),
      default_tones: data.getAll('default_tones').map(String),
      keywords: split(data.get('keywords')),
      content: data.get('content'),
      is_default: data.get('is_default') === '1',
    };
    const response = await fetch(`/v1-api/admin/members/${currentUserId}/personas/${personaId}`, {
      method: 'PUT',
      credentials: 'include',
      headers: {'Content-Type': 'application/json', Accept: 'application/json'},
      body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) throw new Error(payload.detail || payload.message || `HTTP ${response.status}`);
    await openUser(currentUserId);
    await loadMembers();
  }

  async function deleteSelected() {
    const panel = document.getElementById(PANEL_ID);
    const ids = Array.from(panel.querySelectorAll('.sm-row-check:checked')).map((el) => Number(el.value)).filter(Number.isFinite);
    if (!ids.length) {
      alert('Select members to delete.');
      return;
    }
    if (!confirm(`Delete ${ids.length} local StoryMaker account(s)? WordPress is only used as the linked source.`)) return;
    const response = await fetch('/v1-api/admin/users/bulk-delete', {
      method: 'POST',
      credentials: 'include',
      headers: {'Content-Type': 'application/json', Accept: 'application/json'},
      body: JSON.stringify({user_ids: ids}),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) throw new Error(payload.detail || payload.message || `HTTP ${response.status}`);
    panel.querySelector('#sm-check-all').checked = false;
    await loadMembers();
  }

  function showPanel() {
    const inlineBody = window.StoryMakerV1InlinePanels?.open?.('member', MENU_LABEL);
    let panel = document.getElementById(PANEL_ID);
    if (!panel) {
      panel = document.createElement('section');
      panel.id = PANEL_ID;
      panel.innerHTML = panelHtml();
      (inlineBody || document.body).appendChild(panel);

      panel.querySelector('.sm-member-close').addEventListener('click', hidePanel);
      panel.querySelector('#sm-member-search').addEventListener('input', renderMembers);
      panel.querySelector('#sm-member-status').addEventListener('change', renderMembers);
      panel.querySelector('#sm-member-persona').addEventListener('change', renderMembers);
      panel.querySelector('#sm-member-refresh').addEventListener('click', (event) => { event.preventDefault(); loadMembers(); });
      panel.querySelector('#sm-member-delete').addEventListener('click', () => deleteSelected().catch((error) => alert(error.message)));
      panel.querySelector('#sm-check-all').addEventListener('change', (event) => {
        panel.querySelectorAll('.sm-row-check').forEach((check) => { check.checked = event.target.checked; });
        updateSelectedCount();
      });
      panel.addEventListener('change', (event) => { if (event.target.classList.contains('sm-row-check')) updateSelectedCount(); });
      panel.addEventListener('click', (event) => {
        const personaBtn = event.target.closest('[data-persona-id]');
        if (personaBtn) {
          const persona = currentPersonas.find((item) => Number(item.id) === Number(personaBtn.dataset.personaId));
          if (persona) renderPersonaForm(persona, {id: currentUserId});
          return;
        }
        if (event.target.id === 'sm-persona-back') { renderPersonaChooser({id: currentUserId}); return; }
        if (event.target.id === 'sm-persona-cancel') { openUser(currentUserId); return; }
        if (event.target.id === 'sm-persona-close' || event.target.id === 'sm-detail-close') {
          panel.querySelector('#sm-member-detail').hidden = true;
          return;
        }
        if (event.target.id === 'sm-persona-save') {
          savePersona(Number(event.target.dataset.personaId)).catch((error) => alert(error.message));
          return;
        }
        const myPageBtn = event.target.closest('[data-member-mypage-user-id]');
        if (myPageBtn) {
          event.preventDefault();
          event.stopPropagation();
          openUser(Number(myPageBtn.dataset.memberMypageUserId)).catch((error) => alert(error instanceof Error ? error.message : String(error)));
          return;
        }
        const userBtn = event.target.closest('[data-user-id]');
        if (!userBtn) return;
        event.preventDefault();
        openUser(Number(userBtn.dataset.userId)).catch((error) => alert(error instanceof Error ? error.message : String(error)));
      });
    }

    if (inlineBody && panel.parentElement !== inlineBody) {
      inlineBody.innerHTML = '';
      inlineBody.appendChild(panel);
    }
    panel.style.display = 'block';
    panel.hidden = false;
    panel.removeAttribute('hidden');
    loadMembers();
  }

  function hidePanel() {
    const panel = document.getElementById(PANEL_ID);
    if (panel) {
      panel.style.display = 'none';
      panel.setAttribute('hidden', 'true');
    }
    window.StoryMakerV1InlinePanels?.close?.();
  }

  function removeMenu() {
    document.querySelectorAll(`[${MENU_MARK}]`).forEach((node) => node.remove());
    hidePanel();
  }

  async function checkUserRoleAndCreateMenu() {
    try {
      const response = await fetch(`/v1-api/auth/me?_=${Date.now()}`, {
        credentials: 'include',
        cache: 'no-store',
        headers: {Accept: 'application/json', 'Cache-Control': 'no-cache'},
      });
      const payload = await response.json().catch(() => ({}));
      const user = payload?.data?.user || payload?.user || payload?.data || payload;
      adminAccess = response.ok && isAdminUser(user);
    } catch {
      adminAccess = false;
    }
    if (adminAccess) createMenu();
    else removeMenu();
  }

  checkUserRoleAndCreateMenu();
  const observer = new MutationObserver(() => {
    if (adminAccess) createMenu();
    else document.querySelectorAll(`[${MENU_MARK}]`).forEach((node) => node.remove());
  });
  observer.observe(document.documentElement, {childList: true, subtree: true});
  console.info('[StoryMaker V1] admin member inline bridge active');
})();
