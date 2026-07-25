(() => {
  'use strict';

  if (window.__STORYMAKER_V1_WEATHER_INLINE__) return;
  window.__STORYMAKER_V1_WEATHER_INLINE__ = true;

  const REGION_ALIASES = [
    ['서울', ['서울특별시', '서울']],
    ['부산', ['부산광역시', '부산']],
    ['대구', ['대구광역시', '대구']],
    ['인천', ['인천광역시', '인천']],
    ['광주', ['광주광역시', '광주']],
    ['대전', ['대전광역시', '대전']],
    ['울산', ['울산광역시', '울산']],
    ['세종', ['세종특별자치시', '세종']],
    ['경기', ['경기도', '경기']],
    ['강원', ['강원특별자치도', '강원도', '강원']],
    ['충북', ['충청북도', '충북']],
    ['충남', ['충청남도', '충남']],
    ['전북', ['전북특별자치도', '전라북도', '전북']],
    ['전남', ['전라남도', '전남']],
    ['경북', ['경상북도', '경북']],
    ['경남', ['경상남도', '경남']],
    ['제주', ['제주특별자치도', '제주도', '제주']],
  ];

  const clean = (value = '') => String(value).replace(/\s+/g, ' ').trim();
  const normalizeRegion = (text = '') => {
    const value = clean(text);
    for (const [canonical, aliases] of REGION_ALIASES) {
      if (aliases.some((alias) => value.includes(alias))) return canonical;
    }
    return value;
  };

  const WEATHER_PANEL_ID = 'storymaker-v1-weather-panel';

  function closeWeather() {
    document.getElementById(WEATHER_PANEL_ID)?.remove();
  }

  function sidebarRight() {
    const candidates = Array.from(document.querySelectorAll('aside,nav,div'));
    const sidebar = candidates.find((node) => {
      const rect = node.getBoundingClientRect?.();
      if (!rect) return false;
      const visible = rect.width > 0 && rect.height > 0;
      const leftDocked = rect.left >= 0 && rect.left <= 24;
      const sidebarSize = rect.width >= 220 && rect.width <= 340;
      const tallEnough = rect.height >= window.innerHeight * 0.72;
      return visible && leftDocked && sidebarSize && tallEnough;
    });
    return sidebar ? Math.max(240, Math.round(sidebar.getBoundingClientRect().right)) : 260;
  }

  function getBusinessRegion() {
    const synced = clean(window.StoryMakerV1UserRegionWeather?.getRegion?.() || window.StoryMakerV1SelectedRegion || '');
    if (synced) return synced;

    const bodyText = document.body?.innerText || '';
    const explicit = bodyText.match(/지역\s*[:：]\s*([^\n,|]+)/);
    if (explicit) {
      const region = normalizeRegion(explicit[1]);
      if (region) return region;
    }
    return normalizeRegion(bodyText);
  }

  function openWeather(region = '') {
    closeWeather();

    const panel = document.createElement('section');
    panel.id = WEATHER_PANEL_ID;
    panel.setAttribute('aria-label', '기상정보 DB');
    panel.style.cssText = [
      'position:fixed',
      'top:0',
      'right:0',
      'bottom:0',
      `left:${sidebarRight()}px`,
      'z-index:2147483000',
      'background:#071126',
      'overflow:hidden',
    ].join(';');

    const frame = document.createElement('iframe');
    frame.title = '기상정보 DB';
    frame.src = `/static/v1/weather.html?embed=1&region=${encodeURIComponent(normalizeRegion(region))}`;
    frame.loading = 'eager';
    frame.style.cssText = 'display:block;width:100%;height:100%;border:0;background:#071126';
    panel.appendChild(frame);
    document.body.appendChild(panel);
  }

  function bestCard(start, needle) {
    let node = start;
    for (let depth = 0; node && depth < 7; depth += 1, node = node.parentElement) {
      const text = clean(node.textContent || '');
      const rect = node.getBoundingClientRect();
      if (text.includes('LOGIN') || text.includes('로그인') || text.includes('저장/생성 기능')) continue;
      if (text.includes(needle) && text.length < 300 && rect.width > 160 && rect.height > 20) return node;
    }
    return start.parentElement || start;
  }

  function bindTrigger(node, region = '') {
    if (!node || node.dataset.storymakerWeatherInlineTrigger === '1') return;
    node.dataset.storymakerWeatherInlineTrigger = '1';
    node.dataset.storymakerWeatherRegion = region || '';
    node.style.cursor = 'pointer';
    node.setAttribute('role', 'button');
    node.setAttribute('tabindex', '0');
    node.setAttribute('aria-label', '기상정보 DB 열기');
  }

  function captureWeatherActivation(event) {
    if (event.type === 'keydown' && event.key !== 'Enter' && event.key !== ' ') return;
    const trigger = event.target?.closest?.('[data-storymaker-weather-inline-trigger="1"]');
    if (!trigger) return;
    const interactive = event.target?.closest?.('button,a,input,select,textarea,[role="button"]');
    if (interactive && interactive !== trigger) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    openWeather(trigger.dataset.storymakerWeatherRegion || getBusinessRegion());
  }

  document.addEventListener('click', captureWeatherActivation, true);
  document.addEventListener('keydown', captureWeatherActivation, true);

  function refreshTriggers() {
    document.querySelectorAll('[data-weather-menu-live]').forEach((node) => node.remove());

    const weatherLabel = Array.from(document.querySelectorAll('div,span,p,strong,h1,h2,h3,h4'))
      .find((node) => clean(node.textContent) === '실시간 날씨');
    if (weatherLabel) {
      const card = bestCard(weatherLabel, '실시간 날씨');
      bindTrigger(card, normalizeRegion(clean(card.textContent || '')));
    }

    const dateLabel = Array.from(document.querySelectorAll('div,span,p,strong'))
      .find((node) => /^\d{1,2}\s*\/\s*\d{1,2}/.test(clean(node.textContent || '')));
    if (dateLabel) bindTrigger(bestCard(dateLabel, clean(dateLabel.textContent || '')), getBusinessRegion());
  }

  window.addEventListener('message', (event) => {
    if (event.origin === window.location.origin && event.data?.type === 'storymaker-close-weather') {
      closeWeather();
    }
  });

  document.addEventListener('pointerdown', (event) => {
    const panel = document.getElementById(WEATHER_PANEL_ID);
    if (!panel || panel.contains(event.target)) return;
    if (event.target?.closest?.('[data-storymaker-weather-inline-trigger="1"]')) return;
    const clickable = event.target?.closest?.('button,a,[role="button"]');
    if (clickable) closeWeather();
  }, true);

  window.StoryMakerV1Weather = { open: openWeather, close: closeWeather };

  refreshTriggers();
  new MutationObserver(refreshTriggers).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
  });

  console.info('[StoryMaker V1] weather inline bridge active');
})();
