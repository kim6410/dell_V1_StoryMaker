(function(){
  var BAD_COMPANY_VALUES = ['우리동네 인테리어','업체 정보','회사명','상호명','울산','북구','호계동','울산 북구','북구 호계동','울산 북구 호계동','현재 지역','스토리형','마이페이지 등록 필요'];
  var lastSyncAt = 0;
  var lastPersona = null;

  function $(selector){ return document.querySelector(selector); }
  function valueOf(selector){
    var el = $(selector);
    return el ? String(el.value || el.textContent || '').trim() : '';
  }
  function setValue(selector, value){
    var el = $(selector);
    if (!el || !value) return;
    if ('value' in el) el.value = value;
    else el.textContent = value;
  }
  function isBadCompany(value){
    value = String(value || '').trim();
    if (!value) return true;
    if (BAD_COMPANY_VALUES.indexOf(value) >= 0) return true;
    if (value.indexOf('등록 필요') >= 0) return true;
    return false;
  }
  function normalizePhone(value){
    value = String(value || '').replace(/·.*$/,'').trim();
    if (!value || value.indexOf('등록 필요') >= 0 || value.indexOf('미등록') >= 0) return '';
    return value;
  }
  function pickPersona(list){
    if (!Array.isArray(list) || !list.length) return null;
    var selectedId = valueOf('#mypage-persona-selector');
    var selected = list.find(function(p){ return String(p.id) === String(selectedId); });
    if (selected && !isBadCompany(selected.company || selected.company_name || selected.business_name)) return selected;
    var valid = list.find(function(p){ return p && !isBadCompany(p.company || p.company_name || p.business_name); });
    return valid || list[0];
  }
  function applyPersona(persona){
    if (!persona) return false;
    var company = String(persona.company || persona.company_name || persona.business_name || '').trim();
    var phone = normalizePhone(persona.phone || persona.phone_number || persona.tel || '');
    if (!isBadCompany(company)) {
      setValue('#company', company);
      var summary = $('#profile-company-summary');
      if (summary) summary.textContent = company;
    }
    if (phone) {
      setValue('#phone_number', phone);
      var phoneSummary = $('#profile-phone-summary');
      if (phoneSummary) phoneSummary.textContent = phone;
    }
    if (persona.industry_key) setValue('#industry_key', persona.industry_key);
    if (persona.keywords) setValue('#keywords', persona.keywords);
    if (persona.content) setValue('#persona', persona.content);
    lastPersona = persona;
    return true;
  }
  function personaEditorOpen(){
    var modal = $('#mypage-modal');
    var section = $('#mypage-persona-section');
    return !!(modal && section && modal.style.display !== 'none' && section.style.display !== 'none');
  }

  async function syncFromDb(force){
    if (personaEditorOpen()) return;
    var now = Date.now();
    if (!force && now - lastSyncAt < 1500) return;
    lastSyncAt = now;

    if (lastPersona) applyPersona(lastPersona);

    try {
      if (typeof window.fetchWithAuth !== 'function') return;
      var response = await window.fetchWithAuth('/api/auth/personas');
      var res = await response.json();
      var list = [];
      if (Array.isArray(res)) list = res;
      else if (Array.isArray(res.data)) list = res.data;
      else if (res.data && Array.isArray(res.data.items)) list = res.data.items;
      var persona = pickPersona(list);
      applyPersona(persona);
    } catch(e) {
      // DB 동기화 실패 시 하드코딩/예시값으로 대체하지 않는다.
    }
  }

  window.syncStoryMakerPersonaFromDb = syncFromDb;

  document.addEventListener('DOMContentLoaded', function(){
    syncFromDb(true);
    setTimeout(function(){ syncFromDb(true); }, 500);
    setTimeout(function(){ syncFromDb(true); }, 1500);
    setTimeout(function(){ syncFromDb(true); }, 3000);
  });

  document.addEventListener('click', function(event){
    var btn = event.target && event.target.closest ? event.target.closest('button') : null;
    if (!btn) return;
    var text = String(btn.textContent || '').replace(/\s+/g,' ').trim();
    if (text.indexOf('AI 자동') >= 0 || text.indexOf('통합 프롬프트') >= 0) {
      syncFromDb(true);
    }
  }, true);

  setInterval(function(){ syncFromDb(false); }, 5000);
})();