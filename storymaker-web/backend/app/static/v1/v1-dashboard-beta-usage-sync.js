(() => {
  'use strict';

  if (window.__STORYMAKER_V1_DASHBOARD_USAGE_PANEL_V3__) return;
  window.__STORYMAKER_V1_DASHBOARD_USAGE_PANEL_V3__ = true;

  const ROOT_ID = 'v1-dashboard-usage-panel';
  const normalize = value => String(value || '').replace(/\s+/g, ' ').trim();
  let payload = null;
  let loading = false;
  let timer = 0;

  function authHeaders() {
    const token = String(
      localStorage.getItem('storymaker_token')
      || sessionStorage.getItem('storymaker_token')
      || localStorage.getItem('access_token')
      || sessionStorage.getItem('access_token')
      || ''
    ).trim();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async function getJson(path) {
    const response = await fetch(path, {
      method: 'GET',
      credentials: 'include',
      cache: 'no-store',
      headers: { Accept: 'application/json', ...authHeaders() },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok || body?.ok === false) {
      throw new Error(body?.detail || body?.message || `HTTP ${response.status}`);
    }
    return body;
  }

  function isDashboardRoute() {
    const page = new URLSearchParams(location.search).get('page');
    return !page || page === 'dashboard';
  }

  function findPlaceholder() {
    if (!isDashboardRoute()) return null;
    const candidates = Array.from(document.querySelectorAll('main section, main div'))
      .filter(node => {
        const text = normalize(node.textContent);
        if (!text.includes('대시보드 화면은 다음 단계에서 연결합니다')) return false;
        if (!text.includes('기능별로 검증된 API만 분리해서 붙입니다')) return false;
        const rect = node.getBoundingClientRect();
        return rect.width > 420 && rect.height > 120;
      })
      .map(node => {
        const rect = node.getBoundingClientRect();
        return { node, area: rect.width * rect.height };
      })
      .sort((a, b) => a.area - b.area);
    return candidates[0]?.node || null;
  }

  function formatDate(value) {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat('ko-KR', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false,
      timeZone: 'Asia/Seoul',
    }).format(date);
  }

  function buildPayload(responsePayload) {
    const data = responsePayload?.data && typeof responsePayload.data === 'object' ? responsePayload.data : {};
    return {
      totalJobs: Number(data.total_verified_mp4) || 0,
      used: Number(data.period_used) || 0,
      remaining: Number(data.remaining) || 0,
      limit: Number(data.monthly_limit) || 20,
      periodStart: data.period_start || '',
      periodEnd: data.period_end || '',
      planCode: String(data.plan_code || 'free').toLowerCase(),
      retained: Number(data.retained_count) || 0,
    };
  }

  function formatPeriod(startValue, endValue) {
    const start = new Date(startValue);
    const end = new Date(endValue);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return '-';
    const displayEnd = new Date(end.getTime() - 1000);
    const part = date => `${date.getMonth() + 1}/${String(date.getDate()).padStart(2, '0')}`;
    return `${part(start)} ~ ${part(displayEnd)}`;
  }

  function ensureStyle() {
    if (document.getElementById('v1-dashboard-usage-style')) return;
    const style = document.createElement('style');
    style.id = 'v1-dashboard-usage-style';
    style.textContent = `
      #${ROOT_ID}{padding:26px;border:1px solid rgba(51,65,85,.9);border-radius:32px;background:rgba(15,23,42,.88);color:#fff;box-shadow:0 24px 60px rgba(2,6,23,.25)}
      #${ROOT_ID} .v1d-head{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:22px}
      #${ROOT_ID} .v1d-kicker{font-size:13px;font-weight:900;color:#67e8f9;letter-spacing:.04em}
      #${ROOT_ID} h2{margin:7px 0 0;font-size:30px;line-height:1.25;font-weight:950;color:#fff}
      #${ROOT_ID} .v1d-sub{margin:8px 0 0;color:#94a3b8;font-size:14px;line-height:1.7}
      #${ROOT_ID} .v1d-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
      #${ROOT_ID} .v1d-card{display:block;width:100%;padding:20px;border:1px solid #243653;border-radius:22px;background:#0b162b;text-align:left;color:#fff;transition:.18s ease}
      #${ROOT_ID} button.v1d-card{cursor:pointer}
      #${ROOT_ID} button.v1d-card:hover{transform:translateY(-2px);border-color:rgba(103,232,249,.58);background:#0d1b34}
      #${ROOT_ID} .v1d-label{font-size:13px;font-weight:800;color:#94a3b8}
      #${ROOT_ID} .v1d-value{margin-top:9px;font-size:28px;line-height:1.15;font-weight:950;color:#fff}
      #${ROOT_ID} .v1d-note{margin-top:8px;font-size:12px;line-height:1.55;color:#67e8f9}
      #${ROOT_ID} .v1d-detail{margin-top:16px;padding:22px;border:1px solid rgba(34,211,238,.28);border-radius:24px;background:rgba(8,47,73,.22)}
      #${ROOT_ID} .v1d-detail[hidden]{display:none}
      #${ROOT_ID} .v1d-detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
      #${ROOT_ID} .v1d-row{padding:16px;border-radius:17px;background:rgba(2,6,23,.5);border:1px solid rgba(51,65,85,.7)}
      #${ROOT_ID} .v1d-row b{display:block;margin-top:6px;font-size:17px;color:#fff}
      #${ROOT_ID} .v1d-policy{margin-top:14px;padding:16px;border-radius:17px;background:rgba(2,6,23,.44);font-size:13px;line-height:1.8;color:#cbd5e1}
      #${ROOT_ID} .v1d-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}
      #${ROOT_ID} .v1d-actions button{border:1px solid #334155;border-radius:999px;padding:10px 16px;background:#0f172a;color:#e2e8f0;font-weight:850;cursor:pointer}
      #${ROOT_ID} .v1d-actions button.primary{border-color:#22d3ee;background:#22d3ee;color:#082f49}
      @media(max-width:1050px){#${ROOT_ID} .v1d-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @media(max-width:620px){#${ROOT_ID}{padding:18px;border-radius:24px}#${ROOT_ID} h2{font-size:24px}#${ROOT_ID} .v1d-grid,#${ROOT_ID} .v1d-detail-grid{grid-template-columns:1fr}#${ROOT_ID} .v1d-value{font-size:24px}}
    `;
    document.head.appendChild(style);
  }

  function openArchive() {
    const button = Array.from(document.querySelectorAll('nav button, aside button, button'))
      .find(node => normalize(node.textContent).replace('BETA', '').trim() === '보관함');
    if (button) button.click();
  }

  function render(target) {
    if (!payload || !target) return;
    ensureStyle();
    target.id = ROOT_ID;
    target.className = '';
    target.innerHTML = `
      <div class="v1d-head">
        <div>
          <div class="v1d-kicker">사용량 · 보관 현황</div>
          <h2>콘텐츠 제작 현황</h2>
          <p class="v1d-sub">검증 완료 MP4 사용량과 Beta 보관 상태를 한눈에 확인합니다.</p>
        </div>
      </div>
      <div class="v1d-grid">
        <div class="v1d-card">
          <div class="v1d-label">전체 작업</div>
          <div class="v1d-value">${payload.totalJobs}건</div>
          <div class="v1d-note">가입 후 생성·검증 완료 MP4</div>
        </div>
        <button type="button" class="v1d-card" data-v1d-usage>
          <div class="v1d-label">이번달 사용량</div>
          <div class="v1d-value">${payload.used}건</div>
          <div class="v1d-note">${formatPeriod(payload.periodStart, payload.periodEnd)} · 상세 보기</div>
        </button>
        <div class="v1d-card">
          <div class="v1d-label">남은 제작 횟수</div>
          <div class="v1d-value">${payload.remaining}건 / ${payload.limit}건</div>
          <div class="v1d-note">현재 30일 이용기간 기준</div>
        </div>
        <div class="v1d-card">
          <div class="v1d-label">현재 보관 중</div>
          <div class="v1d-value">${payload.retained}개 / ${payload.totalJobs}개</div>
          <div class="v1d-note">현재 보관 / 가입 후 전체 MP4</div>
        </div>
      </div>
      <section class="v1d-detail" data-v1d-detail hidden>
        <div class="v1d-detail-grid">
          <div class="v1d-row"><div class="v1d-label">이번달 사용기간</div><b>${formatPeriod(payload.periodStart, payload.periodEnd)}</b></div>
          <div class="v1d-row"><div class="v1d-label">다음 사용량 초기화</div><b>${formatDate(payload.periodEnd)}</b></div>
          <div class="v1d-row"><div class="v1d-label">사용량 집계 기준</div><b>생성·검증 완료 MP4</b></div>
          <div class="v1d-row"><div class="v1d-label">현재 요금제</div><b>${payload.planCode === 'free' ? '무료회원' : '유료회원'}</b></div>
        </div>
        <div class="v1d-policy">
          무료회원은 최신 콘텐츠 10개, 유료회원은 최신 콘텐츠 20개까지 보관합니다.<br>
          보관 한도를 넘으면 오래된 미디어가 자동 정리되지만 MP4 사용 이력은 유지됩니다.<br>
          새 이용기간이 시작되면 해당 기간 사용량은 0회부터 다시 계산됩니다.
        </div>
        <div class="v1d-actions">
          <button type="button" class="primary" data-v1d-close>상세 닫기</button>
          <button type="button" data-v1d-archive>보관함 열기</button>
        </div>
      </section>
    `;

    const detail = target.querySelector('[data-v1d-detail]');
    target.querySelector('[data-v1d-usage]')?.addEventListener('click', () => {
      detail.hidden = !detail.hidden;
      if (!detail.hidden) detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
    target.querySelector('[data-v1d-close]')?.addEventListener('click', () => { detail.hidden = true; });
    target.querySelector('[data-v1d-archive]')?.addEventListener('click', openArchive);
  }

  async function refresh() {
    if (loading || !isDashboardRoute()) return;
    const placeholder = findPlaceholder();
    const target = document.getElementById(ROOT_ID) || placeholder;
    if (!target) return;

    loading = true;
    try {
      const response = await getJson('/v1-api/auth/dashboard-usage');
      payload = buildPayload(response);
      render(document.getElementById(ROOT_ID) || target);
    } catch (error) {
      console.warn('[V1 dashboard usage panel]', error?.message || error);
    } finally {
      loading = false;
    }
  }

  function schedule() {
    if (timer) return;
    timer = window.setTimeout(() => {
      timer = 0;
      refresh();
    }, 160);
  }

  function start() {
    const root = document.getElementById('root') || document.body;
    new MutationObserver(schedule).observe(root, { childList: true, subtree: true });
    schedule();
    window.setTimeout(refresh, 700);
    window.setTimeout(refresh, 1800);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
