(() => {
  'use strict';

  if (window.__STORYMAKER_V1_DASHBOARD_SUMMARY_CARD_BRIDGE__) return;
  window.__STORYMAKER_V1_DASHBOARD_SUMMARY_CARD_BRIDGE__ = true;

  const normalize = value => String(value || '').replace(/\s+/g, ' ').trim();
  let summary = null;
  let loading = false;
  let timer = 0;

  function isDashboardRoute() {
    const page = new URLSearchParams(location.search).get('page');
    if (!page || page === 'dashboard' || page === 'home' || page === 'main') return true;

    const text = normalize(document.body?.textContent);
    return text.includes('최근 생성') && text.includes('최근 주간 사용량');
  }

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

  function formatPeriod(startValue, endValue) {
    const start = new Date(startValue);
    const end = new Date(endValue);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return '';
    const displayEnd = new Date(end.getTime() - 1000);
    const part = date => `${date.getMonth() + 1}/${date.getDate()}`;
    return `${part(start)} ~ ${part(displayEnd)}`;
  }

  async function loadSummary() {
    if (loading || summary || !isDashboardRoute()) return;
    loading = true;
    try {
      const response = await fetch('/v1-api/auth/dashboard-usage', {
        method: 'GET',
        credentials: 'include',
        cache: 'no-store',
        headers: { Accept: 'application/json', ...authHeaders() },
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok || body?.ok === false) return;
      const data = body?.data && typeof body.data === 'object' ? body.data : {};
      const periodLabel = String(data.period_label || '').trim()
        || formatPeriod(data.period_start, data.period_end);
      summary = {
        total: Number(data.total_verified_videos ?? data.total_verified_mp4) || 0,
        current: Number(data.current_period_used ?? data.period_used) || 0,
        periodNote: periodLabel
          ? `${periodLabel} 이용기간 기준`
          : '최근 1개월 생성 기준',
      };
      apply();
    } catch (_) {
      // 기존 대시보드 표시를 유지한다.
    } finally {
      loading = false;
    }
  }

  function findCardByLabel(labelText) {
    const label = Array.from(document.querySelectorAll('div,span,p,h2,h3'))
      .find(node => normalize(node.textContent) === labelText);
    if (!label) return null;

    let node = label;
    while (node && node !== document.body) {
      const text = normalize(node.textContent);
      const rect = node.getBoundingClientRect();
      if (text.includes(labelText) && rect.width > 250 && rect.height > 90 && rect.height < 260) {
        return node;
      }
      node = node.parentElement;
    }
    return label.parentElement;
  }

  function directTextElements(card) {
    return Array.from(card.querySelectorAll('div,span,p,h2,h3,strong'))
      .filter(node => node.children.length === 0 && normalize(node.textContent));
  }

  function replaceCard(card, oldLabel, newLabel, value, noteMatcher, newNote) {
    if (!card) return false;
    const elements = directTextElements(card);
    const label = elements.find(node => normalize(node.textContent) === oldLabel);
    if (label) label.textContent = newLabel;

    const valueNode = elements.find(node => /^\d+건$/.test(normalize(node.textContent)));
    if (valueNode) valueNode.textContent = `${value}건`;

    const note = elements.find(node => noteMatcher(normalize(node.textContent)));
    if (note) note.textContent = newNote;
    return Boolean(label || valueNode || note);
  }

  function apply() {
    if (!summary || !isDashboardRoute()) return;

    replaceCard(
      findCardByLabel('최근 생성') || findCardByLabel('전체 사용'),
      '최근 생성',
      '전체 사용',
      summary.total,
      text => text === '최근 저장된 콘텐츠 기준' || text === '가입 후 전체 생성 기준',
      '가입 후 전체 생성 기준'
    );

    replaceCard(
      findCardByLabel('최근 주간 사용량') || findCardByLabel('최근 1개월 사용량'),
      '최근 주간 사용량',
      '최근 1개월 사용량',
      summary.current,
      text => text.includes('최근 7일 생성 기준') || text.includes('이용기간 기준') || text === '최근 1개월 생성 기준',
      summary.periodNote
    );
  }

  function schedule() {
    if (timer) return;
    timer = window.setTimeout(() => {
      timer = 0;
      loadSummary();
      apply();
    }, 120);
  }

  function start() {
    const root = document.getElementById('root') || document.body;
    new MutationObserver(schedule).observe(root, { childList: true, subtree: true });
    schedule();
    window.setTimeout(schedule, 700);
    window.setTimeout(schedule, 1800);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();
