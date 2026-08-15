(() => {
  'use strict';

  if (window.__STORYMAKER_V1_ADMIN_POLICY_PANEL__) return;
  window.__STORYMAKER_V1_ADMIN_POLICY_PANEL__ = true;

  const MENU_ID = 'storymaker-v1-admin-policy-menu';
  const PANEL_ID = 'storymaker-v1-admin-policy-panel';
  let adminAccess = false;

  const clean = (value = '') => String(value).replace(/\s+/g, ' ').trim();
  const detectAdmin = (user) => {
    const role = clean(user?.role || user?.user_role || user?.type).toLowerCase();
    return user?.is_admin === true || user?.admin === true || role === 'admin';
  };

  const plans = [
    {name:'Free', price:'0원', credits:'20회 최초 1회', businesses:'1개', rollover:'없음', retention:'7일', addon:'불가'},
    {name:'Starter', price:'4,900원', credits:'월 50회', businesses:'2개', rollover:'잔여 기본량 30%', retention:'30일', addon:'가능'},
    {name:'Standard', price:'9,900원', credits:'월 150회', businesses:'5개', rollover:'잔여 기본량 30%', retention:'30일', addon:'가능'},
    {name:'Professional', price:'29,700원', credits:'월 500회', businesses:'10개', rollover:'잔여 기본량 30%', retention:'30일', addon:'가능'},
    {name:'Business', price:'59,400원', credits:'월 1,200회', businesses:'20개', rollover:'잔여 기본량 30%', retention:'30일', addon:'가능'},
  ];

  function ensureStyle() {
    if (document.getElementById('storymaker-v1-admin-policy-style')) return;
    const style = document.createElement('style');
    style.id = 'storymaker-v1-admin-policy-style';
    style.textContent = `
      .v1ap-wrap{width:100%;max-width:1740px;margin:0 auto;padding:10px 8px 28px;color:#e2e8f0}.v1ap-head,.v1ap-box{border:1px solid rgba(103,232,249,.2);background:rgba(15,23,42,.92);border-radius:20px;padding:18px;margin-bottom:12px}.v1ap-top{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}.v1ap-title{margin:0;font-size:25px;color:#fff}.v1ap-sub{margin:7px 0 0;color:#94a3b8;font-size:14px;line-height:1.7}.v1ap-btn{border:1px solid rgba(148,163,184,.35);background:#0f172a;color:#e2e8f0;border-radius:11px;padding:9px 13px;font-weight:900;cursor:pointer}.v1ap-scroll{overflow-x:auto}.v1ap-table{width:100%;min-width:900px;border-collapse:collapse}.v1ap-table th,.v1ap-table td{padding:13px 11px;border-bottom:1px solid #263449;text-align:left}.v1ap-table th{color:#94a3b8;font-size:12px}.v1ap-table td{font-size:13px;font-weight:800}.v1ap-note{display:grid;gap:9px}.v1ap-note div{border:1px solid #334155;background:#020617;border-radius:12px;padding:13px;line-height:1.65}.v1ap-note strong{color:#7dd3fc}
    `;
    document.head.appendChild(style);
  }

  async function resolveRole() {
    try {
      const response = await fetch('/v1-api/auth/me', {credentials:'include', cache:'no-store', headers:{Accept:'application/json'}});
      const payload = response.ok ? await response.json().catch(() => ({})) : {};
      adminAccess = response.ok && detectAdmin(payload?.data?.user || payload?.user || payload?.data || null);
    } catch (_) {
      adminAccess = false;
    }
    ensureMenu();
  }

  function sidebarSource() {
    const labels = ['과금관리', '회원관리', '요청사항 관리'];
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
    const exact = Array.from(item.querySelectorAll('*')).find((node) => ['과금관리','회원관리','요청사항 관리'].includes(clean(node.textContent)));
    if (exact) exact.textContent = '개발 점검';
    else item.textContent = '개발 점검';
    item.addEventListener('click', (event) => {
      event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation(); openPanel();
    }, true);
    source.insertAdjacentElement('afterend', item);
  }

  function openPanel() {
    if (!adminAccess) return;
    const host = window.StoryMakerV1InlinePanels?.open?.('admin-policy', '개발 점검') || document.querySelector('main') || document.getElementById('root');
    if (!host) return;
    host.innerHTML = `<section id="${PANEL_ID}" class="v1ap-wrap"><div class="v1ap-head"><div class="v1ap-top"><div><h2 class="v1ap-title">회원등급·과금 정책 점검</h2><p class="v1ap-sub">운영 정책을 확인하는 V1 전용 읽기 화면입니다. 실제 회원 변경은 과금관리 메뉴에서만 수행합니다.</p></div><button class="v1ap-btn" data-close>닫기</button></div></div><div class="v1ap-box"><div class="v1ap-scroll"><table class="v1ap-table"><thead><tr><th>등급</th><th>월 요금</th><th>영상 제공량</th><th>업체 수</th><th>이월</th><th>저장</th><th>추가 충전</th></tr></thead><tbody>${plans.map((plan) => `<tr><td>${plan.name}</td><td>${plan.price}</td><td>${plan.credits}</td><td>${plan.businesses}</td><td>${plan.rollover}</td><td>${plan.retention}</td><td>${plan.addon}</td></tr>`).join('')}</tbody></table></div></div><div class="v1ap-box"><div class="v1ap-note"><div><strong>갱신 기준</strong><br>회원별 가입일 또는 결제일 기준 30일 주기로 갱신합니다.</div><div><strong>이월 계산</strong><br>전월 기본 제공량 중 남은 수량의 30%를 올림 처리합니다. 프로필·커뮤니티·추가 충전 보상은 기본 이월 대상에서 분리합니다.</div><div><strong>추가 충전</strong><br>유료회원만 30회 4,900원 상품을 구매할 수 있도록 설계합니다.</div><div><strong>안전 원칙</strong><br>이 화면은 정책 확인용이며 DB 값을 직접 수정하지 않습니다.</div></div></div></section>`;
    host.querySelector('[data-close]')?.addEventListener('click', () => window.StoryMakerV1InlinePanels?.close?.());
  }

  ensureStyle();
  resolveRole();
  new MutationObserver(() => {
    if (adminAccess && !document.getElementById(MENU_ID)) ensureMenu();
  }).observe(document.documentElement, {childList:true, subtree:true});
})();
