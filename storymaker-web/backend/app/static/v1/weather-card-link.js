(() => {
  'use strict';

  if (window.__STORYMAKER_V1_WEATHER_INLINE__) return;
  window.__STORYMAKER_V1_WEATHER_INLINE__ = true;

  const REGIONS = [
    '서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
    '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주', '양양',
  ];

  const clean = (value = '') => String(value).replace(/\s+/g, ' ').trim();
  const normalizeRegion = (text = '') => REGIONS.find((region) => text.includes(region)) || '';

  function getInlineBody() {
    return window.StoryMakerV1InlinePanels?.open?.('weather', '기상정보 DB');
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
    const body = getInlineBody();
    if (!body) {
      console.warn('[StoryMaker V1] inline panel host is not ready');
      return;
    }

    const src = `/static/v1/weather.html?embed=1&region=${encodeURIComponent(region || '')}`;
    body.innerHTML = '';

    const frame = document.createElement('iframe');
    frame.title = '기상정보 DB';
    frame.src = src;
    frame.loading = 'eager';
    frame.style.cssText = [
      'display:block',
      'width:100%',
      'height:min(760px,calc(100vh - 210px))',
      'min-height:620px',
      'border:0',
      'background:#071126',
    ].join(';');
    body.appendChild(frame);
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
    node.style.cursor = 'pointer';
    node.setAttribute('role', 'button');
    node.setAttribute('tabindex', '0');
    node.setAttribute('aria-label', '기상정보 DB 열기');

    const activate = (event) => {
      if (event.type === 'keydown' && event.key !== 'Enter' && event.key !== ' ') return;
      const interactive = event.target?.closest?.('button,a,input,select,textarea,[role="button"]');
      if (interactive && interactive !== node) return;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      openWeather(region || getBusinessRegion());
    };
    node.addEventListener('click', activate, true);
    node.addEventListener('keydown', activate, true);
  }

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
      window.StoryMakerV1InlinePanels?.close?.();
    }
  });

  window.StoryMakerV1Weather = { open: openWeather };

  refreshTriggers();
  new MutationObserver(refreshTriggers).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
  });

  console.info('[StoryMaker V1] weather inline bridge active');
})();
