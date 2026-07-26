(function(){
  var KEY = 'storymaker_user_write_settings';
  var TONES = ['따뜻함','전문가','친근함','신뢰감','현장감','진정성','차분함','활기','고급스러움','담백함'];

  function $(s, r){ return (r || document).querySelector(s); }
  function $all(s, r){ return Array.prototype.slice.call((r || document).querySelectorAll(s)); }

  function read(){
    try { return JSON.parse(localStorage.getItem(KEY) || '{}'); }
    catch(e){ return {}; }
  }

  function write(v){ localStorage.setItem(KEY, JSON.stringify(v || {})); }

  function labelOf(sel){
    var el = $(sel);
    if(!el) return '';
    var op = el.options && el.selectedIndex >= 0 ? el.options[el.selectedIndex] : null;
    return op ? (op.textContent || op.value) : (el.value || '');
  }

  function setVal(sel, v){
    var el = $(sel);
    if(el && v){
      el.value = v;
      el.dispatchEvent(new Event('change', {bubbles:true}));
      el.dispatchEvent(new Event('input', {bubbles:true}));
    }
  }

  function addCss(){
    if($('#uscStyle')) return;
    var s = document.createElement('style');
    s.id = 'uscStyle';
    s.textContent = [
      '.usc-summary{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:8px 0 10px;padding:16px 18px;border:1px solid rgba(56,189,248,.28);border-radius:18px;background:rgba(15,23,42,.66)}',
      '.usc-summary-main{display:grid;gap:4px;min-width:0;flex:1}',
      '.usc-env-chip{display:grid;gap:3px;min-width:0}',
      '.usc-env-chip b{color:#80c2ff;font-size:12px;font-weight:900}',
      '.usc-env-chip span{color:#f8fbff;font-size:13px;font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
      '.usc-profile-compact{display:flex;align-items:center;gap:6px;min-width:0;color:#dbeafe;font-size:13px;font-weight:800}',
      '.usc-profile-compact strong{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
      '.usc-profile-compact span{color:#7f8da3;font-size:12px}',
      '.usc-summary button{width:auto!important;min-width:64px!important;padding:9px 14px!important;border-radius:12px!important;background:rgba(15,23,42,.62)!important;border:1px solid rgba(148,163,184,.28)!important;color:#dbeafe!important;font-size:12px!important;font-weight:900!important}',
      '#input-card{margin-top:0!important}',
      '.workspace{gap:14px!important}',
      '.heading-with-help{justify-content:space-between!important;gap:12px!important;margin-bottom:8px!important}',
      '.heading-with-help .step-label-inline{white-space:nowrap}',
      '.heading-with-help #accordion-icon{margin-left:auto!important}',
      '.usc-hidden-main{display:none!important}',
      '.usc-mypage-box{margin:0 0 18px;border:1px solid rgba(56,189,248,.24);border-radius:16px;background:rgba(15,23,42,.45);overflow:visible;min-height:68px}',
      '.usc-mypage-box.collapsed{height:auto!important}',
      '.usc-mypage-box.collapsed .usc-head{min-height:68px!important}',
      '.usc-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:18px 16px;cursor:pointer;min-height:68px;box-sizing:border-box}',
      '.usc-head h4{margin:0;color:#fff;font-size:15px}',
      '.usc-head span{color:#9aa7c0;font-size:12px}',
      '.usc-body{display:block;padding:0 16px 16px}',
      '.usc-mypage-box.collapsed .usc-body{display:none}',
      '.usc-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}',
      '.usc-grid.two{grid-template-columns:1fr 1fr}',
      '.usc-mypage-box label{display:block;font-size:12px;color:#aab8cc;margin:0 0 6px;font-weight:800}',
      '.usc-mypage-box input,.usc-mypage-box select{width:100%;background:#252d3b;border:1px solid #3a455a;color:#e2e8f0;border-radius:10px;padding:10px 12px}',
      '.usc-tone-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:10px}',
      '.usc-tone{display:flex!important;align-items:center;justify-content:center;min-height:38px;padding:9px 8px!important;border-radius:999px!important;border:1px solid rgba(148,163,184,.28)!important;background:rgba(15,23,42,.58)!important;color:#cbd5e1!important;font-size:12px!important;font-weight:800!important;cursor:pointer}',
      '.usc-tone input{display:none}',
      '.usc-tone:has(input:checked){background:rgba(14,165,233,.22)!important;border-color:rgba(56,189,248,.65)!important;color:#fff!important}',
      '.usc-mypage-actions{display:flex;justify-content:flex-end;margin-top:12px}',
      '.usc-mypage-actions button{width:auto!important;padding:9px 14px!important}',
      '.usc-next-ai-wrap{display:flex;justify-content:center;margin:18px 0 0}',
      '.usc-next-ai-btn{width:min(520px,78%)!important;padding:14px 22px!important;border-radius:16px!important;background:linear-gradient(135deg,#06b6d4,#2563eb 52%,#7c3aed)!important;border:1px solid rgba(103,232,249,.72)!important;color:#fff!important;font-size:15px!important;font-weight:950!important;box-shadow:0 14px 32px rgba(37,99,235,.34),0 0 24px rgba(34,211,238,.22)!important}',
      '.usc-next-ai-btn:hover{filter:brightness(1.08)!important;transform:translateY(-2px)!important}',
      '@media(max-width:760px){.usc-summary{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:8px 12px;margin:6px 0 8px;padding:11px 13px}.usc-summary-main{min-width:0;display:grid;gap:4px}.usc-env-chip{min-width:0;gap:2px}.usc-env-chip b{font-size:12px}.usc-env-chip span{font-size:13px;line-height:1.35}.usc-profile-compact{font-size:12px;line-height:1.3;max-width:100%;overflow:visible;flex-wrap:wrap}.usc-profile-compact strong{max-width:none;flex:0 1 auto}.usc-summary button{width:auto!important;min-width:54px!important;height:32px!important;padding:0 11px!important;align-self:center}.usc-next-ai-btn{width:100%!important}.usc-grid,.usc-grid.two{grid-template-columns:1fr}.usc-tone-grid{grid-template-columns:1fr 1fr}}'
    ].join('');
    document.head.appendChild(s);
  }

  function findControlBlock(){
    var style = $('#style'), ai = $('#ai_preset');
    if(!style && !ai) return null;
    return (style && (style.closest('.input-row') || style.closest('.form-group'))) ||
      (ai && (ai.closest('.input-row') || ai.closest('.form-group')));
  }

  function hideMainControls(){
    [$('#style'), $('#ai_preset')].forEach(function(el){
      var box = el && (el.closest('.input-row') || el.closest('.form-group'));
      if(box) box.classList.add('usc-hidden-main');
    });
    $all('.tone-checkbox-label').forEach(function(el){
      var box = el.closest('.form-group') || el.parentElement;
      if(box) box.classList.add('usc-hidden-main');
    });
  }

  function summaryText(){
    var st = read();
    var region = [st.sido, st.sigungu, st.eupmyeon].filter(Boolean).join(' ') || labelOf('#ai_preset') || '지역 미설정';
    var style = (st.styleLabel || labelOf('#style') || '스토리형').replace(' (기본)', '');
    var tone = (st.tones && st.tones.length ? st.tones : ['따뜻함','전문가']).join('/');
    return region + ' · ' + style + ' · ' + tone;
  }

  function cleanProfileValue(v){
    v = String(v || '').trim();
    if(!v) return '';
    if(/마이페이지|등록\s*필요|미등록|상세\s*설명|업체명|전화번호/i.test(v)) return '';
    return v;
  }

  function currentProfile(){
    var personas = window.myPersonas || [];
    var p = personas.find(function(x){ return x && x.is_default; }) || personas[0] || null;
    var company = cleanProfileValue(p && (p.company_name || p.company || p.name)) ||
      cleanProfileValue(($('#company') || {}).value) ||
      cleanProfileValue(($('#active-persona-company-display') || {}).textContent) ||
      cleanProfileValue(($('#profile-company-summary') || {}).textContent) ||
      '업체명 미등록';
    var phone = cleanProfileValue(p && (p.phone_number || p.phone || p.tel)) ||
      cleanProfileValue(($('#phone_number') || {}).value) ||
      cleanProfileValue(($('#active-persona-phone-display') || {}).textContent) ||
      cleanProfileValue(($('#profile-phone-summary') || {}).textContent) ||
      '전화번호 미등록';
    return { company: company, phone: phone };
  }

  function profileNeedsRefresh(){
    var p = currentProfile();
    return !((window.myPersonas || []).length) || p.company === '업체명 미등록' || p.phone === '전화번호 미등록';
  }

  async function refreshProfileDb(){
    try {
      if(!profileNeedsRefresh()) return;
      var f = window.fetchWithAuth || fetch;
      var r = await f('/api/auth/personas');
      var j = await r.json();
      if(r.ok && j.ok && Array.isArray(j.data)){
        window.myPersonas = j.data;
        updateSummary();
      }
    } catch(e) {}
  }

  function addSummary(){
    if($('#uscSummary')) return;
    var input = $('#input-card');
    var anchor = (input && input.closest('.workspace')) || input || findControlBlock();
    if(!anchor) return;
    var div = document.createElement('div');
    div.id = 'uscSummary';
    div.className = 'usc-summary';
    div.innerHTML = '<div class="usc-summary-main"><div class="usc-env-chip"><b>기본설정</b><span id="uscSummaryText"></span></div><div class="usc-profile-compact"><strong id="uscSummaryCompany">업체명 미등록</strong><span>/</span><strong id="uscSummaryPhone">전화번호 미등록</strong></div></div><button type="button" id="uscOpenSettings">수정</button>';
    anchor.parentNode.insertBefore(div, anchor);
    $('#uscOpenSettings').onclick = openSettings;
    updateSummary();
  }

  function addNextAiButton(summary){
    if($('#uscNextAiWrap')) return;
    var wrap = document.createElement('div');
    wrap.id = 'uscNextAiWrap';
    wrap.className = 'usc-next-ai-wrap';
    wrap.innerHTML = '<button type="button" id="uscNextAiBtn" class="usc-next-ai-btn">다음 단계: AI 콘텐츠 제작</button>';
    summary.insertAdjacentElement('afterend', wrap);
    $('#uscNextAiBtn').onclick = function(){
      if(window.collapseStoryMakerIntro) window.collapseStoryMakerIntro();
      if(window.openStoryMakerMainSection) window.openStoryMakerMainSection('ai');
      var btn = document.querySelector('.btn-ai-auto') || this;
      setTimeout(function(){
        var target = document.querySelector('.btn-ai-auto') || document.getElementById('workspace-ai') || btn;
        if(target && target.scrollIntoView) target.scrollIntoView({behavior:'smooth', block:'center'});
        if(target && target.focus) target.focus({preventScroll:true});
      }, 120);
      if(typeof window.generateAIContentAutomatically === 'function') window.generateAIContentAutomatically(btn);
    };
  }

  function updateSummary(){
    var el = $('#uscSummaryText');
    if(el) el.textContent = summaryText();
    var p = currentProfile();
    var c = $('#uscSummaryCompany');
    var ph = $('#uscSummaryPhone');
    if(c) c.textContent = p.company;
    if(ph) ph.textContent = p.phone;
  }

  function toneButtons(selected){
    selected = selected && selected.length ? selected : ['따뜻함','전문가'];
    return TONES.map(function(t){
      return '<label class="usc-tone"><input type="checkbox" class="uscToneCheck" value="' + t + '" ' + (selected.indexOf(t) >= 0 ? 'checked' : '') + '>' + t + '</label>';
    }).join('');
  }

  function addMyPageSettings(){
    var modal = $('#mypage-modal');
    if(!modal || $('#uscMyPageBox')) return;
    var st = read();
    var box = document.createElement('div');
    box.id = 'uscMyPageBox';
    box.className = 'usc-mypage-box';
    box.innerHTML = '<div class="usc-head" id="uscHead"><div><h4>글쓰기 기본 설정</h4><span>작업 지역과 콘텐츠 분위기를 저장합니다.</span></div><span id="uscFold">접기</span></div><div class="usc-body"><div class="usc-grid"><div><label>시/도</label><input id="uscSido" placeholder="예: 울산" value="' + (st.sido || '') + '"></div><div><label>시/군/구</label><input id="uscSigungu" placeholder="예: 북구" value="' + (st.sigungu || '') + '"></div><div><label>읍/면/동</label><input id="uscEupmyeon" placeholder="예: 매곡동" value="' + (st.eupmyeon || '') + '"></div></div><div class="usc-grid two" style="margin-top:12px;"><div><label>글쓰기 스타일</label><select id="uscStyleSelect"><option value="스토리형">스토리형</option><option value="대화형">대화형</option><option value="뉴스형">뉴스형</option></select></div><div><label>콘텐츠 감성 복수 선택</label><div class="usc-tone-grid">' + toneButtons(st.tones) + '</div></div></div><div class="usc-mypage-actions"><button type="button" id="uscSaveSettings">설정 저장</button></div></div>';
    (document.getElementById('mypage-settings-section') || modal).insertAdjacentElement('afterbegin', box);
    box.classList.add('collapsed');
    var firstFold = $('#uscFold');
    if(firstFold) firstFold.textContent = '펼치기';
    if(st.styleLabel) $('#uscStyleSelect').value = st.styleLabel;
    $('#uscSaveSettings').onclick = saveSettings;
    $('#uscHead').onclick = function(e){
      if(e.target && e.target.id === 'uscSaveSettings') return;
      box.classList.toggle('collapsed');
      $('#uscFold').textContent = box.classList.contains('collapsed') ? '펼치기' : '접기';
    };
  }

  function saveSettings(){
    var styleSel = $('#uscStyleSelect');
    var selected = $all('.uscToneCheck:checked').map(function(x){ return x.value; });
    var v = {
      sido: ($('#uscSido') || {}).value || '',
      sigungu: ($('#uscSigungu') || {}).value || '',
      eupmyeon: ($('#uscEupmyeon') || {}).value || '',
      styleLabel: styleSel ? styleSel.value : '스토리형',
      styleValue: styleSel ? styleSel.value : '스토리형',
      tones: selected.length ? selected : ['따뜻함','전문가']
    };
    write(v);
    applySettings();
    updateSummary();
    var box = $('#uscMyPageBox');
    if(box){
      box.classList.add('collapsed');
      var f = $('#uscFold');
      if(f) f.textContent = '펼치기';
    }
    alert('글쓰기 기본 설정을 저장했습니다.');
  }

  function applySettings(){
    var st = read();
    if(st.styleLabel) setVal('#style', st.styleLabel);
    var ai = $('#ai_preset');
    if(ai && st.sido){
      for(var i=0; i<ai.options.length; i++){
        if((ai.options[i].textContent || '').indexOf(st.sido) >= 0 || (ai.options[i].value || '').indexOf(st.sido) >= 0){
          ai.selectedIndex = i;
          break;
        }
      }
      ai.dispatchEvent(new Event('change', {bubbles:true}));
    }
  }

  async function openSettings(){
    if(typeof window.showMyPageModal === 'function'){
      await window.showMyPageModal();
    }
    setTimeout(function(){
      if(typeof window.switchMyPageTab === 'function') window.switchMyPageTab('settings');
      addMyPageSettings();
      var box = $('#uscMyPageBox');
      if(box){
        box.classList.remove('collapsed');
        var f = $('#uscFold');
        if(f) f.textContent = '접기';
        box.scrollIntoView({behavior:'smooth', block:'center'});
        box.style.boxShadow = '0 0 0 2px rgba(56,189,248,.75),0 0 30px rgba(56,189,248,.22)';
        setTimeout(function(){ box.style.boxShadow = ''; }, 1800);
      }
    }, 250);
  }

  function boot(){
    addCss();
    addSummary();
    hideMainControls();
    addMyPageSettings();
    applySettings();
    updateSummary();
    refreshProfileDb();
    setTimeout(function(){
      addSummary();
      hideMainControls();
      addMyPageSettings();
      applySettings();
      updateSummary();
      refreshProfileDb();
    }, 1000);
    setInterval(updateSummary, 1200);
  }

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();