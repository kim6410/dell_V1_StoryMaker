(function(){
  'use strict';

  const STYLE_ID = 'v1-region-modal-style';
  const MODAL_ID = 'v1-region-modal';
  const BOUND = 'v1RegionModalBound';
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

  function escapeHtml(value){
    return String(value || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function ensureStyle(){
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .v1-region-picker{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;width:100%}
      .v1-region-picker-display{width:100%;box-sizing:border-box;cursor:pointer}
      .v1-region-picker-button{border:1px solid rgba(34,211,238,.55);border-radius:14px;background:rgba(8,145,178,.12);padding:0 16px;color:#0e7490;font-weight:900;white-space:nowrap;cursor:pointer}
      .v1-region-picker-button:hover{background:rgba(8,145,178,.2)}
      #${MODAL_ID}{position:fixed;inset:0;z-index:2147483000;display:none;align-items:center;justify-content:center;padding:18px;background:rgba(2,6,23,.78);backdrop-filter:blur(8px)}
      #${MODAL_ID}.is-open{display:flex}
      #${MODAL_ID} .v1-region-dialog{width:min(680px,100%);max-height:min(760px,92vh);display:flex;flex-direction:column;overflow:hidden;border:1px solid rgba(103,232,249,.35);border-radius:24px;background:#f8fafc;box-shadow:0 30px 90px rgba(0,0,0,.55)}
      #${MODAL_ID} .v1-region-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;padding:22px 22px 16px;background:linear-gradient(135deg,#0f172a,#164e63);color:#fff}
      #${MODAL_ID} h2{margin:0;font-size:22px;font-weight:950}
      #${MODAL_ID} .v1-region-description{margin:7px 0 0;color:#bae6fd;font-size:13px;font-weight:700;line-height:1.6}
      #${MODAL_ID} .v1-region-close{border:0;background:transparent;color:#fff;font-size:30px;line-height:1;cursor:pointer}
      #${MODAL_ID} .v1-region-search-box{padding:18px 20px 12px;background:#f8fafc}
      #${MODAL_ID} .v1-region-query{width:100%;box-sizing:border-box;border:2px solid #67e8f9;border-radius:16px;background:#fff;padding:14px 16px;color:#0f172a;font-size:16px;font-weight:800;outline:none}
      #${MODAL_ID} .v1-region-query:focus{border-color:#0891b2;box-shadow:0 0 0 4px rgba(34,211,238,.18)}
      #${MODAL_ID} .v1-region-help{margin:8px 2px 0;color:#64748b;font-size:12px;font-weight:700}
      #${MODAL_ID} .v1-region-results{min-height:180px;max-height:460px;overflow:auto;padding:8px 20px 20px;background:#f8fafc}
      #${MODAL_ID} .v1-region-empty{padding:38px 12px;text-align:center;color:#64748b;font-size:14px;font-weight:800}
      #${MODAL_ID} .v1-region-result{display:flex;width:100%;align-items:center;justify-content:space-between;gap:14px;margin-top:8px;border:1px solid #cbd5e1;border-radius:15px;background:#fff;padding:13px 15px;color:#0f172a;text-align:left;cursor:pointer}
      #${MODAL_ID} .v1-region-result:hover,#${MODAL_ID} .v1-region-result.is-active{border-color:#06b6d4;background:#ecfeff;box-shadow:0 8px 22px rgba(8,145,178,.12)}
      #${MODAL_ID} .v1-region-result strong{font-size:15px;font-weight:950}
      #${MODAL_ID} .v1-region-result small{display:block;margin-top:4px;color:#64748b;font-size:11px;font-weight:700}
      #${MODAL_ID} .v1-region-select-label{flex:none;border-radius:999px;background:#cffafe;padding:6px 10px;color:#0e7490;font-size:11px;font-weight:950}
      @media(max-width:560px){.v1-region-picker{grid-template-columns:1fr}.v1-region-picker-button{min-height:44px}#${MODAL_ID}{padding:10px}#${MODAL_ID} .v1-region-dialog{border-radius:19px}#${MODAL_ID} .v1-region-head{padding:18px 17px 14px}#${MODAL_ID} .v1-region-search-box,#${MODAL_ID} .v1-region-results{padding-left:14px;padding-right:14px}}
    `;
    document.head.appendChild(style);
  }

  let currentField = null;
  let currentDisplay = null;
  let timer = 0;
  let controller = null;
  let active = -1;

  function ensureModal(){
    let modal = document.getElementById(MODAL_ID);
    if (modal) return modal;
    ensureStyle();
    modal = document.createElement('div');
    modal.id = MODAL_ID;
    modal.setAttribute('aria-hidden', 'true');
    modal.innerHTML = `
      <div class="v1-region-dialog" role="dialog" aria-modal="true" aria-labelledby="v1-region-title">
        <div class="v1-region-head">
          <div><h2 id="v1-region-title">지역 검색</h2><p class="v1-region-description">읍·면·동 이름이나 시·군·구를 입력하고 정확한 지역을 선택하세요.</p></div>
          <button type="button" class="v1-region-close" aria-label="닫기">×</button>
        </div>
        <div class="v1-region-search-box">
          <input type="search" class="v1-region-query" autocomplete="off" placeholder="예: 태장동, 원주 태장, 울산 호계">
          <p class="v1-region-help">두 글자 이상 입력하면 현재 존재하는 법정동만 검색합니다.</p>
        </div>
        <div class="v1-region-results"><div class="v1-region-empty">검색어를 입력해 주세요.</div></div>
      </div>`;
    document.body.appendChild(modal);
    modal.querySelector('.v1-region-close').addEventListener('click', closeModal);
    modal.addEventListener('mousedown', e => { if (e.target === modal) closeModal(); });
    const query = modal.querySelector('.v1-region-query');
    query.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(runSearch, 170); });
    query.addEventListener('keydown', e => {
      const buttons = Array.from(modal.querySelectorAll('button.v1-region-result'));
      if (e.key === 'Escape') { e.preventDefault(); closeModal(); return; }
      if (!buttons.length) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        active = e.key === 'ArrowDown' ? Math.min(buttons.length - 1, active + 1) : Math.max(0, active - 1);
        buttons.forEach((b,i) => b.classList.toggle('is-active', i === active));
        buttons[active]?.scrollIntoView({block:'nearest'});
      } else if (e.key === 'Enter' && active >= 0) {
        e.preventDefault(); buttons[active].click();
      }
    });
    return modal;
  }

  function openModal(field, display){
    currentField = field;
    currentDisplay = display;
    const modal = ensureModal();
    const query = modal.querySelector('.v1-region-query');
    const results = modal.querySelector('.v1-region-results');
    query.value = '';
    results.innerHTML = '<div class="v1-region-empty">읍·면·동 또는 지역 키워드를 입력해 주세요.</div>';
    modal.classList.add('is-open');
    modal.setAttribute('aria-hidden', 'false');
    document.documentElement.style.overflow = 'hidden';
    active = -1;
    setTimeout(() => query.focus(), 30);
  }

  function closeModal(){
    const modal = document.getElementById(MODAL_ID);
    if (!modal) return;
    if (controller) controller.abort();
    modal.classList.remove('is-open');
    modal.setAttribute('aria-hidden', 'true');
    document.documentElement.style.overflow = '';
    currentDisplay?.focus?.();
    currentField = null;
    currentDisplay = null;
    active = -1;
  }

  function setNativeValue(element, value){
    const proto = element instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
    if (setter) setter.call(element, value); else element.value = value;
  }

  function commit(item){
    if (!currentField) return;
    const display = item.display_name || formatRegionDisplay(item.full_name || '');
    const official = item.full_name || display;
    currentField.dataset.regionCode = item.legal_code || '';
    currentField.dataset.regionFull = official;
    currentField.dataset.regionDisplay = display;
    if (currentField.tagName === 'SELECT') {
      let option = Array.from(currentField.options).find(o => o.value === display);
      if (!option) { option = new Option(display, display, true, true); currentField.add(option); }
    }
    setNativeValue(currentField, display);
    if (currentDisplay) currentDisplay.value = display;
    currentField.dispatchEvent(new Event('input', {bubbles:true}));
    currentField.dispatchEvent(new Event('change', {bubbles:true}));
    closeModal();
  }

  async function runSearch(){
    const modal = ensureModal();
    const query = modal.querySelector('.v1-region-query');
    const results = modal.querySelector('.v1-region-results');
    const q = query.value.trim();
    if (q.replace(/\s+/g,'').length < 2) {
      results.innerHTML = '<div class="v1-region-empty">두 글자 이상 입력해 주세요.</div>';
      return;
    }
    if (controller) controller.abort();
    controller = new AbortController();
    results.innerHTML = '<div class="v1-region-empty">지역을 검색하고 있습니다.</div>';
    try {
      const response = await fetch('/v1-api/auth/regions/search?q=' + encodeURIComponent(q) + '&limit=20', {
        credentials:'include', cache:'no-store', headers:{Accept:'application/json'}, signal:controller.signal
      });
      const payload = await response.json().catch(() => ({}));
      const items = Array.isArray(payload?.data) ? payload.data : [];
      results.innerHTML = '';
      if (!items.length) {
        results.innerHTML = '<div class="v1-region-empty">검색 결과가 없습니다. 다른 지역 키워드로 검색해 주세요.</div>';
        return;
      }
      items.forEach(item => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'v1-region-result';
        button.innerHTML = '<span><strong>' + escapeHtml(item.display_name || item.full_name || '') + '</strong><small>법정동코드 ' + escapeHtml(item.legal_code || '') + '</small></span><span class="v1-region-select-label">선택</span>';
        button.addEventListener('click', () => commit(item));
        results.appendChild(button);
      });
      active = -1;
    } catch (error) {
      if (error.name !== 'AbortError') results.innerHTML = '<div class="v1-region-empty">지역 검색 중 오류가 발생했습니다.</div>';
    }
  }

  function eligible(field){
    if (!field || field.dataset[BOUND] === '1') return false;
    const explicitRegionField = field.matches('input[name="region"],select[name="region"]');
    const labeledRegionField = field.dataset.v1RegionField === '1';
    if (!explicitRegionField && !labeledRegionField) return false;
    return field.type !== 'hidden';
  }

  function bind(field){
    if (!eligible(field)) return;
    field.dataset[BOUND] = '1';
    ensureStyle();
    const wrap = document.createElement('div');
    wrap.className = 'v1-region-picker';
    const display = document.createElement('input');
    display.type = 'text';
    display.readOnly = true;
    display.className = (field.className || '') + ' v1-region-picker-display';
    display.placeholder = '지역 검색 버튼을 눌러 선택하세요';
    display.value = formatRegionDisplay(field.value || '');
    display.setAttribute('aria-label', '선택한 지역');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'v1-region-picker-button';
    button.textContent = '지역 검색';
    field.parentNode.insertBefore(wrap, field);
    wrap.append(display, button);
    wrap.appendChild(field);
    field.style.position = 'absolute';
    field.style.opacity = '0';
    field.style.pointerEvents = 'none';
    field.style.width = '1px';
    field.style.height = '1px';
    field.style.margin = '0';
    field.setAttribute('aria-hidden', 'true');
    const open = () => openModal(field, display);
    display.addEventListener('click', open);
    button.addEventListener('click', open);
    field.addEventListener('change', () => { display.value = formatRegionDisplay(field.value || ''); });
  }

  function directLabelText(label){
    return Array.from(label?.childNodes || [])
      .filter(node => node.nodeType === Node.TEXT_NODE)
      .map(node => node.textContent || '')
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function scan(root){
    const scope = root || document;
    scope.querySelectorAll?.('input[name="region"],select[name="region"]').forEach(bind);
    scope.querySelectorAll?.('label').forEach(label => {
      const labelText = directLabelText(label);
      if (!/^\*?\s*지역\s*(필수)?$/.test(labelText)) return;
      const field = label.querySelector('select,input:not([type="hidden"])');
      if (!field) return;
      field.dataset.v1RegionField = '1';
      bind(field);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => scan(document), {once:true}); else scan(document);
  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node.nodeType === 1) { if (eligible(node)) bind(node); scan(node); }
  }))).observe(document.documentElement, {childList:true, subtree:true});
})();
