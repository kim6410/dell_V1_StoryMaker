(() => {
  'use strict';

  const FIELD_NAME = 'region_alias';
  const BOUND = 'v1RegionAliasBound';
  const originalFetch = window.fetch.bind(window);
  let personaCache = [];

  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();

  function personaFormFor(regionField) {
    return regionField?.closest('form') || null;
  }

  async function hydrate(form, input) {
    if (!form || !input || input.dataset.hydrated === '1') return;
    input.dataset.hydrated = '1';
    try {
      const response = await originalFetch('/v1-api/auth/personas', {
        credentials: 'include',
        cache: 'no-store',
        headers: {Accept: 'application/json'},
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload?.ok === false) return;
      const items = Array.isArray(payload?.data) ? payload.data : [];
      personaCache = items;
      const company = clean(form.querySelector('[name="company_name"]')?.value);
      const region = clean(form.querySelector('[name="region"]')?.value);
      const persona = items.find((item) => clean(item?.company_name) === company && clean(item?.region) === region)
        || items.find((item) => item?.is_default)
        || items[0];
      if (persona && !clean(input.value)) input.value = clean(persona.region_alias);
    } catch (_) {
    }
  }

  function bind(regionField) {
    if (!regionField || regionField.dataset[BOUND] === '1') return;
    const form = personaFormFor(regionField);
    if (!form) return;
    regionField.dataset[BOUND] = '1';

    let input = form.querySelector(`[name="${FIELD_NAME}"]`);
    if (!input) {
      const label = document.createElement('label');
      const sourceLabel = regionField.closest('label');
      label.className = `${sourceLabel?.className || ''} v1-region-alias-field`.trim();
      label.innerHTML = '<span>콘텐츠용 지역명</span><input name="region_alias" maxlength="100" placeholder="예: 봉담읍, 상리"><small>행정 지역명보다 우선 사용하는 지역명</small>';
      const aliasInput = label.querySelector('input');
      const referenceInput = sourceLabel?.querySelector('.v1-region-picker-display') || sourceLabel?.querySelector('input:not([type="hidden"]), select');
      if (aliasInput && referenceInput?.className) {
        aliasInput.className = String(referenceInput.className).replace(/\bv1-region-picker-display\b/g, '').replace(/\s+/g, ' ').trim();
      }
      const regionPicker = regionField.closest('.v1-region-picker') || regionField.parentElement;
      const anchor = regionPicker?.parentElement || form;
      if (regionPicker?.nextSibling) anchor.insertBefore(label, regionPicker.nextSibling);
      else anchor.appendChild(label);
      input = label.querySelector('input');
    }
    hydrate(form, input);
  }

  function scan(root = document) {
    root.querySelectorAll?.('input[name="region"],select[name="region"],[data-v1-region-modal-bound="1"]').forEach(bind);
  }

  window.fetch = async function patchedFetch(input, init) {
    const url = typeof input === 'string' ? input : String(input?.url || '');
    const options = init ? {...init} : {};
    const method = String(options.method || (typeof input !== 'string' ? input?.method : 'GET') || 'GET').toUpperCase();
    if (/\/v1-api\/auth\/personas(?:\/\d+)?(?:\?.*)?$/.test(url) && ['POST', 'PUT', 'PATCH'].includes(method) && typeof options.body === 'string') {
      try {
        const data = JSON.parse(options.body);
        if (!Object.prototype.hasOwnProperty.call(data, FIELD_NAME)) {
          const aliasInput = document.querySelector(`[name="${FIELD_NAME}"]`);
          data[FIELD_NAME] = clean(aliasInput?.value);
          options.body = JSON.stringify(data);
        }
      } catch (_) {
      }
    }
    if (/\/v1-api\/generate-prompt(?:\?.*)?$/.test(url) && method === 'POST' && typeof options.body === 'string') {
      try {
        const data = JSON.parse(options.body);
        if (!clean(data.region_alias)) {
          const company = clean(data.company);
          const region = clean(data.region);
          const persona = personaCache.find((item) => clean(item?.company_name) === company && clean(item?.region) === region)
            || personaCache.find((item) => item?.is_default);
          data.region_alias = clean(persona?.region_alias);
          options.body = JSON.stringify(data);
        }
      } catch (_) {
      }
    }
    return originalFetch(input, options);
  };

  const style = document.createElement('style');
  style.textContent = '.v1-region-alias-field{display:flex;flex-direction:column;gap:7px}.v1-region-alias-field>span{font-weight:800}.v1-region-alias-field small{color:#94a3b8;font-size:12px;line-height:1.5}.v1-region-alias-field input{width:100%;box-sizing:border-box}';
  document.head.appendChild(style);

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => scan(), {once:true});
  else scan();
  new MutationObserver((records) => records.forEach((record) => record.addedNodes.forEach((node) => {
    if (node.nodeType === 1) scan(node);
  }))).observe(document.documentElement, {childList:true, subtree:true});
})();
