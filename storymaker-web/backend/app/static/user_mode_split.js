(function(){
  'use strict';
  var KEY='storymaker_view_mode';
  function q(s,r){return (r||document).querySelector(s)}
  function qa(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))}
  function style(){
    if(q('#sm-mode-style')) return;
    var st=document.createElement('style');
    st.id='sm-mode-style';
    st.textContent='\
    .sm-mode-bar{margin:0 0 18px;padding:0;border:1px solid rgba(34,211,238,.3);border-radius:20px;background:linear-gradient(135deg,rgba(14,165,233,.14),rgba(15,23,42,.86));box-shadow:0 12px 30px rgba(0,0,0,.24);overflow:hidden}.sm-mode-acc-head{display:grid;grid-template-columns:minmax(42px,1fr) minmax(0,auto) minmax(52px,1fr);align-items:center;gap:10px;padding:16px 20px;cursor:pointer;user-select:none}.sm-mode-title-wrap{grid-column:2;display:flex;align-items:center;justify-content:center;gap:10px;min-width:0}.sm-mode-acc-icon{font-size:12px;color:#a8b6cc}.sm-mode-header-nav{grid-column:3;justify-self:end;display:flex;align-items:center;justify-content:flex-end}.sm-mode-bar.collapsed .sm-mode-acc-body{display:none}.sm-mode-bar.collapsed .sm-mode-acc-icon{transform:rotate(-90deg)}.sm-mode-acc-body{padding:0 20px 18px}\
    .sm-mode-top{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:0}.sm-mode-copy{min-width:0}.sm-mode-title-row{display:flex;align-items:center;gap:14px;min-width:0}.sm-mode-title{font-size:19px;font-weight:950;color:#fff;letter-spacing:-.05em}.sm-mode-sub{font-size:13px;color:#b8c7dc;line-height:1.6;margin-top:8px;font-weight:750}.sm-work-header-row{display:grid!important;grid-template-columns:minmax(52px,1fr) minmax(0,auto) minmax(52px,1fr)!important;align-items:center!important;width:100%!important;gap:14px!important}.sm-work-header-main{grid-column:2!important;min-width:0!important;text-align:center!important}.sm-work-header-nav{grid-column:3!important;display:flex!important;justify-content:flex-end!important;align-items:center!important;min-width:52px!important}.sm-work-header-row .home-pill,.sm-work-header-row a[href="/"],.sm-work-header-row a[href="https://mystorymaker.net/"]{display:none!important}.sm-hero-nav-link{display:inline-flex!important;align-items:center!important;justify-content:center!important;width:52px!important;height:52px!important;min-width:52px!important;border-radius:999px!important;border:2px solid rgba(116,104,255,.92)!important;color:#d8eaff!important;text-decoration:none!important;font-size:30px!important;font-weight:950!important;line-height:1!important;background:radial-gradient(circle at 32% 24%,rgba(255,255,255,.34),rgba(72,119,255,.22) 34%,rgba(116,104,255,.12) 58%,rgba(10,17,30,.9) 100%)!important;box-shadow:0 0 16px rgba(116,104,255,.52),0 0 34px rgba(56,189,248,.24),inset 0 1px 0 rgba(255,255,255,.22)!important;position:relative!important;overflow:visible!important;text-shadow:0 0 10px rgba(167,212,255,.8)!important;animation:smHeroArrowPulse 1.75s ease-in-out infinite!important}.sm-hero-nav-link:before{content:"";position:absolute;inset:-12px;border-radius:inherit;background:radial-gradient(circle,rgba(59,130,246,.42) 0,rgba(116,104,255,.22) 38%,transparent 68%);filter:blur(3px);z-index:-1;animation:smHeroArrowShine 1.75s ease-in-out infinite}.sm-hero-nav-link:hover{transform:translateX(3px) scale(1.06)!important;border-color:rgba(167,212,255,1)!important;box-shadow:0 0 22px rgba(116,104,255,.78),0 0 48px rgba(56,189,248,.46),inset 0 1px 0 rgba(255,255,255,.28)!important}@keyframes smHeroArrowPulse{0%,100%{filter:brightness(1);box-shadow:0 0 16px rgba(116,104,255,.52),0 0 34px rgba(56,189,248,.24),inset 0 1px 0 rgba(255,255,255,.22)}50%{filter:brightness(1.22);box-shadow:0 0 24px rgba(116,104,255,.86),0 0 58px rgba(56,189,248,.48),inset 0 1px 0 rgba(255,255,255,.32)}}@keyframes smHeroArrowShine{0%,100%{opacity:.54;transform:scale(.96)}50%{opacity:1;transform:scale(1.08)}}.sm-mode-buttons{display:inline-flex;width:auto;gap:6px;padding:5px;border-radius:999px;background:rgba(15,23,42,.85);border:1px solid rgba(148,163,184,.24)}.sm-mode-buttons button{width:auto!important;min-width:94px;padding:8px 13px!important;border-radius:999px!important;font-size:12px!important;font-weight:900!important;color:#9fb2c9!important;background:transparent!important;border:0!important;box-shadow:none!important;transform:none!important}.sm-mode-buttons button.on{color:#07111f!important;background:linear-gradient(135deg,#e0f2fe,#67e8f9)!important}\
    .sm-quick-flow{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.sm-flow-card{padding:14px;border-radius:16px;border:1px solid rgba(148,163,184,.22);background:rgba(15,23,42,.68);color:#dcecff;cursor:pointer;text-align:left}.sm-flow-card:hover{transform:translateY(-2px);border-color:rgba(103,232,249,.6);background:rgba(30,41,59,.88)}.sm-flow-card strong{display:block;font-size:14px;color:#fff;font-weight:950;margin-bottom:4px}.sm-flow-card span{display:block;font-size:12px;color:#9fb2c9;line-height:1.5}\
	    body.sm-user .sm-hide-user,body.sm-user .admin-only-panel,body.sm-user .console-card,body.sm-user .container .admin-tabs-wrap{display:none!important}body.sm-user .container{max-width:1120px!important}body.sm-user .workspace{grid-template-columns:1fr!important;gap:16px!important}body.sm-user header{margin-bottom:14px!important}body.sm-user .card{border-radius:20px!important}\
    body.sm-user .header-brand h1:after,body.sm-admin .header-brand h1:after{content:"";display:none!important}\
    @media(max-width:760px){.container>header{display:flex!important;flex-direction:column!important;align-items:stretch!important;justify-content:center!important;gap:10px!important}.container>header .header-brand{align-items:center!important;text-align:center!important}.sm-mode-acc-head{display:flex!important;flex-direction:column!important;align-items:center!important;justify-content:center!important;gap:8px!important}.sm-mode-title-wrap{width:100%!important;justify-content:center!important;text-align:center!important}.sm-mode-header-nav{width:100%!important;justify-content:center!important}.sm-work-header-row{display:flex!important;flex-direction:column!important;align-items:center!important;justify-content:center!important;gap:8px!important}.sm-work-header-main{width:100%!important;text-align:center!important}.sm-work-header-nav{width:100%!important;display:flex!important;justify-content:center!important;align-items:center!important;min-width:0!important}.sm-mode-acc-head{padding-top:12px!important;padding-bottom:6px!important}.sm-mode-acc-body{padding-top:0!important;padding-bottom:10px!important}.sm-mode-sub{margin-top:0!important;line-height:1.35!important}.sm-mode-title{font-size:17px!important}.sm-mode-top{flex-direction:column;align-items:stretch}.sm-mode-buttons{display:grid;grid-template-columns:1fr 1fr;width:100%}.sm-mode-buttons button{min-width:0}.sm-quick-flow{grid-template-columns:1fr}.sm-header-podcast-arrow{animation:none!important;box-shadow:none!important;overflow:hidden!important;width:42px!important;min-width:42px!important;height:42px!important;font-size:22px!important;transform:none!important}}';
    document.head.appendChild(st);
  }
  function txt(el){return ((el&&(el.innerText||el.textContent))||'').replace(/\s+/g,' ')}
  function mark(){
    qa('.sm-hide-user').forEach(function(el){el.classList.remove('sm-hide-user')});
	    var adminBtn=q('#btn-admin-tab-dashboard')||q('#btn-admin-tab-analytics')||q('#btn-admin-tab-requests');
	    if(adminBtn&&!adminBtn.closest('#admin-modal')){var r=adminBtn.closest('.card')||adminBtn.closest('section');if(r)r.classList.add('sm-hide-user')}
	    qa('.card,section,.accordion-card').forEach(function(el){
	      if(el.closest('#admin-modal')) return;
	      var t=txt(el);
      if(t.indexOf('Admin Intelligence Console')>-1||t.indexOf('SQLite Database Status')>-1||t.indexOf('Content / Business Engine')>-1||t.indexOf('종합 대시보드')>-1||t.indexOf('사용 통계')>-1||t.indexOf('수정요청 게시판')>-1||t.indexOf('시공사례/컨텐츠 업로드')>-1||t.indexOf('업종별 관리')>-1||t.indexOf('패턴 지식')>-1){
        if(t.indexOf('작업 정보 입력')===-1 && t.indexOf('오늘 작업한 현장 내용')===-1){el.classList.add('sm-hide-user')}
      }
    });
  }
  function ensureHeroArrow(){
    // 2026-07-03 임시 비활성화
    // 우측 원형 화살표(sm-header-podcast-arrow)가 모바일에서 overflow/reflow를 유발하여
    // 화면이 격렬하게 흔들리는 원인으로 확인됨.
    // 흔들림 안정화 검증 전까지 동적 생성 자체를 막는다.
    if(q('#sm-header-podcast-arrow')) return;
    var head=q('.container > header')||q('header');
    if(!head) return;
    head.classList.add('sm-work-header-row');
    var brand=q('.header-brand',head)||head.firstElementChild;
    if(brand) brand.classList.add('sm-work-header-main');
    qa('.home-pill,a[href="/"],a[href="https://mystorymaker.net/"]',head).forEach(function(el){el.style.display='none'});
    var nav=document.createElement('div');
    nav.className='sm-work-header-nav';
    var a=document.createElement('a');
    a.id='sm-header-podcast-arrow';
    a.className='sm-hero-nav-link sm-header-podcast-arrow';
    a.href='/podcast';
    a.setAttribute('aria-label','다음 단계 팟캐스트로 이동');
    a.textContent='→';
    a.onclick=function(){try{sessionStorage.setItem('explicit_nav','true')}catch(e){}};
    nav.appendChild(a);
    head.appendChild(nav);
  }
  function bar(){
    if(q('#sm-mode-bar')) return;
    var wrap=q('.container')||document.body, head=q('header',wrap), b=document.createElement('div');
    b.id='sm-mode-bar';b.className='sm-mode-bar';
    b.innerHTML='<div class="sm-mode-acc-head" id="sm-mode-acc-head"><div class="sm-mode-title-wrap"><span class="sm-mode-acc-icon">▼</span><div class="sm-mode-title">생각을 SNS 콘텐츠로 손쉽게 만들어보세요</div></div><div class="sm-mode-header-nav"><a id="sm-mode-podcast-arrow" class="sm-hero-nav-link sm-header-podcast-arrow" href="/podcast" aria-label="다음 단계 팟캐스트로 이동" onclick="event.stopPropagation();try{sessionStorage.setItem(\'explicit_nav\',\'true\')}catch(e){}">→</a></div></div><div class="sm-mode-acc-body"><div class="sm-mode-top"><div><div class="sm-mode-sub">SNS 콘텐츠 기초자료 입력 → AI 생성 → SNS별 자료 완성</div></div><div class="sm-mode-buttons"><button type="button" id="sm-user-btn">사용자</button><button type="button" id="sm-admin-btn">관리자</button></div></div></div>';
    if(head&&head.parentElement) head.insertAdjacentElement('afterend',b); else wrap.insertBefore(b,wrap.firstChild);
    var accHead=q('#sm-mode-acc-head');
    if(accHead) accHead.onclick=function(){b.classList.toggle('collapsed')};
    q('#sm-user-btn').onclick=function(){mode('user')}; q('#sm-admin-btn').onclick=function(){mode('admin')};
    qa('[data-go]').forEach(function(x){x.onclick=function(){go(x.getAttribute('data-go'))}});
  }
  function go(k){
    var map={input:['textarea[placeholder*="오늘 작업"]','textarea'],make:['#generated-prompt-box','#btn-build-prompt','#generate-prompt-btn'],result:['.tabs-header','.tab-content.active','#generated-prompt-box']};
    var arr=map[k]||[], target=null;for(var i=0;i<arr.length;i++){target=q(arr[i]);if(target)break}if(target)target.scrollIntoView({behavior:'smooth',block:'center'});
  }
  function collapseIntro(){var b=q('#sm-mode-bar');if(b)b.classList.add('collapsed')}
  window.collapseStoryMakerIntro=collapseIntro;
  document.addEventListener('click',function(e){
    if(e.target.closest('.btn-ai-auto')||e.target.closest('button[onclick*="generateAIContentAutomatically"]')){
      collapseIntro();
      if(window.openStoryMakerMainSection) window.openStoryMakerMainSection('ai');
    }
    if(e.target.closest('button[onclick*="parseChatGPTResult"]')){
      collapseIntro();
      if(window.openStoryMakerMainSection) window.openStoryMakerMainSection('sns');
    }
  },true);
  function isAdminUser(){
    try{
      var user=JSON.parse(localStorage.getItem('storymaker_user')||'{}')||{};
      var role=String(user.role||'').toLowerCase();
      var roles=Array.isArray(user.roles)?user.roles.map(function(r){return String(r).toLowerCase()}):[];
      return !!(user.is_admin===true||user.is_admin===1||String(user.is_admin).toLowerCase()==='true'||role==='admin'||role==='administrator'||role==='관리자'||roles.indexOf('admin')>-1||roles.indexOf('administrator')>-1||user.username==='admin');
    }catch(e){return false}
  }
  function applyAdminModeButtons(){
    var box=q('.sm-mode-buttons');
    if(box) box.style.display=isAdminUser()?'':'none';
  }
  function mode(m){
    m=m==='admin'?'admin':'user';localStorage.setItem(KEY,m);
    document.body.classList.toggle('sm-user',m==='user');document.body.classList.toggle('sm-admin',m==='admin');
    var u=q('#sm-user-btn'),a=q('#sm-admin-btn');if(u)u.classList.toggle('on',m==='user');if(a)a.classList.toggle('on',m==='admin');
    applyAdminModeButtons();
  }
  function init(){style();bar();ensureHeroArrow();mark();var p=new URLSearchParams(location.search);mode(p.get('mode')||localStorage.getItem(KEY)||'user');setTimeout(function(){bar();ensureHeroArrow();mark();mode(localStorage.getItem(KEY)||'user')},800)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();

(function(){
  'use strict';
  function hasToken(){ return !!String(localStorage.getItem('storymaker_token') || '').trim(); }
  function isStorymakerPath(){ return String(location.pathname || '').indexOf('/storymaker') >= 0; }
  function refreshPersona(){
    try {
      if (typeof window.syncProfileSummary === 'function') window.syncProfileSummary();
      if (typeof window.syncStoryMakerPersonaFromDb === 'function') window.syncStoryMakerPersonaFromDb(true);
    } catch(e) {}
  }
  function protectHomeReset(){
    if (typeof window.showHomeScreen !== 'function' || window.showHomeScreen.bootGuard === true) return;
    var original = window.showHomeScreen;
    var wrapped = function(){
      if (hasToken() && isStorymakerPath() && window.storymakerBootHydrated) {
        try {
          var adminModal = document.getElementById('admin-modal');
          if (adminModal) adminModal.style.display = 'none';
          if (typeof window.toggleInputCard === 'function') window.toggleInputCard(true);
          if (typeof window.initializeWorkspaceAccordions === 'function') window.initializeWorkspaceAccordions();
          refreshPersona();
        } catch(e) {}
        return;
      }
      return original.apply(this, arguments);
    };
    wrapped.bootGuard = true;
    window.showHomeScreen = wrapped;
  }
  function fixMyPageOpen(){
    window.storymakerOpenMyPageNow = async function(){
      if (typeof window.showMyPageModal === 'function') return await window.showMyPageModal();
      setTimeout(function(){
        if (typeof window.showMyPageModal === 'function') window.showMyPageModal();
      }, 250);
      return false;
    };
  }
  async function recoverCookieSession(){
    try {
      if (String(localStorage.getItem('storymaker_token') || '').trim()) return;
      var response = await fetch('/api/auth/me', { credentials: 'include' });
      if (!response.ok) return;
      var res = await response.json();
      if (!res.ok || !res.data) return;
      localStorage.setItem('storymaker_user', JSON.stringify(res.data));
      var userInfoBar = document.getElementById('user-info-bar');
      if (userInfoBar) userInfoBar.style.display = 'flex';
      var loggedInUser = document.getElementById('logged-in-user');
      if (loggedInUser) loggedInUser.innerText = res.data.username + ' (' + res.data.role + ')';
      var adminBtn = document.getElementById('admin-menu-btn');
      if (adminBtn) adminBtn.style.display = res.data.role === 'admin' ? 'inline-block' : 'none';
      if (typeof window.hydrateWorkspaceAfterAuth === 'function') await window.hydrateWorkspaceAfterAuth();
      if (typeof window.snsAiUnifiedRender === 'function') window.snsAiUnifiedRender();
      refreshPersona();
    } catch(e) {}
  }
  function boot(){
    protectHomeReset();
    fixMyPageOpen();
    recoverCookieSession();
    setTimeout(function(){ protectHomeReset(); fixMyPageOpen(); refreshPersona(); recoverCookieSession(); }, 300);
    setTimeout(function(){ protectHomeReset(); fixMyPageOpen(); refreshPersona(); recoverCookieSession(); }, 1200);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
  window.addEventListener('load', boot);
})();
