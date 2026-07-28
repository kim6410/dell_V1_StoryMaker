(() => {
  'use strict';
  if (window.__STORYMAKER_V1_USER_REGION_WEATHER_SYNC_V4__) return;
  window.__STORYMAKER_V1_USER_REGION_WEATHER_SYNC_V4__ = true;

  const PERSONAS_API = '/v1-api/auth/personas';
  const WEATHER_API = '/api/weather/snapshots';
  const clean = (v = '') => String(v).replace(/\s+/g, ' ').trim();
  const normalizeRegion = (value = '') => {
    const text = clean(value);
    const aliases = [
      ['서울', ['서울특별시', '서울']], ['부산', ['부산광역시', '부산']],
      ['대구', ['대구광역시', '대구']], ['인천', ['인천광역시', '인천']],
      ['광주', ['광주광역시', '광주']], ['대전', ['대전광역시', '대전']],
      ['울산', ['울산광역시', '울산']],
      ['충청', ['세종특별자치시', '세종', '충청북도', '충청남도', '충북', '충남', '충청']],
      ['경기', ['경기도', '경기']], ['강원', ['강원특별자치도', '강원도', '강원']],
      ['전라', ['전북특별자치도', '전라북도', '전라남도', '전북', '전남', '전라']],
      ['경북', ['경상북도', '경북']], ['경남', ['경상남도', '경남']],
      ['제주', ['제주특별자치도', '제주도', '제주']],
    ];
    for (const [canonical, names] of aliases) {
      if (names.some((name) => text.includes(name))) return canonical;
    }
    return '서울';
  };
  const esc = (v = '') => String(v)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const displayCompany = (v = '') => clean(v).replace(/^오박사만능인테리어$/, '오박사 만능인테리어');
  let current = null;
  let loading = false;

  async function fetchJson(url) {
    const response = await fetch(url, {
      credentials: 'include',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload?.ok === false) {
      throw new Error(payload?.detail || payload?.message || `HTTP ${response.status}`);
    }
    return payload;
  }

  function getPersonas(payload) {
    const data = payload?.data;
    if (Array.isArray(data)) return data;
    return data?.items || data?.personas || payload?.items || payload?.personas || [];
  }

  async function load() {
    if (loading) return;
    loading = true;
    try {
      const personaPayload = await fetchJson(PERSONAS_API);
      const list = getPersonas(personaPayload);
      const profile = list.find((item) => item?.is_default) || list[0] || {};
      const displayRegion = typeof window.formatRegionDisplay === 'function'
        ? window.formatRegionDisplay(profile.region || '서울')
        : clean(profile.region || '서울');
      const weatherRegion = normalizeRegion(displayRegion || '서울');
      const weatherPayload = await fetchJson(`${WEATHER_API}?page=1&page_size=1&region=${encodeURIComponent(weatherRegion)}`);
      const weatherItem = Array.isArray(weatherPayload?.items) ? (weatherPayload.items[0] || {}) : {};
      current = {
        region: displayRegion,
        weather: clean(weatherItem.weather || ''),
        company: clean(profile.company_name) || '업체명 미등록',
        phone: clean(profile.phone_number) || '전화번호 미등록',
      };
      window.StoryMakerV1SelectedRegion = current.region;
      apply();
    } catch (error) {
      console.warn('[StoryMaker V1 weather sync]', error);
    } finally {
      loading = false;
    }
  }

  function findWeatherCard() {
    const metric = [...document.querySelectorAll('*')].find((node) => clean(node.textContent) === '기온');
    if (!metric) return null;
    const cards = [];
    let node = metric;
    for (let i = 0; node && node !== document.body && i < 10; i += 1, node = node.parentElement) {
      const text = clean(node.textContent);
      const rect = node.getBoundingClientRect?.();
      if (rect && rect.width > 700 && rect.height > 100 && rect.height < 360 && text.includes('기온') && text.includes('체감') && text.includes('습도') && text.includes('바람')) {
        cards.push(node);
      }
    }
    return cards.sort((a, b) => a.getBoundingClientRect().height - b.getBoundingClientRect().height)[0] || null;
  }

  function removeInjectedDuplicates() {
    document.querySelectorAll('#v1-weather-summary-v3,#v1-weather-summary-v4,[data-v1-weather-injected="1"]').forEach((node) => node.remove());
  }

  function findOriginalLeft(card) {
    const direct = [...card.children].filter((child) => {
      const text = clean(child.textContent);
      return !text.includes('기온') && !text.includes('체감') && !text.includes('습도') && !text.includes('바람');
    });
    return direct[0] || null;
  }

  function updateOriginalLeft(left) {
    if (!current || !left) return false;

    const nodes = [...left.querySelectorAll('div,span,p,strong,h1,h2,h3,h4')];
    const liveLabel = nodes.find((node) => clean(node.textContent) === '실시간 날씨');
    const summaryNode = nodes.find((node) => {
      const text = clean(node.textContent);
      return text && text !== '실시간 날씨' && /서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주/.test(text) && !/01[016789]-?\d{3,4}-?\d{4}/.test(text);
    });
    const detailNode = nodes.find((node) => /01[016789]-?\d{3,4}-?\d{4}/.test(clean(node.textContent)) || clean(node.textContent).includes('지역 / 상호 / 전화번호'));

    if (liveLabel) liveLabel.textContent = '실시간 날씨';
    if (summaryNode) summaryNode.textContent = `${current.region} ${current.weather}`.trim();
    if (detailNode) detailNode.innerHTML = `${esc(current.region)} / <strong style="font-weight:950;font-size:calc(1em + 1px);color:#fff">${esc(displayCompany(current.company))}</strong> / ${esc(current.phone)}`;

    if (!summaryNode || !detailNode) {
      left.innerHTML = `
        <div style="font-size:15px;font-weight:900;color:#67e8f9;margin-bottom:8px">실시간 날씨</div>
        <div style="font-size:clamp(22px,1.8vw,32px);font-weight:950;color:#fff;line-height:1.15;margin-bottom:8px">${current.region} ${current.weather}</div>
        <div style="font-size:14px;font-weight:800;color:#dbeafe">${esc(current.region)} / <strong style="font-weight:950;font-size:calc(1em + 1px);color:#fff">${esc(displayCompany(current.company))}</strong> / ${esc(current.phone)}</div>
      `;
    }

    left.dataset.v1WeatherSynced = '1';
    return true;
  }

  function apply() {
    removeInjectedDuplicates();
    if (!current) return false;
    const card = findWeatherCard();
    if (!card) return false;
    const left = findOriginalLeft(card);
    if (!left) return false;
    return updateOriginalLeft(left);
  }

  let timer = 0;
  const schedule = () => {
    clearTimeout(timer);
    timer = setTimeout(apply, 120);
  };

  new MutationObserver(schedule).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
  });

  setInterval(apply, 800);
  setInterval(load, 60000);
  window.addEventListener('focus', load);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load, { once: true });
  } else {
    load();
  }
})();
