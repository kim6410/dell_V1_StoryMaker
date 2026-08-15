(() => {
  'use strict';

  if (window.__STORYMAKER_V1_ADMIN_BILLING_PANEL__) return;
  window.__STORYMAKER_V1_ADMIN_BILLING_PANEL__ = true;

  const MENU_ID = 'storymaker-v1-admin-billing-menu';
  const PANEL_ID = 'storymaker-v1-admin-billing-panel';
  let adminAccess = false;
  let members = [];

  const clean = (value = '') => String(value).replace(/\s+/g, ' ').trim();
  const esc = (value = '') => String(value)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

  function detectAdmin(user) {
    if (!user || typeof user !== 'object') return false;
    const role = clean(user.role || user.user_role || user.type).toLowerCase();
    return user.is_admin === true || user.admin === true || role === 'admin';
  }

  async function api(url, options = {}) {
    const response = await fetch(url, {
      credentials: 'include',
      headers: {'Content-Type': 'application/json', Accept: 'application/json', ...(options.headers || {})},
      ...options,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload?.ok === false) {
      throw new Error(payload?.detail || payload?.message || `HTTP ${response.status}`);
    }
    return payload;
  }

  function ensureStyle() {
    if (document.getElementById('storymaker-v1-admin-billing-style')) return;
    const style = document.createElement('style');
    style.id = 'storymaker-v1-admin-billing-style';
    style.textContent = `
      .v1ab-wrap{width:100%;max-width:1740px;margin:0 auto;padding:10px 8px 28px;color:#e2e8f0}
      .v1ab-head,.v1ab-box,.v1ab-detail{border:1px solid rgba(103,232,249,.2);background:rgba(15,23,42,.92);border-radius:20px;padding:18px;margin-bottom:12px}
      .v1ab-top{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}
      .v1ab-title{margin:0;font-size:25px;color:#fff}.v1ab-sub{margin:7px 0 0;color:#94a3b8;font-size:14px}
      .v1ab-btn{border:1px solid rgba(148,163,184,.35);background:#0f172a;color:#e2e8f0;border-radius:11px;padding:9px 13px;font-weight:900;cursor:pointer}
      .v1ab-btn.primary{border-color:rgba(34,211,238,.55);background:rgba(8,145,178,.25);color:#a5f3fc}
      .v1ab-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:14px}
      .v1ab-card{border:1px solid #334155;background:#020617;border-radius:14px;padding:14px}.v1ab-card span{display:block;color:#94a3b8;font-size:12px;font-weight:900}.v1ab-card strong{display:block;margin-top:7px;font-size:22px;color:#fff}
      .v1ab-filter{display:flex;gap:9px;flex-wrap:wrap}.v1ab-input{border:1px solid #334155;background:#020617;color:#e2e8f0;border-radius:11px;padding:10px 12px;font:inherit}
      .v1ab-scroll{overflow-x:auto}.v1ab-table{width:100%;min-width:900px;border-collapse:collapse}.v1ab-table th,.v1ab-table td{padding:12px 10px;border-bottom:1px solid #263449;text-align:left}.v1ab-table th{color:#94a3b8;font-size:12px}.v1ab-table td{font-size:13px}
      .v1ab-link{border:0;background:none;color:#7dd3fc;font-weight:900;cursor:pointer;text-decoration:underline}.v1ab-detail[hidden]{display:none!important}.v1ab-actions{display:flex;gap:9px;flex-wrap:wrap;margin-top:16px}.v1ab-state{color:#94a3b8;padding:12px 0}.v1ab-wallet{display:flex;justify-content:space-between;gap:12px;border:1px solid #334155;background:#020617;border-radius:12px;padding:12px;margin-top:8px}
      @media(max-width:800px){.v1ab-grid{grid-template-columns:1fr 1fr}}
    `;
    document.head.appendChild(style);
  }

  function sidebarSource() {
    const labels = ['회원관리', '요청사항 관리', '요청사항', '사용현황'];
    for (const label of labels) {
      const node = Array.from(document.querySelectorAll('button,a,[role="button"],li,div')).find((el) => {
        const rect = el.getBoundingClientRect();
        return clean(el.textContent) === label && rect.left < 320 && rect.width > 100 && rect.height >= 28 && rect.height < 90;
      });
      if (node) return node.closest('button,a,[role="button"],li') || node;
    }
    return null;
  }

  function ensureMenu() {
    if (!adminAccess || document.getElementById(MENU_ID)) return;
    const source = sidebarSource();
    if (!source) return;
    const item = source.cloneNode(true);
    item.id = MENU_ID;
    item.removeAttribute('href');
    item.querySelectorAll('[id]').forEach((node) => node.removeAttribute('id'));
    const exact = Array.from(item.querySelectorAll('*')).find((node) => ['회원관리', '요청사항 관리', '요청사항', '사용현황'].includes(clean(node.textContent)));
    if (exact) exact.textContent = '과금관리';
    else item.textContent = '과금관리';
    item.addEventListener('click', (event) => {
      event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation(); openPanel();
    }, true);
    source.insertAdjacentElement('afterend', item);
  }

  function getHost() {
    if (window.StoryMakerV1InlinePanels?.open) return window.StoryMakerV1InlinePanels.open('admin-billing', '과금관리');
    return document.querySelector('main') || document.getElementById('root') || document.body;
  }

  function renderShell(host) {
    host.innerHTML = `<section id="${PANEL_ID}" class="v1ab-wrap">
      <div class="v1ab-head"><div class="v1ab-top"><div><h2 class="v1ab-title">회원 과금·사용량 관리</h2><p class="v1ab-sub">요금제, 영상 크레딧, Free 최초 지급과 갱신일만 관리합니다.</p></div><button class="v1ab-btn" data-close>닫기</button></div>
      <div class="v1ab-grid"><div class="v1ab-card"><span>회원</span><strong data-total>-</strong></div><div class="v1ab-card"><span>업체 등록 회원</span><strong data-persona>-</strong></div><div class="v1ab-card"><span>관리자</span><strong data-admin>-</strong></div><div class="v1ab-card"><span>운영 범위</span><strong>V1 전용</strong></div></div></div>
      <div class="v1ab-box"><div class="v1ab-top"><div class="v1ab-filter"><input class="v1ab-input" data-search placeholder="회원 아이디 검색"><button class="v1ab-btn" data-refresh>새로고침</button></div><div class="v1ab-state" data-state>불러오는 중입니다.</div></div>
      <div class="v1ab-scroll"><table class="v1ab-table"><thead><tr><th>회원</th><th>권한</th><th>업체 수</th><th>프로젝트</th><th>최근 로그인</th><th>관리</th></tr></thead><tbody data-body></tbody></table></div></div>
      <div class="v1ab-detail" data-detail hidden></div>
    </section>`;
    host.querySelector('[data-close]')?.addEventListener('click', () => window.StoryMakerV1InlinePanels?.close?.());
    host.querySelector('[data-refresh]')?.addEventListener('click', loadMembers);
    host.querySelector('[data-search]')?.addEventListener('input', renderMembers);
  }

  function renderMembers() {
    const panel = document.getElementById(PANEL_ID);
    if (!panel) return;
    const query = clean(panel.querySelector('[data-search]')?.value).toLowerCase();
    const filtered = members.filter((item) => {
      const user = item.storymaker || {};
      return !query || clean(user.username).toLowerCase().includes(query);
    });
    panel.querySelector('[data-body]').innerHTML = filtered.map((item) => {
      const user = item.storymaker;
      if (!user) return '';
      return `<tr><td>${esc(user.username || '-')}<div>ID ${Number(user.id)}</div></td><td>${esc(user.role || '-')}</td><td>${Number(item.persona_count || 0)}</td><td>${Number(item.project_count || 0)}</td><td>${esc(user.last_login_at || '-')}</td><td><button class="v1ab-btn primary" data-user="${Number(user.id)}">과금 상세</button></td></tr>`;
    }).join('') || '<tr><td colspan="6">표시할 회원이 없습니다.</td></tr>';
    panel.querySelectorAll('[data-user]').forEach((button) => button.addEventListener('click', () => openBilling(Number(button.dataset.user))));
  }

  async function loadMembers() {
    const panel = document.getElementById(PANEL_ID);
    if (!panel) return;
    panel.querySelector('[data-state]').textContent = '회원 정보를 불러오는 중입니다.';
    try {
      const payload = await api('/v1-api/admin/members');
      members = Array.isArray(payload?.data?.items) ? payload.data.items : [];
      panel.querySelector('[data-total]').textContent = Number(payload?.data?.summary?.storymaker_users || 0).toLocaleString();
      panel.querySelector('[data-persona]').textContent = Number(payload?.data?.summary?.persona_users || 0).toLocaleString();
      panel.querySelector('[data-admin]').textContent = members.filter((item) => item.storymaker?.role === 'admin').length.toLocaleString();
      panel.querySelector('[data-state]').textContent = `${members.length}명 조회 완료`;
      renderMembers();
    } catch (error) {
      panel.querySelector('[data-state]').textContent = error.message;
    }
  }

  async function openBilling(userId) {
    const panel = document.getElementById(PANEL_ID);
    const detail = panel?.querySelector('[data-detail]');
    if (!detail) return;
    detail.hidden = false;
    detail.innerHTML = '<div class="v1ab-state">과금 정보를 불러오는 중입니다.</div>';
    detail.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    try {
      const payload = await api(`/v1-api/admin/members/${userId}/billing`);
      renderBilling(detail, userId, payload.data || {});
    } catch (error) {
      detail.innerHTML = `<div class="v1ab-state">${esc(error.message)}</div>`;
    }
  }

  function renderBilling(detail, userId, data) {
    const profile = data.billing_profile;
    const credits = data.credits || {};
    const plans = Array.isArray(data.plans) ? data.plans : [];
    detail.innerHTML = `<div class="v1ab-top"><div><h3 class="v1ab-title">${esc(data.user?.username || '회원')} 과금 상세</h3><p class="v1ab-sub">사용 가능 ${Number(credits.available || 0)}회 · 예약 ${Number(credits.reserved || 0)}회</p></div><button class="v1ab-btn" data-hide>닫기</button></div>
      <div class="v1ab-grid"><div class="v1ab-card"><span>현재 요금제</span><strong>${esc(profile?.plan_name || profile?.plan_code || '미연결')}</strong></div><div class="v1ab-card"><span>다음 갱신일</span><strong>${esc(profile?.next_billing_at || profile?.current_period_ends_at || '-')}</strong></div><div class="v1ab-card"><span>Free 최초 20회</span><strong>${profile ? (profile.free_signup_credit_given ? '지급 완료' : '미지급') : '-'}</strong></div><div class="v1ab-card"><span>보관 기간</span><strong>${profile?.retention_days ?? '-'}일</strong></div></div>
      ${data.user?.role === 'admin' ? '<div class="v1ab-state">관리자 계정은 제작 횟수 제한 대상이 아닙니다.</div>' : `<div class="v1ab-actions">${data.needs_billing_profile ? '<button class="v1ab-btn primary" data-profile>과금 프로필 생성</button>' : ''}${profile && !profile.free_signup_credit_given ? '<button class="v1ab-btn" data-free>Free 최초 20회 지급</button>' : ''}<select class="v1ab-input" data-plan>${plans.map((plan) => `<option value="${esc(plan.code)}" ${profile?.plan_code === plan.code ? 'selected' : ''}>${esc(plan.name)} · ${Number(plan.monthly_price_krw || 0).toLocaleString()}원 · ${Number(plan.base_video_credits || 0)}회</option>`).join('')}</select><button class="v1ab-btn primary" data-plan-save>요금제 적용</button></div>`}
      <div class="v1ab-box" style="margin-top:16px"><strong>영상 크레딧 지갑</strong>${Array.isArray(credits.wallets) && credits.wallets.length ? credits.wallets.map((wallet) => `<div class="v1ab-wallet"><span>${esc(wallet.credit_type)}${wallet.expires_at ? ` · 만료 ${esc(wallet.expires_at)}` : ''}</span><strong>${Number(wallet.available_amount || 0)}회</strong></div>`).join('') : '<div class="v1ab-state">지급된 크레딧이 없습니다.</div>'}</div>`;

    detail.querySelector('[data-hide]')?.addEventListener('click', () => { detail.hidden = true; });
    detail.querySelector('[data-profile]')?.addEventListener('click', async () => {
      await api(`/v1-api/admin/members/${userId}/billing/profile`, {method: 'POST'});
      await openBilling(userId);
    });
    detail.querySelector('[data-free]')?.addEventListener('click', async () => {
      if (!confirm('Free 최초 20회를 지급하시겠습니까? 중복 지급되지 않습니다.')) return;
      await api(`/v1-api/admin/members/${userId}/billing/free-signup-credit`, {method: 'POST'});
      await openBilling(userId);
    });
    detail.querySelector('[data-plan-save]')?.addEventListener('click', async () => {
      const planCode = detail.querySelector('[data-plan]')?.value;
      await api(`/v1-api/admin/members/${userId}/billing/plan`, {method: 'PUT', body: JSON.stringify({plan_code: planCode})});
      await openBilling(userId);
    });
  }

  async function openPanel() {
    if (!adminAccess) return;
    const host = getHost();
    if (!host) return;
    renderShell(host);
    await loadMembers();
  }

  async function resolveRole() {
    try {
      const payload = await api('/v1-api/auth/me');
      const user = payload?.data?.user || payload?.user || payload?.data || null;
      adminAccess = detectAdmin(user);
    } catch (_) {
      adminAccess = false;
    }
    ensureMenu();
  }

  ensureStyle();
  resolveRole();
  new MutationObserver(() => {
    if (adminAccess && !document.getElementById(MENU_ID)) ensureMenu();
  }).observe(document.documentElement, {childList: true, subtree: true});
})();
