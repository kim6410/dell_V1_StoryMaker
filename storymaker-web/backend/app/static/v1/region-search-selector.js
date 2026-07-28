(function(){
  'use strict';

  const STYLE_ID = 'v1-region-search-style';
  const BOUND = 'v1RegionSearchBound';
  const aliases = [
    ['서울특별시','서울'],['부산광역시','부산'],['대구광역시','대구'],['인천광역시','인천'],
    ['광주광역시','광주'],['대전광역시','대전'],['울산광역시','울산'],['세종특별자치시','세종'],
    ['경기도','경기'],['강원특별자치도','강원도'],['충청북도','충북'],['충청남도','충남'],
    ['전북특별자치도','전북'],['전라북도','전북'],['전라남도','전남'],['경상북도','경북'],
    ['경상남도','경남'],['제주특별자치도','제주']
  ];

  function formatRegionDisplay(value){
    const text = String(value || '').trim().replace(/\s+/g, ' ');
    for (const [official, short] of aliases) {
      if (text === official) return short;
      if (text.startsWith(official + ' ')) return short + text.slice(official.length);
    }
    return text;
  }
  window.formatRegionDisplay = formatRegionDisplay;

  function ensureStyle(){
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = '.v1-region-search{position:relative;width:100%}.v1-region-search-input{width:100%;box-sizing:border-box}.v1-region-results{position:absolute;z-index:10050;left:0;right:0;top:calc(100% + 5px);max-height:280px;overflow:auto;background:#111827;border:1px solid rgba(148,163,184,.35);border-radius:12px;box-shadow:0 18px 45px rgba(0,0,0,.38);display:none}.v1-region-results.is-open{display:block}.v1-region-result{display:block;width:100%;padding:11px 13px;border:0;border-bottom:1px solid rgba(148,163,184,.15);background:transparent;color:#f8fafc;text-align:left;cursor:pointer;font:inherit}.v1-region-result:hover,.v1-region-result.is-active{background:rgba(59,130,246,.22)}.v1-region-result small{display:block;margin-top:3px;color:#94a3b8}.v1-region-hint{margin-top:5px;color:#94a3b8;font-size:12px}';
    document.head.appendChild(style);
  }

  function eligible(field){
    if (!field || field.dataset[BOUND] === '1') return false;
    if (!field.matches('input[name="region"],select[name="region"]')) return false;
    if (field.type === 'hidden') return false;
    return true;
  }

  function bind(field){
    if (!eligible(field)) return;
    field.dataset[BOUND] = '1';
    ensureStyle();

    const original = field;
    const wrap = document.createElement('div');
    wrap.className = 'v1-region-search';
    const input = document.createElement('input');
    input.type = 'text';
    input.autocomplete = 'off';
    input.placeholder = '읍·면·동 또는 지역명을 검색하세요';
    input.className = (field.className || '') + ' v1-region-search-input';
    input.value = formatRegionDisplay(field.value || '');
    const results = document.createElement('div');
    results.className = 'v1-region-results';
    const hint = document.createElement('div');
    hint.className = 'v1-region-hint';
    hint.textContent = '예: 호계동, 울산 호계, 원주 태장';

    field.parentNode.insertBefore(wrap, field);
    wrap.appendChild(input);
    wrap.appendChild(results);
    wrap.appendChild(hint);

    if (field.tagName === 'SELECT') {
      field.style.display = 'none';
      field.setAttribute('aria-hidden', 'true');
    } else {
      field.style.position = 'absolute';
      field.style.opacity = '0';
      field.style.pointerEvents = 'none';
      field.style.width = '1px';
      field.style.height = '1px';
    }

    let timer = 0;
    let controller = null;
    let active = -1;

    function close(){ results.classList.remove('is-open'); results.innerHTML = ''; active = -1; }
    function commit(item){
      const display = item.display_name || formatRegionDisplay(item.full_name || '');
      const official = item.full_name || display;
      input.value = display;
      original.dataset.regionCode = item.legal_code || '';
      original.dataset.regionFull = official;
      original.dataset.regionDisplay = display;
      if (original.tagName === 'SELECT') {
        let option = Array.from(original.options).find(o => o.value === display);
        if (!option) { option = new Option(display, display, true, true); original.add(option); }
        original.value = display;
      } else original.value = display;
      original.dispatchEvent(new Event('input', {bubbles:true}));
      original.dispatchEvent(new Event('change', {bubbles:true}));
      close();
    }

    async function search(){
      const q = input.value.trim();
      if (q.replace(/\s+/g,'').length < 2) { close(); return; }
      if (controller) controller.abort();
      controller = new AbortController();
      try {
        const response = await fetch('/v1-api/auth/regions/search?q=' + encodeURIComponent(q) + '&limit=20', {credentials:'include', headers:{Accept:'application/json'}, signal:controller.signal});
        const payload = await response.json().catch(() => ({}));
        const items = Array.isArray(payload?.data) ? payload.data : [];
        results.innerHTML = '';
        items.forEach((item, index) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'v1-region-result';
          button.innerHTML = '<strong>' + escapeHtml(item.display_name || item.full_name || '') + '</strong><small>법정동코드 ' + escapeHtml(item.legal_code || '') + '</small>';
          button.addEventListener('mousedown', e => { e.preventDefault(); commit(item); });
          results.appendChild(button);
        });
        if (!items.length) results.innerHTML = '<div class="v1-region-result">검색 결과가 없습니다.</div>';
        results.classList.add('is-open');
        active = -1;
      } catch (error) { if (error.name !== 'AbortError') close(); }
    }

    input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(search, 180); });
    input.addEventListener('keydown', e => {
      const buttons = Array.from(results.querySelectorAll('button.v1-region-result'));
      if (!buttons.length) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        active = e.key === 'ArrowDown' ? Math.min(buttons.length - 1, active + 1) : Math.max(0, active - 1);
        buttons.forEach((b,i) => b.classList.toggle('is-active', i === active));
        buttons[active]?.scrollIntoView({block:'nearest'});
      } else if (e.key === 'Enter' && active >= 0) {
        e.preventDefault(); buttons[active].dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
      } else if (e.key === 'Escape') close();
    });
    input.addEventListener('blur', () => setTimeout(close, 150));
  }

  function escapeHtml(value){ return String(value || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function scan(root){ (root || document).querySelectorAll?.('input[name="region"],select[name="region"]').forEach(bind); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => scan(document), {once:true}); else scan(document);
  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => { if (node.nodeType === 1) { if (eligible(node)) bind(node); scan(node); } }))).observe(document.documentElement, {childList:true, subtree:true});
})();
