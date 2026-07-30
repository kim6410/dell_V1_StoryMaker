(function(){
  'use strict';

  const STYLE_ID = 'v1-industry-modal-style';
  const MODAL_ID = 'v1-industry-modal';
  const BOUND = 'v1IndustrySearchBound';
  const INDUSTRY_API = '/v1-api/auth/industry-templates';
  const KAKAO_CHANNEL_URL = 'https://pf.kakao.com/_FxjaxnX';
  let currentField = null;
  let currentDisplay = null;
  let activeIndex = -1;
  let databaseItems = [];
  let databaseLoadPromise = null;

  function clean(value){
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function escapeHtml(value){
    return String(value || '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  }

  function ensureStyle(){
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .v1-industry-picker{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;width:100%}
      .v1-industry-picker-display{width:100%;box-sizing:border-box;cursor:pointer}
      .v1-industry-picker-button{border:1px solid rgba(34,211,238,.55);border-radius:14px;background:rgba(8,145,178,.12);padding:0 16px;color:#22d3ee;font-weight:900;white-space:nowrap;cursor:pointer}
      .v1-industry-picker-button:hover{background:rgba(8,145,178,.22)}
      #${MODAL_ID}{position:fixed;inset:0;z-index:2147483100;display:none;align-items:center;justify-content:center;padding:18px;background:rgba(2,6,23,.8);backdrop-filter:blur(8px)}
      #${MODAL_ID}.is-open{display:flex}
      #${MODAL_ID} .v1-industry-dialog{width:min(700px,100%);max-height:min(780px,92vh);display:flex;flex-direction:column;overflow:hidden;border:1px solid rgba(103,232,249,.35);border-radius:24px;background:#f8fafc;box-shadow:0 30px 90px rgba(0,0,0,.55)}
      #${MODAL_ID} .v1-industry-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;padding:22px 22px 16px;background:linear-gradient(135deg,#0f172a,#164e63);color:#fff}
      #${MODAL_ID} h2{margin:0;font-size:22px;font-weight:950}
      #${MODAL_ID} .v1-industry-description{margin:7px 0 0;color:#bae6fd;font-size:13px;font-weight:700;line-height:1.6}
      #${MODAL_ID} .v1-industry-close{border:0;background:transparent;color:#fff;font-size:30px;line-height:1;cursor:pointer}
      #${MODAL_ID} .v1-industry-search-box{padding:18px 20px 12px;background:#f8fafc}
      #${MODAL_ID} .v1-industry-query{width:100%;box-sizing:border-box;border:2px solid #67e8f9;border-radius:16px;background:#fff;padding:14px 16px;color:#0f172a;font-size:16px;font-weight:800;outline:none}
      #${MODAL_ID} .v1-industry-query:focus{border-color:#0891b2;box-shadow:0 0 0 4px rgba(34,211,238,.18)}
      #${MODAL_ID} .v1-industry-help{margin:8px 2px 0;color:#64748b;font-size:12px;font-weight:700}
      #${MODAL_ID} .v1-industry-results{min-height:220px;max-height:500px;overflow:auto;padding:8px 20px 20px;background:#f8fafc}
      #${MODAL_ID} .v1-industry-contact{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:14px 20px;border-top:1px solid #e5c900;background:#fff9c4}
      #${MODAL_ID} .v1-industry-contact-text{color:#3b2f00;font-size:13px;font-weight:850;line-height:1.5}
      #${MODAL_ID} .v1-industry-contact-button{flex:none;border:1px solid #e6c200;border-radius:999px;background:#fee500;padding:10px 16px;color:#191919;font-size:13px;font-weight:950;cursor:pointer;box-shadow:0 5px 14px rgba(80,65,0,.16)}
      #${MODAL_ID} .v1-industry-contact-button:hover{background:#f7dc00}
      #${MODAL_ID} .v1-industry-empty{padding:42px 12px;text-align:center;color:#64748b;font-size:14px;font-weight:800}
      #${MODAL_ID} .v1-industry-request-wrap{display:grid;gap:12px;justify-items:center;padding:34px 16px;text-align:center}
      #${MODAL_ID} .v1-industry-request-title{color:#0f172a;font-size:16px;font-weight:950}
      #${MODAL_ID} .v1-industry-request-desc{max-width:460px;color:#64748b;font-size:13px;font-weight:700;line-height:1.6}
      #${MODAL_ID} .v1-industry-request-button{border:1px solid #e6c200;border-radius:999px;background:#fee500;padding:11px 18px;color:#191919;font-size:13px;font-weight:950;cursor:pointer;box-shadow:0 5px 14px rgba(80,65,0,.16)}
      #${MODAL_ID} .v1-industry-request-button:hover{background:#f7dc00}
      #${MODAL_ID} .v1-industry-group{margin:14px 2px 5px;color:#0e7490;font-size:12px;font-weight:950;letter-spacing:.02em}
      #${MODAL_ID} .v1-industry-result{display:flex;width:100%;align-items:center;justify-content:space-between;gap:14px;margin-top:7px;border:1px solid #cbd5e1;border-radius:15px;background:#fff;padding:13px 15px;color:#0f172a;text-align:left;cursor:pointer}
      #${MODAL_ID} .v1-industry-result:hover,#${MODAL_ID} .v1-industry-result.is-active{border-color:#06b6d4;background:#ecfeff;box-shadow:0 8px 22px rgba(8,145,178,.12)}
      #${MODAL_ID} .v1-industry-result strong{font-size:15px;font-weight:950}
      #${MODAL_ID} .v1-industry-select-label{flex:none;border-radius:999px;background:#cffafe;padding:6px 10px;color:#0e7490;font-size:11px;font-weight:950}
      @media(max-width:560px){.v1-industry-picker{grid-template-columns:1fr}.v1-industry-picker-button{min-height:44px}#${MODAL_ID}{padding:10px}#${MODAL_ID} .v1-industry-dialog{border-radius:19px}#${MODAL_ID} .v1-industry-head{padding:18px 17px 14px}#${MODAL_ID} .v1-industry-search-box,#${MODAL_ID} .v1-industry-results{padding-left:14px;padding-right:14px}}
    `;
    document.head.appendChild(style);
  }

  function getItems(field){
    const items = [];
    Array.from(field.options || []).forEach(option => {
      const value = clean(option.value);
      const label = clean(option.textContent);
      if (!value || !label) return;
      const parent = option.parentElement;
      const group = parent && parent.tagName === 'OPTGROUP' ? clean(parent.label) : '기타';
      items.push({value, label, group});
    });
    return items;
  }

  function authHeaders(){
    try {
      const token = clean(window.localStorage?.getItem('storymaker_token'));
      return token ? {Authorization: `Bearer ${token}`} : {};
    } catch (_error) {
      return {};
    }
  }

  async function loadDatabaseItems(){
    if (databaseItems.length) return databaseItems;
    if (databaseLoadPromise) return databaseLoadPromise;
    databaseLoadPromise = fetch(INDUSTRY_API, {
      credentials: 'include',
      headers: authHeaders()
    })
      .then(async response => {
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload.ok === false) {
          throw new Error(payload.detail || payload.message || '업종 목록을 불러오지 못했습니다.');
        }
        const source = Array.isArray(payload.data) ? payload.data : [];
        databaseItems = source
          .map(item => ({
            value: clean(item.industry_key),
            label: clean(item.label || item.industry_key),
            group: clean(item.category || '공통')
          }))
          .filter(item => item.value && item.label);
        return databaseItems;
      })
      .catch(error => {
        console.warn('[StoryMaker] 업종 DB 검색 연동 실패, 화면 기본 목록을 사용합니다.', error);
        return [];
      })
      .finally(() => {
        databaseLoadPromise = null;
      });
    return databaseLoadPromise;
  }

  function ensureFieldOption(field, item){
    if (!field || !item?.value) return;
    let option = Array.from(field.options || []).find(candidate => candidate.value === item.value);
    if (!option) {
      let group = Array.from(field.querySelectorAll('optgroup')).find(candidate => clean(candidate.label) === item.group);
      if (!group) {
        group = document.createElement('optgroup');
        group.label = item.group || '공통';
        field.appendChild(group);
      }
      option = document.createElement('option');
      option.value = item.value;
      option.textContent = item.label;
      group.appendChild(option);
    }
  }

  function ensureModal(){
    let modal = document.getElementById(MODAL_ID);
    if (modal) return modal;
    ensureStyle();
    modal = document.createElement('div');
    modal.id = MODAL_ID;
    modal.setAttribute('aria-hidden', 'true');
    modal.innerHTML = `
      <div class="v1-industry-dialog" role="dialog" aria-modal="true" aria-labelledby="v1-industry-title">
        <div class="v1-industry-head">
          <div><h2 id="v1-industry-title">업종 검색</h2><p class="v1-industry-description">업종명이나 관련 단어를 입력하고 정확한 업종을 선택하세요.</p></div>
          <button type="button" class="v1-industry-close" aria-label="닫기">×</button>
        </div>
        <div class="v1-industry-search-box">
          <input type="search" class="v1-industry-query" autocomplete="off" placeholder="예: 인테리어, 카페, 배관, 안경원">
          <p class="v1-industry-help">검색어 없이 열면 전체 업종을 그룹별로 확인할 수 있습니다.</p>
        </div>
        <div class="v1-industry-results"></div>
        <div class="v1-industry-contact">
          <div class="v1-industry-contact-text">찾는 업종이 없나요?<br>카카오톡 채널로 업종 추가를 요청해 주세요.</div>
          <button type="button" class="v1-industry-contact-button">카카오톡 문의</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    modal.querySelector('.v1-industry-close').addEventListener('click', closeModal);
    modal.addEventListener('mousedown', event => { if (event.target === modal) closeModal(); });
    const query = modal.querySelector('.v1-industry-query');
    modal.querySelector('.v1-industry-contact-button')?.addEventListener('click', () => requestMissingIndustry(query.value));
    query.addEventListener('input', renderResults);
    query.addEventListener('keydown', event => {
      const buttons = Array.from(modal.querySelectorAll('button.v1-industry-result'));
      if (event.key === 'Escape') { event.preventDefault(); closeModal(); return; }
      if (!buttons.length) return;
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        activeIndex = event.key === 'ArrowDown'
          ? Math.min(buttons.length - 1, activeIndex + 1)
          : Math.max(0, activeIndex - 1);
        buttons.forEach((button, index) => button.classList.toggle('is-active', index === activeIndex));
        buttons[activeIndex]?.scrollIntoView({block:'nearest'});
      } else if (event.key === 'Enter' && activeIndex >= 0) {
        event.preventDefault();
        buttons[activeIndex]?.click();
      }
    });
    return modal;
  }

  function setNativeValue(element, value){
    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')?.set;
    if (setter) setter.call(element, value); else element.value = value;
  }

  function commit(item){
    if (!currentField) return;
    ensureFieldOption(currentField, item);
    currentField.dataset.v1IndustrySelectedValue = item.value;
    currentField.dataset.v1IndustrySelectedLabel = item.label;
    setNativeValue(currentField, item.value);
    if (currentDisplay) currentDisplay.value = item.label;
    currentField.dispatchEvent(new Event('input', {bubbles:true}));
    currentField.dispatchEvent(new Event('change', {bubbles:true}));
    closeModal();
  }

  async function requestMissingIndustry(query){
    const requestedIndustry = clean(query) || '목록에 없는 업종';
    const message = `스토리메이커 업종 추가 요청\n요청 업종: ${requestedIndustry}`;
    try {
      await navigator.clipboard?.writeText?.(message);
    } catch (_error) {
      // 클립보드 권한이 없어도 카카오톡 채널은 정상적으로 엽니다.
    }
    window.open(KAKAO_CHANNEL_URL, '_blank', 'noopener,noreferrer');
    closeModal();
  }

  function renderResults(){
    const modal = ensureModal();
    const query = clean(modal.querySelector('.v1-industry-query').value).toLowerCase();
    const results = modal.querySelector('.v1-industry-results');
    const items = databaseItems.length ? databaseItems : (currentField ? getItems(currentField) : []);
    const filtered = items.filter(item => !query || `${item.group} ${item.label} ${item.value}`.toLowerCase().includes(query));
    results.innerHTML = '';
    activeIndex = -1;
    if (!filtered.length) {
      results.innerHTML = '<div class="v1-industry-request-wrap"><div class="v1-industry-request-title">찾는 업종이 목록에 없습니다.</div><div class="v1-industry-request-desc">카카오톡 채널에서 추가할 업종명을 보내주세요. 입력한 검색어는 복사를 시도한 뒤 채널을 새 창으로 엽니다.</div><button type="button" class="v1-industry-request-button">카카오톡 채널 문의</button></div>';
      results.querySelector('.v1-industry-request-button')?.addEventListener('click', () => requestMissingIndustry(query));
      return;
    }
    let lastGroup = '';
    filtered.forEach(item => {
      if (item.group !== lastGroup) {
        const heading = document.createElement('div');
        heading.className = 'v1-industry-group';
        heading.textContent = item.group;
        results.appendChild(heading);
        lastGroup = item.group;
      }
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'v1-industry-result';
      button.innerHTML = `<strong>${escapeHtml(item.label)}</strong><span class="v1-industry-select-label">선택</span>`;
      button.addEventListener('click', () => commit(item));
      results.appendChild(button);
    });
  }

  async function openModal(field, display){
    currentField = field;
    currentDisplay = display;
    const modal = ensureModal();
    const query = modal.querySelector('.v1-industry-query');
    const results = modal.querySelector('.v1-industry-results');
    query.value = '';
    modal.classList.add('is-open');
    modal.setAttribute('aria-hidden', 'false');
    document.documentElement.style.overflow = 'hidden';
    results.innerHTML = '<div class="v1-industry-empty">DB에서 전체 업종을 불러오는 중입니다.</div>';
    await loadDatabaseItems();
    if (currentField !== field || !modal.classList.contains('is-open')) return;
    renderResults();
    setTimeout(() => query.focus(), 30);
  }

  function closeModal(){
    const modal = document.getElementById(MODAL_ID);
    if (!modal) return;
    modal.classList.remove('is-open');
    modal.setAttribute('aria-hidden', 'true');
    document.documentElement.style.overflow = '';
    currentDisplay?.focus?.();
    currentField = null;
    currentDisplay = null;
    activeIndex = -1;
  }

  function directLabelText(label){
    return Array.from(label?.childNodes || [])
      .filter(node => node.nodeType === Node.TEXT_NODE)
      .map(node => node.textContent || '')
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function eligible(field){
    if (!field || field.tagName !== 'SELECT' || field.dataset[BOUND] === '1') return false;
    const label = field.closest('label');
    if (!label || !/^업종\s*$/.test(directLabelText(label))) return false;
    return getItems(field).length > 0;
  }

  function syncDisplay(field){
    if (!field || field.dataset[BOUND] !== '1') return;
    const wrap = field.closest('.v1-industry-picker');
    const display = wrap?.querySelector('.v1-industry-picker-display');
    if (!display) return;
    const rememberedValue = clean(field.dataset.v1IndustrySelectedValue);
    const rememberedLabel = clean(field.dataset.v1IndustrySelectedLabel);
    if (rememberedValue && rememberedLabel) ensureFieldOption(field, {value: rememberedValue, label: rememberedLabel, group: '선택한 업종'});
    const selectedLabel = rememberedLabel || clean(field.selectedOptions?.[0]?.textContent || field.value);
    if (display.value !== selectedLabel) display.value = selectedLabel;
  }

  function bind(field){
    if (field?.dataset?.[BOUND] === '1') {
      syncDisplay(field);
      return;
    }
    if (!eligible(field)) return;
    field.dataset[BOUND] = '1';
    ensureStyle();
    const wrap = document.createElement('div');
    wrap.className = 'v1-industry-picker';
    const display = document.createElement('input');
    display.type = 'text';
    display.readOnly = true;
    display.className = `${field.className || ''} v1-industry-picker-display`;
    display.placeholder = '업종 검색 버튼을 눌러 선택하세요';
    display.value = clean(field.selectedOptions?.[0]?.textContent || field.value);
    display.setAttribute('aria-label', '선택한 업종');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'v1-industry-picker-button';
    button.textContent = '업종 검색';
    field.parentNode.insertBefore(wrap, field);
    wrap.append(display, button, field);
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
    field.addEventListener('change', () => {
      display.value = clean(field.selectedOptions?.[0]?.textContent || field.value);
    });
  }

  function scan(root){
    const scope = root || document;
    scope.querySelectorAll?.('label select').forEach(bind);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => scan(document), {once:true});
  } else {
    scan(document);
  }
  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node.nodeType !== 1) return;
    if (node.matches?.('select')) bind(node);
    scan(node);
  }))).observe(document.documentElement, {childList:true, subtree:true});
  window.setInterval(() => {
    document.querySelectorAll('[data-v1-industry-search-bound="1"]').forEach(syncDisplay);
  }, 300);
})();
