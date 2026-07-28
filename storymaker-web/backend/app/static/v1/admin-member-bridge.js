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
  let currentBillingSummary = null;
  let currentMemberUser = null;
  let adminRegionOptions = [];
  let adminAccess = false;

  function isAdminUser(user) {
    if (!user || typeof user !== 'object') return false;
    const role = clean(user.role || user.user_role || user.type).toLowerCase();
    const roles = Array.isArray(user.roles)
      ? user.roles.map((item) => clean(item).toLowerCase())
      : [];
    const isAdminFlag = user.is_admin === true
      || user.is_admin === 1
      || clean(user.is_admin).toLowerCase() === 'true';
    const adminFlag = user.admin === true
      || user.admin === 1
      || clean(user.admin).toLowerCase() === 'true';
    return isAdminFlag
      || adminFlag
      || role === 'admin'
      || role === 'administrator'
      || role === '관리자'
      || roles.includes('admin')
      || roles.includes('administrator')
      || clean(user.username).toLowerCase() === 'admin';
  }

  const STYLE_OPTIONS = ['Naver Blog', 'Tistory', 'Instagram', 'Threads', 'Brunch', 'WordPress'];
  const TONE_OPTIONS = ['professional', 'friendly', 'trustworthy', 'calm', 'witty', 'clear'];
  const INDUSTRY_OPTIONS = [
    ['general', '일반 업종'], ['home_repair', '집수리·인테리어'], ['boiler_facility', '보일러·설비'],
    ['appliance_clean', '가전 청소'], ['general_cleaning', '청소'], ['restaurant', '음식점'],
    ['cafe', '카페'], ['beauty_wellness', '미용·웰니스'], ['car_repair', '자동차 정비'],
    ['pet_beauty_hotel', '반려동물'], ['real_estate', '부동산'], ['education_academy', '교육·학원'],
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

  function visibleSidebarItems() {
    const selectors = [
      'aside button', 'aside a', 'aside [role="button"]',
      'nav button', 'nav a', 'nav [role="button"]',
      '[class*="sidebar"] button', '[class*="sidebar"] a',
      '[class*="side-bar"] button', '[class*="side-bar"] a',
    ];
    return Array.from(document.querySelectorAll(selectors.join(','))).filter((node) => {
      const rect = node.getBoundingClientRect();
      return rect.width > 100 && rect.height >= 34 && rect.height <= 96 && clean(node.textContent);
    });
  }

  function createMenu() {
    if (document.querySelector(`[${MENU_MARK}]`)) return true;
    const anchorLabels = [USAGE_LABEL, '요금제', '작업큐', '업종별 관리', '보관함'];
    const matchedLabel = anchorLabels.map((label) => findTextElement(label)).find(Boolean);
    const sidebarItems = visibleSidebarItems();
    const anchorItem = matchedLabel ? menuClickableFromLabel(matchedLabel) : sidebarItems[0];
    if (!anchorItem) return false;

    const memberItem = anchorItem.cloneNode(true);
    memberItem.setAttribute(MENU_MARK, '1');
    memberItem.setAttribute(MENU_AUTH_MARK, '1');
    memberItem.setAttribute('role', 'button');
    memberItem.setAttribute('tabindex', '0');
    memberItem.setAttribute('aria-label', MENU_LABEL);
    memberItem.removeAttribute('href');
    memberItem.querySelectorAll('[id]').forEach((el) => el.removeAttribute('id'));

    const labelNodes = Array.from(memberItem.querySelectorAll('*')).filter((el) => clean(el.textContent));
    const exact = labelNodes.find((el) => anchorLabels.includes(clean(el.textContent)));
    if (exact) exact.textContent = MENU_LABEL;
    else memberItem.textContent = MENU_LABEL;

    const openMemberPanel = (event) => {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      showPanel();
    };
    memberItem.addEventListener('click', openMemberPanel, true);
    memberItem.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') openMemberPanel(event);
    }, true);

    const matchedItem = matchedLabel ? menuClickableFromLabel(matchedLabel) : null;
    if (matchedItem?.parentElement) matchedItem.insertAdjacentElement('afterend', memberItem);
    else if (anchorItem.parentElement) anchorItem.parentElement.appendChild(memberItem);
    else return false;
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
        .sm-detail-head{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:16px}.sm-detail-head h3{margin:0;font-size:22px}.sm-detail-topbar{justify-content:flex-end}.sm-detail-hidden-title{display:none}.sm-detail-identity{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 12px}.sm-detail-identity h2{margin:0;font-size:29px;line-height:1.2}.sm-detail-identity-meta{color:#a5f3fc;font-size:14px;font-weight:900}.sm-persona-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.sm-persona-item{border:1px solid #334155;background:#020617;border-radius:14px;padding:16px;cursor:pointer;color:#fff;text-align:left}.sm-persona-item strong{display:block;font-size:17px}.sm-persona-item small{display:block;margin-top:7px;color:#94a3b8}
        .sm-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.sm-field{display:flex;flex-direction:column;gap:6px}.sm-field.full{grid-column:1/-1}.sm-field label{font-size:12px;color:#94a3b8;font-weight:900}.sm-field input,.sm-field textarea,.sm-field select{border:1px solid #334155;background:#020617;color:#e2e8f0;border-radius:10px;padding:11px;font:inherit}.sm-field textarea{min-height:130px;resize:vertical}.sm-tone-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;border:1px solid #334155;background:#020617;border-radius:12px;padding:12px}.sm-tone-option{display:flex!important;align-items:center;gap:8px;border:1px solid #334155;border-radius:10px;padding:9px 10px;color:#cbd5e1!important;cursor:pointer}.sm-tone-option input{width:16px;height:16px;padding:0}.sm-detail-actions{display:flex;justify-content:flex-end;gap:9px;margin-top:16px;flex-wrap:wrap}.sm-user-meta{font-size:13px;color:#94a3b8;margin-bottom:14px}
        .sm-detail-overview,.sm-mypage-section{border:1px solid #334155;background:linear-gradient(145deg,rgba(15,23,42,.96),rgba(2,6,23,.76));border-radius:20px;padding:20px;margin-bottom:16px;box-shadow:0 16px 40px rgba(0,0,0,.18)}.sm-detail-overview{border-color:rgba(34,211,238,.28)}.sm-detail-overview .sm-detail-head{margin-bottom:18px}.sm-detail-summary-grid{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;width:100%}.sm-detail-summary-grid>div{min-width:0;border:1px solid #334155;background:rgba(2,6,23,.86);border-radius:16px;padding:16px 17px;box-shadow:inset 0 1px 0 rgba(255,255,255,.025)}.sm-detail-summary-grid>div:first-child{border-color:rgba(59,130,246,.38)}.sm-detail-summary-grid>div:last-child{border-color:rgba(34,211,238,.34)}.sm-detail-summary-grid span{display:block;font-size:13px;line-height:1.3;font-weight:900;color:#94a3b8}.sm-detail-summary-grid strong{display:block;overflow-wrap:anywhere;margin-top:9px;font-size:20px;line-height:1.35;color:#f8fafc}.sm-field label em{font-style:normal;color:#fb7185}.sm-badge{display:inline-flex;align-items:center;border:1px solid rgba(103,232,249,.32);background:rgba(8,145,178,.14);color:#a5f3fc;border-radius:999px;padding:8px 13px;font-size:13px;font-weight:900}.sm-mypage-kicker{font-size:13px;font-weight:900;letter-spacing:.12em;color:#67e8f9}.sm-mypage-title{margin:6px 0 0;font-size:29px;line-height:1.2}.sm-mypage-section>.sm-detail-head{padding-bottom:14px;border-bottom:1px solid rgba(51,65,85,.7)}.sm-detail-card .sm-action{min-height:42px}.sm-detail-card .sm-primary{box-shadow:0 10px 30px rgba(8,145,178,.18)}.sm-usage-box{margin:0 0 14px;border:1px solid rgba(34,211,238,.24);background:linear-gradient(145deg,rgba(8,47,73,.28),rgba(2,6,23,.78));border-radius:18px;padding:18px}.sm-usage-head{display:flex;justify-content:space-between;align-items:flex-end;gap:14px;flex-wrap:wrap}.sm-usage-total{font-size:13px;color:#94a3b8;font-weight:900}.sm-usage-total strong{display:block;margin-top:5px;font-size:24px;color:#f8fafc}.sm-usage-chart{display:grid;grid-template-columns:repeat(14,minmax(24px,1fr));gap:7px;align-items:end;height:150px;margin-top:18px;padding:12px 10px 0;border-top:1px solid rgba(51,65,85,.65)}.sm-usage-day{display:flex;min-width:0;height:100%;flex-direction:column;align-items:center;justify-content:flex-end;gap:6px}.sm-usage-value{min-height:16px;font-size:11px;color:#a5f3fc;font-weight:900}.sm-usage-bar-wrap{display:flex;align-items:flex-end;width:100%;height:92px;border-radius:8px;background:rgba(15,23,42,.62);overflow:hidden}.sm-usage-bar{width:100%;min-height:3px;border-radius:8px 8px 0 0;background:linear-gradient(180deg,#67e8f9,#2563eb);box-shadow:0 0 18px rgba(34,211,238,.2)}.sm-usage-date{font-size:10px;color:#64748b;font-weight:800;white-space:nowrap}.sm-usage-empty{margin-top:14px;color:#94a3b8;font-size:13px;font-weight:800}
        @media(max-width:1200px){.sm-member-grid{grid-template-columns:repeat(3,1fr)}.sm-member-filters{grid-template-columns:1fr 1fr}.sm-member-filters>*:first-child{grid-column:1/-1}.sm-detail-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
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
      <div id="sm-member-detail" class="sm-detail" hidden><div class="sm-detail-card"><div class="sm-detail-head sm-detail-topbar"><h3 id="sm-detail-title" class="sm-detail-hidden-title">My page</h3><button id="sm-detail-close" class="sm-action">닫기</button></div><div id="sm-detail-body"></div></div></div>`;
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

  function formatKoreanDate(value) {
    const text = clean(value);
    if (!text || ['null', 'undefined', 'none'].includes(text.toLowerCase())) return '-';
    const match = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
    return match ? `${match[1]}.${match[2]}.${match[3]}` : text;
  }

  function formatKoreanDateTime(value) {
    const text = clean(value);
    if (!text) return '-';
    const match = text.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/);
    if (!match) return text;
    return `${match[1]}.${match[2]}.${match[3]}${match[4] ? ` ${match[4]}:${match[5]}` : ''}`;
  }

  function dateInputValue(value) {
    const text = clean(value);
    const match = text.match(/^(\d{4}-\d{2}-\d{2})/);
    return match ? match[1] : '';
  }

  function subscriptionDayLabel(value, mode) {
    const text = clean(value);
    if (!text || ['null', 'undefined', 'none'].includes(text.toLowerCase())) return '';
    const match = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!match) return '';
    const target = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    target.setHours(0, 0, 0, 0);
    const diff = Math.round((target.getTime() - today.getTime()) / 86400000);
    if (mode === 'elapsed') return `${Math.max(0, -diff)}일 경과`;
    return diff >= 0 ? `${diff}일 남음` : `${Math.abs(diff)}일 지남`;
  }

  function usageHistoryHtml(summary) {
    const rows = Array.isArray(summary?.daily_usage) ? summary.daily_usage : [];
    if (!rows.length) return '';
    const maxValue = Math.max(1, ...rows.map((row) => Number(row.used || 0) + Number(row.reserved || 0)));
    const totalUsed = rows.reduce((sum, row) => sum + Number(row.used || 0), 0);
    const totalReserved = rows.reduce((sum, row) => sum + Number(row.reserved || 0), 0);
    const bars = rows.map((row) => {
      const used = Number(row.used || 0);
      const reserved = Number(row.reserved || 0);
      const total = used + reserved;
      const height = total > 0 ? Math.max(8, Math.round((total / maxValue) * 92)) : 3;
      const dateText = String(row.date || '').slice(5).replace('-', '/');
      return `<div class="sm-usage-day" title="${esc(row.date)} · 사용 ${used}회${reserved ? ` · 진행 중 ${reserved}회` : ''}"><div class="sm-usage-value">${total || ''}</div><div class="sm-usage-bar-wrap"><div class="sm-usage-bar" style="height:${height}px;opacity:${total ? 1 : .22}"></div></div><div class="sm-usage-date">${esc(dateText)}</div></div>`;
    }).join('');
    return `<section class="sm-usage-box"><div class="sm-usage-head"><div><div class="sm-mypage-kicker">최근 14일 사용량</div></div><div class="sm-usage-total">실제 사용<strong>${totalUsed.toLocaleString()}회</strong>${totalReserved ? `<span>현재 제작 중 ${totalReserved.toLocaleString()}회</span>` : ''}</div></div><div class="sm-usage-chart" aria-label="최근 14일 날짜별 사용량 그래프">${bars}</div>${totalUsed === 0 && totalReserved === 0 ? '<div class="sm-usage-empty">최근 14일 동안 기록된 제작 사용량이 없습니다.</div>' : ''}</section>`;
  }

  function billingSummaryHtml(summary) {
    if (!summary) return '';
    if (summary.error) return `<div class="sm-member-box" style="margin:0 0 14px;border-color:rgba(248,113,113,.35)"><strong>과금 요약</strong><div class="sm-user-meta">불러오기 실패: ${esc(summary.error)}</div></div>`;
    const freeCredit = summary.free_signup_credit_given ? '지급 완료' : '미지급';
    const plans = (Array.isArray(summary.plans) ? summary.plans : []).filter((plan) => ['free', 'starter'].includes(String(plan.code || '').toLowerCase()));
    const isStarter = String(summary.plan_code || '').toLowerCase() === 'starter';
    const statusText = isStarter ? '유료 회원' : '무료 회원';
    const monthly = summary.monthly_credit || {};
    const periodStartRaw = summary.current_period_started_at;
    const periodEndRaw = summary.current_period_ends_at;
    const periodStart = formatKoreanDate(periodStartRaw);
    const periodEnd = formatKoreanDate(periodEndRaw);
    const periodElapsed = subscriptionDayLabel(periodStartRaw, 'elapsed');
    const periodRemaining = subscriptionDayLabel(periodEndRaw, 'remaining');
    const nextReset = formatKoreanDate(monthly.next_reset_at || summary.next_billing_at || summary.current_period_ends_at);
    const freeCycleStart = formatKoreanDate(monthly.period_start);
    const freeCycleEnd = formatKoreanDate(monthly.period_end);
    const monthlyGranted = Number(monthly.monthly_granted || 0);
    const monthlyUsed = Number(monthly.monthly_used || 0);
    const monthlyReserved = Number(monthly.monthly_reserved || 0);
    const monthlyRemaining = Number(monthly.monthly_remaining || 0);
    const bonusRemaining = Number(monthly.bonus_remaining || 0);
    const totalRemaining = Number(monthly.remaining ?? summary.remaining_credits ?? 0);
    const dailyUsage = Array.isArray(summary.daily_usage) ? summary.daily_usage : [];
    const recentUsage = dailyUsage.reduce((sum, row) => sum + Number(row.used || 0), 0);
    const betaUsage = summary.beta_usage || {};
    const todayUsage = Number(betaUsage.today || 0);
    const monthUsage = Number(betaUsage.month || 0);
    const totalUsage = Number(betaUsage.total || 0);
    const lastCompletedAt = betaUsage.last_completed_at || null;
    const billingDateValue = dateInputValue(summary.next_billing_at);
    return `<div class="sm-member-box sm-billing-box" data-billing-user-id="${Number(summary.user_id || currentUserId)}" style="margin:0 0 14px">
      <div class="sm-detail-head" style="margin-bottom:12px"><div><div class="sm-mypage-kicker">SUBSCRIBER DASHBOARD</div><h3 style="margin:6px 0 0">구독자 운영 대시보드</h3><div class="sm-user-meta" style="margin:5px 0 0">요금제, 구독기간, 제작 사용량을 한 화면에서 관리합니다.</div></div></div>
      <div class="sm-member-cards" style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:12px">
        <div class="sm-member-card"><div>현재 요금제</div><strong>${esc(isStarter ? 'Starter' : 'Free')}</strong><small>${isStarter ? '월 4,500원 · 구독 활성' : '무료 이용'}</small></div>
        <div class="sm-member-card"><div>오늘 제작</div><strong>${todayUsage.toLocaleString()}회</strong><small>MP4 생성 완료</small></div>
        <div class="sm-member-card"><div>이번 달 제작</div><strong>${monthUsage.toLocaleString()}회</strong><small>월 누적 사용량</small></div>
        <div class="sm-member-card"><div>구독 시작일</div><strong>${esc(periodStart)}</strong>${periodElapsed ? `<small>${esc(periodElapsed)}</small>` : ''}</div>
        <div class="sm-member-card"><div>구독 종료일</div><strong>${esc(periodEnd)}</strong>${periodRemaining ? `<small>${esc(periodRemaining)}</small>` : ''}</div>
        <div class="sm-member-card"><div>마지막 제작</div><strong>${esc(formatKoreanDateTime(lastCompletedAt))}</strong><small>누적 제작완료 ${totalUsage.toLocaleString()}건</small></div>
      </div>
      ${isStarter ? '' : `<div class="sm-subscription-period" style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:0 0 12px"><div class="sm-member-card"><div>월 제공량</div><strong>${monthlyGranted.toLocaleString()}회</strong><small>무료 월 기본량</small></div><div class="sm-member-card"><div>월 잔여량</div><strong>${monthlyRemaining.toLocaleString()}회</strong><small>이번 이용기간 잔여</small></div><div class="sm-member-card"><div>추가 지급 잔여</div><strong>${bonusRemaining.toLocaleString()}회</strong><small>관리자 추가 지급분</small></div><div class="sm-member-card"><div>다음 리셋일</div><strong>${esc(nextReset)}</strong><small>${esc(freeCycleStart)} ~ ${esc(freeCycleEnd)}</small></div></div>`}
      ${usageHistoryHtml(summary)}
      <div class="sm-member-toolbar" style="margin-top:12px;display:grid;grid-template-columns:minmax(240px,1fr) auto minmax(190px,240px) auto;gap:10px;align-items:end">
        <label style="display:flex;flex-direction:column;gap:6px;font-size:12px;font-weight:900;color:#94a3b8">요금제<select class="sm-member-input" data-billing-plan>${plans.map((plan) => `<option value="${esc(plan.code)}" ${plan.code === summary.plan_code ? 'selected' : ''}>${String(plan.code).toLowerCase() === 'starter' ? 'Starter · 월 4,500원' : 'Free · 0원'}</option>`).join('')}</select></label>
        <button type="button" class="sm-action sm-primary" data-billing-change-plan>요금제 변경</button>
        <label style="display:flex;flex-direction:column;gap:6px;font-size:12px;font-weight:900;color:#94a3b8">결제일<input type="date" class="sm-member-input" data-billing-date value="${esc(billingDateValue)}"></label>
        <button type="button" class="sm-action sm-primary" data-billing-save-date>결제일 저장</button>
        <button type="button" class="sm-action" data-billing-free-credit ${isStarter ? 'disabled' : ''}" ${isStarter ? 'disabled' : ''} style="grid-column:1/-1;${isStarter ? 'display:none' : ''}">무료 20회 추가 지급</button>
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
      if (!confirm('이 무료 회원에게 이용권 20회를 추가 지급하시겠습니까?')) return;
      try { await postBillingAction(userId, `/v1-api/admin/members/${userId}/billing/free-bonus-credit`, {method: 'POST', body: '{}'}); }
      catch (error) { const m = box.querySelector('[data-billing-message]'); if (m) m.textContent = error.message; }
    });
    box.querySelector('[data-billing-change-plan]')?.addEventListener('click', async () => {
      const planCode = box.querySelector('[data-billing-plan]')?.value || 'free';
      try { await postBillingAction(userId, `/v1-api/admin/members/${userId}/billing/plan`, {method: 'PUT', body: JSON.stringify({plan_code: planCode})}); }
      catch (error) { const m = box.querySelector('[data-billing-message]'); if (m) m.textContent = error.message; }
    });
    box.querySelector('[data-billing-save-date]')?.addEventListener('click', async () => {
      const billingDate = box.querySelector('[data-billing-date]')?.value || '';
      if (!billingDate) { const m = box.querySelector('[data-billing-message]'); if (m) m.textContent = '결제일을 선택해 주세요.'; return; }
      try { await postBillingAction(userId, `/v1-api/admin/members/${userId}/billing/date`, {method: 'PUT', body: JSON.stringify({billing_date: billingDate})}); }
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
    body.textContent = '회원 상세정보를 불러오는 중입니다.';
    detail.scrollIntoView({block: 'nearest', behavior: 'smooth'});
    try {
      await ensureRegions();
      const response = await fetch(`/v1-api/admin/members/${userId}/personas`, {credentials: 'include', headers: {Accept: 'application/json'}});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) throw new Error(payload.detail || payload.message || `HTTP ${response.status}`);
      const data = payload.data || {};
      const billingSummary = await loadBillingSummary(userId);
      currentBillingSummary = billingSummary;
      currentMemberUser = data.user || null;
      currentPersonas = Array.isArray(data.personas) ? data.personas : [];
      const detailTitle = panel.querySelector('#sm-detail-title');
      if (detailTitle) {
        detailTitle.textContent = '';
        detailTitle.style.display = 'none';
      }
      if (!currentPersonas.length) {
        body.innerHTML = prependBillingSummary('<div class="sm-user-meta">No registered business persona.</div>', billingSummary);
        attachBillingHandlers();
      } else if (currentPersonas.length === 1) {
        renderPersonaForm(currentPersonas[0], data.user, billingSummary);
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

  function renderPersonaForm(persona, user, billingSummary = currentBillingSummary) {
    const body = document.getElementById('sm-detail-body');
    const tones = Array.isArray(persona.default_tones) ? persona.default_tones : [];
    const keywords = Array.isArray(persona.keywords) ? persona.keywords.join(', ') : '';
    const roleText = (user?.role || 'user') === 'admin' ? '관리자' : '일반 사용자';
    const billingPlanCode = String(billingSummary?.plan_code || user?.tier || 'free').toLowerCase();
    const billingPlanName = String(billingSummary?.plan_name || billingPlanCode || 'Free');
    const tierText = (user?.role || 'user') === 'admin' ? '관리자' : (billingPlanCode !== 'free' ? `유료 · ${billingPlanName}` : '무료');
    const betaUsage = billingSummary?.beta_usage || {};
    body.innerHTML = `<section class="sm-detail-overview">
      <div class="sm-detail-head"><div><div class="sm-mypage-kicker">회원 상세정보</div><div class="sm-detail-identity"><h2>${esc(user?.username || '회원')}</h2><span class="sm-detail-identity-meta">/ ${esc(persona.company_name || '업체 미등록')} / ${esc(persona.region || '지역 미등록')} / ${esc(persona.phone_number || '전화번호 미등록')}</span></div></div><span class="sm-badge">회원번호 ${esc(user?.id || currentUserId)}</span></div>
      <div class="sm-mypage-summary sm-detail-summary-grid" style="grid-template-columns:repeat(3,minmax(0,1fr))">
        <div><span>계정 상태</span><strong>정상</strong></div>
        <div><span>권한</span><strong>${esc(roleText)}</strong></div>
        <div><span>가입일</span><strong>${esc(formatKoreanDate(user?.created_at))}</strong></div>
        <div><span>마지막 로그인</span><strong>${esc(formatKoreanDateTime(user?.last_login_at))}</strong></div>
        <div><span>누적 제작완료</span><strong>${Number(betaUsage.total || user?.project_count || 0).toLocaleString()}건</strong></div>
        <div><span>대표 업체</span><strong>${esc(persona.company_name || '업체 미등록')}</strong></div>
      </div>
    </section>
    ${billingSummaryHtml(billingSummary)}
    <section class="sm-mypage-section"><div class="sm-detail-head"><div><h3 style="margin:0">대표 업체정보</h3></div></div><form id="sm-persona-form" class="sm-form">
        <div class="sm-field"><label>업체명 <em>*</em></label><input name="company_name" value="${esc(persona.company_name || '')}" required></div>
        <div class="sm-field"><label>전화번호 <em>*</em></label><input name="phone_number" value="${esc(persona.phone_number || '')}" required></div>
        <div class="sm-field"><label>홈페이지/SNS</label><input name="website_url" value="${esc(persona.website_url || '')}" placeholder="홈페이지, 블로그 또는 SNS 주소"></div>
        <div class="sm-field"><label>지역 <em>*</em></label><select name="region" required><option value="">지역을 선택해 주세요</option>${adminRegionOptions.map((region) => `<option value="${esc(region)}" ${persona.region === region ? 'selected' : ''}>${esc(region)}</option>`).join('')}${persona.region && !adminRegionOptions.includes(persona.region) ? `<option value="${esc(persona.region)}" selected>${esc(persona.region)}</option>` : ''}</select></div>
        <div class="sm-field"><label>업종 <em>*</em></label><select name="industry_key" required><option value="">업종을 선택해 주세요</option>${INDUSTRY_OPTIONS.map(([value, label]) => `<option value="${esc(value)}" ${persona.industry_key === value ? 'selected' : ''}>${esc(label)}</option>`).join('')}${persona.industry_key && !INDUSTRY_OPTIONS.some(([value]) => value === persona.industry_key) ? `<option value="${esc(persona.industry_key)}" selected>${esc(persona.industry_key)}</option>` : ''}</select></div>
        <div class="sm-field"><label>기본 작성 채널</label><select name="default_style"><option value="">작성 채널을 선택해 주세요</option>${STYLE_OPTIONS.map((style) => `<option value="${esc(style)}" ${persona.default_style === style ? 'selected' : ''}>${esc(style)}</option>`).join('')}</select></div>
        <div class="sm-field"><label>블로그 글 길이</label><select name="blog_content_length"><option value="1200" ${Number(persona.blog_content_length) === 1200 ? 'selected' : ''}>1,200자</option><option value="1500" ${Number(persona.blog_content_length) !== 1200 && Number(persona.blog_content_length) !== 2000 ? 'selected' : ''}>1,500자</option><option value="2000" ${Number(persona.blog_content_length) === 2000 ? 'selected' : ''}>2,000자</option></select></div>
        <div class="sm-field"><label>업체정보 등록일</label><input value="${esc(formatKoreanDateTime(persona.created_at))}" readonly></div>
        <div class="sm-field"><label>업체정보 최종 수정</label><input value="${esc(formatKoreanDateTime(persona.updated_at))}" readonly></div>
        <div class="sm-field full"><label>기본 감성 톤</label><div class="sm-tone-grid">${TONE_OPTIONS.map((tone) => `<label class="sm-tone-option"><input type="checkbox" name="default_tones" value="${esc(tone)}" ${tones.includes(tone) ? 'checked' : ''}><span>${esc(tone)}</span></label>`).join('')}</div></div>
        <div class="sm-field full"><label>핵심 키워드 <em>*</em></label><input name="keywords" value="${esc(keywords)}" placeholder="쉼표로 구분해 입력해 주세요" required></div>
        <div class="sm-field full"><label>페르소나 상세 설명 <em>*</em></label><textarea name="content" placeholder="경력, 전문 분야, 고객층, 차별점, 말투를 상세하게 입력해 주세요" required>${esc(persona.content || '')}</textarea></div>
        <div class="sm-field full"><label class="sm-tone-option"><input type="checkbox" name="is_default" value="1" ${persona.is_default ? 'checked' : ''}><span>대표 업체로 사용</span></label></div>
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
    const requiredChecks = [
      ['업체명', body.company_name],
      ['전화번호', body.phone_number],
      ['지역', body.region],
      ['업종', body.industry_key],
      ['핵심 키워드', body.keywords.length ? 'ok' : ''],
      ['페르소나 상세 설명', String(body.content || '').trim().length >= 10 ? 'ok' : ''],
    ];
    const missing = requiredChecks.filter(([, value]) => !String(value || '').trim()).map(([label]) => label);
    if (missing.length) throw new Error(`필수정보를 확인해 주세요: ${missing.join(', ')}`);
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
      alert('삭제할 회원을 선택해 주세요.');
      return;
    }
    if (!confirm(`선택한 ${ids.length}명의 StoryMaker 회원을 삭제하시겠습니까?\n\nWordPress 계정은 삭제하지 않고 StoryMaker 로컬 계정만 삭제합니다.`)) return;
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
        if (event.target.id === 'sm-member-detail') {
          event.target.hidden = true;
          return;
        }
        const saveButton = event.target.closest('#sm-persona-save');
        if (saveButton) {
          event.preventDefault();
          event.stopPropagation();
          const originalText = saveButton.textContent;
          saveButton.disabled = true;
          saveButton.textContent = '저장 중...';
          savePersona(Number(saveButton.dataset.personaId))
            .then(() => {
              saveButton.textContent = '저장 완료';
            })
            .catch((error) => {
              saveButton.disabled = false;
              saveButton.textContent = originalText;
              alert(error instanceof Error ? error.message : String(error));
            });
          return;
        }
        const personaBtn = event.target.closest('.sm-persona-item[data-persona-id]');
        if (personaBtn) {
          const persona = currentPersonas.find((item) => Number(item.id) === Number(personaBtn.dataset.personaId));
          if (persona) renderPersonaForm(persona, currentMemberUser || {id: currentUserId}, currentBillingSummary);
          return;
        }
        if (event.target.id === 'sm-persona-back') { renderPersonaChooser({id: currentUserId}); return; }
        if (event.target.id === 'sm-persona-cancel') { openUser(currentUserId); return; }
        if (event.target.id === 'sm-persona-close' || event.target.id === 'sm-detail-close') {
          panel.querySelector('#sm-member-detail').hidden = true;
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

  function closeMemberPanelOnOtherSidebarMenu(event) {
    const panel = document.getElementById(PANEL_ID);
    if (!panel || panel.hidden || panel.style.display === 'none') return;

    const target = event.target instanceof Element ? event.target : null;
    const clicked = target?.closest('button,a,[role="button"]');
    if (!clicked || clicked.hasAttribute(MENU_MARK) || clicked.closest(`#${PANEL_ID}`)) return;

    const nav = clicked.closest('nav');
    const rect = clicked.getBoundingClientRect?.();
    const isLeftSidebar = Boolean(nav) || Boolean(rect && rect.left >= 0 && rect.right <= 420 && rect.height >= 24);
    if (!isLeftSidebar) return;

    hidePanel();
  }

  document.addEventListener('click', closeMemberPanelOnOtherSidebarMenu, true);

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
  window.addEventListener('storymaker-auth-changed', () => {
    checkUserRoleAndCreateMenu();
  });
  const observer = new MutationObserver(() => {
    if (adminAccess) createMenu();
    else document.querySelectorAll(`[${MENU_MARK}]`).forEach((node) => node.remove());
  });
  observer.observe(document.documentElement, {childList: true, subtree: true});
  console.info('[StoryMaker V1] admin member inline bridge active');
})();
