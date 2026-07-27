(() => {
  'use strict';
  if (window.__STORYMAKER_ADMIN_MEMBER_KO__) return;
  window.__STORYMAKER_ADMIN_MEMBER_KO__ = true;

  const PANEL_ID = 'storymaker-admin-member-panel';
  const cache = new Map();
  const clean = (v = '') => String(v).replace(/\s+/g, ' ').trim();
  const esc = (v) => String(v ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const toneMap = {professional:'전문가',friendly:'친근함',trustworthy:'신뢰감',calm:'차분함',witty:'재치',clear:'명확함'};
  const industryMap = {general:'일반',home_repair:'집수리',boiler_facility:'보일러·설비',appliance_clean:'가전청소',general_cleaning:'청소',restaurant:'음식점',cafe:'카페',beauty_wellness:'미용·웰니스',car_repair:'자동차 정비',pet_beauty_hotel:'반려동물',real_estate:'부동산',education_academy:'교육·학원',drain_unclog:'하수구·배관'};

  async function loadMeta(userId) {
    if (cache.has(userId)) return cache.get(userId);
    const promise = Promise.all([
      fetch(`/v1-api/admin/members/${userId}/personas`, {credentials:'include'}).then(r => r.json()).catch(() => ({})),
      fetch(`/v1-api/admin/members/${userId}/billing-summary`, {credentials:'include'}).then(r => r.json()).catch(() => ({})),
    ]).then(([p,b]) => {
      const personas = Array.isArray(p?.data?.personas) ? p.data.personas : [];
      const primary = personas.find(x => x?.is_default) || personas[0] || null;
      return {user:p?.data?.user || {}, personas, primary, billing:b?.data || {}};
    });
    cache.set(userId, promise);
    return promise;
  }

  function statusOf(meta) {
    const role = clean(meta?.user?.role).toLowerCase();
    if (role === 'admin' || role === 'administrator' || role === '관리자') return {text:'관리자', cls:'sm-status-admin'};
    const code = clean(meta?.billing?.plan_code || meta?.user?.tier || 'free').toLowerCase();
    if (code && code !== 'free') return {text:`유료 · ${meta?.billing?.plan_name || 'Starter'}`, cls:'sm-status-paid'};
    return {text:'무료', cls:'sm-status-free'};
  }

  function setText(el, text) { if (el && clean(el.textContent) !== text) el.textContent = text; }

  async function rebuildRows(panel) {
    const tbody = panel.querySelector('#sm-member-tbody');
    if (!tbody || tbody.dataset.koBusy === '1') return;
    const rows = [...tbody.querySelectorAll('tr')].filter(row => row.querySelector('.sm-row-check'));
    if (!rows.length) return;
    if (rows.every((row) => row.children.length === 9 && row.dataset.memberUserId)) {
      applyFilters(panel);
      return;
    }
    tbody.dataset.koBusy = '1';
    let free=0, paid=0, admins=0, withPersona=0;
    for (const row of rows) {
      const cells = [...row.children];
      if (cells.length < 10) continue;
      const userId = Number(cells[5]?.textContent);
      if (!Number.isFinite(userId)) continue;
      const username = clean(cells[3]?.textContent) || '-';
      const personaCount = Number(clean(cells[6]?.textContent) || 0);
      const projects = Number(clean(cells[7]?.textContent) || 0);
      const lastLogin = clean(cells[8]?.textContent) || '-';
      const meta = await loadMeta(userId);
      const st = statusOf(meta);
      if (st.text === '관리자') admins += 1; else if (st.text.startsWith('유료')) paid += 1; else free += 1;
      if (personaCount > 0) withPersona += 1;
      const company = clean(meta?.primary?.company_name) || '업체 미등록';
      row.dataset.memberUserId = String(userId);
      row.dataset.memberStatus = st.text === '관리자' ? 'admin' : (st.text.startsWith('유료') ? 'paid' : 'free');
      row.dataset.memberPersona = personaCount > 0 ? 'yes' : 'no';
      row.innerHTML = `
        <td><input class="sm-check sm-row-check" type="checkbox" value="${userId}"></td>
        <td><span class="sm-status ${st.cls}">${esc(st.text)}</span></td>
        <td><button class="sm-user-link" data-user-id="${userId}">${esc(username)}</button></td>
        <td>${esc(company)}${personaCount > 1 ? `<small style="display:block;color:#94a3b8;margin-top:4px">외 ${personaCount-1}개 업체</small>` : ''}</td>
        <td>${userId}</td>
        <td>${personaCount}</td>
        <td>${projects}</td>
        <td>${esc(lastLogin)}</td>
        <td><button class="sm-action sm-primary" data-member-mypage-user-id="${userId}" data-member-key="local:${userId}">상세</button></td>`;
    }
    const total = rows.length;
    const values = {wordpress_linked_ids:total, storymaker_users:free, linked_ids:paid, local_only:admins, wordpress_missing:withPersona, persona_users:Math.max(0,total-withPersona)};
    panel.querySelectorAll('[data-member-summary]').forEach(el => {
      const key = el.dataset.memberSummary;
      if (key in values) el.textContent = Number(values[key]).toLocaleString();
    });
    const cards = [...panel.querySelectorAll('.sm-member-card')];
    const labels = [['전체 회원','StoryMaker 계정'],['무료 회원','Free 요금제'],['유료 회원','Starter 이상'],['관리자','관리 권한'],['업체 등록 회원','업체정보 보유'],['업체 미등록 회원','등록 필요']];
    cards.slice(0,6).forEach((card,i)=>{ const d=card.querySelector('div'); const s=card.querySelector('small'); if(labels[i]){setText(d,labels[i][0]);setText(s,labels[i][1]);}});
    tbody.dataset.koBusy = '0';
    applyFilters(panel);
  }

  function translatePanel(panel) {
    if (!panel.querySelector('#sm-member-ko-style')) {
      const style = document.createElement('style');
      style.id = 'sm-member-ko-style';
      style.textContent = '.sm-member-table th{font-size:14px!important}.sm-member-table td{font-size:16px!important}.sm-user-link,.sm-action{font-size:16px!important}.sm-status{display:inline-flex;align-items:center;padding:5px 10px;border-radius:999px;font-size:14px;font-weight:900}.sm-status-free{background:rgba(59,130,246,.18);color:#bfdbfe}.sm-status-paid{background:rgba(34,197,94,.18);color:#bbf7d0}.sm-status-admin{background:rgba(168,85,247,.20);color:#e9d5ff}';
      panel.prepend(style);
    }
    setText(panel.querySelector('.sm-member-desc'),'StoryMaker 회원의 계정, 대표 업체, 요금제와 프로젝트 현황을 한 화면에서 관리합니다.');
    setText(panel.querySelector('.sm-member-close'),'닫기');
    const search = panel.querySelector('#sm-member-search'); if (search) search.placeholder='아이디·이메일·업체명 검색';
    const st = panel.querySelector('#sm-member-status'); if (st && !st.dataset.ko) { st.innerHTML='<option value="all">전체 회원</option><option value="free">무료 회원</option><option value="paid">유료 회원</option><option value="admin">관리자</option>'; st.dataset.ko='1'; }
    const ps = panel.querySelector('#sm-member-persona'); if (ps && !ps.dataset.ko) { ps.innerHTML='<option value="all">전체 업체상태</option><option value="yes">업체 등록</option><option value="no">업체 미등록</option>'; ps.dataset.ko='1'; }
    setText(panel.querySelector('#sm-member-refresh'),'새로고침');
    setText(panel.querySelector('#sm-member-delete'),'선택 회원 삭제');
    const toolbarStrong = panel.querySelector('.sm-member-toolbar strong'); setText(toolbarStrong,'회원 목록');
    const selected=panel.querySelector('#sm-selected-count'); if(selected && /selected/.test(selected.textContent)) selected.textContent=selected.textContent.replace(/selected/,'명 선택');
    const ths=[...panel.querySelectorAll('.sm-member-table thead th')];
    const heads=['','회원 상태','StoryMaker 계정','대표 업체명','회원번호','업체 수','프로젝트','최근 로그인','관리'];
    if (ths.length === 10) { ths[4].remove(); }
    [...panel.querySelectorAll('.sm-member-table thead th')].forEach((th,i)=>{if(i>0 && heads[i]) setText(th,heads[i]);});
    setText(panel.querySelector('#sm-detail-close'),'닫기');
    const detailTitle=panel.querySelector('#sm-detail-title'); if(detailTitle && /마이페이지|My page/.test(detailTitle.textContent)) detailTitle.textContent=clean(detailTitle.textContent).replace(/마이페이지|My page/g,'회원 상세정보');
  }

  function translateDetail(panel) {
    const body = panel.querySelector('#sm-detail-body'); if (!body) return;
    const replacements = new Map([
      ['MY PAGE','회원 상세'],['마이페이지','회원 상세정보'],['Company','업체명'],['Phone','전화번호'],['Website','홈페이지/SNS'],['Region','지역'],['Industry','업종'],['Default style','기본 작성 채널'],['Blog length','블로그 글 길이'],['Default tones','기본 감성 톤'],['Keywords, comma separated','핵심 키워드'],['Business detail','페르소나 상세 설명'],['Use as default business','대표 업체로 사용'],['Free 20회','무료 20회'],['inactive','무료'],['active','활성'],['Close','닫기']
    ]);
    body.querySelectorAll('label,span,div,h2,h3,button,option,small,strong').forEach(el=>{
      const t=clean(el.textContent); if(replacements.has(t)) el.textContent=replacements.get(t);
      if(toneMap[t]) el.textContent=toneMap[t];
      if(industryMap[t]) el.textContent=industryMap[t];
      if(t==='My page') el.textContent='상세';
    });
    body.querySelectorAll('.sm-user-meta').forEach((el) => {
      const text = clean(el.textContent);
      if (text.includes('WP ID')) {
        const localMatch = text.match(/Local ID\s*(\d+)/i);
        el.textContent = localMatch ? `회원번호 ${localMatch[1]}` : '';
      }
    });
    body.querySelectorAll('select[data-billing-plan] option').forEach(opt=>{
      const code=clean(opt.value).toLowerCase();
      if(code==='free') opt.textContent='무료 · 0원';
      if(code==='starter') opt.textContent='Starter · 월 4,500원';
      if(!['free','starter'].includes(code)) opt.hidden=true;
    });
    const billing=body.querySelector('.sm-billing-box');
    if(billing){
      const starter=clean(billing.querySelector('[data-billing-plan]')?.value).toLowerCase()==='starter';
      const addon=billing.querySelector('[data-billing-addon]'); if(addon) addon.hidden=true;
      const freeBtn=billing.querySelector('[data-billing-free-credit]'); if(freeBtn){ freeBtn.textContent='무료 20회 추가 지급'; freeBtn.hidden=starter; }
      if(starter && !billing.querySelector('[data-first-month-note]')) billing.insertAdjacentHTML('beforeend','<div data-first-month-note class="sm-user-meta" style="margin-top:10px;color:#bbf7d0;font-weight:900">첫 1개월은 한도 없이 사용하며 실제 사용량만 모니터링합니다.</div>');
    }
    if (!body.querySelector('[data-member-delete-one]') && Number.isFinite(Number(window.__smCurrentDeleteUserId))) {
      const actions=body.querySelector('.sm-detail-actions') || body;
      const btn=document.createElement('button'); btn.type='button'; btn.className='sm-action sm-danger'; btn.dataset.memberDeleteOne='1'; btn.textContent='회원 삭제';
      btn.addEventListener('click',()=>deleteOne(panel,Number(window.__smCurrentDeleteUserId)));
      actions.appendChild(btn);
    }
  }

  async function deleteOne(panel,userId){
    const row=panel.querySelector(`tr[data-member-user-id="${userId}"]`); const name=clean(row?.children?.[2]?.textContent)||String(userId); const company=clean(row?.children?.[3]?.textContent)||'업체 미등록';
    if(!confirm(`${name} 회원을 삭제하시겠습니까?\n\n대표 업체: ${company}\n\nStoryMaker 로컬 계정과 연결 데이터가 삭제됩니다. WordPress 계정은 삭제하지 않습니다.`)) return;
    const r=await fetch('/v1-api/admin/users/bulk-delete',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_ids:[userId]})});
    const p=await r.json().catch(()=>({})); if(!r.ok||p.ok===false){alert(p.detail||p.message||'회원 삭제에 실패했습니다.');return;} alert(p.message||'회원을 삭제했습니다.'); panel.querySelector('#sm-member-detail').hidden=true; cache.delete(userId); panel.querySelector('#sm-member-refresh')?.click();
  }

  function applyFilters(panel) {
    const status = panel.querySelector('#sm-member-status')?.value || 'all';
    const persona = panel.querySelector('#sm-member-persona')?.value || 'all';
    let shown = 0;
    panel.querySelectorAll('#sm-member-tbody tr[data-member-user-id]').forEach((row) => {
      const statusOk = status === 'all' || row.dataset.memberStatus === status;
      const personaOk = persona === 'all' || row.dataset.memberPersona === persona;
      row.hidden = !(statusOk && personaOk);
      if (!row.hidden) shown += 1;
    });
    const statusText = panel.querySelector('#sm-member-status-text');
    if (statusText) statusText.textContent = `전체 ${panel.querySelectorAll('#sm-member-tbody tr[data-member-user-id]').length.toLocaleString()}명 중 ${shown.toLocaleString()}명을 표시합니다.`;
  }

  function bind(panel){
    if(panel.dataset.koBound==='1') return; panel.dataset.koBound='1';
    panel.addEventListener('click',e=>{ const b=e.target.closest('[data-member-mypage-user-id],[data-user-id]'); if(b) window.__smCurrentDeleteUserId=Number(b.dataset.memberMypageUserId||b.dataset.userId); });
    panel.addEventListener('change',(event)=>{
      if (event.target?.id === 'sm-member-status' || event.target?.id === 'sm-member-persona') {
        event.stopImmediatePropagation();
        applyFilters(panel);
        return;
      }
      setTimeout(()=>{rebuildRows(panel).then(()=>applyFilters(panel));},0);
    }, true);
  }

  let observerTimer = null;
  const observer=new MutationObserver(()=>{
    if (observerTimer) return;
    observerTimer = setTimeout(() => {
      observerTimer = null;
      const panel=document.getElementById(PANEL_ID); if(!panel) return;
      bind(panel);
      translatePanel(panel);
      rebuildRows(panel).then(() => translateDetail(panel));
    }, 80);
  });
  observer.observe(document.documentElement,{subtree:true,childList:true});
})();
